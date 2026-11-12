"""Deterministische Parametersuche ohne LLM: ein Generator mit Raster (`params`) läuft
je Variante in der Sandbox (Variante als schreibgeschützte `params.json`).

Stufe 1 (billig): Ausgabe parsen und die Kosten SCHÄTZEN (`score_estimate` auf den
statischen Kennzahlen). Die Schätzung dient NUR der Reihenfolge, nie dem Verwerfen.
Byte-gleiche Ausgaben werden nur einmal geprüft. Stufe 2: nur die besten
FULL_JUDGE_TOP_K eindeutigen Varianten durchlaufen den vollen Richter (Kontrakt,
exakter Score, offizieller Verifier). Alle übrigen bleiben ohne Urteil und damit ohne
Status; sie werden nur als Notiz "nicht voll geprüft (Budget)" mit ihrer Schätzung
festgehalten. Abgestürzte Varianten tragen das Sandbox-Gegenbeispiel wie bisher.

Die Schätzung stammt aus der Generator-Ausgabe; sie wird nur bei Q innerhalb der
Obergrenze des Richters gebildet und auf zwei Stellen gerundet (schmaler Kanal wie
Q und Toffoli-Zahl einer Bewertung).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from kmx.cost import compute_metrics, score_estimate
from kmx.lab.judge import MAX_CANDIDATE_QUBITS, Evaluation, Judge
from kmx.lab.teams import ParamGrid, param_variants
from kmx.ops import parse_text

FULL_JUDGE_TOP_K = 3
BUDGET_NOTE = "nicht voll geprüft (Budget)"
JUDGED, DUPLICATE, BUDGET, CRASHED = "judged", "duplicate", "budget", "crashed"


@dataclass
class VariantOutcome:
    """Ergebnis einer Variante; `ev` ist nur bei JUDGED/CRASHED ein Urteil."""

    params: dict[str, Any]
    ev: Evaluation
    outcome: str = BUDGET
    estimate: float | None = None
    same_as: dict[str, Any] | None = None  # bei DUPLICATE: die geprüfte Variante


def params_text(params: dict[str, Any]) -> str:
    return json.dumps(params, ensure_ascii=False)


def estimate_output(judge: Judge, data: bytes) -> float | None:
    """Kostenschätzung einer Ausgabe (nur zum Ordnen); None, wenn nicht schätzbar."""
    try:
        m = compute_metrics(parse_text(data.decode("utf-8")))
    except Exception:  # Ausgabe ist nicht vertrauenswürdig; nur Rangfolge betroffen
        return None
    if not 0 < m.num_qubits <= MAX_CANDIDATE_QUBITS:
        return None
    est = score_estimate(
        m.num_qubits, m.toffoli, m.t_like, m.rotations, judge.session.opts.rot_weight
    )
    return round(est, 2)


def rank_variants(
    items: Sequence[tuple[int, str, float | None]], top_k: int
) -> tuple[list[int], dict[int, int], list[int]]:
    """(voll zu prüfen, Duplikat -> geprüfter Vertreter, ungeprüft) aus
    (Index, Ausgabe-SHA, Schätzung). Erster Index je SHA vertritt; Rangfolge nach
    Schätzung (nicht schätzbar zuletzt), bei Gleichstand nach Index."""
    first: dict[str, int] = {}
    duplicates: dict[int, int] = {}
    unique: list[tuple[int, float | None]] = []
    for idx, sha, est in items:
        if sha in first:
            duplicates[idx] = first[sha]
            continue
        first[sha] = idx
        unique.append((idx, est))
    unique.sort(key=lambda t: (t[1] is None, t[1] or 0.0, t[0]))
    order = [idx for idx, _ in unique]
    return order[:top_k], duplicates, order[top_k:]


def search(
    judge: Judge, source: str, grid: ParamGrid, top_k: int = FULL_JUDGE_TOP_K
) -> list[VariantOutcome]:
    """Alle Varianten in fester Reihenfolge; voll bewertet nur die besten `top_k`."""
    outcomes: list[VariantOutcome] = []
    items: list[tuple[int, str, float | None]] = []
    outputs: dict[int, bytes] = {}
    for idx, params in enumerate(param_variants(grid)):
        ev, data = judge.run_variant(source, params)
        out = VariantOutcome(params, ev)
        outcomes.append(out)
        if data is None:
            out.outcome = CRASHED
            continue
        out.estimate = estimate_output(judge, data)
        outputs[idx] = data
        items.append((idx, hashlib.sha256(data).hexdigest(), out.estimate))
    judged, duplicates, _ = rank_variants(items, top_k)
    for idx in judged:
        outcomes[idx].outcome = JUDGED
        judge.judge_output(outcomes[idx].ev, outputs[idx])
    for idx, rep in duplicates.items():
        outcomes[idx].outcome = DUPLICATE
        outcomes[idx].same_as = outcomes[rep].params
    return outcomes


def outcome_note(o: VariantOutcome) -> str:
    """Notiz zu einer Variante ohne eigenes Urteil (kein Status)."""
    head = f"Variante {params_text(o.params)}: "
    if o.outcome == DUPLICATE and o.same_as is not None:
        return head + (
            f"Ausgabe byte-gleich mit Variante {params_text(o.same_as)} "
            "(nicht erneut geprüft)"
        )
    est = f"{o.estimate:,.2f}" if o.estimate is not None else "-"
    return head + f"{BUDGET_NOTE}, Schätzung {est}"
