"""Kostenmodell und Phasenarithmetik: alle Kosten- und Phasenkonstanten,
Z_POW-Klassifikation, exakte Phasengatter und statische Kennzahlen (samt der
Kompatibilitätsschnittstelle mit den alten API-Namen).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

from kmx.config import DEFAULT_ROT_WEIGHT, env_float
from kmx.ops import TOFFOLI_LIKE, Op, parse_lines, qubit_token

# Toffoli-Äquivalente je feiner Rotation für die Schnellschätzung (siehe
# DEFAULT_ROT_WEIGHT). Wird EINMAL beim Import gelesen; zum Ändern patcht man dieses
# Modul (kmx.cost.ROT_WEIGHT), siehe kmx.config.
ROT_WEIGHT = env_float("COST_ROT_WEIGHT", DEFAULT_ROT_WEIGHT)
T_PER_TOFFOLI = 4.0  # vier T-Gatter kosten so viel wie ein Toffoli
# Offizielle Synthesekosten einer feinen Rotation: 0.56*log2(1/eps) + 5.3 T-Gatter.
ROT_T_PER_LOG2_INV_EPS = 0.56
ROT_T_OFFSET = 5.3
# Relative Rundungsreserve bei Kosten- und Score-Vergleichen: Unterschiede darunter sind
# Gleitkomma-Rauschen (weder echter Gewinn noch echter Anstieg).
COST_RELATIVE_NOISE = 1e-12

# Phasen sind 128-Bit-Festkommazahlen: Exponent e (Halbdrehungen) <-> round(e * 2^127)
# mod 2^128.
PHASE_FRACTION_BITS = 127
PHASE_PLANES = 128  # Bit-Ebenen des Phasenakkumulators, Einheit 2^-127 Halbdrehung
SIGN_PLANE = PHASE_PLANES - 1  # höchstwertige Ebene = Vorzeichen (eine Halbdrehung)
# Der offizielle Verifier liest nur die oberen 64 Ebenen: Phase in Einheiten von 2^-64
# Umdrehungen.
VERIFIER_PHASE_BITS = 64
ZPOW_LEVEL_CLIFFORD, ZPOW_LEVEL_T, ZPOW_LEVEL_ROTATION = 0, 2, 3
# Kostenklassen einer kompilierten Instruktion (letztes Feld von CompiledOp); 0 = wird
# nicht gezählt. T und Rotation sind die Stufen aus zpow_info. step vergleicht aus
# Tempogründen gegen die Literale.
COST_CLASS_NONE, COST_CLASS_TOFFOLI = 0, 1
COST_CLASS_T, COST_CLASS_ROTATION = ZPOW_LEVEL_T, ZPOW_LEVEL_ROTATION
_CLIFFORD_STEP = 1 << (PHASE_FRACTION_BITS - 1)  # Vielfache einer Vierteldrehung (S)
_T_STEP = 1 << (PHASE_FRACTION_BITS - 2)  # Vielfache einer Achteldrehung (T)

# (gesetzte Bit-Ebenen, Stufe, Festkommawert)
ZpowDetails = tuple[tuple[int, ...], int, int]

_ZPOW_CACHE: dict[str, ZpowDetails] = {}


def zpow_full(exp: str) -> ZpowDetails:
    """Wie `zpow_info`, zusätzlich mit dem 128-Bit-Festkommawert des Exponenten;
    je Exponent-Text gecacht."""
    hit = _ZPOW_CACHE.get(exp)
    if hit is None:
        fixed = round(Fraction(exp) * (1 << PHASE_FRACTION_BITS)) % (1 << PHASE_PLANES)
        planes = tuple(j for j in range(PHASE_PLANES) if (fixed >> j) & 1)
        if fixed % _CLIFFORD_STEP == 0:
            level = ZPOW_LEVEL_CLIFFORD
        elif fixed % _T_STEP == 0:
            level = ZPOW_LEVEL_T
        else:
            level = ZPOW_LEVEL_ROTATION
        hit = _ZPOW_CACHE[exp] = (planes, level, fixed)
    return hit


def zpow_info(exp: str) -> tuple[tuple[int, ...], int]:
    """Exponent (Halbdrehungen) -> (gesetzte Bit-Ebenen in Einheiten von 2^-127, Stufe).
    Stufe: 0 = Clifford (frei), 2 = T-artig (1 T), 3 = feine Rotation."""
    return zpow_full(exp)[:2]


def phase_exponent(op: Op) -> Fraction | None:
    """Exponent von Z / Z_POW in Halbdrehungen, falls er sich ohne Rundung
    auf dem 2^-127-Raster darstellen lässt (nur dann ist das Zusammenfassen
    zweier Rotationen bitgenau)."""
    if op.name == "Z":
        return Fraction(1)
    if op.name == "Z_POW":
        exponent = Fraction(op.args[1])
        if (exponent * (1 << PHASE_FRACTION_BITS)).denominator == 1:
            return exponent
    return None


def phase_op(q: int, exponent: Fraction, cond: int | None) -> Op | None:
    """Phasengatter für einen Exponenten (mod 2): None bei 0, Z bei 1, sonst Z_POW mit
    exakter Dezimalzahl. kickmix verlangt die Form [-+]?[0-9]+.[0-9]+ - keine Brüche,
    keine Exponentialschreibweise.
    """
    reduced = exponent % 2
    if reduced > 1:
        reduced -= 2
    if reduced == 0:
        return None
    if reduced == 1:
        return Op("Z", (qubit_token(q),), cond)
    k = reduced.denominator.bit_length() - 1  # Nenner ist 2^k
    # n / 2^k = n * 5^k / 10^k
    digits = str(abs(reduced.numerator) * 5**k).rjust(k + 1, "0")
    fraction_digits = digits[-k:].rstrip("0") or "0"
    sign = "-" if reduced < 0 else ""
    return Op("Z_POW", (qubit_token(q), f"{sign}{digits[:-k]}.{fraction_digits}"), cond)


def is_plain_phase(op: Op, depth: int) -> bool:
    """Z/Z_POW mit exaktem Rasterexponenten und ohne jede Bedingung (`depth` ist die
    Stapeltiefe vor `op`)."""
    return op.cond is None and depth == 0 and phase_exponent(op) is not None


@dataclass
class Metrics:
    """Statische Kennzahlen eines Schaltkreises (ohne Simulation, also ohne
    Rücksicht auf Bedingungen)."""

    ops: int
    num_qubits: int  # wie kickmix: größter Qubit-Index + 1  (das ist Q im Score)
    distinct_qubits: int
    counts: Counter[str]  # Instruktionsname -> Anzahl
    toffoli: int  # CCX + CCZ + CSWAP, statisch gezählt
    t_like: int
    rotations: int  # nicht-Clifford-, nicht-T-Z_POW

    # Kompatibilitätsschnittstelle: alte API-Namen, damit vorhandene Auswerteskripte
    # weiterlaufen
    @property
    def toffoli_cost(self) -> int:
        """Alter API-Name von `toffoli`."""
        return self.toffoli

    @property
    def inner_cost(self) -> float:
        """Geschätzte Toffoli-Äquivalente: Toffoli + T/4 + ROT_WEIGHT x Rotationen."""
        return self.toffoli + self.t_like / T_PER_TOFFOLI + ROT_WEIGHT * self.rotations

    @property
    def real_cost(self) -> float:
        """Geschätzter Score Q x `inner_cost`."""
        return self.num_qubits * self.inner_cost

    def summary(self) -> str:
        """Einzeilige Übersicht für Log und Konsole."""
        c = self.counts
        return (
            f"Q={self.num_qubits} ({self.distinct_qubits} benutzt) | "
            f"Toffoli-artig={self.toffoli} "
            f"(CCX {c['CCX']}, CCZ {c['CCZ']}, CSWAP {c['CSWAP']}) | "
            f"T={self.t_like} | Rot={self.rotations} | "
            f"CX {c['CX']} | CZ {c['CZ']} | HMR {c['HMR']} | Instruktionen {self.ops}"
        )


def compute_metrics(ops: Sequence[Op] | Sequence[str]) -> Metrics:
    """Statische Kennzahlen. Nimmt Op-Listen oder (alte API) eine Liste von
    Textzeilen."""
    if ops and isinstance(ops[0], str):
        ops = parse_lines(ops)
    counts: Counter[str] = Counter()
    qubits: set[int] = set()
    t_like = rotations = 0
    for o in ops:
        counts[o.name] += 1
        qubits.update(o.qs)
        if o.name == "Z_POW":
            level = zpow_info(o.args[1])[1]
            t_like += level == ZPOW_LEVEL_T
            rotations += level == ZPOW_LEVEL_ROTATION
    toffoli = sum(counts[n] for n in TOFFOLI_LIKE)
    num_qubits = (max(qubits) + 1) if qubits else 0
    return Metrics(
        len(ops), num_qubits, len(qubits), counts, toffoli, t_like, rotations
    )


def score_estimate(
    q: int, toffoli_mean: float, t_mean: float, rot_mean: float, rot_weight: float
) -> float:
    """Schnellschätzung S = Q x (Toffoli + T/4 + rot_weight x
    Rotationen), Mittel pro Shot."""
    return q * (toffoli_mean + t_mean / T_PER_TOFFOLI + rot_mean * rot_weight)


def circuit_cost(lines: Sequence[Op] | Sequence[str]) -> float:
    """Alte API: statische Kostenschätzung einer Zeilen- oder Op-Liste."""
    return compute_metrics(lines).real_cost if lines else 0.0
