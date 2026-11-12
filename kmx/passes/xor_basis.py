"""XOR-Basis über Lane-Vektoren (lineare Algebra über GF(2)) und der CX-Ersatz
einer XOR-Summe.
"""

from __future__ import annotations

from collections.abc import Hashable, Sequence

from kmx.ops import Op, qubit_token

# Etikett des konstanten Erzeugers (darf nicht mit einer Qubit-Nummer kollidieren)
ONE = "1"
# Etikett eines Basis-Erzeugers: Qubit-Nummer, ONE oder ein eigenes Tupel des Aufrufers
BasisLabel = Hashable
# Term einer XOR-Summe: Qubit-Nummer oder ONE
XorTerm = int | str


class XorBasis:
    """GF(2)-Basis über Lane-Vektoren mit Buchführung, welche
    Erzeuger kombiniert wurden.

    `piv` bildet das höchste gesetzte Bit auf (reduzierter Vektor, Kombinationsmaske)
    ab; Bit k der Maske steht für den k-ten hinzugefügten Erzeuger (`labels[k]`)."""

    def __init__(self) -> None:
        self.labels: list[BasisLabel] = []
        self.piv: dict[int, tuple[int, int]] = {}

    def copy(self) -> XorBasis:
        """Unabhängige Kopie (die Einträge selbst sind unveränderlich)."""
        nb = XorBasis()
        nb.labels, nb.piv = list(self.labels), dict(self.piv)
        return nb

    def add(self, label: BasisLabel, vec: int) -> None:
        """Nimmt den Erzeuger `label` mit Lane-Vektor `vec` auf (linear abhängige
        zählen nur als Etikett)."""
        combo = 1 << len(self.labels)
        self.labels.append(label)
        piv = self.piv
        while vec:
            p = vec.bit_length() - 1
            e = piv.get(p)
            if e is None:
                piv[p] = (vec, combo)
                return
            vec ^= e[0]
            combo ^= e[1]

    def solve(self, v: int) -> list[BasisLabel] | None:
        """Etiketten der Erzeuger, deren XOR genau `v` ergibt, oder None, wenn `v`
        nicht im Spann liegt."""
        combo, piv = 0, self.piv
        while v:
            e = piv.get(v.bit_length() - 1)
            if e is None:
                return None
            v ^= e[0]
            combo ^= e[1]
        return [lab for i, lab in enumerate(self.labels) if (combo >> i) & 1]


def lin_ops(terms: Sequence[XorTerm], target: int, cond: int | None) -> list[Op]:
    """Erzeugt target ^= XOR(terms); ONE steht für die Konstante."""
    target_token = qubit_token(target)
    return [
        Op("X", (target_token,), cond)
        if t == ONE
        else Op("CX", (qubit_token(t), target_token), cond)
        for t in terms
    ]
