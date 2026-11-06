"""Own v4 exact-expression chain caching with exact zero-fact scope provenance, motivated by credited Busya PRIME V16.

Adapted from our exact branch scanner; signatures nominate only, full opaque-
product affine vectors certify every identity. Cache wire zero/idle intervals
are certified conservatively including phase gates and disabled gates.
CSWAP uses the exact product control*(left XOR right).

Original scanner documentation: Exact branch-aware AND-retention on closed captured-classical scopes.

64-bit XOR signatures only nominate pairs. Every positive is certified by
comparing the complete affine bit-vectors over opaque exact product atoms.
Epoch resets forget facts. Unknown PUSH branches are tracked assuming the captured predicate true; exact unchanged quantum vectors are preserved at POP, changed ones become fresh independent variables. Cross-epoch branch merges preserve constants only. Copy and reuse must share the identical captured scope. Inline unknown guards remain conservative. A cache wire must
be exactly zero and have no quantum touch over the whole proposed interval.
This is an independent implementation of the public retained-product idea;
no public candidate binary or private scanner is used.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import time

import numpy as np
from numba import njit, types
from numba.typed import Dict

ROOT=Path(__file__).resolve().parents[1]
MAGIC=bytes.fromhex('d750c7d5c329d326e3cc9f6834f2b8bf')
DEFAULT=ROOT/'artifacts/continuation-retention-20261031-001/bridge902-native-171-001/dqi.kmb'
EXPECTED='9d3e10d21e2101994a5ac949f8b4d28404196a5eaca014d816f5d0624c4fd54f'
KEYTYPE=types.UniTuple(types.uint64,2)

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def sections(path):
    """Local format reader; official reader and canonical roundtrip are gates."""
    out={}; regs=[]
    with Path(path).open('rb') as f:
        header=f.read(104);assert header[:16]==MAGIC
        h=struct.unpack_from('<4I9Q',header,16);assert h[0]==2
        while f.tell()<Path(path).stat().st_size:
            off=f.tell();i,n=struct.unpack('<QQ',f.read(16));dataoff=f.tell()
            assert dataoff+n<=Path(path).stat().st_size
            if i==0:regs.append((off,16+n))
            else:
                assert i not in out
                out[i]=(dataoff,n)
            f.seek(n,1)
    assert set(out)==set(range(1,12))
    assert out[1][1]==h[4]
    for i,count in [(2,h[5]),(3,h[5]),(4,h[5]),(5,h[6]),(6,h[6]),(7,h[7]),(8,h[8]),(9,h[9])]:
        assert out[i][1]==4*count,(i,out[i],count)
    arrays={i:np.memmap(path,dtype=np.uint8 if i==1 else '<u4',mode='r',offset=o,shape=(n if i==1 else n//4,)) for i,(o,n) in out.items() if i<=9}
    return header,h,out,regs,arrays

@njit
def same(a,b):
    for j in range(a.size):
        if a[j]!=b[j]:return False
    return True

@njit
def zero(a):
    for j in range(a.size):
        if a[j]:return False
    return True

@njit
def token(i):
    # Not proof data: only a deterministic prefilter. Exact vector comparison
    # handles every collision, including deliberately forced collisions.
    x=np.uint64(i)+np.uint64(0x9e3779b97f4a7c15)
    x=(x^(x>>np.uint64(30)))*np.uint64(0xbf58476d1ce4e5b9)
    x=(x^(x>>np.uint64(27)))*np.uint64(0x94d049bb133111eb)
    return x^(x>>np.uint64(31))

@njit
def fresh(st,hs,q,n):
    st[q,:]=0;st[q,n//64]=np.uint64(1)<<np.uint64(n%64);hs[q]=token(n)
    return n+1

@njit
def exact_events(ops,a3,b3,t3,a2,t2,a1,cb,conds,nq,nb,words,maxops,maxret,collision_mask,num_inputs):
    limit=words*64
    st=np.zeros((nq,words),np.uint64);hs=np.zeros(nq,np.uint64)
    nxt=1
    origins=np.zeros(nq,np.int64);origin_snapshots=np.empty((32,nq),np.int64)
    pending=np.full(3,-1,np.int64);pending_scope=0
    # Input syndrome only, not all qubits, is arbitrary.
    for q in range(min(nq,num_inputs)):
        nxt=fresh(st,hs,q,nxt);origins[q]=-1
    known=np.full(nb,-1,np.int8)
    stack=np.empty(32,np.int8);depth=0;unknown=0;false=0
    snapshots=np.empty((32,nq,words),np.uint64)
    known_snapshots=np.empty((32,nb),np.int8)
    snapshot_epochs=np.empty(32,np.int64)
    previous_scopes=np.empty(32,np.int64)
    scope=0;scope_serial=0;closed_restores=0;merged_fresh=0;maxdepth=0
    touch=np.full(nq,-1,np.int64)
    left=np.zeros((limit,words),np.uint64);right=np.zeros((limit,words),np.uint64)
    link=np.full(limit,-1,np.int64)
    start=np.full(limit,-1,np.int64);src=np.full(limit,-1,np.int64)
    source_scope=np.full(limit,-1,np.int64)
    table=Dict.empty(key_type=KEYTYPE,value_type=types.int64)
    out=np.full((3*a3.size,10),-1,np.int64);nr=0;epochs=0;products=0;exact_matches=0;nominees=0
    gaps=np.full((maxret,4),-1,np.int64);ng=0
    busy=np.full(nq,-1,np.int64)
    i3=i2=i1=ib=ic=0
    for i in range(min(ops.size,maxops)):
        for pq in pending:
            if pq>=0:
                if not zero(st[pq]):origins[pq]=-1
                elif origins[pq]<0:origins[pq]=pending_scope
        pending[:]=-1
        code=int(ops[i]);cat=(code&127)>>4;kind=code&15
        a=b=t=-1;c=-1;bv=-1
        if cat==3:a=int(a3[i3]);b=int(b3[i3]);t=int(t3[i3]);i3+=1
        elif cat==2:a=int(a2[i2]);t=int(t2[i2]);i2+=1
        elif cat in (1,5):t=int(a1[i1]);i1+=1
        if cat in (4,5):bv=int(cb[ib]);ib+=1
        if code&128:c=int(conds[ic]);ic+=1
        if code==129:
            assert depth<32
            v=known[c];stack[depth]=v
            snapshots[depth,:,:]=st
            origin_snapshots[depth,:]=origins
            known_snapshots[depth,:]=known
            snapshot_epochs[depth]=epochs
            previous_scopes[depth]=scope
            depth+=1;maxdepth=max(maxdepth,depth)
            if v==0:false+=1
            elif v<0:
                unknown+=1;scope_serial+=1;scope=scope_serial
                if false==0:known[c]=1
            continue
        if code==1:
            assert depth>0
            depth-=1;v=stack[depth];scope=previous_scopes[depth]
            if v==0:false-=1
            elif v<0:
                unknown-=1
                if nxt+nq+8>=limit:
                    old=st.copy();nxt=1;hs[:]=0;st[:,:]=0
                    for q in range(nq):
                        is0=zero(old[q]);is1=(old[q,0]==1)
                        for w in range(1,words):
                            if old[q,w]:is1=False
                        if is1:st[q,0]=1;hs[q]=token(0)
                        elif not is0:nxt=fresh(st,hs,q,nxt)
                    table.clear();start[:]=-1;src[:]=-1;source_scope[:]=-1;epochs+=1
                restored=True
                for q in range(nq):
                    equal=(snapshot_epochs[depth]==epochs and same(st[q],snapshots[depth,q]))
                    if not equal:
                        is0=zero(st[q]) and zero(snapshots[depth,q])
                        is1=(st[q,0]==1 and snapshots[depth,q,0]==1)
                        for w in range(1,words):
                            if st[q,w] or snapshots[depth,q,w]:is1=False
                        if not is0 and not is1:
                            nxt=fresh(st,hs,q,nxt);merged_fresh+=1;restored=False
                for q in range(nq):
                    if not zero(st[q]):origins[q]=-1
                    elif zero(snapshots[depth,q]):origins[q]=origin_snapshots[depth,q]
                    else:origins[q]=scope
                if restored:closed_restores+=1
                for j in range(nb):
                    if known[j]!=known_snapshots[depth,j]:known[j]=-1
            continue
        # All enclosing unknown PUSH predicates are assumed true locally.
        # End-of-scope exact equality is the only way facts survive globally.
        flag=0 if false else 1
        if c>=0:
            if known[c]==0:flag=0
            elif known[c]<0 and flag!=0:flag=-1
        # Touch certificates ignore whether a gate is enabled; this is stronger
        # than needed and protects against dirty phase and classical guards.
        for q in (a,b,t):
            if q>=num_inputs and q>=0 and touch[q]+1<i and zero(st[q]):
                if i-touch[q]>8:
                    assert ng<maxret
                    gaps[ng,:]=np.array([q,touch[q]+1,i,origins[q]],np.int64);ng+=1
            if q>=0:touch[q]=i
        pending[:]=np.array([a,b,t],np.int64);pending_scope=scope
        if nxt+6>=limit:
            # Forget every nonconstant expression, preserving only exact zero
            # and exact one. This weakens the analysis, never proves a match.
            old=st.copy();nxt=1;hs[:]=0;st[:,:]=0
            for q in range(nq):
                is0=zero(old[q]);is1=(old[q,0]==1)
                for w in range(1,words):
                    if old[q,w]:is1=False
                if is1:st[q,0]=1;hs[q]=token(0)
                elif not is0:nxt=fresh(st,hs,q,nxt)
            table.clear();start[:]=-1;src[:]=-1;source_scope[:]=-1;epochs+=1
        if flag==0:continue
        if cat==1:
            if kind==0:continue # Z
            if kind==1:
                if flag==1:st[t,0]^=np.uint64(1);hs[t]^=token(0)
                else:nxt=fresh(st,hs,t,nxt)
            elif kind==2:
                if flag==1:st[t,:]=0;hs[t]=0
                elif not zero(st[t]):nxt=fresh(st,hs,t,nxt)
            else:raise ValueError('unsupported q1 kind')
        elif cat==2:
            if kind==0:continue # CZ
            if kind==1:
                if flag==1:
                    st[t,:]^=st[a,:];hs[t]^=hs[a]
                elif not zero(st[a]):nxt=fresh(st,hs,t,nxt)
            elif kind==2:
                if flag==1:
                    tmp=st[t].copy();st[t,:]=st[a];st[a,:]=tmp
                    sh=hs[t];hs[t]=hs[a];hs[a]=sh
                elif not same(st[t],st[a]):
                    nxt=fresh(st,hs,t,nxt);nxt=fresh(st,hs,a,nxt)
            else:raise ValueError('unsupported q2 kind')
        elif cat==3:
            if flag<0:
                if kind==1:nxt=fresh(st,hs,t,nxt)
                elif kind==2:
                    nxt=fresh(st,hs,b,nxt);nxt=fresh(st,hs,t,nxt)
                continue
            assert kind in (0,1,2)
            for variant in range(3 if kind==0 else 1):
                va=a;vb=b;vt=t
                if variant==1:va=a;vb=t;vt=b
                elif variant==2:va=b;vb=t;vt=a
                lhs=st[va].copy();rhs=st[vb].copy()
                lh=hs[va];rh=hs[vb]
                if kind==2:rhs^=st[vt];rh^=hs[vt]
                if zero(lhs) or zero(rhs):continue
                if same(lhs,rhs):
                    if kind==1:st[t,:]^=lhs;hs[t]^=lh
                    elif kind==2:
                        st[b,:]^=lhs;st[t,:]^=lhs;hs[b]^=lh;hs[t]^=lh
                    continue
                aa=lh&collision_mask;bb=rh&collision_mask
                key=(min(aa,bb),max(aa,bb))
                k=table[key] if key in table else np.int64(-1);atom=-1
                while k>=0:
                    nominees+=1
                    if (same(lhs,left[k]) and same(rhs,right[k])) or (same(lhs,right[k]) and same(rhs,left[k])):
                        atom=k;exact_matches+=1;break
                    k=link[k]
                if atom<0:
                    atom=nxt;nxt+=1;products+=1
                    left[atom,:]=lhs;right[atom,:]=rhs
                    link[atom]=table[key] if key in table else np.int64(-1);table[key]=atom
                if code in (48,49,50):
                    out[nr,:]=np.array([i,scope,epochs,atom,kind,va,vb,vt,i3-1,variant],np.int64);nr+=1
                if kind==1:
                    st[t,atom//64]^=np.uint64(1)<<np.uint64(atom%64);hs[t]^=token(atom)
                elif kind==2:
                    for q in (b,t):
                        st[q,atom//64]^=np.uint64(1)<<np.uint64(atom%64);hs[q]^=token(atom)
        elif cat==4:
            if flag<0:known[bv]=-1
            elif kind==0:known[bv]=0
            elif kind==1:known[bv]=1
            elif kind==2:
                if known[bv]>=0:known[bv]^=1
            else:raise ValueError('unsupported classical kind')
        elif cat==5:
            assert kind==0
            if flag==1:st[t,:]=0;hs[t]=0
            elif not zero(st[t]):nxt=fresh(st,hs,t,nxt)
            known[bv]=-1
        elif cat==0:
            assert kind in (0,6) # NEG / INFO_TAG
        else:raise ValueError('unsupported category')
    assert depth==0
    for pq in pending:
        if pq>=0:
            if not zero(st[pq]):origins[pq]=-1
            elif origins[pq]<0:origins[pq]=pending_scope
    for q in range(num_inputs,nq):
        if zero(st[q]) and ops.size-touch[q]>8:
            assert ng<maxret
            gaps[ng,:]=np.array([q,touch[q]+1,ops.size,origins[q]],np.int64);ng+=1
    return out[:nr],gaps[:ng],np.array([epochs,products,exact_matches,nominees,i3,i2,i1,ib,ic,closed_restores,merged_fresh,maxdepth],np.int64)


def choose(events,gaps):
    """Interval scheduling is heuristic; equality and idle certificates are exact."""
    from bisect import bisect_right
    groups={}
    for j,e in enumerate(events):groups.setdefault(tuple(map(int,e[1:4])),[]).append(j)
    available={}
    for q in sorted(set(map(int,gaps[:,0]))):
        rows=gaps[gaps[:,0]==q];rows=rows[np.argsort(rows[:,1])]
        available[q]=(rows[:,1].tolist(),rows)
    options=[]
    for ids in groups.values():
        if len(ids)<2:continue
        # Every contiguous subchain is considered; excessively long groups
        # are bounded to 64 uses for this first experiment only.
        for a in range(len(ids)-1):
            for b in range(a+1,min(len(ids),a+64)):
                if len(set(map(int,events[ids[a:b+1],8])))!=b-a+1:continue
                first=int(events[ids[a],0]);last=int(events[ids[b],0]);free=[]
                scope=int(events[ids[a],1])
                for q,(starts,rows) in available.items():
                    k=bisect_right(starts,first)-1
                    if k>=0 and int(rows[k,2])>last and int(rows[k,3]) in (0,scope):free.append(q)
                if free:options.append((b-a,first,last,ids[a:b+1],free))
    # Higher static savings dominate. This is not a claim of globally optimal
    # weighted allocation; an exact scheduling solver can be added later.
    options.sort(key=lambda x:(-x[0],x[2]-x[1],x[1]))
    occupied={q:[]for q in available};used=set();chains=[]
    for saving,first,last,ids,free in options:
        if used.intersection(map(int,events[ids,8])):continue
        for q in free:
            if any(not(last<l or first>r)for l,r in occupied[q]):continue
            chains.append(dict(cache=q,event_indices=ids,first=first,last=last,static_saving=saving))
            occupied[q].append((first,last));used.update(map(int,events[ids,8]));break
    chains.sort(key=lambda x:x['first'])
    return chains,len(options)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--words',type=int,default=512);p.add_argument('--max-gaps',type=int,default=3000000)
    p.add_argument('--collision-bits',type=int,default=64);p.add_argument('--num-inputs',type=int,default=840)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    hd,h,sec,regs,arr=sections(a.input)
    events,gaps,stats=exact_events(*[arr[i]for i in range(1,10)],h[1],h[2],a.words,2**63-1,a.max_gaps,np.uint64(2**a.collision_bits-1),a.num_inputs)
    np.save(a.out/'events.npy',events,allow_pickle=False);np.save(a.out/'zero_idle_intervals.npy',gaps,allow_pickle=False)
    chains,options=choose(events,gaps)
    report=dict(status='EXACT_CHAIN_PROPOSALS_ONLY_NOT_NATIVE',input=str(a.input.resolve()),input_sha256=sha(a.input),Q=h[1],ops=h[4],events=len(events),zero_idle_intervals=len(gaps),candidate_intervals=options,selected_chains=len(chains),static_savings=sum(c['static_saving']for c in chains),replaced_gates=sum(len(c['event_indices'])for c in chains),stats=stats.tolist(),words=a.words,collision_bits=a.collision_bits,chains=chains,scanner_sha256=sha(__file__),seconds=time.monotonic()-start,credit='Busya PRIME product-chain caching; own exact affine/product, CSWAP and branch-safe implementation; Gidney MBU.')
    (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copyfile(__file__,a.out/'scanner_source.py')
    print(json.dumps({k:v for k,v in report.items()if k!='chains'}),flush=True)


if __name__=='__main__':main()
