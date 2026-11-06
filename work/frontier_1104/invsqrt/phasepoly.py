#!/usr/bin/env python3
"""Phase-polynomial census over Z_POW gates (fine and T) plus exact linear rewrites.

- Groups Z_POW gates by the full-domain value of their control column.
- Exact tests for every CCX/CSWAP: is the AND equal to a linear form of live wires on the
  whole domain, and does target clear to a linear form of other wires on the whole domain.
usage: phasepoly.py in.kmx out.json
"""
from __future__ import annotations

import hashlib
import json
import sys

import numpy as np

import bsim
from census import in_span


def main() -> None:
    ops, _ = bsim.parse_kmx(sys.argv[1])
    xs = bsim.domain()
    groups: dict[str, list] = {}
    rows_lin: list[dict] = []
    first = np.arange(64)  # x <= 4096 are the rare classes
    rng = np.random.default_rng(1)
    rand = rng.choice(len(xs) // 64, 64, replace=False)
    sample = np.unique(np.concatenate([first, rand]))

    def col(a: np.ndarray) -> int:
        return int.from_bytes(a.tobytes(), 'little')

    def hook(i: int, op: bsim.Op, s: bsim.State) -> None:
        if op.kind == 'Z_POW':
            mask = s.base
            if op.cond >= 0:
                b = s.bits.get(op.cond, s.zero)
                mask = b if mask is None else mask & b
            m = s.q[op.q[0]] if mask is None else s.q[op.q[0]] & mask
            h = hashlib.sha1(m.tobytes()).hexdigest()[:16]
            groups.setdefault(h, []).append(dict(line=op.line, wire=op.q[0], angle=float(op.angle),
                                                 cls=bsim.angle_class(op.angle), p=bsim.popcount(m) / s.n,
                                                 cond=op.cond, depth=len(s.stack)))
            return
        if op.kind not in ('CCX', 'CSWAP') or s.base is not None or op.cond >= 0:
            return
        a = op.q
        if op.kind == 'CCX':
            andv = s.q[a[0]] & s.q[a[1]]
            tgt = s.q[a[2]]
            excl = {a[2]}
        else:
            andv = s.q[a[0]] & (s.q[a[1]] ^ s.q[a[2]])
            tgt = s.q[a[2]]
            excl = {a[1], a[2]}
        sub = s.q[:, sample]
        cols = [col(sub[j]) for j in range(sub.shape[0])]
        allset = col(np.full(len(sample), bsim.ONES, dtype=np.uint64))
        rec = dict(line=op.line, raw=op.raw)
        ok, sol = in_span(cols + [allset], col(andv[sample]), allset)
        if ok:
            v = np.zeros(s.w, dtype=np.uint64)
            for j in sol:
                v ^= s.q[j] if j < s.q.shape[0] else bsim.ONES
            if np.array_equal(v, andv):
                rec['and_linear'] = sol
        tv = tgt ^ andv
        ids = [j for j in range(sub.shape[0]) if j not in excl]
        ok, sol = in_span([cols[j] for j in ids] + [allset], col(tv[sample]), allset)
        if ok:
            v = np.zeros(s.w, dtype=np.uint64)
            for j in sol:
                v ^= s.q[ids[j]] if j < len(ids) else bsim.ONES
            if np.array_equal(v, tv):
                rec['clear_linear'] = [ids[j] if j < len(ids) else -1 for j in sol]
        if len(rec) > 2:
            rows_lin.append(rec)

    s = bsim.run(ops, xs, seed=77, hook=hook)
    print(bsim.check(s))
    dup = [g for g in groups.values() if len(g) > 1]
    print('Z_POW groups', len(groups), 'with duplicates', len(dup))
    for g in dup:
        print(g)
    print('fine rotation p:', [round(v['p'], 4) for g in groups.values() for v in g if v['cls'] == 'rotation'])
    print('t gates:')
    for g in groups.values():
        for v in g:
            if v['cls'] == 't':
                print(v)
    print('exact linear', len(rows_lin))
    for r in rows_lin:
        print(r)
    json.dump(dict(groups=groups, lin=rows_lin), open(sys.argv[2], 'w'))


if __name__ == '__main__':
    main()
