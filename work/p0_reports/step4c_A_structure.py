"""Step 4c: structure of the reference-model base error A(x) in (M, s) coordinates.

M = x_norm / 2^20 in [1,4)  (rational, denom 2^20), s = (22 - bitlen(x))//2.
Checks: does A(x) = 2^-s * g(M) exactly? residual structure? where are A's extremes?
"""
import sys, json, math
import numpy as np
sys.path.insert(0, 'data/verifiers/invsqrt')
import verify_submission_invsqrt as V

U64, I64 = np.uint64, np.int64
N = 3 * (2**10 - 2)**2
xs = np.arange(1, N + 1, dtype=np.int64)
spec = V.ProblemSpecInvSqrt.for_n_p(10, shots_per_x=1)
target, tol = V.reference_values(spec, xs.astype(U64))

A = np.load('work/p0_reports/data/A_ref.npy').astype(object)  # int64 -> object for exact shifts
s_arr = np.load('work/p0_reports/data/s_arr.npy')
x_norm = xs << (2 * s_arr)
Mnum = x_norm >> 2            # M * 2^18 (since x_norm/2^20 -> *2^18 => denom 2^18)

# A should scale as 2^-s: check A * 2^s as function of Mnum only
A_scaled = A * (1 << np.maximum(s_arr, 0))   # object ints
# group by Mnum: is A_scaled constant per Mnum?
import collections
byM = collections.defaultdict(set)
for m, a in zip(Mnum.tolist(), A_scaled.tolist()):
    byM[m].add(a)
n_multi = sum(1 for v in byM.values() if len(v) > 1)
print(f'distinct M values: {len(byM)}, M with >1 A_scaled value: {n_multi}')
if n_multi:
    ex = [m for m, v in byM.items() if len(v) > 1][:5]
    for m in ex:
        print('  M*2^18 =', m, 'A_scaled values:', sorted(byM[m])[:6])

# extremes of |A|/tol and their (M,s)
rat = np.abs(A).astype(np.float64) / tol.astype(np.float64)
order = np.argsort(-rat)[:30]
print('\ntop-30 |A|/tol:')
for i in order:
    print(f'  x={xs[i]:>8d} s={int(s_arr[i])} M={Mnum[i]/2**18:.9f} A={int(A[i]):>14d} ratio={rat[i]:.4f}')

# histogram of M for the top-30
Ms = np.array([Mnum[i] for i in order], dtype=np.float64) / 2**18
print('\nM values top30:', np.round(Ms, 6))
