#!/usr/bin/env python3
"""Official chem verifier on a member dir; prints ratio. Usage: vfy.py <dir> [salt]."""
import json, sys, time
REPO = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum'
sys.path.insert(0, REPO + '/data/verifiers')
from dfthcsos import verify as v
REF = 3355599588.3155375
d = sys.argv[1]
salt = sys.argv[2] if len(sys.argv) > 2 else 'notebook-verification'
t = time.time()
r = v.verify(d, salt=salt)
m = r['metrics']; rs = r['resources']
out = dict(status=r['status'], score=r['score'], ratio=REF / r['score'], lambda_eff=m['lambda_eff'], Lambda=m['Lambda'],
           E_gap=m['E_gap'], error_1=m['error_1'], error_2=m['error_2'], T=r['toffoli_count'], Q=r['num_qubits'],
           angT=rs['angles_toffoli'], heurT=rs['heuristic_toffoli'], outer=rs['outer_state_prep_toffoli'],
           inner=rs['inner_state_prep_toffoli'], giv=rs['givens_rotations_toffoli'], persistent=rs['persistent_qubits'],
           temp=rs['temporary_qubits'], angQ=rs['angles_qubits'], heur_temp=rs['heuristic_temporary_qubits'],
           ang_temp=rs['angles_temporary_qubits'], sha=r['submission_sha256'], secs=round(time.time() - t, 1))
print(json.dumps(out, indent=1))
