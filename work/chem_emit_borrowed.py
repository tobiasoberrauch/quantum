"""Borrowed-cache HMR emitter: rank_parity plans + Atakan-style word[7] borrowing.

Layout (D=1220, J=5, brot=8, lb=4): 11 selection + 40 word + 69 high-cache
+ 6 low-cache-fresh (5 low masks borrow word[7]) = 126 qubits <= 128.
Cache built with init_and (1 CCX each), uncomputed with del_and (HMR + CZ-if-b:
free in the Toffoli metric). Products: 1 CCX each + CX chains.

Usage: .venv/bin/python work/chem_emit_borrowed.py [--J 5] [--lb 4] [--k K]
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path("/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum")
sys.path.insert(0, str(REPO / "work"))
sys.path.insert(0, str(REPO / "sota_mrmeows/sources/dfthcsos_8p5558_complete_with_compiler/dfthcsos_verified_8p555840/compiler"))

import kickmix as km  # noqa: E402
from chem_recompile import load_words, zero_invalid, plan_zeroed  # noqa: E402
import rank_parity as core  # noqa: E402
from borrowed_prefix import symbolic_check  # noqa: E402


def emit_borrowed(ac, terms, J, brot, lb, D):
    """Emit one batch circuit with borrowed low-cache layout. Returns (circuit, trace, report)."""
    A, B, O = ac.shape
    n = (D - 1).bit_length()
    builder = km.CircuitBuilder()
    selection = builder.create_quantum_register(n, "selection")
    words = [builder.create_quantum_register(brot, f"word_{j}") for j in range(J)]
    trace = []

    def gate(name, *qs):
        trace.append((name, *[q.id if hasattr(q, "id") else q for q in qs]))
        getattr(builder, name.lower())(*qs)

    # NOTE: word[brot-1] (redundant sign bit) is NEVER written directly here:
    # those qubits are borrowed as low-cache workspace. The final CX below
    # restores word[brot-1] = word[brot-2] (canonical gauge makes them equal).

    high_masks = [h for h in range(1, A) if h.bit_count() >= 2]
    low_masks = [l for l in range(1, B) if l.bit_count() >= 2]
    high_q = builder.alloc_qubits(len(high_masks))
    borrow = min(len(low_masks), J)
    low_q = [w[brot - 1] for w in words[:borrow]] + list(builder.alloc_qubits(len(low_masks) - borrow))

    # Cache keys: high monomial h lives at key h << lb (disjoint from low keys < B),
    # mirroring Atakan's emitter. Single-bit keys map to selection qubits.
    cache = {}
    for i, s in enumerate(selection):
        cache[1 << i] = s
        if i >= lb:
            cache[(1 << (i - lb)) << lb] = s
    for m, q in zip(high_masks, high_q):
        key = m << lb
        top = 1 << (key.bit_length() - 1)
        builder.init_and(cache[key ^ top], cache[top], q)
        cache[key] = q
    for m, q in zip(low_masks, low_q):
        top = 1 << (m.bit_length() - 1)
        builder.init_and(cache[m ^ top], cache[top], q)
        cache[m] = q

    basis = [cache[h << lb] for h in range(1, A)] + [cache[l] for l in range(1, B)]
    H = A - 1

    def target_bits(direction):
        out = []
        for d in core.set_bits(direction):
            j, bit = divmod(d, brot - 1)
            out.append(words[j][bit])
        return out

    def linear_output(control, direction):
        for q in target_bits(direction):
            gate("CX", control, q)

    def product(a, b, direction):
        if not a or not b or not direction:
            return
        if a == b:
            for i in core.set_bits(a):
                linear_output(basis[i], direction)
            return
        p = (a & -a).bit_length() - 1
        first = list(core.set_bits(a ^ (1 << p)))
        for i in first:
            gate("CX", basis[i], basis[p])
        if b >> p & 1:
            b ^= a ^ (1 << p)
        choices = b & ~(1 << p)
        assert choices, "product: empty choice set"
        q = (choices & -choices).bit_length() - 1
        second = list(core.set_bits(b ^ (1 << q)))
        for i in second:
            gate("CX", basis[i], basis[q])
        pivot, *others = target_bits(direction)
        for out in others:
            gate("CX", pivot, out)
        gate("CCX", basis[p], basis[q], pivot)
        for out in others:
            gate("CX", pivot, out)
        for i in reversed(second):
            gate("CX", basis[i], basis[q])
        for i in reversed(first):
            gate("CX", basis[i], basis[p])

    high_only = [sum(int(ac[h, 0, j]) << j for j in range(O)) for h in range(A)]
    low_only = [sum(int(ac[0, l, j]) << j for j in range(O)) for l in range(B)]
    low_only[0] = 0

    def correction(destination, left, right, direction):
        for a in core.set_bits(left):
            for b in core.set_bits(right):
                index = (a + 1) | (b + 1)
                if index < len(destination):
                    destination[index] ^= direction

    for term in terms:
        pairs = term["factors"]
        direction = term["target_direction"]
        for i in range(0, len(pairs), 2):
            h1, l1 = pairs[i]
            if i + 1 == len(pairs):
                product(h1, l1 << H, direction)
            else:
                h2, l2 = pairs[i + 1]
                product(h1 ^ (l2 << H), h2 ^ (l1 << H), direction)
                correction(high_only, h1, h2, direction)
                correction(low_only, l1, l2, direction)

    for q in target_bits(high_only[0]):
        gate("X", q)
    for mask in range(1, A):
        linear_output(cache[mask << lb], high_only[mask])
    for mask in range(1, B):
        linear_output(cache[mask], low_only[mask])

    # free uncomputation (HMR + CZ-if-b)
    for m, q in reversed(list(zip(low_masks, low_q))):
        top = 1 << (m.bit_length() - 1)
        builder.del_and(cache[m ^ top], cache[top], q)
    for m, q in reversed(list(zip(high_masks, high_q))):
        key = m << lb
        top = 1 << (key.bit_length() - 1)
        builder.del_and(cache[key ^ top], cache[top], q)
    for w in words:
        gate("CX", w[brot - 2], w[brot - 1])

    circuit = builder.finish_circuit()
    native_ccx = int(circuit.operation_statistics().num_toffoli_like)
    expected_ccx = sum(t[0] == "CCX" for t in trace) + len(high_masks) + len(low_masks)  # + init_and cache build
    assert native_ccx == expected_ccx, (native_ccx, expected_ccx)
    return circuit, trace, {"num_qubits": int(circuit.num_qubits), "toffoli_count": native_ccx,
                            "gates": len(trace)}


def native_load(circuit, delta, n, J, brot, seed=99):
    D = len(delta)
    sim = km.Simulator(batch_size=D, seed=seed)
    sim.use_same_registers_as(circuit)
    sel = circuit.register_data["selection"]
    for i in range(n):
        sim.write_across_shots(sel[i], ((np.arange(D) >> i) & 1).astype(bool))
    sim.do(circuit)
    powers = np.int64(1) << np.arange(brot)
    return np.stack([powers @ sim.read_across_shots(circuit.register_data[f"word_{j}"]).astype(np.int64)
                     for j in range(J)], axis=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--J", type=int, default=5)
    ap.add_argument("--lb", type=int, default=4)
    ap.add_argument("--k", type=int, default=None, help="single batch (default: all)")
    ap.add_argument("--max-kernels", type=int, default=32767)
    args = ap.parse_args()

    words, brot, edges = load_words()
    D = len(words)
    n = (D - 1).bit_length()
    J, lb = args.J, args.lb
    K = math.ceil(words.shape[1] // J)
    ks = [args.k] if args.k is not None else range(K)
    total_ccx = 0
    for k in ks:
        delta = core.delta_batch(words, J, k)
        ac = core.coefficients(delta, brot, lb)
        ac = zero_invalid(ac, D, lb)
        terms, planning, stats = plan_zeroed(delta, ac, brot, lb, args.max_kernels)
        circuit, trace, report = emit_borrowed(ac, terms, J, brot, lb, D)
        loaded = native_load(circuit, delta, n, J, brot)
        ok = bool(np.array_equal(loaded, delta))
        total_ccx += report["toffoli_count"]
        print(f"k={k:<2} Q={report['num_qubits']} CCX={report['toffoli_count']:<4} "
              f"products={len(terms):<3} native={'OK' if ok else 'MISMATCH'}")
        if not ok:
            diff = (loaded ^ delta).any(axis=1)
            print("   mismatched addresses:", int(diff.sum()), np.flatnonzero(diff)[:8])
            sys.exit(1)
    if args.k is None:
        print(f"TOTAL CCX={total_ccx} (baseline 4168) -> angle_T={2*total_ccx} (baseline 8336)")
        A = math.ceil(D / (1 << lb))
        Q_total = 86 + J * brot + max(304, n + (A - 1) + ((1 << lb) - 1) - min(J, (1 << lb) - 1))
        T_total = 7930 + 2 * total_ccx
        print(f"Q_total~{Q_total}, T_total={T_total}, T*Q={T_total*Q_total:,} (baseline 6,994,380)")


if __name__ == "__main__":
    main()
