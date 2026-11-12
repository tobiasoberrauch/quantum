"""Eigenschaftstest: check_exact gegen eine unabhängige Brute-Force-Referenz."""

import random

import kmx
from tests.kmx.helpers import (
    P,
    fmt,
)
from tests.kmx.reference import (
    HALF,
    brute_force,
    rand_gate,
)


def mutate(rng, lines, qubits):
    """Zufaellige Bearbeitung; ob sie aequivalent ist, entscheidet allein
    die Brute-Force-Referenz."""
    out = list(lines)
    kind = rng.choice(
        [
            "pair",
            "pair",
            "sym",
            "sym",
            "split",
            "swap3",
            "commute",
            "commute",
            "delete",
            "insert",
            "replace",
            "noop",
        ]
    )
    pos = rng.randrange(len(out) + 1)

    def pick(pred):
        return rng.choice([i for i, g in enumerate(out) if pred(g.split())] or [None])

    if kind == "pair":
        g = rand_gate(rng, qubits, self_inverse=True)
        out[pos:pos] = [g, g]
    elif kind == "sym":
        i = pick(lambda t: t[0] in ("CZ", "CCZ", "SWAP", "CCX", "CSWAP"))
        if i is not None:
            t = out[i].split()
            lo, hi = {"CCX": (1, 3), "CSWAP": (2, 4)}.get(t[0], (1, len(t)))
            mid = t[lo:hi]
            rng.shuffle(mid)
            out[i] = " ".join(t[:lo] + mid + t[hi:])
    elif kind == "split":
        i = pick(lambda t: t[0] == "Z" or (t[0] == "Z_POW" and t[2] in HALF))
        if i is not None:
            t = out[i].split()
            out[i : i + 1] = [
                f"Z_POW {t[1]} {'0.5' if t[0] == 'Z' else HALF[t[2]]}"
            ] * 2
    elif kind == "swap3":
        i = pick(lambda t: t[0] == "SWAP")
        if i is not None:
            _, a, b = out[i].split()
            out[i : i + 1] = [f"CX {a} {b}", f"CX {b} {a}", f"CX {a} {b}"]
    elif kind == "commute":
        ok = [
            i
            for i in range(len(out) - 1)
            if not set(out[i].split()[1:]) & set(out[i + 1].split()[1:])
        ]
        if ok:
            i = rng.choice(ok)
            out[i], out[i + 1] = out[i + 1], out[i]
    elif kind == "delete" and out:
        del out[rng.randrange(len(out))]
    elif kind == "insert":
        out.insert(pos, rand_gate(rng, qubits))
    elif kind == "replace" and out:
        out[rng.randrange(len(out))] = rand_gate(rng, qubits)
    return out


def interleave(rng, main, extra):
    """Mischt `extra` in `main`, beide Reihenfolgen bleiben erhalten."""
    main, extra, out = list(main), list(extra), []
    while main or extra:
        take_extra = extra and (
            not main or rng.random() < len(extra) / (len(extra) + len(main))
        )
        out.append((extra if take_extra else main).pop(0))
    return out


def test_property_check_exact_matches_brute_force_on_random_unitary_windows():
    rng = random.Random(20261111)
    active, verdicts, wide_runs = [0, 1, 2, 3], {"proved": 0, "refuted": 0}, 0
    for trial in range(300):
        base = [rand_gate(rng, active) for _ in range(rng.randint(3, 9))]
        cand = base
        for _ in range(rng.randint(1, 3)):
            cand = mutate(rng, cand, active)
        wide = trial % 2 == 1
        # > 20 Zuschauer-Qubits: nur der Differenzkegel macht das Fenster beweisbar
        if wide:
            pairs = [f"CX q{i} q{i + 1}" for i in range(10, 34, 2)]
            rng.shuffle(pairs)
            spect = pairs + [
                rand_gate(rng, list(range(10, 41))) for _ in range(rng.randint(0, 6))
            ]
            # A (x) S == B (x) S  <=>  A == B (S unitaer)
            ref_qubits, ref_a, ref_b = (
                active,
                P(*base),
                P(*cand),
            )
            wide_runs += 1
        # wenige Zuschauer: Referenz rechnet den GANZEN Schaltkreis inklusive Zuschauer
        else:
            spect = [rand_gate(rng, [10, 11, 12]) for _ in range(rng.randint(0, 5))]
            ref_qubits = active + [10, 11, 12]
        orig_w, cand_w = (
            P(*interleave(rng, base, spect)),
            P(*interleave(rng, cand, spect)),
        )
        if not wide:
            ref_a, ref_b = orig_w, cand_w
        expected = (
            "proved"
            if brute_force(ref_a, ref_qubits) == brute_force(ref_b, ref_qubits)
            else "refuted"
        )

        status, msg = kmx.check_exact(orig_w, cand_w, 0, set())

        assert status == expected, (trial, fmt(orig_w), fmt(cand_w), msg)
        verdicts[status] += 1
    assert (
        wide_runs == 150 and verdicts["proved"] >= 60 and verdicts["refuted"] >= 60
    ), verdicts
