"""Kommandozeile: Argumentparser, alte Aufrufformen (ohne Unterbefehl) und der
Einstiegspunkt `main`."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Collection, Sequence

from kmx.agent.relay import AGENT_DEFAULT_RELAY_ROUNDS, AGENT_DEFAULT_STEPS
from kmx.cli_help import CLI_DESCRIPTION
from kmx.commands import (
    LEGACY_COMMAND,
    cmd_check,
    cmd_info,
    cmd_optimize,
    cmd_research,
    cmd_selftest,
)
from kmx.config import LLM_DEFAULT_MAX_TOKENS, LOCAL_LLM_MODEL, env_flag
from kmx.cost import ROT_WEIGHT
from kmx.crosscheck import KICKMIX_DEFAULT_SHOTS
from kmx.exit_codes import CLI_EXIT_ERROR
from kmx.ops import KmxError
from kmx.score import TRIM_DEFAULT_MAX_RATIO
from kmx.session import Options

# argparse hat für das Ergebnis von add_subparsers() keinen öffentlichen Typ
SubParsers = argparse._SubParsersAction

HELP_FLAGS = frozenset({"-h", "--help"})
SELFTEST_FLAG = "--selftest"
LEGACY_DEFAULT_ARGV = (
    LEGACY_COMMAND,
    "invsqrt.kmx",
    "invsqrt_optimized.kmx",
    "invsqrt_optimization.diff",
)
DEFAULT_MAX_EXHAUSTIVE = 1 << 23
DEFAULT_SAMPLE_LANES = 4096
DEFAULT_FALLBACK_LANES = 65536


def _add_domain_arguments(common: argparse.ArgumentParser) -> None:
    common.add_argument(
        "--input-register", default="x", help="Name des Eingaberegisters (Standard: x)"
    )
    common.add_argument(
        "--range", default=None, help="gültiger Wertebereich LO:HI des Eingaberegisters"
    )
    common.add_argument(
        "--max-exhaustive",
        type=int,
        default=DEFAULT_MAX_EXHAUSTIVE,
        help="bis zu dieser Domänengröße vollständig simulieren",
    )
    common.add_argument(
        "--sample-lanes",
        type=int,
        default=DEFAULT_SAMPLE_LANES,
        help="Lanes der schnellen Stichproben-Domäne",
    )
    common.add_argument(
        "--fallback-lanes",
        type=int,
        default=DEFAULT_FALLBACK_LANES,
        help="Lanes, falls keine vollständige Domäne möglich ist",
    )


def _add_pass_arguments(common: argparse.ArgumentParser) -> None:
    common.add_argument(
        "--rounds",
        type=int,
        default=Options.final_rounds,
        help="Messrunden der Abschlussprüfung",
    )
    common.add_argument(
        "--iters",
        type=int,
        default=Options.iters,
        help="maximale Durchläufe der Pass-Schleife",
    )
    common.add_argument(
        "--budget",
        type=float,
        default=Options.budget_s,
        help="Zeitbudget (s) der Kandidatensuche je Durchlauf",
    )
    common.add_argument(
        "--rot-weight",
        type=float,
        default=ROT_WEIGHT,
        help="Toffoli-Äquivalente je feiner Rotation für die Schnellschätzung "
        "(oder COST_ROT_WEIGHT); für invsqrt wird der Score ohnehin exakt gerechnet",
    )
    common.add_argument(
        "--allow-sampled-facts",
        action="store_true",
        help="faktenbasierte Pässe auch dann, wenn die Domäne nur als "
        "Stichprobe simuliert werden kann",
    )
    common.add_argument(
        "--no-deep",
        action="store_true",
        help="ohne Suche über lineare Hüllen / Toffoli-Gruppen",
    )
    common.add_argument(
        "--no-mbu", action="store_true", help="ohne Measurement-Based Uncomputation"
    )
    common.add_argument("--no-repack", action="store_true", help="ohne Qubit-Repacking")


def _add_gate_arguments(common: argparse.ArgumentParser) -> None:
    common.add_argument(
        "--no-kickmix",
        action="store_true",
        help="ohne Gegenprüfung durch die kickmix-Bibliothek",
    )
    common.add_argument(
        "--kickmix-full",
        action="store_true",
        help="Gegenprüfung mit dem offiziellen Simulator auf der GANZEN Domäne "
        f"statt {KICKMIX_DEFAULT_SHOTS} Shots (ca. 1 min)",
    )
    common.add_argument(
        "--verify-cmd",
        default=None,
        help="offizieller Verifier als Gate VOR dem Schreiben "
        "(oder OFFICIAL_VERIFY_CMD), z. B. "
        "'python verifiers/invsqrt/verify_submission_invsqrt.py {out} --max-workers 8'",
    )
    common.add_argument(
        "--trim-rotations",
        action="store_true",
        help="feine Z_POW streichen, wenn der exakte Score sinkt "
        "(Phase ändert sich innerhalb der Toleranz; oder TRIM_ROTATIONS=1)",
    )
    common.add_argument(
        "--trim-max-ratio",
        type=float,
        default=TRIM_DEFAULT_MAX_RATIO,
        help="beim Trimmen höchstens diesen Anteil der Toleranz ausschöpfen",
    )


def _add_llm_arguments(common: argparse.ArgumentParser) -> None:
    common.add_argument(
        "--exact-only",
        action="store_true",
        default=env_flag("EXACT_ONLY"),
        help="LLM-Rewrites nur annehmen, wenn sie über ALLE Belegungen bewiesen "
        "sind (keine Don't-Cares)",
    )
    common.add_argument(
        "--models",
        default=None,
        help="kommagetrennte Modell-IDs "
        f"(oder LLM_MODEL; Standard lokal: {LOCAL_LLM_MODEL})",
    )
    common.add_argument(
        "--api-url",
        default=None,
        help="OpenAI-kompatibler Endpunkt "
        "(oder LLM_API_URL; Standard: lokale Weinstadt-KI)",
    )
    common.add_argument(
        "--steps",
        type=int,
        default=AGENT_DEFAULT_STEPS,
        help="Tool-Schritte je Modell und Runde",
    )
    common.add_argument(
        "--relay",
        type=int,
        default=AGENT_DEFAULT_RELAY_ROUNDS,
        help="Staffelrunden über alle Modelle",
    )
    common.add_argument("--temperature", type=float, default=None)
    common.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Antwortlimit je LLM-Aufruf "
        f"(oder LLM_MAX_TOKENS, Standard {LLM_DEFAULT_MAX_TOKENS})",
    )
    common.add_argument(
        "--llm-timeout",
        type=int,
        default=None,
        help="Timeout je LLM-Aufruf in Sekunden (oder LLM_TIMEOUT)",
    )
    common.add_argument(
        "--playbook",
        default=None,
        help="Textdatei mit Recherche-Ergebnissen für den Agenten",
    )


def build_common_options_parser() -> argparse.ArgumentParser:
    """Elternparser mit den Optionen, die alle dateibezogenen Unterbefehle teilen
    (Reihenfolge = Hilfetext)."""
    common = argparse.ArgumentParser(add_help=False)
    _add_domain_arguments(common)
    _add_pass_arguments(common)
    _add_gate_arguments(common)
    _add_llm_arguments(common)
    return common


def _add_optimize_subcommands(sub: SubParsers, common: argparse.ArgumentParser) -> None:
    for name, hlp in (
        ("optimize", "deterministische Pässe"),
        ("agent", "Pässe + LLM-Agent"),
    ):
        sp = sub.add_parser(name, parents=[common], help=hlp)
        sp.add_argument("input")
        sp.add_argument("-o", "--output", default=None)
        sp.add_argument("--diff", default=None)
        sp.set_defaults(func=cmd_optimize, agent=(name == "agent"))


def _add_analysis_subcommands(sub: SubParsers, common: argparse.ArgumentParser) -> None:
    sp = sub.add_parser(
        "research",
        parents=[common],
        help="Research-Brief (und optional Playbook) erzeugen",
    )
    sp.add_argument("input")
    sp.add_argument("--out", default="research_brief.md")
    sp.add_argument("--playbook-out", default="playbook.md")
    sp.set_defaults(func=cmd_research)
    sp = sub.add_parser(
        "check", parents=[common], help="zwei Dateien End-to-End vergleichen"
    )
    sp.add_argument("input")
    sp.add_argument("candidate")
    sp.set_defaults(func=cmd_check)
    sp = sub.add_parser("info", parents=[common], help="Kennzahlen und Profil")
    sp.add_argument("input")
    sp.set_defaults(func=cmd_info)
    sp = sub.add_parser("selftest", help="eingebaute Tests")
    sp.set_defaults(func=cmd_selftest)


def _add_legacy_subcommand(sub: SubParsers, common: argparse.ArgumentParser) -> None:
    """Alter Aufruf IN [OUT] [DIFF] mit Positionsargumenten (ohne Unterbefehl)."""
    sp = sub.add_parser(LEGACY_COMMAND, parents=[common])
    sp.add_argument("input")
    sp.add_argument("output", nargs="?", default=None)
    sp.add_argument("diff", nargs="?", default=None)
    sp.set_defaults(func=cmd_optimize, agent=False)


def _build_parser(
    prog: str | None = None,
) -> tuple[argparse.ArgumentParser, frozenset[str]]:
    """Parser mit allen Unterbefehlen (jeder setzt seine Funktion als `args.func`) und
    die Menge der Unterbefehlsnamen."""
    common = build_common_options_parser()
    parser = argparse.ArgumentParser(
        prog=prog,
        description=CLI_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")
    _add_optimize_subcommands(sub, common)
    _add_analysis_subcommands(sub, common)
    _add_legacy_subcommand(sub, common)
    return parser, frozenset(sub.choices)


def build_parser(prog: str | None = None) -> argparse.ArgumentParser:
    """Baut den Argumentparser mit allen Unterbefehlen; jeder setzt seine
    Funktion als `args.func`."""
    return _build_parser(prog)[0]


def normalize_argv(
    argv: Sequence[str], commands: Collection[str] | None = None
) -> list[str]:
    """Bildet die alten Aufrufformen auf Unterbefehle ab: --selftest, kein Argument
    (Standarddateien) und IN [OUT] [DIFF] ohne Unterbefehl. `commands` sind die
    Unterbefehle des Parsers (Standard: die von build_parser)."""
    known = _build_parser()[1] if commands is None else commands
    argv = list(argv)
    if argv and argv[0] == SELFTEST_FLAG:
        return ["selftest"]
    if not argv:
        return list(LEGACY_DEFAULT_ARGV)
    if argv[0] not in known and argv[0] not in HELP_FLAGS:
        return [LEGACY_COMMAND] + argv
    return argv


def main(argv: Sequence[str] | None = None, prog: str | None = None) -> int:
    """Einstiegspunkt: liefert den Exit-Code (1 bei fehlender Eingabedatei oder
    Formatfehler). `prog` ersetzt den Programmnamen in --help."""
    parser, commands = _build_parser(prog)
    args = parser.parse_args(
        normalize_argv(sys.argv[1:] if argv is None else argv, commands)
    )
    for path in (getattr(args, "input", None), getattr(args, "candidate", None)):
        if path and not os.path.exists(path):
            print(f"Datei nicht gefunden: {path}")
            return CLI_EXIT_ERROR
    try:
        return args.func(args)
    except KmxError as e:
        print(f"Formatfehler: {e}")
        return CLI_EXIT_ERROR
