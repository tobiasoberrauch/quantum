"""Abschluss eines Laufs: End-to-End-Prüfung, Kostenvergleich, optionales Trimmen,
offizielles Gate und atomares Schreiben.
"""

from __future__ import annotations

import difflib
import os
import shlex
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from kmx.circuit_io import (
    apply_default_mode,
    atomic_write_text,
    unlink_if_present,
    write_circuit,
)
from kmx.config import OFFICIAL_VERIFY_DEFAULT_TIMEOUT_S, env_flag, env_int, env_text
from kmx.cost import COST_RELATIVE_NOISE, compute_metrics, score_estimate
from kmx.crosscheck import kickmix_crosscheck
from kmx.ops import Op
from kmx.score import ScoreReport, invsqrt_score, trim_rotations
from kmx.session import Session
from kmx.verify.oracle import FinalSig

# so viele Zeichen der Verifier-Ausgabe werden höchstens gezeigt
OFFICIAL_VERIFY_OUTPUT_TAIL = 4000
DIFF_CONTEXT_LINES = 2


@dataclass(frozen=True)
class OutputOptions:
    """Schalter des Abschlusses (Kommandozeile). `verify_cmd` None = Befehl aus
    OFFICIAL_VERIFY_CMD; die Umgebung wird erst beim Gate gelesen."""

    no_kickmix: bool = False
    kickmix_full: bool = False
    verify_cmd: str | None = None


class WriteOutcome(Enum):
    """Ergebnis von write_outputs (die Kommandozeile bildet es auf Exit-Codes ab)."""

    WRITTEN = "geschrieben"
    # End-to-End-Prüfung fehlgeschlagen oder Kosten gestiegen
    REJECTED = "abgelehnt"
    # offizieller Verifier fehlt oder lehnt ab
    GATE_BLOCKED = "offizielles Gate"


def official_verifier_shell_command(command: str, candidate_path: str) -> str:
    """Setzt den (shell-sicher zitierten) Kandidatenpfad für {candidate}/{out} ein; ohne
    Platzhalter wird er angehängt."""
    arg = shlex.quote(candidate_path)
    if "{candidate}" in command or "{out}" in command:
        return command.replace("{candidate}", arg).replace("{out}", arg)
    return f"{command} {arg}"


def run_official_verifier(command: str, candidate_path: str) -> tuple[bool, str]:
    """Führt den konfigurierten offiziellen Verifier auf der Kandidatendatei aus.
    {candidate} oder {out} wird durch den Pfad ersetzt; ohne Platzhalter wird er
    angehängt. Der Befehl stammt aus deiner Konfiguration.
    """
    cmd = official_verifier_shell_command(command, candidate_path)
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=env_int(
                "OFFICIAL_VERIFY_TIMEOUT", OFFICIAL_VERIFY_DEFAULT_TIMEOUT_S
            ),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Verifier-Ausführung fehlgeschlagen: {exc}"
    out = (proc.stdout + proc.stderr).strip()[-OFFICIAL_VERIFY_OUTPUT_TAIL:]
    return proc.returncode == 0, out or f"Exit-Code {proc.returncode}"


def hint_trimmable_rotations(session: Session) -> None:
    """Ohne --trim-rotations: nur melden, wie viel das Trimmen bringen würde (der
    Stand bleibt unverändert)."""
    _, st = trim_rotations(
        session.ops, session.layout, session.dom, session.opts.trim_max_ratio
    )
    if st.get("removed"):
        print(
            f"HINWEIS : {st['removed']} feine Rotation(en) liegen unter der "
            "Phasenreserve. Mit --trim-rotations sinkt der Score um weitere "
            f"{100 * (1 - st['score_after'] / st['score_before']):.2f} % "
            "(ändert die Phase innerhalb der Toleranz, ist also keine äquivalente "
            "Umformung)."
        )


def estimated_costs(session: Session) -> tuple[float, float]:
    """Geschätzte Kosten (vorher, nachher) aus den Simulationsmittelwerten - Ersatz,
    wenn kein exakter Score geht."""
    m0, m1 = compute_metrics(session.orig), compute_metrics(session.ops)
    sig0, sig1, rot_weight = session.orig_sig, session.sig, session.opts.rot_weight
    before = score_estimate(
        m0.num_qubits, sig0.tof_mean, sig0.t_mean, sig0.rot_mean, rot_weight
    )
    after = score_estimate(
        m1.num_qubits, sig1.tof_mean, sig1.t_mean, sig1.rot_mean, rot_weight
    )
    return before, after


def report_cost_comparison(
    session: Session, rep_old: ScoreReport | None, untrimmed_sig: FinalSig | None
) -> tuple[float, float]:
    """Druckt VORHER/NACHHER und liefert die Kosten (vorher, nachher): exakt wie der
    offizielle Verifier, wenn beide Berichte vorliegen, sonst geschätzt. `untrimmed_sig`
    ist die Signatur vor einem etwaigen Trimmen.
    """
    rep_new = session.exact_score(session.ops)
    print("VORHER : ", session.status_line(session.orig, session.orig_sig))
    after_sig = session.sig if session.trimmed else untrimmed_sig
    print("NACHHER: ", session.status_line(session.ops, after_sig))
    if rep_old is None or rep_new is None:
        return estimated_costs(session)
    print("Exakt gerechnet wie der offizielle Verifier:")
    print("  vorher : ", rep_old.line())
    print("  nachher: ", rep_new.line())
    return rep_old.score, rep_new.score


def official_gate_accepts(verify_cmd: str, candidate_path: str) -> bool:
    """Offizielles Gate vor dem Schreiben; ohne konfigurierten Verifier nur
    ein Hinweis (und Annahme)."""
    if not verify_cmd:
        print(
            "HINWEIS : Nur lokale Prüfung; kein offizieller Gesamtverifier ausgeführt "
            "(OFFICIAL_VERIFY_CMD / --verify-cmd)."
        )
        return True
    good, verifier_msg = run_official_verifier(verify_cmd, candidate_path)
    print(f"OFFIZIELLER VERIFIER: {'PASS' if good else 'FAIL'} | {verifier_msg}")
    if not good:
        print("ABBRUCH : Kandidat nicht übernommen; Ausgabe bleibt unverändert.")
    return good


def replace_output_after_gate(
    ops: Sequence[Op], out_path: str, verify_cmd: str
) -> bool:
    """Kandidat zuerst in eine Temporärdatei; erst nach dem optionalen
    offiziellen Gate atomar ersetzen. Liefert False (und lässt `out_path`
    unberührt), wenn das Gate ablehnt."""
    out_dir = os.path.dirname(os.path.abspath(out_path)) or "."
    os.makedirs(out_dir, exist_ok=True)
    fd, candidate = tempfile.mkstemp(
        prefix=".kmx-candidate-",
        suffix=os.path.splitext(out_path)[1] or ".kmx",
        dir=out_dir,
    )
    os.close(fd)
    try:
        write_circuit(candidate, ops)
        if not official_gate_accepts(verify_cmd, candidate):
            return False
        apply_default_mode(candidate)
        os.replace(candidate, out_path)
        candidate = ""
    finally:
        if candidate:
            unlink_if_present(candidate)
    return True


def write_unified_diff(
    session: Session, in_path: str, out_path: str, diff_path: str
) -> None:
    """Schreibt den Unified-Diff Original -> Ergebnis (kanonisch
    formatierte Instruktionen) atomar."""
    a, b = [o.fmt() for o in session.orig], [o.fmt() for o in session.ops]
    diff = difflib.unified_diff(
        a, b, fromfile=in_path, tofile=out_path, lineterm="", n=DIFF_CONTEXT_LINES
    )
    atomic_write_text(diff_path, "\n".join(diff) + "\n")


def _final_check_passes(session: Session) -> bool:
    """End-to-End-Prüfung des Ergebnisses gegen das Original (mit Meldung)."""
    ok, msg = session.final_check()
    print(
        "\nEnd-to-End-Prüfung gegen das Original: "
        f"{'BESTANDEN' if ok else 'FEHLGESCHLAGEN'} - {msg}"
    )
    if not ok:
        print(
            "ABBRUCH : Ausgabe wird nicht geschrieben; vorhandene Datei bleibt "
            "unverändert."
        )
    return ok


def _cost_gate_passes(before: float, after: float) -> bool:
    """Meldet das Kosten-Delta; False, wenn die Kosten (über das Rauschen hinaus)
    steigen."""
    change = 100 * (after / before - 1) if before else 0.0
    print(
        f"Kosten-Delta: {after - before:+,.2f} ({change:+.2f} %)"
        + ("" if after < before else "  -> keine Senkung")
    )
    if after > before * (1 + COST_RELATIVE_NOISE):
        print(
            "ABBRUCH : Kandidat erhöht die Kosten; vorhandene Ausgabe bleibt "
            "unverändert."
        )
        return False
    return True


def _resolve_verify_cmd(cli_value: str | None) -> str:
    """Befehl des offiziellen Gates: --verify-cmd, sonst OFFICIAL_VERIFY_CMD
    (leer = kein Gate)."""
    return (cli_value or env_text("OFFICIAL_VERIFY_CMD", "")).strip()


def write_outputs(
    s: Session,
    in_path: str,
    out_path: str,
    diff_path: str | None,
    opts: OutputOptions,
) -> WriteOutcome:
    """Abschluss: End-to-End-Prüfung, exakter Score, optionales Trimmen, offizielles
    Gate, atomares Schreiben (Diff nur zusammen mit der Ausgabe)."""
    if not _final_check_passes(s):
        return WriteOutcome.REJECTED
    untrimmed_sig = s.sig
    rep_old = invsqrt_score(s.orig, s.layout, s.dom)
    if s.opts.trim:
        s.trim_rotations_step()
    elif rep_old is not None:
        hint_trimmable_rotations(s)
    before, after = report_cost_comparison(s, rep_old, untrimmed_sig)
    if not _cost_gate_passes(before, after):
        return WriteOutcome.REJECTED
    if not opts.no_kickmix:
        full = s.dom if (opts.kickmix_full and s.dom.exhaustive) else None
        print(
            kickmix_crosscheck(
                s.orig, s.ops, s.layout, full=full, same_phase=s.trimmed is None
            )
        )
    verify_cmd = _resolve_verify_cmd(opts.verify_cmd)
    if not verify_cmd and env_flag("REQUIRE_OFFICIAL_VERIFY"):
        print("ABBRUCH : REQUIRE_OFFICIAL_VERIFY=1, aber OFFICIAL_VERIFY_CMD fehlt.")
        return WriteOutcome.GATE_BLOCKED
    if not replace_output_after_gate(s.ops, out_path, verify_cmd):
        return WriteOutcome.GATE_BLOCKED
    if diff_path:
        write_unified_diff(s, in_path, out_path, diff_path)
    print(f"Geschrieben: {out_path}" + (f" | Diff: {diff_path}" if diff_path else ""))
    return WriteOutcome.WRITTEN
