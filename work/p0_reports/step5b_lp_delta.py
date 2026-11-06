"""Step 5b: LP in delta-angle form (numerically stable).

Variables v = (da_1..da_41, c) in S-scaled units, da_j = a'_j - a_j.
Constraints per x:  err(x) + da.b(x) + c <= tol(x)   and   -err(x) - da.b(x) + c <= tol(x)
All quantities O(tol) <= 2^40 -> no catastrophic cancellation. Sparse A_ub.
"""
import sys, json, time
import numpy as np
sys.path.insert(0, 'data/verifiers/invsqrt')
import verify_submission_invsqrt as V
from scipy.optimize import linprog
import scipy.sparse as sp

U64, I64 = np.uint64, np.int64
OUT = 'work/p0_reports/data'
N = 3 * (2**10 - 2)**2

spec = V.ProblemSpecInvSqrt.for_n_p(10, shots_per_x=1)
xs = np.arange(1, N + 1, dtype=U64)
target, tol = V.reference_values(spec, xs)
tolF = tol.astype(np.float64)
err = np.load(f'{OUT}/err_orig.npy').astype(np.float64)
B = np.stack([np.load(f'{OUT}/bcols/col_{j:02d}.npy') for j in range(41)], axis=1)

S = 2.0**20
errS = err / S
tolS = tolF / S

# sparse A_ub: 2N rows x 42 cols  (+side rows 0..N-1, -side rows N..2N-1); skip zeros
rl, cl, vl = [], [], []
tot_ones = 0
for j in range(41):
    idx = np.flatnonzero(B[:, j])
    tot_ones += len(idx)
    rl += [idx, idx + N]
    cl += [np.full(len(idx), j), np.full(len(idx), j)]
    vl += [np.ones(len(idx)), -np.ones(len(idx))]
rl += [np.arange(2 * N)]
cl += [np.full(2 * N, 41)]
vl += [np.ones(2 * N)]
print('total B ones:', tot_ones, 'nnz:', 2 * tot_ones + 2 * N)
A_ub = sp.coo_matrix((np.concatenate(vl), (np.concatenate(rl), np.concatenate(cl))),
                     shape=(2 * N, 42)).tocsr()
b_ub = np.concatenate([tolS - errS, tolS + errS])
cvec = np.zeros(42); cvec[41] = -1.0
half = 0.25 * 2**64 / S
bounds = [(-half, half)] * 41 + [(0.0, float(tolS.max()))]
t0 = time.time()
res = linprog(cvec, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
print('LP status:', res.status, res.message, f'{time.time()-t0:.0f}s')
if res.status == 0:
    c_opt = res.x[41] * S
    print(f'c_optimal (current controls) = {c_opt:.1f} units of 2^-64 turns (current: 58597850)')
    da = res.x[:41] * S
    err_new = np.round(err + B @ da)
    margin_new = tol.astype(np.int64) - np.abs(err_new).astype(np.int64)
    print('achieved min margin (rounded):', int(margin_new.min()), 'at x=', int(xs[margin_new.argmin()])+1)
    print('worst ratio:', float((np.abs(err_new).astype(np.float64) / tolF).max()))
    # how many active constraints at optimum
    act = (np.abs(err_new).astype(np.float64) >= tolF - c_opt - 1000).sum()
    print('active-ish x count (within 1000 units of ceiling):', int(act))
    json.dump({'c_opt': float(c_opt), 'lp_status': int(res.status),
               'da_units': [float(v) for v in da],
               'achieved_min_margin_rounded': int(margin_new.min()),
               'worst_ratio': float((np.abs(err_new).astype(np.float64) / tolF).max())},
              open(f'{OUT}/lp_result.json', 'w'), indent=1)
else:
    print('LP failed')
