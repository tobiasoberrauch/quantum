"""Step 9b: EXACT-integer constant-seed model margins + width sweep + pwq3 seed.

phase = y / 2^F turns, F = out_frac + N_P + 1. In units of 2^-64 turns: y * 2^(64-F) (exact).
margin(x) = tol(x) - |round_to_64grid - target| ... use exact units directly.
"""
import sys, json, math
import numpy as np
sys.path.insert(0, 'data/verifiers/invsqrt')
import verify_submission_invsqrt as V

U64, I64 = np.uint64, np.int64
N_P = 10
WIDTH = 2 * N_P + 2
MAX_X = 3 * (2**N_P - 2)**2
xs = np.arange(1, MAX_X + 1, dtype=np.int64)
spec = V.ProblemSpecInvSqrt.for_n_p(N_P, shots_per_x=1)
target, tol = V.reference_values(spec, xs.astype(U64))
TOL_REL = 2.0**-24

def normalize(xs):
    s = (WIDTH - (np.floor(np.log2(xs)).astype(np.int64) + 1)) // 2
    return s, xs << (2*s)

def seed_table(mode="center", frac=8):
    i = np.arange(128, dtype=np.float64)
    Mc = (i + (0.5 if mode == "center" else 0.0))/32.0
    f = np.where(Mc > 0, 1.0/np.sqrt(np.where(Mc > 0, Mc, 1.0)), 0.0)
    return np.round(f*2.0**frac).astype(np.int64)

def fit_pwq3_float():
    bounds = [(1.0,1.5),(1.5,2.0),(2.0,3.0),(3.0,4.0)]
    out=[]
    for m0,m1 in bounds:
        w=m1-m0; k=np.arange(128,dtype=np.float64); u=k/128.0; M=m0+u*w
        f=1.0/np.sqrt(M); A=np.vander(u,4)[:,::-1]
        coef,*_=np.linalg.lstsq(A,f,rcond=None); out.append(tuple(coef))
    return out
_PWQ3 = fit_pwq3_float()

def constseed_y(xs, *, seed_mode="table", seed_frac=8, n1_frac=16, n2_guard=24, out_frac=26):
    xs=np.asarray(xs,dtype=np.int64); s,x_norm=normalize(xs); idx=x_norm>>(WIDTH-7)
    if seed_mode=="table":
        S=seed_table("center",seed_frac)[idx]
    elif seed_mode=="pwq3":
        top=(x_norm>>(WIDTH-1))&1; second=(x_norm>>(WIDTH-2))&1; third=(x_norm>>(WIDTH-3))&1
        inter=np.where(top==0,third,2+second)
        m0v=np.array([1.,1.5,2.,3.])[inter]; wv=np.array([.5,.5,1.,1.])[inter]
        Mv=x_norm.astype(np.float64)/2.0**(WIDTH-2); u=(Mv-m0v)/wv
        kk=((u*128.0).astype(np.int64)).astype(np.float64)/128.0
        a=np.array([c[0] for c in _PWQ3])[inter]; b=np.array([c[1] for c in _PWQ3])[inter]
        c=np.array([c[2] for c in _PWQ3])[inter]; d=np.array([c[3] for c in _PWQ3])[inter]
        S=(((d*kk+c)*kk+b)*kk+a)*2.0**seed_frac
        S=S.astype(np.int64)
    Q1=(x_norm*S*S)>> (WIDTH-2+2*seed_frac-n1_frac)
    C1=(3<<n1_frac)-Q1
    P1=(S*C1)>>seed_frac
    g=n2_guard+2
    P1g=P1<<(g-n1_frac)
    Q2=(x_norm*P1*P1)>> (WIDTH-g+2*n1_frac)
    C2=((3<<g)-Q2)>>1
    P2=(P1g*C2)>>(2*g-out_frac)
    return P2 << s, s

def margins(y, out_frac):
    F = out_frac + N_P + 1
    shift = 64 - F
    approx_units = y.astype(I64) << shift if shift >= 0 else y.astype(I64) >> (-shift)
    d = np.abs(approx_units - target.astype(I64))
    # mod-1 wrap: values are < 2^64/2 region? y max ~ 2^(F-1) -> units < 2^63 ok, no wrap needed
    margin = tol.astype(I64) - d
    ratio = d.astype(np.float64)/tol.astype(np.float64)
    return int(margin.min()), int(xs[margin.argmin()])+1, float(ratio.max())

print(f'{"variant":38s} {"min_margin":>13s} {"at x":>10s} {"worst_ratio":>12s} {"margin/c0":>10s}')
C0 = 58597850.0
variants = [
    ("table n1=16 g=24 out=26 (mrmeows spec)", dict(seed_mode="table", n1_frac=16, n2_guard=24, out_frac=26)),
    ("pwq3   n1=16 g=24 out=26",               dict(seed_mode="pwq3",   n1_frac=16, n2_guard=24, out_frac=26)),
    ("table n1=17 g=24 out=26",                dict(seed_mode="table", n1_frac=17, n2_guard=24, out_frac=26)),
    ("table n1=16 g=25 out=26",                dict(seed_mode="table", n1_frac=16, n2_guard=25, out_frac=26)),
    ("table n1=16 g=24 out=27",                dict(seed_mode="table", n1_frac=16, n2_guard=24, out_frac=27)),
    ("table n1=18 g=24 out=26",                dict(seed_mode="table", n1_frac=18, n2_guard=24, out_frac=26)),
    ("table seedfrac=9 n1=16 g=24 out=26",     dict(seed_mode="table", seed_frac=9, n1_frac=16, n2_guard=24, out_frac=26)),
]
for name, kw in variants:
    y, s = constseed_y(xs, **kw)
    mm, wx, wr = margins(y, kw["out_frac"])
    print(f'{name:38s} {mm:>13,d} {wx:>10,d} {wr:>12.4f} {mm/C0:>10.2f}')
