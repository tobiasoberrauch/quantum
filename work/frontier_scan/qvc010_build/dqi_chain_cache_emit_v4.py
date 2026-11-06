"""Emit credited product-chain caching with exact idle/expression certificates.

For CSWAP, p=c*(x XOR y) and the swap is CX(p,x);CX(p,y).
Creation and measured erasure expose x XOR y with two temporary CNOTs.
All other gates and their conditional masks are preserved exactly.
"""
import argparse,json,shutil,struct,time
from pathlib import Path
import numpy as np
from numba import njit
from dqi_chain_cache_v4 import sections,sha


@njit
def rewrite(ops,a3,b3,t3,a2,t2,a1,cb,conds,events,eventrow,chainmap,begins,ends,cache,nb):
    n=len(cache);uses=np.sum(chainmap>=0)
    csuses=0;csfirst=0;cslast=0
    for e in events:
        j=int(e[8]);ci=chainmap[j]
        if ci>=0 and e[4]==2:
            csuses+=1
            if begins[j]:csfirst+=1
            if ends[j]:cslast+=1
    # One compute per chain; one HMR and conditional CZ per chain.
    q3n=a3.size+n-uses;q2n=a2.size+uses+csuses+n+2*csfirst+2*cslast
    q1n=a1.size+n;bn=cb.size+n;cn=conds.size+n
    on=ops.size+3*n+csuses+2*csfirst+2*cslast
    out=np.empty(on,np.uint8);x3=np.empty(q3n,np.uint32);y3=np.empty(q3n,np.uint32);z3=np.empty(q3n,np.uint32)
    x2=np.empty(q2n,np.uint32);z2=np.empty(q2n,np.uint32);z1=np.empty(q1n,np.uint32)
    bc=np.empty(bn,np.uint32);cc=np.empty(cn,np.uint32)
    i3=i2=i1=ib=ic=o=o3=o2=o1=ob=oc=0
    for i in range(ops.size):
        code=int(ops[i]);cat=(code&127)>>4;kind=code&15
        a=b=t=bv=c=-1;j=i3
        if cat==3:a=int(a3[i3]);b=int(b3[i3]);t=int(t3[i3]);i3+=1
        elif cat==2:a=int(a2[i2]);t=int(t2[i2]);i2+=1
        elif cat in (1,5):t=int(a1[i1]);i1+=1
        if cat in (4,5):bv=int(cb[ib]);ib+=1
        if code&128:c=int(conds[ic]);ic+=1
        ci=chainmap[j]if cat==3 else -1
        if ci<0:
            out[o]=code;o+=1
            if cat==3:x3[o3]=a;y3[o3]=b;z3[o3]=t;o3+=1
            elif cat==2:x2[o2]=a;z2[o2]=t;o2+=1
            elif cat in (1,5):z1[o1]=t;o1+=1
            if cat in (4,5):bc[ob]=bv;ob+=1
            if code&128:cc[oc]=c;oc+=1
            continue
        if code==48:
            er=events[eventrow[j]];a=int(er[5]);b=int(er[6]);t=int(er[7])
        assert code in (48,49,50);u=int(cache[ci]);assert u!=a and u!=b and u!=t
        if begins[j]:
            if kind==2:
                out[o]=33;o+=1;x2[o2]=b;z2[o2]=t;o2+=1
            out[o]=49;o+=1;x3[o3]=a;y3[o3]=t if kind==2 else b;z3[o3]=u;o3+=1
            if kind==2:
                out[o]=33;o+=1;x2[o2]=b;z2[o2]=t;o2+=1
        if kind==2:
            out[o]=33;o+=1;x2[o2]=u;z2[o2]=b;o2+=1
        out[o]=32 if kind==0 else 33;o+=1;x2[o2]=u;z2[o2]=t;o2+=1
        if ends[j]:
            out[o]=80;o+=1;z1[o1]=u;o1+=1;bc[ob]=nb;ob+=1
            if kind==2:
                out[o]=33;o+=1;x2[o2]=b;z2[o2]=t;o2+=1
            out[o]=160;o+=1;x2[o2]=a;z2[o2]=t if kind==2 else b;o2+=1;cc[oc]=nb;oc+=1
            if kind==2:
                out[o]=33;o+=1;x2[o2]=b;z2[o2]=t;o2+=1
    assert (o,o3,o2,o1,ob,oc)==(on,q3n,q2n,q1n,bn,cn)
    assert (i3,i2,i1,ib,ic)==(a3.size,a2.size,a1.size,cb.size,conds.size)
    return out,x3,y3,z3,x2,z2,z1,bc,cc


def emit(path,plan,out):
    hd,h,sec,regs,arr=sections(path);assert sha(path)==plan['input_sha256']
    folder=Path(plan['_folder']);events=np.load(folder/'events.npy',allow_pickle=False)
    index=np.full(h[5],-1,np.int32);begins=np.zeros(h[5],np.bool_);ends=begins.copy()
    event_lookup={(int(e[8]),int(e[9])):j for j,e in enumerate(events)}
    cache=[];eventrow=np.full(h[5],-1,np.int32)
    for ci,chain in enumerate(plan['chains']):
        ids=chain['event_indices'];rows=events[ids];assert len(rows)>=2
        assert int(rows[0,0])==chain['first']and int(rows[-1,0])==chain['last']
        assert all(np.array_equal(e[1:4],rows[0,1:4])for e in rows)
        assert np.all(np.diff(rows[:,0])>0)
        for e in rows:
            j=int(e[8]);assert index[j]<0;index[j]=ci;eventrow[j]=event_lookup[(int(e[8]),int(e[9]))]
            assert int(arr[1][e[0]])==48+e[4]
            orig=(int(arr[2][j]),int(arr[3][j]),int(arr[4][j]))
            assert sorted(orig)==sorted(map(int,e[5:8])) if int(e[4])==0 else orig==tuple(map(int,e[5:8]))
        begins[int(rows[0,8])]=True;ends[int(rows[-1,8])]=True;cache.append(chain['cache'])
    assert cache
    new=rewrite(*[arr[i]for i in range(1,10)],events,eventrow,index,begins,ends,np.array(cache,np.int64),h[2])
    nh=list(h);nh[2]+=1;nh[1]=max(h[1],max(cache)+1)
    for i,j in [(4,0),(5,1),(6,4),(7,6),(8,7),(9,8)]:nh[i]=len(new[j])
    with path.open('rb')as src,out.open('xb')as dst:
        dst.write(hd[:16]+struct.pack('<4I9Q',*nh))
        for off,n in regs:src.seek(off);dst.write(src.read(n))
        for i,data in enumerate(new,1):dst.write(struct.pack('<QQ',i,data.nbytes));dst.write(data.tobytes())
        for i in (10,11):off,n=sec[i];src.seek(off);dst.write(struct.pack('<QQ',i,n));dst.write(src.read(n))
    return dict(Q=nh[1],old_static_T=h[5],static_T=nh[5],saved_static_T=h[5]-nh[5],num_ops=nh[4],num_bits=nh[2],chains=len(cache),sha256=sha(out))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(exist_ok=False,parents=True);start=time.monotonic();plan=json.loads(a.plan.read_text());plan['_folder']=str(a.plan.parent)
    report=emit(a.input,plan,a.out/'dqi.kmb')
    import kickmix as km
    c=km.Circuit.from_file(a.out/'dqi.kmb',format='kmb');assert c.num_qubits==report['Q']
    assert len(c)==report['num_ops']and int(c.operation_statistics().num_toffoli_like)==report['static_T']
    rt=a.out/'canonical_roundtrip.kmb';c.to_file(rt,format='kmb');assert sha(rt)==report['sha256']
    report.update(status='EXACT_CHAIN_NATIVE_EMITTED_NOT_VERIFIED',input_sha256=sha(a.input),plan_sha256=sha(a.plan),emitter_sha256=sha(__file__),seconds=time.monotonic()-start)
    (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copyfile(__file__,a.out/'emitter_source.py')
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
