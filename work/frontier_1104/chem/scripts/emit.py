#!/usr/bin/env python3
"""Re-emit the product section of a shipped loader with a new product list.

Keeps prefix (infrastructure and decoder) and suffix (cleanup) byte-identical in meaning. Products: tuples
(f, g, wires) where f, g are bool truth tables over the 1220 legal addresses and wires a list of word wires.
"""
from __future__ import annotations

import sys

import kickmix as km
import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
import tensor_probe as tp  # noqa: E402

N = 1220
ADDR = np.arange(N)
Y = ADDR >> 4
Z = ADDR & 15
WORD = range(11, 51)


def additive_cross(f, g):
    """True if f&g has a nonzero y-z cross part on legal addresses (i.e. is a real product)."""
    h = f & g
    tab = np.zeros((77, 16), dtype=bool)
    tab[Y, Z] = h
    v = tab[:76]
    d = v ^ v[:, :1] ^ v[:1, :] ^ v[0, 0]
    return d.any()


def run_tt(ops, st):
    st = st.copy()
    for op, q in ops:
        if op == 'CX':
            st[q[1]] ^= st[q[0]]
        elif op == 'X':
            st[q[0]] = ~st[q[0]]
        elif op == 'R':
            st[q[0]] = False
        elif op == 'CCX':
            st[q[2]] ^= st[q[0]] & st[q[1]]
        elif op == 'HMR':
            st[q[0]] = False
    return st


def init_state(nq, words, k, reverse=False):
    st = np.zeros((nq, N), dtype=bool)
    for i in range(11):
        st[i] = (ADDR >> i) & 1
    src = k if reverse else k - 1
    if src >= 0:
        for j in range(5):
            for b in range(8):
                st[11 + 8 * j + b] = (words[:, 5 * src + j] >> b) & 1
    return st


class Basis:
    """Gaussian elimination over packed truth tables with combination tracking."""

    def __init__(self, wires, tts):
        self.ech = {}
        self.wires = wires
        for idx, tt in enumerate(tts):
            v = int.from_bytes(np.packbits(tt).tobytes(), 'big')
            m = 1 << idx
            while v:
                h = v.bit_length() - 1
                p = self.ech.get(h)
                if p is None:
                    self.ech[h] = (v, m)
                    break
                v ^= p[0]
                m ^= p[1]
        self.dim = len(self.ech)

    def express(self, tt):
        v = int.from_bytes(np.packbits(tt).tobytes(), 'big')
        m = 0
        while v:
            h = v.bit_length() - 1
            p = self.ech.get(h)
            if p is None:
                return None
            v ^= p[0]
            m ^= p[1]
        return [self.wires[i] for i in range(len(self.wires)) if m >> i & 1]


def split_sections(ops, nq, words, k):
    st = init_state(nq, words, k)
    first, last = None, None
    cur = st
    for i, (op, q) in enumerate(ops):
        if op == 'CCX':
            f, g = cur[q[0]].copy(), cur[q[1]].copy()
            if additive_cross(f, g):
                if first is None:
                    first = i
                last = i
        cur = run_tt([(op, q)], cur)
    return first, last


def header_and_ops(path):
    c = km.Circuit.from_file(path, format='kmb')
    hdr, ops = [], []
    for l in str(c).splitlines():
        p = l.split()
        if p[0] in ('APPEND_TO_REGISTER', 'REGISTER'):
            hdr.append(l)
        else:
            ops.append(l)
    return hdr, ops, c.num_qubits


def parse(line):
    p = line.split()
    return p[0], [int(x[1:]) for x in p[1:] if x.startswith('q')]


def rebuild(path, words, k, products, out_path, log=print):
    hdr, lines, nq = header_and_ops(path)
    ops = [parse(l) for l in lines]
    first, last = split_sections(ops, nq, words, k)
    # back off to the start of the CX run that prepares the first product: section begins right after previous CCX/R
    start = first
    while start > 0 and ops[start - 1][0] == 'CX':
        start -= 1
    end = last + 1
    while end < len(ops) and ops[end][0] == 'CX':
        end += 1
    st_f = init_state(nq, words, k)
    st_r = init_state(nq, words, k, reverse=True)
    s0f = run_tt(ops[:start], st_f)
    s0r = run_tt(ops[:start], st_r)
    s1f = run_tt(ops[start:end], s0f)
    s1r = run_tt(ops[start:end], s0r)
    Df = s0f ^ s1f
    Dr = s0r ^ s1r
    nonword_changed = [q for q in range(nq) if q not in WORD and Df[q].any()]
    log(f'section ops {start}..{end} of {len(ops)}; nonword changed {nonword_changed}; D rev==fwd {bool((Df == Dr).all())}')
    srcs = [q for q in range(nq) if q not in WORD or (q - 11) % 8 == 7]
    srcs = [q for q in srcs if (s0f[q] == s0r[q]).all() and not Df[q].any()]
    # exclude ancillas that are unused (all-zero) harmless
    tts = [s0f[q] for q in srcs]
    constant = np.ones(N, dtype=bool)
    basis = Basis(srcs + ['const'], tts + [constant])
    log(f'source wires {len(srcs)} dim {basis.dim}')
    new_lines = []
    residual = Df.copy()
    wires_all = set()
    for f, g, wset in products:
        ex_f = basis.express(f)
        ex_g = basis.express(g)
        if ex_f is None or ex_g is None:
            raise ValueError('control function outside the source span')
        Fs, Gs = set(ex_f), set(ex_g)
        Fc, Gc = 'const' in Fs, 'const' in Gs
        Fs.discard('const')
        Gs.discard('const')
        c1 = c2 = None
        for a in Fs:
            for b in Gs:
                if a != b and not (a in Gs and b in Fs):
                    c1, c2 = a, b
                    break
            if c1 is not None:
                break
        if c1 is None:
            raise ValueError('no control pair')
        pre = []
        if c1 in Gs:
            # c1 participates in g: build g first (uses original c1), then f (c2 not in F)
            pre += [f'CX q{w} q{c2}' for w in Gs if w != c2]
            if Gc:
                pre.append(f'X q{c2}')
            pre += [f'CX q{w} q{c1}' for w in Fs if w != c1]
            if Fc:
                pre.append(f'X q{c1}')
        else:
            # build f first using original wires (c2 may be in F), then g (c1 not in G)
            pre += [f'CX q{w} q{c1}' for w in Fs if w != c1]
            if Fc:
                pre.append(f'X q{c1}')
            pre += [f'CX q{w} q{c2}' for w in Gs if w != c2]
            if Gc:
                pre.append(f'X q{c2}')
        wl = [w for w in wset]
        t = wl[0]
        fan = [f'CX q{t} q{o}' for o in wl[1:]]
        new_lines += pre + fan + [f'CCX q{c1} q{c2} q{t}'] + fan + pre[::-1]
        for w in wl:
            residual[w] ^= f & g
    # residual must be linear in the sources
    for w in range(nq):
        if residual[w].any():
            ex = basis.express(residual[w])
            if ex is None:
                raise ValueError(f'residual on wire {w} is not available from the sources')
            for q in ex:
                if q == 'const':
                    new_lines.append(f'X q{w}')
                else:
                    new_lines.append(f'CX q{q} q{w}')
    text = '\n'.join(hdr + lines[:start] + new_lines + lines[end:]) + '\n'
    tmp = out_path + '.kmx'
    with open(tmp, 'w') as fh:
        fh.write(text)
    c = km.Circuit.from_file(tmp, format='kmx')
    c.to_file(out_path, format='kmb') if hasattr(c, 'to_file') else None
    return c
