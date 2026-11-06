#!/usr/bin/env python3
"""Greedy Toffoli deletion with Clifford repair and minimax angle refit.

Each round: run deltest on tap-zone gates of the current circuit, LP-refit the
least damaging ones in parallel, apply the best if it lowers C, then strong-check it.
Pre-check only. Claims come from official.py at default shots.

usage: greedy.py start.kmx outdir [rounds]
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import subprocess
import sys
import time

import numpy as np

import bsim
import edit
import lpfit

ZONES = [(15270, 15760), (25830, 26110)]
TOPK = 15
PY = sys.executable


def write_angles(lines: list[str], meta: list[bsim.Op], angles: np.ndarray) -> list[str]:
    """Replaces fine rotation angles. `angles` is in 2^-64 turn units, i.e. 2^-63 half turns."""
    out = list(lines)
    for op, u in zip(meta, angles):
        parts = out[op.line].split()
        cond = parts[3:]  # trailing 'if bN' if present
        out[op.line] = ' '.join([parts[0], parts[1], lpfit.units_to_decimal(float(u))] + cond)
    return out


def evaluate(path: str) -> dict:
    ops, _ = bsim.parse_kmx(path)
    xs = bsim.domain()
    a0, b, meta, s, tol = lpfit.extract(ops, xs, seed=6)
    r = bsim.check(s)
    ang = lpfit.angles_units(meta)
    return dict(ops=ops, a0=a0, b=b, meta=meta, s=s, tol=tol, r=r, ang=ang)


def lp_job(args: tuple) -> dict:
    src, rec, tmpdir = args
    e = edit.edits_from_deletion(rec)
    with open(src, encoding='utf-8') as f:
        lines = f.read().splitlines()
    mut = edit.apply(lines, e)
    p = os.path.join(tmpdir, f"cand_{rec['line']}.kmx")
    with open(p, 'w', encoding='utf-8') as f:
        f.write('\n'.join(mut) + '\n')
    try:
        d = evaluate(p)
        if not d['r']['restored'] or d['r']['dirty_qubits']:
            return dict(line=rec['line'], raw=rec['raw'], res='dirty', C=1e9)
        aa, c = lpfit.fit(d['a0'], d['b'], d['tol'], d['ang'])
        if c <= 0:
            return dict(line=rec['line'], raw=rec['raw'], res='neg', c=c, C=1e9)
        s = d['s']
        cost = bsim.cost(62, s.tof / s.n, s.t / s.n, s.rot / s.n, c)
        out = write_angles(mut, d['meta'], aa)
        q = p.replace('.kmx', '_fit.kmx')
        with open(q, 'w', encoding='utf-8') as f:
            f.write('\n'.join(out) + '\n')
        return dict(line=rec['line'], raw=rec['raw'], res='ok', c=c, C=cost['C'], path=q,
                    tof=s.tof / s.n, t=s.t / s.n)
    except Exception as ex:  # noqa: BLE001
        return dict(line=rec['line'], raw=rec['raw'], res='exc', err=repr(ex)[:200], C=1e9)
    finally:
        if os.path.exists(p):
            os.remove(p)


def strong_check(path: str) -> dict:
    """Full domain on two seeds and small x with many outcome repeats."""
    ops, _ = bsim.parse_kmx(path)
    worst = None
    res = []
    for sd in (101, 202):
        s = bsim.run(ops, bsim.domain(), seed=sd)
        res.append(bsim.check(s))
    xs = np.tile(np.arange(1, 16385, dtype=np.uint64), 64)
    s = bsim.run(ops, xs, seed=303)
    res.append(bsim.check(s))
    worst = min(r['min_margin'] for r in res)
    ok = all(r['restored'] and not r['dirty_qubits'] and not r['fails'] for r in res)
    return dict(ok=ok, min_margin=worst, tof=res[0]['tof'], t=res[0]['t'], rot=res[0]['rot'],
                detail=[{k: r[k] for k in ('restored', 'dirty_qubits', 'fails', 'min_margin')} for r in res])


def main() -> None:
    start, outdir = sys.argv[1], sys.argv[2]
    rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 12
    os.makedirs(outdir, exist_ok=True)
    cur = os.path.join(outdir, 'cur.kmx')
    with open(start, encoding='utf-8') as f, open(cur, 'w', encoding='utf-8') as g:
        g.write(f.read())
    d = evaluate(cur)
    aa, c = lpfit.fit(d['a0'], d['b'], d['tol'], d['ang'])
    s = d['s']
    best_c = bsim.cost(62, s.tof / s.n, s.t / s.n, s.rot / s.n, min(c, d['r']['min_margin']) if d['r']['min_margin'] > 0 else c)['C']
    print('start C', best_c, 'c', c, flush=True)
    log = []
    for rnd in range(rounds):
        t0 = time.time()
        ops, _ = bsim.parse_kmx(cur)
        lines = [str(o.line) for o in ops if o.kind in ('CCX', 'CSWAP')
                 and any(a <= o.line <= b for a, b in ZONES)]
        jl = os.path.join(outdir, f'del_{rnd}.jsonl')
        subprocess.run([PY, os.path.join(bsim.LANE, 'deltest.py'), cur, jl, '--lines', ','.join(lines), '--workers', '5'],
                       check=True, capture_output=True, cwd=bsim.LANE)
        recs = [json.loads(l) for l in open(jl)]
        recs = [r for r in recs if r['res'] == 'ok' and r['fire'] == 1 and (r['p_and'] < 5e-3 or r['margin'] > -3e8)]
        recs.sort(key=lambda r: -r['margin'])
        recs = recs[:TOPK]
        print(f'round {rnd}: {len(recs)} candidates; margins', [r['margin'] for r in recs[:6]], flush=True)
        with mp.get_context('spawn').Pool(5) as pool:
            res = pool.map(lp_job, [(cur, r, outdir) for r in recs])
        res.sort(key=lambda r: r['C'])
        for r in res[:6]:
            print('  ', r['line'], r['raw'][:24], r['res'], r.get('c'), r['C'], flush=True)
        accepted = False
        for r in res:
            if r['res'] != 'ok' or r['C'] >= best_c - 0.05:
                break
            sc = strong_check(r['path'])
            print('   strong', r['line'], sc['ok'], sc['min_margin'], flush=True)
            if not sc['ok']:
                continue
            # Report cost from the strong check's own margin, not the LP's float estimate.
            real = bsim.cost(62, sc['tof'], sc['t'], sc['rot'], sc['min_margin'])['C']
            print('   real C', real, flush=True)
            if real >= best_c - 0.05:
                continue
            best_c = real
            step = os.path.join(outdir, f'step{rnd}.kmx')
            os.replace(r['path'], step)
            with open(step, encoding='utf-8') as f, open(cur, 'w', encoding='utf-8') as g:
                g.write(f.read())
            log.append(dict(round=rnd, line=r['line'], raw=r['raw'], c=sc['min_margin'], C=real))
            json.dump(log, open(os.path.join(outdir, 'log.json'), 'w'), indent=1)
            accepted = True
            print(f'ACCEPT round {rnd} {r["raw"]} C {real} margin {sc["min_margin"]} ({time.time() - t0:.0f}s)', flush=True)
            break
        for fn in os.listdir(outdir):
            if fn.startswith('cand_'):
                os.remove(os.path.join(outdir, fn))
        if not accepted:
            print('no further acceptable deletion', flush=True)
            break
    print('final C', best_c, flush=True)


if __name__ == '__main__':
    main()
