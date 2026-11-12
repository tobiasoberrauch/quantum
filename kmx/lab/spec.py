"""Aufgabenbeschreibungen des Labors als Paketdaten (spec_<name>.json) und ihre
kompakte Textform für die Prompts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kmx.lab.claims import safe_id

SPEC_DIR = Path(__file__).parent
INVSQRT_SPEC = "invsqrt"


def load_spec(name: str) -> dict[str, Any]:
    """Liest kmx/lab/spec_<name>.json; `name` muss eine gültige Kennung sein."""
    if safe_id(name) is None or "." in name:
        raise ValueError(f"ungültiger Spec-Name {name!r}")
    with open(SPEC_DIR / f"spec_{name}.json", encoding="utf-8") as f:
        return json.load(f)


def spec_text(spec: dict[str, Any]) -> str:
    """Kurzfassung für die Prompts: Aufgabe, Register, Domäne, Kontrakt, Kosten."""
    reg, dom, phase, cost = (
        spec["register"],
        spec["domain"],
        spec["phase"],
        spec["cost"],
    )
    lines = [
        f"TASK {spec['task']}: {spec['summary']}",
        f"Register {reg['name']}: {reg['width']} qubits, {reg['bit_order']}, restored.",
        f"Domain: x in [{dom['min_x']}, {dom['max_x']}] ({dom['derivation']}).",
        "Contract: " + "; ".join(spec["contract"]) + ".",
        f"Phase: target {phase['target_turns']} turns with beta = {phase['beta']}.",
        f"Tolerance: tol(x) = {phase['tolerance_turns']} turns with beta = "
        f"{phase['beta']} ({phase['note']}).",
        f"Cost: Q = {cost['Q']}; C = {cost['C']}; rotation = {cost['rotation_t']}; "
        f"eps = {cost['eps']}; score = {cost['score']}.",
    ]
    return "\n".join(lines)


def generic_spec_text(range_text: str | None, input_register: str) -> str:
    """Kurzfassung ohne Paket-Spec (kleine Testschaltkreise mit --range)."""
    return (
        f"TASK: produce a circuit equivalent to the baseline on register "
        f"{input_register} over x in {range_text or 'the declared range'}: register "
        "restored as in the baseline, scratch back to |0>, identical phase. "
        "Cost: score = Q * (Toffoli + T/4 + rotation cost), Q = max qubit index + 1."
    )
