#!/usr/bin/env python3
"""Structure of a plan_k.txt: output direction supports grouped; a-space/b-space stats."""
import collections, sys
fn = sys.argv[1]
T = [l.split() for l in open(fn)]
terms = [(int(p), int(a, 16), int(b, 16), int(s, 16)) for p, a, b, s in T]
prods = collections.defaultdict(list)
for t in terms:
    prods[t[0]].append(t)
def outs(s):
    return [i for i in range(40) if s >> i & 1]
sup = collections.Counter()
for p, ts in prods.items():
    s = ts[0][3]
    o = [i for i in outs(s) if i % 8 != 7]
    sup[tuple(sorted(o))] += 1
# connected components of outputs over products
parent = {i: i for i in range(40) if i % 8 != 7}
def f(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]; x = parent[x]
    return x
for o in sup:
    for x in o[1:]:
        parent[f(x)] = f(o[0])
comps = collections.defaultdict(list)
for i in parent: comps[f(i)].append(i)
print('n products', len(prods), 'components', [sorted(c) for c in comps.values()])
print('support size hist', sorted(collections.Counter(len(o) for o, n in sup.items() for _ in range(n)).items()))
first = collections.Counter()
for o, n in sup.items():
    first[min(o) if o else -1] += n
print('first-output hist', sorted(first.items()))
print('rows (product count, top) by exact support top10', sup.most_common(10))
