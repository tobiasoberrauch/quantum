#!/usr/bin/env python3
import bisect, importlib.util, sys
from collections import Counter
import numpy as np
ROOT='/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum'
spec=importlib.util.spec_from_file_location('wl',f'{ROOT}/work/dqi_sources/width_liveness.py'); wl=importlib.util.module_from_spec(spec); spec.loader.exec_module(wl)
r=wl.KmbReader('base.kmb')
tagpos=np.flatnonzero(np.frombuffer(r.types,dtype=np.uint8)==6)
stack=[];ev=[]
ops=[];names=[]
# build interval lists: for lookup record stack at each tag position
st=[]
for p,s in zip(tagpos.tolist(),r.tag_strings):
    if s.startswith('@enter:'): st=st+[s[7:]]
    elif s.startswith('@exit:'):
        n=s[6:]
        if n in st:
            i=len(st)-1-st[::-1].index(n); st=st[:i]
    ops.append(p); names.append('/'.join(st))
def tag(o):
    i=bisect.bisect_right(ops,o)-1
    return names[i] if i>=0 else ''
import pickle
pickle.dump((ops,names),open('out/tags.pkl','wb'))
rows=[l.rstrip('\n').split('\t') for l in open(sys.argv[1])]
C=Counter()
for x in rows:
    if x[8].endswith(',891') and x[8].count(',')==2: C[('B',tag(int(x[1])))]+=1
    elif x[8].count(',')==0 and x[8] and x[8]!='891': C[('A1',tag(int(x[1])))]+=1
    elif not x[8]: C[('zero',tag(int(x[1])))]+=1
    else: C[('other',tag(int(x[1])))]+=1
for k,v in sorted(C.items()): print(k,v)
