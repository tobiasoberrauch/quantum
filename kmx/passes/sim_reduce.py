"""Simulationsgeführte Reduktion (`pass_sim_reduce`): Phase A + Phase B."""

from __future__ import annotations

import time
from collections.abc import Sequence

from kmx.domains import Domain
from kmx.layout import Layout
from kmx.ops import Op
from kmx.passes.reduce_confirm import DomainConfirmation
from kmx.passes.reduce_rules import ReduceCandidate
from kmx.passes.reduce_search import SampleCandidateSearch
from kmx.simulator import compile_ops, push_depths

DEFAULT_BUDGET_S = 180.0  # Zeitbudget (s) der Kandidatensuche je Durchlauf
DEFAULT_MAX_TERMS = 8  # längste XOR-Summe eines linearen Ersatzes
DEFAULT_MAX_GROUP = 6  # größte untersuchte CCX-Gruppe auf einem Ziel
# Statistik-Schlüssel: so viele Toffolis blieben wegen des Zeitbudgets ungeprüft
STAT_SEARCH_ABORTED = "suche_abgebrochen_bei_toffolis"


def pass_sim_reduce(
    ops: Sequence[Op],
    layout: Layout,
    dom: Domain,
    sample_dom: Domain,
    deep: bool = True,
    budget_s: float = DEFAULT_BUDGET_S,
    max_terms: int = DEFAULT_MAX_TERMS,
    max_group: int = DEFAULT_MAX_GROUP,
    drop_idle_hmr: bool = True,
) -> tuple[list[Op], dict[str, int]]:
    """Simulationsgeführte Reduktion.

    Phase A (Stichprobe): sucht Kandidaten per linearer Algebra über den Lane-Vektoren:
       lin    CCX-Produkt liegt in der affinen Hülle der vorhandenen Qubits
              -> CX-Kaskade (0 Toffoli)
       group  mehrere CCX auf dasselbe Ziel: Summe ist affin (0 Toffoli)
              oder u*w + affin (1 Toffoli)
    Phase B (ganze Domäne): bestätigt jeden Kandidaten exakt und findet direkte Fälle
       (nie feuernd, eine Kontrolle impliziert die andere, CSWAP wirkt wie SWAP,
       CCZ wie CZ).
    Übernommen wird nur, was in Phase B auf allen Lanes gilt."""
    depths = push_depths(ops)
    cops = compile_ops(ops)
    cands: dict[int, ReduceCandidate] = {}
    t0 = time.time()
    skipped = 0
    if deep:
        search = SampleCandidateSearch(
            ops, depths, cops, sample_dom, max_terms, max_group
        )
        search.search(t0, budget_s)
        cands, skipped = search.cands, search.skipped

    confirmation = DomainConfirmation(ops, depths, cops, layout, dom, cands)
    if skipped:
        # Zeitbudget erschöpft: --budget erhöhen
        confirmation.stats[STAT_SEARCH_ABORTED] = skipped
    confirmation.confirm()
    confirmation.merge_equal_rotations()
    out = confirmation.rewritten(drop_idle_hmr)
    return out, dict(confirmation.stats)
