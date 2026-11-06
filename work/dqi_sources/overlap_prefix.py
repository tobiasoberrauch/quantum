"""A source-complete two-head polynomial overlap in the actual head bank.

H2's physical slots hold H2*safe(H1) between the nine consumers. The
quadratic coefficient of H1*H2 occupies one extra base-field word. Each
actual head2 consumer reconstructs H2, pays the deferred old-head mask,
then returns the slots to the polynomial encoding if another node remains.
"""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path[:0]=[str(HERE),str(ROOT/'exp/round7/a02'),str(ROOT/'exp/round7/a09')]
from column_double_tail import (old,combine,cx,mul,inv,scalepair,K,
    phase_zero,mul24_xor99,divide_pair_and_invert,second_return)
from exp.decoder.common import ar
from exp.arithmetic.division import zero_flag
from exp.mul99.schedules import multiply_forward99,divide_lowwidth369


class HeadOverlap:
    def __init__(self,first=16,last=8):
        self.first=first;self.last=last;self.state=None

    def _encode(self,b,h1,h2):
        f=self.state['flag']
        b.cx(f,h1[0][0])
        self.state['mask']=multiply_forward99(b,combine(h2),combine(h1),K)
        b.cx(f,h1[0][0])

    def _decode(self,b,h1,h2):
        f=self.state['flag']
        b.cx(f,h1[0][0])
        divide_lowwidth369(b,combine(h2),combine(h1),K)
        b.cx(f,h1[0][0])
        b.cz(combine(h2),self.state['mask']);b.free(self.state['mask'])
        self.state['mask']=None

    def _start(self,b,words,gi):
        assert gi==self.first and self.state is None
        h1,h2=words[2:4],words[4:6]
        top=b.alloc_qubits(12);ar.mul_xor0(b,h1[1],h2[1],top)
        flag=zero_flag(b,combine(h1))
        self.state=dict(top=top,flag=flag,last_gi=gi+1,builder=b,mask=None)
        self._encode(b,h1,h2)

    def _add_product_value(self,b,words,target,spec):
        # True H1*H2 = (1+F)*Pbar + top*q_star as a polynomial.
        p=combine(words[4:6]);f=self.state['flag']
        cx(b,words[5],words[4],spec['c'])
        b.cx(p,target);b.ccx(f,p,target)
        cx(b,words[5],words[4],spec['c'])
        cx(b,self.state['top'],target[:12],spec['kap']^K)

    def _pay_product_value(self,b,words,mask,spec):
        p=combine(words[4:6]);f=self.state['flag']
        cx(b,words[5],words[4],spec['c'])
        b.cz(p,mask);b.ccz(f,p,mask)
        cx(b,words[5],words[4],spec['c'])
        # Constant-linear evaluation needs no coherent multiplication.
        temp=combine(words[2:4]) # just measured to zero by the caller
        cx(b,self.state['top'],temp[:12],spec['kap']^K)
        b.cz(temp,mask)
        cx(b,self.state['top'],temp[:12],spec['kap']^K)

    def prepare(self,b,words,gi,reference=old):
        if self.state is None:self._start(b,words,gi)
        assert self.state['builder'] is b and gi==self.state['last_gi']-1
        self.state['last_gi']=gi
        spec=reference.groups[gi]
        heads=[words[2*i:2*i+2]for i in range(2*gi)]
        qs=[reference.ks[i]^spec['kap']for i in range(2*gi)]
        a=b.alloc_qubits(24);c=combine(heads[1])
        # The future a value retains H1 while its head bank holds c.
        b.cx(c,a);cx(b,a[12:],a[:12],spec['c']);scalepair(b,a,qs[2])
        mask=b.alloc_bits(24);b.hmr(c,mask)
        scalepair(b,a,inv(qs[2]));cx(b,a[12:],a[:12],spec['c'])
        b.cz(a,mask);b.free(mask)
        cx(b,a[12:],a[:12],spec['c']);scalepair(b,a,qs[2])
        self._add_product_value(b,words,c,spec)
        b.gf2_iadd(qs[1],target=c[:12])
        for i in range(3,len(heads)):
            reference.external_scalar_step(b,heads[i],a,c,qs[i],spec['c'])

        def restore():
            for i in reversed(range(3,len(heads))):
                reference.external_scalar_step(b,heads[i],a,c,qs[i],spec['c'],True)
            mask=b.alloc_bits(24);b.hmr(c,mask)
            self._pay_product_value(b,words,mask,spec)
            for bit in ar.bits(qs[1]):b.z(mask[bit])
            b.free(mask)
            scalepair(b,a,inv(qs[2]));b.cx(a,c);b.cx(c,a);b.free(a)
            cx(b,heads[1][1],heads[1][0],spec['c'])
        return (a,c),restore

    def consumer(self,b,words,gi,callback):
        h1,h2=words[2:4],words[4:6]
        self._decode(b,h1,h2)
        self._after_decode(b,h1,h2)
        callback()
        if gi!=self.last:self._encode(b,h1,h2)
        else:
            self._release(b,h1,h2)
            self._retire_top(b,h1,h2)
            f=self.state['flag']
            m=b.alloc_bits(1);b.hmr(f,m[0]);b.free(f)
            phase_zero(b,combine(h1),m[0]);b.free(m)
            self.state=None

    def _release(self,b,h1,h2):
        pass

    def end_node(self,b,words,gi):
        pass

    def _after_decode(self,b,h1,h2):
        pass

    def _retire_top(self,b,h1,h2):
        top=self.state['top']
        m=b.alloc_bits(12);b.hmr(top,m);b.free(top)
        ar.phase_product(b,h1[1],h2[1],m);b.free(m)


def make_return(first=16,last=8,source_type=HeadOverlap):
    source=source_type(first,last)
    def return_node(b,words,gi,token,reference=old,narrow=None):
        spec=reference.groups[gi]
        N=combine(words[spec['word']:spec['word']+2])
        L=combine(words[spec['word']+2:spec['word']+4])
        F=token['pole'];heads=[words[2*i:2*i+2]for i in range(2*gi)]
        params=[];delta=1;corr=0
        for i in range(2*gi):
            q=reference.ks[i]^spec['kap'];params.append((q,corr))
            delta=mul(delta,q);corr^=inv(q)
        assert corr==0
        with b.mark('overlap_source'):(a,c),restore=source.prepare(b,words,gi,reference)
        with b.mark('column_recovery'):
            D=b.alloc_qubits(24)
            b.cx(F,N[0]);mul24_xor99(b,c,N,D,K);b.cx(F,N[0])
            b.cx(a,D);b.ccx(F,a,D);scalepair(b,D,inv(delta))
        with b.mark('overlap_source_return'):restore()
        with b.mark('payload_unnormalize'):
            b.cx(F,N[0]);reference.external_square24(b,L,True)
            divide_pair_and_invert(b,[N,L],D,token['norm'])
            reference.external_square24(b,L)
        with b.mark('pole_retirement'):
            b.ccx(F,N,D)
            mask=b.alloc_bits(1);b.hmr(F,mask[0]);b.free(F)
            phase_zero(b,D,mask[0]);b.free(mask)
        with b.mark('inverse_traversal'):
            for i in reversed(range(2,len(heads))):
                q,corr=params[i]
                def action():
                    reference.external_chain_step(b,heads[i],N,D,L,q,spec['c'],corr,True)
                if i==2:
                    with b.mark('overlap_consumer'):source.consumer(b,words,gi,action)
                else:action()
            q,corr=params[1];q0=params[0][0]
            second_return(b,heads[1],N,D,L,q,q0,spec['c'],corr,reference)
            scalepair(b,N,inv(q0));b.swap(N,D);scalepair(b,L,inv(q0))
            ah,hh=heads[0]
            cx(b,hh,ah,spec['c']);b.cx(combine(heads[0]),N);cx(b,hh,ah,spec['c'])
            b.cx(hh,L[:12]);b.x(D[0]);b.free(D)
        source.end_node(b,words,gi)
    return return_node,source
