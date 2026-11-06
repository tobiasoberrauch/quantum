"""Exact single-bank gauge inversion and normalization.

The 24-bit gauge is inverted through its 12-bit norm.  Only that norm,
its six-bit subnorm, and a three-bit leaf are live together.  Every
measurement in this file is repaid before its source changes.
"""
from pathlib import Path
import sys
H=Path(__file__).resolve().parent;ROOT=H.parents[2]
sys.path[:0]=[str(H),str(ROOT/'exp/next/a16'),str(ROOT/'exp/new/a16'),
             str(ROOT/'exp/new/a07'),str(ROOT/'exp/r-main/narrow240'),
             str(ROOT/'playbook/kit'),str(ROOT/'playbook/kit/decoder')]
from column_hole import paired_source
from lowclean import zero_toggle,chart,chart_data
from streamed import inverse6_unitary29
from exp.decoder.common import ar,K
from exp.noscratch.schedules import norm_xor_noscratch
from exp.inverse19_joint.kernel import inverse_initialized
from exp.mul99.phase36 import phase_inverse36_pivot
from exp.arithmetic.division import phase_zero,phase_product24,zero_flag
from exp.mul99.schedules import multiply_forward99
from exp.noscratch.schedules import inverse_stream_noscratch


def _invert12(b,x):
    to,back,k=ar.tower(12);ar.linear_inplace(b,x,to)
    norm=b.alloc_qubits(6);norm_xor_noscratch(b,x,norm,k)
    inverse6_unitary29(b,norm)
    b.cx(x[6:],x[:6])
    with paired_source(b,norm) as apply:
        apply([x[:6],x[6:]])
    ar._erase_norm(b,x,norm,k);b.free(norm)
    ar.linear_inplace(b,x,back)


def invert24(b,x):
    """Closed inv0 in decoder extension basis; at most21 extra wires."""
    cols,back,_=ar.extension_columns(K);ar.linear_inplace(b,x,cols)
    to,frm,k=ar.tower(24);ar.linear_inplace(b,x,to)
    norm=b.alloc_qubits(12);norm_xor_noscratch(b,x,norm,k)
    _invert12(b,norm)
    b.cx(x[12:],x[:12])
    with paired_source(b,norm) as apply:
        apply([x[:12],x[12:]])
    ar._erase_norm(b,x,norm,k);b.free(norm)
    ar.linear_inplace(b,x,frm);ar.linear_inplace(b,x,back)


def scale_pair(b,targets,source):
    """Multiply all extension targets by one nonzero preserved source."""
    cols,back,_=ar.extension_columns(K)
    ar.linear_inplace(b,source,cols)
    for x in targets:ar.linear_inplace(b,x,cols)
    with paired_source(b,source) as apply:
        apply(targets)
    for x in targets:ar.linear_inplace(b,x,back)
    ar.linear_inplace(b,source,back)


def divide_pair(b,targets,source):
    """Closed division of two targets, sharing the source inverse norm.

    Source is nonzero.  Twelve norm wires and one twelve-bit target output
    coexist; the initial products use24 output wires with no held norm.
    """
    b.cx(source[12:],source[:12])
    old=[multiply_forward99(b,x,source,K) for x in targets]
    b.cx(source[12:],source[:12])
    reciprocal=b.alloc_qubits(12);norm_xor_noscratch(b,source,reciprocal,K)
    nm=inverse_stream_noscratch(b,reciprocal)
    ar._phase_norm(b,source,nm,K);b.free(nm)
    masks=[]
    for x in targets:
        row=[]
        for off in (0,12):
            half=x[off:off+12];out=b.alloc_qubits(12)
            ar.mul_xor0(b,half,reciprocal,out)
            hm=b.alloc_bits(12);b.hmr(half,hm)
            b.swap(half,out);b.free(out);row.append(hm)
        masks.append(row)
    im=b.alloc_bits(12);b.hmr(reciprocal,im);b.free(reciprocal)
    norm=b.alloc_qubits(12);norm_xor_noscratch(b,source,norm,K)
    for x,row in zip(targets,masks):
        for off,m in zip((0,12),row):
            ar.phase_product(b,x[off:off+12],norm,m);b.free(m)
    phase_inverse36_pivot(b,norm,im);b.free(im)
    ar._erase_norm(b,source,norm,K);b.free(norm)
    for x,m in zip(targets,old):phase_product24(b,x,source,m,K);b.free(m)


def divide_pair_and_invert(b,targets,source,old_token=None):
    """Unnormalize both payloads and invert their gauge with one norm.

    All six old-half characters share the same reciprocal norm.  They
    are repaid by one linear inverse character before that norm retires.
    """
    from retained_core_safe27 import linear_inverse_character
    b.cx(source[12:],source[:12])
    old=[multiply_forward99(b,x,source,K) for x in targets]
    b.cx(source[12:],source[:12])
    reciprocal=b.alloc_qubits(12);norm_xor_noscratch(b,source,reciprocal,K)
    nm=inverse_stream_noscratch(b,reciprocal)
    ar._phase_norm(b,source,nm,K);b.free(nm)
    if old_token is not None:
        with b.mark('joint_old_token_closure'):
            close_reciprocal_chart(b,source,reciprocal,old_token)
    terms=[]
    for x in targets:
        for off in (0,12):
            half=x[off:off+12];out=b.alloc_qubits(12)
            ar.mul_xor0(b,half,reciprocal,out)
            m=b.alloc_bits(12);b.hmr(half,m)
            b.swap(half,out);b.free(out);terms.append((half,m))
    # The old complete-payload characters still use the reciprocal gauge.
    for x,m in zip(targets,old):phase_product24(b,x,source,m,K);b.free(m)
    b.cx(source[12:],source[:12])
    for off in (0,12):
        half=source[off:off+12];out=b.alloc_qubits(12)
        ar.mul_xor0(b,half,reciprocal,out)
        m=b.alloc_bits(12);b.hmr(half,m)
        b.swap(half,out);b.free(out);terms.append((half,m))
    zero=b.alloc_bits(12);b.bit_store(zero,False)
    linear_inverse_character(b,reciprocal,zero,terms)
    b.free(zero)
    for _,m in terms:b.free(m)
    ar._erase_norm(b,source,reciprocal,K);b.free(reciprocal)


def close_reciprocal_chart(b,C,reciprocal_norm,masks):
    """Pay the six characters of1/C with held1/Norm(C).

    A single affine inverse character pays every remaining rational term;
    the other terms are linear or bilinear with classical phase masks.
    """
    from core90 import affine_inverse_g_character
    assert set(masks)=={'g','i','h','t','r','f'}
    A,g=C[:12],C[12:]
    F=zero_flag(b,g);b.cswap(F,A,g)
    ar.phase_product(b,g,reciprocal_norm,masks['g']);b.free(masks['g'])
    b.cz(g,masks['t']);b.free(masks['t'])
    # rho(1/C)=A/g+1+F in the selected chart.
    b.z(masks['r'][0]);b.cz(F,masks['r'][0])
    b.cz(F,masks['f'][0]);b.free(masks['f'])
    # 1/g(1/C)=Norm(C)/g=A²/g+A+(K+(K+1)F)g.
    b.cz(A,masks['i'])
    f=ar.field(12)
    ar.phase_linear(b,g,masks['i'],[f.mul(K,1<<j) for j in range(12)])
    for i,x in enumerate(g):
        for j in ar.bits(f.mul(K^1,1<<i)):
            b.ccz(F,x,masks['i'][j])
    affine_inverse_g_character(b,A,g,dict(i=masks['h'],r=masks['r'],h=masks['i']))
    for key in ('h','r','i'):b.free(masks[key])
    b.cswap(F,A,g)
    fm=b.alloc_bits(1);b.hmr(F,fm[0]);b.free(F)
    phase_zero(b,g,fm[0]);b.free(fm)


def _erase_inverse12(b,x,xi):
    m=b.alloc_bits(12);b.hmr(xi,m);b.free(xi)
    phase_inverse36_pivot(b,x,m);b.free(m)


def _scale_with_inverse(b,x,y,yi,inverse=False):
    """Closed target scaling with held y and yi=1/y; y is nonzero."""
    out=b.alloc_qubits(12)
    ar.mul_xor0(b,x,yi if inverse else y,out)
    m=b.alloc_bits(12);b.hmr(x,m);b.swap(x,out);b.free(out)
    ar.phase_product(b,x,y if inverse else yi,m);b.free(m)


def close_chart(b,C,masks):
    """Pay the exact six characters of nonzero selected gauge C."""
    assert set(masks)=={'g','i','h','t','r','f'}
    r,g=C[:12],C[12:]
    F=b.alloc_qubits(1)[0];zero_toggle(b,g,F,r);b.cswap(F,r,g)
    gi=inverse_initialized(b,g)
    _scale_with_inverse(b,r,g,gi,True)
    for x,key in ((g,'g'),(gi,'i'),(r,'r')):
        b.cz(x,masks[key]);b.free(masks[key])
    b.cz(F,masks['f'][0]);b.free(masks['f'])
    _erase_inverse12(b,g,gi)
    # For the even-degree scalar field, the completed chart's trace-zero
    # value is1, exactly the original q=r²+r+K+(K+1)F convention.
    assert chart_data(12,K)[2]==1
    chart(b,r,F,K)
    h=b.alloc_qubits(12);ar.mul_xor0(b,g,r,h)
    b.cz(h,masks['h']);b.free(masks['h'])
    phase_inverse36_pivot(b,h,masks['t']);b.free(masks['t'])
    hm=b.alloc_bits(12);b.hmr(h,hm);b.free(h)
    ar.phase_product(b,g,r,hm);b.free(hm)
    chart(b,r,F,K,True)
    gi=inverse_initialized(b,g)
    _scale_with_inverse(b,r,g,gi,False)
    _erase_inverse12(b,g,gi)
    b.cswap(F,r,g)
    fm=b.alloc_bits(1);b.hmr(F,fm[0]);b.free(F)
    phase_zero(b,g,fm[0]);b.free(fm)
