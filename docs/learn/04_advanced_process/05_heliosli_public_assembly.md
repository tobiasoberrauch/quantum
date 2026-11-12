# The dataset is public now. Enjoy! – der Best-of-Public Assembler

> **Lernziel:** Die *reduzierte* Form des Portfolio-Musters: nimm für jede Task den günstigsten bekannten Circuit, re-verifiziere jede Datei mit den unveränderten offiziellen Verifiern, und schreibe `submission.zip`. Kein eigener Circuit, keine Heuristik – nur Auswahl + Verifikation + eine lückenlose Credits-Kette. Das ist das minimal-vollständige "Assembly"-Notebook, auf dem alle anderen aufbauen.
> **Dauer:** ~8 Minuten
> **Quelle:** Heliosli | 125 votes
> **Fokus:** Portfolio assembly / Verification culture / Credit chain

---

> **Hinweis:** Der Originaltext des Notebooks (Markdown **und** Code-Zellen) steht unten **auf Englisch, unverändert** ("as-is"). Deutsche Anmerkungen sind als 📌-Callouts dazwischen gesetzt. Reine Daten-Zellen (große Lookup-Tabellen) sind als kurzes, klar markiertes Exzerpt wiedergegeben.

For each task this notebook takes the cheapest circuit we know of, re-verifies every file here with the
unmodified official verifiers, and writes `/kaggle/working/submission.zip`.

| Task | Circuit | Ratio |
|---|---|---:|
| invsqrt | syed3000's 62-qubit file | 21.011 |
| DQI | syed3000's 891-qubit decoder | 65.106 |
| dfthcsos | syed3000's (9, 143, 39) table and angle loaders on Lera's pipeline, table weights ours | 10.662 |

## Re-verify every component here

Each file is copied from the release dataset and matched to its SHA-256; then the three official verifiers from the competition data run on it, unmodified, at their default shot counts.

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
EXPECTED_PORTFOLIO = 'v60_syed43c39'
assert MANIFEST['portfolio'] == EXPECTED_PORTFOLIO, ('stale dataset version', MANIFEST['portfolio'], EXPECTED_PORTFOLIO)
SALT = MANIFEST['salt']
print('competition data:', COMP, '| release dataset:', DS, '| salt:', SALT)
```

> **📌 Prozess-Hinweis (DE):** Der `EXPECTED_PORTFOLIO`-Assert ist ein *Stale-Dataset-Wächter*: Wenn das angehängte Dataset eine andere Version als erwartet hat, bricht der Lauf sofort ab, statt stillschweigend veraltete Circuits zu verifizieren. Billiger Schutz gegen die häufigste Assembler-Fehlerquelle.

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

```python
zip_path = WORK / 'submission.zip'
with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    for item in MANIFEST['files']:
        z.write(SUB / item['file'], item['file'])
shutil.rmtree(SUB)
print('wrote', zip_path, round(zip_path.stat().st_size / 2**20, 1), 'MiB')
```

> **📌 Prozess-Hinweis (DE):** Der komplette "Pipeline"-Kern ist ~40 Zeilen: Manifest lesen → Dateien kopieren + SHA-256 prüfen → drei offizielle Verifier laufen lassen → `assert PASS` → GM berechnen → ZIP schreiben. Das ist das *minimal-vollständige* verifizierte Portfolio. Alles, was die anderen Notebooks darüber haben (Ranking, Hedge, Frontier-Charts, Risiko-Modelle), ist Zusatzaufbau auf genau diesem Kern.

# Sources and credits

- **invsqrt** — syed3000's 62-qubit file, byte for byte, from https://www.kaggle.com/code/syed3000/vqcc-24-43-portfolio
  (Apache-2.0; dataset https://www.kaggle.com/datasets/syed3000/vqcc-2443-portfolio), which builds on the public invsqrt
  line of mrmeows (team selenium), busyaprime (Akmal Xodarev) and yoyobar. Earlier lineage of that line, as credited in
  our previous versions: Ahmed Berat Özer's patch as distributed in manwithacat's Quantum Voodoo; earlier: Phuc Thai
  (DePie), Dmitrii Gluzdov, marsyas.

- **dqi** — syed3000's 891-qubit decoder, byte for byte, from the same notebook (Apache-2.0), which builds on their own
  decoder line (made with GPT-6 Astra on SomeJoint's kit, as credited there) with ports of SomeJoint's (Agniv Banerjee)
  892-qubit work and of Ali Haydar Özdağ's (ahoirg) idea, and cites Khattar & Gidney (2024). SomeJoint's notebook credits
  GPT-6 Astra Pro, Claude, Ali Haydar Özdağ (ahoirg), yoyobar and the earlier decoder line (Alex Chilton, jday96314
  (QuantumAI), mrmeows, manwithacat, Dmitrii Gluzdov, ViberTeam, Phuc Thai (DePie)).

- **dfthcsos** — syed3000's (9, 143, 39) table and its fifteen angle loaders, the loaders byte for byte, from the same notebook
  (Apache-2.0), built on Lera's (marculera) DF-THC pipeline
  (https://www.kaggle.com/code/marculera/df-thc-10x-compact-groups-from-the-hamiltonian, Apache-2.0) and Ahmed Berat
  Özer's (ahmedberatozer) progressive rounding, and verified there with manwithacat's kickmix engine.
  The table weights (W, H2_I) in this version are ours, refined from syed3000's.
  Lera's sources, as credited there: Ahmed Berat Özer (ahmedberatozer), somejoint, mrmeows, heliosli, lightningv08,
  kozykappa, Kozykorpesh and Sumit Chongder, Artem1410 (anazemcev), haideptry via phucthaiv02, Michael Rustad, k256net
  and Dmitrii Gluzdov, and the hosts.

- **Organizers** — task definitions, verifiers and kickmix (Google Quantum AI / Qualtran, competition data).

> **📌 Prozess-Hinweis (DE):** Die Credits-Sektion ist *rekursiv*: Heliosli kreditiert syed3000, der SomeJoint und Lera kreditiert, die wiederum Özer, mrmeows, Gluzdov und andere kreditieren – bis zur Wurzel, inklusive der beteiligten AI-Modelle (GPT-6 Astra, Claude). Der eine eigene Beitrag – "The table weights (W, H2_I) in this version are ours, refined from syed3000's" – wird klar als solcher markiert. Transparenz über "was ist von mir" vs. "was ist von anderen" ist der Kern des Assembler-Ethos.

---

## 🧠 Prozess-Lektion

**Wie Heliosli arbeitet – der Assembler als Service:**

1. **Minimal-vollständig, dann skalierbar.** Das Notebook ist der *Kern* des Portfolio-Musters in ~40 Zeilen: Manifest → kopieren + Hash-Check → 3 Verifier → `assert PASS` → GM → ZIP. Alle komplexeren Notebooks (Chilton, manwithacat, prvsiyan) sind Zusatzaufbau auf genau diesem Kern. *Lektion:* Verstehe den minimalen verifizierten Loop zuerst; alles andere ist Optimierung darauf.

2. **Ein eigener Beitrag, klar markiert.** Von drei Tasks ist nur ein Teil "unser": die Table-Gewichte (W, H2_I), "verfeinert von syed3000's". Der Rest ist byte-für-byte fremde Arbeit. *Lektion:* In einem Assembler ist der eigene Wert oft *ein* verifizierter Refit – und er wird ehrlich als solcher deklariert, nicht als "unser Circuit".

3. **Stale-Dataset-Wächter.** `assert MANIFEST['portfolio'] == EXPECTED_PORTFOLIO` bricht ab, wenn das Dataset eine unerwartete Version hat. *Lektion:* Pinne die erwartete Version deiner Eingaben; ein veraltetes Dataset ist die häufigste stille Fehlerquelle bei Assembly.

4. **Rekursive Kredit-Ketten.** Die Credits nennen syed3000 → SomeJoint/Lera → Özer/mrmeows/Gluzdov/… bis zur Wurzel, plus die AI-Modelle (GPT-6 Astra, Claude), die an der Entstehung beteiligt waren. *Lektion:* Eine Kredit-Kette ist so gut wie ihre schwächste Gliederung – führe sie rekursiv, nicht nur eine Ebene.

5. **Verifikation vor allem, ohne Ausnahme.** Jede Datei wird per SHA-256 gegen das Manifest geprüft, jeder Circuit läuft durch den unveränderten offiziellen Verifier, und `assert r['status'] == 'PASS'` blockiert jede Submission mit einem fehlgeschlagenen Teil. *Lektion:* "Best-of-public" heißt: du kannst fremde Arbeit nur verwenden, wenn du sie selbst verifiziert hast. Vertrauen wird durch Hashes und Verifier-Läufe hergestellt, nicht durch Zitate.

**Meta-Erkenntnis:** Heliosli's Notebook (125 votes, der meist-vote-getestete Autor der Competition) zeigt, dass *das Publizieren eines sauberen, verifizierten Assemblers* an sich schon ein hoch bewerteter Beitrag ist – weil es der Community einen verlässlichen Startpunkt gibt, auf dem alle anderen aufbauen. "The dataset is public now. Enjoy!" ist die Devise: öffne den Rohstoff, damit die Frontier für alle schneller wandert.

## 📝 Lern-Notizen

- [ ] Minimalen verifizierten Loop bauen: Manifest lesen → kopieren + SHA-256 → 3 offizielle Verifier → `assert PASS` → GM → ZIP
- [ ] Stale-Dataset-Wächter: `assert MANIFEST['portfolio'] == EXPECTED_PORTFOLIO`
- [ ] Günstigsten Circuit pro Task wählen, aber *selbst* verifizieren (byte-für-byte fremde Arbeit ist nicht automatisch vertrauenswürdig)
- [ ] Rekursive Kredit-Kette führen: Autor → dessen Quellen → deren Quellen, inkl. verwendeter AI-Modelle
- [ ] Einen eigenen Beitrag klar markieren ("die Gewichte sind unsere, verfeinert von X")
- [ ] `format='kmb'` bei `Circuit.from_file` / `to_file` nicht vergessen (siehe Chilton-Fallstrick)
- [ ] GM = `(ref/cost_invsqrt × ref/cost_dqi × ref/cost_chem)^(1/3)` – geometrisches Mittel der drei Ratios
- [ ] Den eigenen Assembler als öffentlichen Service publizieren (Dataset + Notebook), damit andere darauf aufbauen
