"""Exact three-frame forward payload fusion in a retained middle basis.

Coefficient high heads are processed normally. The third long coefficient
update is postponed until all low payload updates have been applied in the
middle polynomial pair. Every flag chart has its full polynomial weight.
The ordinary reverse converter consumes the unchanged transcript interface.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'research/agents/a01'),str(ROOT/'research/agents/a03')]
import ported as p
from rebind_graph import private_rebind
from exp.mul99.phase36 import phase_classical_parity


def mask_word(b,x,F,G,not_f=False,not_g=False):
    if not_f:b.x(F)
    if not_g:b.x(G)
    h=b.alloc_qubits(1)[0];b.init_and(F,G,h)
    out=b.alloc_qubits(12)
    for a,c in zip(x,out):b.init_and(h,a,c)
    b.del_and(F,G,h);b.free(h)
    if not_g:b.x(G)
    if not_f:b.x(F)
    return out


def erase_mask(b,x,out,F,G,not_f=False,not_g=False):
    r=b.alloc_bits(12);b.hmr(out,r);b.free(out)
    if not_f:b.x(F)
    if not_g:b.x(G)
    phase_classical_parity(b,F,G,x,r)
    if not_g:b.x(G)
    if not_f:b.x(F)
    b.free(r)


def copy_flag(b,F,x,y,complement=False):
    if complement:b.x(F)
    for a,c in zip(x,y):b.ccx(F,a,c)
    if complement:b.x(F)


def phase_flag(b,F,x,r,complement=False):
    if complement:b.x(F)
    for a,c in zip(x,r):b.ccz(F,a,c)
    if complement:b.x(F)


def payload_middle(b,lo_f,lo_g,heads,out,q,F0,F1,F2):
    """Accumulate all three deferred low updates, for every flag pattern.

    heads=(s0,s1,s2), q=(q10,q11). P has degree<=1, Q degree<=2.
    Each ephemeral word is measured only while its defining sources survive.
    """
    s0,s1,s2=heads;q0,q1=q
    # M=(1+F0)(1+F1)s0. Its AND flag is retired before both outputs exist.
    M=mask_word(b,s0,F0,F1,True,True)
    P0=b.alloc_qubits(12);ar.mul_xor0(b,q0,M,P0)
    P1=b.alloc_qubits(12);ar.mul_xor0(b,q1,M,P1)
    b.cx(M,P0);b.cx(M,P1)
    copy_flag(b,F0,s0,P0,True);copy_flag(b,F1,s1,P0,True)
    copy_flag(b,F1,s0,P1,True)
    convolution(b,lo_f,[P0,P1],out)
    r0=b.alloc_bits(12);r1=b.alloc_bits(12)
    b.hmr(P0,r0);b.hmr(P1,r1);b.free(P0);b.free(P1)
    ar.phase_product(b,q0,M,r0);ar.phase_product(b,q1,M,r1)
    b.cz(M,r0);b.cz(M,r1)
    phase_flag(b,F0,s0,r0,True);phase_flag(b,F1,s1,r0,True)
    phase_flag(b,F1,s0,r1,True)
    b.free(r0);b.free(r1);erase_mask(b,s0,M,F0,F1,True,True)

    # M=(1+F0)F1s0. It becomes Q0 during the convolution, then is restored.
    M=mask_word(b,s0,F0,F1,True,False)
    Q1=b.alloc_qubits(12);ar.mul_xor0(b,q0,M,Q1)
    Q2=b.alloc_qubits(12);ar.mul_xor0(b,q1,M,Q2)
    b.cx(M,Q1)
    copy_flag(b,F1,s0,Q1);copy_flag(b,F1,s1,Q1);copy_flag(b,F2,s2,Q1)
    copy_flag(b,F0,s0,M,True);copy_flag(b,F2,s2,M,True)
    convolution(b,lo_g,[M,Q1,Q2],out)
    copy_flag(b,F2,s2,M,True);copy_flag(b,F0,s0,M,True)
    r1=b.alloc_bits(12);r2=b.alloc_bits(12)
    b.hmr(Q1,r1);b.hmr(Q2,r2);b.free(Q1);b.free(Q2)
    ar.phase_product(b,q0,M,r1);ar.phase_product(b,q1,M,r2);b.cz(M,r1)
    phase_flag(b,F1,s0,r1);phase_flag(b,F1,s1,r1);phase_flag(b,F2,s2,r1)
    b.free(r1);b.free(r2);erase_mask(b,s0,M,F0,F1,True,False)


def pre_partial(b,f,g,payloads,F,cutoff,defer_coefficient=False):
    pivot(b,g,F);a=g[-1];q0,q1=f[-2:]
    def action(ai):
        for v in payloads:scale(b,v[-1],a,ai,True)
        # Only the future head strip is needed before the block's low update.
        for i in range(cutoff,len(g)-1):
            with dk.selected(b,g[i],g[i-1],F) as coefficient:
                for v in payloads:ar.mul_xor0(b,coefficient,v[-1],v[i])
        scale(b,q1,a,ai,True);cross(b,g,q1,q0,F);scale(b,q0,a,ai,True)
        if not defer_coefficient:dk.shifted_conv(b,g[:-1],[q0,q1],f[:-2],F)
    result=inverse_apply(b,a,action,None,True)
    pivot(b,g,F)
    return result


def look_solve(b,f,g,payloads,H=None,parent=None,reverse=False,phase=None):
    m=len(f)-1
    if reverse or m not in BLOCK_LEVELS:
        return ordinary_solve(b,f,g,payloads,H,parent,reverse,phase)
    assert m-2>=THRESHOLD and not any(n in KEEP_CHILD for n in (m,m-1,m-2))
    cutoff=m-3;frames=[]
    for i in range(3):
        n=len(f)-1;F=fresh_zero_flag(b,g[-1])
        carry=pre_partial(b,f,g,payloads,F,cutoff,i==2)
        frames.append((n,f,g,payloads,H,parent,F,carry))
        if i==2:break
        aligned(b,f,g,F)
        phase['incoming_gap'][n]=hold_flag(b,F)
        childparent=([v[-1]for v in payloads],f[-1],f[-2])
        f,g,payloads,H,parent=g,f[:-2],[v[:-1]for v in payloads],None,childparent
    # These are the same predicates as the two already measured parent flags.
    F0=fresh_zero_flag(b,frames[1][1][-1])
    F1=fresh_zero_flag(b,frames[2][1][-1])
    F2=frames[2][6]
    for j in range(len(payloads)):
        heads=[frame[3][j][-1] for frame in frames]
        payload_middle(b,f[:cutoff],g[:cutoff],heads,payloads[j][:cutoff],
                       frames[1][1][-2:],F0,F1,F2)
    for flag,n in ((F0,m),(F1,m-1)):
        mask=hold_flag(b,flag)
        b.cx(mask,phase['incoming_gap'][n]);b.free(mask)
    # Finish the postponed third coefficient division in its original frame.
    pivot(b,g,F2)
    dk.shifted_conv(b,g[:-1],f[-2:],f[:-2],F2)
    pivot(b,g,F2)
    aligned(b,f,g,F2)
    phase['incoming_gap'][m-2]=hold_flag(b,F2)
    childparent=([v[-1]for v in payloads],f[-1],f[-2])
    look_solve(b,g,f[:-2],[v[:-1]for v in payloads],None,childparent,False,phase)
    for n,f,g,payloads,H,parent,unused,carry in reversed(frames):
        F=phase['returned_gap'].pop(n)
        aligned(b,f,g,F)
        phase['a'][n]=direct_post(b,f,g,payloads,F,H,parent,
                                 incoming=carry,defer=True,phase=phase)
        if n in KEEP_FULL:phase['held_gap'][n]=F
        else:phase['gap_flags'][n]=hold_flag(b,F)


def make_decoder(levels=(16,)):
    cv=p.install_dot_cache(p.install_base_zero(p.install_undo_zeros(
        p.install_child_inverse(p.install_retained_gaps(p.make_converter())))))
    cells=dict(zip(cv.__code__.co_freevars,cv.__closure__))
    short=cells['core'].cell_contents.__globals__
    scope=short['old'].direct_post.__globals__
    scope.update(BLOCK_LEVELS=frozenset(levels),ordinary_solve=scope['look_solve'],
                 convolution=lambda b,x,y,out: scope['dk'].conv(b,x,y,out,len(x)+len(y)-1),phase_classical_parity=phase_classical_parity)
    for fun in (mask_word,erase_mask,copy_flag,phase_flag,payload_middle,pre_partial,look_solve):
        scope[fun.__name__]=p.clone(fun,scope)
    short['old'].look_solve=scope['look_solve']
    cv=private_rebind(cv,p.base.replacements,p.ROOT)
    import local_norm
    return local_norm.make_decoder(count=1,plain_count=1,plain_levels=(3,4,5),
                                   converter=cv,reference_decode=p.decode,factorized=True)


decode=make_decoder()
