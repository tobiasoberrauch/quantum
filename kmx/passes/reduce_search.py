"""Phase A der simulationsgeführten Reduktion: Kandidatensuche auf der
Stichproben-Domäne.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass

from kmx.domains import Domain, LaneVector
from kmx.ops import META_OPS, TOFFOLI_LIKE, X_TYPE, Op, is_plain_xt
from kmx.passes.reduce_rules import (
    CAND_GROUP_AFFINE,
    CAND_GROUP_PRODUCT,
    CAND_LINEAR,
    GroupAffineCandidate,
    GroupCandidate,
    GroupProductCandidate,
    LinearCandidate,
    ReduceCandidate,
    candidate_reads,
    direct_decision,
    toffoli_product_lanes,
)
from kmx.passes.xor_basis import ONE, XorBasis
from kmx.simulator import CompiledOp, State, cur_mask, step
from kmx.taint import Taint

# längere Gruppen werden nicht auf die Form u*w + affin untersucht (Laufzeit)
_GROUP_PRODUCT_MAX_SPAN = 3000
# Basis-Etikett ("p", w) steht für den Produktvektor XOR(u) & w
_PRODUCT_FACTOR_LABEL = "p"
# Startwert der Stichproben-Simulation von Phase A (Messergebnisse)
SEARCH_SEED = "A"


@dataclass
class _CcxTargetRun:
    """Lauf unbedingter CCX auf dasselbe Ziel, das dazwischen weder gelesen
    noch anders angefasst wird."""

    # (Op-Index, Lane-Vektor des Kontrollprodukts), höchstens max_group Einträge
    hist: list[tuple[int, LaneVector]]
    # Index des Gruppenkandidaten, der `hist` bereits abdeckt
    cand: int | None = None


class SampleCandidateSearch:
    """Phase A von pass_sim_reduce: Kandidatensuche auf der Stichproben-Domäne.

    Nur Vorschläge - übernommen wird ein Kandidat erst, wenn Phase B ihn auf der
    ganzen Domäne bestätigt. `cands` hält die Kandidaten in
    Entdeckungsreihenfolge, `skipped` zählt die Toffolis, die wegen des
    erschöpften Zeitbudgets nicht mehr untersucht wurden."""

    def __init__(
        self,
        ops: Sequence[Op],
        depths: Sequence[int],
        cops: Sequence[CompiledOp],
        sample_dom: Domain,
        max_terms: int,
        max_group: int,
    ) -> None:
        self.ops, self.depths, self.cops = ops, depths, cops
        self.max_terms, self.max_group = max_terms, max_group
        self.st, self.taint = State(sample_dom, SEARCH_SEED), Taint()
        self.runs: dict[int, _CcxTargetRun] = {}  # Ziel-Qubit -> offener CCX-Lauf
        self.cands: dict[int, ReduceCandidate] = {}
        self.skipped = 0

    def search(self, t0: float, budget_s: float) -> None:
        """Simuliert die Stichprobe einmal durch und untersucht jeden Toffoli,
        solange das Budget reicht."""
        ops, depths, cops = self.ops, self.depths, self.cops
        st, taint, runs = self.st, self.taint, self.runs
        for i, op in enumerate(ops):
            n = op.name
            if n in TOFFOLI_LIKE:
                if time.time() - t0 >= budget_s:
                    self.skipped += 1
                elif not any(q in taint.random_qubits for q in op.qs):
                    self._examine_toffoli(i, op)
            # Lauf-Buchführung: ein Lauf endet, sobald das Ziel gelesen oder anders
            # angefasst wird
            if n not in META_OPS and op.qs:
                if is_plain_xt(op, depths[i]):
                    for c in op.qs[:-1]:
                        runs.pop(c, None)
                else:
                    for q in op.qs:
                        runs.pop(q, None)
            step(st, cops[i])
            taint.advance(op)

    def _examine_toffoli(self, i: int, op: Op) -> None:
        """Sucht für den Toffoli an Position i einen linearen Ersatz, sonst
        (unbedingtes CCX) eine Gruppe."""
        st = self.st
        m = cur_mask(st, op.cond)
        rnd = self.taint.mask_random(op)
        if direct_decision(op, st, m, rnd) is not None:
            return  # direkte Fälle findet Phase B selbst
        mm = st.all_lanes if (m is None or rnd) else m
        base = self._affine_basis(op, mm)
        v = toffoli_product_lanes(op, st.q.get, mm)
        sol = base.solve(v)
        if sol is not None and len(sol) <= self.max_terms:
            self.cands[i] = LinearCandidate(CAND_LINEAR, sol)
            self._end_runs_of(sol)
        elif op.name == "CCX" and is_plain_xt(op, self.depths[i]):
            self._extend_target_run(i, op.qs[2], v, base)

    def _end_runs_of(self, qubits: Sequence[int | str]) -> None:
        """Der Ersatz liest diese Qubits neu: ihre Läufe enden hier."""
        runs = self.runs
        for x in qubits:
            runs.pop(x, None)

    def _affine_basis(self, op: Op, mm: int) -> XorBasis:
        """Basis aus der Konstanten und allen unverfälschten Qubits außer den Zielen von
        `op`, auf `mm` maskiert. Die eigenen Qubits von `op` kommen zuerst, damit
        Lösungen bevorzugt aus ihnen bestehen.
        """
        st, tainted = self.st, self.taint.random_qubits
        n = op.name
        exclude = (
            set(op.qs[1:]) if n == "CSWAP" else ({op.qs[2]} if n == "CCX" else set())
        )
        base = XorBasis()
        base.add(ONE, mm)
        seen = {0, mm}
        order = list(op.qs) + sorted(q for q in st.q if q not in op.qs)
        for q in order:
            if q in exclude or q in tainted:
                continue
            v = st.q.get(q, 0) & mm
            if v not in seen:
                seen.add(v)
                base.add(q, v)
        return base

    def _extend_target_run(self, i: int, t: int, v: LaneVector, base: XorBasis) -> None:
        """Hängt das CCX an Position i (Produktvektor v) an den Lauf seines Ziels t und
        sucht eine Gruppe: zuerst der ganze Lauf, sonst - wenn noch kein Kandidat
        besteht - nur das letzte Paar.
        """
        runs, cands, max_group = self.runs, self.cands, self.max_group
        run = runs.setdefault(t, _CcxTargetRun([]))
        hist = run.hist
        found = (
            self._find_group(hist + [(i, v)], i, t, base)
            if hist and len(hist) < max_group
            else None
        )
        # größere Gruppe ersetzt den bisherigen Kandidaten
        if found:
            self._end_runs_of(candidate_reads(found))
            if run.cand is not None:
                cands.pop(run.cand, None)
            cands[i] = found
            hist.append((i, v))
            run.cand = i
            return
        # bestehender Kandidat bleibt, neuer Lauf beginnt hier
        if run.cand is not None:
            runs[t] = _CcxTargetRun([(i, v)])
            return
        found = (
            self._find_group(hist[-1:] + [(i, v)], i, t, base)
            if len(hist) > 1
            else None
        )
        if found:
            cands[i] = found
            self._end_runs_of(candidate_reads(found))
            runs[t] = _CcxTargetRun([hist[-1], (i, v)], i)
        else:
            hist.append((i, v))
            del hist[:-max_group]

    def _find_group(
        self, grp: Sequence[tuple[int, LaneVector]], i: int, t: int, base: XorBasis
    ) -> GroupCandidate | None:
        """Ist die Summe der CCX-Produkte der Gruppe affin (0 Toffoli) oder von der Form
        u*w + affin (1 Toffoli)?"""
        delta = 0
        for _, product in grp:
            delta ^= product
        idxs = [j for j, _ in grp]
        sol = base.solve(delta)
        if sol is not None and len(sol) <= self.max_terms:
            return GroupAffineCandidate(CAND_GROUP_AFFINE, idxs, sol)
        if i - idxs[0] > _GROUP_PRODUCT_MAX_SPAN:
            return None
        ctrl, local = self._group_factor_pools(idxs, i, t)
        return self._find_product_form(delta, idxs, ctrl, local, base)

    def _group_factor_pools(
        self, idxs: Sequence[int], i: int, t: int
    ) -> tuple[list[int], list[int]]:
        """Faktor-Kandidaten einer Gruppe: `ctrl` sind die Kontrollen ihrer CCX, `local`
        zusätzlich alles, was zwischen erstem CCX und Position i per X/CX/CCX in eine
        dieser Kontrollen geschrieben wurde.
        """
        ops, tainted = self.ops, self.taint.random_qubits
        ctrl: list[int] = []
        for j in idxs:
            for c in ops[j].qs[:2]:
                if c not in ctrl and c != t and c not in tainted:
                    ctrl.append(c)
        local = list(ctrl)
        for j in range(idxs[0], i):
            o = ops[j]
            if o.name in X_TYPE and o.qs[-1] in ctrl:
                for c in o.qs[:-1]:
                    if c not in local and c != t and c not in tainted:
                        local.append(c)
        return ctrl, local

    def _find_product_form(
        self,
        delta: LaneVector,
        idxs: list[int],
        ctrl: Sequence[int],
        local: Sequence[int],
        base: XorBasis,
    ) -> GroupProductCandidate | None:
        """Sucht delta = XOR(u) * XOR(wset) ^ XOR(lset) mit u aus ein oder zwei
        Kontrollen und wset aus `local`."""
        g = self.st.q.get
        factors = [(c,) for c in ctrl] + [
            (c, d) for k, c in enumerate(ctrl) for d in ctrl[k + 1 :]
        ]
        for u in factors:
            vu = 0
            for c in u:
                vu ^= g(c, 0)
            extended = base.copy()
            for w in local:
                if w != u[0]:
                    extended.add((_PRODUCT_FACTOR_LABEL, w), vu & g(w, 0))
            sol = extended.solve(delta)
            if sol is None:
                continue
            wset = [x[1] for x in sol if isinstance(x, tuple)]
            lset = [x for x in sol if not isinstance(x, tuple)]
            # Pivot (erstes Element) liegt außerhalb von u
            wset.sort(key=lambda w: w in u)
            if (
                wset
                and wset[0] not in u
                and len(wset) + len(lset) <= 2 * self.max_terms
            ):
                return GroupProductCandidate(CAND_GROUP_PRODUCT, idxs, u, wset, lset)
        return None
