#!/usr/bin/env python3
"""Build the public reference DQI decoder (dqi_reference_circuit.py) and report
its T (mean toffoli-like) and Q, so we can measure the gap from 'from scratch'
to the current best (fc3ba816: Q=891, mean T=396,921.5).

Read-only; writes a JSON under work/dqi_builder_recon/. Guards all params.
"""
from __future__ import annotations
import json
import os
import sys
import time


def _guard_out(out_path):
    if out_path is None or not isinstance(out_path, str) or not out_path.strip():
        raise SystemExit("ERROR: out_path must be a non-empty string")
    return out_path.strip()


def main(m, n, degree, out_path):
    m = int(m) if m not in (None, "") else 4095
    n = int(n) if n not in (None, "") else 70
    degree = int(degree) if degree not in (None, "") else 12
    if m <= 0 or n <= 0 or degree <= 0:
        raise SystemExit("ERROR: m/n/degree must be positive")
    out_path = _guard_out(out_path)

    # import the reference builder from the verifiers dir
    vdir = "data/verifiers/dqi"
    sys.path.insert(0, os.path.abspath(vdir))
    import dqi_reference_circuit as ref  # noqa: E402

    t0 = time.time()
    print(f"[ref] building m={m} n={n} degree={degree} ...", file=sys.stderr)
    circuit = ref.build_reference_circuit(m, n, degree)
    build_s = time.time() - t0

    stats = circuit.operation_statistics()
    res = {
        "m": m, "n": n, "degree": degree,
        "num_qubits": circuit.num_qubits,
        "num_bits": circuit.num_bits,
        "num_ops": len(circuit),
        "static_toffoli_like": stats.num_toffoli_like,
        "reaction_depth": circuit.reaction_depth(),
        "build_seconds": round(build_s, 1),
        "op_stats": dict(stats),
    }
    d = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(d, exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None,
         sys.argv[2] if len(sys.argv) > 2 else None,
         sys.argv[3] if len(sys.argv) > 3 else None,
         sys.argv[4] if len(sys.argv) > 4 else "work/dqi_builder_recon/reference_build.json")
