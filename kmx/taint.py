"""Statische Zufalls-Analyse `Taint`: welche Bits und Qubits hängen von
Messergebnissen ab?"""

from __future__ import annotations

from collections.abc import Callable

from kmx.ops import BIT_OPS, META_OPS, X_TYPE, Op


class Taint:
    """Statische Zufalls-Analyse: Welche Bits/Qubits hängen von Messergebnissen ab?
    Fakten aus der Simulation gelten nur für NICHT markierte Qubits als exakt
    (deterministische Funktion der Eingabe, die vollständig aufgezählt wird)."""

    def __init__(self) -> None:
        self.random_bits: set[int] = set()
        self.random_qubits: set[int] = set()
        # je offener PUSH_CONDITION: hängt die Bedingung vom Zufall ab?
        self.stack: list[bool] = []

    def mask_random(self, op: Op) -> bool:
        """Hängt es vom Messzufall ab, OB `op` ausgeführt wird (eigene Bedingung
        oder offener Kontext)?"""
        return (op.cond is not None and op.cond in self.random_bits) or any(self.stack)

    def advance(self, op: Op) -> None:
        """Schreibt die Markierungen über `op` fort. Konservativ: Markierungen
        fallen nur weg, wenn ein Wert unbedingt und außerhalb jedes
        Bedingungskontexts neu gesetzt wird."""
        name = op.name
        if name == "PUSH_CONDITION":
            self.stack.append(op.cond in self.random_bits)
            return
        if name == "POP_CONDITION":
            if self.stack:
                self.stack.pop()
            return
        if name in META_OPS:
            return
        handler = _TAINT_HANDLERS.get(name)
        if handler is not None:
            handler(self, op, self.mask_random(op), op.cond is None and not self.stack)

    def _measured(self, op: Op, randomly: bool, unconditional: bool) -> None:
        """HMR: das Bit ist Zufall; das Qubit ist danach nur unbedingt sicher |0>."""
        self.random_bits.add(op.bit)
        self._reset(op, randomly, unconditional)

    def _reset(self, op: Op, randomly: bool, unconditional: bool) -> None:
        """R (und das Qubit eines HMR): bedingt ausgeführt bleibt der Wert offen."""
        if unconditional:
            self.random_qubits.discard(op.qs[0])
        else:
            self.random_qubits.add(op.qs[0])

    def _bit_written(self, op: Op, randomly: bool, unconditional: bool) -> None:
        """BIT_*: zufällig ausgeführt -> Zufall; unbedingt gesetzt -> wieder sicher
        (BIT_INVERT behält die Abhängigkeit)."""
        if randomly:
            self.random_bits.add(op.bit)
        elif unconditional and op.name != "BIT_INVERT":
            self.random_bits.discard(op.bit)

    def _x_type(self, op: Op, randomly: bool, unconditional: bool) -> None:
        """X/CX/CCX: das Ziel erbt den Zufall von Ausführung oder Kontrollen."""
        tainted = self.random_qubits
        if randomly or any(control in tainted for control in op.qs[:-1]):
            tainted.add(op.qs[-1])

    def _swapped(self, op: Op, randomly: bool, unconditional: bool) -> None:
        """SWAP: tauscht die Markierungen (zufällig ausgeführt: beide markiert)."""
        a, b = op.qs
        tainted = self.random_qubits
        if randomly:
            tainted.update(op.qs)
        elif (a in tainted) != (b in tainted):
            tainted.symmetric_difference_update(op.qs)

    def _controlled_swap(self, op: Op, randomly: bool, unconditional: bool) -> None:
        """CSWAP: hängt irgendetwas vom Zufall ab, sind beide Tauschpartner markiert."""
        tainted = self.random_qubits
        if randomly or any(q in tainted for q in op.qs):
            tainted.update(op.qs[1:])


# Instruktionsname -> Fortschreibung der Markierungen (Phasengatter ändern nichts)
_TAINT_HANDLERS: dict[str, Callable[[Taint, Op, bool, bool], None]] = {
    "HMR": Taint._measured,
    "R": Taint._reset,
    **dict.fromkeys(BIT_OPS, Taint._bit_written),
    **dict.fromkeys(X_TYPE, Taint._x_type),
    "SWAP": Taint._swapped,
    "CSWAP": Taint._controlled_swap,
}
