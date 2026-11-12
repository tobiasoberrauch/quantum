"""Unterbefehle der Kommandozeile (optimize/agent/legacy, research, check, info,
selftest). Hier wird die argparse-Namespace in die Optionen der Fachmodule übersetzt.
"""

from __future__ import annotations

import argparse
import re
import time

from kmx._optional import np
from kmx.agent.stage import LLMStageOptions, llm_stage
from kmx.circuit_io import atomic_write_text, read_circuit
from kmx.config import env_flag, env_text
from kmx.cost import compute_metrics
from kmx.crosscheck import kickmix_crosscheck
from kmx.domains import build_domains
from kmx.exit_codes import (
    CLI_EXIT_ERROR,
    CLI_EXIT_OFFICIAL_GATE,
    CLI_EXIT_OK,
    CLI_EXIT_REJECTED,
)
from kmx.layout import analyze_layout
from kmx.output import OutputOptions, WriteOutcome, write_outputs
from kmx.profile import PROFILE_ROWS_SHOWN, profile_segments
from kmx.research import request_playbook, research_brief
from kmx.selftest import SELFTEST_CHECKS
from kmx.session import Options, Session

LEGACY_COMMAND = "legacy"
# Ausgabename ohne -o: Eingabe mit .kmx/.kmb ersetzt durch _optimized.kmx
DEFAULT_OUTPUT_PATTERN = r"(\.km[xb])?$"
DEFAULT_OUTPUT_SUFFIX = "_optimized.kmx"
WRITE_OUTCOME_EXIT = {
    WriteOutcome.WRITTEN: CLI_EXIT_OK,
    WriteOutcome.REJECTED: CLI_EXIT_REJECTED,
    WriteOutcome.GATE_BLOCKED: CLI_EXIT_OFFICIAL_GATE,
}


def options_from_args(args: argparse.Namespace) -> Options:
    """Übersetzt die Kommandozeile (und die gleichwertigen
    Umgebungsvariablen) in die Pass-Optionen."""
    return Options(
        deep=not args.no_deep,
        mbu=not args.no_mbu,
        repack=not args.no_repack,
        iters=args.iters,
        final_rounds=args.rounds,
        budget_s=args.budget,
        rot_weight=args.rot_weight,
        sampled_facts=args.allow_sampled_facts
        or env_flag("ALLOW_PROBABILISTIC_REWRITES"),
        trim=args.trim_rotations or env_flag("TRIM_ROTATIONS"),
        trim_max_ratio=args.trim_max_ratio,
    )


def output_options_from_args(args: argparse.Namespace) -> OutputOptions:
    """Schalter des Abschlusses (Gegenprüfung, offizielles Gate)."""
    return OutputOptions(
        no_kickmix=args.no_kickmix,
        kickmix_full=args.kickmix_full,
        verify_cmd=args.verify_cmd,
    )


def llm_options_from_args(args: argparse.Namespace) -> LLMStageOptions:
    """Einstellungen der LLM-Stufe."""
    return LLMStageOptions(
        api_url=args.api_url,
        timeout=args.llm_timeout,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        models=args.models,
        steps=args.steps,
        relay=args.relay,
        playbook_path=args.playbook,
        exact_only=args.exact_only,
    )


def load_session(path: str, args: argparse.Namespace) -> Session:
    """Liest die Eingabedatei, bestimmt Layout und Domänen und
    baut daraus die Sitzung."""
    ops = read_circuit(path)
    layout = analyze_layout(ops, args.input_register, args.range)
    for note in layout.notes:
        print("Hinweis:", note)
    dom, sample_dom = build_domains(
        layout, args.max_exhaustive, args.sample_lanes, args.fallback_lanes
    )
    return Session(ops, layout, dom, sample_dom, options_from_args(args))


def _llm_stage_wanted(args: argparse.Namespace) -> bool:
    """Beim Unterbefehl "agent" immer; beim alten Aufruf automatisch, solange
    LLM_MAX_CALLS nicht 0 ist (lokaler Endpunkt als Standard)."""
    return getattr(args, "agent", False) or (
        args.command == LEGACY_COMMAND and env_text("LLM_MAX_CALLS") != "0"
    )


def cmd_optimize(args: argparse.Namespace) -> int:
    """Unterbefehle optimize/agent/legacy: Pässe bis zum Fixpunkt, optional die
    LLM-Stufe, dann Gate und Schreiben."""
    s = load_session(args.input, args)
    if env_text("OPT_MODE") or env_flag("LEGACY_UNSAFE_PASSES"):
        print(
            "Hinweis: OPT_MODE/BEAM_*/LEGACY_UNSAFE_PASSES werden nicht mehr "
            "ausgewertet; die Pässe laufen bis zum Fixpunkt."
        )
    if s.layout.invsqrt and np is None:
        print(
            "Hinweis: numpy fehlt - der Score wird nur geschätzt "
            "(COST_ROT_WEIGHT), nicht exakt gerechnet."
        )
    print("VORHER : ", compute_metrics(s.ops).summary())
    s.run_baseline()
    t = time.time()
    s.run_passes()
    print(f"Pässe fertig in {time.time() - t:.1f}s ({s.oracle.runs} Simulationsläufe).")
    if _llm_stage_wanted(args):
        llm_stage(s, llm_options_from_args(args))
    out = args.output or re.sub(
        DEFAULT_OUTPUT_PATTERN, DEFAULT_OUTPUT_SUFFIX, args.input, count=1
    )
    outcome = write_outputs(
        s, args.input, out, args.diff, output_options_from_args(args)
    )
    return WRITE_OUTCOME_EXIT[outcome]


def cmd_research(args: argparse.Namespace) -> int:
    """Unterbefehl research: Research-Brief schreiben und, mit --models, vom ersten
    Modell ein Playbook holen. Beide Dateien werden atomar geschrieben."""
    s = load_session(args.input, args)
    s.run_baseline()
    brief = research_brief(s)
    atomic_write_text(args.out, brief)
    print(f"Research-Brief geschrieben: {args.out}")
    if args.models:
        # bewusst ungetrimmt: das erste Element so, wie es angegeben wurde
        model = args.models.split(",")[0]
        playbook = request_playbook(
            brief, model, args.api_url, args.llm_timeout, args.max_tokens
        )
        atomic_write_text(args.playbook_out, playbook)
        print(
            f"Playbook von {model} gespeichert: {args.playbook_out} "
            "(ungeprüft; der Agent behandelt es als Hypothesen)"
        )
    return CLI_EXIT_OK


def cmd_check(args: argparse.Namespace) -> int:
    """Unterbefehl check: Kandidat End-to-End gegen das Original prüfen. Ist er nicht
    äquivalent, zählt bei invsqrt ersatzweise die eigenständige Kontraktprüfung (Phase
    innerhalb der Toleranz). Exit 0 oder 2.
    """
    s = load_session(args.input, args)
    s.run_baseline()
    cand = read_circuit(args.candidate)
    ok, msg, sig = s.oracle.check(cand, range(args.rounds))
    print("ORIGINAL:", s.status_line(s.orig, s.oracle.orig_sig(0)))
    print("KANDIDAT:", s.status_line(cand, sig))
    for label, ops in (("ORIGINAL", s.orig), ("KANDIDAT", cand)):
        rep = s.exact_score(ops)
        if rep is not None:
            print(f"{label} exakt: {rep.line()}")
    print(("ÄQUIVALENT: " if ok else "NICHT ÄQUIVALENT: ") + msg)
    within_tolerance = False
    if not ok and s.layout.invsqrt:
        within_tolerance, tolerance_msg = s.tolerance_check(cand, args.rounds)
        print(
            "Eigenständige Kontraktprüfung des Kandidaten: "
            + ("BESTANDEN - " if within_tolerance else "FEHLGESCHLAGEN - ")
            + tolerance_msg
        )
    if (ok or within_tolerance) and not args.no_kickmix:
        print(kickmix_crosscheck(s.orig, cand, s.layout, same_phase=ok))
    return CLI_EXIT_OK if (ok or within_tolerance) else CLI_EXIT_REJECTED


def cmd_info(args: argparse.Namespace) -> int:
    """Unterbefehl info: Kennzahlen, Score (exakt, falls verfügbar) und
    Toffoli-Profil der Eingabe."""
    s = load_session(args.input, args)
    s.run_baseline()
    print(s.current_status_line)
    rep = s.exact_score(s.ops)
    if rep is not None:
        print("Exakt gerechnet wie der offizielle Verifier:", rep.line())
    for r in profile_segments(s.ops, PROFILE_ROWS_SHOWN):
        print(
            f"  {r['toffoli']:6d} Toffoli  {r['instruktionen']:7d} Instr.  "
            f"idx {r['von']}..{r['bis']}  {r['segment']}"
        )
    return CLI_EXIT_OK


def cmd_selftest(_: argparse.Namespace) -> int:
    """Unterbefehl selftest: führt die eingebauten Prüfungen der Reihe nach aus; Exit 1,
    sobald eine fehlschlägt."""
    failed = 0
    for check in SELFTEST_CHECKS:
        good, label = check()
        failed += not good
        print(f"{'OK  ' if good else 'FAIL'} {label}")
    return CLI_EXIT_ERROR if failed else CLI_EXIT_OK
