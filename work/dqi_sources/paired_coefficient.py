"""Closed in-place paired coefficient Schur permutation, all zero charts.

The value interface is documented in PROOF.md.  A and B are n q-adic
base-field words, n odd >=3; B's implicit leading x*q^m coefficient is1.
Two heads U,W occupy A[:2],B[:2]; the degree-(n-2) banks use their suffixes.
This is a component, not the fixed-Hermite syndrome inverse.
"""
from pathlib import Path
from functools import lru_cache
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'playbook/kit'),str(ROOT/'playbook/kit/decoder'),
             str(ROOT/'exp/next/a02'),str(ROOT/'exp/next/root')]
from schur_scalar import inverse_apply,scale,ar
from exp.decoder.common import combine,cx,linear_words,divmodp
from exp.mul99.kernels import mul24_xor99
from exp.mul99.schedules import divide_zero_bridge414,multiply_zero_forward99
from exp.arithmetic.lowwidth import classical_transpose
from jet_character import close_canonical
K=2048


def multiply_closed(b,x,y,k=K):
    """x*=y+[y=0], source preserved, all old-x/zero characters closed."""
    old,fz=multiply_zero_forward99(b,x,y,k)
    to,back,_=ar.extension_columns(k)
    ar.linear_inplace(b,x,to);ar.linear_inplace(b,y,to)
    canon=classical_transpose(b,old,back)
    square=tuple(ar.square_columns(24));sqrt=tuple(ar.inverse_columns(square))
    mask=classical_transpose(b,canon,sqrt)
    mu=b.alloc_bits(24);b.bit_store(mu,False)
    ar.linear_inplace(b,x,square)
    close_canonical(b,y,x,(mu,mask,[fz]))
    ar.linear_inplace(b,x,sqrt)
    ar.linear_inplace(b,y,back);ar.linear_inplace(b,x,back)
    b.free(mu);b.free(mask);b.free(canon);b.free(old);b.free(fz)


def closed_scale24(b,x,y,divide=False,k=K):
    if divide:divide_zero_bridge414(b,x,y,k)
    else:multiply_closed(b,x,y,k)


def erase_affine_product(b,z,a,x,linear=()):
    mask=b.alloc_bits(12);b.hmr(z,mask);b.free(z)
    ar.phase_product(b,a,x,mask)
    for reg in linear:b.cz(reg,mask)
    b.free(mask)


def pivot(b,A,B,reverse=False,k=K):
    n=len(A);m=(n-1)//2
    assert n==len(B) and n>=3 and n%2
    U=combine(A[:2]);W=combine(B[:2]);h=A[1];s=B[1]

    def first():
        for i in range(1,m):
            mul24_xor99(b,U,combine(B[2*i:2*i+2]),combine(A[2*i:2*i+2]),k)
            ar.mul_xor0(b,h,B[2*i-1],A[2*i])
        ar.mul_xor0(b,A[0],B[-1],A[-1]);cx(b,h,A[-1],k)
        ar.mul_xor0(b,h,B[-2],A[-1])

    def second():
        if m==1:return
        for i in range(1,m-1):
            mul24_xor99(b,W,combine(A[2*i+2:2*i+4]),combine(B[2*i:2*i+2]),k)
            ar.mul_xor0(b,s,A[2*i+1],B[2*i])
        Y=b.alloc_qubits(12);b.cx(A[0],Y);b.cx(h,Y);ar.mul_xor0(b,h,B[-1],Y)
        mul24_xor99(b,W,combine([A[-1],Y]),combine(B[-3:-1]),k)
        ar.mul_xor0(b,s,A[-2],B[-3])
        erase_affine_product(b,Y,h,B[-1],(A[0],h))

    def normalize():
        eta=b.alloc_qubits(12);b.x(eta[0]);ar.mul_xor0(b,h,s,eta)
        def constants():
            ar.mul_xor0(b,h,B[0],B[-1]);ar.mul_xor0(b,s,A[0],B[-1]);ar.mul_xor0(b,s,h,B[-1])
        def action(ei):
            if not reverse:
                scale(b,B[-1],eta,ei,False);constants()
            for i in range(2,n):
                scale(b,A[i],eta,ei,reverse)
                scale(b,B[i],eta,ei,not reverse)
            if reverse:
                constants();scale(b,B[-1],eta,ei,True)
        inverse_apply(b,eta,action)
        mask=b.alloc_bits(12);b.hmr(eta,mask);b.free(eta)
        b.z(mask[0]);ar.phase_product(b,h,s,mask);b.free(mask)

    def shear():
        L=b.alloc_qubits(24);lo,hi=L[:12],L[12:]
        b.cx(U,L)
        square=tuple(ar.square_columns(12));sqrt=tuple(ar.inverse_columns(square))
        ar.linear_inplace(b,h,square)
        b.cx(s,B[0]);ar.mul_xor0(b,h,B[0],lo);b.cx(s,B[0]);ar.mul_xor0(b,h,s,hi)
        ar.linear_inplace(b,h,sqrt)
        for i in range(1,m):
            mul24_xor99(b,L,combine(B[2*i:2*i+2]),combine(A[2*i:2*i+2]),k)
            if i>1:ar.mul_xor0(b,hi,B[2*i-1],A[2*i])
        ar.mul_xor0(b,lo,B[-1],A[-1]);cx(b,hi,A[-1],k)
        if m>1:ar.mul_xor0(b,hi,B[-2],A[-1])
        mask=b.alloc_bits(24);b.hmr(L,mask);b.free(L);b.cz(U,mask)
        ar.linear_inplace(b,h,square)
        b.cx(s,B[0]);ar.phase_product(b,h,B[0],mask[:12]);b.cx(s,B[0]);ar.phase_product(b,h,s,mask[12:])
        ar.linear_inplace(b,h,sqrt);b.free(mask)

    def second_head(divide):
        if m>1:return closed_scale24(b,W,combine(A[2:4]),divide,k)
        Y=b.alloc_qubits(12);b.cx(A[0],Y);b.cx(h,Y);ar.mul_xor0(b,h,B[-1],Y)
        closed_scale24(b,W,combine([A[-1],Y]),divide,k)
        erase_affine_product(b,Y,h,B[-1],(A[0],h))

    if not reverse:
        closed_scale24(b,U,W,True,k);first()
        second_head(True);second();normalize();shear()
    else:
        shear();normalize();second()
        second_head(False);first();closed_scale24(b,U,W,False,k)
    return U,W,list(A[2:]),list(B[2:])


@lru_cache(None)
def qadic_matrix(n,k=K):
    cols=[]
    for j in range(n):
        p=[0]*j+[1];out=[]
        for _ in range((n+1)//2):
            p,r=divmodp(p,[k,1,1]);out+=(r+[0,0])[:2]
        cols.append(out[:n])
    return tuple(tuple(cols[j][i]for j in range(n))for i in range(n))


@lru_cache(None)
def implicit_offsets(n,k=K):
    p=[0]*n+[1];out=[]
    for _ in range((n+2)//2):
        p,r=divmodp(p,[k,1,1]);out+=(r+[0,0])[:2]
    assert out[n]==1
    return tuple(out[:n])


def qadic(b,A,B,reverse=False,k=K):
    n=len(A);matrix=qadic_matrix(n,k)
    if reverse:
        for word,c in zip(B,implicit_offsets(n,k)):b.gf2_iadd(c,target=word)
    linear_words(b,A,matrix,reverse);linear_words(b,B,matrix,reverse)
    if not reverse:
        for word,c in zip(B,implicit_offsets(n,k)):b.gf2_iadd(c,target=word)
