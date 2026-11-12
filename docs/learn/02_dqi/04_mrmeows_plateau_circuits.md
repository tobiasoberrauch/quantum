# QCC 21.0 | Open circuits: our invsqrt and chemistry, SomeJoint's decoder. Let's all reach the plateau

> **Lernziel:** Wie man das *Plateau* erreicht — ein vollständiges `submission.zip` aus öffentlichen Quellen, jede Datei per SHA-256 gepinnt. Der DQI-Teil ist SomeJoint's **confluent Hermite decoder** (889 Qubits, 53.60×), der die Syndroms über Werte *und Ableitungen* einer rationalen Funktion liest (**Jets an 17 Knoten**); die Datei erklärt den **Q²-Faktor** („width counts twice") und dass Decoder-Scores ~1 % mit dem Salt wandern.
> **Dauer:** ~10 Minuten lesen
> **Quelle:** mrmeows | — votes (frühes 21.0-Release; nicht im Top-30-Preisbild von busyaprime enthalten)
> **Technik:** RS-Decoding (confluent Hermite / 17-Jets) + Qubit Floor + Failure Penalty
> **Level:** Mittel

---

This notebook writes a complete `submission.zip` from two public sources, every file checked against a pinned SHA-256:

- my dataset [mrmeows/qcc-1375-open-circuits](https://www.kaggle.com/datasets/mrmeows/qcc-1375-open-circuits) (Apache-2.0), version 3: the 63-qubit invsqrt at **20.06x** and the R10 chemistry at **8.61x**, with generators, certificates, official outputs and the full write-up of what changed and what did not work;
- SomeJoint's notebook output [quantum-circuits-20-96-local-gm-confluent-dqi](https://www.kaggle.com/code/somejoint/quantum-circuits-20-96-local-gm-confluent-dqi): their confluent Hermite decoder, 889 qubits, **53.60x**, built from the source embedded in their notebook. **That circuit is not mine.** Their notebook takes my invsqrt and chemistry from this dataset; this notebook takes their decoder from theirs. That is the plateau working as intended.

| Task | Q | Mean Toffolis | Cost | Ratio | By |
|---|---:|---:|---:|---:|---|
| invsqrt | 63 | 1,348.50 | 103,546.17 | 20.0565 | mrmeows |
| dqi | 889 | 480,213.8 | 4.5595e11 | 53.6007 | SomeJoint (Agniv Banerjee's team) |
| dfthcsos | 423 | 19,337 | 3.8964e8 | 8.6121 | mrmeows |

Geometric mean **21.00** on the default verifier salt. The invsqrt and chemistry numbers are my own re-runs of the unmodified official verifiers at full default shot counts (all 3,133,452 inputs at 64 shots; 87,424 chemistry shots). The decoder number is SomeJoint's official run as recorded in their notebook (0 value errors, 2 phase errors in 102,400 shots); I did not re-run it before publishing this version.

## Since the 20.39 release a few hours ago

- invsqrt: two more executed Toffolis gone, same 63 qubits and 41 rotations (104,880 to 103,672 to 103,546).
- dfthcsos: a column merge, C 60 to 59, with the lower-normalization words: T 19,522 to 19,337 at lambda_eff 47.64. error_2 sits 0.024 mHa under the gate and E_gap 1.6e-5 Ha above its floor; both are deterministic functions of the NPZ.
- dqi: SomeJoint went 51.08x to 53.60x by reading the syndromes through values and derivatives of a rational function (**jets at 17 nodes**), which nearly halves the steps of the extraction stage at a higher price per step.

Same deal as always: take it, build on it, keep the credit chains, publish what moves the plateau.

```python
# Code-Zelle: PINNT alle 22 Dateien des submission.zip per SHA-256 (darunter dqi.kmb = 0161fd2a...,
# SomeJoint's confluent Hermite decoder). Sucht unter ROOT (inkl. Zip-Member) nach Dateien mit exakt
# diesem Hash, wirft AssertionError, wenn eine fehlt, und schreibt submission.zip.
# LEHRT DIE VERIFIKATIONSKULTUR: kein File wird verwendet, ohne dass sein SHA-256 geprüft wurde.
import glob, hashlib, io, os, pathlib, zipfile

PIN = {
 "invsqrt.kmb": "0766a111a76f241aa57fbbed466436d743be13436943ddb0628c291ca07d67d6",
 "dqi.kmb": "0161fd2a6e50979838f8c4896b490ddea4d7a673588a9761a63a561a59b7ece5",
 "dfthcsos/angle_k_0.kmb": "5a479d71e3907930f937ffe6b5b19ef1dc008fb5eac82d850f8a8391a58bad52",
 "dfthcsos/angle_k_1.kmb": "cf4db4fafd67014b249d103dc5b3d5d23187ae9ba17642cedd608af68c6cc59c",
 "dfthcsos/angle_k_10.kmb": "c12ca6e2ec53e8d5b8b134413780648ebec7788ef1586b4d27ea66eb06e5973d",
 "dfthcsos/angle_k_11.kmb": "a2e0755f4f2efee668354ae3dd74777ac41be52467b9c33820262125e935942a",
 "dfthcsos/angle_k_12.kmb": "8398b99480bc1587c4ff32fb24033b1770d222cc3d34c71de4c5161f7ab73de2",
 "dfthcsos/angle_k_13.kmb": "8c35d92e284fe2f3843fced1747c2dd0dadc8855d3ce4dd283b07edc66db1c67",
 "dfthcsos/angle_k_14.kmb": "66e29c89db89a366685eab1808f88e2345dfe3b38d67fb284806d528e10989f8",
 "dfthcsos/angle_k_15.kmb": "9973fd4b037a5e3269337e1897d9cdae13499b6bb295a5575787fce984f7b1c4",
 "dfthcsos/angle_k_16.kmb": "f125386c5c300ac4193fb9252efcbe72ba1135f0d7cc9ad3fcba4959e894a90c",
 "dfthcsos/angle_k_17.kmb": "04bd6bdb0d0863983ad9f4e2733d0bf8bf99e2dd127a3dafa37bc889c814f5df",
 "dfthcsos/angle_k_18.kmb": "df26e2f91c815d7f0daccb056b522b554a99747cad468a7e3158934b154c1281",
 "dfthcsos/angle_k_2.kmb": "1d47689ff149bede10027a3a24d3decd472568250c06d73499d5a5d242eb77a4",
 "dfthcsos/angle_k_3.kmb": "bb346799b395a137943c719ec96adc038911a427cf5ab70c8b25b2f5d6c79073",
 "dfthcsos/angle_k_4.kmb": "d958805fde2e2d2b4fa5b9a032449174f7dbfeb2f7bf26527c11cc0be1d8c129",
 "dfthcsos/angle_k_5.kmb": "b4eab9612023c210b6e298b4df2b5327c5ea58df8c50701319c07051539d62da",
 "dfthcsos/angle_k_6.kmb": "7b02557fa87f0467645e91b3da296a0e7d71a849310f49667ca286399daea4ed",
 "dfthcsos/angle_k_7.kmb": "a076db5f1fc47a91853a40cf014033040c41fc48656c69c748b584a60a71c9db",
 "dfthcsos/angle_k_8.kmb": "d4e2fe0264b3eeac51b710f1c7613e58cd1427d1f832b65ecc6cd16f16e9db64",
 "dfthcsos/angle_k_9.kmb": "3326abb0cd525e7822088ef1608af44a81d4118d94669b3b0adf0c803b69daf6",
 "dfthcsos/submission.npz": "8229861b3ee22316e144c900737dfc54f7a30ea88de77ff5391f3375d050fa87"
}

ROOT = pathlib.Path(os.environ.get('QCC_INPUT_ROOT', '/kaggle/input'))

def sha(b): return hashlib.sha256(b).hexdigest()

def candidates(name):
    """Yield bytes of every file under ROOT whose path ends with `name`, including members of zip files."""
    base = name.split('/')[-1]
    for p in ROOT.rglob(base):
        if p.is_file() and str(p).replace(os.sep, '/').endswith('/' + name):
            yield p.read_bytes()
    for z in ROOT.rglob('*.zip'):
        try:
            with zipfile.ZipFile(z) as zf:
                for m in zf.namelist():
                    if m.endswith('/' + name) or m == name:
                        yield zf.read(m)
        except zipfile.BadZipFile:
            continue

files = {}
for name, h in PIN.items():
    for data in candidates(name):
        if sha(data) == h:
            files[name] = data
            break
    else:
        raise AssertionError(f'{name}: no file with sha256 {h[:12]}... under {ROOT} (attach both the dataset and the SomeJoint notebook output)')
out = pathlib.Path(os.environ.get('QCC_OUTPUT', '/kaggle/working')) / 'submission.zip'
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for name, data in files.items():
        z.writestr(name, data)
print(len(files), 'files verified by SHA-256 and written to', out)
```

## How it got here

Every point is a fully verified result (official verifier, default shots). The first chart is the overall score; the three panels are the per task ratios on their own scales. The jumps are architecture changes; the flat parts are everything else.

```python
# Code-Zelle: Zeichnet die Score-Historie (geometrisches Mittel der drei Verhältnisse) von 15.75 bis 21.00.
# Die DQI-Kurve zeigt: der Family-Wechsel (Schur -> 882q -> 889q confluent) IST der Sprung.
# invsqrt ab dem 5. Punkt bei 63 Qubits; dfthcsos = Rustad R10 + mrmeows' Compiler.
import matplotlib.pyplot as plt

BLUE, GOLD, INK, MUTED, GRID, BG = '#2a78d6', '#c8891a', '#0b0b0b', '#52514e', '#e4e3df', '#fcfcfb'
plt.rcParams.update({'figure.facecolor': BG, 'axes.facecolor': BG, 'axes.edgecolor': GRID,
    'axes.labelcolor': MUTED, 'xtick.color': MUTED, 'ytick.color': MUTED, 'text.color': INK,
    'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': True, 'grid.color': GRID,
    'grid.linewidth': 0.8, 'axes.axisbelow': True, 'font.size': 11})

def line(ax, xs, ys, fmt, mark=None, color=BLUE):
    ax.plot(range(len(xs)), ys, color=color, lw=2, marker='o', ms=7, mec=BG, mew=2)
    ax.set_xticks(range(len(xs)), xs, rotation=35, ha='right', fontsize=9)
    for i, y in enumerate(ys):
        if i in (0, len(ys) - 1) or (mark and xs[i] in mark):
            ax.annotate(fmt.format(y), (i, y), textcoords='offset points', xytext=(0, 10), ha='center', color=INK, fontsize=10)
    ax.margins(x=0.08, y=0.25)

steps = ['11.76', '13.22', '13.71', '14.50', '15.05', '15.75 release', 'Schur 918q', 'Schur Q888', 'R10 chem',
         'route C', 'refit', 'inv caches', '883q dqi', 'chem 8.56', 'inv 20x', '20.39 release', '882q dqi', 'chem C59', 'confluent dqi']
scores = [11.76, 13.22, 13.71, 14.50, 15.05, 15.75, 17.63, 18.60, 19.51, 20.05, 20.13, 20.23, 20.30, 20.36, 20.39, 20.39, 20.66, 20.70, 21.00]
fig, ax = plt.subplots(figsize=(12, 4))
line(ax, steps, scores, '{:.2f}', mark={'15.75 release', 'Schur 918q', 'route C', '20.39 release'})
ax.axhline(20, color=GOLD, lw=1, ls='--'); ax.text(0.1, 20.2, '20', color=GOLD)
ax.set_title('Overall score (geometric mean of the three ratios), 15.75 release to this one', loc='left', color=INK)
plt.tight_layout(); plt.show()

fig, axs = plt.subplots(1, 3, figsize=(14, 4))
line(axs[0], ['78q', '76q', '68q', '66q', '63q', 'r10', 'r13', 'caches', 'front', '20x', 'now'],
     [15.04, 16.00, 17.27, 18.17, 19.13, 19.50, 19.52, 19.80, 19.95, 20.03, 20.06], '{:.2f}x', mark={'63q'})
axs[0].axhline(20, color=GOLD, lw=1, ls='--')
axs[0].set_title('invsqrt ratio (63 qubits from the 5th point on)', loc='left', color=INK)
line(axs[1], ['SomeJoint', 'round12', 'Q881', 'Q880', 'Q870', 'Schur 918q', '882q', 'Q888', '883q Ozer', '882q SJ', '889q SJ'],
     [26.42, 27.41, 28.22, 29.00, 30.52, 41.96, 48.55, 49.29, 49.37, 51.08, 53.60], '{:.2f}x', mark={'Q870'})
axs[1].set_title('dqi ratio: the family switch is the step', loc='left', color=INK)
line(axs[2], ['start', '10-bit', 'B333', 'B303', 'gauge', 'refit', 'R10', 'route C', 'refit', 'lambda', 'comb.', 'C59'],
     [4.24, 5.62, 6.15, 6.435, 6.468, 6.691, 7.73, 8.38, 8.48, 8.556, 8.574, 8.612], '{:.2f}x', mark={'refit'})
axs[2].set_title('dfthcsos ratio: Rustad R10 + my compiler', loc='left', color=INK)
plt.tight_layout(); plt.show()
```

## Where the gains came from

**invsqrt**: mean executed Toffolis per shot, 19.13x to 20.06x, all at 63 qubits and all exact on every legal input. Rotations went 44 to 41, and the 20x step raised the phase margin instead of spending it.

**dqi**: Toffolis and qubits by decoder family. Cost is R x Q^2 x T, so **width counts twice**; the Schur family wins on both, and SomeJoint's two rebuilds keep taking Toffolis out of the extraction stage.

**dfthcsos**: where the 19,337 Toffolis of the current build go. The angle lookups are 19 circuits charged twice (forward and reverse) at 275 CCX each; the rest is the official state preparation model, which depends only on the shape.

```python
# Code-Zelle: Drei Detail-Plots. Der mittlere (dqi) zeigt die zwei Decoder-Familien als Streudiagramm
# (Qubits vs. mean Toffolis in Tausend): round12 Q870 (30.5x), Schur 918q (42.0x), Schur Q888 (49.3x),
# Ozer 883q (49.4x), SomeJoint 882q (51.1x), SomeJoint 889q (53.6x). Titel: „cost is R x Q^2 x T".
fig, axs = plt.subplots(1, 3, figsize=(15, 4.2))

names = ['19.13x (release)', 'round10', 'round13', 'history caches', 'front decoder', '20.03x', '20.06x']
tofs = [1404.09, 1394.1, 1392.09, 1368.0, 1356.0, 1350.5, 1348.5]
ax = axs[0]
ax.plot(range(len(names)), tofs, color=BLUE, lw=2, marker='o', ms=7, mec=BG, mew=2)
ax.set_xticks(range(len(names)), names, rotation=35, ha='right', fontsize=9)
for i, v in enumerate(tofs):
    if i in (0, len(tofs) - 1):
        ax.annotate(f'{v:,.1f}', (i, v), textcoords='offset points', xytext=(14, 8) if i == 0 else (0, -18),
                    ha='left' if i == 0 else 'center', color=INK)
ax.margins(x=0.1, y=0.3); ax.set_title('invsqrt: mean Toffolis per shot, 63 qubits', loc='left', color=INK)

ax = axs[1]
fam = [('round12 Q870 (30.5x)', 870, 884041, MUTED, (10, -4)), ('Schur 918q, 0 errors (42.0x)', 918, 580216, BLUE, (10, 8)),
       ('Schur Q888 (49.3x)', 888, 521531, BLUE, (10, 8)), ('Ozer 883q (49.4x)', 883, 519152, GOLD, (-10, -24)),
       ('SomeJoint 882q (51.1x)', 882, 508519, GOLD, (-10, 12)), ('SomeJoint 889q (53.6x)', 889, 480214, GOLD, (10, -14))]
for n, q, t, c, off in fam:
    ax.scatter(q, t / 1000, s=140, color=c, edgecolor=BG, zorder=3)
    ax.annotate(n, (q, t / 1000), textcoords='offset points', xytext=off, fontsize=9, color=INK,
                ha='right' if off[0] < 0 else 'left')
ax.set_xlabel('qubits'); ax.set_ylabel('mean Toffolis (thousands)'); ax.set_xlim(855, 945); ax.set_ylim(430, 960)
ax.set_title('dqi: two decoder families, cost is R x Q^2 x T', loc='left', color=INK)

ax = axs[2]
parts = [('outer prep', 399), ('inner state prep', 6238), ('Givens', 2250), ('ANGLE lookups 19 x 2 x 275', 10450)]
left = 0
cols = [MUTED, MUTED, MUTED, BLUE]
for i, ((n, v), c) in enumerate(zip(parts, cols)):
    ax.barh([0], [v], left=left, color=c, height=0.45, edgecolor=BG)
    if c == BLUE:
        ax.text(left + v / 2, 0, f'{n}\n{v:,}', ha='center', va='center', fontsize=9, color=BG)
    else:
        ax.annotate(f'{n}  {v:,}', (left + v / 2, 0.24), xytext=(left + v / 2, 0.42 + 0.14 * (i % 2)),
                    textcoords='data', ha='center', fontsize=8.5, color=INK,
                    arrowprops=dict(arrowstyle='-', color=MUTED, lw=0.8))
    left += v
ax.set_xlim(0, 19337); ax.set_ylim(-0.35, 0.75); ax.set_yticks([]); ax.grid(False)
ax.set_xticks([0, 5000, 10000, 15000, 19337], ['0', '5k', '10k', '15k', '19,337'])
ax.set_title('dfthcsos: where T = 19,337 goes (Q 423)', loc='left', color=INK)
plt.tight_layout(); plt.show()
```

## What is settled (so nobody repeats it)

- **BLISS is not a scored parameter.** The verifier's loader overwrites the submitted symmetry shifts with `load_fixed_shifts()` before deriving the shifted operator; under the fixed shifts lambda_eff cannot go below 46.79 at the official gap floor.
- **There is no 7 bit qubit cliff on the R10/B129 shape.** Official preflight: 8 bits Q=423, fixed T 9,072; 7 bits Q=419, fixed T 8,772. The cliff is real for B=128 (694 to 403), which is why B=129 already sits on the cheap side. Seven bit words would still save about 10% through the angle circuits, if a word set passed the 20 mHa gates.
- **A cost-first screen of 10,954 chemistry shapes** (official cost model, universal exact lookup compiler as the T bound) found no new shape with a passing fit. Shapes with Q near 384 and T near 16.6k exist on paper; none has a fit yet. That fit is the whole distance between 21 and 22.
- **Five words per ANGLE circuit** is worth about 2% here, not more, and overflows the 128 qubit cap on a 1,366 address table.
- **Decoder scores move about 1% with the salt.** Compare decoders on the same salt at 102,400 shots; fewer value errors are worth more than fewer Toffolis when they are close.
- The constant-seed invsqrt model (128 entry seed, degree 3) passes the full domain numerically at worst error/tolerance 0.617 and is not compiled yet. If you compile it first, publish the flame chart.

## Credits

- **invsqrt:** Akmal Xodarev (busyaprime), Phuc Thai (DePie), Dmitrii Gluzdov, marsyas.
- **dqi:** Agniv Banerjee and the SomeJoint team (the shipped confluent decoder, and the alternating-prefix one before it); Alex Chilton (883 qubit reverse synthesis); jday96314 (QuantumAI); Gu, Kemeny, Yelin and Lukin (arXiv:2610.22367, andigu/uncompute); Ahmed Berat Ozer (v8 Bezout splice); earlier lineage Dmitrii Gluzdov, ViberTeam, manwithacat, Phuc Thai.
- **dfthcsos:** Michael Rustad (the R10 factorization), Ahmed Berat Ozer (group compression), marculera (four address loaders), Vladislav Lavrentev (lightningv08, five word schedule).
- **Verifiers and kickmix:** Google Quantum AI.

The full method notes, negative results and open directions are in the dataset README.

---

## 🔑 Kern-Technik in 3 Sätzen

1. **Confluent Hermite / 17-Jet-Decoding:** SomeJoint's Decoder liest die Reed-Solomon-Syndroms nicht nur über *Werte*, sondern über Werte **und Ableitungen** einer rationalen Funktion an **17 Knoten** (Jets) — das halbiert die Schritte der Extraktionsphase fast, kostet aber mehr pro Schritt; zusammen mit der schmalen 889-Qubit-Breite bringt es den DQI-Ratio von 51.08× auf 53.60×.
2. **„Width counts twice“ (Q²-Faktor):** Die DQI-Cost ist R × Q² × T, also zählt die Qubit-Breite doppelt — deshalb gewinnen die Decoder-Familien, die *sowohl* Qubits *als auch* Toffolis senken (Schur-Familie), und deshalb ist der Family-Wechsel im Chart der eigentliche Sprung, nicht die feinen Toffoli-Optimierungen.
3. **Plateau durch offene Circuits:** Man baut nicht alles selbst, sondern pinnt die jeweils besten öffentlichen Circuit-Familien per SHA-256 (hier mrmeows' invsqrt+Chemistry und SomeJoint's DQI-Decoder) zu einem `submission.zip` — „take it, build on it, keep the credit chains, publish what moves the plateau“.

## ⚠️ Häufigste Fehlerfalle

**Decoder auf unterschiedlichen Salts vergleichen.** mrmeows stellt explizit fest: „Decoder scores move about 1% with the salt.“ Wer zwei Decoder auf verschiedenen Salts (oder mit unterschiedlicher Fehlerrate) vergleicht, misst Salt-Rauschen statt echten Fortschritt — man muss auf demselben Salt bei 102,400 Shots vergleichen, und wenn sie nah beieinander liegen, sind **weniger Value-Errors mehr wert als weniger Toffolis** (weil R(k) den Cost direkt multipliziert). Zweitgefährlich: den confluent-Hermite-Gewinn nur an einem Draw zu messen — hier sind es 0 Value-Errors, aber 2 Phase-Errors in 102,400 Shots, und mrmeows hat den Decoder vor der Veröffentlichung gar nicht neu gelaufen (er vertraut SomeJoint's offiziellen Lauf).

## 📝 Lern-Notizen (füll das selbst aus)

- [ ] Decoding-Prinzip verstanden: confluent Hermite = Syndroms als Werte + Ableitungen (Jets) einer rationalen Funktion an 17 Knoten; halbiert die Extraktionsschritte, teurer pro Schritt.
- [ ] Cost-Formel R(k)×Q²×T internalisiert: Q² heißt, 889 vs 882 vs 918 Qubits ist der dominante Hebel; Toffoli-Reduktion in der Extraktionsphase ist sekundär.
- [ ] Product Caching nachvollziehbar: Hier nicht die Haupttechnik (das ist busyaprimes R41), aber „SomeJoint's two rebuilds keep taking Toffolis out of the extraction stage“ = Produkte/Schritte in der Extraktion werden wiederverwendet bzw. eliminiert.
- [ ] Verbindung zu invsqrt/Chem: invsqrt = linear in Q (63 Qubits, 20.06×), Chemistry = λ_eff·T·Q (linear, 8.61×), DQI = R·Q²·T (quadratisch, 53.60×) → DQI hat den größten Ratio UND den größten Qubit-Hebel; das Plateau (GM 21.00) wird von allen drei getragen.
- [ ] Frage die ich noch habe: Was genau sind die „17 nodes“ — sind das die 17 Produkte der 17-Variante (siehe busyaprimes „17-product DQI variants“), und wie hängt die Jet-Ableitungs-Tiefe mit der Fehlerkorrektur-Stärke zusammen?
