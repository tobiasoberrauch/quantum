import sys, numpy as np, random, time, collections, os
sys.path.insert(0, 'scripts')
import planner as P, extract_plan as ep, replan as rp, padfill, lu, plan_exact as PE
base, k, part, nlu, seed = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
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
rng.shuffle(lsb)
ok = 0
for ts in lsb:
    if ok >= nlu or len(ts) < 2: continue
    (_, a1, b1, s), (_, a2, b2, _) = ts
    p1, p2 = lu.b_to_plane(b1, Inv), lu.b_to_plane(b2, Inv)
    if p1 is None or p2 is None or p1[0] == p2[0]: continue
    c1 = Inv[:, 3*p1[0]:3*p1[0]+3].T.astype(bool); c2 = Inv[:, 3*p2[0]:3*p2[0]+3].T.astype(bool)
    x = lu.find_x(P.plane_rows(X30[:75], c1), P.plane_rows(X30[:75], c2), p1[1], p2[1], a1 & ((1<<75)-1), a2 & ((1<<75)-1), 30, rng)
    if x is None: continue
    lu.apply_ext(X30, a1, b1, x); lu.apply_ext(X30, a2, b2, x); ok += 1
Xf, sel = padfill.fill_padding(X30, Inv, list(range(5)))
planes = []
for t in range(5):
    coord = Inv[:, 3*t:3*t+3].T.astype(bool)
    pl = P.Plane(P.plane_rows(Xf, coord), 30); pl.need = pl.rank; planes.append(pl)
cands = P.cand_pairs(planes, 30)
print('LU applied', ok, 'pad planes', sel, 'ranks', [p.rank for p in planes], 'cands', len(cands), flush=True)
t=time.time()
res = PE.solve(planes, cands, seed=seed, log=print)
if res: print('pairs', len(res[0]), 'singles', len(res[1]), 'products', len(res[0]) + len(res[1]), 'total', len(res[0]) + len(res[1]) + len(lsb), 'sec', round(time.time()-t))
