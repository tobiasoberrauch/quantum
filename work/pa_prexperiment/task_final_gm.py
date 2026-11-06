"""Exact cost-model GM for the FINAL P-A verdict (all 19 new bits generic, R=242).

Reproduces the report's baseline, then evaluates P-A with:
  - n_rot=33, c=332168080 -> rotation-side (recomputed, must match 229.43)
  - mean_exec = 1289.29 + (R - Q_removed), Q_removed ~ 48
Cost model (from verify_submission_invsqrt.py / report):
  eps   = pi*c/2^64/n_rot
  C     = mean_exec + (t_base + n_rot*(0.56*log2(1/eps)+5.3))/4
  cost  = Q*C ; ratio = 2076774.233715282/cost ; GM = (61.056888*9.934269*ratio)^(1/3)
"""
import math
Q = 62
t_base = 20.5
BASE_MEAN = 1289.29
BASE_ROT  = 299.97          # current rotation-side (n_rot=41)
def rot_side(n_rot, c):
    eps = math.pi*c/2**64/n_rot
    return (t_base + n_rot*(0.56*math.log2(1/eps)+5.3))/4
def gm(mean_exec, rot):
    C = mean_exec + rot
    cost = Q*C
    ratio = 2076774.233715282/cost
    return C, cost, ratio, (61.056888*9.934269*ratio)**(1/3)

# sanity: baseline
C0,cost0,r0,gm0 = gm(BASE_MEAN, BASE_ROT)
print(f'BASELINE  C={C0:.2f} cost={cost0:.2f} ratio={r0:.4f} GM={gm0:.4f}  (expect 1589.26/98533.86/21.0768/23.3825)')

PA_ROT = rot_side(33, 332168080)
print(f'P-A rotation-side (n_rot=33,c=332168080) = {PA_ROT:.2f}  (expect ~229.43); saving vs base = {BASE_ROT-PA_ROT:.2f}')

for R in (242, 231, 118):
    Qrem = 48
    dme = R - Qrem
    me = BASE_MEAN + dme
    C,cost,ratio,gmv = gm(me, PA_ROT)
    print(f'R={R}: dme={dme:+d} mean_exec={me:.2f} C={C:.2f} cost={cost:.2f} ratio={ratio:.4f} GM={gmv:.4f} dGM={(gmv/gm0-1)*100:+.2f}%')
