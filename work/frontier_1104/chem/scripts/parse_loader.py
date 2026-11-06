#!/usr/bin/env python3
"""Symbolic GF(2) parse of a loader: controls of every CCX as symbol masks; product outputs.
Symbols: addr bits (0..10), input word bits (11..50), ancilla symbols (R+CCX caches) and products.
Prints statistics for one loader."""
from __future__ import annotations

import collections
import json
import pickle
import re
import sys

import kickmix as km
import numpy as np


def parse(path):
    c = km.Circuit.from_file(path, format='kmb')
    txt = str(c).splitlines()
    nq = c.num_qubits
    # state[q] = python int mask over symbols
    sym_names = []
    def new_sym(name):
        sym_names.append(name)
        return 1 << (len(sym_names) - 1)
    state = [0] * nq
    regs = {}
    for l in txt:
        p = l.split()
        if p[0] == 'APPEND_TO_REGISTER':
            q = int(p[1][1:]); regs.setdefault(p[2], []).append(q)
    for q in range(51):
        state[q] = new_sym(('in', q))
    const = new_sym(('const',))
    ops = []
    ccx = []
    live_anc = {}
    for idx, l in enumerate(txt):
        p = l.split()
        op = p[0]
        if op == 'CX':
            a, b = int(p[1][1:]), int(p[2][1:])
            state[b] ^= state[a]
        elif op == 'X':
            state[int(p[1][1:])] ^= const
        elif op == 'R':
            q = int(p[1][1:])
            state[q] = 0
        elif op == 'CCX':
            a, b, t = int(p[1][1:]), int(p[2][1:]), int(p[3][1:])
            s = new_sym(('ccx', len(ccx)))
            ccx.append(dict(idx=idx, a=a, b=b, t=t, fa=state[a], fb=state[b], tstate=state[t], sym=s, target_is_word=11 <= t < 51))
            state[t] ^= s
        elif op == 'HMR':
            pass
        elif op in ('CZ', 'APPEND_TO_REGISTER', 'REGISTER'):
            pass
        else:
            raise ValueError(op + ' in ' + l)
    return dict(nq=nq, sym_names=sym_names, ccx=ccx, state=state, txt_len=len(txt))


if __name__ == '__main__':
    d = parse(sys.argv[1])
    print('nq', d['nq'], 'ccx', len(d['ccx']), 'syms', len(d['sym_names']))
    tgt = collections.Counter('word' if x['target_is_word'] else 'anc' for x in d['ccx'])
    print(tgt)
    wire = lambda m: bin(m).count('1')
    inmask = (1 << 11) - 1
    wordin = ((1 << 51) - 1) ^ inmask
    # classification of controls for word-target products
    dirty = sum(1 for x in d['ccx'] if (x['fa'] | x['fb']) & wordin)
    print('controls touching word inputs', dirty)
    anc = [x for x in d['ccx'] if not x['target_is_word']]
    print('anc controls sample', [(x['a'], x['b'], x['t'], x['tstate'] != 0) for x in anc[:5]])
    prods = [x for x in d['ccx'] if x['target_is_word']]
    print('prod sample', [(x['a'], x['b'], x['t'], wire(x['fa']), wire(x['fb'])) for x in prods[:8]])
    # final word states
    final = d['state'][11:51]
    print('final word wires: products per wire', [sum(1 for x in d['ccx'] if s & x['sym']) for s in final])
    print('last word state input part', [bin(s & wordin) for s in final[:3]])
