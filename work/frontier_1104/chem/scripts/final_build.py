#!/usr/bin/env python3
"""Assemble final member dir from runs/bestT loaders + the lowest feasible weights; print weights used."""
import glob, os, shutil, subprocess, sys
import numpy as np
ROOT = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/work/frontier_1104/chem'
out = sys.argv[1]
cands = glob.glob(ROOT + '/runs/stage*/best.npz') + [ROOT + '/runs/refit45/best.npz']
best, bl = None, 1e9
for c in cands:
    d = np.load(c)
    if float(d['e2']) <= 0.0199999999 and float(d['e1']) <= 0.0199999999 and float(d['Egap']) > 3.914898 and float(d['lam_eff']) < bl:
        best, bl = c, float(d['lam_eff'])
print('weights', best, bl)
os.makedirs(out, exist_ok=True)
subprocess.check_call([sys.executable, ROOT + '/scripts/make_member.py', ROOT + '/base', best, out])
for f in glob.glob(ROOT + '/runs/bestT/angle_k_*.kmb'):
    shutil.copy2(f, out)
print(sorted(os.listdir(out)))
