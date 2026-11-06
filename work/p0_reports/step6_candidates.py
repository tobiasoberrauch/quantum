"""Step 6: marginal value of ADDITIONAL phase-tap controls.

For each candidate Boolean control g(x), solve the augmented minimax LP
    max c  s.t.  |err(x) + sum_j da_j b_j(x) + dg*g(x)| <= tol(x) - c
via constraint generation (pool of tight constraints, separation over full domain).
Greedy forward selection over the best candidates follows.

Cost model per added rotation (n_rot 41 -> 42, ...):
  rot_T(n, c) = n * (0.56*log2(2^64*n/(pi*c)) + 5.3)   [T-equivalents]
  C delta = dToffoli_exec + (rot_T(n+1,c') - rot_T(n,c))/4
"""
import sys, json, time, math
import numpy as np
sys.path.insert(0, 'data/verifiers/invsqrt')
import verify_submission_invsqrt as V
from scipy.optimize import linprog

U64, I64 = np.uint64, np.int64
OUT = 'work/p0_reports/data'
N = 3 * (2**10 - 2)**2
spec = V.ProblemSpecInvSqrt.for_n_p(10, shots_per_x=1)
xs = np.arange(1, N + 1, dtype=U64)
target, tol = V.reference_values(spec, xs)
tolF = tol.astype(np.float64)
err = np.load(f'{OUT}/err_orig.npy').astype(np.float64)
B = np.stack([np.load(f'{OUT}/bcols/col_{j:02d}.npy') for j in range(41)], axis=1).astype(np.float64)
C0 = 58597850.0

def rot_T(n, c):
    eps = math.pi * c / 2**64 / n
    return n * (0.56 * math.log2(1 / eps) + 5.3)

def cg_lp(extra_cols, pool_init=None, verbose=False):
    """Constraint-generation LP. extra_cols: list of (name, g_array_float). Returns c_opt, coeffs."""
    K = len(extra_cols)
    G = np.stack([g for _, g in extra_cols], axis=1).astype(np.float64) if K else None
    M = 41 + K
    if pool_init is None:
        slack = tolF - np.abs(err)
        pool = np.argsort(slack)[:4000]
    else:
        pool = np.array(pool_init)
    for it in range(60):
        rows = len(pool)
        A = np.zeros((2 * rows, M + 1))
        A[:rows, :41] = B[pool]
        if K: A[:rows, 41:41+K] = G[pool]
        A[rows:, :41] = -B[pool]
        if K: A[rows:, 41:41+K] = -G[pool]
        A[:, M] = 1.0
        b = np.concatenate([tolF[pool] - err[pool], tolF[pool] + err[pool]])
        cvec = np.zeros(M + 1); cvec[M] = -1.0
        half = 0.25 * 2**64
        bounds = [(-half, half)] * M + [(0.0, float(tolF.max()))]
        res = linprog(cvec, A_ub=A, b_ub=b, bounds=bounds, method='highs')
        if res.status != 0:
            return None, res
        c = res.x[M]
        da = res.x[:41]
        dg = res.x[41:M]
        # separation: full-domain violation
        pred = err + B @ da
        if K: pred = pred + G @ dg
        viol = np.flatnonzero(tolF - np.abs(pred) < c - 1.0)
        if len(viol) == 0:
            if verbose: print(f'  converged it={it} pool={rows} c={c:.1f}')
            return c, res.x[:M]
        # add worst violators
        sl = tolF[viol] - np.abs(pred[viol])
        order = viol[np.argsort(sl)][:2000]
        pool = np.unique(np.concatenate([pool, order]))
        if verbose: print(f'  it={it} pool={rows} viol={len(viol)} c={c:.1f}')
    return None, 'max_iter'

# ---- candidate controls -----------------------------------------------------
def bitarr(v, k):
    return ((v >> k) & 1).astype(np.float64)

s_arr = np.load(f'{OUT}/s_arr.npy')
x_norm = xs.astype(np.int64) << (2 * s_arr.astype(np.int64))
cands = {}
for i in range(22):
    cands[f'addr{i:02d}'] = bitarr(xs.astype(np.int64), i)
for k in range(4):
    cands[f'sbit{k}'] = bitarr(s_arr, k)
for k in range(7):
    cands[f'bkt{k}'] = bitarr(x_norm, 15 + k)      # top 7 bits of x_norm (128 buckets of M)
cands['case_top'] = bitarr(x_norm, 21)
cands['case_second'] = bitarr(x_norm, 20)
cands['case_third'] = bitarr(x_norm, 19)

results = {}
t0 = time.time()
for name, g in cands.items():
    c_new, sol = cg_lp([(name, g)])
    if c_new is None:
        results[name] = {'status': str(sol)}
        continue
    f = c_new / C0
    # cost: 1 extra rotation, 0 extra executed Toffolis (control assumed free)
    dC = (rot_T(42, c_new) - rot_T(41, C0)) / 4
    net = -dC   # positive = saves Toffoli-equivalents overall
    results[name] = {'c': float(c_new), 'f': float(f), 'dC_free_ctrl': float(dC),
                     'net_free_ctrl': float(net)}
    print(f'{name:12s} c={c_new:12.1f} f={f:.4f} dC(rot repricing)={dC:+8.2f} cum={time.time()-t0:5.0f}s',
          file=sys.stderr)

json.dump(results, open(f'{OUT}/step6_candidates.json', 'w'), indent=1)
print('done', file=sys.stderr)
