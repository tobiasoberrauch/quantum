"""Consume a promised-nonzero GF64 input with an exact phase transcript."""
from pathlib import Path
from types import FunctionType,SimpleNamespace,ModuleType,CodeType
import sys,json
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path[:0]=[str(ROOT/'exp/r-main/narrow240')]
import decode_combo as combo
import frozen_chart
import retained_core_safe27 as retained
import norm_cache
from exp.jet24 import pro_jet as jet
from exp.inverse_search import inverse20 as ref
from exp.noscratch import schedules
from exp.arithmetic import field as ar
PLAN=json.loads((HERE/'nonzero_plan16.json').read_text())
TRACE=[]

def change_basis(b,live,rows):
    columns=[sum(((r>>(j+1))&1)<<i for i,r in enumerate(rows)) for j in range(len(live))]
    ar.linear_inplace(b,live,columns)
    for q,r in zip(live,rows):
        if r&1:b.x(q)

def retire(b,live,pool,transcript,record):
    change_basis(b,live,record['rows'])
    for action in record['retire']:
        p=action['index']
        for j in action['mix']:b.cx(live[j],live[p])
        q=live.pop(p);m=b.alloc_bits(1)[0];b.hmr(q,m)
        for term in action['phase']:
            if term[0]=='constant':b.z(m)
            elif term[0]=='linear':b.cz(live[term[1]],m)
            elif term[0]=='pair':b.ccz(live[term[1]],live[term[2]],m)
            else:b.cx(m,transcript[term[1]])
        b.free(m);pool.append(q)

def inverse6_nonzero_consume16(b,x):
    """x <- 1/x for x!=0; return original-x HMR character in canonical basis."""
    assert len(x)==6
    ar.linear_inplace(b,x,jet.TO6)
    raw=b.alloc_qubits(6)
    for j,(left,right) in enumerate(jet.RAW):
        with ref.expose_pair(b,x,left,right) as (p,q):b.init_and(p,q,raw[j])
    w=ref.inverse3_virtual(b,list(x)+list(raw),ref.norm_forms(1))
    pool=list(b.alloc_qubits(1))
    all_wires=list(x)+list(raw)+list(w)+pool[:]
    live=list(x)+list(raw)+list(w)
    transcript=b.alloc_bits(6);b.bit_store(transcript,False)
    retire(b,live,pool,transcript,PLAN['begin'])
    for step in PLAN['steps']:
        out=pool.pop()
        with ref.expose_pair(b,live,step['left'],step['right']) as (p,q):b.init_and(p,q,out)
        live.append(out);retire(b,live,pool,transcript,step)
    retire(b,live,pool,transcript,PLAN['final'])
    assert len(live)==6
    for i,target in enumerate(x):
        source=live[i]
        if str(source)==str(target):continue
        other=next((j for j,q in enumerate(live) if str(q)==str(target)),None)
        b.swap(source,target);live[i]=target
        if other is not None:live[other]=source
    retained=set(map(str,x));b.free([q for q in all_wires if str(q) not in retained])
    return transcript

def stream_nonzero(b,x):
    live=b.num_allocated_qubits
    if len(x)==6:
        selected=live+10<=889
        TRACE.append(dict(live=live,selected=selected))
        if selected:return inverse6_nonzero_consume16(b,x)
    return fallback(b,x)

fallback=combo.xsub.clone(schedules.inverse_stream_noscratch,dict(schedules.inverse_stream_noscratch.__globals__,inverse_stream_noscratch=stream_nonzero))

def functions(entry):
    seen=set();found=[]
    def code_names(code):
        names=set(code.co_names)
        for item in code.co_consts:
            if isinstance(item,CodeType):names.update(code_names(item))
        return names
    def visit(value):
        if id(value) in seen:return
        seen.add(id(value))
        if isinstance(value,FunctionType):
            found.append(value)
            for name in code_names(value.__code__):
                if name in value.__globals__:visit(value.__globals__[name])
            for cell in value.__closure__ or ():visit(cell.cell_contents)
        elif isinstance(value,(SimpleNamespace,ModuleType)):
            path=getattr(value,'__file__',None)
            if path is None or str(ROOT) in str(path):
                for item in vars(value).values():visit(item)
        elif isinstance(value,dict):
            for item in value.values():visit(item)
        elif isinstance(value,(tuple,list)):
            for item in value:visit(item)
    visit(entry);return found

def make_stream(ceiling):
    def chosen(b,x):
        if len(x)==6 and b.num_allocated_qubits+10<=ceiling:
            return inverse6_nonzero_consume16(b,x)
        return recursive(b,x)
    recursive=combo.xsub.clone(schedules.inverse_stream_noscratch,dict(schedules.inverse_stream_noscratch.__globals__,inverse_stream_noscratch=chosen))
    return chosen

def keep_for_fast_inverse(b,D):
    k=min(6,max(0,889-b.num_allocated_qubits-10))
    to,back=norm_cache.layout(k)
    saved=b.alloc_qubits(k)
    ar.linear_xor(b,D,saved,[v&((1<<k)-1) for v in to])
    return saved

def install(entry,forward=True,reverse=True,character=True,ceiling=889,retune_cache=False):
    """Patch only chart routines whose input/scalar norm is nonzero by invariant."""
    codes=set()
    if forward:codes.add(frozen_chart.normalize.__code__)
    if reverse:codes.add(retained.normalize_early.__code__)
    if character:codes.add(retained.linear_inverse_character.__code__)
    stream=stream_nonzero if ceiling==889 else make_stream(ceiling)
    extraction=entry.__globals__['extraction'];replacements={}
    for fn in functions(extraction):
        if fn.__code__ in codes:
            scope=dict(fn.__globals__,inverse_stream_noscratch=stream)
            if retune_cache and fn.__code__ is retained.linear_inverse_character.__code__:
                old_core=scope['core']
                cached=SimpleNamespace(**dict(vars(old_core.norm_cache),keep=keep_for_fast_inverse))
                scope['core']=SimpleNamespace(**dict(vars(old_core),norm_cache=cached))
            replacements[id(fn)]=combo.xsub.clone(fn,scope)
    assert replacements
    scope=dict(entry.__globals__,extraction=combo.xsub.private_rebind(extraction,replacements))
    return combo.xsub.clone(entry,scope)

decode=install(combo.decode)
assert decode.__globals__['convert_safe'] is combo.decode.__globals__['convert_safe']
assert decode.__globals__['baseline'] is combo.decode.__globals__['baseline']
