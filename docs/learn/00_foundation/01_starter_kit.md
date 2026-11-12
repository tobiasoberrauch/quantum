# dfthcsos starter: rebuild, verify and submit

> **Lernziel:** Du verstehst den kompletten Workflow einer `dfthcsos`-Submission: Präzision der Winkel testen, Circuits mit Qualtran neu bauen, mit dem offiziellen Verifier scoren und eine gültige `submission.zip` paketieren.
> **Dauer:** ~15 Minuten lesen
> **Quelle:** sohier | https://www.kaggle.com/code/sohier/verifiable-circuit-compilation-starter | 77 votes
> **Wichtigste Konzepte:**
> - `brot`-Präzision: wie viele Bits die Winkel brauchen, damit die Hamiltonian-Rekonstruktion ≤ 20 mHa bleibt
> - `batch-size` (J): Trade-off zwischen Circuit-Breite und Anzahl an ANGLE-Circuits (Limit: 128 Qubits pro Circuit)
> - Offizieller Verifier: `verify.py` simuliert die Circuits und gibt `cost` zurück (lower = better)
> - Submission-Format: ZIP mit `invsqrt.kmb`, `dqi.kmb` und `dfthcsos/`-Ordner (`angle_k_*.kmx` + `submission.npz`)
> - Leaderboard-Score: geometrisches Mittel aus `reference_cost / your_cost` über alle 3 Tasks

---

This notebook walks through one full loop on the `dfthcsos` task with the dfthcsos starter kit:

1. explore how much angle precision the reference factorization needs,
2. rebuild the ANGLE circuits with a small change (a toy edit),
3. score the result with the competition's own verifier, next to the reference submission's circuits,
4. package a complete submission: your new `dfthcsos/` folder plus the sample `invsqrt` and `dqi` circuits.

It takes about 10 minutes on a CPU session and needs internet access, to install Qualtran.

## Setup

The notebook mounts the competition data and the starter kit dataset. Qualtran, which the starter kit uses to build its circuits, is installed below.

- `verifiers/`: the problem spec, the verifier for each task, with `dfthcsos`'s inputs (`FeMoCo76o113e.fcidump` and the fixed symmetry shifts),
- the starter kit dataset's `starter_kit/`: the dfthcsos starter kit,
- `kickmix/`: `kickmix.so`, the circuit simulator, built for this notebook image.

Everything runs straight from the read-only data; only the final `submission.zip` is written to `/kaggle/working`.

Setup: installs Qualtran (pinned commit) from GitHub.

```python
%pip install -q "qualtran @ git+https://github.com/quantumlib/Qualtran.git@c58703d00b01c346d3e77d3913cf2d6e9e556be3"
```

Pfad-Konfiguration und Import von kickmix sowie Verifier-Pfaden.

```python
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

COMPETITION = Path('/kaggle/input/competitions/google-verifiable-quantum-circuit-compilation')
VERIFIERS = COMPETITION / 'verifiers'
# The starter kit dataset; found rather than hard-coded, as where Kaggle mounts an attached dataset varies.
KIT = next(Path('/kaggle/input').glob('**/starter_kit/starter')).parent
KICKMIX = COMPETITION / 'kickmix'
BUILD = Path('/tmp/dfthcsos_J7')  # the toy edit's circuits

# kickmix, the verifiers (dfthcsos, dqi, invsqrt) and the starter kit (dfthc, starter, verifier),
# for this kernel and for the scripts run below.
paths = [str(KICKMIX), str(VERIFIERS), str(KIT)]
sys.path[:0] = paths
os.environ['PYTHONPATH'] = os.pathsep.join([*paths, os.environ.get('PYTHONPATH', '')])

import kickmix

print('kickmix loaded from', kickmix.__file__)
print('starter kit at', KIT)
```

## 1. How much precision do the angles need?

The verifier rotates each vector with angles stored as `brot`-bit words. Fewer bits mean narrower circuits, but the
rounded words must still reproduce the Hamiltonian within 20 mHa. The kit's `encode.py` scores the reference
factorization at several precisions without building any circuits:

Testet die Referenz-Faktorisierung bei brot=11, 12, 13 und zeigt, ab wann der Fehler ≤ 20 mHa bleibt.

```bash
!python {KIT}/starter/task2_angles/encode.py FeMoCo76o113e --tree log_depth --rounding nearest --brots 11 12 13
```

At `brot = 11` the two-body error (`error_2`) exceeds 20 mHa, so the score is `inf`: 12 bits is the least this
factorization can use. Reaching lower precision means changing the factorization itself (Part 1 of the kit).

## 2. Rebuild the circuits with a toy edit

Each ANGLE circuit loads a batch of `J` angle words, so its width is about `J * brot` qubits plus the address and some
workspace, and every circuit must fit in 128 qubits. The reference submission uses `J = 8`; at `brot = 12`, `J = 9`
would need 131 qubits and be rejected. As a toy edit we use `J = 7`: narrower circuits, but one more of them.

The kit's `build_circuits.py` builds the family with Qualtran QROMs, simulates it on every address before writing
anything, and reports its score. It takes about 6 minutes:

Baut die ANGLE-Circuits mit batch-size=7 und brot=12 neu (ca. 6 Min).

```bash
!python {KIT}/starter/task3_circuits/build_circuits.py FeMoCo76o113e --tree log_depth --brot 12 --batch-size 7 --output {BUILD}
```

## 3. Score it with the competition's verifier

`verifiers/dfthcsos/verify.py` is the verifier the leaderboard uses, here without the secret salt, so its simulated
shots differ from the leaderboard's. We score the toy edit and, for comparison, the reference circuits in the
sample submission. Lower cost is better.

Führt den offiziellen dfthcsos-Verifier auf dem Toy-Edit und der Referenz aus und vergleicht die Kosten.

```python
def dfthcsos_cost(circuits: Path) -> float:
    """The competition verifier's dfthcsos cost for a folder of angle_k_* circuits and submission.npz."""
    # verify.py exits 1 when it rejects a submission; its JSON says why, which is raised below.
    result = subprocess.run([sys.executable, str(VERIFIERS / 'dfthcsos' / 'verify.py'), str(circuits)], capture_output=True, text=True, check=False)
    summary = json.loads(result.stdout)
    if summary.get('status') != 'PASS':
        raise RuntimeError(summary)
    return summary['score']


reference = dfthcsos_cost(COMPETITION / 'sample_submission' / 'dfthcsos')
toy_edit = dfthcsos_cost(BUILD)
print(f'reference: {reference:.4g}   toy edit: {toy_edit:.4g}   ratio: {reference / toy_edit:.4f}')
```

The leaderboard score is the geometric mean, over the three tasks, of the reference cost divided by yours. With the
sample circuits for `invsqrt` and `dqi` (a ratio of 1 each), this submission would score about:

Berechnet den erwarteten Leaderboard-Score (geometrisches Mittel über 3 Tasks).

```python
print(f'{(reference / toy_edit) ** (1 / 3):.4f}')
```

The toy edit is valid but slightly worse than the reference: the extra circuit costs more Toffolis than the narrower
word registers save.

## 4. Package a submission

A submission is a zip of `invsqrt.kmb` (or `.kmx`), `dqi.kmb` (or `.kmx`) and a `dfthcsos/` folder holding
`angle_k_0` ... `angle_k_<n-1>` and `submission.npz`. Here the `dfthcsos/` folder is the toy edit's:

Packt die Sample-Circuits für invsqrt/dqi plus den Toy-Edit für dfthcsos in `submission.zip`.

```python
sample = COMPETITION / 'sample_submission'
with zipfile.ZipFile('/kaggle/working/submission.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    for name in ['invsqrt.kmb', 'dqi.kmb']:
        archive.write(sample / name, name)
    circuits = sorted(BUILD.glob('angle_k_*.kmx'), key=lambda path: int(path.stem.removeprefix('angle_k_')))
    for path in [*circuits, BUILD / 'submission.npz']:
        archive.write(path, f'dfthcsos/{path.name}')
print(*zipfile.ZipFile('/kaggle/working/submission.zip').namelist(), sep='\n')
```

## Where to go from here

- **Part 1, factorization:** `starter/task1_factorization/train_df_thc_qaggle.py` trains a new factorization, seeded
  from a baseline. The verifier fixes the symmetry shift to the baseline's and requires the LCU normalization
  `Lambda > 49.0` and the SOS gap `E_gap > 3.914898` Ha (the baseline's are 308.46 and 3.965). The score's
  `lambda_eff` (49.30 for the baseline) has no floor of its own, so a smaller `Lambda` pays, as do factorization
  sizes `R, B, C` and precision that make the circuits cheaper.
- **Part 2, tree and precision:** `starter/task2_angles/` has the path and log-depth Givens trees and the rounding
  options.
- **Part 3, circuits:** the baseline loads each batch with an ordinary QROM. Any construction is allowed as long as the
  simulated circuits load the submitted words; `verifiers/dfthcsos/SCORING_README.md` has the full contract.
- **The other tasks:** `verifiers/invsqrt/` and `verifiers/dqi/` each have a reference-circuit script that writes
  the sample circuits, a starting point for your own.

---

## 📝 Lern-Notizen (füll das selbst aus)

- [ ] Konzept 1 verstanden: `brot`-Präzision — ab 12 Bits bleibt die Hamiltonian-Rekonstruktion ≤ 20 mHa; weniger Bits = breitere Circuits nötig
- [ ] Konzept 2 verstanden: `batch-size` J — bestimmt Circuit-Breite (~J×brot Qubits); Limit 128 Qubits; J=7 → mehr Circuits, aber schmaler
- [ ] Konzept 3 verstanden: Verifier-Workflow — `verify.py` simuliert auf Test-Inputs, gibt `cost` zurück; Leaderboard = geo. Mittel aus ref/cost
- [ ] Konzept 4 verstanden: Submission-Format — ZIP mit invsqrt.kmb, dqi.kmb, dfthcsos/ (angle_k_*.kmx + submission.npz)
- [ ] Eigener Test: Was passiert, wenn ich brot=11 verwende? (Antwort: error_2 > 20 mHa → Score = inf → Rejection)
- [ ] Frage die ich noch habe: Wie genau beeinflusst die Wahl des Givens-Trees (path vs. log_depth) die Circuit-Kosten?
