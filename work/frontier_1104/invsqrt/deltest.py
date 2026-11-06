#!/usr/bin/env python3
"""Delete one Toffoli-like gate, repair measurement phase kicks with Clifford patches, measure damage.

Lockstep simulation of base and mutant on the same shots with the same outcomes. Every
HMR that measures a wire whose mutant value differs from base needs a phase patch
`b * delta`. delta is solved as a GF(2) quadratic form in live mutant wires; quadratic
forms conditioned on b are Clifford and free. Rotations keep their natural effect.

usage: deltest.py in.kmx out.jsonl [--min-p P --max-p P --workers N --lines L1,L2]
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import time

import numpy as np

import bsim

NQ = 62
_state: dict = {}


def to_int(a: np.ndarray) -> int:
    return int.from_bytes(a.tobytes(), 'little')


def parse_ladders(ops: list[bsim.Op]) -> list[dict]:
    """Finds CCZ ladders: PUSH if beta0; CX wi w0 if betai...; CCZ f1 f2 w0. Maps wires to beta bits."""
    out = []
    i = 0
    while i < len(ops):
        o = ops[i]
        if o.kind == 'PUSH_CONDITION':
            j = i + 1
            pairs = []
            while j < len(ops) and ops[j].kind == 'CX' and ops[j].cond >= 0:
                pairs.append((ops[j].q[0], ops[j].cond))
                j += 1
            if len(pairs) >= 5 and ops[j].kind == 'CCZ' and all(p[0] != ops[j].q[2] for p in pairs) \
                    and all(ops[k].q[1] == ops[j].q[2] for k in range(i + 1, j)):
                f1, f2, w0 = ops[j].q
                betas = [(w0, o.cond)] + pairs
                stores = {}
                for k in range(max(0, i - 800), i):
                    if ops[k].kind == 'BIT_STORE0':
                        stores[ops[k].bit] = ops[k].line
                if all(b in stores for _, b in betas):
                    out.append(dict(i=i, f1=f1, f2=f2, line=o.line, betas=betas, store={b: stores[b] for _, b in betas}))
                    i = j
        i += 1
    return out


def monomials(nq: int) -> list[tuple]:
    out: list[tuple] = [()]
    out += [(i,) for i in range(nq)]
    out += [(i, j) for i in range(nq) for j in range(i + 1, nq)]
    return out


MONO = monomials(NQ)


def solve_quad(q: np.ndarray, target: np.ndarray, mask: np.ndarray | None, exclude: tuple = (),
               cubic: list[tuple] | None = None) -> list[tuple] | None:
    """Finds monomials over live wires whose XOR equals target on all (masked) shots."""
    tgt = target if mask is None else target & mask
    t = to_int(tgt)
    if t == 0:
        return []
    allset = np.full(q.shape[1], bsim.ONES, dtype=np.uint64)
    if mask is not None:
        allset = mask
    qm = q if mask is None else q & mask
    wires = [to_int(qm[i]) for i in range(NQ)]
    allint = to_int(allset)
    pivots: dict[int, tuple[int, int]] = {}
    tags: list[tuple] = []
    seen: set[int] = set()

    def add(v: int, mono: tuple) -> None:
        if v == 0 or v in seen:
            return
        seen.add(v)
        tag = 1 << len(tags)
        tags.append(mono)
        while v:
            h = v.bit_length() - 1
            p = pivots.get(h)
            if p is None:
                pivots[h] = (v, tag)
                return
            v ^= p[0]
            tag ^= p[1]

    def reduce_target() -> list[tuple] | None:
        v, tag = t, 0
        while v:
            h = v.bit_length() - 1
            p = pivots.get(h)
            if p is None:
                return None
            v ^= p[0]
            tag ^= p[1]
        return [tags[i] for i in range(len(tags)) if (tag >> i) & 1]

    add(allint, ())
    live = [i for i in range(NQ) if wires[i] and i not in exclude]
    for i in live:
        add(wires[i], (i,))
    sol = reduce_target()
    if sol is not None:
        return sol
    for a in range(len(live)):
        wa = wires[live[a]]
        for b in range(a + 1, len(live)):
            add(wa & wires[live[b]], (live[a], live[b]))
    sol = reduce_target()
    if sol is not None or not cubic:
        return sol
    for tag, col in cubic:
        add(to_int(col if mask is None else col & mask), tag)
    return reduce_target()


def patch_lines(mono: list[tuple], b: int) -> list[str]:
    out = []
    tail = f' if b{b}' if b >= 0 else ''
    for m in mono:
        if m and m[0] in ('L', 'W'):
            continue
        if len(m) == 0:
            out.append('NEG' + tail)
        elif len(m) == 1:
            out.append(f'Z q{m[0]}' + tail)
        else:
            out.append(f'CZ q{m[0]} q{m[1]}' + tail)
    return out


def phase_value(s: bsim.State, op: bsim.Op) -> np.ndarray:
    v = s.q[op.q[0]]
    for w in op.q[1:]:
        v = v & s.q[w]
    return v


def shots_for(line: int, seed: int) -> np.ndarray:
    """Rare set S (repeated for outcome coverage), all small x and a random sample."""
    rng = np.random.default_rng(seed)
    S = _state['S'].get(line)
    parts = [np.arange(1, 2049, dtype=np.uint64),
             rng.integers(1, bsim.MAX_X + 1, size=4096, dtype=np.uint64)]
    if S is not None and len(S):
        s = S if len(S) <= 2048 else rng.choice(S, 2048, replace=False)
        parts += [s] * 4
    xs = np.concatenate(parts)
    pad = (-len(xs)) % 64
    if pad:
        xs = np.concatenate([xs, rng.integers(1, bsim.MAX_X + 1, size=pad, dtype=np.uint64)])
    return xs


def fix_windows(ops: list[bsim.Op]) -> list[dict]:
    """Runs of `CZ f w if b` on one flag wire f; a monomial f*w can be patched into such a run."""
    out = []
    i = 0
    while i < len(ops):
        o = ops[i]
        if o.kind == 'CZ' and o.cond >= 0:
            f = o.q[0]
            j = i
            ws = set()
            while j < len(ops) and ops[j].kind == 'CZ' and ops[j].cond >= 0 and ops[j].q[0] == f:
                ws.add(ops[j].q[1])
                j += 1
            if j - i >= 10:
                out.append(dict(i=i, f=f, line=o.line, wires=sorted(ws)))
                i = j
                continue
        i += 1
    return out


def cubic_columns(ops: list[bsim.Op], xs: np.ndarray, seed: int, after: int) -> list[tuple]:
    """(tag, column) for every ladder monomial f1*f2*w and every fix-up window monomial f*w over the base run."""
    lad = _state['ladders']
    want = {L['i']: L for L in lad if L['i'] > after}
    win = {W['i']: W for W in _state['windows'] if W['i'] > after}
    cols: list[tuple] = []
    s = bsim.State(xs, seed)
    last = max(list(want) + list(win)) if (want or win) else -1
    for i, op in enumerate(ops):
        if i > last:
            break
        if i in win:
            W = win[i]
            for w in W['wires']:
                cols.append((('W', W['line'], W['f'], w, W['line'] - 1), s.q[W['f']] & s.q[w]))
        if i in want:
            L = want[i]
            ff = s.q[L['f1']] & s.q[L['f2']]
            for w, beta in L['betas']:
                cols.append((('L', L['line'], beta, L['store'][beta]), ff & s.q[w]))
        bsim.step(s, op)
    return cols


def lockstep(ops: list[bsim.Op], g: int, xs: np.ndarray, seed: int, c_base: float) -> dict:
    cubic = cubic_columns(ops, xs, seed, g)
    sb = bsim.State(xs, seed)
    for op in ops[:g]:
        bsim.step(sb, op)
    sm = sb.copy()
    bsim.step(sb, ops[g])
    patches: list[dict] = []
    gone = ops[g]
    for i in range(g + 1, len(ops)):
        op = ops[i]
        if op.kind in ('HMR', 'R'):
            w = op.q[0]
            d = sb.q[w] ^ sm.q[w]
            if d.any():
                if op.kind == 'R':
                    return dict(res='R_dirty', at=op.line, wire=w)
                # mask of this HMR
                mask = sm.base
                if op.cond >= 0:
                    b0 = sm.bits.get(op.cond, sm.zero)
                    mask = b0 if mask is None else mask & b0
                bsim.step(sb, op)
                bsim.step(sm, op)
                sb.rng.bit_generator.state = sm.rng.bit_generator.state
                dm = d if mask is None else d & mask
                if dm.any():
                    usable = [c for c in cubic if c[0][-1] > op.line] if False else [
                        c for c in cubic if (c[0][3] if c[0][0] == 'L' else c[0][1]) > op.line]
                    mono = solve_quad(sm.q, dm, mask, cubic=usable)
                    if mono is None:
                        return dict(res='unpatched', at=op.line, wire=w, nd=bsim.popcount(dm))
                    lines = patch_lines(mono, op.bit)
                    toggles = [(m[3], f'BIT_INVERT b{m[2]} if b{op.bit}') for m in mono if m and m[0] == 'L']
                    toggles += [(m[4], f'CZ q{m[2]} q{m[3]} if b{op.bit}') for m in mono if m and m[0] == 'W']
                    patches.append(dict(after=op.line, lines=lines, toggles=toggles))
                    for ln in lines:
                        o2 = bsim.parse_kmx([ln])[0][0]
                        bsim.step(sm, o2)
                    # Ladder toggles act later; account for them on the mutant sign now.
                    for m in mono:
                        if m and m[0] in ('L', 'W'):
                            col = next(c[1] for c in usable if c[0] == m)
                            sm.sign ^= col & sm.bits[op.bit]
                continue
        if op.kind in ('CZ', 'Z', 'CCZ'):
            d = phase_value(sb, op) ^ phase_value(sm, op)
            if d.any():
                mask = sm.base
                if op.cond >= 0:
                    b0 = sm.bits.get(op.cond, sm.zero)
                    mask = b0 if mask is None else mask & b0
                dm = d if mask is None else d & mask
                if dm.any():
                    usable = [c for c in cubic if (c[0][3] if c[0][0] == 'L' else c[0][1]) > op.line] if op.cond >= 0 else []
                    mono = solve_quad(sm.q, dm, mask, cubic=usable)
                    if mono is None:
                        return dict(res='unpatched_phase', at=op.line, nd=bsim.popcount(dm))
                    bsim.step(sb, op)
                    bsim.step(sm, op)
                    lines = patch_lines(mono, op.cond)
                    toggles = [(m[3], f'BIT_INVERT b{m[2]} if b{op.cond}') for m in mono if m and m[0] == 'L']
                    toggles += [(m[4], f'CZ q{m[2]} q{m[3]} if b{op.cond}') for m in mono if m and m[0] == 'W']
                    patches.append(dict(after=op.line, lines=lines, toggles=toggles))
                    for ln in lines:
                        bsim.step(sm, bsim.parse_kmx([ln])[0][0])
                    for m in mono:
                        if m and m[0] in ('L', 'W'):
                            col = next(c[1] for c in usable if c[0] == m)
                            sm.sign ^= col & sm.bits[op.cond]
                    continue
        bsim.step(sb, op)
        bsim.step(sm, op)
    d_w = (sb.q ^ sm.q).any(axis=1)
    if d_w.any():
        return dict(res='dirty', wires=[int(i) for i in np.flatnonzero(d_w)][:8], npatch=len(patches))
    e = sb.sign ^ sm.sign
    if e.any():
        return dict(res='sign', nsign=bsim.popcount(e), npatch=len(patches))
    r = bsim.check(sm)
    if not r['restored'] or r['dirty_qubits']:
        return dict(res='dirty2')
    # Only compare phase damage to rotations; base and mutant shared outcomes.
    du = (sm.units - sb.units).view(np.int64)
    return dict(res='ok', margin=r['min_margin'], worst_x=r['worst_x'], fails=r['fails'], npatch=len(patches),
                patches=patches, ndphase=int((du != 0).sum()), maxdphase=int(np.abs(du).max()))


def work(job: tuple) -> dict:
    g, seed = job
    ops = _state['ops']
    op = ops[g]
    t0 = time.time()
    xs = shots_for(op.line, seed)
    try:
        r = lockstep(ops, g, xs, seed, _state['c'])
    except Exception as ex:  # noqa: BLE001
        r = dict(res='exc', err=repr(ex)[:200])
    r.update(g=g, line=op.line, raw=op.raw, p_and=_state['p'].get(op.line), fire=_state['fire'].get(op.line),
             sec=round(time.time() - t0, 2))
    return r


def collect_supports(ops: list[bsim.Op], seeds: tuple = (101, 102)) -> tuple[dict, dict, dict]:
    """x sets where a gate's unmasked AND is 1, over full-domain runs."""
    S: dict[int, np.ndarray] = {}
    P: dict[int, float] = {}
    fire: dict[int, float] = {}
    xs = bsim.domain()

    def hook(i: int, op: bsim.Op, s: bsim.State) -> None:
        if op.kind not in ('CCX', 'CCZ', 'CSWAP'):
            return
        a = op.q
        if op.kind == 'CSWAP':
            m = s.q[a[0]] & (s.q[a[1]] ^ s.q[a[2]])
        elif op.kind == 'CCX':
            m = s.q[a[0]] & s.q[a[1]]
        else:
            m = s.q[a[0]] & s.q[a[1]] & s.q[a[2]]
        mask = s.base
        if op.cond >= 0:
            b = s.bits.get(op.cond, s.zero)
            mask = b if mask is None else mask & b
        nf = s.n if mask is None else bsim.popcount(mask)
        fire[op.line] = fire.get(op.line, 0) + nf / s.n / len(seeds)
        pc = bsim.popcount(m)
        P[op.line] = max(P.get(op.line, 0), pc / s.n)
        if pc and pc / s.n < 0.01:
            old = S.get(op.line)
            xn = s.xs[s.unpack(m).astype(bool)]
            S[op.line] = xn if old is None else np.union1d(old, xn)

    for sd in seeds:
        bsim.run(ops, xs, seed=sd, hook=hook)
    return S, P, fire


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('kmx')
    ap.add_argument('out')
    ap.add_argument('--min-p', type=float, default=0.0)
    ap.add_argument('--max-p', type=float, default=1.1)
    ap.add_argument('--workers', type=int, default=5)
    ap.add_argument('--lines', default='')
    ap.add_argument('--kinds', default='CCX,CCZ,CSWAP')
    ap.add_argument('--seed', type=int, default=7)
    a = ap.parse_args()
    ops, _ = bsim.parse_kmx(a.kmx)
    t0 = time.time()
    S, P, fire = collect_supports(ops)
    print('supports', round(time.time() - t0, 1), 's', flush=True)
    _state.update(ops=ops, S=S, p=P, fire=fire, c=0.0, ladders=parse_ladders(ops), windows=fix_windows(ops))
    print('windows', [(W['line'], W['f'], len(W['wires'])) for W in _state['windows']], flush=True)
    print('ladders', [(L['line'], L['f1'], L['f2'], len(L['betas'])) for L in _state['ladders']], flush=True)
    kinds = set(a.kinds.split(','))
    want = {int(v) for v in a.lines.split(',')} if a.lines else None
    jobs = []
    for g, op in enumerate(ops):
        if op.kind not in kinds:
            continue
        if want is not None:
            if op.line not in want:
                continue
        elif not (a.min_p <= P.get(op.line, 0) <= a.max_p) or fire.get(op.line, 0) < 1e-4:
            continue
        jobs.append((g, a.seed))
    print('jobs', len(jobs), flush=True)
    ctx = mp.get_context('fork')
    with ctx.Pool(a.workers) as pool, open(a.out, 'w', encoding='utf-8') as f:
        done = 0
        for r in pool.imap_unordered(work, jobs, chunksize=2):
            f.write(json.dumps(r) + '\n')
            f.flush()
            done += 1
            if done % 25 == 0:
                print(done, round(time.time() - t0, 1), flush=True)
    print('done', round(time.time() - t0, 1))


if __name__ == '__main__':
    main()
