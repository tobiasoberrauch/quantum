"""kmx: verifier-gestützter Optimierer und KI-Agent für kickmix-Schaltkreise
(.kmx, .kmb).

Einstiegspunkte: `main.py` neben dem Paket, `python -m kmx` und die Funktion
`kmx.cli.main`; Aufrufformen, Optionen und Umgebungsvariablen zeigt `--help`
(Text in `kmx.cli_help`, Variablen in `kmx.config`).

Schichten, von unten nach oben (jede importiert nur aus tieferen):
  ops, config, layout, domains     Format, Konfiguration, Register, Lane-Domänen
  cost, simulator, taint, profile  Kostenmodell/Phasen, wortparalleler Simulator,
                                   Zufalls-Analyse, Toffoli-Profil
  verify/                          oracle (L3 End-to-End), window (L1 exakt,
                                   L2 kontextuell), compat (alte API-Namen)
  passes/                          deterministische Pässe: cancel, sim_reduce
                                   (reduce_search, reduce_confirm, reduce_rules,
                                   xor_basis), mbu, repack
  score, session, crosscheck       exakter invsqrt-Score, Pipeline mit commit,
                                   kickmix-Gegenprüfung
  agent/                           LLM-Stufe: workbench (Tools), state_cache,
                                   rewrite, facts, hotspots, tools, relay
                                   (Tool-Calling), json_mode, client, stage
  output, research, selftest       Abschluss mit Gate, Research-Brief, Selbsttest
  lab/                             Forschungslabor (oberste Fachschicht, darf alles
                                   darunter importieren): claims, seeds, spec,
                                   untrusted, watchdog, registry, sandbox,
                                   counterexample, official,
                                   judge, llm_json, teams, report, rounds, commands
  commands, cli, cli_help          Kommandozeile (cli importiert aus lab nur
                                   add_lab_subcommand)
  prompts/                         Prompt- und Vorlagentexte als Paketdaten

Optional: numpy (exakter invsqrt-Score) und kickmix (Gegenprüfung, .kmb), siehe
`kmx._optional`. Die hier exportierten Namen sind die öffentliche Schnittstelle; sie
umfasst auch die alten API-Namen (compute_metrics auf Textzeilen, circuit_cost,
BitParallelKMXVerifier, VerificationResult).
"""

from kmx.agent.client import LLMClient, LLMError
from kmx.agent.json_mode import json_windows, run_json_llm
from kmx.agent.relay import run_agent
from kmx.agent.stage import llm_stage
from kmx.agent.tools import TOOLS
from kmx.agent.workbench import Workbench
from kmx.circuit_io import read_circuit, write_circuit
from kmx.cost import (
    ROT_WEIGHT,
    Metrics,
    circuit_cost,
    compute_metrics,
    phase_exponent,
    phase_op,
    score_estimate,
    zpow_info,
)
from kmx.crosscheck import kickmix_crosscheck
from kmx.domains import (
    Domain,
    build_domains,
    exhaustive_domain,
    pattern_bit,
    sample_domain,
)
from kmx.layout import Layout, analyze_layout
from kmx.ops import KmxError, Op, format_ops, parse_line, parse_lines, parse_text
from kmx.output import run_official_verifier
from kmx.passes.cancel import pass_cancel, pass_fold
from kmx.passes.mbu import pass_mbu
from kmx.passes.repack import lifetimes_of, pass_repack, trace_touches
from kmx.passes.sim_reduce import pass_sim_reduce
from kmx.profile import profile_segments
from kmx.research import research_brief
from kmx.score import ScoreReport, invsqrt_score, trim_rotations
from kmx.session import Options, Session
from kmx.simulator import (
    State,
    compile_op,
    compile_ops,
    push_depths,
    simulate,
    step,
)
from kmx.taint import Taint
from kmx.verify.compat import BitParallelKMXVerifier, VerificationResult
from kmx.verify.oracle import FinalSig, Oracle, final_sig
from kmx.verify.window import (
    check_context,
    check_exact,
    dead_bits_after,
    difference_cone,
    off_grid_phase,
)

__version__ = "5"

__all__ = [
    "BitParallelKMXVerifier",
    "Domain",
    "FinalSig",
    "KmxError",
    "LLMClient",
    "LLMError",
    "Layout",
    "Metrics",
    "Op",
    "Options",
    "Oracle",
    "ROT_WEIGHT",
    "ScoreReport",
    "Session",
    "State",
    "TOOLS",
    "Taint",
    "VerificationResult",
    "Workbench",
    "analyze_layout",
    "build_domains",
    "check_context",
    "check_exact",
    "circuit_cost",
    "compile_op",
    "compile_ops",
    "compute_metrics",
    "dead_bits_after",
    "difference_cone",
    "exhaustive_domain",
    "final_sig",
    "format_ops",
    "invsqrt_score",
    "json_windows",
    "kickmix_crosscheck",
    "lifetimes_of",
    "llm_stage",
    "off_grid_phase",
    "parse_line",
    "parse_lines",
    "parse_text",
    "pass_cancel",
    "pass_fold",
    "pass_mbu",
    "pass_repack",
    "pass_sim_reduce",
    "pattern_bit",
    "phase_exponent",
    "phase_op",
    "profile_segments",
    # Simulator-Interna (heißer Pfad) für Analyseskripte
    "push_depths",
    "read_circuit",
    "research_brief",
    "run_agent",
    "run_json_llm",
    "run_official_verifier",
    "sample_domain",
    "score_estimate",
    "simulate",
    "step",
    "trace_touches",
    "trim_rotations",
    "write_circuit",
    "zpow_info",
]
