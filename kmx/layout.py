"""Registerstruktur eines Schaltkreises: Eingaberegister, feste Qubits und gültiger
Wertebereich (inkl. invsqrt-Kontrakt).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

from kmx.ops import BIT_PREFIX, QUBIT_PREFIX, REGISTER_PREFIX, KmxError, Op, is_id

INVSQRT_WIDTH, INVSQRT_MAX_X = 22, 3133452  # n_p = 10: x in [1, 3*(2^10-2)^2]
INVSQRT_MIN_X = 1
VALUE_RANGE_SEPARATOR = ":"


@dataclass
class Layout:
    """Registerstruktur eines Schaltkreises: welche Qubits Eingabe sind, welche ihren
    Index behalten müssen und auf welchem Wertebereich des Eingaberegisters der
    Schaltkreis korrekt sein muss."""

    # Registernummer -> Token (qN / bN) in Deklarationsreihenfolge
    registers: dict[int, list[str]]
    names: dict[int, str]  # Registernummer -> Name aus dem REGISTER-Text
    input_qubits: list[int]  # Eingaberegister, niederwertigstes Bit zuerst
    pinned: set[int]  # alle Register-Qubits (behalten ihren Index)
    reg_bits: list[int]  # klassische Bits, die in einem Register stehen (aufsteigend)
    lo: int | None = None  # gültiger Wertebereich des Eingaberegisters
    hi: int | None = None
    notes: list[str] = field(default_factory=list)
    invsqrt: bool = False  # offizieller invsqrt-Kontrakt (22 Bit, x in [1, 3133452])


def _declared_registers(
    ops: Sequence[Op],
) -> tuple[dict[int, list[str]], dict[int, str]]:
    """Sammelt REGISTER / APPEND_TO_REGISTER ein: (Registernummer -> Token,
    Registernummer -> Name). Die Schlüsselreihenfolge ist die des ersten
    Auftretens im Schaltkreis."""
    registers: dict[int, list[str]] = defaultdict(list)
    names: dict[int, str] = {}
    for o in ops:
        if (
            o.name == "APPEND_TO_REGISTER"
            and len(o.args) == 2
            and is_id(o.args[1], REGISTER_PREFIX)
        ):
            registers[int(o.args[1][1:])].append(o.args[0])
        elif o.name == "REGISTER" and o.args and is_id(o.args[0], REGISTER_PREFIX):
            registers.setdefault(int(o.args[0][1:]), [])
            if o.text:
                names[int(o.args[0][1:])] = o.text.strip('"')
    return registers, names


def _select_input_qubits(
    qubit_registers: dict[int, list[int]],
    names: dict[int, str],
    input_register: str,
    fallback_inputs: int,
    notes: list[str],
) -> list[int]:
    """Qubits des Eingaberegisters: das Register namens `input_register`, sonst das mit
    der kleinsten Nummer, sonst q0..q{fallback_inputs-1}. Jede Abweichung vom
    Normalfall wird in `notes` vermerkt.
    """
    chosen = next((r for r in qubit_registers if names.get(r) == input_register), None)
    if chosen is None and qubit_registers:
        chosen = min(qubit_registers)
        notes.append(
            f"Kein Register namens '{input_register}' gefunden; nutze r{chosen} "
            "als Eingabe."
        )
    if chosen is None:
        notes.append(
            "Keine REGISTER-Deklaration gefunden; nehme "
            f"q0..q{fallback_inputs - 1} als Eingaberegister an."
        )
        return list(range(fallback_inputs))
    return qubit_registers[chosen]


def _parse_value_range(value_range: str, width: int) -> tuple[int, int]:
    """'LO:HI' -> (LO, HI); verlangt 0 <= LO <= HI < 2^width, sonst wäre die
    'vollständige' Domäne gelogen."""
    try:
        lo_text, hi_text = value_range.split(VALUE_RANGE_SEPARATOR)
        lo, hi = int(lo_text), int(hi_text)
    except ValueError:
        raise KmxError(
            f"--range erwartet LO:HI mit ganzen Zahlen, nicht {value_range!r}"
        ) from None
    if not 0 <= lo <= hi < (1 << width):
        raise KmxError(
            f"--range {value_range}: verlangt 0 <= LO <= HI < 2^{width} (Breite "
            "des Eingaberegisters)"
        )
    return lo, hi


def analyze_layout(
    ops: Sequence[Op],
    input_register: str = "x",
    value_range: str | None = None,
    fallback_inputs: int = INVSQRT_WIDTH,
) -> Layout:
    """Leitet das Layout aus den Registerdeklarationen ab.

    `value_range` ("LO:HI") legt den gültigen Wertebereich fest. Ohne Angabe gilt der
    invsqrt-Kontrakt, sobald das Eingaberegister 22 Qubits hat und es keine weiteren
    Register-Qubits gibt; sonst bleibt der Bereich offen.
    """
    registers, names = _declared_registers(ops)
    notes: list[str] = []
    qubit_registers = {
        r: [int(t[1:]) for t in tokens if t[0] == QUBIT_PREFIX]
        for r, tokens in registers.items()
    }
    qubit_registers = {r: qubits for r, qubits in qubit_registers.items() if qubits}
    inputs = _select_input_qubits(
        qubit_registers, names, input_register, fallback_inputs, notes
    )
    pinned = set(inputs)
    for qubits in qubit_registers.values():
        pinned.update(qubits)
    reg_bits = sorted(
        {
            int(t[1:])
            for tokens in registers.values()
            for t in tokens
            if t[0] == BIT_PREFIX
        }
    )
    lo = hi = None
    if value_range:
        lo, hi = _parse_value_range(value_range, len(inputs))
    elif len(inputs) == INVSQRT_WIDTH and len(pinned) == INVSQRT_WIDTH:
        lo, hi = INVSQRT_MIN_X, INVSQRT_MAX_X
        notes.append(
            f"{INVSQRT_WIDTH}-Bit-Eingaberegister erkannt: nehme den invsqrt-Kontrakt "
            f"x in [{INVSQRT_MIN_X}, {INVSQRT_MAX_X}] an (mit --range LO:HI "
            "überschreibbar)."
        )
    is_invsqrt = (
        (lo, hi) == (INVSQRT_MIN_X, INVSQRT_MAX_X)
        and len(inputs) == INVSQRT_WIDTH
        and pinned == set(inputs)
    )
    return Layout(
        dict(registers), names, inputs, pinned, reg_bits, lo, hi, notes, is_invsqrt
    )
