#!/usr/bin/env python3
"""Official DQI verifier, default shots (102,400). Usage: verify_official.py <kmb> <out.json> [salt]"""
import json, sys, time
ROOT='/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum'
sys.path.insert(0, ROOT+'/data/verifiers')
import kickmix as km
from dqi import verify_submission_dqi as v
path,out=sys.argv[1],sys.argv[2]; salt=sys.argv[3] if len(sys.argv)>3 else 'notebook-verification'
t=time.time()
c=km.Circuit.from_file(path,format='kmb')
try:
    r=v.verify(c,v.ProblemSpecDQI.benchmark_instance(),salt=salt,max_workers=4)
except AssertionError as e:
    r={'status':'FAIL','error':str(e)}
keep={k:x for k,x in r.items() if isinstance(x,(int,float,str,bool,type(None)))}
keep['seconds']=time.time()-t; keep['salt']=salt
if r.get('status')=='PASS': keep['ratio']=24439463583672.93/float(r['score'])
json.dump(keep,open(out,'w'),indent=1)
print({k:keep.get(k) for k in ('status','ratio','score','num_qubits','toffoli_count','max_toffoli_count','value_errors','phase_errors','repetition_factor','circuit_sha256','seconds','error')})
