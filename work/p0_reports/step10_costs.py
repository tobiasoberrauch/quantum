"""Step 10: final cost/ratio/GM arithmetic for all proposals."""
import math

REF_INV = 2076774.233715282   # Google reference cost, invsqrt (mrmeows README)
R_DQI, R_CHEM = 61.056888, 9.934269   # yoyobar local ratios
Q = 62

def rot_T(n, c):
    if n == 0: return 0.0
    eps = math.pi * c / 2**64 / n
    return n * (0.56 * math.log2(1 / eps) + 5.3)

def scenario(name, mean_toff, t_base, n_rot, c, q=Q, note=''):
    C = mean_toff + (t_base + rot_T(n_rot, c)) / 4
    cost = q * C
    ratio = REF_INV / cost
    gm = (ratio * R_DQI * R_CHEM) ** (1/3)
    print(f'{name:34s} meanT={mean_toff:9.2f} t_base={t_base:6.1f} nrot={n_rot:3d} '
          f'c={c:13,.0f} C={C:9.2f} cost={cost:12,.2f} ratio={ratio:8.4f} GM={gm:.4f} {note}')
    return ratio, gm

print('--- baseline & proposals ---')
base_ratio, base_gm = scenario('CURRENT (shipped)', 1289.29, 20.5, 41, 58597850, note='[FAKT]')
scenario('LP-polished angles only', 1289.29, 20.5, 41, 58597853, note='+3 units, nothing [FAKT]')
scenario('P-D add 6 free taps', 1289.29, 20.5, 47, 67340595, note='greedy step8 [FAKT]')
scenario('P-A dyadic R=50', 1339.29, 40.5, 0, 332168080, note='[HYP] optimistic routing')
scenario('P-A dyadic R=100', 1389.29, 40.5, 0, 332168080, note='[HYP]')
scenario('P-A dyadic R=200', 1489.29, 40.5, 0, 332168080, note='[HYP] pessimistic routing')
scenario('P-B constseed nrot=0', 1389.29, 40.5, 0, 424039681, note='[SPEK] core delta +100')
scenario('P-B constseed nrot=26', 1389.29, 40.5, 26, 424039681, note='[SPEK] with refit taps')
scenario('P-B constseed nrot=0 core+200', 1489.29, 40.5, 0, 424039681, note='[SPEK] pessimistic core')
scenario('ceiling c=621M nrot=41', 1289.29, 20.5, 41, 621138291, note='[FAKT bound] c alone')
scenario('ceiling c=621M nrot=0', 1389.29, 40.5, 0, 621138291, note='[SPEK] both levers')

print()
print('GM deltas vs baseline:')
for name, args in [
    ('P-A R=50', (1339.29, 40.5, 0, 332168080)),
    ('P-A R=200', (1489.29, 40.5, 0, 332168080)),
    ('P-B nrot0 core+100', (1389.29, 40.5, 0, 424039681)),
    ('P-B nrot0 core+200', (1489.29, 40.5, 0, 424039681)),
    ('both levers', (1389.29, 40.5, 0, 621138291)),
]:
    r, g = scenario(name, *args)
    print(f'  {name:22s} dGM = {(g/base_gm-1)*100:+.2f}%')
print()
print(f'per-rotation synthesis cost at current c: {rot_T(41, 58597850)/41:.2f} T = {rot_T(41,58597850)/41/4:.2f} Toffoli-eq')
print(f'c doubling saving (nrot fixed): {5.74*math.log2(2):.2f} Toffoli-eq total')
print(f'break-even f for 1 added free tap: {2**(7.2/5.74):.2f}x')
