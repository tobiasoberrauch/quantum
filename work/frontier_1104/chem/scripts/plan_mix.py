import collections, sys
sys.path.insert(0,'scripts')
import triples
fn = sys.argv[1]
terms = [(int(p), int(a, 16), int(b, 16), int(s, 16)) for p, a, b, s in (l.split() for l in open(fn))]
bs, planes, tot, rest = triples.triples_of(fn)
pl = {}
for i, P in enumerate(planes):
    for x in P: pl[x] = i
L = sum(1 << (8*j) for j in range(5)); U = sum(((1<<7)-2) << (8*j) for j in range(5))
stat = collections.defaultdict(collections.Counter)
pairs = collections.Counter()
by = collections.defaultdict(list)
for t in terms: by[t[0]].append(t)
for p, ts in by.items():
    s = ts[0][3]
    kind = ('L' if s & L else '') + ('U' if s & U else '')
    if len(ts)==2:
        pa=tuple(sorted((pl.get(ts[0][2],-1),pl.get(ts[1][2],-1))))
        pairs[pa]+=1
    for t in ts:
        stat[pl.get(t[2],-1)][kind]+=1
print('tot', tot, 'unique b', len(bs))
for k in sorted(stat): print('plane',k,dict(stat[k]))
print('pair planes', sorted(pairs.items()))
print('LSB s patterns', collections.Counter(bin(ts[0][3] & L).count('1') for ts in by.values() if ts[0][3]&L))
