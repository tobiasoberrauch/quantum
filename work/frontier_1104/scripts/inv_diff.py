import json, sys, tempfile, os, zipfile, difflib
import kickmix as km
F = sys.argv[1]
c = json.load(open(F + '/candidates.json'))['invsqrt']
def load(p):
    k = next(x for x in c if x.startswith(p)); l = c[k]['locs'][0]
    raw = zipfile.ZipFile(l['path']).read(l['inner']) if l['inner'] else open(l['path'], 'rb').read()
    t = tempfile.NamedTemporaryFile(suffix='.kmb', delete=False); t.write(raw); t.close()
    circ = km.Circuit.from_file(t.name, format='kmb'); os.unlink(t.name)
    return circ
a, b = load('af4698478fba'), load('0104d1b44d73')
print(a.operation_statistics()); print(b.operation_statistics())
sa, sb = str(a).splitlines(), str(b).splitlines()
print(len(sa), len(sb))
for l in list(difflib.unified_diff(sa, sb, lineterm='', n=0))[:40]:
    print(l[:120])
