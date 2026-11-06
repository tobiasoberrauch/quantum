import sys, numpy as np, collections
sys.path.insert(0,'scripts')
import planner as P
d=np.load('base/submission.npz'); w=d['angle_words']; E=d['tree_edges']
N=76
# sign propagation: flipping theta_j by pi negates parent and child amplitude at step j.
# sign vector over nodes as linear function of g in F2^75: node n sign = sum_j g_j * affected(j,n)
# affected: node whose final amplitude descends from parent/child after step j
aff=np.zeros((75,76),dtype=bool)
for j in range(75):
    # simulate: start with flags at parent and child
    f=np.zeros(76,dtype=bool); p,c=E[j]; f[p]=True; f[c]=True
    for k in range(j+1,75):
        pp,cc=E[k]
        if f[pp]: f[cc]=True   # amplitude from parent flows to child
        # child initially zero so child sign follows parent
    aff[j]=f
# G: g with all node signs equal (0 or 1)
rows=[]
for n in range(1,76):
    v=0
    for j in range(75):
        if aff[j,n]^aff[j,0]: v|=1<<j
    rows.append(v)
ns=P.nullspace(rows,75)
print('dim G',len(ns))
print('tree order commuting? first edges',E[:6].tolist())
for i,g in enumerate(ns[:8]):
    print(i,'weight',bin(g).count('1'),[j for j in range(75) if (g>>j)&1][:30])
# observed gauge functions per column
A=np.arange(1220);Y=A>>4;Z=A&15
g=((w>>7)&1)^((w>>6)&1)
print('cols with nonzero g',int((g.any(axis=0)).sum()))
uniq=collections.Counter(g[:,j].tobytes() for j in range(75))
print('distinct column functions',len(uniq),[n for _,n in uniq.most_common(8)])
for k in (0,1,2,5,14):
    gb=g[:,5*k:5*k+5]
    print('batch',k,'g weights',gb.sum(axis=0).tolist(), 'as z-functions?',[bool(all(((gb[:,j]^gb[Z,j])==0))) for j in range(5)])
print('z fn example', [[int(g[z,5*5+j]) for z in range(16)] for j in range(2)])
# rows: which rows have nonzero
print('row g rank', len(P.rref_basis([int(''.join(map(str,g[:,j].astype(int))),2) for j in range(75)])))
