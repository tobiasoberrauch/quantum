"""Step 4: CORRECTED P-A economics with n_rot = 33 (not 0), as a function of the
net mean-executed-Toffoli change Delta_me = R_routing - Q_removed_quadratics.

Cost model (verifier): C = mean_exec_Toffolis + (t_base + n_rot*(0.56*log2(1/eps)+5.3))/4,
eps = pi*c/2^64/n_rot ; cost = Q*C ; ratio = reference_cost/cost ; GM=(DQI*chem*ratio)^(1/3).
"""
import math, json

REF_COST = 2076774.233715282
Q = 62
DQI, CHEM = 61.056888, 9.934269

# ---- current (shipped) ----
cur = dict(mean_exec=1289.29, t_base=20.5, n_rot=41, c=58597850)
def rot_side(t_base, n_rot, c):
    if n_rot == 0:
        return t_base/4, None
    eps = math.pi*c/2**64/n_rot
    per = 0.56*math.log2(1/eps)+5.3
    return (t_base + n_rot*per)/4, (eps, per)
cur_rs, cur_ep = rot_side(cur['t_base'], cur['n_rot'], cur['c'])
cur_C = cur['mean_exec'] + cur_rs
cur_cost = Q*cur_C
cur_ratio = REF_COST/cur_cost
cur_GM = (DQI*CHEM*cur_ratio)**(1/3)
print('=== CURRENT (check vs Report B) ===')
print(f'rot_side={cur_rs:.2f} (eps={cur_ep[0]:.3e}, per_rot={cur_ep[1]:.3f})')
print(f'C={cur_C:.2f} cost={cur_cost:.2f} ratio={cur_ratio:.4f} GM={cur_GM:.4f}')
print(f'(Report B: C=1589.26 cost=98533.87 ratio=21.0768 GM=23.3825)\n')

# ---- P-A corrected: n_rot=33, c=332168080 ----
pa_c = 332168080
pa_nrot = 33
pa_tbase = 20.5          # approx (core T-gates dominate); uncertainty +-5
pa_rs, pa_ep = rot_side(pa_tbase, pa_nrot, pa_c)
print('=== P-A rotation side (n_rot=33, c=332,168,080) ===')
print(f'rot_side={pa_rs:.2f} (eps={pa_ep[0]:.3e}, per_rot={pa_ep[1]:.3f})')
print(f'rotation-side saving vs current = {cur_rs-pa_rs:.2f} Toffoli-eq\n')

print('=== P-A total, swept over net mean-exec change Delta_me ===')
print(f'{"Delta_me":>9} {"mean_exec":>10} {"C":>9} {"cost":>10} {"ratio":>8} {"GM":>8} {"dGM%":>7}')
rows=[]
for dme in [-100,-50,0,20,50,100,200,585]:
    me = cur['mean_exec'] + dme
    C = me + pa_rs
    cost = Q*C
    ratio = REF_COST/cost
    gm = (DQI*CHEM*ratio)**(1/3)
    dgm = (gm/cur_GM-1)*100
    rows.append(dict(dme=dme, mean_exec=round(me,2), C=round(C,2), cost=round(cost,2),
                     ratio=round(ratio,4), GM=round(gm,4), dGM_pct=round(dgm,3)))
    print(f'{dme:>9} {me:>10.2f} {C:>9.2f} {cost:>10.2f} {ratio:>8.4f} {gm:>8.4f} {dgm:>+7.2f}')

print('\nNote: Delta_me = R_routing(new s-aware y-bit taps) - Q_removed(24 quadratic taps dropped).')
print('Option (a) data-controlled shift: R=585 -> Delta_me ~ +537 (after ~48 quad removal) -> see row.')
print('Option (b) cheap algebraic forms (like existing 14 raw-y taps ~1-3 T each): R~22-66.')
json.dump({'current': dict(C=round(cur_C,2), cost=round(cur_cost,2), ratio=round(cur_ratio,4), GM=round(cur_GM,4)),
           'PA_rotation_side': round(pa_rs,2), 'PA_rot_saving': round(cur_rs-pa_rs,2),
           'sweep': rows}, open('work/pa_prexperiment/data/step4_economics.json','w'), indent=1)
print('saved work/pa_prexperiment/data/step4_economics.json')
