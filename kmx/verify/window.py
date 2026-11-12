"""L1 und L2: Fenster exakt über alle Belegungen (Wahrheitstabelle, Differenzkegel,
Phasenraster) und kontextuell auf den erreichbaren Zuständen.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from enum import Enum

from kmx.cost import SIGN_PLANE, phase_exponent
from kmx.domains import Domain, LaneVector, first_lane, pattern_bit
from kmx.layout import Layout
from kmx.ops import BIT_OPS, META_OPS, UNITARY_OPS, Op, OpKey, bit_token, qubit_token
from kmx.simulator import DRAW_HMR, DRAW_RESET, State, compile_ops, step

EXACT_MAX_VARIABLES = 20  # größte Wahrheitstabelle von L1: 2^20 Belegungen

# Variable der L1-Wahrheitstabelle: ("q", Qubit) | ("b", Bit) | ("top",) |
# MeasurementKey ("H"|"R", Bit bzw. Qubit, Ziehung).
TruthTableKey = tuple[str, ...] | tuple[str, int] | tuple[str, int, int]
KEY_QUBIT, KEY_BIT, KEY_TOP = "q", "b", "top"
# Erste Abweichung zweier Fensterzustände: (Beschreibung, Lane).
WindowDifference = tuple[str, int]


class ExactStatus(str, Enum):
    """Ergebnis von check_exact. Der str-Anteil hält die alten Werte vergleichbar
    (ExactStatus.PROVED == "proved"); Ausgaben zeigen den Wert, nicht den Namen."""

    PROVED = "proved"
    REFUTED = "refuted"
    UNDECIDED = "na"

    __str__ = str.__str__
    __format__ = str.__format__
    __hash__ = str.__hash__


def op_bits_written(ops: Sequence[Op]) -> set[int]:
    """Bits, die das Fenster schreibt (HMR-Ergebnisse und BIT_*-Instruktionen)."""
    return {
        o.bit
        for o in ops
        if o.bit is not None and (o.name == "HMR" or o.name in BIT_OPS)
    }


def _op_bits_read(ops: Sequence[Op]) -> set[int]:
    """Bits, die das Fenster als Bedingung liest."""
    return {o.cond for o in ops if o.cond is not None}


def _has_randomness(ops: Sequence[Op]) -> bool:
    """Kann der Messzufall das Fenster beeinflussen (Messung, Reset
    oder bedingte Instruktion)?"""
    return any(o.name in ("HMR", "R") or o.cond is not None for o in ops)


def _bit_read_before_overwrite(
    ops: Sequence[Op], start: int, bit: int, depths: Sequence[int]
) -> bool:
    """Wird der Wert von `bit` ab Index `start` noch gelesen, bevor ihn eine unbedingte
    Instruktion auf Stapeltiefe 0 überschreibt? BIT_INVERT liest den alten Wert,
    bedingte Schreiber lassen ihn teils stehen.
    """
    for j in range(start, len(ops)):
        o = ops[j]
        if o.cond == bit:
            return True
        if o.bit == bit and o.name not in META_OPS:
            if o.name == "BIT_INVERT":
                return True
            if o.cond is None and depths[j] == 0:
                return False
    return False


def dead_bits_after(
    ops: Sequence[Op], end: int, bits: set[int], layout: Layout, depths: Sequence[int]
) -> set[int]:
    """Bits, deren Wert nach Index `end` nie mehr gelesen wird (vor dem nächsten
    unbedingten Überschreiben). Register-Bits sind nie tot: sie gehören zum Ergebnis."""
    dead = set()
    for b in bits:
        if b in layout.reg_bits:
            continue
        if not _bit_read_before_overwrite(ops, end + 1, b, depths):
            dead.add(b)
    return dead


def compare_window_states(
    sa: State, sb: State, qubits: set[int], bits: set[int], dom: Domain
) -> WindowDifference | None:
    """Vergleicht zwei Zustände nach einem Fenster. Liefert (Beschreibung,
    Lane) der ersten Abweichung."""
    for q in sorted(qubits):
        diff = sa.q.get(q, 0) ^ sb.q.get(q, 0)
        if diff:
            return f"Qubit {qubit_token(q)}", first_lane(diff)
    for j, (x, y) in enumerate(zip(sa.planes(), sb.planes(), strict=True)):
        if x != y:
            what = (
                "Phase (Vorzeichen)"
                if j == SIGN_PLANE
                else f"Phase (Ebene 2^-{SIGN_PLANE - j} Halbdrehung)"
            )
            return what, first_lane(x ^ y)
    for b in sorted(bits):
        diff = sa.b.get(b, 0) ^ sb.b.get(b, 0)
        if diff:
            return f"Bit {bit_token(b)}", first_lane(diff)
    if len(sa.stack) != len(sb.stack):
        return "Bedingungsstapel (Tiefe)", 0
    top_a = sa.all_lanes if sa.top is None else sa.top
    top_b = sb.all_lanes if sb.top is None else sb.top
    if top_a != top_b:
        return "Bedingungsstapel", first_lane(top_a ^ top_b)
    return None


def exact_keys(
    orig_w: Sequence[Op], cand_w: Sequence[Op], entry_depth: int
) -> list[TruthTableKey]:
    """Freie Variablen eines Fensters: Qubits, gelesene Bits, Bedingungskontext,
    Messergebnisse. Je Messstelle (HMR-Bit bzw. R-Qubit) so viele Ergebnisse, wie das
    Fenster mit den meisten Ziehungen braucht.
    """
    both = list(orig_w) + list(cand_w)
    qubits = sorted({q for o in both for q in o.qs})
    # Auch nur geschriebene Bits sind frei: ihr Startwert ist unbekannt ("b0 := 0" ist
    # nicht "b0 unverändert").
    bits = sorted(_op_bits_read(both) | op_bits_written(both))
    keys: list[TruthTableKey] = [(KEY_QUBIT, q) for q in qubits]
    keys += [(KEY_BIT, b) for b in bits]
    if entry_depth:
        keys.append((KEY_TOP,))
    for tag, name in ((DRAW_HMR, "HMR"), (DRAW_RESET, "R")):
        draws_needed: Counter[int] = Counter()
        for w in (orig_w, cand_w):
            draws = Counter(
                (o.bit if tag == DRAW_HMR else o.qs[0]) for o in w if o.name == name
            )
            for ident, k in draws.items():
                draws_needed[ident] = max(draws_needed[ident], k)
        for ident, k in sorted(draws_needed.items()):
            keys += [(tag, ident, i) for i in range(k)]
    return keys


def off_grid_phase(ops: Sequence[Op]) -> Op | None:
    """Erstes Z_POW, dessen Exponent nicht auf dem 2^-127-Raster liegt. Der Simulator
    rundet solche Winkel; ein Fenstervergleich wäre dann kein Beweis mehr (ein Winkel
    unter 2^-128 sähe aus wie die Identität).
    """
    return next(
        (o for o in ops if o.name == "Z_POW" and phase_exponent(o) is None), None
    )


def _strip_common_gates(
    orig_w: Sequence[Op], cand_w: Sequence[Op]
) -> tuple[Sequence[Op], Sequence[Op]]:
    """Entfernt das längste gemeinsame Präfix und danach das längste gemeinsame Suffix
    beider Fenster (Vergleich über Op.key). Die Reste überlappen das Präfix nicht."""
    keys_a, keys_b = [o.key() for o in orig_w], [o.key() for o in cand_w]
    lo = 0
    while lo < len(keys_a) and lo < len(keys_b) and keys_a[lo] == keys_b[lo]:
        lo += 1
    hi_a, hi_b = len(keys_a), len(keys_b)
    while hi_a > lo and hi_b > lo and keys_a[hi_a - 1] == keys_b[hi_b - 1]:
        hi_a, hi_b = hi_a - 1, hi_b - 1
    return orig_w[lo:hi_a], cand_w[lo:hi_b]


class _QubitComponents:
    """Zusammenhangskomponenten von Qubits (Union-Find): zwei Qubits hängen zusammen,
    sobald irgendein Gatter der übergebenen Folge beide berührt."""

    __slots__ = ("_root",)

    def __init__(self, ops: Sequence[Op]) -> None:
        self._root: dict[int, int] = {}
        for o in ops:
            for q in o.qs:
                self._root.setdefault(q, q)
            for q in o.qs[1:]:
                self._root[self.find(q)] = self.find(o.qs[0])

    def find(self, q: int) -> int:
        """Vertreter der Komponente von `q` (mit Pfadhalbierung)."""
        root = self._root
        while root[q] != q:
            root[q] = root[root[q]]
            q = root[q]
        return q

    def gate_keys(self, ops: Sequence[Op]) -> dict[int, list[OpKey]]:
        """Gatterfolge (als Op.key) je Komponente, in Programmreihenfolge.
        Gatter ohne Qubit fehlen."""
        by_component: dict[int, list[OpKey]] = defaultdict(list)
        for o in ops:
            if o.qs:
                by_component[self.find(o.qs[0])].append(o.key())
        return by_component

    def restrict(self, ops: Sequence[Op], components: set[int]) -> list[Op]:
        """Gatter von `ops`, die in einer der `components` liegen; Gatter
        ohne Qubit bleiben immer."""
        return [o for o in ops if not o.qs or self.find(o.qs[0]) in components]


def difference_cone(
    orig_w: Sequence[Op], cand_w: Sequence[Op]
) -> tuple[Sequence[Op], Sequence[Op]]:
    """Reduziert zwei Fenster aus unbedingten, unitären Gattern auf das,
    worin sie sich unterscheiden:
      1. L*O*R == L*C*R  <=>  O == C: gemeinsames Präfix und Suffix entfallen.
      2. Gatter verschiedener Qubit-Zusammenhangskomponenten (über BEIDE Reste gebildet)
         kommutieren, der Operator zerfällt in ein Tensorprodukt; Komponenten mit
         identischer Gatterfolge entfallen.
    So passen auch breite Fenster mit vielen unbeteiligten Gattern in die
    Wahrheitstabelle. NEG (globale Phase, ohne Qubit) bleibt immer stehen. Andere
    Fenster kommen unverändert zurück.
    """
    if any(
        o.cond is not None or o.name not in UNITARY_OPS
        for w in (orig_w, cand_w)
        for o in w
    ):
        return orig_w, cand_w
    rest_a, rest_b = _strip_common_gates(orig_w, cand_w)
    components = _QubitComponents((*rest_a, *rest_b))
    gates_a, gates_b = components.gate_keys(rest_a), components.gate_keys(rest_b)
    differing = {
        c for c in gates_a.keys() | gates_b.keys() if gates_a.get(c) != gates_b.get(c)
    }
    return components.restrict(rest_a, differing), components.restrict(
        rest_b, differing
    )


def _truth_table_domain(
    vec: dict[TruthTableKey, LaneVector], n: int, num_vars: int
) -> Domain:
    """Domäne mit einer Lane je Belegung: Qubit-Variablen als Anfangswerte,
    Messergebnisse als Tabelle."""
    return Domain(
        n,
        {k[1]: v for k, v in vec.items() if k[0] == KEY_QUBIT},
        True,
        f"alle 2^{num_vars} Belegungen",
        lambda lane: f"Belegung {lane:#x}",
        truth_table={k: v for k, v in vec.items() if k[0] in (DRAW_HMR, DRAW_RESET)},
    )


def _run_window_on_truth_table(
    window: Sequence[Op],
    dom: Domain,
    vec: dict[TruthTableKey, LaneVector],
    entry_depth: int,
) -> State:
    """Führt ein Fenster auf allen Belegungen aus; gelesene Bits und der
    Bedingungskontext sind frei."""
    st = State(dom)
    st.b = {k[1]: v for k, v in vec.items() if k[0] == KEY_BIT}
    if entry_depth:
        st.top = vec[(KEY_TOP,)]
    for cop in compile_ops(window):
        step(st, cop)
    return st


def check_exact(
    orig_w: Sequence[Op],
    cand_w: Sequence[Op],
    entry_depth: int,
    dead_bits: set[int],
    max_vars: int = EXACT_MAX_VARIABLES,
) -> tuple[ExactStatus, str]:
    """L1: vollständige Wahrheitstabelle über Fenster-Qubits, gelesene Bits,
    Bedingungskontext und alle Messergebnisse. Rückgabe (ExactStatus, Text).

    Beweiskraft hat das nur, weil (a) Winkel außerhalb des Phasenrasters vorab
    abgelehnt werden und (b) difference_cone ausschließlich Gatter streicht, die auf
    beiden Seiten denselben Faktor bilden.
    """
    rough = off_grid_phase((*orig_w, *cand_w))
    if rough is not None:
        return (
            ExactStatus.UNDECIDED,
            f"{rough.fmt()!r} liegt nicht auf dem 2^-127-Phasenraster",
        )
    orig_w, cand_w = difference_cone(orig_w, cand_w)
    keys = exact_keys(orig_w, cand_w, entry_depth)
    if len(keys) > max_vars:
        return ExactStatus.UNDECIDED, f"{len(keys)} Variablen > {max_vars}"
    n = 1 << len(keys)
    vec = {k: pattern_bit(i, n) for i, k in enumerate(keys)}
    dom = _truth_table_domain(vec, n, len(keys))
    st_orig = _run_window_on_truth_table(orig_w, dom, vec, entry_depth)
    st_cand = _run_window_on_truth_table(cand_w, dom, vec, entry_depth)
    qubits = {k[1] for k in keys if k[0] == KEY_QUBIT}
    bits = (op_bits_written(orig_w) | op_bits_written(cand_w)) - dead_bits
    diff = compare_window_states(st_orig, st_cand, qubits, bits, dom)
    if diff is None:
        return (
            ExactStatus.PROVED,
            f"exakt bewiesen über alle 2^{len(keys)} = {n:,} Belegungen "
            "(inkl. Messergebnisse)",
        )
    what, lane = diff
    assign = ", ".join(
        f"{k[0]}{k[1] if len(k) > 1 else ''}={(vec[k] >> lane) & 1}"
        for k in keys
        if k[0] in (KEY_QUBIT, KEY_BIT)
    )
    return ExactStatus.REFUTED, f"allgemeine Belegung verletzt: {what} bei {assign}"


def check_context(
    entry: State,
    orig_w: Sequence[Op],
    cand_w: Sequence[Op],
    dead_bits: set[int],
    dom: Domain,
    rounds: int,
) -> tuple[bool, str, tuple[float, float]]:
    """L2: Fenster auf den tatsächlich erreichten Zuständen. Liefert auch die
    mittleren Toffoli-Kosten. Ohne Zufall im Fenster und ohne
    Bedingungskontext genügt eine Messrunde."""
    both = list(orig_w) + list(cand_w)
    qubits = {q for o in both for q in o.qs}
    bits = (op_bits_written(orig_w) | op_bits_written(cand_w)) - dead_bits
    cops_orig, cops_cand = compile_ops(orig_w), compile_ops(cand_w)
    cost = (0.0, 0.0)
    if not _has_randomness(both) and entry.top is None:
        rounds = 1
    for r in range(rounds):
        st_orig, st_cand = entry.copy(), entry.copy()
        for st in (st_orig, st_cand):
            st.seed, st.count, st.toffoli_lanes = f"{entry.seed}~{r}", True, 0
        for cop in cops_orig:
            step(st_orig, cop)
        for cop in cops_cand:
            step(st_cand, cop)
        cost = (st_orig.toffoli_lanes / st_orig.n, st_cand.toffoli_lanes / st_cand.n)
        diff = compare_window_states(st_orig, st_cand, qubits, bits, dom)
        if diff is not None:
            what, lane = diff
            vals = ", ".join(
                f"{qubit_token(q)}={(entry.q.get(q, 0) >> lane) & 1}"
                for q in sorted(qubits)
            )
            return (
                False,
                f"{what} weicht ab bei {dom.describe(lane)} (Fenstereingang: {vals})",
                cost,
            )
    return True, f"gleich auf {dom.label} x {rounds} Messrunde(n)", cost
