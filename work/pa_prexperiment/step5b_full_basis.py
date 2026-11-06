"""Step 5b (fixed): DECISIVE option-(b) search using the FULL pipeline-bit basis.
Model copied EXACTLY from step4a (int64 throughout); basis bits cast to uint8 at the end.
"""
import sys, json, math
import numpy as np
U64, I64 = np.uint64, np.int64
N_P=10; WIDTH=2*N_P+2; N=3*(2**N_P-2)**2
xs=np.arange(1,N+1,dtype=I64)
def bit(v,i): return (v>>i)&1          # int64, like step4a

POLY_A=(0.99994132489119882162,0.49609891915903542303,0.33261112772430493331,0.14876762006038398086)
POLY_B=(0.81648515205385221995,0.27136515484240234115,0.12756148214815175348,0.044753028579153842218)
def product(rows,operand,out_bits,operand_bits,limit):
    acc=np.zeros_like(xs)
    for ctl,w in rows:
        e=out_bits-operand_bits+w
        acc+=ctl*(operand<<e if e>=0 else operand>>-e)
    assert (acc<2**limit).all(), 'overflow'
    return acc

s=(WIDTH-(np.floor(np.log2(xs.astype(float))).astype(I64)+1))//2
xn=xs<<(2*s)
top,second,third=bit(xn,WIDTH-1),bit(xn,WIDTH-2),bit(xn,WIDTH-3)
cases=[POLY_A,POLY_B,[a/(2**j*math.sqrt(2)) for j,a in enumerate(POLY_A)],[b/(2**j*math.sqrt(2)) for j,b in enumerate(POLY_B)]]
table=np.array([[round(c*2**17) for c in case] for case in cases],dtype=I64)
c0,c1,c2,c3=(table[np.where(top==0,third,2+second),j] for j in range(4))
delta=[(top&third,-1)]+[(bit(xn,WIDTH-2-m),-m) for m in range(2,15)]
y0,mult=c0,c3
for acc in (c2,c1,c0):
    y0=mult=acc-product(delta,mult,17,17,17)
    assert ((y0>0)&(y0<2**17)).all(), 'horner'
wc=17
Y={k:bit(y0,wc-k) for k in range(1,wc+1)}
square=np.zeros_like(xs)
for k in range(1,wc+1):
    if 2*k<=28: square+=Y[k]<<(28-2*k)
    for l in range(k+1,wc+1):
        if k+l-1<=28: square+=(Y[k]&Y[l])<<(28-(k+l-1))
m_rows=[(bit(xn,i),i-WIDTH+2) for i in range(WIDTH)]
z=product(m_rows,square,28,28,30)
correction=(3<<28)-z
p=product([(Y[k],-k) for k in range(1,wc+1)],correction,29,28,30)
y=p<<s
print('pipeline ok; p max',int(p.max()),'y max',int(y.max()),file=sys.stderr)

basis={}
for j in range(41): basis[f'b{j:02d}']=np.load(f'work/p0_reports/data/bcols/col_{j:02d}.npy').astype(np.uint8)
for i in range(WIDTH): basis[f'x{i:02d}']=bit(xs,i).astype(np.uint8)
for k in range(4): basis[f's{k}']=bit(s,k).astype(np.uint8)
basis['top']=top.astype(np.uint8); basis['second']=second.astype(np.uint8); basis['third']=third.astype(np.uint8)
for nm,arr in [('c0',c0),('c1',c1),('c2',c2),('c3',c3)]:
    for bb in range(17): basis[f'{nm}_{bb:02d}']=bit(arr,bb).astype(np.uint8)
for k in range(1,18): basis[f'y{k:02d}']=Y[k].astype(np.uint8)
for bb in range(28): basis[f'sq{bb:02d}']=bit(square,bb).astype(np.uint8)
for bb in range(28): basis[f'z{bb:02d}']=bit(z,bb).astype(np.uint8)
for bb in range(29): basis[f'cr{bb:02d}']=bit(correction,bb).astype(np.uint8)
for bb in range(30): basis[f'p{bb:02d}']=bit(p,bb).astype(np.uint8)
names=list(basis); K=len(names)
print(f'full basis K={K}',file=sys.stderr)

rng=np.random.default_rng(2); idx=rng.choice(N,size=300000,replace=False)
B=np.stack([basis[nm][idx] for nm in names],axis=1).astype(np.uint8)
ybits=((y[idx].astype(U64)[:,None]>>np.arange(40,dtype=U64)[None,:])&1).astype(np.uint8)

new_bits=list(range(4,15))+list(range(22,30))
results={}
print(f'{"i":>3} {"T":>3}  form')
for i in new_bits:
    yi=ybits[:,i]; n1=int(yi.sum()); Ns=len(yi)
    if n1<=6 or n1>=Ns-6:
        results[i]=(0,'const'); print(f'{i:>3} {0:>3}  const'); continue
    idm=np.where((B==yi[:,None]).all(axis=0))[0]
    if len(idm): results[i]=(0,names[int(idm[0])]); print(f'{i:>3} {0:>3}  reuse {names[int(idm[0])]}'); continue
    notm=np.where(((1-B)==yi[:,None]).all(axis=0))[0]
    if len(notm): results[i]=(0,'NOT '+names[int(notm[0])]); print(f'{i:>3} {0:>3}  NOT {names[int(notm[0])]}'); continue
    fx=None
    for a in range(K):
        need=yi^B[:,a]
        m=np.where((B==need[:,None]).all(axis=0))[0]
        if len(m) and int(m[0])!=a: fx=(a,int(m[0])); break
    if fx: results[i]=(0,f'{names[fx[0]]} XOR {names[fx[1]]}'); print(f'{i:>3} {0:>3}  {names[fx[0]]} XOR {names[fx[1]]}'); continue
    cover=[a for a in range(K) if int((B[:,a]&yi).sum())==n1]
    fa=None
    for a in cover:
        Fa=(B[:,a]==1)&(yi==0)
        for b in cover:
            if b<=a: continue
            if int((B[:,b]&Fa).sum())!=0: continue
            if np.array_equal(B[:,a]&B[:,b],yi): fa=(a,b); break
        if fa: break
    if fa: results[i]=(1,f'{names[fa[0]]} AND {names[fa[1]]}'); print(f'{i:>3} {1:>3}  {names[fa[0]]} AND {names[fa[1]]}'); continue
    results[i]=(None,'NO <=2-gate form')
    print(f'{i:>3} {10:>3}  NO cheap form (generic mux ~10 T)')

known=[v[0] for v in results.values() if v[0] is not None]; unk=len(results)-len(known)
print(f'\ncheap(<=1 Toffoli): {len(known)}/{len(results)} ; no-cheap-form: {unk}')
print(f'R(option b) unknown=10T: {sum(known)+unk*10} ; unknown=3T: {sum(known)+unk*3}')
json.dump({str(k):list(v) for k,v in results.items()},open('work/pa_prexperiment/data/step5b_expr.json','w'),indent=1)
print('saved work/pa_prexperiment/data/step5b_expr.json')
