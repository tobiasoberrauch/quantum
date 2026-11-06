#!/usr/bin/env python3
"""Group chem candidates by angle word-table; list loader sums and lambda for sets >= threshold; per-k minima by family."""
import hashlib, io, json, lzma, os, sys, tempfile, zipfile
import numpy as np
import kickmix as km
F = sys.argv[1]; TH = float(sys.argv[2])
cand = json.load(open(F + '/candidates.json'))['chem']
def read(loc):
    raw = zipfile.ZipFile(loc['path']).open(loc['inner']) if loc['inner'] is not None else open(loc['path'], 'rb')
    with (lzma.open(raw) if loc['xz'] else raw) as f:
        return f.read()
fam = {}
for key, c in cand.items():
    p = f'{F}/results/chem_{key}.json'
    if not os.path.exists(p): continue
    r = json.load(open(p))
    if (r.get('ratio') or 0) < TH: continue
    N = np.load(io.BytesIO(read(c['locs']['submission.npz'])), allow_pickle=False)
    w = hashlib.sha256(N['angle_words'].tobytes()).hexdigest()[:10]
    extra = {a: hashlib.sha256(N[a].tobytes()).hexdigest()[:6] for a in ('U', 'tree_edges', 'codes', 'coded', 'W') if a in N.files}
    loaders = {}
    for k in c['locs']:
        if k == 'submission.npz': continue
        with tempfile.NamedTemporaryFile(suffix='.kmb', delete=False, dir=F + '/scratch') as t:
            t.write(read(c['locs'][k])); pth = t.name
        circ = km.Circuit.from_file(pth, format='kmb'); os.unlink(pth)
        st = circ.operation_statistics()
        loaders[k] = {'t': int(st.num_toffoli_like), 'q': int(circ.num_qubits), 'sha': c['members'][k]}
    fam.setdefault(w, []).append({'key': key, 'ratio': r['ratio'], 'lam': r['lambda_eff'], 'T': r['toffoli_count'], 'Q': r['num_qubits'], 'npz': c['members']['submission.npz'], 'extra': extra, 'loaders': loaders, 'src': c['sources'][0], 'e1': None})
json.dump(fam, open(F + '/chem_families.json', 'w'), indent=1)
for w, rs in fam.items():
    print('FAM', w, len(rs))
    rs.sort(key=lambda x: -x['ratio'])
    for x in rs:
        print('  ', x['key'][:12], round(x['ratio'], 5), 'lam', round(x['lam'], 6), 'T', x['T'], 'Q', x['Q'], 'loaders', sum(v['t'] for v in x['loaders'].values()), 'maxq', max(v['q'] for v in x['loaders'].values()), x['extra'].get('U'), x['extra'].get('W'), x['npz'][:8], x['src'][:40])
    if len(rs) > 1:
        ks = sorted(rs[0]['loaders'], key=lambda s: int(s.split('_')[2].split('.')[0]))
        mins = [min(x['loaders'][k]['t'] for x in rs if k in x['loaders']) for k in ks]
        print('   per-k min', mins, sum(mins), 'best lam', min(x['lam'] for x in rs))
