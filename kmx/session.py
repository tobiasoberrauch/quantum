"""Pipeline: Schalter (`Options`) und Sitzung (`Session`), über deren `commit` jede
Änderung End-to-End geprüft wird.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypedDict

from kmx.cost import ROT_WEIGHT, compute_metrics, score_estimate
from kmx.domains import Domain
from kmx.layout import Layout
from kmx.ops import Op, ops_unchanged
from kmx.passes.cancel import CANCEL_DEFAULT_DEPTH, pass_cancel, pass_fold
from kmx.passes.mbu import MbuStats, pass_mbu
from kmx.passes.repack import RepackStats, pass_repack
from kmx.passes.sim_reduce import DEFAULT_BUDGET_S, pass_sim_reduce
from kmx.score import (
    TRIM_DEFAULT_MAX_RATIO,
    ScoreReport,
    TrimStats,
    invsqrt_score,
    trim_rotations,
)
from kmx.simulator import compile_ops, simulate
from kmx.verify.oracle import FinalSig, Oracle, digest, final_sig

# Unabhängigkeit vom Messzufall braucht mindestens zwei Messrunden
_MIN_TOLERANCE_ROUNDS = 2
AUDIT_OK, AUDIT_REJECTED = "OK", "VERWORFEN"


@dataclass
class Options:
    """Schalter und Budgets der deterministischen Pipeline."""

    deep: bool = True
    mbu: bool = True
    repack: bool = True
    iters: int = 3
    final_rounds: int = 4
    budget_s: float = DEFAULT_BUDGET_S
    rot_weight: float = ROT_WEIGHT
    cancel_depth: int = CANCEL_DEFAULT_DEPTH
    # feine Rotationen innerhalb der Toleranz streichen (nicht äquivalent!)
    trim: bool = False
    # dabei nie näher als so an die Toleranzgrenze gehen
    trim_max_ratio: float = TRIM_DEFAULT_MAX_RATIO
    # faktenbasierte Pässe auch ohne vollständige Domäne zulassen
    sampled_facts: bool = False


class PassSummary(TypedDict, total=False):
    """Ergebnis von Session.run_passes (nur Schlüssel der gelaufenen Pässe)."""

    cancelled: int
    phase_merged: int
    sim: dict[str, int]
    mbu: MbuStats
    repack: RepackStats


def _audit_verdict(ok: bool) -> str:
    return AUDIT_OK if ok else AUDIT_REJECTED


class Session:
    """Hält Original, aktuellen Stand, Domänen und Prüfer; alle Änderungen laufen über
    `commit`. `dom` ist die Hauptdomäne (Beweise), `sample_dom` die schnelle
    Stichprobe (Kandidatensuche)."""

    def __init__(
        self,
        ops: Sequence[Op],
        layout: Layout,
        dom: Domain,
        sample_dom: Domain,
        opts: Options,
        log: Callable[[str], None] = print,
    ) -> None:
        self.orig, self.ops = list(ops), list(ops)
        self.layout, self.dom, self.sample_dom = layout, dom, sample_dom
        self.opts, self.log = opts, log
        self.oracle = Oracle(ops, layout, dom, log)
        self.audit: list[str] = []
        self.sig: FinalSig | None = None
        self.clean = True
        # gesetzt, sobald Rotationen gestrichen wurden
        self.trimmed: TrimStats | None = None
        self.orig_sig: FinalSig | None = None

    def run_baseline(self) -> None:
        """Simuliert das Original, merkt sich dessen Signatur und prüft, ob es den
        Kontrakt selbst erfüllt. Nur dann (`clean`) dürfen Pässe laufen, die sich auf
        sauberen Scratch verlassen.
        """
        t = time.time()
        self.sig = self.orig_sig = self.oracle.orig_sig(0)
        issues = self.oracle.self_check()
        self.clean = not issues
        sampling_note = (
            ""
            if self.dom.exhaustive
            else "  (Stichprobe: Fakten sind statistisch, nicht exakt)"
        )
        self.log(f"Domäne: {self.dom.label}" + sampling_note)
        verdict = (
            "Kontrakt erfüllt (Scratch sauber, Register erhalten, "
            "Phase deterministisch)"
            if not issues
            else "ACHTUNG: " + "; ".join(issues)
        )
        self.log(f"Basislauf in {time.time() - t:.1f}s: " + verdict)

    def status_line(self, ops: Sequence[Op], sig: FinalSig | None) -> str:
        """Kennzahlenzeile; mit Signatur zusätzlich Toffoli je Shot und der geschätzte
        Score."""
        m = compute_metrics(ops)
        if sig is None:
            return m.summary()
        s = score_estimate(
            m.num_qubits, sig.tof_mean, sig.t_mean, sig.rot_mean, self.opts.rot_weight
        )
        return f"{m.summary()} | Toffoli/Shot={sig.tof_mean:.2f} | Score≈{s:,.0f}"

    @property
    def current_status_line(self) -> str:
        """`status_line` des aktuellen Stands."""
        return self.status_line(self.ops, self.sig)

    def exact_score(self, ops: Sequence[Op]) -> ScoreReport | None:
        """Exakter invsqrt-Score oder None, wenn er hier nicht berechenbar ist
        (siehe `invsqrt_score`)."""
        return invsqrt_score(ops, self.layout, self.dom)

    def tolerance_check(self, ops: Sequence[Op], rounds: int) -> tuple[bool, str]:
        """Kontraktprüfung ohne Bezug aufs Original: Register erhalten, Scratch
        sauber, Phase vom Messzufall unabhängig und für jedes x innerhalb der
        offiziellen Toleranz."""
        rounds = max(_MIN_TOLERANCE_ROUNDS, rounds)
        init = tuple(
            digest(self.dom.init_q.get(q, 0)) for q in sorted(self.layout.pinned)
        )
        cops, first = compile_ops(ops), None
        for seed in range(rounds):
            sig = final_sig(simulate(cops, self.dom, f"tol{seed}"), self.layout)
            if sig.reg != init or not sig.scratch_clean or sig.depth:
                return (
                    False,
                    "Register, Scratch oder Bedingungsstapel verletzen den Kontrakt",
                )
            if first is not None and sig.planes != first:
                return False, "Phase hängt vom Messzufall ab"
            first = sig.planes
        rep = self.exact_score(ops)
        if rep is None:
            return False, "exakter Score nicht verfügbar"
        # bewusst negiert: auch NaN fällt durch
        if not rep.worst_ratio < 1.0:
            return False, "Phase außerhalb der Toleranz"
        return (
            True,
            f"Kontrakt erfüllt auf {self.dom.label} x {rounds} Messrunden; "
            f"{rep.line()}",
        )

    def trim_rotations_step(self) -> TrimStats | None:
        """Optionaler letzter Schritt (--trim-rotations). Danach ist der Stand die
        neue Vergleichsbasis."""
        new_ops, st = trim_rotations(
            self.ops, self.layout, self.dom, self.opts.trim_max_ratio
        )
        if not st.get("removed"):
            return None
        ok, msg = self.tolerance_check(new_ops, self.opts.final_rounds)
        self.record(
            f"[{_audit_verdict(ok)}] Rotations-Trimmen: {st['removed']} Z_POW "
            f"gestrichen | {msg}"
        )
        if not ok:
            return None
        self.ops, self.trimmed = new_ops, st
        self.oracle = Oracle(new_ops, self.layout, self.dom, self.log)
        self.sig = self.oracle.orig_sig(0)
        return st

    def commit(
        self, name: str, new_ops: list[Op], detail: str, seeds: Sequence[int] = (0,)
    ) -> bool:
        """Übernimmt `new_ops` nur, wenn der End-to-End-Prüfer sie gegen das Original
        bestätigt; protokolliert Annahme wie Ablehnung im Audit."""
        ok, msg, sig = self.oracle.check(new_ops, seeds)
        if ok:
            self.ops, self.sig = new_ops, sig
        self.record(f"[{_audit_verdict(ok)}] {name}: {detail} | {msg}")
        return ok

    def record(self, entry: str) -> None:
        """Hängt `entry` ans Audit und protokolliert es eingerückt."""
        self.audit.append(entry)
        self.log("  " + entry)

    def run_passes(self) -> PassSummary:
        """Lässt die deterministischen Pässe bis zum Fixpunkt (höchstens `iters`
        Runden) laufen, danach einmal das Qubit-Repacking. Jeder Schritt geht
        einzeln durch `commit`."""
        summary: PassSummary = {}
        facts = self.dom.exhaustive or self.opts.sampled_facts
        if not facts:
            self.log(
                "  Keine vollständige Eingabedomäne: Es laufen nur die rein "
                "syntaktischen Pässe. Simulationsgestützte Pässe wären hier nur "
                "statistisch abgesichert (--allow-sampled-facts)."
            )
        for _ in range(self.opts.iters):
            changed = self._cancel_step(summary)
            if facts:
                changed |= self._sim_reduce_step(summary)
                changed |= self._mbu_step(summary)
            if not changed:
                break
        if facts:
            self._repack_step(summary)
        return summary

    def _cancel_step(self, summary: PassSummary) -> bool:
        """Faltung, Auslöschung kommutierender Paare und Phasenfusion (rein
        syntaktisch)."""
        folded, n_folds = pass_fold(self.ops)
        cancelled, n_pairs, n_merged = pass_cancel(folded, self.opts.cancel_depth)
        if not (n_folds or n_pairs or n_merged):
            return False
        ok = self.commit(
            "Auslöschung",
            cancelled,
            f"{n_pairs} Paare gelöscht, {n_merged} Phasengatter zusammengefasst, "
            f"{n_folds} Faltungen",
        )
        summary["cancelled"] = summary.get("cancelled", 0) + n_pairs
        summary["phase_merged"] = summary.get("phase_merged", 0) + n_merged
        return ok

    def _sim_reduce_step(self, summary: PassSummary) -> bool:
        """Simulationsgeführte Reduktion; HMR ohne Wirkung fallen nur bei sauberem
        Original weg."""
        o = self.opts
        reduced, st = pass_sim_reduce(
            self.ops,
            self.layout,
            self.dom,
            self.sample_dom,
            o.deep,
            o.budget_s,
            drop_idle_hmr=self.clean,
        )
        if ops_unchanged(reduced, self.ops):
            return False
        ok = self.commit(
            "Simulationsgeführte Reduktion", reduced, json.dumps(st, ensure_ascii=False)
        )
        summary["sim"] = st
        return ok

    def _mbu_step(self, summary: PassSummary) -> bool:
        """Measurement-Based Uncomputation; setzt sauberen Scratch im Original
        voraus."""
        if not (self.opts.mbu and self.clean):
            return False
        rewritten, st = pass_mbu(self.ops, self.layout, self.dom)
        if not st.get("chains"):
            return False
        ok = self.commit("Measurement-Based Uncomputation", rewritten, json.dumps(st))
        summary["mbu"] = st
        return ok

    def _repack_step(self, summary: PassSummary) -> None:
        """Qubit-Repacking; wird nur übernommen, wenn die Qubitzahl tatsächlich
        sinkt."""
        if not (self.opts.repack and self.clean):
            return
        repacked, st = pass_repack(self.ops, self.layout, self.dom)
        if st["q_after"] < st["q_before"]:
            self.commit("Qubit-Repacking", repacked, json.dumps(st))
        else:
            self.log(
                f"  Qubit-Repacking: kein Gewinn (Q={st['q_before']}, "
                f"Scratch-Spitze {st['peak_scratch']})"
            )
        summary["repack"] = st

    def final_check(self) -> tuple[bool, str]:
        """Abschließender End-to-End-Vergleich über `final_rounds` Messrunden."""
        ok, msg, sig = self.oracle.check(self.ops, range(self.opts.final_rounds))
        if ok:
            self.sig = sig
        return ok, msg
