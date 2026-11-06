#!/usr/bin/env python3
"""usage: lpcand.py base.kmx deltest.jsonl line[,line...]  -> deletion edits + full-domain LP refit report."""
import json, sys
import numpy as np
import bsim, edit, lpfit
src, recs, lines = sys.argv[1], sys.argv[2], [int(v) for v in sys.argv[3].split(',')]
R = {r['line']: r for r in (json.loads(l) for l in open(recs))}
txt = open(src).read().splitlines()
e = {}
for l in lines:
    e = edit.merge(e, edit.edits_from_deletion(R[l]))
    print('del', l, R[l]['raw'], 'npatch', R[l].get('npatch'))
out = edit.apply(txt, e)
import os; tmp = bsim.LANE + f'/runs/lpcand_tmp{os.getpid()}.kmx'
open(tmp, 'w').write('\n'.join(out) + '\n')
ops, _ = bsim.parse_kmx(tmp)
xs = bsim.domain()
a0, b, meta, s, tol = lpfit.extract(ops, xs, seed=6)
ang = lpfit.angles_units(meta)
r = bsim.check(s)
print('restored', r['restored'], 'dirty', r['dirty_qubits'], 'tof', s.tof / s.n, 't', s.t / s.n)
m0 = (tol.astype(np.float64) - np.abs((a0 + (b.T.astype(np.int64) @ np.rint(ang).astype(np.int64))).astype(np.float64))).min()
print('margin before refit', m0, 'fails', int((tol.astype(np.float64) - np.abs((a0 + (b.T.astype(np.int64) @ np.rint(ang).astype(np.int64))).astype(np.float64)) < 0).sum()))
aa, c = lpfit.fit(a0, b, tol, ang)
print('LP c', c, bsim.cost(62, s.tof / s.n, s.t / s.n, s.rot / s.n, max(c, 1)))
os.remove(tmp); print('RESULT', lines, c, bsim.cost(62, s.tof / s.n, s.t / s.n, s.rot / s.n, max(c, 1))['C'], flush=True)
