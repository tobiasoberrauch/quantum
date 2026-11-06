import collections, sys
fn = sys.argv[1]
terms = [(int(p), int(a, 16), int(b, 16), int(s, 16)) for p, a, b, s in (l.split() for l in open(fn))]
cb = collections.Counter(t[2] for t in terms)
print('unique b', len(cb))
for b, n in sorted(cb.items(), key=lambda kv: kv[0]):
    print(format(b, '015b'), n)
pairs = collections.Counter()
prods = collections.defaultdict(list)
for t in terms: prods[t[0]].append(t)
LSB = sum(1 << (8 * j) for j in range(5))
same = 0; cross = collections.Counter()
for p, ts in prods.items():
    if len(ts) == 2:
        pairs[(ts[0][2] ^ ts[1][2]) == 0] += 1
print(pairs)
print('LSB-only products', sum(1 for p, ts in prods.items() if ts[0][3] & ~LSB == 0), 'mixed', sum(1 for p, ts in prods.items() if ts[0][3] & LSB and ts[0][3] & ~LSB))
