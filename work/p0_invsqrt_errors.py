"""P0 audit: per-x SIGNED phase-error distribution for invsqrt.kmb (1 shot per x, deterministic phase).

Outputs: min_margin, exact top-20 worst-x, sign structure, histogram, and the optimal
CONSTANT global-phase shift delta* (minimax over x) with its effect on worst-ratio/min_margin.
A constant shift is implementable as one extra (or adjusted) rotation on the phased qubit.
"""
import sys, json, time
from fractions import Fraction
import numpy as np
sys.path.insert(0, 'data/verifiers/invsqrt')
import verify_submission_invsqrt as V
import kickmix as km

CIRCUIT = 'work/frontier_scan/mwa_unpacked/invsqrt.kmb'
U64 = np.uint64
I64 = np.int64

circuit = km.Circuit.from_file(CIRCUIT)
n_p = V.N_P
spec = V.ProblemSpecInvSqrt(width=2 * n_p + 2, max_x=3 * (2**n_p - 2) ** 2, beta=Fraction(1),
                            precision_bits=24, shots_per_x=1, system_qubits=3 * V.ETA * n_p)
x_reg, scratch = V.validate_registers(circuit, spec)
target, tol = V.reference_values(spec, np.arange(1, spec.max_x + 1, dtype=U64))
N = spec.max_x
print(f'N={N} width={spec.width}', file=sys.stderr)

BS = 65536
errors = np.empty(N, dtype=I64)          # signed, units of 2^-64 turns
t0 = time.time()
sim = km.Simulator(batch_size=BS, debug_print=False, counting_operations=True, seed=0)
for start in range(0, N, BS):
    stop = min(start + BS, N)
    n = stop - start
    xs = np.arange(start + 1, stop + 1, dtype=U64)
    if n < BS:  # pad last chunk to simulator batch size
        xs = np.concatenate([xs, np.full(BS - n, xs[0], dtype=U64)])
    sim.clear_for_shot()
    sim.write_across_shots(x_reg, V.to_bits(xs, spec.width))
    sim.do(circuit)
    theta = np.array([V.half_turns_to_units(sim.read_shot_phase(i)) for i in range(n)], dtype=U64)
    errors[start:stop] = (theta - target[np.arange(start + 1, stop + 1, dtype=U64) - U64(1)]).view(I64)
    if (start // BS) % 8 == 0:
        print(f'{start / N:5.1%}  {time.time() - t0:6.0f}s', file=sys.stderr)
print(f'done in {time.time() - t0:.0f}s', file=sys.stderr)

used = np.abs(errors)
margin = tol.astype(I64) - used
min_margin = int(margin.min())
worst_idx = int(margin.argmin())

# exact top-50 by cross-multiplication (Python ints), from float prefilter
import functools
ratio_f = (used.astype(np.float64)) / (tol.astype(np.float64))
pref = np.argsort(-ratio_f)[:200]
def cmp(a, b):
    ua, ta, ub, tb = int(used[a]), int(tol[a]), int(used[b]), int(tol[b])
    l, r_ = ua * tb, ub * ta   # compare used_a/tol_a vs used_b/tol_b exactly
    return -1 if l > r_ else (1 if l < r_ else 0)
top50 = sorted(pref.tolist(), key=functools.cmp_to_key(cmp))[:50]

out = {
    'circuit': CIRCUIT,
    'min_margin_units_2m64': min_margin,
    'min_margin_x': worst_idx + 1,
    'min_margin_ratio': float(used[worst_idx]) / float(tol[worst_idx]),
    'global_max_error': int(errors.max()), 'global_min_error': int(errors.min()),
    'frac_positive': float((errors > 0).mean()), 'frac_negative': float((errors < 0).mean()),
    'frac_zero': float((errors == 0).mean()),
    'top50_worst': [
        {'x': i + 1, 'signed_err_units': int(errors[i]), 'tol_units': int(tol[i]),
         'ratio': float(used[i]) / float(tol[i]), 'margin_units': int(margin[i])}
        for i in top50],
    'histogram_ratio_buckets': {},
}
edges = [0.0, .1, .2, .3, .4, .5, .6, .7, .8, .9, .95, .99, .999, 1.000001]
labels = ['<0.1','0.1-0.2','0.2-0.3','0.3-0.4','0.4-0.5','0.5-0.6','0.6-0.7','0.7-0.8','0.8-0.9','0.9-0.95','0.95-0.99','0.99-0.999','0.999-1.0']
cnt = np.zeros(len(labels))
r = ratio_f
for j, lab in enumerate(labels):
    lo, hi = edges[j], edges[j + 1]
    cnt[j] = ((r >= lo) & (r < hi)).sum()
out['histogram_ratio_buckets'] = dict(zip(labels, cnt.tolist()))

# --- constant-shift minimax: delta* = (max+min)/2 shifts error range to be centered ---
emax, emin = int(errors.max()), int(errors.min())
delta_star = (emax + emin) // 2
shifted = errors - delta_star
used_s = np.abs(shifted)
margin_s = tol.astype(I64) - used_s
worst_s = int(margin_s.argmin())
out['constant_shift'] = {
    'delta_star_units_2m64': delta_star,
    'delta_star_turns': delta_star / 2**64,
    'new_min_margin_units': int(margin_s.min()),
    'new_worst_ratio': float(used_s[worst_s]) / float(tol[worst_s]),
    'new_worst_x': worst_s + 1,
    'old_min_margin_units': min_margin,
    'margin_improvement_factor': min_margin / max(1, int(margin_s.min())) if int(margin_s.min()) > 0 else None,
}
# also scan a grid of shifts around delta_star for robustness (in case of wrap effects)
best = None
for d in range(delta_star - 2**30, delta_star + 2**30 + 1, 2**20):
    m = int((tol.astype(I64) - np.abs(errors - d)).min())
    if best is None or m > best[1]:
        best = (d, m)
out['constant_shift']['grid_best_delta'] = best[0]
out['constant_shift']['grid_best_min_margin'] = best[1]

json.dump(out, open('work/frontier_scan/p0_invsqrt_errors.json', 'w'), indent=1)
print(json.dumps({k: out[k] for k in ['min_margin_units_2m64','min_margin_x','min_margin_ratio','global_max_error','global_min_error','frac_positive','frac_negative']}, indent=1))
print('top10:', json.dumps(out['top50_worst'][:10], indent=1))
print('hist:', json.dumps(out['histogram_ratio_buckets']))
print('shift:', json.dumps(out['constant_shift'], indent=1))
