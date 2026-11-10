#!/usr/bin/env python3
"""FAST invsqrt pre-check (NOT an official claim).

Simulates a stratified subset of x (all small x, every 2^k boundary, evenly-spaced
and random large x) through the unmodified kickmix simulator, reusing the official
verifier's exact register validation, reference values and phase tolerance. Emits the
same contract JSON as invsqrt_official.py but with precheck=true and an ESTIMATED
cost (static gate counts), so broken mutations are rejected in seconds before the
~10-minute official 64-shots/x run.

Why a pre-check exists: the official verifier requires shots_per_x*max_x to be a
multiple of batch_size=256, and max_x=3133452=4*(odd), so shots_per_x must be a
multiple of 64 -> 64 is the floor. A cheaper *full* run is impossible; a subset is.

argv: <candidate.kmb> <salt>
env:  QVC_PRECHECK_N  stratified sample count (default 512)
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys

import numpy as np

ROOT = "/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum"
sys.path.insert(0, os.path.join(ROOT, "data", "verifiers"))
REF = 2076774.233715282
BATCH = 256


def emit(payload: dict) -> None:
    print(json.dumps(payload))


def fail(salt: str, msg: str, shots=None) -> None:
    emit({"source": "official_verifier", "passed": False, "cost": None, "shots": shots,
          "salt": salt, "precheck": True, "error": msg[:500]})


def stratified(max_x: int, n: int, seed: int = 0) -> np.ndarray:
    s: set[int] = set()
    for x in range(1, min(256, max_x) + 1):
        s.add(x)
    k = 1
    while (1 << k) <= max_x:
        for d in (-1, 0, 1):
            v = (1 << k) + d
            if 1 <= v <= max_x:
                s.add(v)
        k += 1
    rng = np.random.default_rng(seed)
    for x in np.linspace(1, max_x, max(n, 16)).astype(np.int64):
        s.add(int(x))
    for x in rng.integers(1, max_x + 1, size=max(n, 16)):
        s.add(int(x))
    return np.array(sorted(s), dtype=np.uint64)


def main() -> int:
    if len(sys.argv) < 3:
        fail("", "usage: invsqrt_precheck.py <candidate.kmb> <salt>")
        return 2
    candidate, salt = sys.argv[1], sys.argv[2]
    try:
        n = int(os.environ.get("QVC_PRECHECK_N", "512"))
    except ValueError:
        n = 512
    try:
        import kickmix as km
        from invsqrt import verify_submission_invsqrt as v
        circ = km.Circuit.from_file(candidate, format="kmb")
        spec = v.ProblemSpecInvSqrt.for_n_p(10)
        x_reg, scratch = v.validate_registers(circ, spec)

        buf = io.BytesIO(); circ.to_file(buf, format="kmb")
        ch = hashlib.sha256(buf.getvalue()).hexdigest()
        seed = int(hashlib.sha256(f"{ch}{salt}".encode()).hexdigest(), 16) if salt else int(ch, 16)

        xs = stratified(spec.max_x, n)
        pad = (-len(xs)) % BATCH
        if pad:
            xs = np.concatenate([xs, xs[:pad]])
        target, tol = v.reference_values(spec, xs)

        sim = km.Simulator(batch_size=BATCH, debug_print=False, counting_operations=True, seed=seed)
        worst = (0.0, -1)
        for start in range(0, len(xs), BATCH):
            cxs = xs[start:start + BATCH]
            sim.clear_for_shot()
            sim.write_across_shots(x_reg, v.to_bits(cxs, spec.width))
            sim.do(circ)
            if not np.array_equal(v.from_bits(sim.read_across_shots(x_reg)), cxs):
                fail(salt, "x not restored on pre-check subset", len(xs)); return 0
            if len(scratch):
                dirty = sim.read_across_shots(scratch).any(axis=1)
                if dirty.any():
                    fail(salt, f"scratch qubit {scratch[int(np.argmax(dirty))]} not |0>", len(xs)); return 0
            theta = np.array([v.half_turns_to_units(sim.read_shot_phase(i)) for i in range(BATCH)], dtype=np.uint64)
            allowed = tol[start:start + BATCH]; tgt = target[start:start + BATCH]
            err = (theta - tgt).view(np.int64)
            used = np.abs(err).view(np.uint64)
            bad = np.flatnonzero(used > allowed)
            if len(bad):
                i = bad[0]
                fail(salt, f"x={cxs[i]}: phase error {err[i]/2**64:.3e} > tol {allowed[i]/2**64:.3e}", len(xs)); return 0
            ratio = np.divide(used, allowed, out=np.zeros(BATCH), where=allowed > 0)
            worst = max(worst, (float(ratio.max()), -int(cxs[ratio == ratio.max()].min())))

        stats = circ.operation_statistics()
        est_cost = circ.num_qubits * (stats.num_toffoli_like + stats.num_t_like / 4)
        emit({"source": "official_verifier", "passed": True, "cost": est_cost, "shots": len(xs),
              "salt": salt, "precheck": True, "cost_is_estimate": True,
              "num_qubits": circ.num_qubits, "toffoli_like_static": int(stats.num_toffoli_like),
              "worst_error_over_tolerance": worst[0], "estimated_ratio": REF / est_cost})
    except Exception as exc:
        fail(salt, f"{type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
