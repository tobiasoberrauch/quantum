#!/usr/bin/env python3
"""Independent single-run check of an invsqrt circuit with the unmodified official verifier.

usage: python -I -B fresh_verify.py file.kmb SALT [max_x shots_per_x]
Default arguments give the official spec. max_x/shots_per_x are a stress mode and never a claim.
Prints one JSON line. Exit code 1 on verifier failure.
"""
import hashlib
import json
import sys
import time

REPO = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum'
REF_COST = 2076774.233715282
WORKERS = 6

sys.path.insert(0, REPO + '/data/verifiers')
import kickmix as km  # noqa: E402
from invsqrt import verify_submission_invsqrt as official  # noqa: E402
import dataclasses  # noqa: E402


def main() -> None:
    path, salt = sys.argv[1], sys.argv[2]
    with open(path, 'rb') as f:
        raw = f.read()
    circuit = km.Circuit.from_file(path, format='kmb')
    spec = official.ProblemSpecInvSqrt.for_n_p(10)
    stress = len(sys.argv) > 3
    if stress:
        spec = dataclasses.replace(spec, max_x=int(sys.argv[3]), shots_per_x=int(sys.argv[4]))
    out = {'file': path, 'file_sha256': hashlib.sha256(raw).hexdigest(), 'salt': salt,
           'stress': stress, 'max_x': spec.max_x, 'shots_per_x': spec.shots_per_x,
           'verifier': official.__file__, 'kickmix': km.__file__}
    t0 = time.time()
    code = 0
    try:
        res = official.verify(circuit, spec, salt=salt, max_workers=WORKERS)
        res['ratio'] = REF_COST / res['score']
        out.update(res)
    except (AssertionError, ValueError, RuntimeError) as ex:
        out.update(status='FAIL', error=str(ex)[:400])
        code = 1
    out['seconds'] = round(time.time() - t0, 1)
    print(json.dumps(out), flush=True)
    sys.exit(code)


if __name__ == '__main__':
    main()
