"""Min error_2 at fixed words for C=45 and truncated C (SVD per block + L-BFGS on e2^2)."""
import sys, time, numpy as np
from scipy.optimize import minimize
sys.path.insert(0, '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/work/frontier_1104/chem/scripts')
import wcore
base = sys.argv[1]
maxit = int(sys.argv[2])
ref = wcore.load_ref()
eng, w0, wB0 = wcore.load_engine(base, ref=ref)
R, B, C = w0.shape
def solve(w, tag):
    Cc = w.shape[2]
    e = wcore.Eng(R, B, Cc, eng.G, eng.A, eng.T2, eng.u2, eng.V1, eng.h1base, eng.ecore, eng.eta, eng.beta1, eng.E_up)
    def f(x):
        v, g = e.e2sq(x.reshape(w.shape)); return v * 1e6, g.ravel() * 1e6
    t = time.time()
    r = minimize(f, w.ravel(), jac=True, method='L-BFGS-B', options=dict(maxiter=maxit, maxcor=30, ftol=1e-14, gtol=1e-9, maxfun=maxit*2))
    print(tag, 'start e2 mHa', 1e3*np.sqrt(f(w.ravel())[0]*1e-6), 'end', 1e3*np.sqrt(r.fun*1e-6), 'nit', r.nit, 'sec', round(time.time()-t,1), flush=True)
    return r.x.reshape(w.shape)
w45 = solve(w0, 'C45')
np.save(sys.argv[3] + '/w_mine2_45.npy', w45)
for dC in (1, 2):
    ws = []
    for r in range(R):
        U, s, Vt = np.linalg.svd(w45[r], full_matrices=False)
        ws.append(U[:, :C-dC] * s[:C-dC])
    w = np.stack(ws)
    wt = solve(w, f'C{C-dC}')
    np.save(sys.argv[3] + f'/w_mine2_{C-dC}.npy', wt)
