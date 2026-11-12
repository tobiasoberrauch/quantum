"""Domänen: Mengen gleichzeitig simulierter Trajektorien (Lanes) - vollständig über alle
gültigen Eingaben oder als Stichprobe.
"""

from __future__ import annotations

import random
from collections.abc import Callable

from kmx.layout import Layout

# Lane-Vektor: Python-Ganzzahl, deren Bit i den Wert der Trajektorie (Lane) i trägt.
LaneVector = int
# Schlüssel eines Messergebnisses: (Art "H"|"R", Bit bzw. Qubit, wievielte Ziehung).
MeasurementKey = tuple[str, int, int]

# Startwert der Stichproben-Domäne (zweites Ergebnis von build_domains)
SAMPLE_DOMAIN_SEED = 1
# Startwert der Ersatz-Domäne, wenn die Eingaben nicht aufzählbar sind
FALLBACK_DOMAIN_SEED = 2


def first_lane(lanes: LaneVector) -> int:
    """Index der niedrigsten gesetzten Lane (-1, wenn keine gesetzt ist)."""
    return (lanes & -lanes).bit_length() - 1


def pattern_bit(k: int, m: int) -> LaneVector:
    """Lane-Vektor der Länge m: Lane i trägt Bit k der Zahl i."""
    half = 1 << k
    v, length = ((1 << half) - 1) << half, half << 1
    while length < m:
        v |= v << length
        length <<= 1
    return v & ((1 << m) - 1)


class Domain:
    """Menge gleichzeitig simulierter Trajektorien (Lanes).

    `init_q` belegt die Qubits je Lane vor, `exhaustive` sagt, ob die Lanes ALLE
    gültigen Eingaben abdecken (nur dann sind Simulationsfakten Beweise), `describe`
    benennt eine Lane für Meldungen. Ist `truth_table` gesetzt, kommen Messergebnisse
    aus dieser Tabelle statt aus dem Zufallsgenerator (Wahrheitstabelle von L1).
    `all_lanes` ist die Maske aller n Lanes.
    """

    def __init__(
        self,
        n: int,
        init_q: dict[int, LaneVector],
        exhaustive: bool,
        label: str,
        describe: Callable[[int], str],
        truth_table: dict[MeasurementKey, LaneVector] | None = None,
    ) -> None:
        self.n, self.all_lanes, self.init_q = n, (1 << n) - 1, init_q
        self.exhaustive, self.label, self.describe = exhaustive, label, describe
        self.truth_table = truth_table


def exhaustive_domain(layout: Layout) -> Domain:
    """Domäne mit genau einer Lane je gültigem Eingabewert x in [lo, hi]
    (Lane i trägt x = lo + i)."""
    lo, hi = layout.lo, layout.hi
    n = hi - lo + 1
    init = {q: pattern_bit(k, hi + 1) >> lo for k, q in enumerate(layout.input_qubits)}
    return Domain(
        n,
        init,
        True,
        f"alle {n:,} Eingaben x in [{lo}, {hi}]",
        lambda lane: f"x={lo + lane}",
    )


def _boundary_sample_values(lo: int, hi: int, width: int) -> list[int]:
    """Aufsteigend sortierte Randwerte des Eingabebereichs: beide Enden und
    alle Zweierpotenzen +-1."""
    vals = {lo, hi, min(hi, lo + 1), max(lo, hi - 1)}
    for k in range(width + 1):
        for d in (-1, 0, 1):
            if lo <= (1 << k) + d <= hi:
                vals.add((1 << k) + d)
    return sorted(vals)


def sample_domain(layout: Layout, n: int, seed: int) -> Domain:
    """Stichproben-Domäne mit n Lanes: zuerst die Randwerte, dann Zufallswerte aus [lo,
    hi]. Register-Qubits außerhalb des Eingaberegisters werden zufällig vorbelegt."""
    rng = random.Random(seed)
    width = len(layout.input_qubits)
    lo = layout.lo if layout.lo is not None else 0
    hi = layout.hi if layout.hi is not None else (1 << width) - 1
    vals_l = _boundary_sample_values(lo, hi, width)[:n]
    while len(vals_l) < n:
        vals_l.append(rng.randint(lo, hi))
    init = {
        q: sum(((v >> k) & 1) << i for i, v in enumerate(vals_l))
        for k, q in enumerate(layout.input_qubits)
    }
    for q in sorted(layout.pinned - set(layout.input_qubits)):
        init[q] = rng.getrandbits(n)
    return Domain(
        n, init, False, f"{n:,} Stichproben-Eingaben", lambda lane: f"x={vals_l[lane]}"
    )


def build_domains(
    layout: Layout, max_exhaustive: int, sample_lanes: int, fallback_lanes: int
) -> tuple[Domain, Domain]:
    """Liefert (Hauptdomäne, Stichproben-Domäne). Die Hauptdomäne ist vollständig, wenn
    das Eingaberegister das einzige Register ist und sein Wertebereich höchstens
    `max_exhaustive` Werte hat; sonst eine größere Stichprobe."""
    sample_dom = sample_domain(layout, sample_lanes, SAMPLE_DOMAIN_SEED)
    only_input_pinned = set(layout.input_qubits) == layout.pinned
    if (
        layout.lo is not None
        and only_input_pinned
        and layout.hi - layout.lo + 1 <= max_exhaustive
    ):
        return exhaustive_domain(layout), sample_dom
    return sample_domain(layout, fallback_lanes, FALLBACK_DOMAIN_SEED), sample_dom
