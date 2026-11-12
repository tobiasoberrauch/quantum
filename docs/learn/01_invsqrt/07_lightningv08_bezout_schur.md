# Bezout-Schur + 5-Word QROM

> **Lernziel:** Die **5-Word-QROM / Word-Table-Design**-Technik verstehen: freie Lookup-Qubits nutzen, um **fünf** Winkel gleichzeitig zu laden (`Q_ANGLE(J)=11+8J+72`), wodurch die Chemie-Familie von **19 auf 15 Circuits** schrumpft und die Gesamtkost trotz mehr Qubits sinkt — plus der **Bézout–Schur**-DQI-Splice als Kontext.
> **Dauer:** ~15 Minuten lesen
> **Quelle:** lightningv08 | Votes: – (im lokalen Kernel-Dump nicht enthalten)
> **Technik:** Word Table Design (5-Word QROM) + Bézout–Schur
> **Level:** Fortgeschritten

---

# Bezout-Schur + 5-Word QROM

**26 October 2026 · source-built chemistry · CPU reproduction**

**Use spare lookup qubits to load five angles at once.** The chemistry family shrinks from **19 circuits to 15**. Each circuit uses 123 qubits, below the 128-qubit cap. The complete chemistry cost falls from **432.325 million to 426.974 million: 1.24% lower**, with **identical factorization, angle words and physical errors**.

The portfolio combines mrmeows's 63-qubit inverse square root, Ahmed Berat Özer's new Bézout–Schur decoder, and his R4/B255/C128 factorization recompiled here at J=5. The decoder and factors are credited public components. The new contribution here is the wider lookup schedule, its kernel-relation budget, exact source rebuild and controlled full-cost comparison.

**Fixed-salt full-verifier projection: 19.599953.** The previous archive received **19.24359** on the public leaderboard. The observed score for this notebook is shown in Kaggle's Best Score badge; the fixed-salt projection is a separate measurement.

**Run All** reconstructs the chemistry circuits from source and saved algebraic plans, runs correctness checks and writes one `submission.zip`. No GPU or compilation search is needed for this path. The earlier C59 compression study remains in the notebook history and is discussed below.

## 1. Rebuild and verify

Attach the competition, [Ahmed's v8 components, version 1](https://www.kaggle.com/datasets/ahmedberatozer/vqcc-v8-components/versions/1), and [Alex Chilton's output, version 37](https://www.kaggle.com/code/alexchilton/toffolis-go-18-3-schur-dqi-at-883-qubits), which supplies the unchanged 63-qubit invsqrt binary. All input and generated-file hashes are checked.

The compiler uses saved seeds and low-monomial permutations to regenerate exact GF(2) decomposition certificates. It checks the tensor reconstruction and emits the gates with the credited CircuitBuilder compiler. Saved plans avoid repeating the offline search. Full receipts are reused only for identical bytes, reference/verifier/native fingerprints, runtime and development salt; chemistry and independent invsqrt/DQI probes are checked afresh. Set `FORCE_FULL = True` in the second code cell to repeat every full simulation.

```python
# Source-Build: lädt die gepinnten Inputs (PIN/PLANS/COMPILER_SOURCE), extrahiert
# die 63Q-Inverse aus Alex Chiltons Archiv, regeneriert die 15 J5-Chemie-Circuits
# aus den gespeicherten algebraischen Plänen und prüft alle 18 Mitglieder-Hashes.
import os
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
import gc,hashlib,json,lzma,math,shutil,sys,time,zipfile
from pathlib import Path
import numpy as np
INPUT=Path('/kaggle/input');WORK=Path('/kaggle/working')
COMP=next(p.parents[2] for p in INPUT.rglob('verify_submission_invsqrt.py'))
sys.path[:0]=[str(COMP/'kickmix'),str(COMP/'verifiers')]
import kickmix as km
from invsqrt import verify_submission_invsqrt as IV
from dqi import verify_submission_dqi as DV
from dfthcsos.verify import verify as verify_chemistry
FINAL=Path('/tmp/wide-qrom-selected');FINAL.mkdir(exist_ok=True)
(FINAL/'dfthcsos').mkdir(exist_ok=True)
WORKERS=min(4,os.cpu_count() or 1)
SALT='lightningv08-v13-fixed-20261026'
REFERENCE={'invsqrt':2076774.233715282,'dqi':24439473914136.668,'dfthcsos':3355599588.3155365}
PIN=json.loads(r'''{ … members: 18 SHA-256 (angle_k_*.kmb, submission.npz, dqi.kmb,
  invsqrt.kmb=9ac50386…); dqi_xz_sha256; invsqrt_source_archive … }''')
# PLANS: 15 Einträge, alle {T:297.0, Q:123, target:450, paired:225, relations:75,
#   rel_base:4, extra:15, seed:<0..7>, permutation:[15 low-monomial Indices]}
PLANS=json.loads(r'''[{"k":0,"T":297.0,"Q":123,"target":450,"paired":225,"relations":75,
  "rel_base":4,"extra":15,"seed":7,"permutation":[9,14,1,3,8,10,0,13,11,6,7,4,12,2,5]}, … ]''')
# COMPILER_SOURCE: eingebettete Compiler-Quellen (rank_parity.py, emit_j5.py,
#   hyper_native.py, borrowed_prefix.py, LICENSE, NOTICE) — Apache-2.0.
COMPILER_SOURCE=json.loads(r'''{ … }''')

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
DATA=next(p.parent for p in INPUT.rglob('dqi.kmb.xz') if (p.parent/'dfthcsos/submission.npz').is_file() and sha(p.parent/'dfthcsos/submission.npz')==PIN['members']['dfthcsos/submission.npz'])
assert sha(DATA/'dqi.kmb.xz')==PIN['dqi_xz_sha256']
with lzma.open(DATA/'dqi.kmb.xz') as source,(FINAL/'dqi.kmb').open('wb') as target:shutil.copyfileobj(source,target,8<<20)
assert sha(FINAL/'dqi.kmb')==PIN['members']['dqi.kmb']
ARCHIVE=next(p for p in INPUT.rglob('submission.zip') if sha(p)==PIN['invsqrt_source_archive'])
with zipfile.ZipFile(ARCHIVE) as z:
    with z.open('invsqrt.kmb') as source,(FINAL/'invsqrt.kmb').open('wb') as target:shutil.copyfileobj(source,target,8<<20)
assert sha(FINAL/'invsqrt.kmb')==PIN['members']['invsqrt.kmb']
shutil.copy2(DATA/'dfthcsos/submission.npz',FINAL/'dfthcsos/submission.npz')
SOURCE_DIR=WORK/'compiler_src';SOURCE_DIR.mkdir(exist_ok=True)
for name,text in COMPILER_SOURCE.items():(SOURCE_DIR/name).write_text(text)
(SOURCE_DIR/'plans.json').write_text(json.dumps(PLANS,indent=2))
sys.path.insert(0,str(SOURCE_DIR))
import emit_j5 as E
from hyper_native import build_hmr
words=np.asarray(np.load(FINAL/'dfthcsos/submission.npz',allow_pickle=False)['angle_words'],dtype=np.int64)
assert words.shape==(1096,75) and len(PLANS)==15
t0=time.monotonic();BUILD=[]
for plan in PLANS:
    k=plan['k'];delta=E.core.delta_batch(words,5,k)
    result,certificate=E.plan_general(delta,plan['rel_base'],plan['extra'],plan['seed'],plan['permutation'])
    assert result is not None,('Certificate regeneration failed',k)
    ac,terms=result
    circuit,_,resources=build_hmr(delta,8,4,ac,terms)
    assert circuit.num_qubits==123 and resources['toffoli_count']==297
    path=FINAL/f'dfthcsos/angle_k_{k}.kmb';circuit.to_file(path,format='kmb')
    assert sha(path)==PIN['members'][f'dfthcsos/angle_k_{k}.kmb'],('Compiled bytes differ',k,sha(path))
    BUILD.append({'k':k,'Toffolis':297,'Qubits':123,'paired products':certificate['paired'],'kernel relations':certificate['relations']})
    del circuit
MEMBERS={p.relative_to(FINAL).as_posix():sha(p) for p in sorted(FINAL.rglob('*')) if p.is_file()}
assert MEMBERS==PIN['members'] and len(MEMBERS)==18
def environment_fingerprint():
    files=[]
    for root in [COMP/'kickmix',COMP/'verifiers']:
        files.extend(p for p in root.rglob('*') if p.is_file() and p.suffix in {'.py','.so','.npz','.fcidump'})
    assert any(p.suffix=='.so' for p in files)
    return {p.relative_to(COMP).as_posix():sha(p) for p in sorted(set(files))}
ENVIRONMENT=environment_fingerprint()
RUNTIME={'python':sys.version.split()[0],'numpy':np.__version__,'kickmix':km.__version__}
REPORT_DIR=WORK/'reports';REPORT_DIR.mkdir(exist_ok=True)
def save_report(name,data):(REPORT_DIR/(name+'.json')).write_text(json.dumps(data,indent=2,default=str))
RESULTS={};PLAN={'invsqrt':'mrmeows 63Q, Alex Chilton v37 byte-pinned output','dqi':'Ahmed v8 Bezout-Schur splice, dataset v1','dfthcsos':'Ahmed v8 R4/B255/C128 factor, recompiled here at J5 from credited exact compiler'}
save_report('build',{'rows':BUILD,'seconds':time.monotonic()-t0,'members':MEMBERS})
print(f'15 exact J5 circuits rebuilt from source in {time.monotonic()-t0:.2f}s; all 18 member hashes PASS.',flush=True)
```

```python
# Verifikation + InvSqrt-Probe: entscheidet pro Task „cached receipt“ vs „fresh run“,
# führt dann einen unabhängigen InvSqrt-Prüflauf (64 Batches × 256 Shots) durch, der
# Phase gegen reference_values und Input-/Scratch-Restaurierung prüft.
import pandas as pd,matplotlib.pyplot as plt
from IPython.display import display,FileLink
FORCE_FULL=False
RECEIPT=json.loads(r'''{ … reports: invsqrt/dfthcsos/dqi (PASS, Scores, Shots),
  baseline_chemistry, members, environment, runtime, salt … }''')
CACHE_VALID=(RECEIPT['members']==MEMBERS and RECEIPT['environment']==ENVIRONMENT and RECEIPT['runtime']==RUNTIME and RECEIPT['salt']==SALT)
EXPECTED_SHOTS={'invsqrt':200540928,'dqi':102400,'dfthcsos':70144}
MODES={}
for task in ['dfthcsos','invsqrt','dqi']:
    cached=RECEIPT['reports'].get(task,{})
    if task!='dfthcsos' and CACHE_VALID and not FORCE_FULL and cached.get('status')=='PASS' and cached.get('verified_shots')==EXPECTED_SHOTS[task]:
        r=cached;MODES[task]='Exact-environment full receipt + fresh probes'
    else:
        start=time.monotonic();print('Fresh full official verification:',task,flush=True)
        if task=='dfthcsos':r=verify_chemistry(FINAL/'dfthcsos',salt=SALT)
        elif task=='invsqrt':
            c=km.Circuit.from_file(str(FINAL/'invsqrt.kmb'),format='kmb')
            r=IV.verify(c,IV.ProblemSpecInvSqrt.for_n_p(10),salt=SALT,max_workers=WORKERS);del c
        else:
            c=km.Circuit.from_file(str(FINAL/'dqi.kmb'),format='kmb')
            r=DV.verify(c,DV.ProblemSpecDQI.benchmark_instance(),salt=SALT,max_workers=1);del c
        r['wall_seconds']=time.monotonic()-start;MODES[task]='Fresh full official run'
    assert r['status']=='PASS' and r['verified_shots']==EXPECTED_SHOTS[task]
    RESULTS[task]=r;save_report('full_'+task,r);gc.collect()
# --- Unabhängiger InvSqrt-Probe (63Q): Phase gegen β/√x-Referenz prüfen ---
spec=IV.ProblemSpecInvSqrt.for_n_p(10)
c=km.Circuit.from_file(str(FINAL/'invsqrt.kmb'),format='kmb')
xreg,scratch=IV.validate_registers(c,spec)
rng=np.random.default_rng(20261026);sim=km.Simulator(batch_size=256,seed=20261026,debug_print=False)
for batch in range(64):
    values=rng.integers(1,spec.max_x+1,256,dtype=np.uint64)
    if batch==0:values[:7]=[1,2,3,4,32,spec.max_x-1,spec.max_x]
    sim.clear_for_shot();sim.write_across_shots(xreg,IV.to_bits(values,spec.width));sim.do(c)
    assert np.array_equal(IV.from_bits(sim.read_across_shots(xreg)),values)
    assert not sim.read_across_shots(scratch).any()
    phase=np.array([IV.half_turns_to_units(sim.read_shot_phase(i)) for i in range(256)],dtype=np.uint64)
    target,tol=IV.reference_values(spec,values)
    assert (np.abs((phase-target).view(np.int64)).view(np.uint64)<=tol).all()
del c,sim;gc.collect()
c=km.Circuit.from_file(str(FINAL/'dqi.kmb'),format='kmb')
fresh_dqi=DV.verify(c,DV.ProblemSpecDQI.benchmark_instance(num_shots=4096),salt=SALT+'-fresh',max_workers=1)
assert fresh_dqi['status']=='PASS';save_report('fresh_dqi',fresh_dqi);del c;gc.collect()
FULL_RECEIPT={**RECEIPT,'reports':RESULTS,'members':MEMBERS,'environment':ENVIRONMENT,'runtime':RUNTIME,'verification_modes':MODES}
(WORK/'full_verification.json').write_text(json.dumps(FULL_RECEIPT,indent=2))
display(pd.DataFrame([{'Task':k,'Status':v['status'],'Full shots':v['verified_shots'],'Evidence':MODES[k]} for k,v in RESULTS.items()]).style.hide(axis='index').format({'Full shots':'{:,.0f}'}))
plt.rcParams.update({'figure.dpi':140,'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold','text.color':'#16324b','axes.labelcolor':'#16324b','figure.facecolor':'white'})
COLORS={'invsqrt':'#27869c','dqi':'#7260a8','dfthcsos':'#be7d3c'}
```

## 2. Complete cost, not gate count alone

The competition combines the three reference-to-cost ratios geometrically:

$$S=\left(\prod_t C_{t,\mathrm{ref}}/C_t\right)^{1/3}.$$

The table uses full official verifier results. DQI includes its sampled failure penalty. The earlier C59 release used the same fixed salt, but the changed DQI circuit hash gives a different simulation seed; its cost comparison therefore includes sampling variation.

```python
# Vollständige Cost-Tabelle (aus den echten Verifier-Reports) + Portfolio-Projektion.
OLD={'invsqrt':108560.36455801228,'dqi':511874506651.3508,'dfthcsos':433601590.02861047}
table=pd.DataFrame([{'Task':k,'Qubits':r['num_qubits'],'Mean Toffolis':r['toffoli_count'],'Cost':r['score'],'Reference / cost':REFERENCE[k]/r['score'],'Full shots':r['verified_shots']} for k,r in RESULTS.items()])
projection=math.prod(REFERENCE[k]/RESULTS[k]['score'] for k in REFERENCE)**(1/3)
display(table.style.hide(axis='index').format({'Cost':'{:,.3f}','Mean Toffolis':'{:,.1f}','Reference / cost':'{:.3f}x','Full shots':'{:,.0f}'}))
fig,ax=plt.subplots(figsize=(8.5,3.8),layout='constrained');keys=['invsqrt','dqi','dfthcsos'];x=np.arange(3)
ax.bar(x-.18,[REFERENCE[k]/OLD[k] for k in keys],.35,color='#d7e0e8',label='Previous C59 portfolio')
bars=ax.bar(x+.18,[REFERENCE[k]/RESULTS[k]['score'] for k in keys],.35,color=[COLORS[k] for k in keys],label='Selected portfolio')
for b in bars:ax.text(b.get_x()+b.get_width()/2,b.get_height()+.5,f'{b.get_height():.2f}x',ha='center')
ax.set(xticks=x,xticklabels=['Inverse square root','Bezout-Schur DQI','Chemistry'],ylabel='Reference / measured cost',title='The selected portfolio: full verifier measurements');ax.legend(frameon=False);ax.grid(axis='y',alpha=.15)
fig.savefig(WORK/'portfolio_gains.png',bbox_inches='tight');plt.show();table.to_csv(WORK/'verified_costs.csv',index=False)
print(f'Fixed-salt portfolio projection: {projection:.6f}')
```

> **📊 Cost-Tabelle (aus `RESULTS`, volle Verifier-Reports):**
>
> | Task | Qubits | Mean Toffolis | Cost | Reference / cost | Full shots |
> |---|---:|---:|---:|---:|---:|
> | **invsqrt** (mrmeows 63Q) | **63** | 1,404.09 | **108,560.36** | **19.13×** | 200,540,928 |
> | dqi (Bézout–Schur) | 883 | 519,152 | 487,993,123,590.67 | 50.08× | 102,400 |
> | dfthcsos (J5) | 429 | 20,961 | 426,973,779.38 | 7.86× | 70,144 |
>
> Fixed-salt Portfolio-Projektion: **19.599953** (vorheriges C59-Archiv: **19.24359**).
> InvSqrt-Details: `max_toffoli_count 1490`, `rotation_count 44`, `worst_error_over_tolerance 0.99966`, `worst_x 60`.

## 3. The new idea: spend the free memory on a fifth word

After Ahmed's B=255 pruning, the lookup cache needs 72 temporary qubits. The address uses 11 qubits and each angle word uses 8 output qubits. In this cache layout,

$$Q_{\mathrm{ANGLE}}(J)=11+8J+72.$$

Thus J=4 needs 115 qubits, **J=5 fits at 123**, and J=6 would need 131 and violate the cap. Five also divides the 75 angle columns exactly: 15 batches cover every angle without a padded last word. This comparison concerns this cache layout, not a proof that every possible J=6 compiler is impossible.

Wider lookups make each circuit a little more expensive, while reducing the number of circuits. They also increase the persistent output register. The correct decision uses **the whole chemistry cost** $\lambda_{\mathrm{eff}}T_{\mathrm{total}}Q_{\mathrm{total}}$.

```python
# J4-Baseline vs J5-Vergleich: identische Physik (Errors/Lambda/E_gap), aber
# 19 vs 15 Circuits. Zeichnet „Same physics, cheaper compilation“ + Trade-off-Plot.
BASELINE=RECEIPT['baseline_chemistry'];new=RESULTS['dfthcsos']
for key in ['error_1','error_2','Lambda','E_gap','lambda_eff']:assert abs(new['metrics'][key]-BASELINE['metrics'][key])<1e-9
ab=pd.DataFrame([{'Schedule':'Public J4 baseline','Words / batch':4,'ANGLE circuits':19,'Peak ANGLE qubits':115,'Whole qubits':BASELINE['num_qubits'],'Whole Toffolis':BASELINE['toffoli_count'],'Cost':BASELINE['score']},
 {'Schedule':'Source-built J5','Words / batch':5,'ANGLE circuits':15,'Peak ANGLE qubits':123,'Whole qubits':new['num_qubits'],'Whole Toffolis':new['toffoli_count'],'Cost':new['score']}])
display(ab.style.hide(axis='index').format({'Cost':'{:,.3f}','Whole Toffolis':'{:,.0f}'}))
q=new['num_qubits']/BASELINE['num_qubits'];t=new['toffoli_count']/BASELINE['toffoli_count'];ratio=new['score']/BASELINE['score']
fig,(ax,bx)=plt.subplots(1,2,figsize=(10.1,3.7),layout='constrained')
ax.bar(['J4 baseline','J5 wider lookup'],ab['Cost']/1e6,color=['#aebdca','#27869c']);ax.set(ylabel='Whole chemistry cost (millions)',title='Same physics, cheaper compilation');ax.set_ylim(0,470)
for i,v in enumerate(ab['Cost']/1e6):ax.text(i,v+4,f'{v:.3f}',ha='center')
grid=np.linspace(.98,1.05,200);bx.plot(grid,1/grid,color='#586474',label='Equal cost at fixed normalization');bx.fill_between(grid,.93,1/grid,alpha=.08,color='#27869c');bx.scatter([q],[t],s=80,color='#27869c',zorder=4)
bx.annotate(f'+{100*(q-1):.2f}% qubits\n{100*(t-1):.2f}% Toffolis',(q,t),xytext=(.985,.945),arrowprops={'arrowstyle':'->','color':'#586474'})
bx.set(xlabel='Whole qubit ratio: J5 / J4',ylabel='Whole Toffoli ratio: J5 / J4',title='More qubits can still lower cost',ylim=(.93,1.025));bx.legend(frameon=False,fontsize=9);bx.grid(alpha=.15)
fig.savefig(WORK/'qrom_cost_tradeoff.png',bbox_inches='tight');plt.show();ab.to_csv(WORK/'qrom_comparison.csv',index=False)
print(f'Cost ratio Q*T: {q:.6f} * {t:.6f} = {ratio:.6f}; chemistry reduction {100*(1-ratio):.4f}%')
print(f'Isolated portfolio gain: {100*(ratio**(-1/3)-1):.4f}%')
display(pd.DataFrame([{'J':4,'ANGLE qubits':115,'Fits 128':True},{'J':5,'ANGLE qubits':123,'Fits 128':True},{'J':6,'ANGLE qubits':131,'Fits 128':False}]).style.hide(axis='index'))
```

### Why the algebraic relation budget changes

The lookup emitter uses exact paired products over GF(2). One redundant sign bit leaves 7 independent Boolean functions per angle word. With 15 nonconstant low-address monomials, J4 has $15\cdot28=420$ mixed coordinates. Its 60 selected kernel relations leave 360 coordinates, represented by 180 paired products. The cache adds 72 Toffolis, giving **252 per circuit**.

J5 has $15\cdot35=525$ mixed coordinates. Retuning to **five relations per three-vertex block**, 75 independent relations overall, leaves 450 coordinates: **225 paired products + 72 cache Toffolis = 297 per circuit**. The exact tensor reconstruction is checked before emission.

Although 297 is larger than 252, $15\cdot297=4455$ is smaller than $19\cdot252=4788$. Counting forward and inverse ANGLE passes saves **666 Toffolis** in the complete block. Extra persistent output storage costs eight whole-system qubits. Both effects are included above. The factorization, integer words, normalization and Hamiltonian errors remain unchanged.

> **🔥 Kern-Rechnung (Word-Table-Design):**
> - J4: 19 Circuits × 252 Toffolis = **4,788**
> - J5: 15 Circuits × 297 Toffolis = **4,455** → spart **666 Toffolis** (vor+zurück ANGLE-Pässe)
> - Pro Circuit teurer (297 > 252), aber weniger Circuits (15 < 19) → Gesamtkost sinkt.
> - Qubit-Budget: `Q_ANGLE(J)=11+8J+72` → J=5 bei **123** (unter 128-Cap), J=6 würde 131 brauchen.

## 4. DQI: the public Bézout-Schur splice

Ahmed's v8 replaces the Schur amplitude-conversion middle block and its inverse with mrmeows's round17 central Bézout transform. Coefficient reversal, word swaps and CNOT basis changes adapt the representations without Toffolis. The classical mask projection also skips 70 scan points. The full decoder remains at 883 qubits and falls from roughly 536,798 to 519,152 mean Toffolis.

The supplied binary is reused unchanged and credited below. Rare failures still affect the repetition penalty. This curve is a **sensitivity scenario** using the official confidence-bound functions, not a leaderboard confidence interval. No salt is chosen from its result.

```python
# DQI-Fehler-Sensitivität: für 0..20 hypothetische Fehl-Shots rechnet Clopper-Pearson-
# Obergrenze + Repetition-Overhead und zeigt den Portfolio-Score. Beobachteter Punkt
# (3 value errors) wird markiert.
d=RESULTS['dqi']
failures=np.arange(0,21)
scenario=[]
for count in failures:
    eps=DV.clopper_pearson_upper_bound(int(count),102400,log2_delta=-128)
    rep=DV.repetition_overhead(eps)
    cost=rep*d['num_qubits']**2*d['toffoli_count']
    score=(REFERENCE['dqi']/cost*REFERENCE['invsqrt']/RESULTS['invsqrt']['score']*REFERENCE['dfthcsos']/RESULTS['dfthcsos']['score'])**(1/3)
    scenario.append({'Failed shots':int(count),'Error upper bound':eps,'Repetition':rep,'Portfolio projection':score})
risk=pd.DataFrame(scenario)
observed=int(d['value_errors']+d['phase_errors'])
fig,ax=plt.subplots(figsize=(8.1,3.5),layout='constrained')
ax.plot(risk['Failed shots'],risk['Portfolio projection'],color='#217f9c',lw=2,marker='o',markersize=3)
if observed<=20:
    rr=risk.iloc[observed];ax.scatter([observed],[rr['Portfolio projection']],s=70,color='#bb7831',zorder=4,label=f'Full-check observation: {observed} failures');ax.legend(frameon=False)
ax.set(xlabel='Hypothetical failed shots out of 102,400',ylabel='Projected portfolio score',title='DQI failure sensitivity · all other costs held fixed')
ax.grid(alpha=.15);fig.savefig(WORK/'dqi_failure_sensitivity.png',bbox_inches='tight');plt.show()
display(risk.iloc[[0,1,2,5,10,20]].style.hide(axis='index').format({'Error upper bound':'{:.6f}','Repetition':'{:.5f}','Portfolio projection':'{:.6f}'}))
risk.to_csv(WORK/'dqi_failure_scenarios.csv',index=False)
```

## 5. What the other experiments taught us

The previous release developed offset-preserving ensemble coalescence, followed by a protected GPU refit. Its R10/C59 chemistry passed full verification and cost 433.602 million, 0.447% below its public C60 baseline. That archive received **19.24359** on the leaderboard. [Version 13 contains the derivation and research recipe](https://www.kaggle.com/code/lightningv08/schur-dqi-c59-circuit-cost-lab?scriptVersionId=362605535).

Applying the same merge to the new R4/C128 factorization, then refitting to C127, passed native physical accuracy but raised effective normalization to about 48.489. It lost on complete cost and is excluded. An earlier ordinary physical SVD also lost because its column orientation inflated the L1 normalization. These checks are useful: fewer factors or fewer qubits alone do not establish an improvement.

The selected update keeps Ahmed's newer coefficients unchanged and improves their exact lookup compilation. The fixed development salt is retained from the earlier release. Compiler search used exact algebra and native correctness checks; it did not select a favourable sampled DQI outcome.

## 6. Package the verified files

The official metric reader checks the archive contract. Every archived member is rehashed after compression and the ZIP CRC is checked. Outputs include full reports, exact compiler sources, search plans and the controlled comparison. Run All never submits automatically.

> *(Zelle 13 `metric_preflight.py` ist der offizielle Kaggle-Metric-v10-Reader, eingebettet als String — prüft nur den Datei-Contract (erlaubte Instruktionen, Register-Limits, NPZ-Größe), keine Task-Verifikation. Boilerplate; vollständig in der Quelle.)*

```python
# Contract-Check + deterministisches Packaging: preflight_directory(FINAL) muss PASS
# sein, 15 ANGLE-Circuits mit max 123 Qubits; schreibt submission.zip (18 Mitglieder,
# fixe Timestamps), release_manifest.json, LICENSE, NOTICE.
from metric_preflight import preflight_directory
contract=preflight_directory(FINAL)
assert contract['status']=='PASS' and set(contract['archive_members'])==set(MEMBERS)
assert len(contract['angle_qubits'])==15 and max(contract['angle_qubits'])==123
archive=WORK/'submission.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for name in sorted(MEMBERS):
        info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.create_system=3
        info.external_attr=0o600<<16;info.compress_type=zipfile.ZIP_DEFLATED
        with z.open(info,'w') as target,(FINAL/name).open('rb') as source:shutil.copyfileobj(source,target,8<<20)
with zipfile.ZipFile(archive) as z:
    assert len(z.namelist())==len(set(z.namelist()))==18 and z.testzip() is None
    assert {n:hashlib.file_digest(z.open(n),'sha256').hexdigest() for n in z.namelist()}==MEMBERS
manifest={'members':MEMBERS,'archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size,'contract':contract,
 'projection':projection,'full_environment_match':CACHE_VALID,'verification_modes':MODES,'fixed_development_salt':SALT,
 'previous_observed_score':19.24359,'current_version_observed_score':None,'build':BUILD}
(WORK/'release_manifest.json').write_text(json.dumps(manifest,indent=2))
table.to_csv(WORK/'verified_costs.csv',index=False)
(WORK/'LICENSE').write_text(COMPILER_SOURCE['LICENSE'])
(WORK/'NOTICE').write_text(COMPILER_SOURCE['NOTICE']+'\n'+(DATA/'DQI_NOTICE.md').read_text())
print(f'submission.zip: {archive.stat().st_size/2**20:.2f} MiB | 18 verified members')
print('SHA-256:',manifest['archive_sha256']);print(f'Fixed-salt full-check projection: {projection:.6f}')
display(FileLink(str(archive)))
```

## Sources and credit

- [Ahmed Berat Özer — DF-THC Group Compression, v8](https://www.kaggle.com/code/ahmedberatozer/quantum-ai-df-thc-group-compression), [v8 components](https://www.kaggle.com/datasets/ahmedberatozer/vqcc-v8-components): the Bézout–Schur splice, R4/B255/C128 factorization, pruning/quantization/offset optimization, and generalized kernel-relation compiler. The DQI binary and factorization are unchanged here.
- [mrmeows — open circuits and research notes](https://www.kaggle.com/code/mrmeows/15-75-circuits-let-s-all-reach-the-plateau): the 63-qubit inverse square root, round17 Bézout transform, paired-product lookup algebra, kernel tools, native checker and HMR emitter. Compiler sources are Apache 2.0.
- [Alex Chilton — Schur at 883 qubits](https://www.kaggle.com/code/alexchilton/toffolis-go-18-3-schur-dqi-at-883-qubits): the narrower reverse synthesis and the pinned invsqrt source output. The continued-fraction Schur design originates with **jday96314**. The DQI source notice is preserved verbatim; its upstream repository does not state a source-code licence.
- Earlier foundations credited upstream include Dmitrii Gluzdov, SomeJoint / Agniv Banerjee, manwithacat, Phuc Thai, Kozykorpesh, Artem1410, Rudra Bhaskar, Marsyas, Sumit Chongder, marculera, Michael Rustad and other contributors named in the source headers and DQI notice.
- [Google Quantum AI competition data and verifiers](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/data) define the register contracts, accuracy constraints and cost; they are unchanged.

New here: use the freed lookup workspace for five words, retune the relation budget, regenerate the exact certificates and compare full costs under unchanged physics. Earlier C59 experiments remain available in history. The compiler sources, plans, licence and attribution notices are exported with the result.

---

## 🔑 Kern-Technik in 3 Sätzen

Die **5-Word-QROM**-Idee nutzt freie Lookup-Qubits, um fünf statt vier Winkel pro Batch zu laden: mit `Q_ANGLE(J)=11+8J+72` passt J=5 bei **123 Qubits** (unter dem 128-Cap) und deckt die 75 Winkel-Spalten exakt mit 15 Batches ab. Zwar kostet jeder Circuit mehr (297 statt 252 Toffolis), aber es gibt weniger Circuits (15 statt 19), sodass $15·297=4455 < 19·252=4788$ — **666 Toffolis gesamt gespart**, bei identischer Physik. Das InvSqrt-Binary (mrmeows 63Q, Cost `108,560.36`, Ratio `19.13×`) wird hier nur byte-gepinnt übernommen und per 64×256-Shot-Probe gegen `β/√x`-Referenzwerte unabhängig geprüft.

## 📝 Lern-Notizen (füll das selbst aus)

- [ ] Technik verstanden: 5-Word-QROM (J=5, 123 Qubits) + Relation-Budget (225 Paired Products + 72 Cache)
- [ ] Cost-Delta nachvollziehbar: Chemie 432.325M → 426.974M (−1.24 %); 15×297 < 19×252 (−666 Toffolis)
- [ ] Könnte ich das selbst bauen?: teilweise/weil… (Qubit-Budget-Rechnung klar; GF(2)-Zertifikate + Compiler brauchen die gespeicherten Pläne)
- [ ] Verbindung zu anderen Notebooks: „Word Table Design“ ist dieselbe Technik wie die 5-Winkel-Loader in 03/04/05; Bézout–Schur = DQI-Kontext
- [ ] Frage die ich noch habe: Warum teilt 5 die 75 Spalten exakt auf, und was wäre bei 75/6=12.5 (Padding nötig)?
