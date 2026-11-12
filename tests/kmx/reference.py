"""Unabhängige Brute-Force-Referenz für unitäre Fenster und Zufallsgatter."""

from fractions import Fraction

import kmx


def brute_force(ops, qubits):
    """Referenz: jedes Gatter ist Permutation x Diagonalphase; Wirkung je Basiszustand
    als (Bits, Phase mod 2)."""
    idx = {q: i for i, q in enumerate(qubits)}
    table = []
    for s in range(1 << len(qubits)):
        v = [(s >> i) & 1 for i in range(len(qubits))]
        ph = Fraction(0)
        for o in ops:
            q = [idx[x] for x in o.qs]
            n = o.name
            if n == "X":
                v[q[0]] ^= 1
            elif n == "CX":
                v[q[1]] ^= v[q[0]]
            elif n == "CCX":
                v[q[2]] ^= v[q[0]] & v[q[1]]
            elif n == "SWAP":
                v[q[0]], v[q[1]] = v[q[1]], v[q[0]]
            elif n == "CSWAP":
                if v[q[0]]:
                    v[q[1]], v[q[2]] = v[q[2]], v[q[1]]
            elif n == "Z":
                ph += v[q[0]]
            elif n == "CZ":
                ph += v[q[0]] & v[q[1]]
            elif n == "CCZ":
                ph += v[q[0]] & v[q[1]] & v[q[2]]
            elif n == "Z_POW":
                ph += v[q[0]] * Fraction(o.args[1])
            elif n == "NEG":
                ph += 1
            else:
                raise AssertionError(n)
        table.append((tuple(v), ph % 2))
    return table


ARITY = {"X": 1, "CX": 2, "CCX": 3, "SWAP": 2, "CSWAP": 3, "Z": 1, "CZ": 2, "CCZ": 3}


HALF = {
    "0.5": "0.25",
    "0.25": "0.125",
    "1.5": "0.75",
    "-0.25": "-0.125",
    "0.125": "0.0625",
    "0.75": "0.375",
}


ANGLES = sorted(HALF) + [
    "-0.125",
    "1.0",
    kmx.phase_op(0, Fraction(1, 1 << 127), None).args[1],
]


def rand_gate(rng, qubits, self_inverse=False):
    roll = rng.random()
    if roll < 0.06:
        return "NEG"
    if roll < 0.22 and not self_inverse:
        return f"Z_POW q{rng.choice(qubits)} {rng.choice(ANGLES)}"
    name = rng.choice(sorted(ARITY))
    return " ".join([name] + [f"q{q}" for q in rng.sample(qubits, ARITY[name])])
