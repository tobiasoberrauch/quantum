#!/usr/bin/env python3
"""From true-distribution census: new candidates (dense product in span) not already in c2_all / rejected; writes cand mask."""
import glob
import numpy as np
cnt=np.load('out/rates_total.npy')
rows=[]
for p in glob.glob('out/tc_?.tsv'):
    rows+= [l.split('\t') for l in open(p)]
rows.sort(key=lambda x:int(x[1]))
print(len(rows))
g=np.array([int(x[1]) for x in rows]); z=np.array([int(x[6]) for x in rows]); sa=np.array([int(x[8]) for x in rows]); sp=np.array([int(x[9]) for x in rows]); ty=np.array([int(x[2],16) for x in rows])
old=set(l.split('\t')[2] for l in open('out/c2_all.tsv'))
print('zero',(z!=0).sum(),'span_ab',((sa!=0)&(z==0)).sum(),'span_post',((sp!=0)&(sa==0)&(z==0)).sum())
new=((sa!=0)|(sp!=0))&(z==0)
isold=np.array([str(x) in old for x in g])
print('new not in old',(new&~isold).sum())
mask=np.zeros(len(cnt),dtype=np.uint8)
# dense only: gate fires at >= 0.1% (sparse hits are chance-level fits)
dense=cnt[g]>=1024
m2=new&dense
print('dense span hits',m2.sum(),'of which new',(m2&~isold).sum())
mask[g[m2]]=1
mask.tofile('out/cand_true.u8')
