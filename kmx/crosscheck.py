"""Gegenprüfung mit der offiziellen kickmix-Bibliothek (optional)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from kmx._optional import kickmix
from kmx.cost import Metrics, compute_metrics
from kmx.domains import Domain, sample_domain
from kmx.layout import Layout
from kmx.ops import Op, format_ops

KICKMIX_SAMPLE_SEED = 7
KICKMIX_MISSING = (
    "kickmix nicht installiert (pip install kickmix) - Gegenprüfung übersprungen"
)
KICKMIX_DEFAULT_SHOTS = 4096  # Stichprobe der Gegenprüfung ohne --kickmix-full

# (kickmix.Circuit, Qubit -> Wert über alle Shots, Phase je Shot); kickmix ist optional
KickmixRun = tuple[Any, dict[int, int], list[Any]]


def kickmix_simulate(ops: Sequence[Op], dom: Domain) -> KickmixRun:
    """Lässt `ops` im offiziellen Simulator laufen, ein Shot
    je Lane der Domäne `dom`."""
    circ = kickmix.Circuit(format_ops(ops))
    sim = kickmix.Simulator(batch_size=dom.n, debug_print=False)
    for q, v in dom.init_q.items():
        sim.write_across_shots(kickmix.q(q), v)
    sim.do(circ)
    qvals = {
        q: sim.read_across_shots(kickmix.q(q), out=int) for q in range(circ.num_qubits)
    }
    phases = [sim.read_shot_phase(i) for i in range(dom.n)]
    return circ, qvals, phases


def kickmix_crosscheck_problems(
    reference: KickmixRun,
    candidate: KickmixRun,
    metrics: Metrics,
    layout: Layout,
    same_phase: bool,
) -> list[str]:
    """Vergleicht zwei kickmix-Läufe: eigene Kennzahlen gegen kickmix,
    Registerinhalt, Scratch und (nur wenn `same_phase`) die Phase je Shot modulo
    einer vollen Umdrehung."""
    _, q0, p0 = reference
    c1, q1, p1 = candidate
    problems = []
    if (
        c1.num_qubits != metrics.num_qubits
        or c1.operation_statistics().num_toffoli_like != metrics.toffoli
    ):
        problems.append("Kennzahlen weichen von kickmix ab")
    if any(q0.get(q, 0) != q1.get(q, 0) for q in layout.pinned):
        problems.append("Registerinhalt weicht ab")
    if any(v for q, v in q1.items() if q not in layout.pinned):
        problems.append("Scratch nicht sauber")
    bad = (
        sum(1 for a, b in zip(p0, p1, strict=False) if (a - b) % 2 != 0)
        if same_phase
        else 0
    )
    if bad:
        problems.append(f"Phase weicht in {bad} Shots ab")
    return problems


def kickmix_crosscheck(
    orig: Sequence[Op],
    new: Sequence[Op],
    layout: Layout,
    shots: int = KICKMIX_DEFAULT_SHOTS,
    full: Domain | None = None,
    same_phase: bool = True,
) -> str:
    """Unabhängige Kontrolle mit dem offiziellen Simulator: parst die Ausgabe,
    vergleicht Kennzahlen und prüft auf einer Stichprobe Registerinhalt, saubere
    Scratch-Qubits und die exakte Phase je Shot.
    """
    if kickmix is None:
        return KICKMIX_MISSING
    dom = (
        full if full is not None else sample_domain(layout, shots, KICKMIX_SAMPLE_SEED)
    )
    reference = kickmix_simulate(orig, dom)
    candidate = kickmix_simulate(new, dom)
    metrics = compute_metrics(new)
    problems = kickmix_crosscheck_problems(
        reference, candidate, metrics, layout, same_phase
    )
    if problems:
        return "kickmix-Gegenprüfung FEHLGESCHLAGEN: " + "; ".join(problems)
    return (
        "kickmix-Gegenprüfung bestanden: Ausgabe geparst, "
        f"Q={candidate[0].num_qubits}, Toffoli={metrics.toffoli}, "
        f"{dom.n:,} Shots ({dom.label}) mit identischem Register, sauberem Scratch"
        + (
            " und exakt gleicher Phase"
            if same_phase
            else " (Phase bewusst verändert, siehe Toleranzprüfung)"
        )
    )
