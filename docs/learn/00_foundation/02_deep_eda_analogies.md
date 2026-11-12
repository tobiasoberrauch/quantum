# 🧠 How Quantum Circuits Reached the 25× Frontier

> **Lernziel:** Du verstehst die drei Quanten-Benchmarks (InVSQRT, DQI, FeMoCo-Chemistry) über anschauliche Analogien (Fabrik, Stadt, Küche), kannst die offiziellen Kostenfunktionen erklären, und siehst die vollständige Evolution von Score 1.0 auf 25.14 — inklusive aller experimentellen Fehlschläge und der finalen SHA-pinned Verifizierung.
> **Dauer:** ~45 Minuten lesen
> **Quelle:** evgendvorkin | https://www.kaggle.com/code/evgendvorkin/google-quantum-ai-deep-eda-with-analogies | 58 votes
> **Wichtigste Konzepte:**
> - Drei Analogien: Fabrik (InVSQRT), Stadt (DQI), Michelin-Küche (Chemistry) — jede erklärt eine andere Kostenstruktur
> - Kostenfunktionen: invsqrt = Q×C, dqi = R(ε₊)·Q²·T, dfthcsos = λ_eff·T_total·Q_total
> - Geometrisches Mittel als Leaderboard-Metric: higher is better
> - Experiment-Ledger: dokumentierte Fehlschläge (SVD-Truncation, Bit-Truncation) sind genauso wichtig wie Erfolge
> - SHA-256-pinned Verifizierung: 18 Dateien, 3 offizielle Verifier, reproduzierbares Ergebnis

---

**What is the scientific question?** Google defines three exacting computational tasks. A valid quantum circuit must produce the right result and use as few costly resources as possible. This Notebook explains the problem, audits public architectures, and performs **fresh official verification** of a newer 18-file open portfolio.

**Research provenance.** Our [published V22](https://www.kaggle.com/code/evgendvorkin/google-quantum-ai-deep-eda-with-analogies?scriptVersionId=366600651) reached **25.00894 Kaggle Public** after 25.008936130425 local verification. The preceding heliosli portfolio (V23 source) reported **25.14224**. This V24 reproduces the updated heliosli **25.14772 source portfolio**, release `v95mxfu_mxf_ay3`, from [The dataset is public now. Enjoy!](https://www.kaggle.com/code/heliosli/the-dataset-is-public-now-enjoy). Only the inverse-square-root circuit and Chemistry weights changed relative to V23: the new components are credited to [maoxin123](https://www.kaggle.com/code/maoxin123/lb-25-14-public-frontier-refit-chem-weights). The DQI decoder and 15 ANGLE lookup circuits are identical to V23. Underlying circuits and source algorithms belong to their credited authors; our contributions are the educational EDA, full Stories, Reading Room, circuit archaeology and independent verification.

**Read your way:** 📚 [THE READING ROOM](#reading-room) · [Evolution](#evolution) · [Factory](#factory) · [City](#city) · [Kitchen](#kitchen) · [Research ledger](#experiment-ledger) · [3 official PASS](#build-verifier) · [Credits](#credits).

*Reproducible input: official Competition Data plus [heliosli's QCC circuits live Dataset](https://www.kaggle.com/datasets/heliosli/qcc-circuits-live), containing manifest `v95mxfu_mxf_ay3`, or a private copy of the [exact archived release](https://drive.google.com/file/d/1w2sAU49MONCSHanR0yl_wh2kj06xmLRb/view). The loader verifies all 18 source files by SHA-256, decompressing DQI from `.xz` in chunks. No network calls are made during verification.*

---

<a id="reading-room"></a>
## 📚 The Reading Room — From Our Analogies to the Actual Science

*The papers explain the algorithms. The competition's reference circuits and official verifiers provide the measurements.*

| Source | Why it matters to our investigation |
|:--|:--|
| [Google Quantum AI — Competition & evaluation](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/overview) | Official challenge rules, benchmarks and submission instructions |
| [Khattar et al. (2026) — *Leveraging verifiable structure in quantum circuits to find more efficient compilations with agentic AI*](https://arxiv.org/abs/2610.23832) | Main research paper connecting all three tasks to classically verifiable circuit structure |
| [Qualtran / kickmix — Official open-source implementation](https://github.com/quantumlib/Qualtran/tree/main/kickmix) | Library behind `.kmb` circuit generation and resource inspection |
| [Rubin et al. (2023) — *Quantum computation of stopping power for inertial fusion target design*](https://arxiv.org/abs/2308.12352) | Why inverse-square-root phase arithmetic matters for fusion-related simulation |
| [Jordan et al. (2024) — *Optimization by Decoded Quantum Interferometry*](https://arxiv.org/abs/2408.08292) | Where the DQI benchmark comes from and how decoding connects to optimization |
| [Khattar et al. (2025) — *Verifiable Quantum Advantage via Optimized DQI Circuits*](https://arxiv.org/abs/2510.10967) | Technical background for reversible Reed–Solomon decoding and efficient circuits |

**First-party ground truth:** the bundled `verifiers/` source code and `verifiers/dfthcsos/SCORING_README.md` define the precise contracts applied to the supplied files. The papers motivate the problem; **the verifiers decide whether a candidate passes**.

---

<a id="latest-result"></a>
<a id="evolution"></a>
## 🏆 From Google's Reference to the 25× Frontier

We started with Google's three reference quantum circuits and a score of **1.00**. Today, we are studying solutions that have achieved a **25-fold improvement** over that baseline.

But the real story is not the number itself. Every major leap challenged us to rethink **how quantum computations work and why one circuit costs less than another**.

## 🧬 Evolution — How the Solutions Developed

| Stage | Score | What Changed and What We Learned |
|:--|--:|:--|
| 🟢 **Google Reference** | 1.00 | Three quantum tasks, three different sources of computational cost. |
| 🏭 **V7** | 15.6810 | Our first strong combination of open solutions. We discovered that the three tasks could be improved independently. |
| 🌆 **V8** | 18.4315 | A new DQI decoder and compressed Chemistry. Architecture matters more than individual gates. |
| 👨‍🍳 **V9–V12** | 21.8798 | R10 factorization and coefficient optimization. We learned to verify physical accuracy, not just cost. |
| 🧪 **V13** | 22.6316 | **Our improvement:** 12 orthogonal rotations reduced Chemistry cost while preserving correctness. |
| ⚡ **V14** | 24.4325 | A new DQI decoder and Chemistry's transition from R8/C60 to R9/C39. One of the largest architectural leaps. |
| 🌠 **V16** | 24.5942 | Compact R8/C45 Chemistry demonstrated that different architectures can lead to better results. |
| 💠 **V17–V18** | 24.7978 | Improved circuits and numerical weights. The search for smaller resource savings began. |
| 🏆 **V19–V20** | 24.94093 | Advances in DQI and the reuse of intermediate computations. |
| 🧭 **V21** | 24.94111 | Another DQI optimization and new Chemistry coefficients. |
| 🚀 **V22** | 25.00894 | A new combination of InVSQRT, DQI, and Chemistry crossed the 25× frontier. |
| ✨ **V23** | 25.14224 | A newer inverse, updated DQI and chemistry weights — sourced from heliosli's credited release. |
| 🚀 **V24** | 25.14772 | The same DQI and ANGLE loaders, with maoxin123's upgraded InVSQRT and Chemistry weights in heliosli's new release. |

### 🔬 What We Discovered Beyond the Table

Our EDA helped us understand what drives the cost of quantum circuits: qubit counts, expensive gates, the structure of ANGLE tables, and the physical accuracy of Chemistry.

In our private **Astra** laboratory, we investigated the original circuit generators and found a way to reduce a historical DQI block from **56 to 40 Toffoli-like operations**. This is a verified local optimization that still needs to be integrated into a modern circuit.

Studying **29 consecutive versions of InVSQRT** revealed something unexpected: algorithmic progress was not a continuous series of improvements. Sometimes, researchers increased the cost while exploring a different architecture before discovering a more efficient solution.

**The key insight:** the biggest leaps came from changing the computation itself. Smaller improvements emerged as researchers developed a deeper understanding of an existing algorithm.

That is why this work is more than a Notebook with a score around 25. It is **a research diary about understanding and improving quantum computation**.

---

<a id="factory"></a>
## 🏭 Story I — The Quantum Factory

Imagine that Google owns **three factories**. The first computes an extremely precise numerical function; the second decodes a difficult message; the third prepares instructions for a quantum chemistry simulation.

Every factory works. The problem is its **resource bill**. Some machines are expensive to run, some production lines occupy too much space, and even seemingly harmless shortcuts may change the product.

You are the efficiency engineer. **Redesign the process, but keep the product correct.**

| Inside the factory | Inside the competition |
|:--|:--|
| A factory | A quantum circuit or subroutine |
| Machines and floor space | Logical qubits |
| Operations on the assembly line | Quantum gates / instructions |
| Expensive manufacturing steps | Toffoli-like gates and other costly non-Clifford operations |
| Temporary workstations | Ancilla / scratch qubits |
| An independent quality inspector | Official verifier |
| Operating cost | Task-specific cost function |

**Factory insight:** a file containing more instructions is not necessarily more expensive according to the *official* resource metric. Our EDA will measure both, and keep them separate.

<a id="city"></a>
## 🌆 Story II — Quantum City: Every Qubit Occupies Land

Now we are architects of a futuristic city, where **every square meter is expensive**. The city needs permanent infrastructure, but it also needs construction sites for temporary work.

Here's the catch: you cannot simply move into a new construction site while leaving the old one full of debris. In reversible computation, temporary quantum registers must be returned to their required states — often \(|0\rangle\) — before their space can be safely reused.

| Quantum City | Quantum-circuit engineering |
|:--|:--|
| Land | Qubit capacity |
| Permanent infrastructure | Registers that must stay live |
| Temporary building site | Scratch / ancilla workspace |
| Clearing and reusing a site | Uncomputation / workspace reuse |
| City planning constraint | Qubit caps and persistent-vs-temporary allocation |
| Expensive new district | Extra logical qubits contributing to cost |

**A concrete example from our baseline:** each chemistry `ANGLE_k` circuit uses **119 qubits**, while that part of the verifier allows at most **128**. Just **nine qubits** of local headroom remain. The **overall** chemistry qubit bill also includes state-preparation resources, so it is not equal to 119.

**City insight:** freeing temporary workspace can matter as much as removing gates — but only if the verifier approves the cleanup.

<a id="kitchen"></a>
## 👨‍🍳 Story III — The Quantum Michelin Kitchen

Welcome to a restaurant with **three impossibly precise recipes**. A great chef reduces waste, eliminates unnecessary steps and makes clever substitutions. But there is a non-negotiable rule: **the final dish must pass inspection**.

Some recipes allow a tiny approximation, others demand a particular quantum phase, and every recipe needs its own quality test. A cheap dish that fails inspection does not earn any points.

| Michelin Kitchen | Quantum compilation |
|:--|:--|
| Recipe | Quantum algorithm / circuit design |
| Ingredients | Encoded numerical parameters |
| Utensils and workspace | Qubits and temporary registers |
| Cooking steps | Gates and arithmetic subroutines |
| Acceptable taste tolerance | Benchmark-specific numerical / statistical accuracy |
| Michelin inspector | Official verification contract |
| Total restaurant bill | Measured resources and task cost |

**Kitchen insight:** the cheapest *valid* recipe wins. The term **valid** is the entire challenge: correct numerical value alone may not be enough if the phase or scratch registers are wrong.

---

## 🗺️ Three acts of quantum engineering

**Act I · Inspect the reference machines.** We measure gate types, widths and lookup-table properties in Google's reference examples. They are reference circuits, *not* the optimized C60 submission.

**Act II · Understand the bill.** The inverse-square-root error envelope, the DQI width penalty and the geometric-mean Score show why certain improvements are disproportionately valuable.

**Act III · Enter the research lab.** Compare the R10 and C60 architectures, document why rank truncation fails, test a Gram-preserving numerical refinement, and reconstruct the full three-task C60 portfolio with new official verifier runs.

---

## ⚡ A 30-second engineering map

**Problem:** Build three valid, low-cost quantum circuits. **Bill:** qubits and expensive gate operations, plus task-specific accuracy and repetition penalties. **Goal:** maximize the geometric mean of reference-to-candidate cost ratios.

**The three routes to improvement:**

1. **Factory · InVSQRT:** replace repeated numerical work with cheaper reversible arithmetic and lookup structure.
2. **City · DQI:** optimize decoding, uncompute temporary workspace and reduce expensive nonlinear operations.
3. **Kitchen · Chemistry:** change the mathematical factorization and refit weights without invalidating the physical Hamiltonian.

**Reader challenge:** If the cost of DQI falls but its qubit footprint rises, is that necessarily better? The answer comes from the verifier's *full* cost function, not a single gate count.

---

## 🔎 How to read the evidence in this Notebook

| Label | What it means | What it does *not* mean |
|:--|:--|:--|
| **Official PASS** | Unmodified verifier accepted the particular submitted circuit | Universal proof for every possible input unless specifically established |
| **Verified local GM** | Our three-task verifier run completed and computed reference/candidate ratios | Kaggle Public score |
| **Public LB** | Kaggle measured a published submission | That we invented its upstream circuit architecture |
| **Source estimate** | An upstream author predicted the score from checked costs | Our independently verified improvement |

**Look for evidence before/after each mechanism:** a measured reduction, a correctness check and an explicit owner/source. We preserve unsuccessful historical experiments because they help explain *why* an apparent shortcut was rejected.

---

## 01 · 🔧 Open the factory: environment & tools

Our starting point is Google's **reference circuit package** and the `kickmix` resource inspector. We'll explore the reference files first, then run three official verifiers against a refined portfolio in Section 15.

The figures are rendered as static PNG images, preserving their appearance in a saved Kaggle Notebook.

Setup: installiert kaleido für statisches PNG-Rendering, konfiguriert Plotly-Stil, findet Competition-Daten und lädt kickmix.

```python
# Prepare static PNG export BEFORE importing Plotly.
# In Kaggle's Plotly 5.24.1 environment, kaleido==0.2.1 works.
# If a package must be downloaded, enable Internet in Kaggle settings.
import sys, subprocess
from importlib.metadata import version, PackageNotFoundError

try:
    kaleido_installed = version('kaleido')
except PackageNotFoundError:
    kaleido_installed = None

if kaleido_installed != '0.2.1':
    try:
        subprocess.check_call([
            sys.executable, '-m', 'pip', 'install', '-q', 'kaleido==0.2.1'
        ], timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        print('⚠️ Kaleido unavailable; EDA graphs will use a notebook renderer:', repr(exc))

from pathlib import Path
from collections import deque
import ast, math
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from IPython.display import display, Markdown

pio.renderers.default = 'png'  # Prefer static images for published EDA.

# If Plotly was imported in an old, still-running kernel, refresh detection.
import importlib
import plotly.io._kaleido as kaleido_backend
if kaleido_backend.scope is None:
    importlib.reload(kaleido_backend)
if kaleido_backend.scope is None:
    # A missing static image backend must never prevent valid circuit verification.
    pio.renderers.default = 'notebook'
    print('⚠️ Plotly static export unavailable; interactive notebook figures enabled.')

# A unified, presentation-ready visual style.
INK = '#233044'
MUTED = '#64748b'
NAVY = '#183b65'
TEAL = '#0f9488'
GOLD = '#d79b32'
CORAL = '#d96755'
PURPLE = '#8c6cbd'
BG = '#ffffff'

def finish(fig, height=430, legend=False):
    fig.update_layout(
        template='plotly_white', height=height,
        paper_bgcolor=BG, plot_bgcolor=BG,
        font=dict(family='Arial, sans-serif', color=INK, size=12),
        title_font=dict(size=19, color=NAVY),
        margin=dict(l=40, r=35, t=75, b=50),
        showlegend=legend,
        hoverlabel=dict(bgcolor='white', font_size=12),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor='#d7e1ea')
    fig.update_yaxes(gridcolor='#edf2f7', zeroline=False, linecolor='#d7e1ea')
    return fig

matches = list(Path('/kaggle/input').rglob('invsqrt.kmb'))
if not matches:
    raise FileNotFoundError(
        'Competition input not found. Use Add Input → competition data: '
        'google-verifiable-quantum-circuit-compilation.'
    )

root = next((p.parent.parent for p in matches
             if (p.parent.parent / 'kickmix' / 'kickmix.so').is_file()), None)
if root is None:
    raise FileNotFoundError('Found invsqrt.kmb, but not kickmix/kickmix.so in its dataset root.')

sys.path.insert(0, str(root / 'kickmix'))
import kickmix as km

print('✅ Competition root:', root)
print('✅ kickmix loaded:', getattr(km, '__file__', '(module loaded)'))
print('✅ Static PNG charts enabled; CPU-only EDA; no full verifier run')
```

---

## 02 · 📦 Factory inventory: there is no `train.csv`

A normal Kaggle EDA begins with rows, columns, and missing values. Here the *units of analysis* are files, circuits, registers, and numerical arrays.

**Why file size matters:** it tells us how difficult a baseline is to distribute or inspect. **Why it is not the leaderboard cost:** compressed bytes are not the number of executed gates, and different benchmarks price resources differently.

Listet alle Dateien im Competition-Dataset und gruppiert nach Family mit Größen.

```python
all_files = sorted(p for p in root.rglob('*') if p.is_file())
files_df = pd.DataFrame([
    {'File': str(p.relative_to(root)),
     'Family': p.relative_to(root).parts[0],
     'Type': p.suffix.lower() or '(none)',
     'MiB': p.stat().st_size / 2**20}
    for p in all_files
])
print(f'📁 {len(files_df)} files | {files_df.MiB.sum():,.1f} MiB total')
display(files_df.groupby('Family', as_index=False)
        .agg(Files=('File', 'size'), Size_MiB=('MiB', 'sum'))
        .sort_values('Size_MiB', ascending=False).round(2))

top_files = files_df.nlargest(12, 'MiB').sort_values('MiB')
fig = px.bar(top_files, x='MiB', y='File', orientation='h',
             color='Family',
             color_discrete_sequence=[NAVY, TEAL, GOLD, PURPLE],
             title='The factory inventory · 12 largest supplied files',
             labels={'MiB':'File size (MiB)', 'File':''})
fig.update_traces(hovertemplate='%{y}<br>%{x:.2f} MiB<extra></extra>')
finish(fig, 530, True).show()
```

### 🔍 Observation A · A giant file is not automatically an expensive computation

In the reference package inspected for this study, **`dqi.kmb` occupies roughly 845 MiB**, while **`invsqrt.kmb` is only about 0.55 MiB**. This makes DQI the dominant *disk-size* item — not necessarily the dominant cost in the official score.

Because the DQI binary is so large, **we deliberately do not load it in the default EDA**. We can still study its formal verifier contract, default parameters, and resource trade-offs without risking the notebook memory budget.

---

## 03 · 🏭 Circuit X-ray: what do the machines actually do?

The first job is to measure the **reference** `invsqrt` circuit and the **ten** chemistry `ANGLE_k` circuits. Each file is loaded one at a time, profiled, then released.

We distinguish:

- **Qubits** → size of the logical workspace (our 🌆 city footprint).
- **Instructions** → raw number of serialized operations; **not** the cost metric.
- **Toffoli-like** → an important class of expensive gates; still not the whole score.
- **Non-Clifford** → gates outside the cheaper Clifford family.
- **T-like / Z-power** → phase-gate details, particularly relevant to `invsqrt`.

The counts below are **static circuit statistics**. Executed per-shot counts and additional synthesis / heuristic terms may differ.

Lädt die Referenz-Circuits (invsqrt + 10 ANGLE_k), misst Qubits, Instructions, Toffoli-like, Non-Clifford, T-like.

```python
source_dir = root / 'sample_submission'
angle_paths = sorted((source_dir / 'dfthcsos').glob('angle_k_*.kmb'),
    key=lambda p: int(p.stem.rsplit('_', 1)[-1]))
scan_paths = [source_dir / 'invsqrt.kmb'] + angle_paths


def stat_number(stats, name, default=np.nan):
    try:
        v = getattr(stats, name)
        if callable(v):
            v = v()
        return int(v)
    except (AttributeError, TypeError, ValueError):
        return default

circuit_records = []
for path in scan_paths:
    c = km.Circuit.from_file(str(path))
    s = c.operation_statistics()
    circuit_records.append({
        'Circuit': path.stem,
        'Family': 'Inverse square root' if path.stem == 'invsqrt' else 'ANGLE lookup',
        'Qubits': int(c.num_qubits),
        'Registers': int(c.num_registers),
        'Instructions': stat_number(s, 'num_instructions'),
        'Toffoli-like': stat_number(s, 'num_toffoli_like'),
        'Non-Clifford': stat_number(s, 'num_non_clifford'),
        'T-like': stat_number(s, 'num_t_like'),
        'File (MiB)': path.stat().st_size / 2**20,
    })
    del s, c

circuit_df = pd.DataFrame(circuit_records)
circuit_df['Toffoli / instruction'] = (
    circuit_df['Toffoli-like'] / circuit_df['Instructions']
)
print('📋 Reference circuit feature matrix (DQI binary intentionally excluded)')
display(circuit_df.round({'File (MiB)':3, 'Toffoli / instruction':4}))
```

Scatter-Plot: Qubits vs. Toffoli-like Operations, farbig nach Family.

```python
fig = px.scatter(
    circuit_df, x='Qubits', y='Toffoli-like',
    size='Instructions', color='Family', text='Circuit',
    size_max=43,
    color_discrete_map={'Inverse square root':CORAL, 'ANGLE lookup':TEAL},
    title='The machine room · Qubits vs expensive gates',
    labels={'Toffoli-like':'Static Toffoli-like operations', 'Qubits':'Logical qubits'},
    hover_data={'Instructions':':,', 'Registers':True,
                'File (MiB)':':.3f', 'Circuit':False}
)
fig.update_traces(textposition='top center', textfont_size=10)
finish(fig, 520, True).show()
```

> **Factory insight.** The ten ANGLE machines share a **119-qubit / 3,974-Toffoli-like** configuration, while the reference `invsqrt` machine uses **260 qubits / 7,735 Toffoli-like** operations. A smaller file can have a larger logical footprint and a larger expensive-gate count.

**Do not turn this into a cross-task leaderboard ranking:** the tasks use different mathematical cost functions and correctness conditions.

---

## 04 · ⚙️ Ten production batches, two surprising regimes

If every ANGLE circuit has the same qubit and Toffoli-like counts, are all the batches identical? **No.** Look at the total number of instructions.

Gruppiert die 10 ANGLE-Batches in zwei Regime (0–3 vs. 4–9) und zeigt die Instruction-Zählung.

```python
angles_df = circuit_df[circuit_df['Family']=='ANGLE lookup'].copy()
angles_df['Batch'] = angles_df['Circuit'].str.rsplit('_', n=1).str[-1].astype(int)
angles_df = angles_df.sort_values('Batch').reset_index(drop=True)
angles_df['Regime'] = np.where(angles_df['Batch'] < 4,
                               'Batches 0–3', 'Batches 4–9')

fig = px.bar(angles_df, x='Batch', y='Instructions', color='Regime',
             text='Instructions',
             color_discrete_map={'Batches 0–3':TEAL, 'Batches 4–9':GOLD},
             title='Ten production lines · Same Toffoli count, different instructions')
fig.update_traces(texttemplate='%{text:,.0f}', textposition='outside',
                  textfont_size=10)
fig.update_xaxes(tickmode='linear', dtick=1, title='ANGLE batch index')
fig.update_yaxes(range=[0, float(angles_df['Instructions'].max())*1.16],
                 title='Raw circuit instructions')
finish(fig, 470, True).show()

regime_df = (angles_df.groupby('Regime', as_index=False)
             .agg(Batches=('Batch','size'),
                  Mean_instructions=('Instructions','mean'),
                  Min_instructions=('Instructions','min'),
                  Max_instructions=('Instructions','max'),
                  Toffoli_like=('Toffoli-like','first'),
                  Qubits=('Qubits','first')))
display(regime_df.round(1))
print('Instruction range (max / min - 1):',
      f"{100*(angles_df.Instructions.max()/angles_df.Instructions.min()-1):.1f}%")
```

### Observation B · The same equipment, different workloads

Across the ten reference ANGLE circuits, static Toffoli-like count and qubit footprint are **constant**, but the instruction count varies by about **18% from smallest to largest**.

**Hypothesis, not yet a causal finding:** the different quantized angle distributions might influence the number of cheap / conditional operations. Let's inspect the underlying words before deciding *why* the circuits differ.

---

## 05 · 👨‍🍳 The chemistry pantry: what's inside `submission.npz`?

The chemistry submission contains arrays rather than a training set. Think of these as **ingredients and recipes**, not rows with labels.

| Array | Interpretation (high level) |
|:--|:--|
| `angle_words` | Quantized angle lookup words loaded by ANGLE circuits |
| `tree_edges` | Connectivity for a rotation tree |
| `U`, `W` | Numerical factorization-related arrays |
| `H2_I`, `H1_I`, `Hsym_lower` | Additional supplied terms / auxiliary data |

**Important:** a submitted numeric array is not automatically the source of truth for every metric. In particular, the chemistry verifier recovers angle words from the **circuits**; read its README to understand which submitted fields are used or ignored.

Lädt `submission.npz` und zeigt Shape, Dtype, Min/Max, Zero-Anteil jedes Arrays.

```python
npz_path = source_dir / 'dfthcsos' / 'submission.npz'
with np.load(npz_path, allow_pickle=False) as z:
    ingredients = {name: z[name].copy() for name in z.files}

array_info = []
for name, a in ingredients.items():
    array_info.append({
        'Ingredient': name,
        'Shape': str(a.shape),
        'Dtype': str(a.dtype),
        'Elements': a.size,
        'Min': float(np.min(a)),
        'Max': float(np.max(a)),
        'Zero share (%)': 100*float(np.mean(a==0))
    })
display(pd.DataFrame(array_info).round(3))

words = ingredients['angle_words'].astype(np.int64, copy=False)
edges = ingredients['tree_edges'].astype(np.int64, copy=False)
print(f'🍳 Angle words: {words.shape[0]:,} addresses × {words.shape[1]} rotations = {words.size:,} values')
print(f'🔢 Range: {words.min()}…{words.max()} | unique: {np.unique(words).size:,}')
print(f'🏙️ Tree: {edges.shape[0]} edges')
```

---

## 06 · 🔢 Twelve-bit recipes: where are the ones?

An angle word is a quantized integer. We can examine the activity of each bit position to discover regularities in the reference lookup tables.

Below we inspect all twelve bit positions and the 75 rotation columns distributed across ten ANGLE batches.

Zeigt die Bit-Aktivität (Anteil = 1) für alle 12 Bit-Positionen der Angle-Wörter.

```python
BIT_WIDTH = 12  # Baseline example: values lie in 0...4095.
bit_frequency = np.array([
    np.mean((words >> bit) & 1) * 100 for bit in range(BIT_WIDTH)
])
bit_df = pd.DataFrame({'Bit':np.arange(BIT_WIDTH), 'On (%)':bit_frequency})

fig = px.bar(bit_df, x='Bit', y='On (%)',
             color='On (%)', color_continuous_scale=[[0,TEAL],[1,GOLD]],
             title='The recipe bits · Fraction of words with bit = 1',
             text='On (%)')
fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
fig.add_hline(y=50, line_dash='dash', line_color='#9aa9b7',
              annotation_text='50% reference' , annotation_position='top left')
fig.update_xaxes(tickmode='linear', dtick=1)
fig.update_yaxes(range=[0,65])
fig.update_layout(coloraxis_showscale=False)
finish(fig, 435).show()
```

### Observation C · Low bits are busy; the highest bits are less frequently set

For the supplied baseline, bits 0–8 are set roughly half the time, while bits 10 and 11 are set **only about 29%** of the time.

Does that mean two bits are redundant? **No.** Even rarely set bits can determine correctness. The verifier checks decoded angle words and numerical reconstruction; a simple change in precision can fail the official acceptance gates.

---

## 07 · 🧩 Batch heatmap: a pattern hidden in the lookup table

The supplied sample uses **8 rotation columns per batch** (`J = 8`), with the final batch containing three columns. This is the basis for the ten `angle_k_*.kmb` files.

Let's look at the **bit activity for each batch**, rather than averaging all 298,200 numbers together.

Berechnet die Bit-Aktivität pro ANGLE-Batch und zeigt ein Heatmap + Korrelations-Scatter.

```python
J = 8  # Baseline sample layout; see official SCORING_README.md
batches = [(k, words[:,k*J:min((k+1)*J,words.shape[1])])
           for k in range(math.ceil(words.shape[1]/J))]
if len(batches) != len(angle_paths):
    raise ValueError('The ANGLE batch count differs from baseline J=8; inspect scoring README.')

batch_rows, activity = [], []
for k, a in batches:
    high10 = 100 * np.mean((a >> 10) & 1)
    high11 = 100 * np.mean((a >> 11) & 1)
    activity.append([100*np.mean((a >> b)&1) for b in range(BIT_WIDTH)])
    batch_rows.append({
        'Batch':k, 'Columns':a.shape[1],
        'Mean word':float(a.mean()),
        'Median word':float(np.median(a)),
        'Unique words':int(np.unique(a).size),
        'Bit 10 (%)':high10,
        'Bit 11 (%)':high11,
        'Zero (%)':100*float(np.mean(a==0)),
    })
batch_df = pd.DataFrame(batch_rows)
display(batch_df.round(2))

fig = go.Figure(go.Heatmap(
    z=np.asarray(activity), x=[f'bit {i}' for i in range(BIT_WIDTH)],
    y=[f'ANGLE {i}' for i in range(len(activity))],
    colorscale=[[0, '#e9f6f4'],[0.5,TEAL],[1,NAVY]],
    zmin=0, zmax=60,
    colorbar=dict(title='% of ones'),
    hovertemplate='%{y} · %{x}<br>On: %{z:.2f}%<extra></extra>'
))
fig.update_yaxes(autorange='reversed')
fig.update_layout(title='The hidden recipe · Bit activity by ANGLE batch')
finish(fig, 490).show()
```

Korrelation zwischen Mean Word und Instruction Count, gefärbt nach Bit-11-Aktivität.

```python
joined = angles_df[['Batch','Instructions','Toffoli-like','Qubits']].merge(
    batch_df[['Batch','Mean word','Bit 11 (%)']], on='Batch', validate='one_to_one'
)
fig = px.scatter(
    joined, x='Mean word', y='Instructions',
    color='Bit 11 (%)', size='Bit 11 (%)', size_max=28,
    text='Batch',
    color_continuous_scale=[[0,TEAL],[1,GOLD]],
    title='Hypothesis map · Mean angle word vs circuit instructions',
    labels={'Mean word':'Mean encoded angle word',
            'Instructions':'Raw circuit instructions'}
)
fig.update_traces(textposition='top center')
finish(fig, 445).show()
```

### 🧠 Why this is interesting

Early batches (0–2, and much of 3) occupy a narrow range of encoded words. Batches 4–9 span a broader range. **Instruction count rises alongside that change**, while static Toffoli-like counts remain constant.

This raises a useful engineering question: which word-distribution patterns translate into *measured* savings when the lookup circuit is rebuilt? The generator and the official resource model give us the answer, rather than the bit histogram alone.

---

## 08 · 🌆 Quantum City: a tree with 76 neighborhoods

The `tree_edges` array connects the chemistry's **76 nodes** and organizes its rotation structure.

We'll measure connectivity, degrees, depth and branching, then draw the supplied tree using node `0` as a convenient visual root.

Analysiert den Givens-Tree: BFS von Node 0, misst Tiefe, Grad, Blätter; zeichnet hierarchisches Layout.

```python
all_nodes = sorted(set(map(int, edges.reshape(-1))))
adj = {node:[] for node in all_nodes}
for left, right in edges:
    u, v = int(left), int(right)
    adj[u].append(v)
    adj[v].append(u)

root_node = 0 if 0 in adj else all_nodes[0]
parent = {root_node:None}
depth = {root_node:0}
queue = deque([root_node])
while queue:
    u = queue.popleft()
    for v in sorted(adj[u]):
        if v not in depth:
            parent[v] = u
            depth[v] = depth[u] + 1
            queue.append(v)

is_tree = (len(edges)==len(all_nodes)-1 and len(depth)==len(all_nodes))
assert is_tree, 'Expected a connected tree; inspect supplied tree_edges.'
children = {u:[] for u in all_nodes}
for v, p in parent.items():
    if p is not None:
        children[p].append(v)

leaf_count = sum(len(adj[u])==1 for u in all_nodes)
degrees = [len(adj[u]) for u in all_nodes]
print('🏙️ CITY STRUCTURE')
print('Nodes:', len(all_nodes), '| Edges:',len(edges),'| Connected tree:',is_tree)
print('Leaf nodes (undirected degree 1):',leaf_count)
print('Max degree:',max(degrees),'| Depth from chosen root:',max(depth.values()))
display(pd.DataFrame({'Depth':list(depth.values())})
        .groupby('Depth',as_index=False).size().rename(columns={'size':'Nodes'}))

# Deterministic, pure-Python hierarchical layout — no networkx required.
xpos = {}
leaf_cursor = [0]
def place(u):
    if not children[u]:
        xpos[u] = leaf_cursor[0]
        leaf_cursor[0] += 1
    else:
        for v in children[u]:
            place(v)
        xpos[u] = float(np.mean([xpos[v] for v in children[u]]))
place(root_node)

edge_x, edge_y = [], []
for v, p in parent.items():
    if p is not None:
        edge_x.extend([xpos[p],xpos[v],None])
        edge_y.extend([-depth[p],-depth[v],None])

fig = go.Figure()
fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode='lines',
                         line=dict(color='#cbd5e1', width=1.3),
                         hoverinfo='skip', showlegend=False))
fig.add_trace(go.Scatter(
    x=[xpos[u] for u in all_nodes], y=[-depth[u] for u in all_nodes],
    mode='markers',
    marker=dict(size=9, color=[len(adj[u]) for u in all_nodes],
                colorscale=[[0,TEAL],[0.5,GOLD],[1,CORAL]],
                line=dict(width=1.2,color='white'),
                colorbar=dict(title='Degree')),
    text=[f'Node {u} · depth {depth[u]} · degree {len(adj[u])}'
          for u in all_nodes],
    hovertemplate='%{text}<extra></extra>', showlegend=False
))
fig.update_layout(title='Quantum City · The baseline 76-node rotation tree',
                  xaxis=dict(visible=False), yaxis=dict(visible=False))
finish(fig, 530).show()
```

### Observation D · A compact tree, but not a free circuit

For this sample, the tree has **76 nodes, 75 edges, 44 leaves**, and maximum undirected degree **7**. Its depth from visual root `0` is **6**.

The diagram shows *connectivity*, not hardware layout or actual live qubits. Understanding how a tree affects costs requires tracing the official angle lookup and reconstruction logic — another good target for follow-up research.

---

## 09 · 🧬 The remaining ingredients: factorization coefficients

The chemistry factorization combines the angle table with the real-valued arrays `U`, `W`, `H2_I` and `Hsym_lower`. Together they determine the numerical representation and its resource estimates.

Let's inspect their ranges and coefficient distributions. These numbers describe a single physical system, with each array playing its own role in the Hamiltonian.

Zeigt statistische Kennzahlen (Mean, Std, P01, Median, P99, Max abs) und Histogramme für U, W, H2_I.

```python
coefficient_names = ['U','W','H2_I','Hsym_lower']
coefficient_rows = []
for name in coefficient_names:
    a = ingredients[name].astype(np.float64, copy=False).reshape(-1)
    coefficient_rows.append({
        'Array':name, 'Shape':str(ingredients[name].shape),
        'Mean':a.mean(), 'Std':a.std(), 'P01':np.percentile(a,1),
        'Median':np.median(a), 'P99':np.percentile(a,99),
        'Max abs':np.max(np.abs(a)),
    })
display(pd.DataFrame(coefficient_rows).round(5))

# Fixed deterministic sampling protects notebooks if future versions are larger.
rng = np.random.default_rng(2026)
coeff_long = []
for name in ['U','W','H2_I']:
    a = ingredients[name].reshape(-1)
    if a.size > 30000:
        a = a[rng.choice(a.size, size=30000, replace=False)]
    coeff_long.append(pd.DataFrame({'Value':a,'Array':name}))
plot_coefficients = pd.concat(coeff_long, ignore_index=True)

fig = px.histogram(plot_coefficients, x='Value', color='Array',
                   facet_row='Array', nbins=90, opacity=.85,
                   color_discrete_map={'U':TEAL,'W':GOLD,'H2_I':CORAL},
                   title='Ingredients under the microscope · Coefficient distributions',
                   labels={'Value':'Coefficient value'})
fig.for_each_annotation(lambda a: a.update(text=a.text.split('=')[-1]))
fig.update_yaxes(matches=None, showticklabels=True)
fig.update_xaxes(matches=None, showticklabels=True)
finish(fig, 700).show()
```

> **Kitchen insight.** `U` has a much wider numeric range than `W` in the sample arrays. That does **not** mean we can simply threshold smaller coefficients: every proposed approximation must survive the official reconstruction-error and normalization checks. Think of precision as part of the recipe, not decorative seasoning.

---

## 10 · ⚖️ What does the verifier actually bill us for?

This is the most important conceptual difference from a conventional prediction task: the **score is a resource bill for a *valid* quantum implementation**. A cheap but incorrect scheme is rejected.

### ⚡ Benchmark I: `invsqrt` — preserve the phase

For every input $x$ in the benchmark domain, the circuit must implement

$$
|x\rangle|0\cdots0\rangle\longmapsto
e^{2\pi i/\sqrt{x}}|x\rangle|0\cdots0\rangle.
$$

- **Input:** 22-bit $x$, covering $1\leq x\leq 3{,}133{,}452$.
- **Accuracy:** phase tolerance $2^{-24}/\sqrt{x}$ in turns.
- **Correctness:** restore the input and all workspace; match the required phase.
- **Cost:** $Q\times C$, where $C$ incorporates Toffoli-equivalent gates **and** synthesis of rotations (not raw instruction count).

The default full check performs 64 shots per input — about **200.5 million** shots. **We deliberately do not invoke it here.**

### 🧩 Benchmark II: `dqi` — accuracy itself has a price

The decoder operates over \(GF(2^{12})\) with default \(m=4095\) positions and \(n=70\) syndrome registers. The provided code draws 102,400 test shots from an official **non-uniform error distribution**. The code measures failures conservatively, using the one-sided Clopper–Pearson upper bound \(\varepsilon_+\).

$$
C_{\mathrm{DQI}}=R(\varepsilon_+)\,Q^2T,
\qquad R(\varepsilon)=\frac{\ln2}{-\ln(\tfrac12+2\sqrt\varepsilon)}.
$$

- Must have \(\varepsilon_+<1/16\).
- **\(Q^2\)**: qubit reductions carry quadratic weight in this benchmark.
- \(T\): mean actually executed Toffoli-like gates, not merely static instructions.
- Input has 840 quantum syndrome bits (70 × 12); the 4095 × 12 MBUC outcome bits are **classical**, not additional logical qubits.

### 🧬 Benchmark III: `dfthcsos` — the complete recipe

$$
C_{\mathrm{chem}}=\lambda_{\mathrm{eff}}\,T_{\mathrm{total}}\,Q_{\mathrm{total}}.
$$

`T_total` includes **forward and reverse** ANGLE lookups plus heuristic state-preparation and Givens-rotation costs. `Q_total` includes **persistent** qubits plus the **maximum** shared temporary workspace, not a naive sum of all circuit qubits.

The supplied scoring README imposes strict acceptance gates: no ANGLE circuit may exceed **128 qubits**, reconstruction errors must be at most **20 mHa**, and both \(\Lambda>49.0\) and \(E_{gap}>3.914898\) Ha must hold, alongside \(0<E_{gap}<2\Lambda\).

The chemistry reference uses **119 of the 128 permitted ANGLE-circuit qubits**: only **9 spare qubits** under this local cap.

**Read these contracts in the bundled source:** `verifiers/invsqrt/verify_submission_invsqrt.py`, `verifiers/dqi/verify_submission_dqi.py`, and `verifiers/dfthcsos/SCORING_README.md`.

---

## 11 · 📐 The inverse-square-root accuracy envelope

This quick numerical illustration draws the **exact target value and allowed absolute error**, not actual errors from the baseline. Its sole purpose is to show the scale of the requested precision.

Zeichnet die exakte Zielkurve 1/√x und den erlaubten Fehlerbereich (log-log).

```python
max_x = 3*(2**10 - 2)**2
xs = np.unique(np.rint(np.geomspace(1,max_x,360)).astype(np.int64))
target = 1/np.sqrt(xs.astype(float))
allowed_abs_err = 2.0**-24 * target

fig = go.Figure()
fig.add_trace(go.Scatter(x=xs, y=target, mode='lines',
                         name='Exact 1/sqrt(x)', line=dict(color=TEAL,width=3)))
fig.add_trace(go.Scatter(x=xs, y=allowed_abs_err, mode='lines',
                         name='Allowed absolute phase error (turns)',
                         line=dict(color=CORAL,width=3,dash='dash')))
fig.update_layout(title='Precision is part of the recipe · Target vs permitted error',
                  xaxis_title='x (log scale)', yaxis_title='Value (log scale)')
fig.update_xaxes(type='log')
fig.update_yaxes(type='log')
finish(fig, 450, True).show()
```

---

## 12 · 🧩 DQI: the cost of uncertainty

DQI is a particularly different factory: a small failure rate may be allowed, **but it gets priced**. The verifier uses a confidence upper bound $\varepsilon_+$, not simply the observed failure fraction.

With the default **102,400** shots and confidence failure probability $2^{-128}$, even **zero observed failures** do not imply an upper bound of zero. The curve below is a **mathematical exploration of the published cost formula**, not a measured DQI baseline.

Exploriert die DQI-Kostenfunktion R(ε₊) mathematisch; zeigt den CP-Upper-Bound bei 0 Fehlern.

```python
N_DQI = 400 * 256
DELTA = 2.0**-128
# Clopper-Pearson one-sided upper confidence bound when k = 0 failures.
eps_if_zero_fail = -np.expm1(np.log(DELTA) / N_DQI)

def repetition_overhead(eps):
    e = np.asarray(eps, dtype=float)
    if np.any((e < 0) | (e >= 1/16)):
        raise ValueError('epsilon must satisfy 0 <= epsilon < 1/16')
    return np.log(2)/(-np.log(0.5 + 2*np.sqrt(e)))

eps_grid = np.linspace(0,0.06,250)
r_grid = repetition_overhead(eps_grid)
fig = go.Figure()
fig.add_trace(go.Scatter(x=eps_grid, y=r_grid, mode='lines',
                         line=dict(color=PURPLE,width=3), name='R(epsilon)'))
fig.add_vline(x=eps_if_zero_fail, line_dash='dash', line_color=GOLD,
              annotation_text='CP upper bound if 0 failures',
              annotation_position='top left')
fig.update_layout(title='DQI · A tiny error bound changes the resource bill',
                  xaxis_title='One-sided error upper bound ε₊',
                  yaxis_title='Repetition overhead R(ε₊)')
fig.update_yaxes(type='log', title='Repetition overhead R(ε₊) · log scale')
finish(fig,470).show()
print(f'At N = {N_DQI:,} shots, 0 failures give ε₊ ≈ {eps_if_zero_fail:.7f}')
print(f'The corresponding repetition overhead is R ≈ {float(repetition_overhead(eps_if_zero_fail)):.4f}×')
print('Illustration only — no DQI verifier was run.')
```

---

## 13 · 🌆 A thought experiment: why a smaller city sometimes wins

All three benchmarks reward less expensive *valid* computations, but their resource formulas have different sensitivities.

For intuition, suppose an experimental change reduces qubits by **10%** and increases the expensive-gate component by **5%**. What happens if other cost factors stay fixed?

**These are hypothetical normalized calculations — not verified new circuits.**

Vergleicht die hypothetische Kostenänderung (−10% Qubits, +5% Gates) über alle drei Benchmarks.

```python
scenarios = pd.DataFrame([
    {'Benchmark':'invsqrt · Q × C',
     'Relative cost':0.90*1.05},
    {'Benchmark':'DQI · Q² × T × R',
     'Relative cost':0.90**2*1.05},
    {'Benchmark':'Chemistry · λ × T × Q',
     'Relative cost':0.90*1.05},
])
scenarios['Change (%)'] = (scenarios['Relative cost'] - 1)*100
scenarios['Verdict'] = np.where(scenarios['Relative cost']<1,
                                 'Lower hypothetical cost','Higher hypothetical cost')
display(scenarios.round(3))

fig = px.bar(scenarios, x='Benchmark', y='Relative cost',
             color='Benchmark', text='Relative cost',
             color_discrete_sequence=[TEAL,PURPLE,GOLD],
             title='A hypothetical redesign · 10% fewer qubits, 5% more gates')
fig.add_hline(y=1, line_dash='dash', line_color=CORAL,
              annotation_text='No improvement')
fig.update_traces(texttemplate='%{text:.3f}×', textposition='outside')
fig.update_yaxes(range=[0,1.15], title='New cost / old cost')
fig.update_xaxes(title='')
finish(fig, 435).show()
```

### 🏆 And what about the *competition* leaderboard?

The individual benchmark costs are **lower-is-better**. The combined Kaggle measure is the geometric mean of improvements relative to the three reference costs:

$$
\mathrm{Leaderboard\ Score}=
\left(\frac{C_{\mathrm{ref},1}}{C_1}
\frac{C_{\mathrm{ref},2}}{C_2}
\frac{C_{\mathrm{ref},3}}{C_3}\right)^{1/3}.
$$

So **higher is better** on the combined leaderboard. Improving just one benchmark can matter, even if the other two remain at reference performance. But a **valid submission still needs the required artifacts for all three tasks**.

Illustriert das geometrische Mittel mit Beispiel-Szenarien.

```python
example_gains = [
    ('All three at baseline', 1,1,1),
    ('One task 2× cheaper', 2,1,1),
    ('One task 4× cheaper', 4,1,1),
    ('All three 2× cheaper', 2,2,2),
]
leaderboard_illustration = pd.DataFrame([
    {'Illustration':name, 'Gain 1':g1, 'Gain 2':g2, 'Gain 3':g3,
     'Overall':(g1*g2*g3)**(1/3)}
    for name,g1,g2,g3 in example_gains
])
display(leaderboard_illustration.round(3))
```

---

## 14 · 🧠 Four clues from the reference circuits

| Observation | Research question |
|:--|:--|
| Original ANGLE batches: 119 qubits and 3,974 static Toffoli-like operations | Could a different lookup architecture compress this resource cost? |
| Uneven angle-bit activity | Which bits can be encoded cheaply without violating accuracy constraints? |
| The geometry of qubit use | Would a lower-qubit decoder beat a lower-Toffoli decoder? |
| FeMoCo weight structure | How can we change a factorization without changing the chemistry it represents? |

The three stories suggest different engineering strategies: reduce operations in the **Factory**, reuse memory in the **City**, and reformulate coefficients in the **Kitchen**. The research ledger below follows the last strategy and records where a tempting shortcut fails.

---

<a id="experiment-ledger"></a>
## 15 · 🔬 An experiment ledger that separates discoveries from composition

### Experiment 01 · The full evolution

The plot below records historical reference points and explicitly distinguishes our **verified local/Public milestones** from the **new source checkpoint**. Changes in this line may reflect circuit synthesis, decoder structure, a different physical factorization, or imported components; the curve alone is not a causal ablation.

> **How to read the remaining ledger:** Experiments 02–05 preserve earlier R8/C60 investigations (including failures), 06–07 document the R9/C39 and compact-group transitions, and 08 records the current one-CCZ change. We do not convert the Astra subblock experiment into a Public Score claim.

Zeichnet die vollständige Score-Evolution von Reference (1.0) bis V24 Source (25.14772).

```python
milestones = pd.DataFrame([
    ('Reference', 1.0, 'Reference', 'official benchmark'),
    ('V7', 15.681036, 'Historic', 'public architecture'),
    ('V8', 18.431534, 'Historic', 'DQI architecture'),
    ('V12', 21.879769, 'Historic', 'chemistry + small refinement'),
    ('V13', 22.631601551, 'Historic', 'C60 / rotations'),
    ('Open v44', 23.0308, 'Source local', 'source-reported local GM'),
    ('V14', 24.4325303223301, 'Verified local', 'R9/C39 + new DQI'),
    ('V16', 24.594211039869, 'Verified local', 'SomeJoint compact factorization'),
    ('V17', 24.786102426501, 'Public LB', 'Heliosli portfolio'),
    ('V18', 24.797825178941, 'Public LB', 'inverse + chemistry refit'),
    ('V19', 24.85585, 'Public LB', 'Syed DQI v7'),
    ('V20', 24.94093, 'Public LB', 'yoyobar public portfolio'),
    ('V21', 24.941111244564, 'Verified local', 'Maoxin v2 + yoyobar DQI'),
    ('V22', 25.00894, 'Kaggle Public', 'Syed + Ozer alternate DQI'),
    ('V23 source', 25.14224, 'Source checkpoint', 'heliosli v93hs7u_hs6_ay3'),
    ('V24 source', 25.14772, 'Source checkpoint', 'heliosli v95mxfu_mxf_ay3'),
], columns=['Stage','Score','Evidence','Mechanism'])
fig = px.line(milestones, x='Stage', y='Score', markers=True, text='Score',
              title='Quantum engineering evolution — source evidence vs verified scores')
fig.update_traces(line_width=3, marker_size=11, textposition='top left')
fig.add_scatter(x=['V23 source','V24 source'], y=[25.14224,25.14772], mode='markers',
                marker=dict(size=17, symbol='diamond-open', line=dict(width=2, color='#b7791f')),
                name='Source checkpoint', showlegend=True)
fig.update_yaxes(range=[0,29], title='Geometric mean of reference / cost ratios')
finish(fig,height=485,legend=True).show()
display(milestones.style.hide(axis='index').format({'Score':'{:.9f}'}))
print('V24 source release 25.14772; the independently verified local GM is computed below.')
```

### Experiment 02 · A rank reduction that fails physics

The released FeMoCo factorization uses `R=8, B=143, C=60`. At the original coefficients, the two physical errors are nearly on the 20 mHa boundary. Lowering C on paper reduces resource cost, but we must test the *reconstructed Hamiltonian*, not just gate counts.

We tried an orthogonal SVD transformation followed by truncation. The new C59 and C58 candidates missed the official accuracy limit. The plot separates the two things people often conflate: **a lower theoretical cost and a valid physical solution**.

Zeigt die physikalische Zulässigkeit: beide Fehler müssen ≤ 20 mHa sein.

```python
phys = pd.DataFrame([
    ('C60 original',60,19.99877,19.99880,48.56091),
    ('C59 SVD truncation',59,20.44442,22.77338,64.26237),
    ('C58 SVD truncation',58,21.66821,26.17327,64.28111),
],columns=['Candidate','Rank C','Error 1 (mHa)','Error 2 (mHa)','lambda_eff'])
fig = px.scatter(phys, x='Error 1 (mHa)',y='Error 2 (mHa)',color='Candidate',text='Candidate',
                 title='Physical admissibility: both errors must be ≤ 20 mHa')
fig.add_vline(x=20, line_dash='dash', line_color='gray')
fig.add_hline(y=20, line_dash='dash', line_color='gray')
fig.update_traces(marker_size=13,textposition='top left')
finish(fig,height=430).show()
display(phys)
```

### Experiment 03 · Resource projections are not candidate circuits

Using the official chemistry cost model, a smaller C would be attractive *if* accuracy and the remaining resource parameters stayed unchanged. The rightmost points below are hypotheses, not verified submissions. The SVD test above explains why simply deleting factor columns is not enough.

Zeigt die konditionale Score-Frontier für C=54..60 (nur C60 ist physisch verifiziert).

```python
frontier=pd.DataFrame([
    (60,22.629719,True),(59,22.665430,False),(58,22.701830,False),
    (57,22.737999,False),(56,22.792082,False),(55,22.828746,False),(54,22.907950,False),
],columns=['Rank C','Conditional Score','Physically verified candidate'])
fig=px.line(frontier.sort_values('Rank C'),x='Rank C',y='Conditional Score',markers=True,
            title='Conditional score frontier — a research target, not a leaderboard')
fig.update_traces(marker_size=10,line_width=3)
fig.update_xaxes(autorange='reversed')
finish(fig,height=410).show()
display(frontier)
```

### Experiment 04 · Rotate the recipe instead of deleting ingredients

We kept all 60 factor columns and the exact ANGLE truth tables. The new numerical experiment applies **twelve selected orthogonal column rotations** to `W` and `H2_I` together. Because these rotations preserve the appropriate Gram matrices, the two-body operator is unchanged apart from floating-point rounding. The independent classical FeMoCo check found no meaningful change in the two physical errors or the gap, while the one-body-adjusted norm decreased.

| Measurement | Original C60 | Rotated C60 |
|:--|--:|--:|
| Two-body norm (`lambda_H2`) | 290.300138 | **290.149384** |
| Effective normalization (`lambda_eff`) | 48.560906 | **48.548751** |
| Source portfolio Score / projected score | 22.629719 | **~22.631608** |

The estimate becomes a **measured portfolio result only after the fresh verifier runs below**. The ANGLE programs, DQI program and inverse-square-root program are reused byte-for-byte.

Zeigt den gemessenen λ_eff-Gewinn durch 12 orthogonale Rotationen.

```python
gain_df=pd.DataFrame([
    ('Source C60',48.56090566),
    ('12 rotations',48.54875062),
],columns=['Experiment','lambda_eff'])
fig=px.bar(gain_df,x='Experiment',y='lambda_eff',color='Experiment',text='lambda_eff',
           title='Measured numerical gain at fixed factor rank and unchanged ANGLE tables')
fig.update_traces(texttemplate='%{text:.8f}',textposition='outside')
fig.update_yaxes(range=[48.54,48.57],title='lambda_eff (truncated axis)')
finish(fig,height=405).show()
print('Independent numerical estimate: 22.629719 → ~22.631608; verify with Google below.')
```

### Experiment 05 · What did not work yet?

- **Small random J5 basis searches:** sixty search attempts produced no cheaper exact compiled ANGLE circuit.
- **SVD rank truncation:** C59 and C58 violated the FeMoCo accuracy threshold; a new jointly optimized factorization is needed.
- **Simple angle-bit truncation:** the 8→7-bit rounded tables failed the physical test.
- **Naive cache rescheduling:** existing C60 schedules outperform simple greedy alternatives; an improved compiler must beat those exact plans, not a rough arithmetic bound.

These failures define our next engineering work: optimize truth-table synthesis or build a new physically admissible rank reduction. Neither is silently presented as a result in this edition.

### Experiment 06 · New public architecture: R9/C39 + DQI 891Q

A source archaeology audit across ten archived stages found a fundamental change from **R8/C60 → R9/C39** and a cheaper **891-qubit DQI**. All eighteen submitted members differ between v44 and v60. We did not invent this representation; we independently reproduced its released bytes and obtained **three fresh official PASS, local GM 24.4325303223** in a private Kaggle run. The executable section below repeats the verification for this Notebook version.

**Negative findings remain part of the record.** Our own ANGLE XOR coding and ordinary QROM variants did not establish an actual Toffoli reduction; a mere 5% reduction in BDD nodes is *not* an official quantum resource gain. The R9/C39 codebook and physical weights must be optimized jointly to create a genuinely new valid candidate.

### Experiment 07 · Competing chemistry architectures: V14 R9/C39 vs V16 R8/C45

| Source | R/B/C | Chemistry Q | Chemistry T | λeff | Source-local chemistry ratio |
|:--|:--|--:|--:|--:|--:|
| V14 verified v60 | 9 / 143 / 39 | 428 | 15,629 | ~47.049 | 10.662058 |
| SomeJoint V16 source | 8 / 143 / 45 | 427 | 15,459 | ~47.184606 | 10.773592 |

**Observation:** a factorization with **more columns C** can still be cheaper overall, because Q, T, λ and the corresponding loader circuits all matter. A good architecture search cannot rank candidates by C alone. The R8/C45 source is not our new physical model. The verifier cells below check this exact credited release.

### Experiment 08 · Astra research versus V23 public assembly

| Question | Historical Astra work | V23 public release |
|:--|:--|:--|
| **Mechanism** | Source-level `phase_B` optimization in an early DQI decoder | Reuse of publicly released newer Kirill/Özer/Atakan/Syed-line DQI assembled and published by heliosli |
| **Measured resource effect** | Historical 56 → 40 static Toffoli at 64Q; matched local subblock tests | Source report: 892-qubit DQI decoder `f277b054` and upstream provenance in the pinned manifest; verify cost with the official tool |
| **Evidence boundary** | Equivalence demonstrated only for historical subblock | New 18-file release reproduces upstream architectures; exact local GM measured below |
| **Next work** | Recover and modify active generators; integrate only after exact whole-circuit verification | Read all component credits, pin all 18 files including the decompressed `.xz` DQI and verify three official tasks |

**No hidden Astra patch is included in the present source package.** Our separate research continues on algorithm generators and Chemistry refit.

---

<a id="build-verifier"></a>
## 16 · 🛠️ Exact V24 reproduction — three fresh official verifiers

**Source:** [heliosli — The dataset is public now. Enjoy!](https://www.kaggle.com/code/heliosli/the-dataset-is-public-now-enjoy) and the version-pinned [QCC circuits live Dataset](https://www.kaggle.com/datasets/heliosli/qcc-circuits-live). **Saved release:** [archive (55).zip](https://drive.google.com/file/d/1w2sAU49MONCSHanR0yl_wh2kj06xmLRb/view). Exact release ID: `v95mxfu_mxf_ay3`; eighteen submitted files, including the 892-qubit DQI stored as `dqi.kmb.xz`. The original source's `CREDITS.md` identifies the actual contributors to each circuit. This release combines **maoxin123's version-3 inverse**, **maoxin123's version-3 Chemistry W / H2_I refit**, and heliosli's existing DQI composition on the Kirill Tymchishin / Ahmed Berat Özer / Syed / Atakan lineage; the 15 ANGLE loader binaries remain from Syed Asad Ali. Both `.kmb` and `.npz` replacements are credited to their creators.

### Kaggle inputs

1. Attach the **official Google Quantum AI Competition Data**.
2. Attach the public [heliosli Dataset](https://www.kaggle.com/datasets/heliosli/qcc-circuits-live) with pinned release `v95mxfu_mxf_ay3` in `QCC_RELEASE_MANIFEST.json`, or make the exact archived ZIP available as a Kaggle Dataset.
3. Use Kaggle CPU / Python 3.13. The loader detects the release by its embedded manifest, verifies **all 18 SHA-256 checksums and lengths**, and streams the LZMA-compressed DQI into `submission/dqi.kmb`. A changed/stale Dataset version is rejected.

The official unmodified task verifiers run against **InVSQRT, DQI and Chemistry** with `salt='notebook-verification'`. Only after three PASS does the Notebook create `submission.zip`.

Definiert die SHA-256-Pins für alle 18 Dateien und sucht das Release-Dataset.

```python
# V24 / heliosli v95mxfu_mxf_ay3 / exact hash-pinned source components.
# Circuit creators and upstream licenses are credited in the release's CREDITS.md.
import os, sys, time, math, json, hashlib, shutil, zipfile, lzma, contextlib
from pathlib import Path
INPUT = Path(os.environ.get('QCC_INPUT_ROOT', '/kaggle/input'))
WORK = Path(os.environ.get('QCC_WORK_DIR', '/kaggle/working'))
WORK.mkdir(parents=True, exist_ok=True)
for old in ('submission.zip','fresh_summary.json'):
    (WORK/old).unlink(missing_ok=True)
SUB=WORK/'submission'
if SUB.exists(): shutil.rmtree(SUB)
SUB.mkdir(parents=True, exist_ok=True)
PINS=json.loads('{"dfthcsos/angle_k_0.kmb": {"bytes": 390615, "sha256": "d3aab7479fe3b8510e3af3797a14ec8d9bfa226d7aa7717ae4e93f496d2d9538", "stored_as": "dfthcsos__angle_k_0.kmb"}, "dfthcsos/angle_k_1.kmb": {"bytes": 381353, "sha256": "4595e5dcc982295db2520c8497219e1768757edf3aa9e706fa44b1716f996ed2", "stored_as": "dfthcsos__angle_k_1.kmb"}, "dfthcsos/angle_k_10.kmb": {"bytes": 340218, "sha256": "f28f2ead2b7eb3d45aadf4e0bb9f9399c7d8f016247d7020ae39dbd9c062cace", "stored_as": "dfthcsos__angle_k_10.kmb"}, "dfthcsos/angle_k_11.kmb": {"bytes": 337990, "sha256": "7b9094ddc215c6c7db223fe319e6d2a6f67c1669f412e4d3281c280723df5b81", "stored_as": "dfthcsos__angle_k_11.kmb"}, "dfthcsos/angle_k_12.kmb": {"bytes": 337720, "sha256": "d49dfbfdb8cff3c3d680e4ef65a3d1a01db7a2fc666f49a522d7f58f50305e78", "stored_as": "dfthcsos__angle_k_12.kmb"}, "dfthcsos/angle_k_13.kmb": {"bytes": 336880, "sha256": "cb7e48a7029323a6ec11c0f6dede5f5e0443f67da92e0e6554ff9120b8279efd", "stored_as": "dfthcsos__angle_k_13.kmb"}, "dfthcsos/angle_k_14.kmb": {"bytes": 336049, "sha256": "07fcdcb75d3a9e7f2573e057376ec20b7a56bf9a53fe7d7f00fb351614c2003f", "stored_as": "dfthcsos__angle_k_14.kmb"}, "dfthcsos/angle_k_2.kmb": {"bytes": 385773, "sha256": "77dec28c5ebffe723fb58717a31c017d66c44cbec220bc3cc5a15a2fff051aa3", "stored_as": "dfthcsos__angle_k_2.kmb"}, "dfthcsos/angle_k_3.kmb": {"bytes": 383561, "sha256": "8e137a014a1325450eaf9ec15bc824475b757b3a05bbc542eed9cccfd6b5ec53", "stored_as": "dfthcsos__angle_k_3.kmb"}, "dfthcsos/angle_k_4.kmb": {"bytes": 337382, "sha256": "d9f2a0d739142a1d20789352c617cccc702a8f0b4b17f91971e4e4ef3e6f6c3f", "stored_as": "dfthcsos__angle_k_4.kmb"}, "dfthcsos/angle_k_5.kmb": {"bytes": 338559, "sha256": "bd0886bb6c3d5c04f5e1fd29dbd2562d1c7e5b1a7406bc1abde6819093a0880e", "stored_as": "dfthcsos__angle_k_5.kmb"}, "dfthcsos/angle_k_6.kmb": {"bytes": 338608, "sha256": "12c0c6f92d708ff7d852f2c6f36a40ecf4369249fa1f0ab4527b08e0152e7558", "stored_as": "dfthcsos__angle_k_6.kmb"}, ...}')
EXPECTED_MANIFEST=json.loads('{"extras": [], "files": [{"bytes": 390615, "file": "dfthcsos/angle_k_0.kmb", "sha256": "d3aab7479fe3b8510e3af3797a14ec8d9bfa226d7aa7717ae4e93f496d2d9538", "stored_as": "dfthcsos__angle_k_0.kmb"}, ...]}')
EXPECTED_PORTFOLIO='v95mxfu_mxf_ay3'
SALT='notebook-verification'
REFERENCE=EXPECTED_MANIFEST['reference_costs']
assert EXPECTED_MANIFEST['portfolio']==EXPECTED_PORTFOLIO
assert EXPECTED_MANIFEST['salt']==SALT
EXPECTED_FILES=set(PINS)
MEMBERS=PINS
assert len(PINS)==18
assert EXPECTED_FILES==({'invsqrt.kmb','dqi.kmb','dfthcsos/submission.npz'} | {f'dfthcsos/angle_k_{i}.kmb' for i in range(15)})

def digest_stream(stream):
    h=hashlib.sha256(); n=0
    for b in iter(lambda:stream.read(4*1024*1024),b''):
        h.update(b); n+=len(b)
    return h.hexdigest(),n

def source_candidates():
    seen=set()
    hints=[os.environ.get('QCC_RELEASE_PATH'),
           '/kaggle/input/datasets/heliosli/qcc-circuits-live',
           '/kaggle/input/qcc-circuits-live']
    for raw in hints:
        if raw:
            p=Path(raw)
            if p.exists() and str(p) not in seen:
                seen.add(str(p));yield p
    for where,dirs,files in os.walk(INPUT):
        dirs[:]=[d for d in dirs if d not in ('kickmix','verifiers','sample_submission','.git')]
        p=Path(where)
        if 'QCC_RELEASE_MANIFEST.json' in files and str(p) not in seen:
            seen.add(str(p));yield p
        for filename in files:
            if filename.lower().endswith('.zip') and ('archive' in filename.lower() or 'helios' in filename.lower() or 'qcc' in filename.lower()):
                f=p/filename
                if str(f) not in seen:
                    seen.add(str(f));yield f

def read_manifest(candidate):
    if candidate.is_file():
        with zipfile.ZipFile(candidate) as z:
            if 'QCC_RELEASE_MANIFEST.json' not in z.namelist():raise ValueError('missing manifest')
            data=json.loads(z.read('QCC_RELEASE_MANIFEST.json'))
            available=set(z.namelist())
    else:
        data=json.loads((candidate/'QCC_RELEASE_MANIFEST.json').read_text(encoding='utf-8'))
        available={p.name for p in candidate.iterdir() if p.is_file()}
    if data!=EXPECTED_MANIFEST: raise ValueError('release manifest differs from pinned v95mxfu_mxf_ay3')
    if not {r['stored_as'] for r in PINS.values()}.issubset(available):
        raise ValueError('release member missing')
    return data

RELEASE=None;rejected=[]
for p in source_candidates():
    try:
        read_manifest(p);RELEASE=p;break
    except Exception as exc:
        rejected.append(f'{p}: {str(exc)[:130]}')
if RELEASE is None:
    print('Unavailable/mismatched release candidates:',*rejected[:8],sep='\n')
    raise RuntimeError('Attach heliosli QCC circuits live release v95mxfu_mxf_ay3 or archive (55).zip')
print('PINNED V24 RELEASE:',RELEASE)
print('Portfolio:',EXPECTED_PORTFOLIO,'18 members; compressed DQI will be verified after streaming extraction')
```

Staged 18 Dateien aus dem Release, streamt LZMA-DQI, auditiert SHA-256 der dekomprimierten Bytes.

```python
# Stage 18 files, streaming LZMA DQI and auditing SHA-256 of DECOMPRESSED bytes.
@contextlib.contextmanager
def read_release_member(archive, item):
    stored=item['stored_as']
    if archive is not None:
        with archive.open(stored) as raw:
            if stored.endswith('.xz'):
                with lzma.LZMAFile(raw,'rb') as source: yield source
            else: yield raw
    else:
        with (RELEASE/stored).open('rb') as raw:
            if stored.endswith('.xz'):
                with lzma.LZMAFile(raw,'rb') as source: yield source
            else: yield raw

archive=zipfile.ZipFile(RELEASE) if RELEASE.is_file() else None
try:
    for name in sorted(PINS):
        item=PINS[name]
        dst=SUB/name
        dst.parent.mkdir(parents=True,exist_ok=True)
        h=hashlib.sha256();n=0
        with read_release_member(archive,item) as f, dst.open('wb') as out:
            for buf in iter(lambda:f.read(4*1024*1024),b''):
                out.write(buf);h.update(buf);n+=len(buf)
        assert (h.hexdigest(),n)==(item['sha256'],item['bytes']),(name,h.hexdigest(),n)
        print('SHA PASS',name,item['sha256'][:16],n,flush=True)
finally:
    if archive is not None: archive.close()
assert len(list(SUB.rglob('*.kmb')))==17
assert (SUB/'dfthcsos/submission.npz').is_file()
print('✅ V24 selected 18/18 pinned members staged, including 892-qubit DQI')
```

Validiert die Chemistry-Array-Shape-Kontrakte (U, W, H2_I, angle_words, tree_edges).

```python
# Validate the V24 R8/B143/C44 Chemistry field and shape contract.
import numpy as np
with np.load(SUB/'dfthcsos/submission.npz',allow_pickle=False) as npz:
    required={'U','W','H2_I','H1_I','Hsym_lower','tree_edges','angle_words'}
    assert required.issubset(set(npz.files)),required-set(npz.files)
    shapes={k:npz[k].shape for k in ('U','W','H2_I','angle_words')}
    assert shapes=={'U':(8,143,76),'W':(8,143,44),'H2_I':(8,44),'angle_words':(1220,75)},shapes
    assert npz['tree_edges'].dtype.kind=='i'
    for k in ('U','W','H2_I','H1_I','Hsym_lower'):
        assert npz[k].dtype.kind=='f',(k,npz[k].dtype)
    chem_keys=tuple(sorted(npz.files))
print('✅ Chemistry array shape contract PASS:',shapes)
print('NPZ fields:',chem_keys)
print('Now run the three official unmodified task verifiers.')
```

Führt die drei offiziellen Verifier neu aus (CPU-intensiv!) und berechnet das geometrische Mittel.

```python
# Three NEW official V24 task verifications. This may be CPU-intensive on Kaggle.
import time
COMP=next((p for p in (
    Path('/kaggle/input/competitions/google-verifiable-quantum-circuit-compilation'),
    Path('/kaggle/input/google-verifiable-quantum-circuit-compilation'),
) if (p/'kickmix/kickmix.so').is_file() and (p/'verifiers').is_dir()),None)
if COMP is None:
    raise RuntimeError('Attach the official Google Quantum AI Competition Data')
assert sys.version_info[:2]==(3,13),'Kickmix requires the Kaggle Python 3.13 CPU environment'
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key]='1'
if hasattr(os,'sched_getaffinity'):
    allowed=sorted(os.sched_getaffinity(0))[:4]
    if allowed:os.sched_setaffinity(0,allowed)
sys.path[:0]=[str(COMP/'kickmix'),str(COMP/'verifiers')]
import kickmix as km
from invsqrt import verify_submission_invsqrt as vinv
from dqi import verify_submission_dqi as vdqi
from dfthcsos import verify as vchem
REPORTS={}
for task,func in (
    ('invsqrt',lambda:vinv.verify(km.Circuit.from_file(str(SUB/'invsqrt.kmb'),format='kmb'),vinv.ProblemSpecInvSqrt.for_n_p(10),salt=SALT)),
    ('dqi',lambda:vdqi.verify(km.Circuit.from_file(str(SUB/'dqi.kmb'),format='kmb'),vdqi.ProblemSpecDQI.benchmark_instance(),salt=SALT)),
    ('dfthcsos',lambda:vchem.verify(str(SUB/'dfthcsos'),salt=SALT)),
):
    started=time.monotonic()
    report=func()
    REPORTS[task]=report
    print(task,report['status'],'Q=',report['num_qubits'],'cost=',report['score'],'seconds=',round(time.monotonic()-started,1),flush=True)
    assert report['status']=='PASS',report
assert set(REPORTS)==set(REFERENCE)
RATIOS={t:REFERENCE[t]/float(REPORTS[t]['score']) for t in REFERENCE}
gm=math.prod(RATIOS.values())**(1/3)
print('✅ THREE FRESH OFFICIAL PASS',json.dumps(RATIOS,indent=2))
print(f'🏆 VERIFIED LOCAL GEOMETRIC MEAN: {gm:.12f}')
```

Packt die Submission erst nach 3×PASS; verifiziert die Member-Bytes erneut im fertigen ZIP.

```python
# Package only after 3 PASS. Verify member bytes again inside the finished zip.
assert len(REPORTS)==3 and all(REPORTS[t]['status']=='PASS' for t in REFERENCE)
OUTPUT_ZIP=WORK/'submission.zip'
with zipfile.ZipFile(OUTPUT_ZIP,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as out:
    for name in sorted(MEMBERS):
        out.write(SUB/name,name)
with zipfile.ZipFile(OUTPUT_ZIP) as reread:
    assert set(reread.namelist())==EXPECTED_FILES
    for name,row in MEMBERS.items():
        with reread.open(name) as file:sha,size=digest_stream(file)
        assert (sha,size)==(row['sha256'],row['bytes']),name
with OUTPUT_ZIP.open('rb') as f: zipsha,zipsize=digest_stream(f)
summary={'status':'FRESH_OFFICIAL_PASS','version':'V24',
         'source_author':'heliosli credited assembly / maoxin123 inverse / Kirill-Özer-line DQI / Syed and maoxin123 chemistry','source_url':'https://www.kaggle.com/code/heliosli/the-dataset-is-public-now-enjoy',
         'source_pins':PINS,'portfolio':EXPECTED_PORTFOLIO,
         'members':{name:row['sha256'] for name,row in MEMBERS.items()},
         'ratios':RATIOS,'local_gm':gm,'reports':REPORTS,
         'submission_sha256':zipsha,'submission_bytes':zipsize}
(WORK/'fresh_summary.json').write_text(json.dumps(summary,indent=2,default=str)+'\n',encoding='utf-8')
print('✅ ZIP READBACK PASS: 18/18, three official PASS')
print('🏆 VERIFIED LOCAL GEOMETRIC MEAN:',f'{gm:.12f}')
print('📦',OUTPUT_ZIP)
```

Finaler Statusbericht — verifiziert durch Ausführung der offiziellen Verifier in diesem Run.

```python
# Final status — verified by executing the official task verifiers in THIS run.
print('🏆 V24 · heliosli credited portfolio · v95mxfu_mxf_ay3')
for task in ('invsqrt','dqi','dfthcsos'):
    r=REPORTS[task]
    print(f'{task:9s} PASS Q={r["num_qubits"]:4d} ratio={RATIOS[task]:.9f} cost={r["score"]:.8g}')
print(f'🏆 VERIFIED LOCAL GEOMETRIC MEAN: {gm:.12f}')
print('📦 Submission:',WORK/'submission.zip')
print('The Kaggle Public Leaderboard score is determined by Kaggle separately.')
```

---

## 17 · 📊 Resource invoice — what Google actually charges us

The final comparison below is calculated **only from V24's freshly executed official verifier outputs**. A matching SHA-256 is an identity check, *not* a scientific PASS; author measurements are distinct from our fresh verification, and Kaggle Public Score is distinct from both. The historical educational charts above use Google reference inputs by design.

Zeigt die frischen Verifier-Ergebnisse als Tabelle und Balkendiagramm.

```python
benchmarks = [('Inverse square root','invsqrt'), ('DQI decoder','dqi'), ('FeMoCo chemistry','dfthcsos')]
scoreboard = pd.DataFrame([{
    'Task': label,
    'Qubits': int(REPORTS[task]['num_qubits']),
    'Verified cost': float(REPORTS[task]['score']),
    'Reference / cost': REFERENCE[task] / float(REPORTS[task]['score']),
    'Official status': REPORTS[task]['status'],
} for label, task in benchmarks])
assert set(scoreboard['Official status']) == {'PASS'}
display(scoreboard.style.hide(axis='index').format({
    'Verified cost': '{:,.4f}', 'Reference / cost':'{:.4f}×'
}))
fig = px.bar(scoreboard, x='Task', y='Reference / cost', color='Task',
             text='Reference / cost', title='Fresh verifier results: how much each task improves on Google's reference')
fig.update_traces(texttemplate='%{text:.3f}×', textposition='outside')
finish(fig, height=450).show()
print(f'🏆 VERIFIED LOCAL GEOMETRIC MEAN: {gm:.12f}')
print(f'📦 Submission: {WORK / "submission.zip"}')
print('The Kaggle Public Leaderboard score is determined by Kaggle separately.')
```

---

<a id="credits"></a>
# 🙏 Credits — All the researchers behind the 25× frontier

**V24 is an educational Notebook designed for independent verification of a credited public portfolio.** Our original work is the Deep EDA, the Factory / City / Michelin Kitchen Stories, quantum-resource visualizations, historical experiments, mathematical analogies and the independent SHA-pinned three-task verification. We do **not** claim upstream circuit design as our own.

**Special credit to [heliosli](https://www.kaggle.com/heliosli)** for sharing the [public release Notebook](https://www.kaggle.com/code/heliosli/the-dataset-is-public-now-enjoy) and [QCC circuits live Dataset](https://www.kaggle.com/datasets/heliosli/qcc-circuits-live), which combines and verifies publicly credited components. This V24 reproduces the exact release `v95mxfu_mxf_ay3`.

### Component-level attribution

- **Inverse-square-root:** [maoxin123](https://www.kaggle.com/code/maoxin123/lb-25-14-public-frontier-refit-chem-weights), building on [Hosen42](https://www.kaggle.com/code/hosen42/vqcc-our-submission), with the earlier work of [Ahmed Berat Özer](https://www.kaggle.com/code/ozertuu/25-137-starter-notebook), [Atakan Aldemir](https://www.kaggle.com/code/atakanaldemir/qcc-early-measurement-and-domain-aware-inverse), [Kirill Tymchishin](https://www.kaggle.com/code/kirilltym/quantum-circuits-pi-gauge-weight-refinement), Maoxin, Syed Asad Ali, mrmeows, busyaprime and yoyobar.
- **DQI decoder:** heliosli's update of a public decoder from [Kirill Tymchishin](https://www.kaggle.com/code/kirilltym/quantum-circuits-pi-gauge-weight-refinement), developed through [Ahmed Berat Özer](https://www.kaggle.com/datasets/ahmedberatozer/vqcc-v23-portfolio), [Atakan Aldemir](https://www.kaggle.com/datasets/atakanaldemir/qcc-c44-five-helper-release-sources/versions/1), [daifanhao / MAIDANG](https://www.kaggle.com/code/daifanhao/lb-24-94096-c44-and-exact-dqi-product-reuse), [Syed Asad Ali](https://www.kaggle.com/code/syed3000/vqcc-own-circuit-portfolio-notebook), SomeJoint, jday96314, Ali Haydar Özdağ and other contributors named below.
- **FeMoCo Chemistry:** [Syed Asad Ali](https://www.kaggle.com/code/syed3000/vqcc-own-circuit-portfolio-notebook)'s R8/B143/C44 words and 15 loaders, with [maoxin123](https://www.kaggle.com/code/maoxin123/lb-25-14-public-frontier-refit-chem-weights)'s version-3 W and H2_I refit. Based on [Lera / marculera](https://www.kaggle.com/code/marculera/df-thc-10x-compact-groups-from-the-hamiltonian)'s compact-group DF-THC pipeline, progressive rounding, QROM and other sources documented below.
- **Previous V22 portfolio:** [samanyu1808](https://www.kaggle.com/samanyu1808) contributed the credited, SHA-pinned [Syed release assembly](https://www.kaggle.com/code/samanyu1808/credited-public-portfolio-syed-release) used in our [published V22](https://www.kaggle.com/code/evgendvorkin/google-quantum-ai-deep-eda-with-analogies?scriptVersionId=366600651). This is a historical project checkpoint, distinct from the V24 source.
- **Organizers:** Google Quantum AI / Qualtran — benchmark contracts, official verifiers and reference cost models.

### Full original V24 release credits (preserved)

*First-person claims below belong to heliosli and cited upstream authors, not to this educational Notebook.*

# Sources and credits

- **invsqrt** — the 62-qubit file 1c5b1ee2 shipped in maoxin123's notebook https://www.kaggle.com/code/maoxin123/lb-25-14-public-frontier-refit-chem-weights (version 3; their code
  Apache-2.0, each circuit keeps its authors' terms), byte for byte: their combination of Hosen42's version-6 edit
  (https://www.kaggle.com/code/hosen42/vqcc-our-submission) with their own edit (made with ChatGPT's help, as credited there), on the file 13b5bf7a shipped in
  ozertuu's notebook https://www.kaggle.com/code/ozertuu/25-137-starter-notebook (version 15), which combines Atakan Aldemir's (atakanaldemir) edit from https://www.kaggle.com/code/atakanaldemir/qcc-early-measurement-and-domain-aware-inverse (version 2)
  with the file 29505732 shipped in kirilltym's (Kirill Tymchishin) notebook https://www.kaggle.com/code/kirilltym/quantum-circuits-pi-gauge-weight-refinement (version 22), on the public
  invsqrt lineage (Hosen42's measure-first rewrites, syed3000 (Syed Asad Ali), mrmeows (team selenium), busyaprime
  (Akmal Xodarev), yoyobar), as credited there.

- **dqi** — our update of the 892-qubit decoder 337cb049 shipped in kirilltym's (Kirill Tymchishin) notebook
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
  The table weights (W, H2_I) in this version are maoxin123's version-3 weights fd4d4d00, byte for byte, from
  https://www.kaggle.com/code/maoxin123/lb-25-14-public-frontier-refit-chem-weights (version 3; Apache-2.0), on the lineage credited there.
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

**Licenses:** this release retains `LICENSE.md`; source-authored code is Apache-2.0 where stated, while each imported circuit retains its original terms.

---

## 🚀 Next laboratory · Beyond 25× with our own compiler

Our **private Astra Quantum Architecture Lab** found a historical, source-level DQI phase correction reducing a subblock from **56 to 40 static Toffoli-like** at 64Q, with matched functional and phase tests. This is **not yet an improvement of the modern 892-qubit decoder**, and it is deliberately not part of the assembled V24.

Our next experiments focus on the editable generator: rebuild a verified modern circuit from source, identify repeated non-linear work, modify the synthesis/scheduling code, check value and phase correctness and clean ancilla, then measure actual Q/T/error and re-run official verifiers. The long-term plan is a private, multi-author **Quantum Evolution Lab** tracing each historical Dataset version, not just the strongest final portfolio.

**Educational takeaway:** source → circuit → exact correctness → resource invoice → validated Score. A copied circuit gets us a baseline; understanding and improving the generator is how we create our own result.

---

## 📝 Lern-Notizen (füll das selbst aus)

- [ ] Konzept 1 verstanden: Drei Analogien — Fabrik (Gate-Zählung ≠ Kosten), Stadt (Qubit-Wiederverwendung via Uncomputation), Küche (Validität > Billigkeit)
- [ ] Konzept 2 verstanden: Kostenfunktionen — invsqrt: Q×C (linear in Qubits), dqi: R(ε₊)·Q²·T (quadratisch in Qubits!), dfthcsos: λ_eff·T_total·Q_total
- [ ] Konzept 3 verstanden: Geometrisches Mittel — ein einzelner 2×-Gewinn bei einem Task hebt den Gesamtscore um 2^(1/3) ≈ 1.26×; alle drei 2× → 2.0×
- [ ] Konzept 4 verstanden: Experiment-Ledger — Fehlschläge (SVD-Truncation, Bit-Truncation) sind dokumentiert, weil sie zeigen, warum naive Optimierungen nicht funktionieren
- [ ] Konzept 5 verstanden: SHA-256-Pinning — jede der 18 Dateien hat eine feste Prüfsumme; ein Byte-Unterschied bricht die Verifizierung
- [ ] Eigener Test: Warum ist DQI der stärkste Hebel (Ratio 65×)? → Weil Q² in der Kostenfunktion ist: weniger Qubits haben quadratischen Effekt
- [ ] Frage die ich noch habe: Wie genau funktioniert die „lattice-aware rounding" in der DF-THC-Pipeline? Was bedeutet „lattice" in diesem Kontext?
