import sys, numpy as np
sys.path.insert(0,'scripts')
import emit, extract_plan as ep, tensor_probe as tp
base,k='base',8
words=np.load(base+'/submission.npz')['angle_words']
hdr,lines,nq=emit.header_and_ops(f'{base}/angle_k_{k}.kmb')
ops=[emit.parse(l) for l in lines]
first,last=emit.split_sections(ops,nq,words,k)
start=first
while start>0 and ops[start-1][0]=='CX': start-=1
end=last+1
while end<len(ops) and ops[end][0]=='CX': end+=1
st=emit.init_state(nq,words,k)
s0=emit.run_tt(ops[:start],st); s1=emit.run_tt(ops[start:end],s0)
D=s0^s1
Y=emit.Y;Z=emit.Z
def cross(h):
    t=np.zeros((77,16),dtype=int)-0; t=np.zeros((77,16),dtype=bool); t[Y,Z]=h
    v=t[:77]; d=v^v[:,:1]^v[:1,:]^v[0,0]
    d[76,4:]=False
    return d
X,tie=ep.tensor_of_words(words,k)
for w in [0,1,6,7,8]:
    c=cross(D[11+w]); print('wire',w,'D cross bits',int(c.sum()),'X bits',int(X[:,:,w].sum()),'match',bool((c[1:,1:]==X[:,:,w]).all()), 'rows with diff', np.unique(np.argwhere(c[1:,1:]!=X[:,:,w])[:,0])[:5])
# prefix/suffix effect on word wires
sE=emit.run_tt(ops[end:],s1)
print('prefix changed word wires', [w for w in range(40) if (s0[11+w]!=st[11+w]).any()][:12])
print('suffix changed word wires', [w for w in range(40) if (sE[11+w]!=s1[11+w]).any()][:12])
print('ops around start', lines[start-3:start+6])
print('ops after end', lines[end-2:end+6])
import replan as rp, collections, os
terms=[(int(p),int(x,16),int(b,16),int(s,16)) for p,x,b,s in (l.split() for l in open('runs/rp/plan_8.txt'))]
byp=collections.defaultdict(list)
for t in terms: byp[t[0]].append(t)
lm=sum(1<<(8*j) for j in range(5))
R=D[11].copy()
acc=np.zeros(1220,bool)
for p,ts in byp.items():
    s=ts[0][3]
    if s&1:
        (q,a1,b1,_)=ts[0]
        a2,b2=(ts[1][1],ts[1][2]) if len(ts)>1 else (0,0)
        f,g=rp.tt_from(a1,b2),rp.tt_from(a2,b1)
        acc^=f&g
        print(p,len(ts),format(s,'x'))
print('cross of D^acc',int(cross(D[11]^acc).sum()), 'cross acc', int(cross(acc).sum()))
c=cross(D[11]^acc); print(np.argwhere(c)[:10])
tr=np.zeros((77,16),bool); tr[Y,Z]=D[11]^acc
print('legal rows check', (c[1:,1:]).sum())
print('additive residual sample y=76', tr[76,:4].astype(int), tr[75,:4].astype(int))
