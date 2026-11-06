#!/usr/bin/env python3
"""Verify every not-yet-verified candidate, respecting a 6-process budget:
2 heavy slots (3 workers each, invsqrt/dqi), then chem with 6 single-process slots."""
import json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
ROOT = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum'
PY = ROOT + '/.venv/bin/python'
B = ROOT + '/work/frontier_1104'
F = B + '/frontier'

def run(job):
    comp, key = job
    env = dict(os.environ, VQ_WORKERS='3')
    p = subprocess.run([PY, B + '/scripts/verify_one.py', comp, key, F + '/candidates.json', F + '/results', F + '/scratch'],
                       capture_output=True, text=True, env=env, cwd='/tmp')
    line = (p.stdout.strip().splitlines() or [''])[-1]
    print(line[:400] if p.returncode == 0 else f'FAIL {comp} {key[:12]} {p.stderr[-400:]}', flush=True)

def main():
    want = sys.argv[1:] or ['chem', 'invsqrt', 'dqi']
    cand = json.load(open(F + '/candidates.json'))
    todo = lambda c: [(c, k) for k in cand[c] if not os.path.exists(f'{F}/results/{c}_{k}.json')]
    if 'chem' in want:
        with ThreadPoolExecutor(6) as ex:
            list(ex.map(run, todo('chem')))
    heavy = []
    for c in ('invsqrt', 'dqi'):
        if c in want:
            heavy += todo(c)
    with ThreadPoolExecutor(2) as ex:
        list(ex.map(run, heavy))
    print('VERIFY-DONE', flush=True)
main()
