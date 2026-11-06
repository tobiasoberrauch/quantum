import sys
import numpy as np
import bsim
ops,_=bsim.parse_kmx(sys.argv[1])
sites=[int(v) for v in sys.argv[2].split(',')]
xs=bsim.domain()
s=bsim.State(xs,4)
col=lambda a:int.from_bytes(a.tobytes(),'little')
allset=col(np.full(s.w,bsim.ONES,dtype=np.uint64))
def rel():
    piv={}
    deps=[]
    names=[('ONE',allset)]+[(k,col(s.q[k])) for k in range(62)]
    tags=[]
    for i,(n,v) in enumerate(names):
        tag=1<<i
        while v:
            h=v.bit_length()-1
            if h in piv:
                v^=piv[h][0]; tag^=piv[h][1]
            else:
                piv[h]=(v,tag); break
        if v==0:
            deps.append([names[j][0] for j in range(len(names)) if (tag>>j)&1])
    return deps
for op in ops:
    if op.line in sites:
        d=rel()
        print(op.line,op.raw[:30],'live',int(s.q.any(axis=1).sum()),'deps (nonzero rel):',[x for x in d if len(x)>1][:6], 'zero wires',[k for k in range(62) if not s.q[k].any()][:10],flush=True)
    bsim.step(s,op)
