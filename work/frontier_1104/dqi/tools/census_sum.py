#!/usr/bin/env python3
"""Join census results with block tags and summarise."""
import bisect, importlib.util, sys
from collections import Counter, defaultdict
import numpy as np
ROOT='/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum'
spec=importlib.util.spec_from_file_location('wl',f'{ROOT}/work/dqi_sources/width_liveness.py'); wl=importlib.util.module_from_spec(spec); spec.loader.exec_module(wl)
r=wl.KmbReader(sys.argv[1])
t=r.types
tagpos=np.flatnonzero(t==6).tolist()
evs=[(p,s) for p,s in zip(tagpos,r.tag_strings)]
roots=['extract','unextract','synthesis','unsynthesis','convert','unconvert','scan','initial','uninitial']
ranges=[]
op={}
for p,s in evs:
    if s.startswith('@enter:'):
        n=s.split(':',1)[1]
        if n in roots: op[n]=p
    elif s.startswith('@exit:'):
        n=s.split(':',1)[1]
        if n in op: ranges.append((op.pop(n),p,n))
ranges.sort(); los=[x[0] for x in ranges]
def block(p):
    i=bisect.bisect_right(los,p)-1
    if i<0: return 'pre'
    return ranges[i][2] if p<ranges[i][1] else 'gap'
C=defaultdict(Counter)
for line in open(sys.argv[2]):
    f=line.split('\t'); o=int(f[0]); ty=int(f[2],16); z,one,sa,sp,tz,pz,eq=map(int,f[6:13])
    b=block(o); nm={0x31:'CCX',0x30:'CCZ',0x32:'CSWAP'}[ty]
    C[b]['n_'+nm]+=1
    if z: C[b]['zero_'+nm]+=1
    if sa and not z: C[b]['span_ab_'+nm]+=1
    if sp and not (sa or z): C[b]['span_post_only_'+nm]+=1
    if pz: C[b]['post_zero_'+nm]+=1
    if tz: C[b]['t_zero_'+nm]+=1
tot=Counter()
for b in sorted(C):
    print(b,dict(sorted(C[b].items()))); tot.update(C[b])
print('TOTAL',dict(sorted(tot.items())))
