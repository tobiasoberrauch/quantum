#!/usr/bin/env python3
"""Build a shot file enriched in rare-branch shots. Usage: build_rich.py <base.kmb> <out.bin> <nshots> <P> <batches_per_proc>"""
import os, struct, subprocess, sys
import numpy as np
from concurrent.futures import ThreadPoolExecutor
PY=sys.executable
base,out,nshots,P,NB=sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4]),int(sys.argv[5])
cnt=np.load('out/rates_total.npy')
rare=(cnt<=2000).astype(np.uint8); rare.tofile('out/rare.u8')
print('rare gates',int(rare.sum()))
def one(p):
    got=[]
    for i in range(NB):
        s=3000000+p*1000+i
        f=f'out/tmp_rich_{p}.bin'
        subprocess.run([PY,'tools/gen_shots.py',base,f,'4096',str(s),'0.0'],check=True,stdout=subprocess.DEVNULL)
        m=f'out/tmp_mask_{p}.bin'
        subprocess.run(['tools/raremask',base,f,'out/rare.u8',str(s),m],check=True,stdout=subprocess.DEVNULL)
        mask=np.fromfile(m,dtype=np.uint64)
        idx=[w*64+b for w,x in enumerate(mask) for b in range(64) if (int(x)>>b)&1]
        with open(f,'rb') as fh:
            nq,nb,W,n=struct.unpack('<4Q',fh.read(32))
            arr=np.frombuffer(fh.read(8*(nq+nb)*W),dtype=np.uint64).reshape(nq+nb,W)
        keep_rows=np.flatnonzero((arr!=0).any(axis=1))
        for sh in idx:
            w,b=sh//64,sh%64
            got.append(((arr[keep_rows,w]>>np.uint64(b))&np.uint64(1)).astype(np.uint8).copy() if False else (keep_rows,((arr[keep_rows,w]>>np.uint64(b))&np.uint64(1)).astype(np.uint8)))
        os.unlink(f); os.unlink(m)
    return nq,nb,got
with ThreadPoolExecutor(P) as ex:
    res=list(ex.map(one,range(P)))
nq,nb=res[0][0],res[0][1]
rich=[g for r in res for g in r[2]]
print('rare shots harvested',len(rich))
# dense shots
d=f'out/tmp_dense.bin'
W=nshots//64
import random
random.seed(5)
random.shuffle(rich)
n_dense=1024
n_dense=n_dense-n_dense%64
subprocess.run([PY,'tools/gen_shots.py',base,d,str(max(n_dense,64)),'7003','0.25'],check=True,stdout=subprocess.DEVNULL)
with open(d,'rb') as fh:
    _,_,Wd,nd=struct.unpack('<4Q',fh.read(32))
    dense=np.frombuffer(fh.read(8*(nq+nb)*Wd),dtype=np.uint64).reshape(nq+nb,Wd)
os.unlink(d)
A=np.zeros((nq+nb,W),dtype=np.uint64)
A[:,:min(Wd,W)]=dense[:,:min(Wd,W)]
pos=n_dense
sel=rich[:nshots-pos]
for s,(rows,bits) in enumerate(sel):
    sh=pos+s; w,b=sh//64,sh%64
    A[:,w]&=~(np.uint64(1)<<np.uint64(b))
    A[rows,w]|=bits.astype(np.uint64)<<np.uint64(b)
with open(out,'wb') as f:
    f.write(struct.pack('<4Q',nq,nb,W,nshots)); f.write(A.tobytes()); f.write(np.zeros(W,dtype=np.uint64).tobytes())
print('wrote',out,'dense',pos,'rare',len(sel))
