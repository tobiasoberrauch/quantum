"""Step 1: parse invsqrt.kmb text; classify Z_POW angles; list fine rotations."""
import json, math, sys
from fractions import Fraction
import kickmix as km

CIRCUIT = 'work/frontier_scan/mwa_unpacked/invsqrt.kmb'
c = km.Circuit.from_file(CIRCUIT)
text = str(c)
lines = [ln for ln in text.splitlines()]
print('total text lines:', len(lines), file=sys.stderr)

def zpow_class(half_turns: Fraction):
    # mirror of verifier: clifford if mult of 1/2 turn (Z^int), t if mult of 1/4, else rotation
    ht = half_turns
    if ht % Fraction(1, 2) == 0: return 'clifford'
    if ht % Fraction(1, 4) == 0: return 't'
    return 'rotation'

ops = []
rots = []
n_cliff = n_t = 0
for i, ln in enumerate(lines):
    s = ln.strip()
    if not s or s.startswith('#'): continue
    parts = s.split()
    name = parts[0]
    ops.append((i, name, parts))
    if name == 'Z_POW':
        q = parts[1]
        ang = Fraction(parts[2])  # HALF turns (builder.z_pow takes half turns)
        cls = zpow_class(ang)
        if cls == 'clifford': n_cliff += 1
        elif cls == 't': n_t += 1
        else:
            rots.append({'line': i, 'qubit': q, 'angle_halfturns_str': parts[2],
                         'angle_turns': float(ang) / 2.0, 'angle_halfturns_frac': str(ang)})

print(f'ops={len(ops)} zpow_clifford={n_cliff} zpow_t={n_t} zpow_rotation={len(rots)}', file=sys.stderr)
from collections import Counter
print(Counter(n for _, n, _ in ops).most_common(20), file=sys.stderr)

json.dump({'num_ops': len(ops), 'n_clifford_zpow': n_cliff, 'n_t_zpow': n_t,
           'n_rotation_zpow': len(rots), 'rotations': rots},
          open('work/p0_reports/step1_rotations.json', 'w'), indent=1)
for r in rots:
    print(r['line'], r['qubit'], r['angle_halfturns_str'][:44], f"{r['angle_turns']:.6e} turns")
