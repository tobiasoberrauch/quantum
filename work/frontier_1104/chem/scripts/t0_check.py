import sys, time, numpy as np
sys.path.insert(0, '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/work/frontier_1104/chem/scripts')
import wcore
base = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/work/frontier_1104/chem/base/submission.npz'
ref = wcore.load_ref()
t = time.time(); eng, w, wB = wcore.load_engine(base, ref=ref); print('load', time.time() - t)
print('mine', eng.metrics(w, wB))
print('official', wcore.official_metrics(base, w, wB, ref))
t = time.time()
for _ in range(10): eng.e2sq(w)
print('e2sq per call', (time.time() - t) / 10)
# grad check
v, g = eng.e2sq(w)
rng = np.random.default_rng(0); dw = rng.normal(size=w.shape) * 1e-6
vp, _ = eng.e2sq(w + dw); vm, _ = eng.e2sq(w - dw)
print('fd', (vp - vm) / 2, 'an', np.sum(g * dw))
sv = [np.linalg.svd(w[r], compute_uv=False) for r in range(8)]
for r in range(8): print(r, 'sv head', np.round(sv[r][:3], 3), 'tail', np.round(sv[r][-5:], 4))
print('wB zeros', (wB == 0).mean(), 'wB |<1e-6|', (np.abs(wB) < 1e-6).mean(), 'w zeros', (w == 0).mean())
print('column L1 sum sq head', np.sort(0.25 * ((np.abs(w).sum(1) + np.abs(wB)) ** 2).ravel())[:10])
