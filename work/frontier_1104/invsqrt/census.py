#!/usr/bin/env python3
"""Full-domain census of every Toffoli-like gate and HMR in a kmx circuit.

For each gate records: firing rate, control statistics, redundancy flags, membership
of the AND value in the GF(2) span of live wires, and whether the target clears to a
span of other wires (a measurement-based uncompute candidate). Output is JSON.
usage: census.py in.kmx out.json [seed]
"""
from __future__ import annotations

import json
import sys
import time

import numpy as np

import bsim

SAMPLE_WORDS = 96  # 6144 sampled shots for GF(2) span tests


def to_ints(mat: np.ndarray, mask: np.ndarray | None) -> list[int]:
    """Packed columns to python ints; restricted to shots where mask is set by clearing others."""
    out = []
    for row in mat:
        r = row if mask is None else row & mask
        out.append(int.from_bytes(r.tobytes(), 'little'))
    return out


def in_span(columns: list[int], target: int, nbits_mask: int) -> tuple[bool, list[int]]:
    """Gaussian elimination over GF(2) on python ints. Returns (in span, column indices)."""
    pivots: dict[int, tuple[int, int]] = {}
    for idx, v in enumerate(columns):
        tag = 1 << idx
        while v:
            h = v.bit_length() - 1
            if h in pivots:
                pv, pt = pivots[h]
                v ^= pv
                tag ^= pt
            else:
                pivots[h] = (v, tag)
                break
    v = target
    tag = 0
    while v:
        h = v.bit_length() - 1
        if h not in pivots:
            return False, []
        pv, pt = pivots[h]
        v ^= pv
        tag ^= pt
    return True, [i for i in range(len(columns)) if (tag >> i) & 1]


def main() -> None:
    path, out = sys.argv[1], sys.argv[2]
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 11
    ops, _ = bsim.parse_kmx(path)
    xs = bsim.domain()
    rng = np.random.default_rng(99)
    sample_idx = rng.choice(len(xs) // 64, SAMPLE_WORDS, replace=False)
    sample_idx.sort()
    rows: list[dict] = []
    hmr_rows: list[dict] = []
    t0 = time.time()

    def live_sample(s: bsim.State, mask: np.ndarray | None) -> tuple[list[int], int]:
        sub = s.q[:, sample_idx]
        m = None if mask is None else mask[sample_idx]
        cols = to_ints(sub, m)
        allset = int.from_bytes((np.full(SAMPLE_WORDS, bsim.ONES, dtype=np.uint64) if m is None else m).tobytes(),
                                'little')
        return cols, allset

    def hook(i: int, op: bsim.Op, s: bsim.State) -> None:
        k = op.kind
        if k not in ('CCX', 'CCZ', 'CSWAP', 'HMR'):
            return
        mask = s.base
        if op.cond >= 0:
            b = s.bits.get(op.cond, s.zero)
            mask = b if mask is None else mask & b
        nfire = s.n if mask is None else bsim.popcount(mask)
        if k == 'HMR':
            q1 = s.q[op.q[0]] if mask is None else s.q[op.q[0]] & mask
            hmr_rows.append(dict(i=i, line=op.line, q=op.q[0], bit=op.bit, cond=op.cond, in_block=len(s.stack),
                                 fire=nfire / s.n, p1=bsim.popcount(q1) / s.n))
            return
        a = op.q
        if k == 'CSWAP':
            c1, c2, tgt = s.q[a[0]], s.q[a[1]] ^ s.q[a[2]], s.q[a[2]]
        elif k == 'CCX':
            c1, c2, tgt = s.q[a[0]], s.q[a[1]], s.q[a[2]]
        else:
            c1, c2, tgt = s.q[a[0]], s.q[a[1]], s.q[a[2]]
        andv = c1 & c2
        if k == 'CCZ':
            andv = andv & tgt
        if mask is not None:
            c1m, c2m, am = c1 & mask, c2 & mask, andv & mask
        else:
            c1m, c2m, am = c1, c2, andv
        rec = dict(i=i, line=op.line, kind=k, q=list(a), cond=op.cond, in_block=len(s.stack), fire=nfire / s.n,
                   p_c1=bsim.popcount(c1m) / max(nfire, 1), p_c2=bsim.popcount(c2m) / max(nfire, 1),
                   p_and=bsim.popcount(am) / max(nfire, 1), p_t=bsim.popcount(tgt if mask is None else tgt & mask) / max(nfire, 1))
        rec['never'] = bool(not am.any())
        if k != 'CCZ':
            rec['eq_c1'] = bool(np.array_equal(am, c1m))
            rec['eq_c2'] = bool(np.array_equal(am, c2m))
            cols, allset = live_sample(s, mask)
            names = [f'q{j}' for j in range(s.q.shape[0])]
            # Column set: all qubits except controls can still be used, plus constant.
            target = int.from_bytes((am[sample_idx]).tobytes(), 'little')
            ok, sol = in_span(cols + [allset], target, allset)
            rec['and_linear'] = [names[j] if j < len(names) else 'ONE' for j in sol] if ok else None
            # Clear test: t ^ (and) in span of the other wires. Skips the target itself.
            tgtv = (tgt ^ andv) if mask is None else (tgt ^ andv) & mask
            tgt_int = int.from_bytes(tgtv[sample_idx].tobytes(), 'little')
            excl = {a[2]} if k == 'CCX' else {a[1], a[2]}
            cols2 = [c for j, c in enumerate(cols) if j not in excl]
            nm2 = [names[j] for j in range(len(cols)) if j not in excl]
            ok2, sol2 = in_span(cols2 + [allset], tgt_int, allset)
            rec['clear_linear'] = [nm2[j] if j < len(nm2) else 'ONE' for j in sol2] if ok2 else None
        rows.append(rec)

    s = bsim.run(ops, xs, seed=seed, hook=hook)
    res = bsim.check(s)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(dict(check=res, toffoli=rows, hmr=hmr_rows), f)
    print(res, round(time.time() - t0, 1), 's')
    n = len(rows)
    print('toffoli-like', n, 'conditional', sum(1 for r in rows if r['fire'] < 1))
    print('never', [r['line'] for r in rows if r['never']])
    print('eq', [r['line'] for r in rows if r.get('eq_c1') or r.get('eq_c2')])
    print('and_linear', [(r['line'], r['and_linear']) for r in rows if r.get('and_linear') is not None][:60])
    print('clear_linear', [(r['line'], r['clear_linear']) for r in rows if r.get('clear_linear') is not None][:80])
    zero = [r for r in hmr_rows if r['p1'] == 0]
    print('hmr total', len(hmr_rows), 'q always 0', [(r['line'], r['q'], r['bit']) for r in zero])


if __name__ == '__main__':
    main()
