#!/usr/bin/env python3
"""make_edits.py cands.tsv mis.npy out_edits.txt: emit gate replacements for identities with zero mismatches and at least min_fires."""
import sys
import numpy as np
cands,misf,firesf,out,minf=sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4],int(sys.argv[5])
NQ=891
rows=[l.rstrip('\n').split('\t') for l in open(cands)]
mis=np.load(misf); fires=np.load(firesf)
n=0
with open(out,'w') as f:
    for r,m,fi in zip(rows,mis,fires):
        if m!=0 or fi<minf: continue
        tag,op,g,ty,a,b,c=r[0],int(r[1]),r[2],r[3],int(r[4]),int(r[5]),int(r[6])
        L=[int(x) for x in r[8].split(',')] if r[8] else []
        if tag=='AB':
            items=[('X %d'%c) if w==NQ else ('CX %d %d'%(w,c)) for w in L] or ['DROP']
        elif tag=='CSWAP' and not L:
            items=['DROP']
        else:
            continue
        f.write(f"{op}\t{';'.join(items)}\n"); n+=1
print('edits',n)
