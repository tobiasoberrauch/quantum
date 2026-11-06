#!/usr/bin/env python3
"""Census of AND recomputation modulo live linear forms.

For each Toffoli-like gate g with AND value v_g (for CCZ: each pair), find the latest earlier
gate e with v_e such that v_g ^ v_e is a linear form of wires live at g. If a wire stays free
from e to g, a copy of v_e can be parked there and g no longer needs a Toffoli.

usage: reuse.py in.kmx out.json
"""
from __future__ import annotations

import json
import sys

import numpy as np

import bsim

NQ = 62


def main() -> None:
    ops, _ = bsim.parse_kmx(sys.argv[1])
    rng = np.random.default_rng(11)
    xs = np.concatenate([np.tile(np.arange(1, 4097, dtype=np.uint64), 1),
                         rng.integers(1, bsim.MAX_X + 1, 12288, dtype=np.uint64)])
    xs = xs[:len(xs) // 64 * 64]
    s = bsim.State(xs, 21)
    history: list[tuple] = []  # (i, line, tag, int value)
    rows: list[dict] = []
    occupied = np.zeros((NQ, len(ops)), dtype=bool)  # wire nonzero or written at op i
    to_int = lambda a: int.from_bytes(a.tobytes(), 'little')
    for i, op in enumerate(ops):
        mask = s.base
        if op.cond >= 0:
            b = s.bits.get(op.cond, s.zero)
            mask = b if mask is None else mask & b
        fire = 1.0 if mask is None else bsim.popcount(mask) / s.n
        if op.kind in ('CCX', 'CCZ', 'CSWAP'):
            a = op.q
            if op.kind == 'CCX':
                pairs = [((a[0], a[1]), None)]
            elif op.kind == 'CSWAP':
                pairs = [((a[0], a[1]), a[2])]
            else:
                pairs = [((a[0], a[1]), None), ((a[0], a[2]), None), ((a[1], a[2]), None)]
            # Echelon basis of live wires at this point.
            basis: dict[int, int] = {}
            allset = to_int(np.full(s.w, bsim.ONES, dtype=np.uint64))
            for v in [to_int(s.q[k]) for k in range(NQ)] + [allset]:
                while v:
                    h = v.bit_length() - 1
                    p = basis.get(h)
                    if p is None:
                        basis[h] = v
                        break
                    v ^= p

            def red(v: int) -> int:
                # Reduce fully: walk pivots from high to low.
                for h in sorted(basis, reverse=True):
                    if (v >> h) & 1:
                        v ^= basis[h]
                return v

            hist_red: dict[int, tuple] = {}
            for he in history:
                r = red(he[3])
                hist_red[r] = he  # latest wins since history is chronological
            for (u, w), other in pairs:
                val = s.q[u] & (s.q[w] if other is None else s.q[w] ^ s.q[other])
                vi = to_int(val)
                r = red(vi)
                if r == 0:
                    rows.append(dict(line=op.line, raw=op.raw, kind=op.kind, fire=fire, i=i, match='linear', pair=[u, w]))
                    continue
                he = hist_red.get(r)
                if he is not None:
                    rows.append(dict(line=op.line, raw=op.raw, kind=op.kind, fire=fire, i=i, match='prior', pair=[u, w],
                                     e_i=he[0], e_line=he[1], e_raw=he[2]))
                history.append((i, op.line, op.raw, vi))
        bsim.step(s, op)
        occupied[:, i] = s.q.any(axis=1)
        for w in op.q:
            occupied[w, i] = True
    for r in rows:
        if r['match'] != 'prior':
            continue
        span = occupied[:, r['e_i']:r['i'] + 1].any(axis=1)
        r['free_wires'] = [int(k) for k in np.flatnonzero(~span)]
    json.dump(rows, open(sys.argv[2], 'w'))
    print('hits', len(rows))
    for r in rows:
        if r.get('match') == 'prior':
            print(r['line'], r['raw'][:26], 'fire %.3f' % r['fire'], 'pair', r['pair'], '<-', r['e_line'], r['e_raw'][:26],
                  'gap', r['line'] - r['e_line'], 'free', r['free_wires'][:6])
    print('saving if all free (fire sum, kinds):', sum(r['fire'] for r in rows if r.get('free_wires')))


if __name__ == '__main__':
    main()
