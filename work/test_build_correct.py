"""Brute-force correctness test of core.build (rank_parity emitter) on small random
delta tables: symbolic check + native simulation on all addresses."""
import math
import sys

import numpy as np

sys.path.insert(0, "work")
sys.path.insert(0, "sota_mrmeows/sources/dfthcsos_8p5558_complete_with_compiler/dfthcsos_verified_8p555840/compiler")

import kickmix as km  # noqa: E402
from chem_recompile import zero_invalid, plan_zeroed  # noqa: E402
import rank_parity as core  # noqa: E402
from borrowed_prefix import symbolic_check  # noqa: E402


def make_delta(rng, D, J, brot):
    """Random delta table satisfying the redundant sign-bit precondition."""
    delta = np.zeros((D, J), dtype=np.int64)
    for j in range(J):
        x = rng.integers(0, 1 << (brot - 2), size=D)
        top = (x >> (brot - 3)) & 1
        delta[:, j] = (x & ((1 << (brot - 2)) - 1)) | (top << (brot - 2)) | (top << (brot - 1))
    return delta


def native_load(circuit, delta, n, J, brot, seed=99):
    D = len(delta)
    sim = km.Simulator(batch_size=D, seed=seed)
    sim.use_same_registers_as(circuit)
    sel = circuit.register_data["selection"]
    for i in range(n):
        sim.write_across_shots(sel[i], ((np.arange(D) >> i) & 1).astype(bool))
    sim.do(circuit)
    powers = np.int64(1) << np.arange(brot)
    loaded = np.stack(
        [powers @ sim.read_across_shots(circuit.register_data[f"word_{j}"]).astype(np.int64) for j in range(J)],
        axis=1,
    )
    return loaded


def main():
    rng = np.random.default_rng(7)
    fails = 0
    for trial in range(40):
        D = int(rng.integers(3, 21))
        n = (D - 1).bit_length()
        J, brot, lb = 2, 4, 2
        B = 1 << lb
        A = math.ceil(D / B)
        delta = make_delta(rng, D, J, brot)
        ac = core.coefficients(delta, brot, lb)
        ac = zero_invalid(ac, D, lb)
        terms, planning, stats = plan_zeroed(delta, ac, brot, lb, min(32767, (1 << (B - 1)) - 1))
        try:
            circuit, trace, report = core.build(delta, brot, lb, ac, terms)
        except Exception as e:
            print(f"trial {trial}: build failed: {e}")
            fails += 1
            continue
        sym_ok = symbolic_check(trace, delta, brot, circuit.num_qubits)["status"] == "PASS"
        loaded = native_load(circuit, delta, n, J, brot)
        nat_ok = bool(np.array_equal(loaded, delta))
        if not (sym_ok and nat_ok):
            fails += 1
            print(f"trial {trial}: FAIL D={D} sym={sym_ok} native={nat_ok} ccx={report['toffoli_count']}")
    print(f"done, fails={fails}/40")


if __name__ == "__main__":
    main()
