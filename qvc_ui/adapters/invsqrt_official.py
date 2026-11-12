#!/usr/bin/env python3
"""Trusted invsqrt verifier wrapper (operator-supplied, NOT LLM-generated).

Runs the UNMODIFIED official verifier in data/verifiers/invsqrt and prints exactly
one contract JSON object to stdout:
    {"source":"official_verifier","passed":bool,"cost":float|null,"shots":int|null,
     "salt":str, ...}
`cost` is the official `score` (= Q*C). qvc_discovery turns cost into
ratio = REFERENCE_COSTS['invsqrt'] / cost.

Env:
    QVC_SHOTS   shots_per_x (default 64). Only 64 is an official claim; a smaller
                value is a labelled PRE-CHECK (covers every x fewer times, so rare
                salt-dependent phase errors and the rotation epsilon may differ).
    QVC_WORKERS verifier process-pool size (default 2). OMP threads are forced to 1
                by qvc_discovery.verify_candidate.

Always exits 0 on a completed evaluation (PASS or FAIL); non-zero only on usage error.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = "/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum"
sys.path.insert(0, os.path.join(ROOT, "data", "verifiers"))
REF = 2076774.233715282


def _emit(payload: dict) -> None:
    print(json.dumps(payload))


def main() -> int:
    if len(sys.argv) < 3:
        _emit({"source": "official_verifier", "passed": False, "cost": None, "shots": None,
               "salt": "", "error": "usage: invsqrt_official.py <candidate.kmb> <salt>"})
        return 2
    candidate, salt = sys.argv[1], sys.argv[2]
    try:
        shots = int(os.environ.get("QVC_SHOTS", "64"))
        workers = int(os.environ.get("QVC_WORKERS", "2"))
    except ValueError:
        shots, workers = 64, 2
    precheck = shots != 64
    try:
        import kickmix as km
        from invsqrt import verify_submission_invsqrt as v
        circ = km.Circuit.from_file(candidate, format="kmb")
        spec = v.ProblemSpecInvSqrt.for_n_p(10, shots_per_x=shots)
        r = v.verify(circ, spec, salt=salt, max_workers=workers)
        _emit({"source": "official_verifier", "passed": True, "cost": r["score"],
               "shots": r["verified_shots"], "salt": salt, "num_qubits": r["num_qubits"],
               "ratio": REF / r["score"], "precheck": precheck})
    except Exception as exc:  # completed evaluation that FAILED -> report, do not crash
        _emit({"source": "official_verifier", "passed": False, "cost": None, "shots": None,
               "salt": salt, "precheck": precheck,
               "error": f"{type(exc).__name__}: {exc}"[:500]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
