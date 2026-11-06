#!/usr/bin/env python3
"""Build the public reference decoder, write it to .kmb, and run the official
verifier with a small shot count to confirm correctness and measure its actual
score (R*Q^2*T). Anchors the 'gap to close' number for the feasibility report.

Read-only over sources; writes under work/dqi_builder_recon/. Guards params.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys


def _guard(p, label):
    if p is None or not isinstance(p, str) or not p.strip():
        raise SystemExit(f"ERROR: {label} must be a non-empty string")
    return p.strip()


def main(m, n, degree, shots, out_kmb, out_json):
    m = int(m) if m not in (None, "") else 4095
    n = int(n) if n not in (None, "") else 70
    degree = int(degree) if degree not in (None, "") else 12
    shots = int(shots) if shots not in (None, "") else 256
    out_kmb = _guard(out_kmb, "out_kmb")
    out_json = _guard(out_json, "out_json")
    if m <= 0 or n <= 0 or degree <= 0 or shots <= 0:
        raise SystemExit("ERROR: m/n/degree/shots must be positive")

    vdir = os.path.abspath("data/verifiers/dqi")
    sys.path.insert(0, vdir)
    import dqi_reference_circuit as ref  # noqa: E402

    print(f"[refv] building reference m={m} n={n} degree={degree} ...", file=sys.stderr)
    circuit = ref.build_reference_circuit(m, n, degree)
    circuit.to_file(out_kmb, format="kmb")
    print(f"[refv] wrote {out_kmb} ({os.path.getsize(out_kmb)/1e6:.1f} MB)", file=sys.stderr)

    # run official verifier (few shots, single worker for safety)
    cmd = [sys.executable, os.path.join(vdir, "verify_submission_dqi.py"),
           out_kmb, "--num-shots", str(shots), "--batch-size", "256", "--max-workers", "1"]
    print("[refv] running verifier: " + " ".join(cmd), file=sys.stderr)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    summary = None
    try:
        summary = json.loads(proc.stdout)
    except Exception as e:
        print(f"[refv] verifier output parse failed: {e}\nSTDOUT:{proc.stdout[:2000]}\nSTDERR:{proc.stderr[:2000]}", file=sys.stderr)

    res = dict(m=m, n=n, degree=degree, shots=shots,
               num_qubits=circuit.num_qubits,
               static_toffoli_like=circuit.operation_statistics().num_toffoli_like,
               verifier=summary)
    d = os.path.dirname(os.path.abspath(out_json)); os.makedirs(d, exist_ok=True)
    with open(out_json, "w") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None,
         sys.argv[2] if len(sys.argv) > 2 else None,
         sys.argv[3] if len(sys.argv) > 3 else None,
         sys.argv[4] if len(sys.argv) > 4 else "256",
         sys.argv[5] if len(sys.argv) > 5 else "work/dqi_builder_recon/reference.kmb",
         sys.argv[6] if len(sys.argv) > 6 else "work/dqi_builder_recon/reference_verify.json")
