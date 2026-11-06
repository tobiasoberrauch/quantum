"""Definitive R_total: build the generic s-router for ALL 19 new y-bits in-circuit
and measure total APPLIED toffolis (num_toffoli_like). Per-bit term count is NOT
uniform: y_i = p_{i-s}, valid k satisfy 0<=i-k<=29 and 0<=k<=10 -> count_i terms.
Low bits (i=4..9) have fewer terms than 11.
"""
import sys, json
import numpy as np
import kickmix as km
U64, I64 = np.uint64, np.int64
N = 3*(2**10-2)**2
p_all = np.load('work/pa_prexperiment/data/p.npy')
s_all = np.load('work/pa_prexperiment/data/s.npy')
P_W, S_W = 30, 4
KS = list(range(0,11))
NEW_BITS = list(range(4,15)) + list(range(22,30))   # 19 bits

def valid_terms(i):
    return [k for k in KS if 0 <= i-k <= P_W-1]

def build_router(test_bits):
    b = km.CircuitBuilder()
    P = b.create_quantum_register(P_W,'P'); S = b.create_quantum_register(S_W,'S')
    Snot = b.alloc_qubits(S_W)
    for m in range(S_W): b.x(Snot[m]); b.cx(S[m],Snot[m])
    def literal(m,val): return S[m] if val else Snot[m]
    eq = {}
    for k in KS:
        e = b.alloc_qubits(1)[0]; b.cx(literal(0,k&1), e)   # e = lit_0 (free)
        for m in range(1,S_W):
            t = b.alloc_qubits(1)[0]; b.ccx(e,literal(m,(k>>m)&1),t); b.hmr(e,b.alloc_bits(1)[0]); e=t
        eq[k]=e
    accs={}
    for i in test_bits:
        A=b.alloc_qubits(1)[0]
        for k in valid_terms(i):
            t=b.alloc_qubits(1)[0]; b.ccx(eq[k],P[i-k],t); b.cx(t,A); b.hmr(t,b.alloc_bits(1)[0])
        accs[i]=A
    return b.finish_circuit(), P, S, accs

def measure(circ,P,S,accs,idx):
    pp=p_all[idx]; ss=s_all[idx]
    inq=km.array(list(P)+list(S))
    pin=np.zeros((P_W+S_W,len(idx)),dtype=bool)
    for j in range(P_W): pin[j]=((pp>>j)&1).astype(bool)
    for m in range(S_W): pin[P_W+m]=((ss>>m)&1).astype(bool)
    BS=1024
    sim=km.Simulator(batch_size=BS,debug_print=False,counting_operations=True,seed=0)
    ok=True
    for st in range(0,len(idx),BS):
        en=min(st+BS,len(idx)); sim.clear_for_shot(); sim.write_across_shots(inq,pin[:,st:en]); sim.do(circ)
        for i,A in accs.items():
            got=sim.read_across_shots(km.array([A]))[0]
            want=((pp[st:en]>>(i-ss[st:en]))&1).astype(bool)
            ok=ok and bool(np.array_equal(got,want))
    return int(sim.operation_statistics().num_toffoli_like)/len(idx), ok

rng=np.random.default_rng(0)
sel=[]
for sv in range(11):
    cls=np.flatnonzero(s_all==sv)
    sel.append(rng.choice(cls,size=min(len(cls),max(30,int(0.05*len(cls)))),replace=False))
idx=np.concatenate(sel); rng.shuffle(idx)
BS=1024; target=int(np.ceil(len(idx)/BS))*BS
if len(idx)<target: idx=np.concatenate([idx,rng.choice(idx,size=target-len(idx),replace=True)])
idx=idx[:target]
print(f'sample n={len(idx)}',file=sys.stderr)

# baseline decode-only
c0,P0,S0,a0=build_router([]); t0,ok0=measure(c0,P0,S0,{},idx)
# all 19
c19,P19,S19,a19=build_router(NEW_BITS); t19,ok19=measure(c19,P19,S19,a19,idx)
R_total=t19-t0
term_counts={i:len(valid_terms(i)) for i in NEW_BITS}
sum_terms=sum(term_counts.values())
print(f'T_decode={t0:.2f}  all-19 total={t19:.2f}  R_total(measured)={R_total:.2f}  correct={ok19}')
print(f'per-bit valid-term counts: {term_counts}')
print(f'sum of term counts={sum_terms}  (+T_decode {t0:.0f} = {sum_terms+t0:.0f})  [should equal measured R_total]')
json.dump({'T_decode':round(t0,2),'R_total_measured':round(R_total,2),'correct':bool(ok19),
           'per_bit_terms':{str(k):v for k,v in term_counts.items()},
           'sum_terms':sum_terms,'break_even_R<118':bool(R_total<118),'gate_R<200':bool(R_total<200)},
          open('work/pa_prexperiment/data/task1_all19.json','w'),indent=1)
print('saved work/pa_prexperiment/data/task1_all19.json')
