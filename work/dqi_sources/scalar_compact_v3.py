"""Exact local norm-pair retention in the reverse converter.

Only the A01 port, its private graph copier, and unchanged kit arithmetic
are dependencies. No research diagnostic or losing candidate is imported.
"""
from pathlib import Path
from contextlib import contextmanager
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'research/agents/a01'))
import ported as p
from rebind_graph import private_rebind
import exact_subs as xs
from exp.noscratch.schedules import norm_xor_noscratch
from exp.noscratch.kernels import mul_xor_noscratch
from exp.arithmetic.lowwidth import classical_transpose
ar=p.ar


def prefix(b,x):
    to,frm,K=ar.tower(12);ar.linear_inplace(b,x,to)
    norm=b.alloc_qubits(6);norm_xor_noscratch(b,x,norm,K)
    invnorm,Z=xs.inverse6_joint18_12extra(b,norm)
    ar.linear_inplace(b,x,frm)
    return Z,(norm,invnorm)


def finish(b,x,saved):
    norm,invnorm=saved
    to,frm,K=ar.tower(12);ar.linear_inplace(b,x,to)
    out=b.alloc_qubits(12);b.cx(x[6:],x[:6])
    mul_xor_noscratch(b,x[:6],invnorm,out[:6])
    mul_xor_noscratch(b,x[6:],invnorm,out[6:])
    b.cx(x[6:],x[:6]);ar.linear_inplace(b,x,frm);ar.linear_inplace(b,out,frm)
    return out


def inverse_zero_normpair(b,x):
    to,frm,K=ar.tower(12);ar.linear_inplace(b,x,to)
    norm=b.alloc_qubits(6);norm_xor_noscratch(b,x,norm,K)
    invnorm,Z=xs.inverse6_joint18_12extra(b,norm)
    out=b.alloc_qubits(12);b.cx(x[6:],x[:6])
    mul_xor_noscratch(b,x[:6],invnorm,out[:6])
    mul_xor_noscratch(b,x[6:],invnorm,out[6:])
    b.cx(x[6:],x[:6]);ar.linear_inplace(b,x,frm);ar.linear_inplace(b,out,frm)
    return out,Z,(norm,invnorm)


def erase_normpair(b,x,ai,Z,saved,handoff=None):
    norm,invnorm=saved
    mask=b.alloc_bits(12);zm=b.alloc_bits(1)
    b.hmr(ai,mask)
    if handoff is not None:
        b.free(ai);F,phase=handoff
        Zparent=b.alloc_qubits(1)[0];b.init_and(F,Z,Zparent)
        phase.setdefault('_undo_parent_zeros',{})[2]=Zparent
        b.hmr(Z,zm[0]);b.free(Z)
    else:
        b.hmr(Z,zm[0]);b.free(ai);b.free(Z)
    to,frm,K=ar.tower(12);ar.linear_inplace(b,x,to)
    mt=classical_transpose(b,mask,frm)
    b.cx(x[6:],x[:6])
    ar.phase_product(b,x[:6],invnorm,mt[:6])
    ar.phase_product(b,x[6:],invnorm,mt[6:])
    b.cx(x[6:],x[:6]);b.free(mt);b.free(mask)
    b.z(zm[0]);zero_mask=b.alloc_bits(6);b.bit_store(zero_mask,False)
    b.cx(zm[0],zero_mask[0]);ar.phase_product(b,norm,invnorm,zero_mask)
    b.free(zero_mask);b.free(zm)
    im=b.alloc_bits(6);b.hmr(invnorm,im);b.free(invnorm)
    xs.phase_inverse6_quad4(b,norm,im);b.free(im)
    ar._erase_norm(b,x,norm,K);b.free(norm);ar.linear_inplace(b,x,frm)


def scale_before_inverse(b,x,a):
    out=b.alloc_qubits(12);ar.mul_xor0(b,x,a,out)
    mask=b.alloc_bits(12);b.hmr(x,mask);b.swap(x,out);b.free(out)
    return mask


@contextmanager
def selected_partial(b,x,y,F,borrow=11):
    b.cswap(F,x[:borrow],y[:borrow])
    z=b.alloc_qubits(12-borrow)
    for j in range(borrow,12):
        b.cx(y[j],x[j]);b.init_and(F,x[j],z[j-borrow]);b.cx(y[j],x[j])
        b.cx(x[j],z[j-borrow])
    yield list(x[:borrow])+list(z)
    mask=b.alloc_bits(12-borrow);b.hmr(z,mask);b.free(z)
    for j in range(borrow,12):
        b.cz(x[j],mask[j-borrow]);b.cx(y[j],x[j])
        b.ccz(F,x[j],mask[j-borrow]);b.cx(y[j],x[j])
    b.free(mask);b.cswap(F,x[:borrow],y[:borrow])


def converter_of(decoder):
    cells=dict(zip(decoder.__code__.co_freevars,decoder.__closure__))
    return cells['g'].cell_contents['convert_safe']


def scope_of(cv):
    core=dict(zip(cv.__code__.co_freevars,cv.__closure__))['core'].cell_contents
    return core.__globals__['old'].direct_post.__globals__


def install_pre(cv,levels=range(6,17),plain_levels=(2,3,4,5)):
    scope=scope_of(cv)
    dcells=dict(zip(scope['direct_pre'].__code__.co_freevars,scope['direct_pre'].__closure__))
    original=dcells['handed'].cell_contents;scope=original.__globals__
    levels=frozenset(levels);plain_levels=frozenset(plain_levels)

    def close_heads(b,f,g,ai,F,masks):
        lo,hi=f[-2:]
        ar.phase_product(b,hi,ai,masks[1]);ar.phase_product(b,lo,ai,masks[0])
        with selected_partial(b,g[-2],g[-3],F)as c:
            p.triple_square_phase(b,hi,c,ai,masks[0])
        for mask in masks:b.free(mask)

    def handed(b,f,g,payloads,F,incoming,defer,Z0):
        if len(f)-1 not in levels:return original(b,f,g,payloads,F,incoming,defer,Z0)
        assert not defer
        b.cx(Z0,g[-2][0]);masks=scope['high_full_restore'](b,f,g,F);b.cx(Z0,g[-2][0])
        scope['pivot'](b,g,F);a=g[-1]
        for v in payloads:scope['dk'].shifted_product(b,g[:-1],v[-1],v[:-1],F)
        b.cx(Z0,a[0]);debts=[scale_before_inverse(b,v[-1],a)for v in payloads];b.cx(Z0,a[0])
        zm=b.alloc_bits(1);b.hmr(Z0,zm[0]);b.free(Z0)
        ai,Z,saved=inverse_zero_normpair(b,a)
        b.cz(Z,zm[0]);b.free(zm);scope['consume'](b,ai,Z,incoming)
        b.cx(Z,a[0]);b.cx(Z,ai[0])
        for v,mask in zip(payloads,debts):ar.phase_product(b,ai,v[-1],mask);b.free(mask)
        close_heads(b,f,g,ai,F,masks)
        b.cx(Z,ai[0]);b.cx(Z,a[0]);erase_normpair(b,a,ai,Z,saved)
        scope['pivot'](b,g,F)

    dcells['handed'].cell_contents=handed;scope['handed_aligned_pre']=handed
    pcells=dict(zip(scope['pre'].__code__.co_freevars,scope['pre'].__closure__))
    plain_original=pcells['plain_handed'].cell_contents

    def plain(b,f,g,payloads,incoming,defer,Z0):
        if len(f)-1 not in plain_levels:return plain_original(b,f,g,payloads,incoming,defer,Z0)
        assert not defer
        a=g[-1];b.cx(Z0,a[0]);masks=scope['full_restore'](b,f,g);b.cx(Z0,a[0])
        for v in payloads:
            for i in range(len(g)-1):ar.mul_xor0(b,g[i],v[-1],v[i])
        b.cx(Z0,a[0]);debts=[scale_before_inverse(b,v[-1],a)for v in payloads];b.cx(Z0,a[0])
        zm=b.alloc_bits(1);b.hmr(Z0,zm[0]);b.free(Z0)
        ai,Z,saved=inverse_zero_normpair(b,a)
        b.cz(Z,zm[0]);b.free(zm);scope['consume'](b,ai,Z,incoming)
        b.cx(Z,a[0]);b.cx(Z,ai[0])
        for v,mask in zip(payloads,debts):ar.phase_product(b,ai,v[-1],mask);b.free(mask)
        scope['close_heads'](b,f,g,ai,masks)
        b.cx(Z,ai[0]);b.cx(Z,a[0]);erase_normpair(b,a,ai,Z,saved)

    pcells['plain_handed'].cell_contents=plain;scope['handed_plain_pre']=plain
    return cv


def install_quotient(decoder,levels=range(1,16)):
    scope=scope_of(converter_of(decoder))['q_post'].__globals__
    original=scope['prior_q_post'];levels=frozenset(levels)

    def q_post(b,q,payloads,H,m,parent,reverse=False,phase=None):
        if not reverse or m not in levels or parent is None:
            return original(b,q,payloads,H,m,parent,reverse,phase)
        tops,p,c=parent
        F=phase['given_gap'].pop(m+1);b.cswap(F,q,p)
        scope['masked_products'](b,F,payloads,c,tops)
        Z,saved=prefix(b,q)
        b.cx(Z,q[0]);debts=[scale_before_inverse(b,v[-1],q)for v in payloads];b.cx(Z,q[0])
        qi=finish(b,q,saved);scope['consume'](b,qi,Z,phase['q'].pop(m))
        b.cx(Z,q[0]);b.cx(Z,qi[0])
        for v,mask in zip(payloads,debts):ar.phase_product(b,qi,v[-1],mask);b.free(mask)
        b.cx(Z,qi[0]);b.cx(Z,q[0]);erase_normpair(b,q,qi,Z,saved)
        for v,t in zip(payloads,tops):b.cswap(F,v[-1],t)
        b.cswap(F,q,p)
        if m+1 not in scope['KEEP_CHILD']:
            phase['return_mask'][m+1]=scope['hold_flag'](b,F)
        else:phase['returned_gap'][m+1]=F

    scope['prior_q_post']=q_post
    return decoder


def install_base(decoder):
    scope=scope_of(converter_of(decoder));original=scope['base_case']

    def base_case(b,f,g,payloads,H,parent,reverse=False,phase=None):
        if not reverse:return original(b,f,g,payloads,H,parent,reverse,phase)
        a=g[0];q=f[-1]
        def action(ai):
            scope['runops'](b,[('s',v[0],True)for v in payloads]+[('s',q,False)],a,ai,True)
        carry=scope['inverse_apply'](b,a,action,phase['a'].pop(1),True)
        scope['q_post'](b,q,payloads,H,1,parent,True,phase)
        Z,saved=prefix(b,a)
        b.cx(Z,a[0]);words=[v[0]for v in payloads]+[q]
        debts=[scale_before_inverse(b,x,a)for x in words];b.cx(Z,a[0])
        ai=finish(b,a,saved);scope['consume'](b,ai,Z,carry)
        b.cx(Z,a[0]);b.cx(Z,ai[0])
        for x,mask in zip(words,debts):ar.phase_product(b,ai,x,mask);b.free(mask)
        b.cx(Z,ai[0]);b.cx(Z,a[0])
        erase_normpair(b,a,ai,Z,saved,(phase['returned_gap'][2],phase))

    scope['base_case']=base_case
    return decoder


def make_decoder(converter=None,reference_decode=None):
    cv=private_rebind(p.convert_safe,p.base.replacements,p.ROOT)if converter is None else converter
    install_pre(cv)
    reference=p.decode if reference_decode is None else reference_decode
    decoder=p.clone(reference,dict(reference.__globals__,convert_safe=cv))
    decoder=private_rebind(p.install_factorized_boundary(decoder),p.base.replacements,p.ROOT)
    install_quotient(decoder);install_base(decoder)
    return decoder


decode=make_decoder()
