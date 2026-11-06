"""Diagnostic: distribution of ANF size/degree on CCX/CCZ/CSWAP control wires."""
import sys
from collections import defaultdict, Counter
sys.path.insert(0, 'work/invsqrt_caching')
import importlib.util
spec = importlib.util.spec_from_file_location('sp', 'work/invsqrt_caching/symbolic_pass.py')
# reuse parse + core by re-implementing minimal walk with NO cap, measuring only
from symbolic_pass import parse_ops, ZERO, ONE

def _x(a,b):
    if a is None or b is None: return None
    return a ^ b
def _a(a,b):
    if a is None or b is None: return None
    if len(a)*len(b) > 400000: return None   # guard: too big to expand
    out=defaultdict(int)
    for m1 in a:
        for m2 in b: out[m1|m2]+=1
    return frozenset(m for m,c in out.items() if c%2)

ops = parse_ops('work/invsqrt_caching/invsqrt.kmx')
val = {}
def get(w): return val.get(w, ZERO)
def setw(w,a): val[w]=a
next_var=0
for i in range(22):
    w=f'q{i}'; next_var+=1; setw(w, frozenset({frozenset([next_var-1])}))
cond_stack=[]
def eff(cb):
    a=ONE
    for s in cond_stack:
        a=_a(a,s)
        if a is None: return None
    if cb is not None: a=_a(a,get(cb))
    return a

ccx_ctrl_sizes=Counter(); ccz_ctrl_sizes=Counter(); cswap_ctrl_sizes=Counter()
cond_sizes=Counter()
maxsize=0
def sz(a): return 0 if a is None else len(a)
def deg(a): return 0 if a is None else max((len(m) for m in a), default=0)

for idx,(op,args,cb) in enumerate(ops):
    if op=='PUSH_CONDITION':
        c=cb if cb is not None else (args[0] if args else None)
        cond_stack.append(get(c) if c is not None else ONE); continue
    if op=='POP_CONDITION': cond_stack.pop(); continue
    if op in ('APPEND_TO_REGISTER','REGISTER'): continue
    cond=eff(cb)
    if op=='X': t=args[0]; setw(t,_x(get(t),ONE))
    elif op in ('Z','NEG','Z_POW'): pass
    elif op=='CX': c,t=args; setw(t,_x(get(t),get(c)))
    elif op=='CZ': pass
    elif op=='CCX':
        c1,c2,t=args
        ccx_ctrl_sizes[(sz(get(c1)),sz(get(c2)))]+=1
        prod=_a(get(c1),get(c2)); setw(t,_x(get(t),prod))
        maxsize=max(maxsize,sz(get(c1)),sz(get(c2)),sz(prod))
    elif op=='CCZ':
        c1,c2,c3=args
        ccz_ctrl_sizes[(sz(get(c1)),sz(get(c2)),sz(get(c3)))]+=1
    elif op=='SWAP':
        a,b=args; va,vb=get(a),get(b); setw(a,vb); setw(b,va)
    elif op=='CSWAP':
        c,a,b=args
        cswap_ctrl_sizes[(sz(get(c)),sz(get(a)),sz(get(b)))]+=1
        d=_x(get(a),get(b)); prod=_a(get(c),d); setw(a,_x(get(a),prod)); setw(b,_x(get(b),prod))
    elif op=='HMR':
        q,b=args; next_var+=1; setw(b,frozenset({frozenset([next_var-1])})); setw(q,ZERO)
    elif op=='R': setw(args[0],ZERO)
    elif op=='BIT_STORE0': setw(args[0],ZERO)
    elif op=='BIT_STORE1': setw(args[0],ONE)
    elif op=='BIT_INVERT': b=args[0]; setw(b,_x(get(b),ONE))

print('max ANF size seen:', maxsize)
print('\nCCX control-size pairs (|c1|,|c2|) : count   [top 25]')
for k,v in ccx_ctrl_sizes.most_common(25): print(f'  {k}: {v}')
print('\nCCZ control-size triples (|c1|,|c2|,|c3|) : count [top 25]')
for k,v in ccz_ctrl_sizes.most_common(25): print(f'  {k}: {v}')
print('\nCSWAP control-size triples (|c|,|a|,|b|) : count [top 25]')
for k,v in cswap_ctrl_sizes.most_common(25): print(f'  {k}: {v}')
