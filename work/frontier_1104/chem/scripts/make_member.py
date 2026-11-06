#!/usr/bin/env python3
"""Write a member dir: base loaders + new weights in submission.npz (all other arrays byte-kept).
Usage: make_member.py <basedir> <weights.npz> <outdir>"""
import glob
import os
import shutil
import sys

import numpy as np

base, wf, out = sys.argv[1:4]
os.makedirs(out, exist_ok=True)
for f in glob.glob(base + '/angle_k_*.kmb'):
    shutil.copy2(f, out)
d = dict(np.load(base + '/submission.npz', allow_pickle=False))
w = np.load(wf)
assert d['W'].shape == w['w'].shape and d['H2_I'].shape == w['wB'].shape
d['W'] = w['w'].astype(np.float64)
d['H2_I'] = w['wB'].astype(np.float64)
if 'offset_W' in d:
    d['offset_W'] = d['H2_I'] - d['W'].sum(axis=1)
np.savez_compressed(out + '/submission.npz', **d)
print('wrote', out)
