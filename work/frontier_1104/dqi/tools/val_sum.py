#!/usr/bin/env python3
import sys, numpy as np
from collections import Counter
tag=sys.argv[1]; cands=sys.argv[2]; P=int(sys.argv[3])
rows=[l.rstrip('\n').split('\t') for l in open(cands)]
mis=np.zeros(len(rows),dtype=np.int64); fires=np.zeros(len(rows),dtype=np.int64)
for p in range(P):
    mis+=np.fromfile(f'out/{tag}_mis_{p}.u32',dtype=np.uint32); fires+=np.fromfile(f'out/{tag}_fires_{p}.u32',dtype=np.uint32)
h=Counter()
for r,m,fi in zip(rows,mis,fires):
    b='fires0' if fi==0 else ('fires<10' if fi<10 else ('fires<300' if fi<300 else 'fires>=300'))
    h[(r[0],'OK' if m==0 else 'BAD',b)]+=1
for k in sorted(h): print(k,h[k])
np.save(f'out/{tag}_mis.npy',mis); np.save(f'out/{tag}_fires.npy',fires)
