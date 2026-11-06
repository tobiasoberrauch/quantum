#!/usr/bin/env python3
"""Random restart driver over coded loaders; keeps the cheapest verified-by-count loader per k in runs/bestT."""
from __future__ import annotations

import glob
import json
import os
import random
import shutil
import subprocess
import sys
import time

import kickmix as km

ROOT = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/work/frontier_1104/chem'
PY = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/.venv/bin/python'
BEST = ROOT + '/runs/bestT'
deadline = time.time() + float(sys.argv[1])
NP = int(sys.argv[2])
KS = [int(x) for x in sys.argv[3].split(',')]
os.makedirs(BEST, exist_ok=True)


def count(path):
    c = km.Circuit.from_file(path, format='kmb')
    return int(c.operation_statistics().num_toffoli_like), int(c.num_qubits)


def seed_best():
    best = {}
    for k in range(15):
        p = f'{ROOT}/base/angle_k_{k}.kmb'
        best[k] = (count(p)[0], p)
    for p in glob.glob(ROOT + '/runs/p35*/**/angle_k_*.kmb', recursive=True) + glob.glob(ROOT + '/runs/ptest*/**/angle_k_*.kmb', recursive=True) + glob.glob(ROOT + '/runs/rp1/angle_k_*.kmb') + glob.glob(BEST + '/angle_k_*.kmb'):
        k = int(os.path.basename(p).split('_')[2].split('.')[0])
        t, q = count(p)
        if q <= 128 and t < best[k][0]:
            best[k] = (t, p)
    for k, (t, p) in best.items():
        dst = f'{BEST}/angle_k_{k}.kmb'
        if os.path.abspath(p) != dst:
            shutil.copy2(p, dst)
    return {k: t for k, (t, p) in best.items()}


best = seed_best()
print('start best', best, flush=True)
running = []
rng = random.Random(int(time.time()))
specs = ['randlin:2', 'randlin:2', 'randlin', 'own']
n = 0
order = []
while time.time() < deadline or running:
    still = []
    for pr, k, out, logf, t0 in running:
        if pr.poll() is None:
            if time.time() - t0 > 220:
                pr.kill()
            still.append((pr, k, out, logf, t0))
            continue
        p = f'{out}/angle_k_{k}.kmb'
        if os.path.exists(p):
            t, q = count(p)
            if q <= 128 and t < best[k]:
                best[k] = t
                shutil.copy2(p, f'{BEST}/angle_k_{k}.kmb')
                print(f'{time.strftime("%H:%M:%S")} new best k{k} T={t}  {out}', flush=True)
        shutil.rmtree(out, ignore_errors=True)
    running = still
    if time.time() < deadline:
        while len(running) < NP:
            if not order:
                order = sorted(KS, key=lambda k: -best[k] + rng.random())
            k = order.pop(0)
            sp = rng.choice(specs)
            part = f'{ROOT}/runs/plans0bd8/plan_{k}.txt' if sp == 'own' else sp
            n += 1
            out = f'{ROOT}/runs/drv/{n}'
            os.makedirs(out, exist_ok=True)
            logf = open(out + '.log', 'w')
            env = dict(os.environ, OMP_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
            pr = subprocess.Popen([PY, ROOT + '/scripts/plan35.py', ROOT + '/base', str(k), part, out, '--tries', '90', '--seed', str(rng.randrange(1 << 30)), '--maxsteps', '10', '--tmax', '150'], stdout=logf, stderr=subprocess.STDOUT, env=env, cwd=ROOT)
            running.append((pr, k, out, logf, time.time()))
    time.sleep(1)
print('end best', best, sum(best.values()), flush=True)
json.dump(best, open(BEST + '/best.json', 'w'))
