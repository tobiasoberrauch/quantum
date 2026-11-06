"""Verify task1_search findings on the FULL domain (not subsample):
- y_22 claimed = XOR of two basis bits (free). Identify them + confirm full-domain.
- Spot-confirm 2 'generic' bits (y_10, y_25) are NOT single/NOT/XOR2/AND2/A.L on full domain.
"""
import sys, json, math
import numpy as np
U64, I64 = np.uint64, np.int64
N=3*(2**10-2)**2
y=np.load('work/pa_prexperiment/data/y.npy')
s=np.load('work/pa_prexperiment/data/s.npy')
x=np.arange(1,N+1,dtype=I64)
def bit(v,i): return (v.astype(I64)>>i)&1

# rebuild basis (full domain)
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
B=np.stack([basis[nm] for nm in names],axis=1).astype(np.uint8)
ybits=((y.astype(U64)[:,None]>>np.arange(40,dtype=U64)[None,:])&1).astype(np.uint8)

def find_xor2(yi):
    for a in range(K):
        need=yi^B[:,a]; m=np.where((B==need[:,None]).all(axis=0))[0]
        if len(m) and int(m[0])!=a: return names[a],names[int(m[0])]
    return None

print('=== y_22 full-domain check ===')
yi=ybits[:,22]
print('density:',round(float(yi.mean()),4),'ones:',int(yi.sum()))
xr=find_xor2(yi)
print('XOR2 pair:',xr)
if xr:
    a,b=xr; print('verify (B_a ^ B_b)==y22 full domain:',bool(np.array_equal(B[:,names.index(a)]^B[:,names.index(b)],yi)))

print('\n=== spot-check generic bits are NOT 0/1-gate on full domain ===')
for i in [10,25,22]:
    yi=ybits[:,i]
    idm=np.where((B==yi[:,None]).all(axis=0))[0]
    notm=np.where(((1-B)==yi[:,None]).all(axis=0))[0]
    x2=find_xor2(yi)
    cover=[a for a in range(K) if int((B[:,a]&yi).sum())==int(yi.sum())]
    and2=None
    for a in cover:
        Fa=(B[:,a]==1)&(yi==0)
        for bb in cover:
            if bb<=a: continue
            if int((B[:,bb]&Fa).sum())!=0: continue
            if np.array_equal(B[:,a]&B[:,bb],yi): and2=(names[a],names[bb]); break
        if and2: break
    print(f'y_{i}: identity={len(idm)>0} NOT={len(notm)>0} XOR2={x2 is not None} AND2={and2 is not None}')
