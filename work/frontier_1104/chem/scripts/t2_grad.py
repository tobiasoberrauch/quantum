import sys, numpy as np
sys.path.insert(0, '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/work/frontier_1104/chem/scripts')
import wcore, refit
base = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/work/frontier_1104/chem/base/submission.npz'
eng, w, wB = wcore.load_engine(base)
al = refit.AL(eng, 0.0199999, 0.0199999, 3.9148982); al.rho=0.05; al.y2=0.002;al.y1=0.001;al.yg=0.01
R,B,C=w.shape;n=R*B*C
w = w + 1e-5*np.sign(w+1e-12)
x=np.concatenate([w.ravel(),wB.ravel()])
sg=(np.sign(w),np.sign(wB))
v,g=al.fg(x,sg)
rng=np.random.default_rng(1);d=rng.normal(size=x.shape)*1e-8
d[:n]=d[:n]; vp,_=al.fg(x+d,sg);vm,_=al.fg(x-d,sg)
print('fd',(vp-vm)/2,'an',g@d)
# isolate
p=refit.smooth_parts(eng,w,wB)
for key,(gw,gB),f in [('Lam',(p['gLw'],p['gLB']),'Lam'),('Eg',(p['gEw'],p['gEB']),'Eg'),('e1s',(p['g1w'],p['g1B']),'e1s')]:
    dw=rng.normal(size=w.shape)*1e-8; dB=rng.normal(size=wB.shape)*1e-8
    a=refit.smooth_parts(eng,w+dw,wB+dB,False)[f]; b=refit.smooth_parts(eng,w-dw,wB-dB,False)[f]
    print(key,'fd',(a-b)/2,'an',np.sum(gw*dw)+np.sum(gB*dB))
