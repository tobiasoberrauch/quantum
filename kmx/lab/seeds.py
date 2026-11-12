"""Altbefunde, mit denen ein neues Labor startet: echte Ergebnisse früherer Läufe
(agent-memory 2026-11-03..11), mit ehrlichem Status und Quelle.

Sie werden beim Anlegen als `claim` plus `historical`-Ereignis geschrieben. Ein
Altbefund kann nie `verified` sein; er ist Erfahrung, kein Beweis. Widerlegte Altbefunde
sind als die POSITIVE Hypothese formuliert, die widerlegt wurde ("X senkt die
Kosten"), damit "refuted" wörtlich stimmt; der Gegenbeleg steht in den Annahmen.
"""

from __future__ import annotations

from typing import NamedTuple

from kmx.lab.claims import EXPERIMENTAL, REFUTED

SEED_SOURCE = "agent-memory 2026-11-03..11"
CONSTSEED_GENERATOR = (
    "/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/work/"
    "constseed_build/build_constseed_circuit.py (+ REPORT.md)"
)
# Stand des öffentlichen Felds (Kontext für die Teams, keine Behauptung)
FRONTIER_NOTE = (
    "Public invsqrt frontier ratio ~22.1; best own submission 26ebf39df3b1 ratio "
    "21.9677 (source: " + SEED_SOURCE + ")."
)


class Seed(NamedTuple):
    claim_id: str
    claim: str
    status: str
    assumptions: tuple[str, ...]
    extra_sources: tuple[str, ...] = ()


SEEDS: tuple[Seed, ...] = (
    Seed(
        "seed-window-llm-rewrites",
        "Window-level LLM rewriting of invsqrt finds no accepted rewrites "
        "(qwen3.8-27b, 63 calls, 0 accepted); the deterministic passes leave invsqrt "
        "a15 locally optimal, so remaining leverage is global re-synthesis at the "
        "generator level.",
        EXPERIMENTAL,
        ("baseline a15b0d73f720", "local 27B model", "window sizes of kmx agent"),
    ),
    Seed(
        "seed-magnitude-shortcut",
        "Using lower precision for large x ('magnitude shortcut') lowers the cost "
        "while staying within the phase tolerance.",
        REFUTED,
        (
            "refuted by: tolerance tol(x) ~ 2^-24*beta/sqrt(x) FALLS with x, so large "
            "x need finer, not coarser, precision",
        ),
    ),
    Seed(
        "seed-error-constant-c",
        "The error constant c = 58,597,850 is the minimax-LP ceiling of the current "
        "construction; grinding c further is dead (< +0.05%).",
        EXPERIMENTAL,
        ("current construction family", "minimax LP model"),
    ),
    Seed(
        "seed-pure-dyadic-kickback",
        "Pure-dyadic phase kickback (P-A, n_rot 41->0) makes the phase stage cheaper "
        "than the current 41 rotations.",
        REFUTED,
        (
            "current 41-rotation phase stage",
            "refuted by: only 3 of 41 rotations become free, and barrel-shift "
            "s-routing costs ~585 Toffolis",
        ),
    ),
    Seed(
        "seed-constant-seed-newton",
        "A constant-seed model (128-entry seed table + Newton, 'mrmeows direction') "
        "beats the current construction as a direct path.",
        REFUTED,
        (
            "reconstruction faithful to the public description",
            "refuted by: the reconstruction reaches 0.63x of current and is capped "
            "at ~12.7x ratio",
        ),
        (CONSTSEED_GENERATOR,),
    ),
    Seed(
        "seed-rotation-share",
        "The 41 rotations carry the whole phase and cost ~294.8 Toffoli-equivalents; "
        "mean Toffolis 1,289 are ~81% of C.",
        EXPERIMENTAL,
        ("baseline a15b0d73f720 exact score 93,925.48, Q=62",),
    ),
)
