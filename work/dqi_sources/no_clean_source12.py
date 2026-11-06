"""Complete nonzero GF4096 source with only borrowed dirty wires.

No fresh wire, HMR or phase. The nonzero promise is necessary only for
the exceptional row r=0,b=0, which never occurs at the homogeneous chart.
The completed row correction is deliberately explicit and may be costly.
"""
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'exp/next/a04'),str(ROOT/'exp/next/a11'),
             str(ROOT/'exp/new/a07'),str(ROOT/'exp/new/a16')]
from virtual_norm import ar,encoded_norm6,regular_matrix12,mul_xor_noscratch
from structured_log65 import logarithm
from lowclean import mcx_dirty,controlled_linear
from constant_scale import factor


class Tape:
    def __init__(self):self.ops=[]
    def mul_boundary(self):self.ops.append(('mul_boundary',()))
    @staticmethod
    def seq(x):return [x] if isinstance(x,int) else list(x)
    def x(self,x):
        for q in self.seq(x):self.ops.append(('x',(q,)))
    def _pair(self,name,*args):
        arrays=[self.seq(a) for a in args];n=max(map(len,arrays))
        assert all(len(a) in (1,n) for a in arrays)
        for i in range(n):self.ops.append((name,tuple(a[0] if len(a)==1 else a[i] for a in arrays)))
    def cx(self,a,z):self._pair('cx',a,z)
    def ccx(self,a,c,z):self._pair('ccx',a,c,z)
    def swap(self,a,z):self._pair('swap',a,z)
    def cswap(self,c,a,z):
        self.cx(a,z);self.ccx(c,z,a);self.cx(a,z)
    def gf2_iadd(self,value,*,target,**kw):
        assert not kw
        for i in ar.bits(value):self.x(target[i])


def replay(b,ops,wires,reverse=False):
    for name,args in reversed(ops) if reverse else ops:
        getattr(b,name)(*(wires[j] for j in args))


def inverse6_dirty(b,r,borrow):
    """inv0 on all64 values. Its odd six-wire parity needs dirty borrowing."""
    logarithm(b,r);b.x(r);logarithm(b,r,True)
    # The even logarithm complement swaps0 and1. Correct that transposition.
    b.x(r[1:]);mcx_dirty(b,r[1:],r[0],borrow);b.x(r[1:])


def one_plus_zeta(b,x,s,inverse=False):
    """Multiply x by 1+s*zeta, using its fixed nonzero upper-left pivot."""
    if inverse:
        tape=Tape();one_plus_zeta(tape,list(range(6,18)),list(range(6)))
        replay(b,tape.ops,list(s)+list(x),True);return
    to,back,K=ar.tower(12);f=ar.field(6)
    ar.linear_inplace(b,x,to);a,z=x[:6],x[6:]
    ar.linear_inplace(b,s,tuple(f.mul(K,1<<i) for i in range(6)))
    mul_xor_noscratch(b,s,z,a)
    with encoded_norm6(b,s,K) as apply:apply([z])
    ar.linear_inplace(b,z,tuple(f.mul(f.invert(K),1<<i) for i in range(6)))
    ar.linear_inplace(b,s,tuple(f.mul(f.invert(K),1<<i) for i in range(6)))
    mul_xor_noscratch(b,s,a,z)
    ar.linear_inplace(b,x,back)


@lru_cache(None)
def correction_program():
    t=Tape();r=list(range(6));x=list(range(6,18));dirty=list(range(18,26))
    inverse6_dirty(t,r,dirty);one_plus_zeta(t,x,r,True);inverse6_dirty(t,r,dirty)
    # Suppressing target Toffolis leaves a fixed, invertible target linear map.
    rows={j:1<<(j-6) for j in x}
    for name,args in t.ops:
        touched=[j in rows for j in args]
        if name=='ccx':
            if any(touched):assert touched[-1] and sum(touched)>=2
            continue
        if any(touched):
            assert all(touched),('source-target linear mixing',name,args)
            if name=='cx':rows[args[1]]^=rows[args[0]]
            elif name=='swap':rows[args[0]],rows[args[1]]=rows[args[1]],rows[args[0]]
            else:raise AssertionError((name,args))
    columns=tuple(sum(((rows[6+i]>>j)&1)<<i for i in range(12)) for j in range(12))
    return tuple(t.ops),columns,tuple(ar.inverse_columns(columns))


def controlled_linear_predicate(b,x,columns,controls,borrow):
    for w,f in factor(tuple(columns)):
        p=next(i for i in range(len(x)) if f>>i&1)
        others=[i for i in range(len(x)) if i!=p and f>>i&1]
        for i in others:b.cx(x[i],x[p])
        q=next(i for i in range(len(x)) if i!=p and w>>i&1)
        direction=[i for i in range(len(x)) if i not in (p,q) and w>>i&1]
        for i in direction:b.cx(x[q],x[i])
        mcx_dirty(b,list(controls)+[x[p]],x[q],borrow)
        for i in reversed(direction):b.cx(x[q],x[i])
        for i in reversed(others):b.cx(x[i],x[p])


def exception_correction(b,x,r,key,borrow,inverse=False):
    """Multiply by r/(r+zeta) iff key=63; promised r!=0 on that row."""
    if inverse:
        t=Tape();exception_correction(t,list(range(6,18)),list(range(6)),list(range(18,24)),list(range(24,32)))
        replay(b,t.ops,list(r)+list(x)+list(key)+list(borrow[:8]),True);return
    assert len(borrow)>=8
    ops,off,off_back=correction_program();wires=list(r)+list(x)+list(borrow[:8])
    for name,args in ops:
        if name=='ccx' and any(6<=j<18 for j in args):
            a,c,z=(wires[j] for j in args)
            mcx_dirty(b,list(key)+[a,c],z,borrow)
        else:getattr(b,name)(*(wires[j] for j in args))
    ar.linear_inplace(b,x,off_back)
    controlled_linear_predicate(b,x,off,key,borrow)


def key_scale6(b,x,key,inverse=False):
    f=ar.field(6);alpha=f.invert(2) if inverse else 2
    cols=tuple(f.mul(alpha,1<<i) for i in range(6))
    for j in range(6):
        pre=tuple(f.pow(1<<i,1<<((6-j)%6)) for i in range(6))
        post=tuple(f.pow(1<<i,1<<j) for i in range(6))
        ar.linear_inplace(b,x,pre);controlled_linear(b,x,cols,key[j]);ar.linear_inplace(b,x,post)


@contextmanager
def source(b,y,borrow,inverse=False):
    assert len(y)==12 and len(borrow)>=8
    to,back,_=ar.tower(12);ar.linear_inplace(b,y,to)
    r,key=y[:6],y[6:];logarithm(b,key);key_scale6(b,r,key,True)
    def apply(targets):
        for x in targets:
            if inverse:exception_correction(b,x,r,key,borrow,True)
            regular_matrix12(b,x,r,inverse)
            ar.linear_inplace(b,x,to)
            key_scale6(b,x[:6],key,inverse);key_scale6(b,x[6:],key,inverse)
            ar.linear_inplace(b,x,back)
            if not inverse:exception_correction(b,x,r,key,borrow)
    yield apply
    key_scale6(b,r,key);logarithm(b,key,True);ar.linear_inplace(b,y,back)
