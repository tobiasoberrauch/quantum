"""Width-safe paired normalization in high-component denominator chart.

All scalar-inverse and gauge debts are explicit; forward chain unchanged.
This is an intentionally conservative combined-width baseline, not a cost win.
"""
from pathlib import Path
import sys
from functools import lru_cache
from types import FunctionType
root=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(root/'playbook/kit/decoder'),str(root/'playbook/kit')]
from final_decoder import decode as ref
from exp.decoder.common import *
from exp.noscratch.schedules import inverse_stream_noscratch
from exp.mul99.phase36 import phase_inverse36_pivot
from final_decoder.conversion import clear_flag


def clone(fn,scope):
 out=FunctionType(fn.__code__,scope,fn.__name__,fn.__defaults__,fn.__closure__)
 out.__kwdefaults__=fn.__kwdefaults__;return out


def scale_defer(b,x,f):
 out=b.alloc_qubits(12);ar.mul_xor0(b,x,f,out)
 m=b.alloc_bits(12);b.hmr(x,m);b.swap(x,out);b.free(out);return m


def add_masks(b,*ms):
 out=ms[0]
 for m in ms[1:]:b.cx(m,out);b.free(m)
 return out


@lru_cache(None)
def norm_chart_columns():
 # r -> r^2+r, with one kernel bit to make the map invertible.
 f=ar.field(12);base=[f.mul(1<<i,1<<i)^(1<<i)for i in range(12)]
 # kernel={0,1}; keep r's low bit, and inject a missing image direction.
 for extra in range(1,4096):
  cols=[v|((1 if i==0 else 0)<<12)for i,v in enumerate(base)]+[extra]
  try:back=ar.inverse_columns(cols)
  except (AssertionError,ValueError,StopIteration):continue
  return tuple(cols),tuple(back)
 raise AssertionError('no rank13 norm chart')


def chart_norm(b,r,F,h,reverse=False):
 cols,back=norm_chart_columns();w=list(r)+[h]
 # q=r²+r+K except subfield chart F=1,r=0, where q=1.
 if not reverse:
  ar.linear_inplace(b,w,cols)
  for i in ar.bits(K):b.x(r[i])
  for i in ar.bits(K^1):b.cx(F,r[i])
 else:
  for i in ar.bits(K^1):b.cx(F,r[i])
  for i in ar.bits(K):b.x(r[i])
  ar.linear_inplace(b,w,back)


def correct_subfield(b,x,F):
 # In the subfield chart, swap input halves and use final shear r+1-F.
 # This costs one controlled swap rather than two controlled shears.
 b.cswap(F,x[:12],x[12:])


def normalize(b,N,D,L):
 # sqrt(L)/D, then square, equals L/D² with no nonlinear cost.
 ref.external_square24(b,L,True)
 r,g=D[:12],D[12:]
 F=ref.guarded.fresh_zero_flag(b,g);b.cswap(F,r,g)
 oldg=inverse_stream_noscratch(b,g)
 olda=scale_defer(b,r,g)
 for x in (N,L):correct_subfield(b,x,F)
 for x in (N,L):ar.mul_xor0(b,r,x[12:],x[:12])
 half_masks=[scale_defer(b,x[12:],g)for x in (N,L)]
 im=inverse_stream_noscratch(b,g) # g restored
 b.cz(g,oldg);b.free(oldg)
 ar.phase_product(b,r,g,olda);b.free(olda)
 for x,m in zip((N,L),half_masks):ar.phase_product(b,x[12:],g,m);b.free(m)
 h=b.alloc_qubits(1)[0];chart_norm(b,r,F,h)
 gm=scale_defer(b,g,r) # g*q
 chart_norm(b,r,F,h,True);b.free(h)
 hm=inverse_stream_noscratch(b,g) # t=1/(g*q)
 half_masks=[scale_defer(b,x[:12],g)for x in (N,L)]
 tm=inverse_stream_noscratch(b,g) # g*q restored
 for x,m in zip((N,L),half_masks):ar.phase_product(b,x[:12],g,m);b.free(m)
 b.x(r[0]);b.cx(F,r[0])
 for x in (N,L):ar.mul_xor0(b,r,x[:12],x[12:]);b.swap(x[:12],x[12:])
 b.cx(F,r[0]);b.x(r[0]);ref.external_square24(b,L)
 rm=b.alloc_bits(12);gg=b.alloc_bits(12);fm=b.alloc_bits(1)
 b.hmr(r,rm);b.hmr(g,gg);b.free(D);b.hmr(F,fm[0]);b.free(F)
 return dict(g=gm,i=im,h=add_masks(b,hm,gg),t=tm,r=rm,f=fm)


def pay_charts(b,D,forward,reverse):
 # Reciprocity preserves F and q, sends r->r+1 (unless F), and
 # (g,1/g,g*q,1/(g*q))->(t,h,1/g,g).
 r,g=D[:12],D[12:]
 F=ref.guarded.fresh_zero_flag(b,g)
 b.cz(F,forward['f'][0]);b.cz(F,reverse['f'][0])
 b.free(forward['f']);b.free(reverse['f'])
 b.z(reverse['r'][0]);b.cz(F,reverse['r'][0])
 masks=dict(g=add_masks(b,forward['g'],reverse['t']),
            i=add_masks(b,forward['i'],reverse['h']),
            h=add_masks(b,forward['h'],reverse['i']),
            t=add_masks(b,forward['t'],reverse['g']),
            r=add_masks(b,forward['r'],reverse['r']))
 b.cswap(F,r,g)
 oldg=inverse_stream_noscratch(b,g)
 olda=scale_defer(b,r,g)
 im=inverse_stream_noscratch(b,g)
 b.cz(g,oldg);b.free(oldg)
 ar.phase_product(b,r,g,olda);b.free(olda)
 masks['i']=add_masks(b,masks['i'],im)
 b.cz(g,masks['g']);b.free(masks['g'])
 b.cz(r,masks['r']);b.free(masks['r'])
 h=b.alloc_qubits(1)[0];chart_norm(b,r,F,h)
 gm=scale_defer(b,g,r)
 chart_norm(b,r,F,h,True);b.free(h)
 b.cz(g,masks['h']);b.free(masks['h'])
 phase_inverse36_pivot(b,g,masks['t']);b.free(masks['t'])
 # Restore g from g*q, retaining r through the rank11 affine norm chart.
 h=b.alloc_qubits(1)[0];chart_norm(b,r,F,h)
 qm=inverse_stream_noscratch(b,r)
 hm=scale_defer(b,g,r)
 qi=inverse_stream_noscratch(b,r)
 b.cz(r,qm);b.free(qm)
 ar.phase_product(b,g,r,hm);b.free(hm)
 phase_inverse36_pivot(b,r,qi);b.free(qi)
 chart_norm(b,r,F,h,True);b.free(h)
 am=scale_defer(b,r,g)
 b.cz(g,gm);b.free(gm)
 # Fresh old-r mask and both normalizers' reciprocal-g debts.
 z=inverse_stream_noscratch(b,g)
 b.cz(g,masks['i']);b.free(masks['i'])
 ar.phase_product(b,r,g,am);b.free(am)
 zi=inverse_stream_noscratch(b,g)
 b.cz(g,z);b.free(z)
 phase_inverse36_pivot(b,g,zi);b.free(zi)
 b.cswap(F,r,g);ref.guarded.zero_toggle(b,g,F);b.free(F)


def external_node_chain(b,words,gi,reverse=False,token=None,normalizer=None):
 gnode=ref.groups[gi];N=combine(words[gnode['word']:gnode['word']+2]);L=combine(words[gnode['word']+2:gnode['word']+4])
 heads=[words[2*i:2*i+2]for i in range(2*gi)]
 params=[];c=0
 for i in range(2*gi):
  q=ref.ks[i]^gnode['kap'];params.append((q,c));c^=inv(q)
 assert c==0
 if not reverse:
  D=b.alloc_qubits(24);b.x(D[0])
  for i,(head,(q,c))in enumerate(zip(heads,params)):
   ref.external_chain_step(b,head,N,D,L,q,gnode['c'],c,first=i==0)
  pole=zero_flag24(b,D);b.cswap(pole,N,D)
  norm=normalize(b,N,D,L)
  return dict(pole=pole,norm=norm)
 pole=token['pole'];D=b.alloc_qubits(24);b.x(D[0]);b.cswap(pole,N,D)
 for head,(q,c)in reversed(list(zip(heads,params))[1:]):ref.external_chain_step(b,head,N,D,L,q,gnode['c'],c,True)
 q0=params[0][0];scalepair(b,N,inv(q0));b.swap(N,D);scalepair(b,L,inv(q0))
 norm=normalize(b,N,D,L)
 a,h=heads[0];cx(b,h,a,gnode['c']);b.cx(combine(heads[0]),N);cx(b,h,a,gnode['c']);b.cx(h,L[:12])
 D=b.alloc_qubits(24);b.x(D[0])
 for i,(head,(q,c))in enumerate(zip(heads,params)):ref.external_scalar_step(b,head,N,D,q,gnode['c'],first=i==0)
 b.cswap(pole,N,D);pay_charts(b,D,token['norm'],norm);b.cswap(pole,N,D)
 clear_flag24(b,D,pole)
 for i in reversed(range(len(heads))):
  if i==1:scalar_erase_second24(b,heads[i],N,D,params[i][0],gnode['c'],q0)
  else:ref.external_scalar_step(b,heads[i],N,D,params[i][0],gnode['c'],True,first=i==0)
 b.x(D[0]);b.free(D)


def and_flag(b,x):
 ladder=b.alloc_qubits(len(x)-1)
 b.init_and(x[0],x[1],ladder[0])
 for i in range(1,len(ladder)):b.init_and(ladder[i-1],x[i+1],ladder[i])
 for i in reversed(range(len(ladder)-1)):
  if i:b.del_and(ladder[i-1],x[i+1],ladder[i])
  else:b.del_and(x[0],x[1],ladder[0])
 b.free(ladder[:-1]);return ladder[-1]


def phase_and(b,x,m):
 b.push_condition(m)
 nodes=b.alloc_qubits(len(x)-2)
 b.init_and(x[0],x[1],nodes[0])
 for i in range(1,len(nodes)):b.init_and(nodes[i-1],x[i+1],nodes[i])
 b.cz(nodes[-1],x[-1])
 for i in reversed(range(len(nodes))):
  if i:b.del_and(nodes[i-1],x[i+1],nodes[i])
  else:b.del_and(x[0],x[1],nodes[0])
 b.free(nodes);b.pop_condition()


def erase_and(b,x,F):
 m=b.alloc_bits(1);b.hmr(F,m[0]);b.free(F);phase_and(b,x,m[0]);b.free(m)


def zero_flag24(b,x):
 b.x(x);a=and_flag(b,x[:12]);c=and_flag(b,x[12:]);F=b.alloc_qubits(1)[0]
 b.init_and(a,c,F);erase_and(b,x[:12],a);erase_and(b,x[12:],c);b.x(x)
 return F


def clear_flag24(b,x,F):
 m=b.alloc_bits(1);b.hmr(F,m[0]);b.free(F)
 b.push_condition(m[0]);b.x(x)
 a=and_flag(b,x[:12]);c=and_flag(b,x[12:]);b.cz(a,c)
 erase_and(b,x[:12],a);erase_and(b,x[12:],c)
 b.x(x);b.pop_condition();b.free(m)
