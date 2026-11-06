import sys, numpy as np, random, time, collections
sys.path.insert(0, 'scripts')
import planner as P, tensor_probe as tp, extract_plan as ep, triples
base, k, partfn, secs = sys.argv[1], int(sys.argv[2]), sys.argv[3], float(sys.argv[4])
words = np.load(base + '/submission.npz')['angle_words']
X, tie = ep.tensor_of_words(words, k)
print('tie', tie)
# 30 non-LSB outputs (bits 1..6 of each word)
outs = [8 * j + b for j in range(5) for b in range(1, 7)]
X30 = X[:, :, outs]
O = 30
# planes
if partfn != 'random':
    _, planes_b, _, _ = triples.triples_of(partfn)
    rng = random.Random(0)
    # basis of each plane; b bits: i -> z=i+1
    basis = []
    for pl in planes_b:
        pb = []
        piv = {}
        for x in pl:
            r = P.reduce_v(x, piv)
            if r:
                piv[r.bit_length() - 1] = r
                pb.append(x)
        basis.append(pb)
else:
    rng = random.Random(1)
    while True:
        B = np.array([[rng.random() < .5 for _ in range(15)] for _ in range(15)], dtype=np.uint8)
        try:
            P.gf2_inv(B); break
        except ValueError:
            pass
    basis = [[sum(int(B[3*t+i, j]) << j for j in range(15)) for i in range(3)] for t in range(5)]
Bm = np.array([[ (v >> j) & 1 for j in range(15)] for pb in basis for v in pb], dtype=np.uint8)  # rows: b vectors (15)
Inv = P.gf2_inv(Bm)
# x(z) = sum_coord c_i b_i(z)  => c = x @ Inv  (row vectors over z)
planes = []
for t in range(5):
    coord = Inv[:, 3 * t:3 * t + 3].T.astype(bool)  # (3,15): functional for c_i
    rows = P.plane_rows(X30, coord)
    pl = P.Plane(rows, O)
    pl.need = pl.rank
    planes.append(pl)
    print('plane', t, 'rank', pl.rank, 'ann', len(pl.ann), 'dimV', [O - len(pl.pivV[b]) for b in range(1, 8)])
cands = P.cand_pairs(planes, O)
print('cands', len(cands), collections.Counter(c[0] == c[2] for c in cands))
ch, ech, best = P.search(planes, O, cands, secs, log=print)
print('final', best, 'pairs', len(ch), 'filled', [len(e) for e in ech])
