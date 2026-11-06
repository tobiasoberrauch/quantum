"""Refined diagnostic: distinguish ZERO vs COMPLEX(None); dump simple CCX gates."""
from collections import defaultdict, Counter
from symbolic_pass import parse_ops, ZERO, ONE

def _x(a,b):
    if a is None or b is None: return None
    return a ^ b
def _a(a,b):
    if a is None or b is None: return None
    if len(a)*len(b) > 400000: return None
    out=defaultdict(int)
    for m1 in a:
        for m2 in b: out[m1|m2]+=1
    return frozenset(m for m,c in out.items() if c%2)
def kind(a):
    if a is None: return 'C'
    if a == ZERO: return '0'
    return str(len(a))
def canon(anf):
    if anf is None: return None
    return tuple(sorted(tuple(sorted(m)) for m in anf))

ops = parse_ops('work/invsqrt_caching/invsqrt.kmx')
val={}
def get(w): return val.get(w,ZERO)
def setw(w,a): val[w]=a
nv=0
for i in range(22):
    w=f'q{i}'; nv+=1; setw(w,frozenset({frozenset([nv-1])}))
stack=[]
def eff(cb):
    a=ONE
    for s in stack:
        a=_a(a,s)
        if a is None: return None
    if cb is not None: a=_a(a,get(cb))
    return a

ccx_kind=Counter(); simple_ccx=[]
for idx,(op,args,cb) in enumerate(ops):
    if op=='PUSH_CONDITION':
        c=cb if cb is not None else (args[0] if args else None)
        stack.append(get(c) if c is not None else ONE); continue
    if op=='POP_CONDITION': stack.pop(); continue
    if op in ('APPEND_TO_REGISTER','REGISTER'): continue
    cond=eff(cb)
    if op=='X': t=args[0]; setw(t,_x(get(t),ONE))
    elif op in ('Z','NEG','Z_POW'): pass
    elif op=='CX': c,t=args; setw(t,_x(get(t),get(c)))
    elif op=='CZ': pass
    elif op=='CCX':
        c1,c2,t=args
        ccx_kind[(kind(get(c1)),kind(get(c2)),kind(cond))]+=1
        a1,a2=get(c1),get(c2)
        if a1 is not None and a2 is not None and len(a1)<=8 and len(a2)<=8:
            simple_ccx.append((idx,c1,c2,t,cond,canon(a1),canon(a2)))
    elif op=='CCZ': pass
    elif op=='SWAP':
        a,b=args; va,vb=get(a),get(b); setw(a,vb); setw(b,va)
    elif op=='CSWAP':
        c,a,b=args; d=_x(get(a),get(b)); p=_a(get(c),d); setw(a,_x(get(a),p)); setw(b,_x(get(b),p))
    elif op=='HMR':
        q,b=args; nv+=1; setw(b,frozenset({frozenset([nv-1])})); setw(q,ZERO)
    elif op=='R': setw(args[0],ZERO)
    elif op=='BIT_STORE0': setw(args[0],ZERO)
    elif op=='BIT_STORE1': setw(args[0],ONE)
    elif op=='BIT_INVERT': b=args[0]; setw(b,_x(get(b),ONE))

print('CCX (kind(c1), kind(c2), kind(cond)) : count   [C=complex, 0=zero, N=size]')
for k,v in sorted(ccx_kind.items(), key=lambda kv:-kv[1]): print(f'  {k}: {v}')
print(f'\nSIMPLE CCX gates (both controls size<=8): {len(simple_ccx)}')
for idx,c1,c2,t,cond,a1c,a2c in simple_ccx:
    print(f'  idx={idx:5d} {c1:>4} {c2:>4} -> {t:<4} cond={kind(cond)} | c1={a1c} | c2={a2c}')

# group by unordered control-ANF pair + cond
grp=defaultdict(list)
for idx,c1,c2,t,cond,a1c,a2c in simple_ccx:
    key=(tuple(sorted([a1c,a2c])), canon(cond))
    grp[key].append(idx)
print(f'\nDistinct simple-product signatures: {len(grp)}; repeated (size>=2): {sum(1 for v in grp.values() if len(v)>=2)}')
for k,v in grp.items():
    if len(v)>=2: print('  REPEAT:', k, '->', v)
