"""Rewrite-Vorschläge (`propose_rewrite`): statische Vorprüfungen, Kosten und der
Äquivalenzbeweis eines Fensters."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from kmx.agent.tools import ToolResult
from kmx.cost import compute_metrics
from kmx.domains import Domain
from kmx.layout import Layout
from kmx.ops import REGISTER_DECLARATIONS, TOFFOLI_LIKE, Op, qubit_token
from kmx.simulator import State
from kmx.verify.window import (
    ExactStatus,
    check_context,
    check_exact,
    dead_bits_after,
    op_bits_written,
)

# mindestens so viele Messrunden prüft L2 auf der ganzen Domäne
FULL_CONTEXT_MIN_ROUNDS = 2
SAMPLE_COUNTEREXAMPLE_HINT = "Das Gegenbeispiel ist ein real auftretender Zustand. "


def rewrite_rejection(reason: str, hint: str | None = None) -> ToolResult:
    """Antwort von propose_rewrite bei Ablehnung (mit Hinweis, falls angegeben)."""
    result: ToolResult = {"accepted": False, "reason": reason}
    if hint is not None:
        result["hinweis"] = hint
    return result


def window_structure_error(window: Sequence[Op], who: str) -> str | None:
    """Ein Fenster darf keine Register deklarieren und muss
    PUSH/POP_CONDITION in sich ausgleichen."""
    if any(o.name in REGISTER_DECLARATIONS for o in window):
        return f"{who} enthält Register-Deklarationen"
    depth = 0
    for o in window:
        depth += (o.name == "PUSH_CONDITION") - (o.name == "POP_CONDITION")
        if depth < 0:
            return f"{who}: POP_CONDITION ohne passendes PUSH im Fenster"
    if depth:
        return f"{who}: PUSH/POP im Fenster nicht ausgeglichen"
    return None


def rewrite_shape_error(
    ops: Sequence[Op], orig_w: Sequence[Op], cand_w: Sequence[Op]
) -> str | None:
    """Statische Vorbedingungen eines Rewrites: Fensterstruktur beider Seiten, und der
    Kandidat darf Q nicht erhöhen."""
    for window, who in ((orig_w, "Originalfenster"), (cand_w, "Kandidat")):
        reason = window_structure_error(window, who)
        if reason is not None:
            return reason
    num_qubits = compute_metrics(ops).num_qubits
    if any(q >= num_qubits for o in cand_w for q in o.qs):
        return (
            f"Kandidat nutzt Qubits >= {qubit_token(num_qubits)}; das würde Q erhöhen"
        )
    return None


def window_dead_bits(
    ops: Sequence[Op],
    end: int,
    orig_w: Sequence[Op],
    cand_w: Sequence[Op],
    layout: Layout,
    depths: Sequence[int],
) -> set[int]:
    """Bits, die eines der Fenster schreibt und die hinter dem Fenster niemand mehr
    liest. Bits, die im Schaltkreis sonst gar nicht vorkommen (frische Messbits des
    Kandidaten), sind per Definition tot.
    """
    known_bits = {o.bit for o in ops if o.bit is not None} | {
        o.cond for o in ops if o.cond is not None
    }
    touched = op_bits_written(orig_w) | op_bits_written(cand_w)
    return dead_bits_after(ops, end, touched & known_bits, layout, depths) | (
        touched - known_bits
    )


def static_window_cost(window: Sequence[Op]) -> tuple[int, int]:
    """(Toffoli-artige Gatter, Instruktionen) eines Fensters, ohne
    Rücksicht auf Bedingungen."""
    return sum(o.name in TOFFOLI_LIKE for o in window), len(window)


def prove_window(
    orig_w: Sequence[Op],
    cand_w: Sequence[Op],
    dead: set[int],
    entry_depth: int,
    sample_check: tuple[bool, str],
    exact_only: bool,
    full_entry: Callable[[], State],
    dom: Domain,
    rounds: int,
) -> tuple[str | None, ToolResult | None]:
    """Äquivalenzbeweis für ein Fenster. Rückgabe (Beweistext, None) oder
    (None, Ablehnung).

    Ein exakter Beweis (L1) gilt für alle Belegungen und genügt allein. Sonst muss
    das Fenster kontextuell (L2) halten: erst auf der Stichprobe (`sample_check` =
    (bestanden, Text) vom Aufrufer), dann auf der ganzen Domäne `dom`, deren
    Eingangszustand `full_entry` erst bei Bedarf berechnet. Mit `exact_only` wird der
    kontextuelle Weg gar nicht erst versucht."""
    status, exact_msg = check_exact(orig_w, cand_w, entry_depth, dead)
    if status == ExactStatus.PROVED:
        return exact_msg, None
    if exact_only:
        return None, rewrite_rejection(
            "Kein Beweis über alle Belegungen möglich (--exact-only): " + exact_msg
        )
    sample_ok, sample_msg = sample_check
    if not sample_ok:
        return None, rewrite_rejection(
            "Verifier-Ablehnung (erreichbarer Zustand): " + sample_msg,
            hint=SAMPLE_COUNTEREXAMPLE_HINT
            + (exact_msg if status == ExactStatus.REFUTED else ""),
        )
    full_ok, full_msg, _ = check_context(
        full_entry(),
        orig_w,
        cand_w,
        dead,
        dom,
        max(FULL_CONTEXT_MIN_ROUNDS, rounds // 2),
    )
    if not full_ok:
        return None, rewrite_rejection(
            "Stichprobe bestanden, aber auf der ganzen Domäne widerlegt: " + full_msg
        )
    return "kontextuell verifiziert: " + full_msg, None
