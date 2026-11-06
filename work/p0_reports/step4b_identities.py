"""Step 4b: for pinned x, test whether theta_sim(x) +/- c equals simple integer functions of x.

theta_sim = target + err (units of 2^-64 turns). Candidates:
  isqrt(2^128 // x), r>>1, r>>1 +/- r>>25, floor(2^64/sqrt(x)), round(...), etc.
"""
import sys, json, math
import numpy as np
sys.path.insert(0, 'data/verifiers/invsqrt')
import verify_submission_invsqrt as V

U64, I64 = np.uint64, np.int64
spec = V.ProblemSpecInvSqrt.for_n_p(10, shots_per_x=1)
xs_all = np.arange(1, spec.max_x + 1, dtype=U64)
target, tol = V.reference_values(spec, xs_all)
p0 = json.load(open('work/frontier_scan/p0_invsqrt_errors.json'))
pinned = [e for e in p0['top50_worst'] if 58597845 <= e['margin_units'] <= 58597860]
print(f'{len(pinned)} pinned x in top50')

C_LO, C_HI = 58597850, 58597855
rows = []
for e in pinned:
    x = int(e['x']); i = x - 1
    err = int(e['signed_err_units']); tg = int(target[i]); tl = int(tol[i])
    th = tg + err
    r = math.isqrt((1 << 130) // x)
    cands = {
        'isqrt(2^128//x)': math.isqrt((1 << 128) // x),
        'r>>1': r >> 1,
        'r>>1 - r>>25': (r >> 1) - (r >> 25),
        'r>>1 + r>>25': (r >> 1) + (r >> 25),
        'round(r/2)-c-': None,
    }
    # theta -/+ c
    for sign in (+1, -1):
        t2 = th - sign * C_LO  # try subtracting c (if err<0: th = tg - (tol-c) -> th + c = tg - tol)
    rows.append((x, err, tg, tl, th, r))

# Direct identity tests with exact c per point:
print(f'{"x":>8} {"err":>14} {"tg":>14} {"tol":>14} {"th":>14} | th+c vs tg-tol | th-c vs tg+tol | th vs isqrt128')
for x, err, tg, tl, th, r in rows:
    c = tg + err and (abs(err))  # placeholder
    margin = tl - abs(err)
    t_plus_c = th + margin      # if err<0: th + (tol-|err|) = tg - tol
    t_minus_c = th - margin     # if err>0: th - (tol-|err|) = tg + tol
    side = 'neg' if err < 0 else 'pos'
    if side == 'neg':
        lhs, rhs = t_plus_c, tg - tl
        lhs2, rhs2 = t_minus_c, tg + tl
    else:
        lhs, rhs = t_minus_c, tg + tl
        lhs2, rhs2 = t_plus_c, tg - tl
    sq = math.isqrt((1 << 128) // x)
    print(f'{x:>8} {err:>14d} {tg:>14d} {tl:>14d} {th:>14d} | {lhs-rhs:>+4d} ({side})   {lhs2-rhs2:>+6d}   {th-sq:>+8d}')
