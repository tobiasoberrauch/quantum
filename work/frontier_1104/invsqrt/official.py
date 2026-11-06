#!/usr/bin/env python3
"""Official verifier wrapper. usage: official.py file.{kmx,kmb} [--shots N] [--workers W] [--salt S] [--to-kmb out.kmb]

Unmodified verifier from data/verifiers. --shots < 64 is only a pre-check; only
the default of 64 counts as a claim.
"""
import argparse
import hashlib
import json
import os
import sys
import time

ROOT = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum'
sys.path.insert(0, os.path.join(ROOT, 'data', 'verifiers'))

import kickmix as km  # noqa: E402
from invsqrt import verify_submission_invsqrt as v  # noqa: E402

REF = 2076774.233715282


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('path')
    ap.add_argument('--shots', type=int, default=64)
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--salt', default='notebook-verification')
    ap.add_argument('--to-kmb', default=None)
    a = ap.parse_args()
    fmt = 'kmx' if a.path.endswith('.kmx') else 'kmb'
    c = km.Circuit.from_file(a.path, format=fmt)
    if a.to_kmb:
        c.to_file(a.to_kmb, format='kmb')
        print('wrote', a.to_kmb, hashlib.sha256(open(a.to_kmb, 'rb').read()).hexdigest())
    t0 = time.time()
    spec = v.ProblemSpecInvSqrt.for_n_p(10, shots_per_x=a.shots)
    try:
        r = v.verify(c, spec, salt=a.salt, max_workers=a.workers)
    except (AssertionError, ValueError, RuntimeError) as ex:
        print(json.dumps({'status': 'FAIL', 'error': str(ex)[:300], 'seconds': round(time.time() - t0, 1)}))
        sys.exit(1)
    r['ratio'] = REF / r['score']
    r['seconds'] = round(time.time() - t0, 1)
    r['shots_per_x'] = a.shots
    r['salt'] = a.salt
    print(json.dumps(r))


if __name__ == '__main__':
    main()
