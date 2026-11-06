"""Step 2+3: extract per-rotation control functions b_j(x) by angle perturbation.

For each of the 41 fine rotations: perturb its text angle by delta = 2^-30 half turns
(an exact binary rational, finite decimal), re-simulate the full domain (seed=0,
1 shot/x), and read b_j(x) = (err_pert(x) - err_orig(x)) / (delta*2^65) in {0,1}.

Phase is deterministic per x (measurement repairs are phase-only Clifford; outcomes
are seeded RNG independent of phase values) - verified on a subset with two seeds.

Outputs (work/p0_reports/data/):
  err_orig.npy      int64[N]   signed error, units of 2^-64 turns
  bcols/col_{j:02d}.npy  uint8[N]
  meta.json         angles as exact Fractions (half turns), delta, checks
"""
import json, sys, time
from fractions import Fraction
import numpy as np
sys.path.insert(0, 'data/verifiers/invsqrt')
import verify_submission_invsqrt as V
import kickmix as km

CIRCUIT = 'work/frontier_scan/mwa_unpacked/invsqrt.kmb'
OUT = 'work/p0_reports/data'
import os
os.makedirs(f'{OUT}/bcols', exist_ok=True)

U64, I64 = np.uint64, np.int64
MASK64 = (1 << 64) - 1

circuit = km.Circuit.from_file(CIRCUIT)
n_p = V.N_P
spec = V.ProblemSpecInvSqrt(width=2 * n_p + 2, max_x=3 * (2**n_p - 2) ** 2, beta=Fraction(1),
                            precision_bits=24, shots_per_x=1, system_qubits=3 * V.ETA * n_p)
x_reg, scratch = V.validate_registers(circuit, spec)
target, tol = V.reference_values(spec, np.arange(1, spec.max_x + 1, dtype=U64))
N = spec.max_x

lines = str(circuit).splitlines()
rots = json.load(open('work/p0_reports/step1_rotations.json'))['rotations']
assert len(rots) == 41

DELTA_HALF = Fraction(1, 2**30)          # half turns
DELTA_UNITS = DELTA_HALF * 2**63         # units of 2^-64 turns = 2^33
print('delta units:', DELTA_UNITS, file=sys.stderr)

def frac_to_decimal(fr: Fraction) -> str:
    # exact finite decimal (denominator is a power of 2): num/2^k -> ip.frac with k digits
    num, den = fr.numerator, fr.denominator
    neg = num < 0
    num = abs(num)
    k = den.bit_length() - 1
    assert den == 2**k
    ip, rem = divmod(num, den)
    fp = rem * 5**k
    s = f'{ip}.{fp:0{k}d}'
    return ('-' if neg else '') + s

def simulate(text_lines, seed=0):
    circ = km.Circuit('\n'.join(text_lines))
    BS = 65536
    errs = np.empty(N, dtype=I64)
    sim = km.Simulator(batch_size=BS, debug_print=False, counting_operations=False, seed=seed)
    t0 = time.time()
    for start in range(0, N, BS):
        stop = min(start + BS, N)
        n = stop - start
        xs = np.arange(start + 1, stop + 1, dtype=U64)
        if n < BS:
            xs = np.concatenate([xs, np.full(BS - n, xs[0], dtype=U64)])
        sim.clear_for_shot()
        sim.write_across_shots(x_reg, V.to_bits(xs, spec.width))
        sim.do(circ)
        theta = np.array([V.half_turns_to_units(sim.read_shot_phase(i)) for i in range(n)], dtype=U64)
        errs[start:stop] = (theta - target[np.arange(start + 1, stop + 1, dtype=U64) - U64(1)]).view(I64)
    return errs, time.time() - t0

# --- seed-independence check on a subset -------------------------------------
sub = slice(0, 8192)
e_a, _ = simulate(lines, seed=0)
sim_check = km.Simulator(batch_size=8192, debug_print=False, counting_operations=False, seed=12345)
xs = np.arange(1, 8193, dtype=U64)
sim_check.clear_for_shot()
sim_check.write_across_shots(x_reg, V.to_bits(xs, spec.width))
sim_check.do(km.Circuit('\n'.join(lines)))
th = np.array([V.half_turns_to_units(sim_check.read_shot_phase(i)) for i in range(8192)], dtype=U64)
e_b = (th - target[xs - U64(1)]).view(I64)
print('seed-independence subset match:', bool(np.array_equal(e_a[sub], e_b)), file=sys.stderr)

# --- original full run ---------------------------------------------------------
err_orig, t_orig = simulate(lines, seed=0)
np.save(f'{OUT}/err_orig.npy', err_orig)
json.dump({'tol_min': int(tol.min()), 'target_sample': int(target[0])}, open(f'{OUT}/ref.json', 'w'))
print(f'orig done {t_orig:.0f}s', file=sys.stderr)

# sanity vs p0 JSON top entries
p0 = json.load(open('work/frontier_scan/p0_invsqrt_errors.json'))
ok = True
for e in p0['top50_worst'][:10]:
    x = e['x'] - 1
    if int(err_orig[x]) != e['signed_err_units']:
        ok = False
        print('MISMATCH at x=', e['x'], int(err_orig[x]), e['signed_err_units'], file=sys.stderr)
print('matches p0 top10:', ok, file=sys.stderr)

# --- perturbation runs ---------------------------------------------------------
meta = {'delta_half_turns': str(DELTA_HALF), 'delta_units_2m64': int(DELTA_UNITS),
        'angles_half_turns_frac': [], 'angle_units_2m64_frac': []}
t_all = time.time()
for j, r in enumerate(rots):
    ang_frac = Fraction(r['angle_halfturns_str'])
    meta['angles_half_turns_frac'].append(str(ang_frac))
    meta['angle_units_2m64_frac'].append(str(ang_frac * 2**65))
    new_lines = list(lines)
    new_ang = ang_frac + DELTA_HALF
    new_lines[r['line']] = f"Z_POW {r['qubit']} {frac_to_decimal(new_ang)}"
    err_p, t_p = simulate(new_lines, seed=0)
    d = err_p - err_orig                      # in {0, DELTA_UNITS} up to +-2 rounding
    DU = int(DELTA_UNITS)
    col = ((d + DU // 4) // (DU // 2)).clip(0, 1).astype(np.uint8)
    n_bad = int((np.abs(d[col == 1] - DU) > 2).sum() + (np.abs(d[col == 0]) > 2).sum())
    if n_bad:
        print(f'WARN rot {j}: {n_bad} x with unexpected delta', file=sys.stderr)
    np.save(f'{OUT}/bcols/col_{j:02d}.npy', col)
    print(f'rot {j:02d} line {r["line"]:6d} q{r["qubit"]:>3s} ones={int(col.sum()):8d} '
          f'{t_p:5.0f}s cum={time.time()-t_all:6.0f}s', file=sys.stderr)

json.dump(meta, open(f'{OUT}/meta.json', 'w'), indent=1)
print('ALL DONE', file=sys.stderr)
