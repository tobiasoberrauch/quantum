"""Step 5 (efficient): cheapest <=2-gate expression of the 22 non-overlapping y-bits
in terms of already-computed functions (41 tap controls + x/s/case bits). Bounds option-(b) R.
XOR/NOT/CX are FREE; AND costs 1 Toffoli. A y-bit with no cheap form would need a generic
11-way s-mux (~10 Toffolis lower bound)."""
import sys, json
import numpy as np
U64, I64 = np.uint64, np.int64
N = 3 * (2**10 - 2)**2
y = np.load('work/pa_prexperiment/data/y.npy')
s = np.load('work/pa_prexperiment/data/s.npy')
x = np.arange(1, N+1, dtype=I64)

# subsample for speed (a wrong form mismatches ~half the domain; 300k is decisive)
rng = np.random.default_rng(1)
idx = rng.choice(N, size=300000, replace=False)

def bit(v, i): return ((v.astype(I64) >> i) & 1).astype(np.uint8)

basis = {}
for j in range(41):
    basis[f'b{j:02d}'] = np.load(f'work/p0_reports/data/bcols/col_{j:02d}.npy').astype(np.uint8)[idx]
for i in range(22):
    basis[f'x{i:02d}'] = bit(x[idx], i)
for k in range(4):
    basis[f's{k}'] = bit(s[idx], k)
width = 22
sfull = (width - (np.floor(np.log2(x.astype(float))).astype(I64)+1))//2
xn = x << (2*sfull)
basis['top'] = bit(xn[idx], width-1); basis['second'] = bit(xn[idx], width-2); basis['third'] = bit(xn[idx], width-3)

names = list(basis)
K = len(names)
B = np.stack([basis[nm] for nm in names], axis=1).astype(np.uint8)   # [Ns, K]
ybits = ((y[idx].astype(U64)[:,None] >> np.arange(40,dtype=U64)[None,:]) & 1).astype(np.uint8)

new_bits = list(range(4,15)) + list(range(22,30)) + [37,38,39]
results = {}
print(f'{"i":>3} {"T":>3}  form')
for i in new_bits:
    yi = ybits[:, i]
    n1 = int(yi.sum()); Ns = len(yi)
    if n1 <= 6 or n1 >= Ns-6:      # (near-)constant on the sample -> free (don't tap / tap const)
        results[i]=(0,f'const {"1" if n1>Ns//2 else "0"} ({n1}/{Ns} ones)'); print(f'{i:>3} {0:>3}  const {("1" if n1>Ns//2 else "0")} ({n1}/{Ns})'); continue
    # 0-gate identity / NOT
    idm = np.where((B == yi[:,None]).all(axis=0))[0]
    if len(idm):
        results[i]=(0,names[int(idm[0])]); print(f'{i:>3} {0:>3}  reuse {names[int(idm[0])]}'); continue
    notm = np.where(((1-B) == yi[:,None]).all(axis=0))[0]
    if len(notm):
        results[i]=(0,'NOT '+names[int(notm[0])]); print(f'{i:>3} {0:>3}  NOT {names[int(notm[0])]}'); continue
    # free XOR of two
    fx=None
    for a in range(K):
        need = yi ^ B[:,a]
        m = np.where((B == need[:,None]).all(axis=0))[0]
        if len(m) and int(m[0])!=a:
            fx=(a,int(m[0])); break
    if fx:
        results[i]=(0,f'{names[fx[0]]} XOR {names[fx[1]]}'); print(f'{i:>3} {0:>3}  {names[fx[0]]} XOR {names[fx[1]]}'); continue
    # 1 Toffoli AND of two (cover-pruned)
    cover = [a for a in range(K) if int((B[:,a] & yi).sum()) == int(yi.sum())]  # B_a is 1 wherever yi is 1
    fa=None
    for a in cover:
        for b in cover:
            if b<=a: continue
            if np.array_equal(B[:,a]&B[:,b], yi):
                fa=(a,b); break
        if fa: break
    if fa:
        results[i]=(1,f'{names[fa[0]]} AND {names[fa[1]]}'); print(f'{i:>3} {1:>3}  {names[fa[0]]} AND {names[fa[1]]}'); continue
    results[i]=(None,'NO cheap form -> generic 11-way s-mux (~10 T)')
    print(f'{i:>3} {10:>3}  NO cheap form (generic mux ~10 T)')

known=[v[0] for v in results.values() if v[0] is not None]
unk=len(results)-len(known)
print(f'\ncheap forms: {len(known)}/{len(results)} ; no-cheap-form: {unk}')
print(f'R(option b) pessimistic (unknown=10T): {sum(known)+unk*10}')
print(f'R(option b) optimistic  (unknown=3T):  {sum(known)+unk*3}')
json.dump({str(k):list(v) for k,v in results.items()}, open('work/pa_prexperiment/data/step5_expr.json','w'), indent=1)
print('saved work/pa_prexperiment/data/step5_expr.json')
