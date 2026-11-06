#!/usr/bin/env python3
"""Official verifier at default salt, two other salts, and 256 shots per address (robustness, not selection)."""
import hashlib, json, os, sys
sys.path.insert(0, '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/data/verifiers')
from dfthcsos import verify as v
d = sys.argv[1]
out = []
for salt, sh in (('notebook-verification', 64), ('', 64), ('robust-a', 64), ('robust-b', 256)):
    r = v.verify(d, salt=salt, shots_per_address=sh)
    out.append(dict(salt=salt, shots=sh, status=r['status'], score=r['score'], ratio=3355599588.3155375 / r['score'], T=r['toffoli_count'], Q=r['num_qubits'], lam=r['metrics']['lambda_eff'], e1=r['metrics']['error_1'], e2=r['metrics']['error_2'], Egap=r['metrics']['E_gap'], sha=r['submission_sha256']))
    print(json.dumps(out[-1]), flush=True)
json.dump(out, open(sys.argv[2], 'w'), indent=1)
