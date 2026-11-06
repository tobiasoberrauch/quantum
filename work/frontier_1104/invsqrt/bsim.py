#!/usr/bin/env python3
"""Bit-sliced numpy simulator for kmx text, mirroring kickmix/sim/sim.h semantics.

Used only as a fast pre-check and analysis tool. Every claim is finally made by
the official verifier in data/verifiers/invsqrt.
"""
from __future__ import annotations

import dataclasses
import math
import os
import sys
from fractions import Fraction

import numpy as np

ROOT = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum'
LANE = ROOT + '/work/frontier_1104/invsqrt'
MAX_X = 3133452
ONES = np.uint64(0xFFFFFFFFFFFFFFFF)
TWO63 = 1 << 63


@dataclasses.dataclass
class Op:
    kind: str
    q: tuple
    bit: int = -1          # bit target (HMR, BIT_*)
    cond: int = -1         # 'if bN'
    angle: Fraction | None = None
    line: int = -1
    raw: str = ''


def parse_kmx(path_or_lines) -> tuple[list[Op], list[str]]:
    """Returns (ops, header_lines). Line numbers are 0-based within the file."""
    if isinstance(path_or_lines, str):
        with open(path_or_lines, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
    else:
        lines = list(path_or_lines)
    ops: list[Op] = []
    header: list[str] = []
    for i, ln in enumerate(lines):
        t = ln.split()
        if not t:
            continue
        k = t[0]
        if k in ('APPEND_TO_REGISTER', 'REGISTER'):
            header.append(ln)
            continue
        cond = -1
        if len(t) >= 3 and t[-2] == 'if':
            cond = int(t[-1][1:])
            t = t[:-2]
        q: list[int] = []
        bit = -1
        angle = None
        for a in t[1:]:
            if a[0] == 'q':
                q.append(int(a[1:]))
            elif a[0] == 'b':
                bit = int(a[1:])
            else:
                angle = Fraction(a)
        ops.append(Op(k, tuple(q), bit, cond, angle, i, ln))
    return ops, header


class State:
    def __init__(self, xs: np.ndarray, seed: int, nq: int = 62):
        self.n = len(xs)
        if self.n % 64:
            raise ValueError('shots must be a multiple of 64')
        self.w = self.n // 64
        self.xs = xs
        self.q = np.zeros((nq, self.w), dtype=np.uint64)
        for i in range(22):
            self.q[i] = np.packbits(((xs >> np.uint64(i)) & np.uint64(1)).astype(np.uint8),
                                    bitorder='little').view(np.uint64)
        self.bits: dict[int, np.ndarray] = {}
        self.zero = np.zeros(self.w, dtype=np.uint64)
        self.sign = np.zeros(self.w, dtype=np.uint64)
        self.units = np.zeros(self.n, dtype=np.uint64)   # dyadic+fine phase in 2^-64 turns
        self.rng = np.random.Generator(np.random.PCG64(seed))
        self.tof = 0
        self.t = 0
        self.rot = 0
        self.stack: list[np.ndarray] = []
        self.base: np.ndarray | None = None  # None means all shots

    def copy(self) -> 'State':
        s = State.__new__(State)
        s.n, s.w, s.xs, s.zero = self.n, self.w, self.xs, self.zero
        s.q = self.q.copy()
        s.bits = {k: v.copy() for k, v in self.bits.items()}
        s.sign = self.sign.copy()
        s.units = self.units.copy()
        s.rng = np.random.Generator(np.random.PCG64())
        s.rng.bit_generator.state = self.rng.bit_generator.state
        s.tof, s.t, s.rot = self.tof, self.t, self.rot
        s.stack = [a.copy() for a in self.stack]
        s.base = None if self.base is None else self.base.copy()
        return s

    def unpack(self, packed: np.ndarray) -> np.ndarray:
        return np.unpackbits(packed.view(np.uint8), bitorder='little')[:self.n]


def units_of(angle: Fraction) -> int:
    """Half-turns to 2^-64 turn units, rounded as the verifier rounds a total."""
    n, d = angle.as_integer_ratio()
    return (((n << 64) // d + 1) >> 1) & ((1 << 64) - 1)


def angle_class(angle: Fraction) -> str:
    if angle % Fraction(1, 2) == 0:
        return 'clifford'
    if angle % Fraction(1, 4) == 0:
        return 't'
    return 'rotation'


def popcount(a: np.ndarray) -> int:
    return int(np.bitwise_count(a).sum())


def step(s: State, op: Op, rotcol=None, force: dict | None = None) -> None:
    k = op.kind
    if k == 'PUSH_CONDITION':
        b = s.bits.get(op.cond, s.zero)
        s.base = b.copy() if s.base is None else s.base & b
        s.stack.append(s.base)
        return
    if k == 'POP_CONDITION':
        s.stack.pop()
        s.base = s.stack[-1] if s.stack else None
        return
    cond = s.base
    if op.cond >= 0:
        b = s.bits.get(op.cond, s.zero)
        cond = b if cond is None else cond & b
    q = s.q
    a = op.q
    if k == 'CX':
        if cond is None:
            q[a[1]] ^= q[a[0]]
        else:
            q[a[1]] ^= q[a[0]] & cond
    elif k == 'CZ':
        m = q[a[0]] & q[a[1]]
        s.sign ^= m if cond is None else m & cond
    elif k == 'Z':
        s.sign ^= q[a[0]] if cond is None else q[a[0]] & cond
    elif k == 'X':
        if cond is None:
            q[a[0]] ^= ONES
        else:
            q[a[0]] ^= cond
    elif k == 'CCX':
        m = q[a[0]] & q[a[1]]
        if cond is None:
            s.tof += s.n
        else:
            m = m & cond
            s.tof += popcount(cond)
        q[a[2]] ^= m
    elif k == 'CCZ':
        m = q[a[0]] & q[a[1]] & q[a[2]]
        if cond is None:
            s.tof += s.n
        else:
            m = m & cond
            s.tof += popcount(cond)
        s.sign ^= m
    elif k == 'CSWAP':
        c = q[a[0]]
        if cond is None:
            s.tof += s.n
        else:
            c = c & cond
            s.tof += popcount(cond)
        d = (q[a[1]] ^ q[a[2]]) & c
        q[a[1]] ^= d
        q[a[2]] ^= d
    elif k == 'SWAP':
        if cond is None:
            q[[a[0], a[1]]] = q[[a[1], a[0]]]
        else:
            d = (q[a[0]] ^ q[a[1]]) & cond
            q[a[0]] ^= d
            q[a[1]] ^= d
    elif k == 'HMR':
        r = s.rng.integers(0, 1 << 64, size=s.w, dtype=np.uint64, endpoint=False)
        if force is not None and op.line in force:
            r = (np.zeros(s.w, dtype=np.uint64) if force[op.line] == 0
                 else np.full(s.w, ONES, dtype=np.uint64))
        if cond is None:
            s.bits[op.bit] = r
            s.sign ^= q[a[0]] & r
            q[a[0]] = 0
        else:
            old = s.bits.get(op.bit, s.zero)
            s.bits[op.bit] = (old & ~cond) ^ (r & cond)
            s.sign ^= q[a[0]] & r & cond
            q[a[0]] &= ~cond
    elif k == 'R':
        r = s.rng.integers(0, 1 << 64, size=s.w, dtype=np.uint64, endpoint=False)
        if cond is None:
            s.sign ^= q[a[0]] & r
            q[a[0]] = 0
        else:
            s.sign ^= q[a[0]] & r & cond
            q[a[0]] &= ~cond
    elif k == 'NEG':
        s.sign ^= ONES if cond is None else cond
    elif k == 'BIT_INVERT':
        old = s.bits.get(op.bit, s.zero)
        s.bits[op.bit] = old ^ (ONES if cond is None else cond)
    elif k == 'BIT_STORE0':
        old = s.bits.get(op.bit, s.zero)
        s.bits[op.bit] = s.zero.copy() if cond is None else old & ~cond
    elif k == 'BIT_STORE1':
        old = s.bits.get(op.bit, s.zero)
        s.bits[op.bit] = np.full(s.w, ONES, dtype=np.uint64) if cond is None else old | cond
    elif k == 'Z_POW':
        m = q[a[0]] if cond is None else q[a[0]] & cond
        mb = s.unpack(m)
        fired = s.n if cond is None else popcount(cond)
        cls = angle_class(op.angle)
        if cls == 't':
            s.t += fired
        elif cls == 'rotation':
            s.rot += fired
        if rotcol is not None and cls == 'rotation':
            rotcol(op, mb)
        else:
            s.units += mb.astype(np.uint64) * np.uint64(units_of(op.angle))
    else:
        raise ValueError(f'unknown op {k}: {op.raw}')


def domain(extra_pad: bool = True) -> np.ndarray:
    xs = np.arange(1, MAX_X + 1, dtype=np.uint64)
    pad = (-len(xs)) % 64
    if pad:
        xs = np.concatenate([xs, np.arange(1, pad + 1, dtype=np.uint64)])
    return xs


def reference(xs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(target, tol) in 2^-64 turn units for each x in xs, from the verifier's formula."""
    cache = LANE + '/inputs/ref_full.npz'
    if os.path.exists(cache):
        d = np.load(cache)
        tgt, tol = d['target'], d['tol']
    else:
        rs = [math.isqrt((1 << 130) // x) for x in range(1, MAX_X + 1)]
        tgt = np.array([((r + 1) >> 1) & ((1 << 64) - 1) for r in rs], dtype=np.uint64)
        tol = np.array([min(r >> 25, TWO63) for r in rs], dtype=np.uint64)
        np.savez(cache, target=tgt, tol=tol)
    idx = (xs - np.uint64(1)).astype(np.int64)
    return tgt[idx], tol[idx]


def phase_units(s: State) -> np.ndarray:
    sign = s.unpack(s.sign).astype(np.uint64) * np.uint64(TWO63)
    return s.units + sign


def check(s: State) -> dict:
    """Value checks plus margin, using the units accumulated so far."""
    x_back = np.zeros(s.n, dtype=np.uint64)
    for i in range(22):
        x_back |= s.unpack(s.q[i]).astype(np.uint64) << np.uint64(i)
    restored = bool(np.array_equal(x_back, s.xs))
    dirty = int((s.q[22:].any(axis=1)).sum())
    tgt, tol = reference(s.xs)
    err = (phase_units(s) - tgt).view(np.int64)
    used = np.abs(err).view(np.uint64)
    margin = tol.astype(np.int64) - used.astype(np.int64)
    return dict(restored=restored, dirty_qubits=dirty, min_margin=int(margin.min()),
                worst_x=int(s.xs[int(margin.argmin())]), tof=s.tof / s.n, t=s.t / s.n, rot=s.rot / s.n,
                fails=int((margin < 0).sum()))


def rotation_t(eps: float) -> float:
    return 0.56 * math.log2(1 / eps) + 5.3


def cost(q: int, tof: float, t: float, rot: float, margin: float) -> dict:
    eps = math.pi * margin / 2**64 / rot if rot else None
    tc = t + (rot * rotation_t(eps) if rot else 0)
    c = tof + tc / 4
    return dict(C=c, score=q * c, ratio=2076774.233715282 / (q * c), eps=eps)


def run(ops: list[Op], xs: np.ndarray, seed: int = 1, rotcol=None, force=None,
        hook=None, nq: int = 62) -> State:
    s = State(xs, seed, nq=nq)
    for i, op in enumerate(ops):
        if hook is not None:
            hook(i, op, s)
        step(s, op, rotcol, force)
    return s


if __name__ == '__main__':
    import time
    ops, _ = parse_kmx(sys.argv[1])
    t0 = time.time()
    st = run(ops, domain(), seed=int(sys.argv[2]) if len(sys.argv) > 2 else 1)
    r = check(st)
    print(r, round(time.time() - t0, 1), 's')
    print(cost(62, r['tof'], r['t'], r['rot'], r['min_margin']))
