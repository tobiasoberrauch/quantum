#!/usr/bin/env python3
"""Compare word tables of all npz vs v23; list those with identical angle data; report lambda from results."""
import io, json, lzma, sys, zipfile, glob, hashlib
import numpy as np
F = sys.argv[1]
cand = json.load(open(F + '/candidates.json'))['chem']
def read(loc):
    raw = zipfile.ZipFile(loc['path']).open(loc['inner']) if loc['inner'] is not None else open(loc['path'], 'rb')
    with (lzma.open(raw) if loc['xz'] else raw) as f:
        return f.read()
base = [k for k in cand if k.startswith('34d19b96538d')][0]
B = np.load(io.BytesIO(read(cand[base]['locs']['submission.npz'])), allow_pickle=False)
seen = {}
for key, c in cand.items():
    sha = c['members']['submission.npz']
    if sha in seen: continue
    N = np.load(io.BytesIO(read(c['locs']['submission.npz'])), allow_pickle=False)
    r = json.load(open(f'{F}/results/chem_{key}.json'))
    same = {}
    for a in ('angle_words', 'coded', 'coded2', 'codes', 'tree_edges', 'brot', 'U', 'H2_I', 'W'):
        same[a] = bool(a in N.files and a in B.files and N[a].shape == B[a].shape and np.array_equal(N[a], B[a]))
    seen[sha] = 1
    print(sha[:10], key[:12], round(r.get('lambda_eff') or 0, 6), r.get('toffoli_count'), r.get('num_qubits'), r['status'], 'WORDS_SAME' if same['angle_words'] else '-', {k: v for k, v in same.items() if k != 'angle_words'}, c['sources'][0][:40])
