#!/usr/bin/env python3
"""Per-loader Toffoli/qubit stats for all chem candidates, grouped by submission.npz word tables."""
import hashlib, io, json, lzma, sys, zipfile
import numpy as np
import kickmix as km
cand = json.load(open(sys.argv[1]))['chem']
res = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else {}

def read(loc):
    raw = zipfile.ZipFile(loc['path']).open(loc['inner']) if loc['inner'] is not None else open(loc['path'], 'rb')
    with (lzma.open(raw) if loc['xz'] else raw) as f:
        return f.read()

out = {}
for key, c in cand.items():
    rec = {'sources': c['sources'][:2], 'loaders': {}}
    npz = np.load(io.BytesIO(read(c['locs']['submission.npz'])), allow_pickle=False)
    rec['npz_keys'] = sorted(npz.files)
    for k in c['locs']:
        if k == 'submission.npz':
            continue
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix='.kmb', delete=False, dir=sys.argv[2]) as t:
            t.write(read(c['locs'][k])); p = t.name
        circ = km.Circuit.from_file(p, format='kmb' if k.endswith('kmb') else 'kmx')
        os.unlink(p)
        st = circ.operation_statistics()
        rec['loaders'][k] = {'ccx': int(st.get('CCX', 0) + st.get('CCZ', 0)), 'q': int(circ.num_qubits), 'sha': c['members'][k][:12]}
    out[key] = rec
    print(key[:12], len(rec['loaders']), sum(v['ccx'] for v in rec['loaders'].values()), flush=True)
json.dump(out, open(sys.argv[2] + '/loader_stats.json', 'w'), indent=1)
