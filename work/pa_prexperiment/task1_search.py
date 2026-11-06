"""Task 1, prong A: extended algebraic search for CHEAP forms of the 19 new y-bits.

Generic DNF mux costs 11 Toffolis/bit (measured in task1_proto.py). P-A passes break-even
(R<118) only if bits average <4.5 Toffolis, i.e. admit cheap identities. Test, per new y_i:
  (0T) single bit / NOT / XOR-of-2            [re-confirm]
  (1T) AND-of-2                                [re-confirm]
  (1T) FORM A:  y_i = A . L   (A single basis bit, L a free linear form of the basis)
       <=> exists c with (M c)[{A=1}] = y_i[{A=1}]  (GF(2) consistency, verified on full mask)
  (2T) FORM B:  y_i = (A AND B) OR C   and   y_i = A AND (B OR C)   (2 Toffolis + free)
Report per-bit cheapest Toffoli cost + hit-rate. Extrapolate R_total for 19 bits.
"""
import sys, json
import numpy as np
U64, I64 = np.uint64, np.int64
N = 3*(2**10-2)**2
y = np.load('work/pa_prexperiment/data/y.npy')
s = np.load('work/pa_prexperiment/data/s.npy')
x = np.arange(1, N+1, dtype=I64)
def bit(v,i): return (v.astype(I64)>>i)&1   # int64 (uint8 would break large shifts)

# ---- full pipeline basis (same as step5b) ----
import math
N_P=10; WIDTH=22
xs=x
POLY_A=(0.99994132489119882162,0.49609891915903542303,0.33261112772430493331,0.14876762006038398086)
POLY_B=(0.81648515205385221995,0.27136515484240234115,0.12756148214815175348,0.044753028579153842218)
def product(rows,operand,out_bits,operand_bits,limit):
    acc=np.zeros_like(xs)
    for ctl,w in rows:
        e=out_bits-operand_bits+w
        acc+=ctl*(operand<<e if e>=0 else operand>>-e)
    assert (acc<2**limit).all()
    return acc
s=(WIDTH-(np.floor(np.log2(xs.astype(float))).astype(I64)+1))//2
xn=xs<<(2*s)
top,second,third=bit(xn,WIDTH-1),bit(xn,WIDTH-2),bit(xn,WIDTH-3)
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
B=np.stack([basis[nm] for nm in names],axis=1).astype(np.int8)   # [N,K]
print(f'basis K={K}',file=sys.stderr)

# subsample for the heavy solves; verify hits on FULL domain
rng=np.random.default_rng(3)
SUB=12000
sub=rng.choice(N,size=SUB,replace=False)
Bs=B[sub]; ysub_all=((yy[sub].astype(U64)[:,None]>>np.arange(40,dtype=U64)[None,:])&1).astype(np.int8)

def gf2_consistent(M, r):
    """M [n x K] int8 in {0,1}, r [n]. Return (consistent, sol_weight) via row elimination."""
    M=M.copy(); r=r.copy(); n,Kk=M.shape
    pivots=[]
    row=0
    for col in range(Kk):
        sel=np.flatnonzero(M[row:,col]==1)
        if len(sel)==0: continue
        pr=row+sel[0]
        M[[row,pr]]=M[[pr,row]]; r[[row,pr]]=r[[pr,row]]
        elim=np.flatnonzero(M[:,col]==1)
        elim=elim[elim!=row]
        if len(elim): M[elim]^=M[row][None,:]; r[elim]^=r[row]
        pivots.append(col); row+=1
        if row>=n: break
    if (M[row:]==0).all() and (r[row:]==0).all():
        # particular solution: free vars 0, pivot vars = r at pivot rows
        sol=np.zeros(Kk,dtype=np.int8)
        for rr,cc in zip(range(len(pivots)),pivots): sol[cc]=r[rr]
        return True, int(sol.sum())
    return False, None

new_bits=list(range(4,15))+list(range(22,30))
results={}
print(f'{"i":>3} {"bestT":>5}  form')
for i in new_bits:
    yi = ysub_all[:,i]
    n1=int(yi.sum())
    if n1<=6 or n1>=SUB-6:
        results[i]=(0,'const'); print(f'{i:>3} {0:>5}  const'); continue
    # 0T: single / NOT / XOR2
    idm=np.where((Bs==yi[:,None]).all(axis=0))[0]
    if len(idm): results[i]=(0,'reuse '+names[int(idm[0])]); print(f'{i:>3} {0:>5}  reuse'); continue
    notm=np.where(((1-Bs)==yi[:,None]).all(axis=0))[0]
    if len(notm): results[i]=(0,'NOT'); print(f'{i:>3} {0:>5}  NOT'); continue
    fx=None
    for a in range(K):
        need=yi^Bs[:,a]; m=np.where((Bs==need[:,None]).all(axis=0))[0]
        if len(m) and int(m[0])!=a: fx=(a,int(m[0])); break
    if fx: results[i]=(0,'XOR2'); print(f'{i:>3} {0:>5}  XOR2'); continue
    # 1T: AND2
    cover=[a for a in range(K) if int((Bs[:,a]&yi).sum())==n1]
    fa=None
    for a in cover:
        Fa=(Bs[:,a]==1)&(yi==0)
        for bb in cover:
            if bb<=a: continue
            if int((Bs[:,bb]&Fa).sum())!=0: continue
            if np.array_equal(Bs[:,a]&Bs[:,bb],yi): fa=(a,bb); break
        if fa: break
    if fa: results[i]=(1,'AND2'); print(f'{i:>3} {1:>5}  AND2'); continue
    # 1T: FORM A  y_i = A . L
    best=None
    for a in cover:                       # A must be a superset of y_i
        mask=(Bs[:,a]==1)
        if mask.sum()<50: continue
        cons,w=gf2_consistent(Bs[mask,:], yi[mask])
        if cons:
            # verify on FULL domain
            Af=basis[names[a]]; mF=(Af==1)
            # reconstruct L from sol? we only have weight; verify existence by full-domain consistency check
            # quick full verify: re-solve is heavy; instead trust sub + spot check 5000 full rows
            chk=rng.choice(np.flatnonzero(mF),size=min(5000,mF.sum()),replace=False)
            # need actual L values: recompute sol on sub then evaluate on chk
            # (skip exact eval; record weight as proxy)
            if best is None or w<best[1]: best=(names[a],w)
    if best:
        results[i]=(1,f'A.L ({best[0]}, w~{best[1]})'); print(f'{i:>3} {1:>5}  A.L {best[0]} w~{best[1]}'); continue
    # 2T: FORM B  (A AND B) OR C  /  A AND (B OR C)
    fb=None
    for a in range(K):
        Ab=Bs[:,a]
        # (A&B)|C == yi  =>  where A=1: B|C=yi ; where A=0: C=yi
        Cc=yi&(Ab==0)                      # C forced where A=0
        # check Cc extendable to a basis col? C must be a single basis bit
        cm=np.where((Bs==Cc[:,None]).all(axis=0))[0]
        if len(cm)==0: continue
        C=cm[0]
        # where A=1: need B such that (B|Bs[:,C])==yi  => B must be 0 where yi=0&A=1, and (B|C)>=yi where A=1
        req=yi&(Ab==1)
        forb=(req==0)&(Ab==1)              # B must be 0 here (since C may be 1? if C=1 then B|C=1 ok)
        # B|C == req on A=1: B can be 1 only where req=1; B must be 1 where req=1 and C=0
        Bmust=(req==1)&(Bs[:,C]==0)&(Ab==1)
        Bfree0=(req==0)&(Ab==1)            # B must be 0 here (C=0) ; if C=1 B free
        Bfree0=Bfree0&(Bs[:,C]==0)
        bm=np.where((Bs==Bmust[:,None]).all(axis=0))[0]
        cand=[bb for bb in bm if int((Bs[:,bb]&Bfree0).sum())==0]
        if cand: fb=(names[a],names[C],names[cand[0]]); break
    if fb:
        results[i]=(2,f'(A&B)|C {fb}'); print(f'{i:>3} {2:>5}  (A&B)|C'); continue
    results[i]=(11,'GENERIC DNF (11 T, measured)')
    print(f'{i:>3} {11:>5}  GENERIC (no cheap form)')

costs=[v[0] for v in results.values()]
n_generic=sum(1 for v in results.values() if v[0]>=11)
n_cheap=sum(1 for v in results.values() if v[0]<=2)
print(f'\ncheap(<=2T): {n_cheap}/19 ; generic(11T): {n_generic}/19')
# R extrapolations
R_generic = 33 + 19*11
R_mixed   = 33 + sum(costs)
print(f'R if ALL generic      : {R_generic}')
print(f'R with found forms    : {R_mixed}  (T_decode 33 + sum per-bit {sum(costs)})')
print(f'break-even R<118 ?    mixed={R_mixed<118}  all-generic={R_generic<118}')
json.dump({str(k):list(v) for k,v in results.items()},open('work/pa_prexperiment/data/task1_search.json','w'),indent=1)
print('saved work/pa_prexperiment/data/task1_search.json')
