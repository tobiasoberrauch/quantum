"""Step 8: joint LP with ALL candidate controls at once (span test) + greedy forward selection.

If c* with {41 current + 39 candidates} ~= 58.6M, the candidates add nothing (in-span).
Greedy: repeatedly add the candidate with largest marginal c gain (full re-solve each step).
"""
import sys, json, time
import numpy as np
sys.path.insert(0, 'data/verifiers/invsqrt')
import verify_submission_invsqrt as V
from scipy.optimize import linprog

U64, I64 = np.uint64, np.int64
OUT = 'work/p0_reports/data'
N = 3 * (2**10 - 2)**2
spec = V.ProblemSpecInvSqrt.for_n_p(10, shots_per_x=1)
xs = np.arange(1, N + 1, dtype=U64).astype(np.int64)
target, tol = V.reference_values(spec, xs.astype(U64))
tolF = tol.astype(np.float64)
err = np.load(f'{OUT}/err_orig.npy').astype(np.float64)
B = np.stack([np.load(f'{OUT}/bcols/col_{j:02d}.npy') for j in range(41)], axis=1).astype(np.float64)
s_arr = np.load(f'{OUT}/s_arr.npy')
x_norm = xs << (2 * s_arr)
C0 = 58597852.7

def bitarr(v, k): return ((v >> k) & 1).astype(np.float64)

cands = {}
for i in range(22): cands[f'addr{i:02d}'] = bitarr(xs, i)
for k in range(4): cands[f'sbit{k}'] = bitarr(s_arr, k)
for k in range(7): cands[f'bkt{k}'] = bitarr(x_norm, 15 + k)
cands['case_top'] = bitarr(x_norm, 21)
cands['case_second'] = bitarr(x_norm, 20)
cands['case_third'] = bitarr(x_norm, 19)
# drop duplicates found in step6 (identical c): keep representatives
for dup in ['sbit0','sbit1','sbit2','sbit3','bkt5','bkt6','case_top','case_second']:
    cands.pop(dup)
names = list(cands.keys())
G = np.stack([cands[n] for n in names], axis=1)
print('candidates:', len(names), names, file=sys.stderr)

def cg_lp(Gextra, pool_init=None, verbose=False):
    """Gextra: (K, N) matrix of extra controls (float). Returns (c_opt, da, dg) or None."""
    K = Gextra.shape[1] if Gextra.ndim == 2 else 0
    M = 41 + K
    slack = tolF - np.abs(err)
    pool = np.argsort(slack)[:4000] if pool_init is None else np.array(pool_init)
    sol = None
    for it in range(80):
        rows = len(pool)
        A = np.zeros((2 * rows, M + 1))
        A[:rows, :41] = B[pool]
        if K: A[:rows, 41:M] = Gextra[pool]
        A[rows:, :41] = -B[pool]
        if K: A[rows:, 41:M] = -Gextra[pool]
        A[:, M] = 1.0
        b = np.concatenate([tolF[pool] - err[pool], tolF[pool] + err[pool]])
        cvec = np.zeros(M + 1); cvec[M] = -1.0
        half = 0.25 * 2**64
        bounds = [(-half, half)] * M + [(0.0, float(tolF.max()))]
        res = linprog(cvec, A_ub=A, b_ub=b, bounds=bounds, method='highs')
        if res.status != 0:
            return None
        c = res.x[M]
        pred = err + B @ res.x[:41]
        if K: pred = pred + Gextra @ res.x[41:M]
        viol = np.flatnonzero(tolF - np.abs(pred) < c - 1.0)
        if len(viol) == 0:
            if verbose: print(f'  converged it={it} pool={rows} c={c:.1f}', file=sys.stderr)
            return c, res.x[:41], res.x[41:M]
        sl = tolF[viol] - np.abs(pred[viol])
        order = viol[np.argsort(sl)][:2000]
        pool = np.unique(np.concatenate([pool, order]))
        if verbose: print(f'  it={it} pool={rows} viol={len(viol)} c={c:.1f}', file=sys.stderr)
    return None

# ---- 1) joint span test ------------------------------------------------------
t0 = time.time()
r = cg_lp(G, verbose=True)
if r:
    c_joint = r[0]
    print(f'JOINT c* = {c_joint:.1f} (baseline {C0}) gain={c_joint-C0:.1f} '
          f'({(c_joint/C0-1)*100:.3f}%)  {time.time()-t0:.0f}s', file=sys.stderr)
    dg = r[2]
    top = sorted(zip(names, dg), key=lambda t: -abs(t[1]))[:10]
    print('top |dg|:', [(n, float(d)) for n, d in top], file=sys.stderr)
else:
    print('JOINT failed', file=sys.stderr)
    c_joint = None

# ---- 2) greedy forward selection --------------------------------------------
selected = []
c_prev = C0
greedy = []
t0 = time.time()
for round_i in range(6):
    best = None
    for n in names:
        if n in selected: continue
        Gsel = np.stack([cands[m] for m in selected + [n]], axis=1) if selected else cands[n][:, None]
        r = cg_lp(Gsel)
        if r is None: continue
        if best is None or r[0] > best[1]:
            best = (n, r[0])
    if best is None or best[1] <= c_prev + 100:
        print(f'round {round_i}: stop (best {best})', file=sys.stderr)
        break
    n, c_new = best
    selected.append(n)
    greedy.append({'name': n, 'c': float(c_new), 'gain': float(c_new - c_prev)})
    c_prev = c_new
    print(f'round {round_i}: +{n} -> c={c_new:.1f} (gain {c_new-c_prev:+.1f}) '
          f'{time.time()-t0:.0f}s', file=sys.stderr)

json.dump({'joint_c': c_joint, 'greedy': greedy}, open(f'{OUT}/step8_greedy.json', 'w'), indent=1)
print('done', file=sys.stderr)
