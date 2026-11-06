#!/usr/bin/env python3
import bisect, importlib.util, sys
from collections import Counter, defaultdict
import numpy as np
ROOT='/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum'
spec=importlib.util.spec_from_file_location('wl',f'{ROOT}/work/dqi_sources/width_liveness.py'); wl=importlib.util.module_from_spec(spec); spec.loader.exec_module(wl)
r=wl.KmbReader('base.kmb')
cnt=np.zeros(r.n3q,dtype=np.uint64)
for p in range(5): cnt+=np.fromfile(f'out/rates_{p}.u32',dtype=np.uint32)
np.save('out/rates_total.npy',cnt)
N=50*5*4096
rows=[l.split('\t') for l in open('out/census_all.tsv')]
ops=np.array([int(x[0]) for x in rows]); ty=np.array([int(x[2],16) for x in rows])
evs=[(p,s) for p,s in zip(np.flatnonzero(r.types==6).tolist(),r.tag_strings)]
roots=['extract','unextract','synthesis','unsynthesis','convert','unconvert','scan','initial','uninitial']
ranges=[];opn={}
for p,s in evs:
    n=s.split(':',1)[1]
    if s.startswith('@enter:') and n in roots: opn[n]=p
    elif s.startswith('@exit:') and n in opn: ranges.append((opn.pop(n),p,n))
ranges.sort(); los=[x[0] for x in ranges]
def block(p):
    i=bisect.bisect_right(los,p)-1
    if i<0: return 'pre'
    return ranges[i][2] if p<ranges[i][1] else 'gap'
blk=np.array([block(int(o)) for o in ops])
edges=[0,1,2,5,10,30,100,300,1000,3000,10000,30000,100000,300000,1e12]
print('N',N)
print('rate bucket (count upper) -> gates by kind')
for t,nm in ((0x31,'CCX'),(0x32,'CSWAP'),(0x30,'CCZ')):
    h=np.histogram(cnt[ty==t].astype(float),bins=edges)[0]
    print(nm,list(zip(edges,h)))
for b in sorted(set(blk)):
    m=blk==b
    print(b,'n',m.sum(),'zero',int((cnt[m]==0).sum()),'lt30',int((cnt[m]<30).sum()),'lt1000',int((cnt[m]<1000).sum()),'lt10000',int((cnt[m]<10000).sum()))
order=np.sort(cnt.astype(float))
cum=np.cumsum(order)
for g in (1000,2000,4000,6000,8000,10000,12000,15000,17000,20000,25000,30000):
    print('prune',g,'gates: max count',order[g-1],'sum fires',cum[g-1],'upper bound fail rate',cum[g-1]/N)
