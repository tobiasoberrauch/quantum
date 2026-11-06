"""Exact reverse middle fusion at the public root and degree-14 blocks.

The zero predicate is X-measured only while the three weight words coexist.
It is reconstructed from the restored pivot and its character is consumed
before the ordinary scalar restoration continues.
"""
from pathlib import Path
from types import FunctionType
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'research/agents/a08'),
              str(ROOT/'research/agents/a12'),
              str(ROOT/'research/agents/a01')]
import scalar_compact_v3 as scalar
import reverse_root_lifetime
p,ar=scalar.p,scalar.ar


def install(cv):
    starts=(17,14)
    scope=scalar.scope_of(cv)
    short=dict(zip(cv.__code__.co_freevars,cv.__closure__))['core'].cell_contents.__globals__
    reverse_root_lifetime.install(cv)
    original_solve=scope['look_solve']
    original_root=short['look_root_cached']
    original_product=scope['dk'].shifted_product
    pre=scope['direct_pre']
    dcells=dict(zip(pre.__code__.co_freevars,pre.__closure__))
    original_handed=dcells['handed'].cell_contents
    hc=dict(zip(original_handed.__code__.co_freevars,original_handed.__closure__))
    handed_scope=hc['scope'].cell_contents
    close_heads=hc['close_heads'].cell_contents
    original_restore=handed_scope['high_full_restore']
    starts=frozenset(starts)
    bottom_to_top={m-2:m for m in starts}
    frame_to_top={m-j:m for m in starts for j in range(3)}
    assert len(frame_to_top)==3*len(starts)
    frames=[]
    original_hold=scope['hold_flag']
    retained_starts=frozenset((min(starts),))
    retained_levels=frozenset(n for top in retained_starts for n in (top,top-1))

    def hold_flag(b,F):
        if frames and frames[-1]['reverse'] and not frames[-1]['restored']:
            frame=frames[-1];n=frame['m']+1
            if n in retained_levels:
                held=frame['phase'].setdefault('_a14_held_reverse_gaps',{})
                assert n not in held
                held[n]=F
                mask=b.alloc_bits(1);b.bit_store(mask,False)
                return mask
        return original_hold(b,F)

    # The quotient pipeline owns closure dictionaries as well as function
    # globals. Patch all of those owners, not merely the dispatch dictionary.
    owners={};seen=set()
    def visit(value):
        if id(value) in seen:return
        seen.add(id(value))
        if isinstance(value,dict):
            if 'hold_flag' in value:
                owners[id(value)]=value
                for name in ('q_post','prior_q_post'):
                    if name in value:visit(value[name])
        elif isinstance(value,FunctionType):
            visit(value.__globals__)
            for cell in value.__closure__ or ():
                try:child=cell.cell_contents
                except ValueError:continue
                if isinstance(child,(dict,FunctionType)):visit(child)
    visit(scope);visit(handed_scope)
    for owner in owners.values():owner['hold_flag']=hold_flag

    def solve(b,f,g,payloads,H=None,parent=None,reverse=False,phase=None):
        frames.append(dict(m=len(f)-1,f=f,g=g,payloads=payloads,
                           phase=phase,reverse=reverse,restored=False))
        try:return original_solve(b,f,g,payloads,H,parent,reverse,phase)
        finally:frames.pop()

    def root(b,O,g,payloads,reverse,phase):
        frames.append(dict(m=len(O),f=None,g=g,payloads=payloads,
                           phase=phase,reverse=reverse,restored=False))
        try:return original_root(b,O,g,payloads,reverse,phase)
        finally:frames.pop()

    def fuse(b,f,g,F):
        frame=frames[-1];m=frame['m'];top=bottom_to_top[m]
        block=frames[-3:];cutoff=top-3
        assert [row['m'] for row in block]==[top,top-1,top-2]
        assert block[-1]['f'] is f and block[-1]['g'] is g
        if top in retained_starts:
            held=frame['phase']['_a14_held_reverse_gaps']
            F0=held.pop(top);F1=held.pop(top-1)
        else:
            F0=scope['fresh_zero_flag'](b,block[1]['f'][-1])
            F1=scope['fresh_zero_flag'](b,block[2]['f'][-1])
        for j in range(len(frame['payloads'])):
            heads=[row['payloads'][j][-1] for row in block]
            scope['payload_middle'](b,f[:cutoff],g[:cutoff],heads,
                frame['payloads'][j][:cutoff],block[1]['f'][-2:],F0,F1,F)
        for flag,n in ((F0,top),(F1,top-1)):
            mask=original_hold(b,flag)
            b.cx(mask,frame['phase']['return_mask'][n]);b.free(mask)
        for row in block:row['restored']=True

    def shifted_product(b,g,x,out,F):
        if not frames:return original_product(b,g,x,out,F)
        frame=frames[-1];m=frame['m']
        if not frame['reverse'] or not frame['restored'] or m not in frame_to_top:
            return original_product(b,g,x,out,F)
        cutoff=frame_to_top[m]-3
        assert len(out)==m-1
        for i in range(cutoff,len(out)):
            with scope['dk'].selected(b,g[i],g[i-1],F) as coefficient:
                ar.mul_xor0(b,coefficient,x,out[i])

    def handed(b,f,g,payloads,F,incoming,defer,Z0):
        m=len(f)-1
        if m not in bottom_to_top:
            return original_handed(b,f,g,payloads,F,incoming,defer,Z0)
        assert frames[-1]['reverse'] and frames[-1]['m']==m and not defer
        b.cx(Z0,g[-2][0]);masks=original_restore(b,f,g,F);b.cx(Z0,g[-2][0])
        zm=b.alloc_bits(1);b.hmr(Z0,zm[0]);b.free(Z0)
        fuse(b,f,g,F)
        scope['pivot'](b,g,F);a=g[-1]
        for v in payloads:shifted_product(b,g[:-1],v[-1],v[:-1],F)
        ai,Z,saved=scalar.inverse_zero_normpair(b,a)
        b.cz(Z,zm[0]);b.free(zm)
        scope['consume'](b,ai,Z,incoming)
        b.cx(Z,a[0]);b.cx(Z,ai[0])
        for v in payloads:scope['scale'](b,v[-1],a,ai,False)
        close_heads(b,f,g,ai,F,masks)
        b.cx(Z,ai[0]);b.cx(Z,a[0]);scalar.erase_normpair(b,a,ai,Z,saved)
        scope['pivot'](b,g,F)

    dcells['handed'].cell_contents=handed
    scope['look_solve']=solve
    scope['dk'].shifted_product=shifted_product
    handed_scope['dk'].shifted_product=shifted_product
    short['old'].look_solve=solve
    short['look_root_cached']=root
    return cv

