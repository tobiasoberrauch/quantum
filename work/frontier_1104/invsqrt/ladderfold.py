#!/usr/bin/env python3
"""Shrink a CCZ ladder whose flag product is true on few x: rewrite beta toggles onto a basis of the wires on that support.

The ladder applies f1*f2*sum(beta_w * w). On the support of f1*f2 the wires span a small space, so betas of dependent wires
can be folded onto basis wires, which makes the ladder's first-nonzero test fire less often. Phase is unchanged on the domain.
usage: ladderfold.py in.kmx out.kmx f1 f2 [f1 f2 ...]
"""
import sys
import numpy as np
import bsim
from deltest import parse_ladders

def main():
    src, dst = sys.argv[1], sys.argv[2]
    pairs = list(zip(map(int, sys.argv[3::2]), map(int, sys.argv[4::2])))
    ops, _ = bsim.parse_kmx(src)
    lines = open(src, encoding='utf-8').read().splitlines()
    lads = parse_ladders(ops)
    xs = np.tile(np.arange(1, 1 << 15, dtype=np.uint64), 4)
    xs = xs[:len(xs) // 64 * 64]
    for f1, f2 in pairs:
        cand = [L for L in lads if L['f1'] == f1 and L['f2'] == f2 and len(L['betas']) == max(len(M['betas']) for M in lads if M['f1'] == f1 and M['f2'] == f2)]
        L = cand[0]
        s = bsim.State(xs, 5)
        for op in ops:
            if op.line == L['line']:
                break
            bsim.step(s, op)
        un = lambda p: s.unpack(p).astype(bool)
        sup = un(s.q[f1]) & un(s.q[f2])
        ux = sorted(set(xs[sup].tolist()))
        first = {}
        for i, x in enumerate(xs.tolist()):
            first.setdefault(x, i)
        idx = [first[x] for x in ux]
        vecs = {w: int(''.join('1' if un(s.q[w])[i] else '0' for i in idx), 2) for w, _ in L['betas']}
        print('ladder', L['line'], (f1, f2), 'support x', ux[:20], 'n', len(ux))
        piv = {}
        basis = []
        comb = {}
        BCONST = 60000 + f1 * 100 + f2
        allones = (1 << len(idx)) - 1
        piv[allones.bit_length() - 1] = (allones, 1)
        basis.append((-1, BCONST))
        for w, beta in L['betas']:
            v = vecs[w]
            tag = 0
            while v:
                h = v.bit_length() - 1
                if h in piv:
                    v ^= piv[h][0]
                    tag ^= piv[h][1]
                else:
                    piv[h] = (v, tag | (1 << len(basis)))
                    basis.append((w, beta))
                    tag = None
                    break
            if tag is not None:
                comb[w] = [basis[i] for i in range(len(basis)) if (tag >> i) & 1]
        print(' rank', len(basis), 'basis', basis, 'fold', {k: [b[0] for b in v] for k, v in comb.items()})
        wire_of = {b: w for w, b in L['betas']}
        betaset = set(wire_of)
        store = dict(L['store'])
        store[BCONST] = min(store.values())
        L['betas'] = L['betas'] + [(-1, BCONST)]
        L['store'] = store
        edits = {}
        # rewrite every BIT_INVERT beta if bk line in the beta definition area
        lo = min(store.values())
        hi = L['line']
        out = []
        for i, ln in enumerate(lines):
            if lo <= i < hi and ln.startswith('BIT_INVERT'):
                p = ln.split()
                b = int(p[1][1:])
                if b in betaset and wire_of[b] in comb:
                    cond = p[3]
                    for w2, b2 in comb[wire_of[b]]:
                        out.append(f'BIT_INVERT b{b2} if {cond}')
                    continue
            if i == lo:
                out.append(f'BIT_STORE0 b{BCONST}')
            if i == hi:
                out.append(f'CZ q{f1} q{f2} if b{BCONST}')
            out.append(ln)
        # Basis toggles must precede the store that reads them, so reorder by rebuilding definitions in place.
        lines = reorder(out, L)
        open(dst, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
        ops, _ = bsim.parse_kmx(dst)
        lads = parse_ladders(ops)

def reorder(lines, L):
    """Gathers all toggles of each beta right after its BIT_STORE0 line, keeping the rest in order."""
    betas = {b for _, b in L['betas']}
    tog = {b: [] for b in betas}
    out = []
    lo = min(L['store'].values())
    # first scan collects toggles in the definition range
    hi = next(i for i, ln in enumerate(lines) if i > lo and ln.startswith('PUSH_CONDITION') and ln.endswith(f"b{L['betas'][0][1]}"))
    for i in range(lo, hi):
        ln = lines[i]
        if ln.startswith('BIT_INVERT'):
            b = int(ln.split()[1][1:])
            if b in betas:
                tog[b].append(ln)
    for i, ln in enumerate(lines):
        if lo <= i < hi and ln.startswith('BIT_INVERT') and int(ln.split()[1][1:]) in betas:
            continue
        out.append(ln)
        if lo <= i < hi and ln.startswith('BIT_STORE0'):
            b = int(ln.split()[1][1:])
            if b in betas:
                out.extend(tog[b])
    return out

main()
