"""Phase B der simulationsgeführten Reduktion: exakte Bestätigung auf der
ganzen Domäne, Rotationen auf wertgleichen Qubits und HMR ohne Wirkung.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from fractions import Fraction

from kmx.cost import is_plain_phase, phase_exponent, phase_op
from kmx.domains import Domain, LaneVector
from kmx.layout import Layout
from kmx.ops import CONDITION_STACK_OPS, META_OPS, TOFFOLI_LIKE, Op, ops_unchanged
from kmx.passes.reduce_rules import (
    CAND_GROUP_AFFINE,
    CAND_GROUP_PRODUCT,
    CAND_LINEAR,
    GROUP_CANDIDATES,
    DirectDecision,
    GroupCandidate,
    ReduceCandidate,
    apply_direct,
    candidate_reads,
    direct_decision,
    linear_replacement,
    product_group_replacement,
    toffoli_product_lanes,
    xor_of_terms,
)
from kmx.passes.xor_basis import XorTerm, lin_ops
from kmx.simulator import CompiledOp, State, cur_mask, push_depths, step
from kmx.taint import Taint
from kmx.verify.window import dead_bits_after

# Startwert der Simulation von Phase B (Messergebnisse)
CONFIRM_SEED = "B"
STAT_TOFFOLI_SAVED = "toffoli_saved"
STAT_PHASE_MERGE = "phase_merge"
STAT_IDLE_HMR = "idle_hmr"


class DomainConfirmation:
    """Phase B von pass_sim_reduce: exakte Bestätigung auf der ganzen Domäne.

    Sammelt, was auf ALLEN Lanes gilt: direkte Fälle (direct_decision), bestätigte
    Kandidaten aus Phase A, Z_POW auf wertgleichen Qubits und Messungen von Qubits, die
    ohnehin |0> sind. `repl` (Index -> Ersatz) und `delete` beschreiben die Umformung;
    `stats` zählt in der Reihenfolge des ersten Auftretens.
    """

    def __init__(
        self,
        ops: Sequence[Op],
        depths: Sequence[int],
        cops: Sequence[CompiledOp],
        layout: Layout,
        dom: Domain,
        cands: dict[int, ReduceCandidate],
    ) -> None:
        self.ops, self.depths, self.cops = ops, depths, cops
        self.layout, self.cands = layout, cands
        # CCX-Index -> Gruppenkandidat, in dem er aufgeht
        self.member_of: dict[int, int] = {}
        for i, c in cands.items():
            if c.kind in GROUP_CANDIDATES:
                for j in c.members[:-1]:
                    self.member_of[j] = i
        # Ziel -> (erster, letzter Index) je Gruppenkandidat
        self.spans: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for i, c in cands.items():
            if c.kind in GROUP_CANDIDATES:
                self.spans[ops[i].qs[2]].append((c.members[0], i))
        # Lane-Vektor -> Z_POW-Indizes mit genau diesem Vektor
        self.zgroups: dict[LaneVector, list[int]] = {}
        # CCX-Index -> Kontrollprodukt an seiner Originalposition
        self.stash: dict[int, LaneVector] = {}
        self.repl: dict[int, list[Op]] = {}
        self.delete: set[int] = set()
        self.stats: Counter[str] = Counter()
        # HMR auf Qubits, die auf der ganzen Domäne |0> sind
        self.idle_hmr: list[int] = []
        self.st, self.taint = State(dom, CONFIRM_SEED), Taint()

    def confirm(self) -> None:
        """Simuliert die ganze Domäne einmal durch und füllt
        repl/delete/stats/zgroups/idle_hmr."""
        cops, st, taint = self.cops, self.st, self.taint
        for i, op in enumerate(self.ops):
            if self._is_idle_hmr(i, op):
                self.idle_hmr.append(i)
            n = op.name
            if (
                n not in META_OPS
                and n not in CONDITION_STACK_OPS
                and not any(q in taint.random_qubits for q in op.qs)
            ):
                self._visit_deterministic(i, op)
            step(st, cops[i])
            taint.advance(op)

    def _is_idle_hmr(self, i: int, op: Op) -> bool:
        """Unbedingtes HMR auf einem messunabhängigen Scratch-Qubit, das hier auf der
        ganzen Domäne |0> ist (Kandidat für _without_idle_hmr)."""
        return (
            op.name == "HMR"
            and op.cond is None
            and self.depths[i] == 0
            and op.qs[0] not in self.taint.random_qubits
            and op.qs[0] not in self.layout.pinned
            and self.st.q.get(op.qs[0], 0) == 0
        )

    def _visit_deterministic(self, i: int, op: Op) -> None:
        """Untersucht eine Instruktion, deren Qubits nicht vom Messzufall abhängen:
        direkte Entscheidung, Z_POW-Gruppe, Kontrollprodukt merken, Kandidat
        bestätigen."""
        st = self.st
        m = cur_mask(st, op.cond)
        rnd = self.taint.mask_random(op)
        g = st.q.get
        dec = direct_decision(op, st, m, rnd)
        if dec is not None:
            self._apply_decision(i, op, dec)
        if op.name == "Z_POW" and dec is None and is_plain_phase(op, self.depths[i]):
            self.zgroups.setdefault(g(op.qs[0], 0), []).append(i)
        cand = self.cands.get(i)
        if op.name == "CCX" and (
            i in self.member_of or (cand and cand.kind != CAND_LINEAR)
        ):
            self.stash[i] = g(op.qs[0], 0) & g(op.qs[1], 0)
        if cand is None:
            return
        mm = st.all_lanes if (m is None or rnd) else m
        if cand.kind == CAND_LINEAR:
            if dec is None:
                self._confirm_linear(i, op, cand.terms, mm)
        elif all(j in self.stash for j in cand.members):
            self._confirm_group(i, op, cand, mm)

    def _apply_decision(self, i: int, op: Op, dec: DirectDecision) -> None:
        """Übernimmt eine direkte Entscheidung (gilt auf allen Lanes)."""
        self.repl[i] = apply_direct(op, dec)
        self.stats[dec.kind] += 1
        self.stats[STAT_TOFFOLI_SAVED] += op.name in TOFFOLI_LIKE and not any(
            o.name in TOFFOLI_LIKE for o in self.repl[i]
        )

    def _inside_group(self, q: XorTerm, i: int) -> bool:
        """Würde ein neuer Lesezugriff auf q an Position i in eine (mögliche)
        Gruppenumformung von q fallen?"""
        return any(a < i < b for a, b in self.spans.get(q, ()))

    def _confirm_linear(
        self, i: int, op: Op, terms: Sequence[XorTerm], mm: LaneVector
    ) -> None:
        """Übernimmt einen "lin"-Kandidaten, wenn Produkt = XOR(terms) auf allen
        (aktiven) Lanes gilt."""
        g = self.st.q.get
        v = toffoli_product_lanes(op, g, mm)
        if xor_of_terms(terms, g, mm) == v and not any(
            self._inside_group(x, i) for x in terms
        ):
            self.repl[i] = linear_replacement(op, terms)
            self.stats[CAND_LINEAR] += 1
            self.stats[STAT_TOFFOLI_SAVED] += 1

    def _confirm_group(
        self, i: int, op: Op, cand: GroupCandidate, mm: LaneVector
    ) -> None:
        """Übernimmt einen Gruppenkandidaten: die an den Originalpositionen gemerkten
        Kontrollprodukte müssen in Summe dem Ersatz an Position i entsprechen. Die
        übrigen CCX der Gruppe werden gelöscht.
        """
        g, stash, repl, delete = self.st.q.get, self.stash, self.repl, self.delete
        kind, members = cand.kind, cand.members
        delta = 0
        for j in members:
            delta ^= stash[j]
        t = op.qs[2]
        if kind == CAND_GROUP_AFFINE:
            ok = xor_of_terms(cand.terms, g, mm) == delta
            new = lin_ops(cand.terms, t, None)
        else:
            u, wset, lset = cand.u, cand.wset, cand.lset
            product = xor_of_terms(u, g, mm) & xor_of_terms(wset, g, mm)
            ok = product ^ xor_of_terms(lset, g, mm) == delta
            new = product_group_replacement(u, wset, lset, t)
        if not ok or any(self._inside_group(x, i) for x in candidate_reads(cand)):
            return
        # Toffolis, die die Gruppe bisher noch kostet (gelöschte oder bereits
        # Toffoli-frei ersetzte zählen nicht)
        before = sum(
            1
            for j in members
            if j not in delete
            and not (j in repl and not any(o.name == "CCX" for o in repl[j]))
        )
        for j in members[:-1]:
            delete.add(j)
            repl.pop(j, None)
        repl[i] = new
        self.stats[kind] += 1
        self.stats[STAT_TOFFOLI_SAVED] += before - (kind == CAND_GROUP_PRODUCT)

    def merge_equal_rotations(self) -> None:
        """Rotationen auf Qubits mit identischem Wert (auf der ganzen Domäne) sind EINE
        Rotation mit der Winkelsumme; sie bleibt an der Stelle der letzten stehen."""
        ops, repl, delete = self.ops, self.repl, self.delete
        for idxs in self.zgroups.values():
            if len(idxs) > 1:
                total = sum((phase_exponent(ops[j]) for j in idxs), Fraction(0))
                for j in idxs[:-1]:
                    delete.add(j)
                    repl.pop(j, None)
                both = phase_op(ops[idxs[-1]].qs[0], total, None)
                repl[idxs[-1]] = [both] if both else []
                self.stats[STAT_PHASE_MERGE] += len(idxs) - 1

    def rewritten(self, drop_idle_hmr: bool) -> list[Op]:
        """Wendet repl/delete an (und streicht auf Wunsch überflüssige HMR). Ohne
        Änderung: Kopie von `ops`."""
        ops, repl, delete, idle_hmr = self.ops, self.repl, self.delete, self.idle_hmr
        if not repl and not delete and not (drop_idle_hmr and idle_hmr):
            return list(ops)
        out: list[Op] = []
        pos: dict[int, int] = {}  # alter Index -> Position des (ersten) Ersatzes in out
        for i, op in enumerate(ops):
            if i in delete:
                continue
            pos[i] = len(out)
            if i in repl:
                out.extend(repl[i])
            else:
                out.append(op)
        if drop_idle_hmr and idle_hmr:
            out = self._without_idle_hmr(out, pos)
        if ops_unchanged(out, ops):
            return list(ops)
        return out

    def _without_idle_hmr(self, out: list[Op], pos: dict[int, int]) -> list[Op]:
        """Ein HMR auf einem |0>-Qubit hat keinen Kickback; es darf weg, wenn sein Bit
        danach nicht mehr gelesen wird."""
        depths = push_depths(out)
        gone = {
            pos[i]
            for i in self.idle_hmr
            if i in pos
            and out[pos[i]].name == "HMR"
            and dead_bits_after(out, pos[i], {out[pos[i]].bit}, self.layout, depths)
        }
        if not gone:
            return out
        self.stats[STAT_IDLE_HMR] = len(gone)
        return [o for k, o in enumerate(out) if k not in gone]
