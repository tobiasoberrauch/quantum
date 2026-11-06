#!/usr/bin/env python3
"""Keep structural identities only: zero mismatches on v3 (1M, true dist) and on v1 (512k incl. 10% uniform weight), dense firing, L with >=2 wires."""
import numpy as np
v1rows=[l.rstrip('\n').split('\t') for l in open('out/c2_all.tsv')]
m1={r[1]:(int(a),int(b)) for r,a,b in zip(v1rows,np.load('out/v1_mis.npy'),np.load('out/v1_fires.npy'))}
rows=[l.rstrip('\n').split('\t') for l in open('out/c3.tsv')]
mis=np.load('out/v3_mis.npy'); fires=np.load('out/v3_fires.npy')
N=60*4*4096
out=[];rej=dict(mis=0,sparse=0,single=0,zero=0)
for r,m,f in zip(rows,mis,fires):
    a,b=m1[r[1]]
    if r[0]!='AB': continue
    L=r[8].split(',') if r[8] else []
    if m or a: rej['mis']+=1; continue
    if not L: rej['zero']+=1; continue
    if f<N/1000: rej['sparse']+=1; continue
    if len(L)==1: rej['single']+=1; continue
    out.append(r)
print('accepted',len(out),'rejected',rej)
with open('out/bank1.txt','w') as fh:
    for r in out:
        c=int(r[6]); items=[('X %d'%c) if int(w)==891 else ('CX %s %d'%(w,c)) for w in r[8].split(',')]
        fh.write(f"{r[1]}\t{';'.join(items)}\n")
for r in out[:12]: print(r[1],r[3:7],r[8],)
