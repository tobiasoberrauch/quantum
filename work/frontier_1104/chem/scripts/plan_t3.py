import sys, numpy as np, random, time, collections, os, contextlib, io
sys.path.insert(0, 'scripts')
import planner as P, extract_plan as ep, replan as rp, padfill, lu
base, k, part, secs, nlu, seed = sys.argv[1], int(sys.argv[2]), sys.argv[3], float(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])
words = np.load(base + '/submission.npz')['angle_words']
X, tie = ep.tensor_of_words(words, k)
X30 = X[:, :, rp.OUTS30].copy()
rng = random.Random(seed)
basis = rp.partition_basis(part, rng)
Bm = np.array([[(v >> j) & 1 for j in range(15)] for pb in basis for v in pb], dtype=np.uint8)
Inv = P.gf2_inv(Bm)
terms = [(int(p), int(a_, 16), int(b, 16), int(s, 16)) for p, a_, b, s in (l.split() for l in open(f'runs/rp1/plan_{k}.txt'))]
byp = collections.defaultdict(list)
for t in terms: byp[t[0]].append(t)
L = sum(1 << (8*j) for j in range(5))
lsb = [ts for ts in byp.values() if ts[0][3] & L]
print('lsb products', len(lsb))
ok = 0
rng.shuffle(lsb)
used = []
for ts in lsb:
    if ok >= nlu or len(ts) < 2: continue
    (_, a1, b1, s), (_, a2, b2, _) = ts
    p1, p2 = lu.b_to_plane(b1, Inv), lu.b_to_plane(b2, Inv)
    if p1 is None or p2 is None or p1[0] == p2[0]:
        print('skip', p1, p2); continue
    c1 = Inv[:, 3*p1[0]:3*p1[0]+3].T.astype(bool); c2 = Inv[:, 3*p2[0]:3*p2[0]+3].T.astype(bool)
    r1 = P.plane_rows(X30[:75], c1); r2 = P.plane_rows(X30[:75], c2)
    x = lu.find_x(r1, r2, p1[1], p2[1], a1 & ((1<<75)-1), a2 & ((1<<75)-1), 30, rng)
    print('product', ts[0][0], 'planes', p1, p2, 'x', None if x is None else bin(x).count('1'))
    if x is None: continue
    lu.apply_ext(X30, a1, b1, x); lu.apply_ext(X30, a2, b2, x)
    used.append((ts[0][0], x)); ok += 1
print('applied', ok)
Xf, sel = padfill.fill_padding(X30, Inv, list(range(5)))
print('padding planes', sel)
planes = []
for t in range(5):
    coord = Inv[:, 3*t:3*t+3].T.astype(bool)
    pl = P.Plane(P.plane_rows(Xf, coord), 30); pl.need = pl.rank; planes.append(pl)
print('ranks', [p.rank for p in planes])
c = P.cand_pairs(planes, 30)
print('cands', len(c))
ch, ech, best = P.search(planes, 30, c, secs, seed=seed, log=print)
print('final', best, 'pairs', len(ch), [len(e) for e in ech], 'total with lsb', best[0] + len(lsb))
