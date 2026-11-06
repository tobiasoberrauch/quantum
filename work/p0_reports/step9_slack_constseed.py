"""Step 9: (a) slack-layer thickness around the ceiling; (b) constant-seed model margins.

(a) slack(x) = tol(x) - |err(x)|. Count x with slack < k*c for k in 1..12.
    Also: per-pinned-point shadow value: c* when that point's constraint is dropped
    (approximate: relax its tol by a large amount).
(b) Reconstruct mrmeows' constant-seed model (128-entry table, 2 Newton steps,
    out_frac 26) exactly as in notebooks/constseed-invsqrt-reconstruction.ipynb,
    compute min_margin over the full domain, and the rotation-count implication.
"""
import sys, json, math
import numpy as np
sys.path.insert(0, 'data/verifiers/invsqrt')
import verify_submission_invsqrt as V

U64, I64 = np.uint64, np.int64
OUT = 'work/p0_reports/data'
N = 3 * (2**10 - 2)**2
spec = V.ProblemSpecInvSqrt.for_n_p(10, shots_per_x=1)
xs_u = np.arange(1, N + 1, dtype=U64)
target, tol = V.reference_values(spec, xs_u)
tolF = tol.astype(np.float64)
err = np.load(f'{OUT}/err_orig.npy').astype(np.float64)
C0 = 58597850.0
slack = tolF - np.abs(err)

print('--- (a) slack layer ---')
for k in [1, 2, 3, 4, 6, 8, 12, 20, 50]:
    n = int((slack < k * C0).sum())
    print(f'  slack < {k:3d}*c : {n:7d} x-values ({n/N*100:.3f}%)')
print(f'  median slack: {np.median(slack):.3e}  (= {np.median(slack)/C0:.1f} c)')
print(f'  min tol: {int(tol.min())} at x={N} ; 0.383*min_tol = {0.383*tol.min():.3e}')

# --- (b) constant-seed model --------------------------------------------------
N_P = 10
WIDTH = 2 * N_P + 2
MAX_X = 3 * (2**N_P - 2)**2
xs = np.arange(1, MAX_X + 1, dtype=np.int64)
TOL_REL = 2.0**-24

def normalize(xs):
    s = (WIDTH - (np.floor(np.log2(xs)).astype(np.int64) + 1)) // 2
    return s, xs << (2*s)

def seed_table(mode="center", frac=8):
    i = np.arange(128, dtype=np.float64)
    Mc = (i + (0.5 if mode == "center" else 0.0))/32.0
    f = np.where(Mc > 0, 1.0/np.sqrt(np.where(Mc > 0, Mc, 1.0)), 0.0)
    return np.round(f*2.0**frac).astype(np.int64)

def constseed_units(xs, *, seed_mode="table", seed_frac=8, n1_frac=16, n2_guard=24, out_frac=26):
    """Returns approx phase in units of 2^-64 turns (float), and rel error vs exact."""
    xs = np.asarray(xs, dtype=np.int64)
    s, x_norm = normalize(xs)
    idx = x_norm >> (WIDTH-7)
    if seed_mode == "table":
        S = seed_table("center", seed_frac)[idx]
    else:
        raise ValueError
    # Newton #1 (units of 2^-n1)
    Q1 = (x_norm*S*S) >> (WIDTH-2+2*seed_frac-n1_frac)
    C1 = (3<<n1_frac) - Q1
    P1 = (S*C1) >> seed_frac
    # Newton #2 (units of 2^-g)
    g = n2_guard + 2
    P1g = P1 << (g-n1_frac)
    Q2 = (x_norm*P1*P1) >> (WIDTH-g+2*n1_frac)
    C2 = ((3<<g) - Q2) >> 1
    P2 = (P1g*C2) >> (2*g-out_frac)
    y = P2 << s                      # phase = y / 2^(out_frac + N_P + 1) turns
    F = out_frac + N_P + 1
    approx_turns = y / 2.0**F
    exact_turns = 1.0/np.sqrt(xs.astype(np.float64))
    return approx_turns, exact_turns, y

for mode in ["table"]:
    approx, exact, y = constseed_units(xs, seed_mode=mode)
    rel = np.abs(approx-exact)/exact
    ratio = rel/TOL_REL
    i = int(ratio.argmax())
    print(f'\n--- (b) constseed {mode}: worst ratio {ratio.max():.4f} at x={xs[i]:,} ---')
    # margin in 2^-64 units: |approx - target| vs tol
    target_c, tol_c = V.reference_values(spec, xs.astype(U64))
    approx_units = np.round(approx * 2**64)
    # mod-1 wrap handling: exact/approch are in (0,1) turns, small
    d = np.abs(((approx_units - target_c.astype(np.int64)) % (2**64)))
    d = np.minimum(d, 2**64 - d)
    margin = tol_c.astype(np.int64) - d
    print(f'min_margin = {int(margin.min()):,} units (x={int(xs[margin.argmin()])+1:,}) '
          f'= {margin.min()/C0:.2f} x current c')
    print(f'worst ratio (unit-exact) = {float((d/tol_c.astype(float)).max()):.4f}')
    # output bits needed: y < 2^F with F = 27 -> phase grid 2^-27 turns
    print(f'y range: {int(y.min()):,} .. {int(y.max()):,}  (max bit {int(y.max()).bit_length()})')
