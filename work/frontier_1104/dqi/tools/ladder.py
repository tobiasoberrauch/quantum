#!/usr/bin/env python3
"""Census: 3q gates whose exact triple recurs soon with target-not-read patterns. Class by zero-wire availability."""
import sys, numpy as np
from collections import Counter, defaultdict
Z=np.loadtxt(sys.argv[1],dtype=np.int64,usecols=(0,1,3,4,5,6,7),delimiter='\t')
ty=np.array([int(l.split('\t')[2],16) for l in open(sys.argv[1])])
op,g,a,b,c,nz,tz=Z.T
print('gates',len(op))
# find pairs: same triple (a,b,c) reoccurs, with gap in gates <= 64, c may be read between (dirty/pebble), a,b not changed unknown
last={}
pairs=0; dirty_pairs=0; dirty_with_clean=0; hist=Counter()
gaps=Counter()
mark=np.zeros(len(op),bool)
for i in range(len(op)):
    if ty[i]!=0x31: continue
    k=(a[i],b[i],c[i])
    j=last.get(k)
    if j is not None and i-j<=64:
        pairs+=1; gaps[i-j]+=1
        mark[i]=mark[j]=True
        if not tz[j]:
            dirty_pairs+=1
            if nz[j]>=1: dirty_with_clean+=1
    last[k]=i
print('pairs',pairs,'dirty_pairs(target nonzero before first)',dirty_pairs,'with_clean_available',dirty_with_clean)
print('gates in pairs',mark.sum())
print('gap hist',sorted(gaps.items())[:30])
