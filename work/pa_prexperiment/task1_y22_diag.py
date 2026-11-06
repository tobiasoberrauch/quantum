"""Diagnose the y_22 XOR2 discrepancy between subsample-search and full-domain.

task1_search.py (SUB=12000) reported y_22 = XOR2 of two basis bits.
task1_verify_full.py (full N) found NO such pair. Reconstruct the exact
subsample pair, then count how many FULL-domain rows it disagrees on.
"""
import sys, math
import numpy as np
U64, I64 = np.uint64, np.int64
N = 3*(2**10-2)**2
y = np.load('work/pa_prexperiment/data/y.npy')
s = np.load('work/pa_prexperiment/data/s.npy')
x = np.arange(1, N+1, dtype=I64)
def bit(v,i): return (v.astype(I64)>>i)&1

# rebuild yy (reference model) - same as step1_model
N_P=10; WIDTH=22; xs=x
POLY_A=(0.99994132489119882162,0.49609891915903542303,0.33261112772430493331,0.14876762006038398086)
POLY_B=(0.81648515205385221995,0.27136515484240234115,0.12756148214815175348,0.044753028579153842218)
def product(rows,operand,out_bits,operand_bits,limit):
    acc=np.zeros_like(xs)
    for ctl,w in rows:
        e=out_bits-operand_bits+w; acc+=ctl*(operand<<e if e>=0 else operand>>-e)
    assert (acc<2**limit).all(); return acc
s=(WIDTH-(np.floor(np.log2(xs.astype(float))).astype(I64)+1))//2
xn=xs<<(2*s); top,second,third=bit(xn,WIDTH-1),bit(xn,WIDTH-2),bit(xn,WIDTH-3)
cases=[POLY_A,POLY_B,[a/(2**j*math.sqrt(2)) for j,a in enumerate(POLY_A)],[b/(2**j*math.sqrt(2)) for j,b in enumerate(POLY_B)]]
table=np.array([[round(c*2**17) for c in case] for case in cases],dtype=I64)
c0,c1,c2,c3=(table[np.where(top==0,third,2+second),j] for j in range(4))
delta=[(top&third,-1)]+[(bit(xn,WIDTH-2-m),-m) for m in range(2,15)]
y0,mult=c0,c3
for acc in (c2,c1,c0): y0=mult=acc-product(delta,mult,17,17,17)
wc=17; Y={k:bit(y0,wc-k) for k in range(1,wc+1)}
square=np.zeros_like(xs)
for k in range(1,wc+1):
    if 2*k<=28: square+=Y[k]<<(28-2*k)
    for l in range(k+1,wc+1):
        if k+l-1<=28: square+=(Y[k]&Y[l])<<(28-(k+l-1))
m_rows=[(bit(xn,i),i-WIDTH+2) for i in range(WIDTH)]
z=product(m_rows,square,28,28,30); correction=(3<<28)-z
p=product([(Y[k],-k) for k in range(1,wc+1)],correction,29,28,30)
yy=p<<s
assert np.array_equal(yy,y), 'model mismatch'

# rebuild full basis (same order as task1_search)
basis={}
for j in range(41): basis[f'b{j:02d}']=np.load(f'work/p0_reports/data/bcols/col_{j:02d}.npy').astype(np.uint8)
for i in range(WIDTH): basis[f'x{i:02d}']=bit(xs,i)
for k in range(4): basis[f's{k}']=bit(s,k)
basis['top']=top; basis['second']=second; basis['third']=third
for nm,arr in [('c0',c0),('c1',c1),('c2',c2),('c3',c3)]:
    for bb in range(17): basis[f'{nm}_{bb:02d}']=bit(arr,bb)
for k in range(1,18): basis[f'y{k:02d}']=Y[k]
for bb in range(28): basis[f'sq{bb:02d}']=bit(square,bb)
for bb in range(28): basis[f'z{bb:02d}']=bit(z,bb)
for bb in range(29): basis[f'cr{bb:02d}']=bit(correction,bb)
for bb in range(30): basis[f'p{bb:02d}']=bit(p,bb)
names=list(basis); K=len(names)
Bf=np.stack([basis[nm] for nm in names],axis=1).astype(np.uint8)   # [N,K] full
yi_f=((y.astype(U64)[:,None]>>22)&1).astype(np.uint8)[:,0]         # full y_22

# replicate the EXACT subsample used by task1_search (rng seed 3, SUB=12000)
rng=np.random.default_rng(3)
SUB=12000
sub=rng.choice(N,size=SUB,replace=False)
Bs=Bf[sub]; yi_s=yi_f[sub]

# find the subsample XOR2 pair (same loop as search)
pair=None
for a in range(K):
    need=yi_s^Bs[:,a]; m=np.where((Bs==need[:,None]).all(axis=0))[0]
    if len(m) and int(m[0])!=a: pair=(a,int(m[0])); break
print('subsample XOR2 pair:', (names[pair[0]], names[pair[1]]) if pair else None)
if pair:
    a,b=pair
    # count FULL-domain disagreements of B_a ^ B_b vs y_22
    xor_full = Bf[:,a]^Bf[:,b]
    dis = int((xor_full!=yi_f).sum())
    print(f'FULL-domain disagreements of ({names[a]} ^ {names[b]}) vs y_22 : {dis} / {N}  ({dis/N:.3%})')
    print(f'agreement on the 12000 subsample rows : {int((xor_full[sub]==yi_f[sub]).sum())}/{SUB}')
    # where do they disagree? show s-distribution of disagreement rows
    drows=np.flatnonzero(xor_full!=yi_f)
    if len(drows):
        sv=s[drows]
        from collections import Counter
        print('disagreement rows s-value histogram:', dict(sorted(Counter(sv.tolist()).items())))
