import sys, numpy as np, random, time, collections
sys.path.insert(0, 'scripts')
import planner as P, extract_plan as ep, replan as rp, padfill
base, k, part, secs = sys.argv[1], int(sys.argv[2]), sys.argv[3], float(sys.argv[4])
nq = int(sys.argv[5]) if len(sys.argv) > 5 else 5
seed = int(sys.argv[6]) if len(sys.argv) > 6 else 0
words = np.load(base + '/submission.npz')['angle_words']
X, tie = ep.tensor_of_words(words, k)
X30 = X[:, :, rp.OUTS30]
rng = random.Random(seed)
basis = rp.partition_basis(part, rng)
Bm = np.array([[(v >> j) & 1 for j in range(15)] for pb in basis for v in pb], dtype=np.uint8)
Inv = P.gf2_inv(Bm)
Xf, sel = padfill.fill_padding(X30, Inv, list(range(nq)))
print('planes satisfied', sel)
planes = []
for t in range(5):
    coord = Inv[:, 3 * t:3 * t + 3].T.astype(bool)
    pl = P.Plane(P.plane_rows(Xf, coord), 30)
    pl.need = pl.rank
    planes.append(pl)
print('ranks', [p.rank for p in planes], 'ann', [len(p.ann) for p in planes])
c = P.cand_pairs(planes, 30)
print('cands', len(c), collections.Counter((c_[0], c_[2]) for c_ in c).most_common(20))
ch, ech, best = P.search(planes, 30, c, secs, seed=seed, log=print)
print('final', best, 'pairs', len(ch), [len(e) for e in ech])
