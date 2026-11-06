"""Consume the first completed product without decoding H2 at each node.

The whole two-head value and jet action is emitted directly in coordinates
Y=H1+[H1=0], P=Y*H2. H2 is reconstructed only once, after the ninth return.
The true polynomial top is retained; all width and source work are charged.
"""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path[:0]=[str(HERE),str(ROOT/'exp/round7/a15'),str(ROOT/'exp/round7/a12'),str(ROOT/'exp/next/a08')]
from overlap_prefix import *
from gauge_return import close_inverse_character
from exp.noscratch.schedules import classical_transpose
from block_phase import close_inverse_debts
from exp.noscratch.schedules import norm_xor_noscratch,inverse_stream_noscratch
from exp.mul99.phase36 import phase_inverse36_pivot
from exp.arithmetic.division import phase_product24


def mask_zero(b,n):
    m=b.alloc_bits(n);b.bit_store(m,False);return m


class RetiredTopOverlap(HeadOverlap):
    def _start(self,b,words,gi):
        super()._start(b,words,gi)
        self.state.update(top_debt=mask_zero(b,12),flag_debt=mask_zero(b,1),source_debts=[])

    def retire_top_before_gauge(self,b,gi):
        t=self.state['top'];m=b.alloc_bits(12);b.hmr(t,m);b.free(t)
        b.cx(m,self.state['top_debt']);b.free(m);self.state['top']=None
        if gi==self.first:
            f=self.state['flag'];m=b.alloc_bits(1);b.hmr(f,m[0]);b.free(f)
            b.cx(m,self.state['flag_debt']);b.free(m);self.state['flag']=None

    def _pay_product_value(self,b,words,mask,spec):
        m=mask_zero(b,24);b.cx(mask,m)
        self.state['source_debts'].append((spec['c'],m))

    def restore_top_at_consumer(self,b,words):
        assert self.state['top'] is None
        h1,p=words[2:4],words[4:6];u,h=h1
        if self.state['flag'] is None:self.state['flag']=zero_flag(b,combine(h1))
        f=self.state['flag'];b.cx(f,u[0]);y=combine(h1)
        n=b.alloc_qubits(12);norm_xor_noscratch(b,y,n,K)
        nm=inverse_stream_noscratch(b,n);ar._phase_norm(b,y,nm,K);b.free(nm)
        t=b.alloc_qubits(12)
        ar.mul_xor0(b,h,p[0],t);ar.mul_xor0(b,u,p[1],t)
        out=b.alloc_qubits(12);ar.mul_xor0(b,h,t,out)
        m=b.alloc_bits(12);b.hmr(t,m);b.swap(t,out);b.free(out)
        ar.phase_product(b,h,p[0],m);ar.phase_product(b,u,p[1],m);b.free(m)
        out=b.alloc_qubits(12);ar.mul_xor0(b,t,n,out)
        m=b.alloc_bits(12);b.hmr(t,m);b.swap(t,out);b.free(out)
        im=inverse_stream_noscratch(b,n)
        phase_inverse36_pivot(b,n,im);b.free(im)
        ar.phase_product(b,t,n,m);b.free(m)
        ar._erase_norm(b,y,n,K);b.free(n);b.cx(f,u[0])
        self.state['top']=t

    def _retire_top(self,b,h1,h2):
        t=self.state['top'];m=b.alloc_bits(12);b.hmr(t,m);b.free(t)
        b.cx(m,self.state['top_debt']);b.free(m)
        m=self.state.pop('top_debt');ar.phase_product(b,h1[1],h2[1],m);b.free(m)
        for ct,m in self.state.pop('source_debts'):
            cx(b,h1[1],h1[0],ct);cx(b,h2[1],h2[0],ct)
            phase_product24(b,combine(h1),combine(h2),m,K);b.free(m)
            cx(b,h2[1],h2[0],ct);cx(b,h1[1],h1[0],ct)



def product_frame(b,p,top,ct,delta):
    cx(b,p[1],p[0],ct);cx(b,top,p[0],delta)


def product_unframe(b,p,top,ct,delta):
    cx(b,top,p[0],delta);cx(b,p[1],p[0],ct)


def coefficient(b,h1,p,top,F,ct,delta):
    """Return C=h2*Y(beta)^2 using three GF4096 products."""
    C=b.alloc_qubits(24);u,h=h1
    b.cx(F,u[0]);b.cx(top,p[1])
    ar.mul_xor0(b,u,p[1],C[:12])
    b.cx(top,p[1]);b.cx(F,u[0])
    ar.mul_xor0(b,h,p[0],C[:12])
    ar.mul_xor0(b,h,top,C[12:])
    cx(b,C[12:],C[:12],ct^delta)
    return C


def erase_coefficient(b,C,h1,p,top,F,ct,delta):
    m=b.alloc_bits(24);b.hmr(C,m);b.free(C);u,h=h1
    b.cx(F,u[0]);b.cx(top,p[1])
    ar.phase_product(b,u,p[1],m[:12])
    b.cx(top,p[1]);b.cx(F,u[0])
    ar.phase_product(b,h,p[0],m[:12])
    f=ar.field(12);extra=classical_transpose(b,m[:12],[f.mul(ct^delta,1<<j)for j in range(12)])
    b.cx(extra,m[12:]);b.free(extra)
    ar.phase_product(b,h,top,m[12:]);b.free(m)


def two_head_return(b,words,gi,N,D,L,params,source,reference):
    h1,p=words[2:4],words[4:6]
    F=source.state['flag'];top=source.state['top']
    spec=reference.groups[gi];ct=spec['c'];delta=spec['kap']^K
    q0=params[0][0];q1=params[1][0];q2=params[2][0]
    assert q0==q1 and params[2][1]==0
    # a=N2/(q2*Y), a+(1+F)*v=q0/Y.
    scalepair(b,N,inv(q2));cx(b,h1[1],h1[0],ct);b.cx(F,h1[0][0])
    divide_lowwidth369(b,N,combine(h1),K)
    b.cx(F,h1[0][0]);cx(b,h1[1],h1[0],ct)
    product_frame(b,p,top,ct,delta)
    mul24_xor99(b,combine(p),N,D,K)
    product_unframe(b,p,top,ct,delta)
    scalepair(b,D,inv(q0)) # D=v is the exact old affine payload.

    # L0=L2/(q0*q2)+C*a^2/q0+(H1/q0+h1)*v^2.
    scalepair(b,L,inv(mul(q0,q2)))
    C=coefficient(b,h1,p,top,F,ct,delta)
    reference.external_square24(b,N);scalepair(b,N,inv(q0))
    mul24_xor99(b,C,N,L,K)
    scalepair(b,N,q0);reference.external_square24(b,N,True)
    erase_coefficient(b,C,h1,p,top,F,ct,delta)
    reference.external_square24(b,D)
    reference.external_corrected_product(b,h1,D,L,ct,inv(q0))
    reference.external_square24(b,D,True)

    # This measured coordinate is a known inverse-Y function plus v.
    m=b.alloc_bits(24);b.hmr(N,m)
    b.cz(D,m);b.ccz(F,D,m)
    if source.state.get('defer_inverse'):
        source.state['inverse_debts'].append((ct,delta,q0,m))
    else:
        cx(b,h1[1],h1[0],ct);b.cx(F,h1[0][0]);scalepair(b,combine(h1),inv(q0))
        close_inverse_character(b,combine(h1),m)
        scalepair(b,combine(h1),q0);b.cx(F,h1[0][0]);cx(b,h1[1],h1[0],ct)
        b.free(m)
    b.gf2_iadd(q0,target=N[:12])


def make_return(first=16,last=8,source_type=RetiredTopOverlap,defer_inverse=True):
    source=source_type(first,last)
    def return_node(b,words,gi,token,reference=old,narrow=None):
        spec=reference.groups[gi]
        N=combine(words[spec['word']:spec['word']+2]);L=combine(words[spec['word']+2:spec['word']+4])
        F=token['pole'];heads=[words[2*i:2*i+2]for i in range(2*gi)]
        params=[];delta=1;corr=0
        for i in range(2*gi):
            q=reference.ks[i]^spec['kap'];params.append((q,corr));delta=mul(delta,q);corr^=inv(q)
        assert corr==0
        with b.mark('block_source'):(a,c),restore=source.prepare(b,words,gi,reference)
        if defer_inverse and 'inverse_debts' not in source.state:
            source.state.update(defer_inverse=True,inverse_debts=[])
        with b.mark('retire_top_before_gauge'):source.retire_top_before_gauge(b,gi)
        with b.mark('column_recovery'):
            D=b.alloc_qubits(24)
            b.cx(F,N[0]);mul24_xor99(b,c,N,D,K);b.cx(F,N[0])
            b.cx(a,D);b.ccx(F,a,D);scalepair(b,D,inv(delta))
        with b.mark('block_source_return'):restore()
        with b.mark('payload_unnormalize'):
            b.cx(F,N[0]);reference.external_square24(b,L,True)
            divide_pair_and_invert(b,[N,L],D,token['norm']);reference.external_square24(b,L)
        with b.mark('pole_retirement'):
            b.ccx(F,N,D);m=b.alloc_bits(1);b.hmr(F,m[0]);b.free(F)
            phase_zero(b,D,m[0]);b.free(m)
        with b.mark('inverse_traversal'):
            for i in reversed(range(3,len(heads))):
                q,corr=params[i]
                reference.external_chain_step(b,heads[i],N,D,L,q,spec['c'],corr,True)
            with b.mark('reconstruct_top'):source.restore_top_at_consumer(b,words)
            with b.mark('two_head_block'):two_head_return(b,words,gi,N,D,L,params,source,reference)
            q0=params[0][0];scalepair(b,N,inv(q0));b.swap(N,D);scalepair(b,L,inv(q0))
            ah,hh=heads[0];cx(b,hh,ah,spec['c']);b.cx(combine(heads[0]),N);cx(b,hh,ah,spec['c'])
            b.cx(hh,L[:12]);b.x(D[0]);b.free(D)
        if gi==last:
            with b.mark('final_head_decode'):
                h1,h2=words[2:4],words[4:6]
                source._decode(b,h1,h2);source._retire_top(b,h1,h2)
                f=source.state['flag']
                if defer_inverse:
                    with b.mark('shared_inverse_characters'):
                        close_inverse_debts(b,h1,f,source.state.pop('inverse_debts'))
                m=b.alloc_bits(1);b.hmr(f,m[0]);b.free(f)
                fd=source.state.pop('flag_debt');b.cx(fd,m);b.free(fd)
                phase_zero(b,combine(h1),m[0]);b.free(m);source.state=None
    return return_node,source
