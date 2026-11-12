# The dataset is public now. Enjoy!⭐⭐⭐

> **Lernziel:** Du verstehst, wie eine vollständige, verifizierte Submission aus einem öffentlichen Release-Dataset gebaut wird: SHA-256-Prüfung aller Dateien, Aufruf der drei offiziellen Verifier mit dem Release-Salt, und Packaging der `submission.zip`.
> **Dauer:** ~12 Minuten lesen
> **Quelle:** heliosli | https://www.kaggle.com/code/heliosli/the-dataset-is-public-now-enjoy | 78 votes
> **Wichtigste Konzepte:**
> - Release-Portfolio `v100at1_mx4_ay3`: 18 Dateien mit SHA-256-Prüfsummen in `QCC_RELEASE_MANIFEST.json`
> - Drei offizielle Verifier (invsqrt, dqi, dfthcsos) werden unmodifiziert mit dem Manifest-Salt ausgeführt
> - Ratios: invsqrt 21.7815, DQI 65.2262, dfthcsos 11.198 → geometrisches Mittel ≈ 25.14
> - LZMA-Streaming für die große DQI-Datei (`.xz`)
> - Vollständige Quellen-Nachverfolgung (Credits) für jede Circuit-Komponente

---

For each task this notebook takes the cheapest circuit we know of, re-verifies every file here with the
unmodified official verifiers, and writes `/kaggle/working/submission.zip`.

| Task | Circuit | Ratio |
|---|---|---:|
| invsqrt | maoxin123's version-1 edit of the 62-qubit file 13b5bf7a (with Hosen42's q25 merge) | 21.7815 |
| DQI | atakanaldemir's version-1 892-qubit file (on ozertuu's version-70 readout) | 65.2262 |
| dfthcsos | syed3000's own (8, 143, 44) table and version-9 angle circuits, table weights: our refit of maoxin123's version-1 table | 11.198 |

## Re-verify every component here

Each file is copied from the release dataset and matched to its SHA-256; then the three official verifiers from the competition data run on it, unmodified, at their default shot counts.

Findet die Competition-Daten und das Release-Dataset, konfiguriert sys.path und lädt kickmix + Verifier.

```python
import glob, hashlib, json, lzma, math, os, shutil, sys, time, zipfile, pathlib

def find_comp():
    for p in [os.environ.get('QCC_COMP_DIR', ''), '/kaggle/input/competitions/google-verifiable-quantum-circuit-compilation',
              '/kaggle/input/google-verifiable-quantum-circuit-compilation']:
        if p and os.path.isdir(os.path.join(p, 'verifiers')):
            return p
    raise SystemExit('competition data not found')

def find_release():
    if os.environ.get('QCC_DS_DIR'):
        return os.environ['QCC_DS_DIR']
    hits = glob.glob('/kaggle/input/**/QCC_RELEASE_MANIFEST.json', recursive=True)
    if not hits:
        raise SystemExit('release dataset not found')
    return os.path.dirname(hits[0])

COMP, DS = find_comp(), find_release()
WORK = pathlib.Path(os.environ.get('QCC_WORK_DIR', '/kaggle/working'))
SUB = WORK / 'submission'
sys.path[:0] = [os.path.join(COMP, 'kickmix'), os.path.join(COMP, 'verifiers')]
import kickmix as km
from invsqrt import verify_submission_invsqrt as vinv
from dqi import verify_submission_dqi as vdqi
from dfthcsos import verify as vdft
MANIFEST = json.load(open(os.path.join(DS, 'QCC_RELEASE_MANIFEST.json')))
EXPECTED_PORTFOLIO = 'v100at1_mx4_ay3'
assert MANIFEST['portfolio'] == EXPECTED_PORTFOLIO, ('stale dataset version', MANIFEST['portfolio'], EXPECTED_PORTFOLIO)
SALT = MANIFEST['salt']
print('competition data:', COMP, '| release dataset:', DS, '| salt:', SALT)
```

Kopiert alle 18 Dateien aus dem Release-Dataset, prüft SHA-256, entpackt `.xz`-Dateien per LZMA-Streaming.

```python
def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 22), b''):
            h.update(chunk)
    return h.hexdigest()

if SUB.exists():
    shutil.rmtree(SUB)
for item in MANIFEST['files']:
    src, dst = os.path.join(DS, item['stored_as']), SUB / item['file']
    dst.parent.mkdir(parents=True, exist_ok=True)
    if item['stored_as'].endswith('.xz'):
        with lzma.open(src) as fi, open(dst, 'wb') as fo:
            shutil.copyfileobj(fi, fo, 1 << 22)
    else:
        shutil.copyfile(src, dst)
    got = sha256(dst)
    assert got == item['sha256'], (item['file'], got)
    print('sha256', item['file'], got)
print(len(MANIFEST['files']), 'files copied and matched to the manifest by SHA-256')
```

Führt die drei offiziellen Verifier unmodifiziert aus und berechnet das geometrische Mittel der Ratios.

```python
REF = MANIFEST['reference_costs']
results = {}
t0 = time.time()
circ = km.Circuit.from_file(str(SUB / 'invsqrt.kmb'), format='kmb')
results['invsqrt'] = vinv.verify(circ, vinv.ProblemSpecInvSqrt.for_n_p(10), salt=SALT)
print('invsqrt done', round(time.time() - t0), 's'); t0 = time.time()
circ = km.Circuit.from_file(str(SUB / 'dqi.kmb'), format='kmb')
results['dqi'] = vdqi.verify(circ, vdqi.ProblemSpecDQI.benchmark_instance(), salt=SALT)
del circ
print('dqi done', round(time.time() - t0), 's'); t0 = time.time()
results['dfthcsos'] = vdft.verify(str(SUB / 'dfthcsos'), salt=SALT)
print('dfthcsos done', round(time.time() - t0), 's')
rows, ratios = [], []
for task in ('invsqrt', 'dqi', 'dfthcsos'):
    r = results[task]
    assert r['status'] == 'PASS', (task, r)
    ratio = REF[task] / float(r['score'])
    ratios.append(ratio)
    if task == 'invsqrt':
        extra = f"{r['num_qubits']} qubits, {r['toffoli_equivalent']:.1f} Toffoli-equivalents"
    elif task == 'dqi':
        extra = (f"{r['num_qubits']} qubits, {r['toffoli_count']:.0f} mean Toffolis, "
                 f"{r.get('value_errors', 0)} value / {r.get('phase_errors', 0)} phase errors")
    else:
        extra = f"lambda_eff {r['lambda_eff']:.3f}, {r['toffoli_count']:.0f} Toffolis, {r['num_qubits']} qubits"
    rows.append((task, float(r['score']), ratio, extra))
    print(f"{task:9s} PASS cost {float(r['score']):.6g}  ratio {ratio:8.4f}  ({extra})")
gm = math.prod(ratios) ** (1 / 3)
print(f'geometric mean of reference / cost: {gm:.4f}')
```

## Write the submission

Packt alle verifizierten Dateien in `submission.zip`.

```python
zip_path = WORK / 'submission.zip'
with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    for item in MANIFEST['files']:
        z.write(SUB / item['file'], item['file'])
shutil.rmtree(SUB)
print('wrote', zip_path, round(zip_path.stat().st_size / 2**20, 1), 'MiB')
```

# Sources and credits

- **invsqrt** — the 62-qubit file 034c7c2a shipped in maoxin123's notebook https://www.kaggle.com/code/maoxin123/lb-25-1498-combined-invsqrt-refit-chem (version 1; their code
  Apache-2.0, each circuit keeps its authors' terms), byte for byte: their edits (made with ChatGPT's help, as
  credited there) with Hosen42's version-6 q25 merge (https://www.kaggle.com/code/hosen42/vqcc-our-submission), on the file 13b5bf7a shipped in ozertuu's notebook
  https://www.kaggle.com/code/ozertuu/25-137-starter-notebook (version 15), which combines Atakan Aldemir's (atakanaldemir) edit from https://www.kaggle.com/code/atakanaldemir/qcc-early-measurement-and-domain-aware-inverse (version 2) with the file
  29505732 shipped in kirilltym's (Kirill Tymchishin) notebook https://www.kaggle.com/code/kirilltym/quantum-circuits-pi-gauge-weight-refinement (version 22), on the public invsqrt lineage
  (Hosen42's measure-first rewrites, syed3000 (Syed Asad Ali), mrmeows (team selenium), busyaprime (Akmal Xodarev),
  yoyobar), as credited there.

- **dqi** — the 892-qubit file e9f54be3 shipped in atakanaldemir's (Atakan Aldemir) notebook https://www.kaggle.com/code/atakanaldemir/qcc-terminal-readout-and-phase-folds (version 1),
  byte for byte: their seven phase folds and same-slot outcome schedule on the 48 controlled-swap readout
  replacements published in ozertuu's notebook https://www.kaggle.com/code/ozertuu/25-137-starter-notebook (version 70; the identity documented in kirilltym's notebook
  https://www.kaggle.com/code/kirilltym/quantum-circuits-conditional-uncompute-audit, version 5), whose file 4e9b50b1 is loaded there from isabe11am00re's public dataset https://www.kaggle.com/datasets/isabe11am00re/qcc-v84337cb049akt21-circuits; that file is a
  further update of the decoder 337cb049 shipped in kirilltym's (Kirill Tymchishin) notebook
  https://www.kaggle.com/code/kirilltym/quantum-circuits-pi-gauge-weight-refinement (version 21; their code Apache-2.0, upstream artefacts keep their terms), which is their composition on
  the decoder 77bace9d shipped in ozertuu's notebook https://www.kaggle.com/code/ozertuu/25-137-starter-notebook (version 5), from
  Ahmed Berat Özer's (ahmedberatozer) dataset https://www.kaggle.com/datasets/ahmedberatozer/vqcc-v23-portfolio (its terms retained there), credited there to Atakan Aldemir
  and daifanhao (MAIDANG), on syed3000's (Syed Asad Ali) decoder line (daifanhao: https://www.kaggle.com/code/daifanhao/lb-24-94096-c44-and-exact-dqi-product-reuse; syed3000: https://www.kaggle.com/code/syed3000/vqcc-own-circuit-portfolio-notebook,
  Apache-2.0; Atakan Aldemir's scanner and emitter: https://www.kaggle.com/datasets/atakanaldemir/qcc-c44-five-helper-release-sources/versions/1, Apache-2.0, which credit Busya PRIME's retained-product
  idea and Gidney's measurement-based uncomputation). kirilltym's notebook (its own code Apache-2.0) also credits
  SomeJoint (Agniv Banerjee), Ali Haydar Özdağ (ahoirg) and James Day (jday96314) on this lineage. syed3000's decoder
  builds on their own decoder line (made with GPT-6 Astra on SomeJoint's kit, as credited there) with ports of
  SomeJoint's 892-qubit work and of Ali Haydar Özdağ's idea, and cites Khattar & Gidney (2024). SomeJoint's notebook
  credits GPT-6 Astra Pro, Claude, Ali Haydar Özdağ (ahoirg), yoyobar and the earlier decoder line (Alex Chilton,
  jday96314 (QuantumAI), mrmeows, manwithacat, Dmitrii Gluzdov, ViberTeam, Phuc Thai (DePie)).

- **dfthcsos** — syed3000's (Syed Asad Ali) own (8, 143, 44) DF-THC table, its angle words and 15 angle circuits,
  byte for byte, from https://www.kaggle.com/code/syed3000/vqcc-own-circuit-portfolio-notebook (table version 4, angle circuits version 9; Apache-2.0), made there with their
  loader compiler and lattice-aware
  rounding on Lera's (marculera) DF-THC pipeline (https://www.kaggle.com/code/marculera/df-thc-10x-compact-groups-from-the-hamiltonian,
  Apache-2.0) and Ahmed Berat Özer's progressive rounding, as credited there; refitting the weights up to the error gate
  was first shown publicly by heliosli.
  The table weights (W, H2_I) in this version are our refit of maoxin123's version-1 weights d994cd72 from
  https://www.kaggle.com/code/maoxin123/lb-25-1498-combined-invsqrt-refit-chem (version 1; Apache-2.0), on the lineage credited there.
  Lera's sources, as credited there: Ahmed Berat Özer (ahmedberatozer), somejoint, mrmeows, heliosli, lightningv08,
  kozykappa, Kozykorpesh and Sumit Chongder, Artem1410 (anazemcev), haideptry via phucthaiv02, Michael Rustad, k256net
  and Dmitrii Gluzdov, and the hosts.

  Lera's NOTICE (Apache-2.0), as carried in ayodejiibrahimlateef's archive:

  > DF-THC compact groups pipeline
  > Copyright 2026 marculera (Kaggle)
  > 
  > Licensed under the Apache License, Version 2.0 (see LICENSE). The weights, seeds and tables in this dataset were
  > trained here and derive from the competition's FeMoCo Hamiltonian; the arrays H1_I and Hsym_lower in them are the
  > hosts' fixed shifts, as published in the starter kit (sohier/verifiable-circuit-compilation-starter-kit).
  > 
  > Parts of the pipeline in dfthc_refit/ adapt or reimplement public work. Each module's docstring names its source:
  > 
  > - refine.py: adapted from chemistry_refine.py of ahmedberatozer/quantum-ai-df-thc-group-compression (notebook
  >   code, Apache-2.0), which credits kozykappa's sparse column rotations and anazemcev's effective-norm method.
  > - quantize.py, experiments/quantize_rm.py: ahmedberatozer's staged progressive rounding and the fine start of its
  >   schedule (vqcc-v8-components); michaelrustad's L-BFGS stages (hybrid quantization). Own code.
  > - experiments/rmcode.py: somejoint's coded low bit (qcc-our-chemistry-b143-c60-xor2, Apache-2.0). Own code.
  > - tensorqrom.py: mrmeows' exact lookup emitter design (qcc-1375-open-circuits, Apache-2.0), heliosli's scratch bit,
  >   somejoint's codes. Own code.
  > - fourqrom.py: ANF loading and erasure as in the public banked-QROM code (banked_lab.py in ahmedberatozer's
  >   group-compression notebook, after Kozykorpesh and Sumit Chongder). Own construction.
  > - onebody.py: the role of mrmeows' refresh_one_body8.py; own code. polish_words.py: phucthaiv02's exact word-level
  >   coordinate descent after rounding; own version.
  > - refit_weights.py: phucthaiv02's joint (w, W) refit at fixed words (qcc-verified-portfolio-df-thc-retraining-study,
  >   Apache-2.0); our own implementation. experiments/refit_al.py puts it in augmented-Lagrangian form.
  > 
  > No file in this dataset is copied from a dataset under other terms. Tables derived from ahmedberatozer's
  > factorization datasets (license "other") are not included; the notebook records their measured values instead.

- **Organizers** — task definitions, verifiers and kickmix (Google Quantum AI / Qualtran, competition data).

---

## 📝 Lern-Notizen (füll das selbst aus)

- [ ] Konzept 1 verstanden: Release-Portfolio — ein JSON-Manifest (`QCC_RELEASE_MANIFEST.json`) listet alle 18 Dateien mit SHA-256 und Byte-Länge; der Code prüft jede Datei gegen das Manifest
- [ ] Konzept 2 verstanden: Verifizierung mit Salt — der Salt aus dem Manifest wird an alle drei Verifier übergeben; das Ergebnis ist reproduzierbar, aber nicht offline vorhersagbar
- [ ] Konzept 3 verstanden: Ratios — invsqrt 21.78×, DQI 65.23×, dfthcsos 11.20× → geo. Mittel ≈ 25.14; DQI ist der stärkste Hebel
- [ ] Konzept 4 verstanden: Credits-Nachverfolgung — jede Circuit-Komponente ist byte-für-byte einer bestimmten Source zugeordnet; das ist wichtig für Lizenzkonformität und Reproduzierbarkeit
- [ ] Eigener Test: Was passiert, wenn ich eine Datei aus dem Manifest ändere? → SHA-256-Mismatch → AssertionError → Notebook bricht ab
- [ ] Frage die ich noch habe: Warum ist der DQI-Ratio (65×) so viel höher als der dfthcsos-Ratio (11×)? Ist das an der Q²-Penalty in der DQI-Kostenfunktion?
