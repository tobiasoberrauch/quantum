"""Diagnose the 50% phase mismatch: is sim_phase == 1-exp (sign flip)?
Correlated with syndrome/M parity? Print per-shot table."""
import importlib.util
import sys
import numpy as np

sys.path.insert(0, '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/work/dqi_t_sprint')
from sim3 import Sim, sample_shots, to_bits, initial_seed, make_batches, field_tables

ROOT = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum'
KMB = f'{ROOT}/work/frontier_scan/mwa_unpacked/dqi.kmb'
import hashlib
h = hashlib.sha256()
with open(KMB, 'rb') as f:
    for chunk in iter(lambda: f.read(1 << 22), b''):
        h.update(chunk)
chash = h.hexdigest()
sim = Sim(KMB)
base_seed = initial_seed(chash)
batches = make_batches(base_seed, 1)
rng_seed, sim_seed = batches[0]
rng = np.random.default_rng(rng_seed)
m, n, degree, r = 4095, 70, 12, 2016
synd, mbuc, phases, weights = sample_shots(m, n, degree, r, 32, rng)
sb = to_bits(synd, degree).astype(np.uint32)
mb = to_bits(mbuc, degree).astype(np.uint32)
res = sim.run_batch(sb, mb, None, 'zero')
PH = res['PH']
exp = phases.astype(np.uint32)
print('shot wt  exp sim  sim^exp  sim==(1^exp)  synParity  mParity')
for s in range(32):
    synpar = int(sb[:, s].sum()) & 1
    mpar = int(mb[:, s].sum()) & 1
    print(f'{s:4d} {weights[s]:3d}  {exp[s]}   {PH[s]}   {PH[s]^exp[s]}      {int(PH[s]==(1^exp[s]))}        {synpar}         {mpar}')
print('\nsim==exp count:', int((PH == exp).sum()))
print('sim==1^exp count:', int((PH == (1 ^ exp)).sum()))
# correlation of (sim^exp) with synParity / mParity
d = PH ^ exp
sp = np.array([int(sb[:, s].sum()) & 1 for s in range(32)])
mp = np.array([int(mb[:, s].sum()) & 1 for s in range(32)])
print('corr(d, synParity):', int((d == sp).sum()), '/32')
print('corr(d, mParity):', int((d == mp).sum()), '/32')
print('corr(d, synParity^mParity):', int((d == (sp ^ mp)).sum()), '/32')
sim.r.close()
