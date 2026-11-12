"""Unterbefehl `lab` der Kommandozeile: init, run, status, eval.

`add_lab_subcommand` hängt den Parser an die Unterbefehle von `kmx.cli`; die übrigen
Unterbefehle bleiben unverändert.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable
from typing import Any

from kmx.agent.client import LLMClient
from kmx.circuit_io import read_circuit
from kmx.config import env_text
from kmx.cost import compute_metrics
from kmx.domains import build_domains
from kmx.exit_codes import CLI_EXIT_ERROR, CLI_EXIT_OK, CLI_EXIT_REJECTED
from kmx.lab.claims import EV_LAB, official_passed, safe_id
from kmx.lab.judge import KIND_GENERATOR, KIND_KMX, Judge
from kmx.lab.official import verifier_pin
from kmx.lab.registry import LabConfig, LabError, Registry, now_iso, sha256_file
from kmx.lab.report import counterexample_line, status_report, verifier_pin_line
from kmx.lab.rounds import LabRun, RunOptions
from kmx.lab.spec import INVSQRT_SPEC, generic_spec_text, load_spec, spec_text
from kmx.lab.teams import parse_team_list
from kmx.layout import analyze_layout
from kmx.session import Options, Session

DEFAULT_LAB_ROOT = os.path.join("runs", "lab")
DEFAULT_LAB_NAME = "invsqrt"
DEFAULT_CHECK_ROUNDS = 2
SAMPLE_LANES = 256
FALLBACK_LANES = 65536
SubParsers = argparse._SubParsersAction  # wie in kmx.cli
# austauschbar für Tests (Stub-Client ohne Netzwerk)
make_client: Callable[..., Any] = LLMClient


def _quiet(_: str) -> None:
    return None


def _lab_dir(args: argparse.Namespace) -> str:
    if args.lab_dir:
        return args.lab_dir
    name = safe_id(args.name)
    if name is None:
        raise LabError(f"ungültiger Laborname {args.name!r}")
    return os.path.join(DEFAULT_LAB_ROOT, name)


def build_session(
    path: str,
    input_register: str,
    value_range: str | None,
    max_exhaustive: int,
    check_rounds: int,
    log: Callable[[str], None] = _quiet,
) -> Session:
    """Sitzung der Basis mit vollständiger Domäne (sonst LabError) und Basislauf."""
    ops = read_circuit(path)
    layout = analyze_layout(ops, input_register, value_range)
    dom, sample = build_domains(layout, max_exhaustive, SAMPLE_LANES, FALLBACK_LANES)
    if not dom.exhaustive:
        raise LabError(
            "Keine vollständige Domäne: Das Labor bewertet nur über ALLE Eingaben "
            "(--range LO:HI angeben oder --max-exhaustive erhöhen)."
        )
    s = Session(ops, layout, dom, sample, Options(final_rounds=check_rounds), log)
    s.run_baseline()
    return s


def _verify_cmd(args: argparse.Namespace) -> str | None:
    return getattr(args, "verify_cmd", None) or env_text("OFFICIAL_VERIFY_CMD")


def _open(args: argparse.Namespace) -> tuple[Registry, Judge, LabConfig]:
    reg = Registry.open(_lab_dir(args))
    cfg = reg.config()
    s = build_session(
        reg.baseline_path(),
        cfg.input_register,
        cfg.value_range,
        cfg.max_exhaustive,
        args.check_rounds,
    )
    verify_cmd = _verify_cmd(args)
    judge = Judge(
        s,
        reg,
        args.check_rounds,
        verify_cmd,
        input_register=cfg.input_register,
        value_range=cfg.value_range,
    )
    return reg, judge, cfg


def cmd_lab_init(args: argparse.Namespace) -> int:
    """lab init: Labor anlegen, Basis prüfen, Altbefunde schreiben."""
    lab_dir = _lab_dir(args)
    if os.path.exists(Registry(lab_dir).events_path):
        raise LabError(f"Labor existiert bereits: {os.path.abspath(lab_dir)}")
    if not os.path.exists(args.baseline):
        print(f"Datei nicht gefunden: {args.baseline}")
        return CLI_EXIT_ERROR
    s = build_session(
        args.baseline, args.input_register, args.range, args.max_exhaustive, 2
    )
    if not s.clean:
        print("Basis erfüllt den Kontrakt nicht (Scratch/Register/Phase); kein Labor.")
        return CLI_EXIT_ERROR
    suffix = ".kmb" if args.baseline.lower().endswith(".kmb") else ".kmx"
    verify_cmd = _verify_cmd(args)
    pin = verifier_pin(verify_cmd) if verify_cmd else {}
    cfg = LabConfig(
        name=os.path.basename(os.path.normpath(lab_dir)),
        baseline_file="baseline" + suffix,
        baseline_sha256=sha256_file(args.baseline),
        input_register=args.input_register,
        value_range=args.range,
        max_exhaustive=args.max_exhaustive,
        spec=INVSQRT_SPEC if s.layout.invsqrt else None,
        created=now_iso(),
        verifier_pin=pin or None,
        verifier_command=verify_cmd if pin else None,
    )
    reg = Registry.create(lab_dir, args.baseline, cfg)
    judge = Judge(s, reg, 2, input_register=cfg.input_register, value_range=args.range)
    m = compute_metrics(s.orig)
    reg.append(
        {
            "kind": EV_LAB,
            "action": "baseline",
            "baseline_score": judge.baseline_score,
            "score_kind": judge.baseline_score_kind,
            "q": m.num_qubits,
            "toffoli": m.toffoli,
            "domain": s.dom.label,
        }
    )
    print(f"Labor angelegt: {reg.lab_dir}")
    print(f"Basis: {m.summary()} | Domäne: {s.dom.label}")
    if judge.baseline_score is not None:
        print(f"Basis-Score ({judge.baseline_score_kind}): {judge.baseline_score:,.2f}")
    print(f"{len(reg.claims())} Altbefunde als Behauptungen übernommen.")
    print(verifier_pin_line(cfg.verifier_pin))
    return CLI_EXIT_OK


def _client_and_models(args: argparse.Namespace) -> tuple[Any, list[str]]:
    client = make_client(
        api_url=args.api_url, timeout=args.llm_timeout, max_tokens=args.max_tokens
    )
    models = [m.strip() for m in (args.models or "").split(",") if m.strip()]
    return client, models or client.default_models()


def cmd_lab_run(args: argparse.Namespace) -> int:
    """lab run: CEGIS-Runden mit den Teams."""
    teams = parse_team_list(args.teams)
    client, models = _client_and_models(args)
    if not models:
        print("Kein Modell angegeben (--models oder LLM_MODEL).")
        return CLI_EXIT_ERROR
    max_calls = int(getattr(client, "max_calls", 40))
    if max_calls <= 0:
        print("LLM_MAX_CALLS=0: kein LLM-Aufruf erlaubt, kein Lauf.")
        return CLI_EXIT_OK
    if hasattr(client, "reachable") and not client.reachable():
        print(f"STOPP: LLM-Endpunkt nicht erreichbar: {client.api_url}")
        return CLI_EXIT_ERROR
    reg, judge, cfg = _open(args)
    text = (
        spec_text(load_spec(cfg.spec))
        if cfg.spec
        else generic_spec_text(cfg.value_range, cfg.input_register)
    )
    opts = RunOptions(
        models=models,
        rounds=args.rounds,
        teams=teams,
        max_calls=max_calls,
        critic=not args.no_critic,
        conference=not args.no_conference,
    )
    summary = LabRun(reg, judge, client, opts, text).run()
    passed = sum(e.passed for e in summary.evaluations)
    print(
        f"Runden {summary.rounds_done}/{args.rounds} | LLM-Aufrufe {summary.llm_calls} "
        f"| Vorschläge {summary.proposals} | Fehlversuche {summary.failed_attempts} | "
        f"Vetos {summary.vetoes} | Bewertungen {len(summary.evaluations)} "
        f"(bestanden {passed})"
    )
    print(status_report(reg))
    if summary.proposals == 0 and summary.failed_attempts > 0:
        print("FEHLER: kein einziger Vorschlag, nur Fehlversuche (Exit 1).")
        return CLI_EXIT_ERROR
    return CLI_EXIT_OK


def cmd_lab_status(args: argparse.Namespace) -> int:
    print(status_report(Registry.open(_lab_dir(args))))
    return CLI_EXIT_OK


def cmd_lab_eval(args: argparse.Namespace) -> int:
    """lab eval: nur der Richter, kein LLM."""
    reg, judge, _ = _open(args)
    kind = KIND_GENERATOR if args.candidate.lower().endswith(".py") else KIND_KMX
    with open(args.candidate, "rb") as f:
        data = f.read()
    claim_id = reg.add_hypothesis(
        f"Manually submitted candidate {os.path.basename(args.candidate)} ({kind})",
        "human:lab-eval",
    )
    ev = judge.evaluate(kind, data)
    judge.record(claim_id or "", ev)
    print(f"Kandidat {ev.candidate_sha256 or '-'} [{claim_id}]: {ev.line()}")
    if ev.counterexample:
        print("Gegenbeispiel:", counterexample_line(ev.counterexample))
    status = reg.claims()[claim_id].status if claim_id else "?"
    print(f"Status der Behauptung: {status}")
    official_ok = ev.official is None or official_passed(ev.official)
    return CLI_EXIT_OK if ev.passed and official_ok else CLI_EXIT_REJECTED


def _wrap(fn: Callable[[argparse.Namespace], int]) -> Callable[..., int]:
    """Laborfehler als Meldung mit Exit 1 statt Traceback."""

    def run(args: argparse.Namespace) -> int:
        try:
            return fn(args)
        except (LabError, ValueError) as e:
            print(f"Laborfehler: {e}")
            return CLI_EXIT_ERROR

    return run


def _add_lab_location(sp: argparse.ArgumentParser) -> None:
    sp.add_argument(
        "--lab-dir",
        default=None,
        help=f"Laborverzeichnis (Standard: {DEFAULT_LAB_ROOT}/NAME)",
    )
    sp.add_argument("--name", default=DEFAULT_LAB_NAME, help="Laborname ohne --lab-dir")


def _add_check_rounds(sp: argparse.ArgumentParser) -> None:
    sp.add_argument(
        "--check-rounds",
        type=int,
        default=DEFAULT_CHECK_ROUNDS,
        help="Messrunden der Kontraktprüfung je Kandidat",
    )


def _add_run_options(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--rounds", type=int, default=1, help="Forschungsrunden")
    sp.add_argument("--teams", default=None, help="kommagetrennt; Standard: alle vier")
    sp.add_argument(
        "--verify-cmd",
        default=None,
        help="offizieller Verifier (oder OFFICIAL_VERIFY_CMD); nur damit 'verified'",
    )
    sp.add_argument("--models", default=None, help="Modell-IDs (oder LLM_MODEL)")
    sp.add_argument("--api-url", default=None, help="Endpunkt (oder LLM_API_URL)")
    sp.add_argument("--max-tokens", type=int, default=None)
    sp.add_argument("--llm-timeout", type=int, default=None)
    sp.add_argument("--no-critic", action="store_true", help="ohne Kritiker")
    sp.add_argument("--no-conference", action="store_true", help="ohne Konferenz")


def add_lab_subcommand(sub: SubParsers) -> None:
    """Unterbefehl `lab` mit init, run, status, eval."""
    lab = sub.add_parser("lab", help="Forschungslabor (Teams + Richter)")
    lab_sub = lab.add_subparsers(dest="lab_command", required=True)
    sp = lab_sub.add_parser("init", help="Labor anlegen")
    _add_lab_location(sp)
    sp.add_argument("--baseline", required=True, help="Basisschaltkreis .kmx/.kmb")
    sp.add_argument("--input-register", default="x")
    sp.add_argument("--range", default=None, help="Wertebereich LO:HI")
    sp.add_argument("--max-exhaustive", type=int, default=1 << 23)
    sp.add_argument(
        "--verify-cmd",
        default=None,
        help="offizieller Verifier (oder OFFICIAL_VERIFY_CMD) wird gepinnt; nur ein "
        "PASS dieses Verifiers zählt als 'verified'",
    )
    sp.set_defaults(func=_wrap(cmd_lab_init))
    sp = lab_sub.add_parser("run", help="Forschungsrunden mit LLM-Teams")
    _add_lab_location(sp)
    _add_check_rounds(sp)
    _add_run_options(sp)
    sp.set_defaults(func=_wrap(cmd_lab_run))
    sp = lab_sub.add_parser("status", help="Behauptungen, Scores, Gegenbeispiele")
    _add_lab_location(sp)
    sp.set_defaults(func=_wrap(cmd_lab_status))
    sp = lab_sub.add_parser("eval", help="nur den Richter auf einen Kandidaten")
    _add_lab_location(sp)
    _add_check_rounds(sp)
    sp.add_argument("--verify-cmd", default=None, help="offizieller Verifier")
    sp.add_argument("candidate", help="Kandidat .kmx/.kmb oder Generator .py")
    sp.set_defaults(func=_wrap(cmd_lab_eval))
