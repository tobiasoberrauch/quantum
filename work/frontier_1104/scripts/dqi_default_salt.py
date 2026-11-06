#!/usr/bin/env python3
"""Robustness info only: finalist DQI at the verifier's default (empty) salt plus static gate counts."""
import json, lzma, os, sys, tempfile, zipfile, time
ROOT = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum'
F = ROOT + '/work/frontier_1104/frontier'
sys.path.insert(0, ROOT + '/data/verifiers')
import kickmix as km
from dqi import verify_submission_dqi as v
pref = sys.argv[1]
cand = json.load(open(F + '/candidates.json'))['dqi']
key = next(k for k in cand if k.startswith(pref)); loc = cand[key]['locs'][0]
raw = zipfile.ZipFile(loc['path']).open(loc['inner']) if loc['inner'] is not None else open(loc['path'], 'rb')
fi = lzma.open(raw) if loc['xz'] else raw
with tempfile.NamedTemporaryFile(suffix='.kmb', delete=False, dir=F + '/scratch') as t:
    for b in iter(lambda: fi.read(1 << 22), b''):
        t.write(b)
try:
    c = km.Circuit.from_file(t.name, format='kmb')
    st = c.operation_statistics()
    r = v.verify(c, v.ProblemSpecDQI.benchmark_instance(), salt='', max_workers=3)
finally:
    os.unlink(t.name)
keep = {k: x for k, x in r.items() if isinstance(x, (int, float, str, bool, type(None)))}
keep.update(key=key, static_toffoli_like=int(st.num_toffoli_like), static_instructions=int(st.num_instructions), ratio=24439463583672.93 / float(r['score']))
json.dump(keep, open(f'{F}/results_info_dqi_defaultsalt_{key[:12]}.json', 'w'), indent=1)
print({k: keep.get(k) for k in ('key', 'status', 'score', 'ratio', 'value_errors', 'phase_errors', 'repetition_factor', 'toffoli_count', 'max_toffoli_count', 'static_toffoli_like', 'static_instructions')})
