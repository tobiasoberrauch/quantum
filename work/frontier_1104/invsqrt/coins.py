#!/usr/bin/env python3
"""Force each HMR whose wire reads 0 on the full domain to outcome 0 or 1; report cost change.

Also reports the fine-rotation pairwise relations and T-gate parity merges.
usage: coins.py in.kmx census.json out.json
"""
from __future__ import annotations

import json
import multiprocessing as mp
import sys

import numpy as np

import bsim

_ops: list = []


def job(args: tuple) -> dict:
    line, val = args
    xs = bsim.domain()
    s = bsim.run(_ops, xs, seed=321, force={line: val})
    r = bsim.check(s)
    r.update(line=line, val=val)
    return r


def main() -> None:
    global _ops
    ops, _ = bsim.parse_kmx(sys.argv[1])
    _ops = ops
    cen = json.load(open(sys.argv[2]))
    zero = [h for h in cen['hmr'] if h['p1'] == 0 and h['fire'] > 0.01]
    print('zero-wire HMRs with fire>0.01:', len(zero), flush=True)
    jobs = [(h['line'], v) for h in zero for v in (0, 1)]
    with mp.get_context('fork').Pool(5) as pool:
        res = pool.map(job, jobs)
    base = bsim.run(ops, bsim.domain(), seed=321)
    b = bsim.check(base)
    print('base', b)
    rows = []
    for r in sorted(res, key=lambda r: r['tof'] + r['t'] / 4):
        d = r['tof'] + r['t'] / 4 - b['tof'] - b['t'] / 4
        r['dC'] = d
        rows.append(r)
        print(r['line'], ops and [o.raw for o in ops if o.line == r['line']][0], 'force', r['val'],
              'dC %.4f' % d, 'pass' if r['restored'] and not r['dirty_qubits'] and not r['fails'] else
              f"FAIL restored={r['restored']} dirty={r['dirty_qubits']} fails={r['fails']}", 'margin', r['min_margin'], flush=True)
    json.dump(rows, open(sys.argv[3], 'w'), indent=1)


if __name__ == '__main__':
    main()
