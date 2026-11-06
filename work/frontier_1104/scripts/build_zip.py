#!/usr/bin/env python3
"""Build frontier/build/submission.zip by streaming members from their located bytes.
Member order matches work/qvc008/extracted.json; ZIP_DEFLATED; no intermediate DQI file."""
import hashlib, json, lzma, os, sys, zipfile
B = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/work'
F = B + '/frontier_1104/frontier'
PICK = {'invsqrt': sys.argv[1], 'dqi': sys.argv[2], 'chem': sys.argv[3]}
cand = json.load(open(F + '/candidates.json'))
mix = json.load(open(F + '/candidates_mix.json'))
def get(comp, pref):
    for src in (cand[comp], mix.get(comp, {})):
        for k, v in src.items():
            if k.startswith(pref):
                return k, v
    raise SystemExit(f'no candidate {comp} {pref}')
def open_loc(loc):
    raw = zipfile.ZipFile(loc['path']).open(loc['inner']) if loc['inner'] is not None else open(loc['path'], 'rb')
    return lzma.open(raw) if loc['xz'] else raw
order = [it['file'] for it in json.load(open(B + '/qvc008/extracted.json'))['files']]
ik, iv = get('invsqrt', PICK['invsqrt']); dk, dv = get('dqi', PICK['dqi']); ck, cv = get('chem', PICK['chem'])
def locate(name):
    if name == 'invsqrt.kmb': return iv['locs'][0], ik
    if name == 'dqi.kmb': return dv['locs'][0], dk
    base = name.split('/', 1)[1]
    return cv['locs'][base], cv['members'][base]
out = F + '/build/submission.zip'
if os.path.exists(out): os.remove(out)
members = {}
with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    for name in order:
        loc, want = locate(name)
        h = hashlib.sha256(); n = 0
        with open_loc(loc) as fi, z.open(name, 'w', force_zip64=True) as fo:
            while True:
                b = fi.read(1 << 22)
                if not b: break
                h.update(b); fo.write(b); n += len(b)
        if h.hexdigest() != want: raise SystemExit(f'SHA MISMATCH {name}')
        members[name] = {'sha256': want, 'size': n}
        print(f'{name:32s} {want} {n}')
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None
    names = [n for n in z.namelist() if not n.endswith('/')]
    assert names == order and len(names) == 18, names
json.dump({'invsqrt': ik, 'dqi': dk, 'chem': ck, 'members': members}, open(F + '/build/build_manifest.json', 'w'), indent=1)
print('wrote', out, os.path.getsize(out))
