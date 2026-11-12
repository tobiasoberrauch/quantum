# LB 24.73387 | Top 30 QCC Notebooks, Re-Verified

> **Lernziel:** Das komplette DQI-Handwerk aus einer Top-30-Referenz: wie man mit *exact product caching* (R41) Toffolis spart, warum der **Q²-Faktor** die Qubit-Zahl so dominant macht, und wie die *Failure-Penalty* R(k) über den Leaderboard-Score entscheidet.
> **Dauer:** ~45 Minuten lesen
> **Quelle:** Akmal Xodarev (busyaprime) | 51 votes (V17; diese Datei ist V18)
> **Technik:** Product Caching (R41) + Failure Penalty + Qubit Floor
> **Level:** Fortgeschritten

---

**Leaderboard 24.73387** (Public split): our submission 58003999 of these exact bytes, 5 November 00:42 UTC, equal to its k 0 prediction 24.733872, truncated. **The hosts' metric, run below on Kaggle's CPU** with their own metric code: **24.73387** at our salt A and **24.73386** at our salt B (our salts; the hosts' are secret). The DQI file fails 0 of its 102,400 test shots at salt A and 0 at salt B; on the leaderboard's Public salt it failed 0 in all 9 of our submissions that carry it (section 3; one failed shot would cost 0.153% of the score).

**What is ours: two pieces, both in this zip.**
1. `dqi.kmb` (fd0ef09e), our exact product caching (R41) on yoyobar's 891-qubit file 993c7038, **13.816 Toffolis fewer per shot** (mean of 3 paired seeds: -13.6, -14.1, -13.7; failed shots member / base 1 / 1 in 307,200).
2. The **W and H2_I arrays of `dfthcsos/submission.npz`**: our refit at fixed words and circuits (R55, our R53 method): descent along the constraint surface with exact restoration, error_1, error_2 and E_gap each held 2.002e-7 Ha inside its gate; the 15 angle files and the other five npz arrays are byte-identical to HW-19's. On manwithacat's HW-19 it takes lambda_eff from 47.019778 to 46.944209 and the chemistry cost **0.16072%** lower (306,723,130.32 to 306,230,171.25). **On the leaderboard:** our 58002211, the same files with HW-19's own weights, read 24.72061; this zip reads 24.73387 (+0.01326). The idea of refitting the weights up to the error gates is not ours: heliosli showed it publicly first, as Syed Asad Ali credits, and manwithacat's HW-03 holds the gates as constraints with a step back onto them. The code and this run are ours.

Also ours: the price list of the field (section 2), the lesson on failed DQI shots (section 3) and the rewrite history (section 4). **What is credited, unchanged:** `invsqrt.kmb` (af469847), SomeJoint's version 34 circuit on a chain that runs from mrmeows through Alex Chilton, qiuqiuh and Kirill Tymchishin. The 15 angle files are manwithacat's HW-19 (Hedge Wizardry version 23): `angle_k_0..3` as Syed Asad Ali's own-circuit portfolio V3 shipped them, `angle_k_4..14` re-planned by HW-19 with qwertykeypadapple's kernel search and Lera's emitter. The npz's other five arrays are Syed Asad Ali's V3 (his own (8, 143, 45) table in Lera's layout), which HW-19 carries unchanged; our weights start from his. Every name is in section 6.

| task | file (SHA-256) | written by | qubits | Toffolis per shot (unsalted) | cost at salt A / salt B (hosts' metric) | Google's reference cost | reference / cost |
|---|---|---|---:|---:|---:|---:|---:|
| invsqrt | `af469847` | SomeJoint V34, on Alex Chilton's, qiuqiuh's and Kirill Tymchishin's edits | 62 | 1,281.66 | 97,921.58 / 97,921.70 | 2,076,774.23 | **21.2085** |
| DQI | `fd0ef09e` | **ours** (R41) on yoyobar's 993c7038, on Syed Asad Ali's decoder | 891 | 396,904.56 | 3.753601e+11 (k 0) / 3.753602e+11 (k 0) | 2.443946e+13 | **65.109 / 65.109** |
| chemistry | 15 angle files + npz `3d51e969` | angle files manwithacat's HW-19 (0 to 3 Syed Asad Ali's); npz arrays Syed Asad Ali V3; **W and H2_I ours (R55)** | 427 | 15,277 | 306,230,171.25 on both | 3,355,599,588.32 | **10.9578** |

The score is the geometric mean of the three ratios. **The Code tab at 02:46 UTC on 5 November** (Kaggle CLI, score order) opens with yoyobar's 62-qubit invsqrt notebook (version 30, page score 24.72074), Kirill Tymchishin's Quantum Compilation 19 (version 5, 24.72062) and manwithacat's Hedge Wizardry (version 23, 24.72025); page scores read at 02:47 UTC. None of the first five current page scores reads above this zip's 24.73387. In our watcher's 01:00 UTC pass the cheapest public chemistry is 21d6f276 (Kirill Tymchishin's version 5: HW-19's angle files with Isabe11aM00re V4's npz 8bf7a9d1), 306,711,859.83 on our verifier, 0.157% above ours; this `invsqrt.kmb` is the cheapest public invsqrt and 993c7038 the cheapest public DQI, which our rewrite replaces (prices in section 2). The cells below draw the field and the failure ladder, copy the 18 files from the dataset by SHA-256, write `/kaggle/working/submission.zip`, unpack it and run the hosts' metric on it at both salts (about 30 minutes on Kaggle's CPU).

```python
# Code-Zelle 1: Zeichnet das Feld (Top-30 der Code-Seite) und die DQI-Failure-Ladder.
# Kern: R(k) = Wiederholungs-Faktor des Verifiers (Clopper-Pearson-Grenze); ein fehlgeschlagener
# Shot kostet über die Kubikwurzel im Score 0.153%. S0 ist der Score bei k=0.
import math, sys
from pathlib import Path
import matplotlib.pyplot as plt

COMP = next(p for p in (Path('/kaggle/input/competitions/google-verifiable-quantum-circuit-compilation'),
                        Path('/kaggle/input/google-verifiable-quantum-circuit-compilation')) if (p / 'verifiers').is_dir())
sys.path += [str(COMP / 'kickmix'), str(COMP / 'verifiers')]
from dqi import verify_submission_dqi as vdqi

# Code tab top 30 (score order, CLI 01:19 UTC, 5 November) with the score each page showed (01:19-01:20 UTC):
# (owner, score, 'page' = the current version's score | 'best' = an earlier version's best | 'ours' = our previous version)
PAGES = [('kirilltym/quantum-compilat', 24.72062, 'page'), ('manwithacat/vqcc-hedge-wizar', 24.72025, 'page'), ('isabe11am00re/qcc-v66s33w-subm', 24.69693, 'page'), ('prvsiyan', 24.69663, 'page'), ('syed3000/vqcc-own-circuit', 24.6725, 'page'), ('busyaprime (ours, version 17)', 24.65425, 'ours'), ('leoprovorov/full-xor-chemist', 24.65395, 'best'), ('somejoint', 24.65393, 'page'), ('manwithacat/the-real-150k-wa', 24.65389, 'best'), ('qwertykeypadapple', 24.65388, 'page'), ('kalidenaiarys', 24.59425, 'page'), ('evgendvorkin', 24.5942, 'page'), ('alexchilton', 24.5942, 'page'), ('nilanjansaha123', 24.5942, 'page'), ('kirilltym/quantum-circuits', 24.59418, 'page'), ('isabe11am00re/qcc-v65wqq-submi', 24.57994, 'page'), ('yoyobar', 24.56851, 'best'), ('ayodejiibrahimlateef', 24.56307, 'best'), ('qiuqiuh/qcc-refresh-v65w', 24.56203, 'page'), ('heliosli/the-dataset-is-p', 24.54651, 'best'), ('orecord', 24.53786, 'page'), ('kawh1111', 24.52648, 'page'), ('qiuqiuh/qcc-refresh-v64y', 24.52648, 'page'), ('isabe11am00re/qcc-v58x-submiss', 24.50462, 'page'), ('leoprovorov/but-some-q-squar', 24.4959, 'page'), ('ahoirg', 24.49359, 'page'), ('syed3000/vqcc-24-43-portf', 24.47034, 'page'), ('heliosli/quantum-ai-v1', 24.43253, 'page'), ('nicks037', 24.43253, 'page'), ('dmitriigluzdov', 24.34924, 'page')]
N = vdqi.DEFAULT_NUM_SHOTS
R = [vdqi.repetition_overhead(vdqi.clopper_pearson_upper_bound(k, N, log2_delta=vdqi.DEFAULT_LOG2_DELTA)) for k in range(5)]
S0 = 24.733864202506382  # hosts' metric of these files at salt B, where the DQI file fails 0 shots (re-measured below)
SALTS = {'salt A': (0, 24.733878001387986), 'salt B': (0, 24.733864202506382)}  # (DQI failed shots k, hosts' metric), re-measured below
ladder = [S0 * (R[0] / r) ** (1 / 3) for r in R]
trunc = lambda x: f'{math.floor(x * 1e5) / 1e5:.5f}'  # the leaderboard truncates to 5 decimals
print('repetition factor R(k):', ', '.join(f'{r:.6f}' for r in R))
print('score of these files when the DQI file fails k shots:', ', '.join(f'k {k}: {trunc(s)}' for k, s in enumerate(ladder)))
print(f'one failed shot: {100 * (ladder[1] / ladder[0] - 1):.3f}% on the score')

fig, (a, b) = plt.subplots(1, 2, figsize=(14, 6.5), gridspec_kw={'width_ratios': [1.3, 1]})
pages = sorted(PAGES, key=lambda p: p[1])
a.barh(range(len(pages)), [p[1] - 24.3 for p in pages], left=24.3,
       color=['#7f7f7f' if p[2] == 'ours' else '#9ecae1' if p[2] == 'best' else '#3182bd' for p in pages])
a.axvline(S0, color='#d62728', lw=2, ls='--', label='these 18 files, hosts\' metric at k 0')
a.set_yticks(range(len(pages)), [p[0] for p in pages], fontsize=7)
a.set_xlim(24.3, 24.78)
a.set_xlabel('Public Score on each page: current version (dark), best of an earlier version (light), ours (grey)')
a.set_title('Code tab top 30 at 01:19 UTC, 5 November (page data 01:19-01:20 UTC)', fontsize=10)
a.legend(fontsize=8, loc='lower right')
ks = list(range(len(ladder)))
b.plot(ks, ladder, 'o-', color='#3182bd', label='these 18 files, score at DQI failures k')
at_k = {}
for name, (k, s) in SALTS.items():  # one label per k, so salts with the same k do not print over each other
    b.scatter([k], [s], marker='x', s=90, color='black', zorder=4)
    at_k.setdefault(k, []).append((name, s))
for k, pts in at_k.items():
    b.annotate(f"hosts' metric here, {' and '.join(n for n, _ in pts)} (k {k})", (k, max(s for _, s in pts)),
               textcoords='offset points', xytext=(10, -14), fontsize=8)
b.set_xticks(ks)
b.set_xlabel('failed DQI shots k among 102,400 (set by the salt)')
b.set_ylabel('score')
b.set_title(f'Same bytes, different salt: one failed shot costs {100 * (1 - ladder[1] / ladder[0]):.3f}%', fontsize=10)
b.legend(fontsize=8, loc='upper right')
plt.tight_layout()
plt.show()
```

```python
# Code-Zelle 2: Schreibt submission.zip aus den 18 Dateien des Datasets, jede per SHA-256 geprüft.
# LEHRT DIE VERIFIKATIONSKULTUR: jeder Eintrag wird gegen seinen Hash abgeglichen, das Zip wird
# neu entpackt und nochmal hashgeprüft. SUBZIP ist der SHA-256 unserer echten Submission 58003999.
import hashlib, os, shutil, zipfile, zlib
INPUT, WORKING, TMP = Path('/kaggle/input'), Path('/kaggle/working'), Path('/tmp/qcc_v18')
DS = next(p.parent for p in INPUT.rglob('SHA256SUMS') if (p.parent / 'dqi.kmb').is_file())
FILES = [["invsqrt.kmb", "invsqrt.kmb", "af4698478fbad775a5a271690cf4c2d8783caf0b8d12048106d1973c4ac6862e", [1980, 1, 1, 0, 0, 0]], ["dqi.kmb", "dqi.kmb", "fd0ef09efd45f9f772e2c83100c3ccf8f93332057b1814a69f1dc56c9851df9e", [1980, 1, 1, 0, 0, 0]], ["dfthcsos__angle_k_0.kmb", "dfthcsos/angle_k_0.kmb", "5d47e1ff09ccea81b8c10c0dd0c6250eb70f71ac0c6100ae5f0571310c827baf", [1980, 1, 1, 0, 0, 0]], ["dfthcsos__angle_k_1.kmb", "dfthcsos/angle_k_1.kmb", "ef9ae7ce12753019a64168c39c5e5f8472b8aaaf69155b3ae4b0fd27e48eb34c", [1980, 1, 1, 0, 0, 0]], ["dfthcsos__angle_k_10.kmb", "dfthcsos/angle_k_10.kmb", "645c128b8c45d7b5f06c0099d4babbd7219826b21d7ea73b322fe05f427adcf6", [1980, 1, 1, 0, 0, 0]], ["dfthcsos__angle_k_11.kmb", "dfthcsos/angle_k_11.kmb", "2c61b5b57f45f31a3acc36fec6ecc6d0b736df47c05a3a8b1996882c55a203e6", [1980, 1, 1, 0, 0, 0]], ["dfthcsos__angle_k_12.kmb", "dfthcsos/angle_k_12.kmb", "057330142df58290a6bb889fa4df4db1d7066bb3447472d4ec1febbe0092018a", [1980, 1, 1, 0, 0, 0]], ["dfthcsos__angle_k_13.kmb", "dfthcsos/angle_k_13.kmb", "76ca65a2cfc737ef522268db380332e8d770296d4071d808404e2f10ad11b973", [1980, 1, 1, 0, 0, 0]], ["dfthcsos__angle_k_14.kmb", "dfthcsos/angle_k_14.kmb", "73be0ea411a2a1de24d339896b61c1704eafa10438c271fc5841b749c7f39ea0", [1980, 1, 1, 0, 0, 0]], ["dfthcsos__angle_k_2.kmb", "dfthcsos/angle_k_2.kmb", "eafd7cb6184e656e2f83f02397bde356b04edaaf6e9368a1f6bc0b9b005963b0", [1980, 1, 1, 0, 0, 0]], ["dfthcsos__angle_k_3.kmb", "dfthcsos/angle_k_3.kmb", "febdecb860bba9baa00670c29673f257b563e04263bcf8feec54d0a7788a96a5", [1980, 1, 1, 0, 0, 0]], ["dfthcsos__angle_k_4.kmb", "dfthcsos/angle_k_4.kmb", "547894a42290b9200b93aa7b8adb5bd1aaa1af1dd5a52bcdb663a90a03aaa45c", [1980, 1, 1, 0, 0, 0]], ["dfthcsos__angle_k_5.kmb", "dfthcsos/angle_k_5.kmb", "656fbbf0a1ad9618178bec29c3e140c040d6c42fa0e313dd6db832c694ca056a", [1980, 1, 1, 0, 0, 0]], ["dfthcsos__angle_k_6.kmb", "dfthcsos/angle_k_6.kmb", "81c21629b97020b44da54b97dcdcc5ceacb0f4f645946ebe7f9a7f910a93462c", [1980, 1, 1, 0, 0, 0]], ["dfthcsos__angle_k_7.kmb", "dfthcsos/angle_k_7.kmb", "…", [1980, 1, 1, 0, 0, 0]], ["dfthcsos__angle_k_8.kmb", "dfthcsos/angle_k_8.kmb", "…", [1980, 1, 1, 0, 0, 0]], ["dfthcsos__angle_k_9.kmb", "dfthcsos/angle_k_9.kmb", "…", [1980, 1, 1, 0, 0, 0]], ["dfthcsos__submission.npz", "dfthcsos/submission.npz", "3d51e969…", [1980, 1, 1, 0, 0, 0]]]
SUBZIP = '764ce65a643484f6db2f3fdf951fa0e512898ddaee53f6d9829dfd015b64e08d'  # SHA-256 of our submission 58003999 (these files)
shutil.rmtree(TMP, ignore_errors=True)
TMP.mkdir(parents=True)
data = {}
for name, path, sha, stamp in FILES:
    b = (DS / name).read_bytes()
    assert hashlib.sha256(b).hexdigest() == sha, f'{name}: SHA-256 differs (is the dataset version mounted?)'
    data[path] = b
print(len(data), 'files matched by SHA-256 in', DS)
OUT = WORKING / 'submission.zip'
with zipfile.ZipFile(OUT, 'w') as z:
    for name, path, sha, stamp in FILES:  # one entry per file: the submitted zip's timestamp and mode, deflate at zlib's default level
        zi = zipfile.ZipInfo(path, date_time=tuple(stamp))
        zi.compress_type, zi.external_attr, zi.create_system = zipfile.ZIP_DEFLATED, 0x1800000, 3
        z.writestr(zi, data[path])
del data
with zipfile.ZipFile(OUT) as z:
    assert z.testzip() is None and [i.filename for i in z.infolist()] == [p for _, p, _, _ in FILES]
    for name, path, sha, stamp in FILES:
        assert hashlib.sha256(z.read(path)).hexdigest() == sha, path
h = hashlib.sha256(OUT.read_bytes()).hexdigest()
print(f'wrote {OUT}: {OUT.stat().st_size:,} bytes, SHA-256 {h}')
print('byte-identical to our submission 58003999' if h == SUBZIP else f'not byte-identical to our submission 58003999 (zlib {zlib.ZLIB_RUNTIME_VERSION}); its 18 entries match')
```

```python
# Code-Zelle 3: DER METRIC-CODE DER HOSTS, wortwörtlich kopiert (https://www.kaggle.com/code/metric/google-quantum-ai-metric).
# Nichts hier ist geändert. Zeigt die exakte Bewertung: Cost pro Benchmark, Score = geometrisches Mittel von
# baseline_cost/cost. Für DQI: R(k) x Q^2 x T. Die Verifier laufen pro Salt (Public/Private) einmal.
"""Kaggle metric for 161954: verifiable quantum circuit compilation benchmarks.

A submission is an archive holding one entry per benchmark, with every circuit in either the text
(.kmx) or the binary (.kmb) kickmix format:

    invsqrt.kmx or invsqrt.kmb   Benchmark I: phasing by beta / sqrt(x), at n_p = 10.
    dqi.kmx or dqi.kmb           Benchmark II: the DQI Reed-Solomon decoder, RS(4095, 4025) over GF(2^12).
    dfthcsos/                    Benchmark III: the DFTHC-SOS block encoding of FeMoCo76o113e, as the
                                 ANGLE_k circuits angle_k_0 ... angle_k_<n-1>, each .kmx or .kmb,
                                 and submission.npz, holding the factorization and the Givens tree.

Each benchmark is checked by its verifier, from the competition data, which simulates the circuits on many test inputs,
rejects the submission if any test fails, and otherwise returns its cost (lower is better). Each
leaderboard split seeds the simulations with its own secret salt, so every benchmark is verified once
per split. A split's score is the geometric mean over the benchmarks of `baseline_cost / cost`: the
hosts' reference submissions score 1.0, and halving every benchmark's cost scores 2.0.

The verifiers and kickmix come from the competition data itself, attached to the metric, so it scores
with exactly the files participants download: verifiers/ and kickmix/, built by the 161954 prep
pipeline from pinned commits of the hosts' code and Qualtran. kickmix.so is compiled for that
build's Kaggle image, so the metric must run in that same image. To run the metric locally instead,
install kickmix and the verifiers; local installs take precedence over the competition data.
"""

import json
import math
import pathlib
import random
import stat
import sys
import time
import tokenize
import zipfile
import zlib
from collections.abc import Callable, Mapping
from typing import Any

import numpy as np
import pandas as pd

# kickmix/ and verifiers/ in the competition data, at the 161954 prep pipeline's COMPETITION_DATA_MOUNT.
KICKMIX_DIR = '/kaggle/input/competitions/google-verifiable-quantum-circuit-compilation/kickmix'
VERIFIERS_DIR = '/kaggle/input/competitions/google-verifiable-quantum-circuit-compilation/verifiers'
# Where the orchestrator, and run_metric_locally, put the solution and metadata files.
EVAL_INPUTS_DIR = pathlib.Path('/kaggle/input/competition_evaluation')

# Every kickmix instruction, as named by Circuit.operation_statistics. Listing them rejects any
# instruction a future Qualtran adds until it is reviewed. INFO_TAG is a no-op in simulation;
# kickmix's CircuitBuilder emits it around every iadd and isub. DEBUG_PRINT is a no-op too, as every
# verifier's simulator ignores it, but its qubit and bit ids still count toward the circuit's.
ALLOWED_INSTRUCTIONS = {
    'X', 'CX', 'CCX', 'Z', 'CZ', 'CCZ', 'Z_POW', 'NEG', 'SWAP', 'CSWAP', 'R', 'HMR', 'BIT_INVERT', 'BIT_STORE0', 'BIT_STORE1',
    'PUSH_CONDITION', 'POP_CONDITION', 'INFO_TAG', 'DEBUG_PRINT',
}  # fmt: skip
# Qubit and bit ids must be below this. Verifier memory grew by ~1.5 KB per bit (dqi) and ~1.1 KB
# per qubit (invsqrt) with the verifiers at c636a96, so this capped the growth at ~1 GB; at 03027f8,
# dqi's grows by only ~0.2 KB per qubit or bit, linearly rather than with their product. The
# baselines use ids below 50,000. Raise it if a harder benchmark needs more.
MAX_QUBIT_OR_BIT_ID = 2**30 // 1536
# The arrays read from a dfthcsos submission.npz may total at most this many bytes, ~30 times the
# ~2 MB the reference factorization and tree take.
MAX_NPZ_BYTES = 2**26


class ParticipantVisibleError(Exception):
    pass


def read_circuit(path: pathlib.Path, max_registers: int) -> Any:
    """Return a submitted .kmx or .kmb circuit as a kickmix.Circuit; raise ValueError unless it is fit to verify.

    kickmix validates a file as it parses it, within limits that keep parsing cheap, but simulating
    takes memory that grows with the largest qubit and bit ids, which kickmix allows up to ~5e8,
    so those are capped at MAX_QUBIT_OR_BIT_ID. kickmix also allows a million registers, at
    ~110 bytes each even if empty, so a circuit may have at most `max_registers`, the most its
    benchmark needs. Every register must be named: the dfthcsos verifier crashes on an unnamed one.
    """
    import kickmix  # ty: ignore[unresolved-import]  # In kickmix/, which generate_standard_submission put on sys.path.

    circuit = kickmix.Circuit.from_file(path, format=path.suffix.removeprefix('.'))
    unsupported = set(circuit.operation_statistics()) - ALLOWED_INSTRUCTIONS
    if unsupported:
        raise ValueError(f'unsupported instructions {sorted(unsupported)}')
    largest_id = max(circuit.num_qubits, circuit.num_bits) - 1
    if largest_id >= MAX_QUBIT_OR_BIT_ID:
        raise ValueError(f'qubit or bit id {largest_id} is above the limit of {MAX_QUBIT_OR_BIT_ID - 1}')
    if circuit.num_registers > max_registers:
        raise ValueError(f'{circuit.num_registers} registers, above the limit of {max_registers} for this benchmark')
    if not all(isinstance(name, str) for name in circuit.register_data):
        raise ValueError('every register needs a name, given by its REGISTER line')
    return circuit


def read_npz(path: pathlib.Path, spec: Mapping[str, tuple[str, tuple[int | str, ...]]]) -> dict[str, np.ndarray]:
    """Return the arrays `spec` names from an .npz; raise ValueError unless each is a plain number array as specified.

    `spec` maps each key to the numpy dtype kinds it may have, such as 'f' for floats, and its shape,
    in which a string names a dimension of any positive size that must agree wherever it recurs.

    Each array's header is a Python literal of its dtype and shape, which np.load trusts: a few KB
    of deflated zeros can claim a terabyte-sized array, and the dtype can be anything numpy can
    describe, from structured and nested types to Python objects that need unpickling. So the
    headers are read first, and the arrays loaded only if each is a plain number type of its kind,
    not big-endian, with its shape, and they total at most MAX_NPZ_BYTES. Only format 1.0 headers,
    which numpy.savez writes, are accepted, and numpy refuses any over 10 KB before parsing it.
    """
    dimensions: dict[str, int] = {}
    total = 0
    with zipfile.ZipFile(path) as archive:
        members = {name.removesuffix('.npy'): name for name in archive.namelist()}
        missing = [key for key in spec if key not in members]
        if missing:
            raise ValueError(f'{path.name} has no {missing}')
        for key, (kinds, expected_shape) in spec.items():
            with archive.open(members[key]) as member:
                if np.lib.format.read_magic(member) != (1, 0):
                    raise ValueError(f'{key} in {path.name} is not in .npy format 1.0, which numpy.savez writes')
                shape, _, dtype = np.lib.format.read_array_header_1_0(member)
            if dtype.kind not in kinds or dtype.names is not None or dtype.subdtype is not None or dtype.byteorder == '>':
                raise ValueError(f'{key} in {path.name} has dtype {dtype}, not a plain number type of numpy kind {kinds!r}')
            matches = len(shape) == len(expected_shape) and all(
                size > 0 and size == (dimensions.setdefault(expected, size) if isinstance(expected, str) else expected)
                for size, expected in zip(shape, expected_shape, strict=True)
            )
            if not matches:
                raise ValueError(f'{key} in {path.name} has shape {shape}, not {expected_shape} with its named dimensions as in {dimensions}')
            total += math.prod(shape) * dtype.itemsize
    if total > MAX_NPZ_BYTES:
        raise ValueError(f'the arrays in {path.name} take {total:,} bytes, above the limit of {MAX_NPZ_BYTES:,}')
    with np.load(path, allow_pickle=False) as npz:
        return {key: np.array(npz[key]) for key in spec}


def find_one(root: pathlib.Path, name: str, description: str, is_dir: bool = False) -> pathlib.Path:
    """The one path called `name` (a glob) under `root`, where the submission unpacked; raise ParticipantVisibleError otherwise."""
    # macOS Finder's Compress adds __MACOSX/, which mirrors every directory, with an AppleDouble ._ file per file.
    paths = [path for path in root.rglob(name) if path.is_dir() == is_dir and '__MACOSX' not in path.relative_to(root).parts]
    if len(paths) != 1:
        raise ParticipantVisibleError(f'The submission must contain exactly one {description}, found {len(paths)}.')
    return paths[0]


def generate_standard_submission(submission_dir: str) -> None:
    """Verify the submission under every split's salt, and write each verification's cost as submission.csv.

    `submission_dir` is where the orchestrator unpacked the submission archive. Every split's verifications run here, in random order, before the orchestrator calls score() for
    either split, so neither a failure's timing nor its message shows which split it failed on.
    Every file is read and checked before any verifier runs, so a malformed file fails in seconds
    rather than after another benchmark's verification. The verifiers run one at a time, as the
    invsqrt and dqi verifiers spread their own simulation across processes.

    The orchestrator passes neither the solution nor the metadata in, so the solution is read from
    where it puts it; this metric's own solution names its row id column `row_id`. Each row's
    `seed_salt` is merged by its verifier with the submission's hash to seed the simulation, so a
    submission always faces the same tests, but participants can't compute them. Unsalted, the seed
    would let a team whose circuit fails on a few inputs re-roll its tests offline with cost-free
    edits until they miss those inputs; with the salt, each re-roll costs a submission. A salt that
    is missing or short is refused, as it would leave the seed unsalted or guessable.

    kickmix and the verifiers are imported here rather than at the top because the orchestrator imports
    this module during validation, when the competition data isn't mounted.
    """
    solution_paths = list(EVAL_INPUTS_DIR.glob('solution.*'))
    if len(solution_paths) != 1:
        raise ValueError(f'Expected one solution.csv or solution.parquet in {EVAL_INPUTS_DIR}, found {[path.name for path in solution_paths]}')
    [solution_path] = solution_paths
    solution = pd.read_csv(solution_path) if solution_path.suffix == '.csv' else pd.read_parquet(solution_path)
    scored = solution[solution['Usage'] != 'Ignored']
    # score()'s hyperparameters, which the orchestrator passes only to score().
    hyperparameters = json.loads((EVAL_INPUTS_DIR / 'metadata.json').read_text()).get('Hyperparameters') or {}
    shot_divisor = int(hyperparameters.get('verification_shot_divisor', 1))
    for salt in scored['seed_salt']:
        if not isinstance(salt, str) or len(salt) < 32:
            raise ValueError(f'Every scored solution row needs a seed_salt of at least 32 characters, got {salt!r}')

    # Appended, not prepended, so local installs of kickmix and the verifiers win when running locally.
    sys.path += [KICKMIX_DIR, VERIFIERS_DIR]
    from dfthcsos import verify as dfthcsos_verify  # ty: ignore[unresolved-import]  # These live in verifiers/.
    from dfthcsos.scoreinfra.reference import FACTORIZATION_KEYS, ORBITALS  # ty: ignore[unresolved-import]
    from dqi import verify_submission_dqi  # ty: ignore[unresolved-import]
    from invsqrt import verify_submission_invsqrt  # ty: ignore[unresolved-import]

    root = pathlib.Path(submission_dir)

    def read(path: pathlib.Path, reader: Callable[[pathlib.Path, Any], Any], spec: Any) -> Any:
        # tar and 7z submissions can unpack links, which would have this read the host's files, and
        # FIFOs and devices, which would block or never end.
        status = path.lstat()
        if not stat.S_ISREG(status.st_mode) or status.st_nlink > 1 or not path.resolve().is_relative_to(root.resolve()):
            raise ParticipantVisibleError(f'{path.relative_to(root)} must be a regular file, not a link or a special file.')
        try:
            return reader(path, spec)
        # What kickmix, zipfile, zlib and numpy raise on malformed files, found by fuzzing an .npz.
        except (ValueError, RuntimeError, OSError, EOFError, zipfile.BadZipFile, zlib.error, tokenize.TokenError) as err:
            raise ParticipantVisibleError(f'{path.relative_to(root)} is invalid: {err}') from err

    batches = max(1, verify_submission_dqi.DEFAULT_NUM_SHOTS // verify_submission_dqi.DEFAULT_BATCH_SIZE // shot_divisor)
    dqi_spec = verify_submission_dqi.ProblemSpecDQI.benchmark_instance(num_shots=batches * verify_submission_dqi.DEFAULT_BATCH_SIZE)
    # Each circuit's most registers: invsqrt's x, and dqi's S_i and E_j.
    invsqrt = read(find_one(root, 'invsqrt.km[xb]', 'invsqrt.kmx or invsqrt.kmb'), read_circuit, 1)
    dqi = read(find_one(root, 'dqi.km[xb]', 'dqi.kmx or dqi.kmb'), read_circuit, dqi_spec.n + dqi_spec.m)
    dfthcsos_dir = find_one(root, 'dfthcsos', 'dfthcsos directory', is_dir=True)
    angle_files = list(dfthcsos_dir.glob('angle_k_*.km[xb]'))
    angle_paths = {path.stem: path for path in angle_files}
    # A circuit given in both formats leaves fewer stems than files, so the two can't match.
    stems = [f'angle_k_{k}' for k in range(len(angle_files))]
    if not stems or sorted(angle_paths) != sorted(stems):
        raise ParticipantVisibleError('dfthcsos/ must hold the circuits angle_k_0 ... angle_k_<n-1>, each once, as .kmx or .kmb.')
    # An ANGLE_k circuit's `selection` and `word_j` registers each hold a qubit, of at most QUBIT_CAP.
    # The verifier allows other registers too, but none are needed.
    angle_circuits = [read(angle_paths[stem], read_circuit, dfthcsos_verify.QUBIT_CAP) for stem in stems]
    # The factorization (see dfthcsos.scoreinfra.reference), with R factors of B vectors over the N
    # orbitals and C copies, and the Givens tree's N - 1 edges.
    npz_spec = {
        'U': ('f', ('R', 'B', ORBITALS)),
        'W': ('f', ('R', 'B', 'C')),
        'H2_I': ('f', ('R', 'C')),
        'H1_I': ('f', ()),
        'Hsym_lower': ('f', (ORBITALS * (ORBITALS + 1) // 2,)),
        'tree_edges': ('iu', (ORBITALS - 1, 2)),
    }
    if set(npz_spec) != {*FACTORIZATION_KEYS, 'tree_edges'}:
        raise ValueError(f'The dfthcsos verifier reads the factorization arrays {FACTORIZATION_KEYS}, which npz_spec must cover exactly')
    npz = read(find_one(dfthcsos_dir, 'submission.npz', 'dfthcsos/submission.npz'), read_npz, npz_spec)
    tree_edges = npz.pop('tree_edges')

    # Benchmark -> its verifier run, given the salt.
    verifications: dict[str, Callable[[str], dict[str, Any]]] = {
        'invsqrt': lambda salt: verify_submission_invsqrt.verify(invsqrt, verify_submission_invsqrt.ProblemSpecInvSqrt.for_n_p(10), salt=salt),
        'dqi': lambda salt: verify_submission_dqi.verify(dqi, dqi_spec, salt=salt),
        'dfthcsos': lambda salt: dfthcsos_verify.verify(
            angle_circuits, npz, tree_edges, salt=salt, shots_per_address=max(1, dfthcsos_verify.SHOTS_PER_ADDRESS // shot_divisor)
        ),
    }
    runs = list(zip(scored['row_id'], scored['benchmark'], scored['seed_salt'], strict=True))
    random.shuffle(runs)
    # Ignored rows aren't scored, but the orchestrator still expects a submission row for each.
    costs, seconds = dict.fromkeys(solution['row_id'], 0.0), dict.fromkeys(solution['row_id'], 0.0)
    for row_id, benchmark, salt in runs:
        start = time.monotonic()
        try:
            costs[row_id] = float(verifications[benchmark](salt)['score'])
        # The exceptions the verifiers' command lines report as a failed submission; dfthcsos's
        # InvalidCircuits is a ValueError.
        except (AssertionError, ValueError, RuntimeError, KeyError) as err:
            raise ParticipantVisibleError(f'The {benchmark} submission failed verification: {err}') from err
        if not costs[row_id] > 0:
            raise ParticipantVisibleError(f'The {benchmark} submission has non-positive cost {costs[row_id]}.')
        seconds[row_id] = time.monotonic() - start
    pd.DataFrame({'row_id': list(costs), 'cost': list(costs.values()), 'seconds': list(seconds.values())}).to_csv('submission.csv', index=False)


def score(
    solution: pd.DataFrame, submission: pd.DataFrame, row_id_column_name: str, verification_shot_divisor: int = 1
) -> tuple[float, dict[str, Any]]:
    """Return the geometric mean over the benchmarks of `baseline_cost / cost`, where higher is better.

    `verification_shot_divisor` is for testing only, and must stay 1 on Kaggle. generate_standard_submission
    reads it, and divides the dqi and dfthcsos verifiers' default numbers of shots by it, which makes
    their verification that much faster and weaker, and changes their costs, so that the reference
    submissions no longer score 1.0. invsqrt's verifier is the fastest, and needs a multiple of 64
    shots per input to fill its batches, its default, so it keeps every shot.

    The solution has a row per benchmark and leaderboard split, holding the split's secret
    `seed_salt` and the `baseline_cost` its benchmark's reference submission scored under that salt.
    `submission` is generate_standard_submission's output, which holds each row's `cost`, as the
    verification runs there. Returns each benchmark's cost, improvement and verification time as
    details.
    """
    merged = solution.merge(submission, on=row_id_column_name, validate='one_to_one')
    details = {
        benchmark: {'cost': cost, 'improvement_over_baseline': baseline_cost / cost, 'seconds': run_seconds}
        for benchmark, cost, baseline_cost, run_seconds in zip(
            merged['benchmark'], merged['cost'], merged['baseline_cost'], merged['seconds'], strict=True
        )
    }
    ratios = [benchmark_details['improvement_over_baseline'] for benchmark_details in details.values()]
    return math.prod(ratios) ** (1 / len(ratios)), details
```

```python
# Code-Zelle 4: Führt den Host-Metric-Code auf unserem Zip bei zwei eigenen Salts aus (Public/Private).
# EXPECTED enthält die auf unserer Maschine gemessenen Kosten; die Assertion prüft Übereinstimmung < 1e-9.
# Für DQI wird zusätzlich k (fehlgeschlagene Shots) und R (Repetition Factor) ausgegeben.
import json, time
import pandas as pd
KICKMIX_DIR, VERIFIERS_DIR = str(COMP / 'kickmix'), str(COMP / 'verifiers')
EVAL_INPUTS_DIR = TMP / 'eval_inputs'
EVAL_INPUTS_DIR.mkdir()
TASKS = ('invsqrt', 'dqi', 'dfthcsos')
REF = {"invsqrt": 2076774.233715282, "dqi": 24439463583672.93, "dfthcsos": 3355599588.3155365}  # baseline_cost: our unsalted runs of the hosts' sample circuits (their salted values are secret)
SALT = {(s, t): hashlib.sha256(f'33-metric-local-submission.zip-{s}-{t}'.encode()).hexdigest()[:40] for s in ('Public', 'Private') for t in TASKS}
NAME = {'Public': 'salt A', 'Private': 'salt B'}
solution = pd.DataFrame([{'row_id': f'{s}_{t}', 'benchmark': t, 'seed_salt': SALT[s, t], 'baseline_cost': REF[t], 'Usage': s}
                         for s in ('Public', 'Private') for t in TASKS])
solution.to_csv(EVAL_INPUTS_DIR / 'solution.csv', index=False)
(EVAL_INPUTS_DIR / 'metadata.json').write_text(json.dumps({'Hyperparameters': {}}))
with zipfile.ZipFile(OUT) as z:  # the metric reads the files the zip holds, not the dataset copies
    z.extractall(TMP / 'unpacked')

sys.path += [KICKMIX_DIR, VERIFIERS_DIR]
from dqi import verify_submission_dqi
from invsqrt import verify_submission_invsqrt
from dfthcsos import verify as dfthcsos_verify
REPORTS = []


def recording(task, fn):  # returns each verifier's report unchanged and keeps a copy for the table below
    def run(*args, **kwargs):
        report = fn(*args, **kwargs)
        REPORTS.append((task, kwargs.get('salt'), report))
        return report
    return run


for task, module in (('invsqrt', verify_submission_invsqrt), ('dqi', verify_submission_dqi), ('dfthcsos', dfthcsos_verify)):
    module.verify = recording(task, module.verify)
t0, here = time.time(), os.getcwd()
os.chdir(TMP)  # the metric writes submission.csv into the working directory; keep it out of /kaggle/working
try:
    generate_standard_submission(str(TMP / 'unpacked'))
finally:
    os.chdir(here)
costs = pd.read_csv(TMP / 'submission.csv')
EXPECTED = {"Public": {"invsqrt": 97921.57623452431, "dqi": 375360071326.3232, "dfthcsos": 306230171.24607325}, "Private": {"invsqrt": 97921.69731080656, "dqi": 375360235441.8261, "dfthcsos": 306230171.24607325}}  # the same metric on our machine (arm64 kickmix build), these files
for split in ('Public', 'Private'):
    sol = solution[solution['Usage'] == split].reset_index(drop=True)
    value, details = score(sol, costs[costs['row_id'].isin(sol['row_id'])], 'row_id')
    print(f"hosts' metric at {NAME[split]} (solution rows Usage = {split}): {value!r}")
    for t, d in details.items():
        print(f"    {t:9s} cost {d['cost']:.12g}   reference / cost {d['improvement_over_baseline']:.6f}   ({d['seconds']:.0f} s)")
        assert abs(d['cost'] / EXPECTED[split][t] - 1) < 1e-9, (split, t, d['cost'], EXPECTED[split][t])
print()
for task, salt, r in sorted(REPORTS, key=lambda x: (TASKS.index(x[0]), x[1])):
    split = next(s for s in ('Public', 'Private') if SALT[s, task] == salt)
    line = f"{task:9s} {NAME[split]}: {r['status']}, qubits {r.get('num_qubits')}, Toffolis {r.get('toffoli_count'):,.2f}"
    if task == 'dqi':
        line += f", failed shots k = {r['value_errors'] + r['phase_errors']} of {r['verified_shots']:,}, R = {r['repetition_factor']:.7f}"
    if task == 'dfthcsos':
        line += f", lambda_eff {r.get('lambda_eff'):.6f}"
    print(line)
print(f'metric wall time {time.time() - t0:.0f} s')
shutil.rmtree(TMP)
```

## 2. The field, priced

The top 30 of the Code tab in score order (Kaggle CLI, 02:46 UTC on 5 November). Version, score and votes: the data each notebook's page shows, read between 02:46 and 02:47 UTC; a page score belongs to the version named next to it, not always to the current one ("not scored at our read": the current version had no score yet). The figure above keeps its 01:19 UTC reads. Newest outputs priced on our machine with the official verifiers (default shots, unsalted; watcher pass of 01:00 UTC). One line each: what the notebook does, in the authors' terms where it describes its own work. Licence: as each page or text states it; Kaggle's page shows Apache 2.0 for every public notebook. The last column says what this zip takes from it.

| # | notebook | author | version | score, time of read (UTC) | votes | licence | conclusion | taken here |
|---|---|---|---:|---|---:|---|---|---|
| 1 | [yoyobar/lb-22-99-invsqrt-101-62-qubits](https://www.kaggle.com/code/yoyobar/lb-22-99-invsqrt-101-62-qubits) | yoyobar | 30 | **24.72074** (V30) | 86 | Apache 2.0 | V28 = SomeJoint V34 plus one more DQI product-cache edit (one CCZ fewer, 993c7038). Its 01:10 UTC run (version 29, packaging only, by its log) ships invsqrt 0104d1b4, a new DQI e87b2de6 (396,917.39 Toffolis at our verifier's unsalted seed in our 02:01 UTC watcher pass, 1.10 fewer than 993c7038 and 12.84 more than our fd0ef09e; 1 failed shot there) and chemistry 21d6f276. Version 30 (its 02:11 UTC run) is the current version at our 02:47 UTC read, page score 24.72074; not pulled by us. | the base of `dqi.kmb` (993c7038) |
| 2 | [kirilltym/quantum-compilation-19](https://www.kaggle.com/code/kirilltym/quantum-compilation-19) | Kirill Tymchishin | 5 | **24.72062** (V5) | 4 | Apache 2.0 (page); its sources Apache 2.0 (its text) | An audit and integration, by its own text: manwithacat's HW-19 loaders with the weight release 8bf7a9d1 Isabe11aM00re V4 publishes, on Syed Asad Ali's word table. Version 5 (00:12 UTC run) ships chemistry 21d6f276 (15,277 Toffolis, 306,711,859.83 ours, the cheapest public chemistry in our watcher at 01:00 UTC), invsqrt 0104d1b4 and DQI 993c7038. Version 4 (21:44 UTC) reused Syed Asad Ali's c3a41b23; version 3 (20:48 UTC) is the chemistry of our version 17. | none (its version 3 chemistry was in our version 17) |
| 3 | [manwithacat/vqcc-hedge-wizardry-notebook](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook) | manwithacat | 23 | **24.72025** (V23) | 52 | Apache 2.0 | Hedge Wizardry, one small verified tweak per version. Version 23 (23:33 UTC run) is HW-19: his HW-18 padded-row step on Syed Asad Ali's word table, loaders 4 to 14 at 280 Toffolis per pass instead of 282 (15,277 Toffolis, 306,723,130.32 ours); its log prints 24.72026 at its default salt and 24.71317 expected over 48 DQI draws. HW-16 and HW-17 were the bases of our R53 and R54 refits; HW-07 is in our R42 rewrite. | **the 15 angle files** (bytes); the constrained-refit idea of HW-03 (credited) |
| 4 | [heliosli/the-dataset-is-public-now-enjoy](https://www.kaggle.com/code/heliosli/the-dataset-is-public-now-enjoy) | Heliosli | 7 | best 24.69693 (V6); V7 not scored at our read | 25 | Apache 2.0 | An earlier output: invsqrt 15118bfa, DQI 748b01a7, chemistry on syed3000's (9, 143, 39) table with heliosli's weights. Syed Asad Ali credits heliosli with first showing the weight refit up to the error gate. Version 6 is its 00:28 UTC run (24.69693 on its page). Version 7 (its 01:57 UTC run) is the current version at our 02:47 UTC read, not scored then; not pulled by us. | none (the refit idea, credited) |
| 5 | [isabe11am00re/qcc-v66s33w-submission](https://www.kaggle.com/code/isabe11am00re/qcc-v66s33w-submission) | Isabe11aM00re | 4 | **24.69693** (V4) | 2 | Apache 2.0 (page; no text) | Version 4 (23:25 UTC run): invsqrt af469847, DQI 993c7038 and Syed Asad Ali's c3a41b23 loaders with a new npz 8bf7a9d1 (307,595,234.96 ours), the first public ship of that npz in our pulls; the notebook has no markdown. | none |
| 6 | [prvsiyan/verifier-guided-quantum-circuit-optimization](https://www.kaggle.com/code/prvsiyan/verifier-guided-quantum-circuit-optimization) | prvsiyan | 27 | best 24.69663 (V26); V27 not scored at our read | 23 | Apache 2.0 | A verified best-of of the best public members, by its own text (version 27 is a text-only update of version 26). Its 22:49 and 01:09 UTC outputs ship af469847, 993c7038 and c3a41b23. | none |
| 7 | [syed3000/vqcc-own-circuit-portfolio-notebook](https://www.kaggle.com/code/syed3000/vqcc-own-circuit-portfolio-notebook) | Syed Asad Ali | 3 | **24.67250** (V3) | 20 | Apache 2.0 (page; his text: "Public portfolio (Apache-2.0)") | His own 891-qubit DQI decoder (fc3ba816: retained-head chain, telescoped prefix jump, measurement clean-up, product caching) and an invsqrt with deferred fan-in lookup. Its 21:28 UTC run (version 3) ships invsqrt 556ee4c8 (98,208.31 ours), DQI fc3ba816 and chemistry c3a41b23 (15,321 Toffolis, 307,606,537.91 ours), the first public release of that chemistry; his text describes it as marculera's DF-THC pipeline and Ozer's progressive rounding with his own loader compiler, lattice-aware rounding, 8-group (8, 143, 45) table and weight refit. | `angle_k_0..3` and five npz arrays (bytes, through HW-19); the decoder under `dqi.kmb` |
| 8 | [busyaprime/lb-24-65425-top-30-qcc-notebooks-re-verified](https://www.kaggle.com/code/busyaprime/lb-24-65425-top-30-qcc-notebooks-re-verified) | Akmal Xodarev (busyaprime) | 17 | **24.65425** (V17), the previous public version | 51 | Apache 2.0 | This notebook, version 17: our DQI rewrite fd0ef09e with Kirill Tymchishin's Quantum Compilation 19 chemistry (submission 57998728, LB 24.65425). | this notebook |
| 9 | [leoprovorov/full-xor-chemistry-no-borrowed-bits](https://www.kaggle.com/code/leoprovorov/full-xor-chemistry-no-borrowed-bits) | AlekseiProvorov | 14 | best 24.65395 (V11); V14 not scored at our read | 9 | Apache 2.0 | A chemistry study: the cost law lambda_eff x T x Q taken apart, toward loaders with no borrowed bits (its title and opening). Its 23:42 UTC run (version 14) left no submission.zip in our pull. | none |
| 10 | [somejoint/quantum-circuits-24-65-local-gm-chem-refit](https://www.kaggle.com/code/somejoint/quantum-circuits-24-65-local-gm-chem-refit) | Agniv Banerjee | 36 | **24.65393** (V36) | 116 | Apache 2.0 | V34 wrote our invsqrt af469847 (their version 33 circuit with Kirill Tymchishin's two forced phase bits), with yoyobar's 748b01a7 DQI and their own W and H2_I refit on Lera's chemistry. Its 21:35 UTC run (version 36) carries chemistry 5d9e21c4 (15,347 Toffolis, 309,207,580.14 ours). | `invsqrt.kmb` (author) |
| 11 | [manwithacat/the-real-150k-was-the-friends-we-made](https://www.kaggle.com/code/manwithacat/the-real-150k-was-the-friends-we-made) | manwithacat | 114 | best 24.65389 (V112); V114 not scored at our read | 85 | Apache 2.0 | An automated best-of selector; DQI ranked by mean cost over 48 fixed draws. Its 23:17 UTC run (version 113) ships invsqrt 0104d1b4, DQI fc3ba816 and chemistry c3a41b23. Version 114 (its 02:17 UTC run) is the current version at our 02:47 UTC read, not scored then; not pulled by us. | none |
| 12 | [qwertykeypadapple/qcc-kernel-search-24-65](https://www.kaggle.com/code/qwertykeypadapple/qcc-kernel-search-24-65) | qwertykeypadapple | 1 | **24.65388** (V1) | 0 | Apache 2.0 (its text) | Its own 15 chemistry angle loaders from a kernel-relation search on Lera's compiler, 15,347 Toffolis per step against Lera's 15,967 (their numbers), with SomeJoint's refit weights (cf0bc9f0; 309,209,296.10 ours); invsqrt af469847, DQI 993c7038. | the kernel search behind HW-19's loaders 4 to 14 (through manwithacat) |
| 13 | [kalidenaiarys/quantum-circuit-compilation-public-lb-24-59425](https://www.kaggle.com/code/kalidenaiarys/quantum-circuit-compilation-public-lb-24-59425) | Kaliden Aiarys | 1 | **24.59425** (V1) | 1 | Apache 2.0 code statement (as Kirill Tymchishin relays it) | An audit and repackaging of a submission zip it does not attribute: invsqrt 0104d1b4, DQI 748b01a7, chemistry f15688a5 (npz b463690f; 15,459 Toffolis, 311,463,217.94 ours). | none (its npz was in our version 17) |
| 14 | [evgendvorkin/google-quantum-ai-deep-eda-with-analogies](https://www.kaggle.com/code/evgendvorkin/google-quantum-ai-deep-eda-with-analogies) | Дворкин Евгений Владимирович | 16 | **24.59420** (V16) | 28 | Apache 2.0 | An EDA of the three tasks with analogies; its 19:45 UTC output ships invsqrt af469847, DQI 748b01a7 and a chemistry on npz e2ba3d64. | none |
| 15 | [alexchilton/24-59-lb-verified-three-task-portfolio](https://www.kaggle.com/code/alexchilton/24-59-lb-verified-three-task-portfolio) | alex chilton | 106 | best 24.72065 (V105); V106 not scored at our read | 110 | Apache 2.0 | Ships SomeJoint's invsqrt and, in its 15:59 UTC run, yoyobar's 993c7038 DQI; research cells (an invsqrt at 93 qubits, a DQI port with 4 phase errors) not shipped. | the bytes of `invsqrt.kmb` and of the 993c7038 base |
| 16 | [nilanjansaha123/quantum-circuits-24-59-chem-gauge-refit](https://www.kaggle.com/code/nilanjansaha123/quantum-circuits-24-59-chem-gauge-refit) | Nilanjan_Saha123 | 1 | **24.59420** (V1) | 2 | Apache 2.0 (page; its text states none) | By its section titles, an invsqrt symbolic peephole and free-coin reconstructor, a salt-safe DQI selector and an exact column-gauge and guarded tangent weight refitter for the chemistry. Its 21:12 UTC run ships invsqrt 55de52ae, DQI 748b01a7 and a chemistry on npz e2ba3d64 (not priced by us); its log prints a local geometric mean of 24.59421. | none |
| 17 | [kirilltym/quantum-circuits-four-loaders-eight-toffolis](https://www.kaggle.com/code/kirilltym/quantum-circuits-four-loaders-eight-toffolis) | Kirill Tymchishin | 10 | **24.59418** (V10) | 45 | Apache 2.0 | invsqrt 0104d1b4: a zero certificate proves q21 = 0 before two HMRs. His attribution field credits Leo Tang (first single-accumulator merge), Qiuqiu (affine-conjugated quadratic merge), Malachi Moody and Syed Asad Ali (free-coin idea) and SomeJoint (phase split). His own DQI trial met 1 failure at another salt. | the forced phase bits inside `invsqrt.kmb` |
| 18 | [isabe11am00re/qcc-v65wqq-submission](https://www.kaggle.com/code/isabe11am00re/qcc-v65wqq-submission) | Isabe11aM00re | 2 | **24.57994** (V2) | 7 | Apache 2.0 | Assembly: invsqrt 0104d1b4, DQI 06aa8ca2, chemistry at Lera's own weights (lambda_eff 47.267). | none |
| 19 | [ayodejiibrahimlateef/vqcc-24-56308-local](https://www.kaggle.com/code/ayodejiibrahimlateef/vqcc-24-56308-local) | Ayodeji | 4 | best 24.56307 (V3); V4 not scored at our read | 4 | Apache 2.0 | The first public transport of Lera's compact-group chemistry, as SomeJoint and Alex Chilton credit it; code only. | none |
| 20 | [qiuqiuh/qcc-refresh-v65w-sx-sy7-inverse](https://www.kaggle.com/code/qiuqiuh/qcc-refresh-v65w-sx-sy7-inverse) | qiuqiu | 1 | **24.56203** (V1) | 6 | Apache 2.0 | The cut of one accumulator's four Toffolis to two, which SomeJoint V34 credits to qiuqiuh first. | the cut inside `invsqrt.kmb` |
| 21 | [orecord/quantum-circuit-compilation-pipeline](https://www.kaggle.com/code/orecord/quantum-circuit-compilation-pipeline) | Or4k2! | 10 | best 24.53786 (V10); V10 not scored at our read | 9 | Apache 2.0 | The newest output equals syed3000 V2's files; the text describes own builds that this output does not hold. | none |
| 22 | [kawh1111/qcomp-harvest-v32](https://www.kaggle.com/code/kawh1111/qcomp-harvest-v32) | kawh1111 | 5 | **24.52648** (V5) | 9 | Apache 2.0 | A copy of heliosli's 'qcc-circuits-live' v32 set. | none |
| 23 | [qiuqiuh/qcc-refresh-v64y-sx-sy6](https://www.kaggle.com/code/qiuqiuh/qcc-refresh-v64y-sx-sy6) | qiuqiu | 1 | **24.52648** (V1) | 3 | Apache 2.0 | The same three files as kawh1111's copy. | none |
| 24 | [isabe11am00re/qcc-v58x-submission](https://www.kaggle.com/code/isabe11am00re/qcc-v58x-submission) | Isabe11aM00re | 5 | **24.50462** (V5) | 11 | Apache 2.0 | Assembly; the first ship of yoyobar's rewrite 06aa8ca2. | none |
| 25 | [leoprovorov/but-some-q-squared-width-lab](https://www.kaggle.com/code/leoprovorov/but-some-q-squared-width-lab) | AlekseiProvorov | 29 | **24.49590** (V29) | 17 | Apache 2.0 | A peak-live-qubit study; chemistry refit to lambda_eff 47.0236. | none |
| 26 | [ahoirg/qcc-reproducible-circuit-portfolio](https://www.kaggle.com/code/ahoirg/qcc-reproducible-circuit-portfolio) | Ali Haydar Özdağ | 2 | **24.49359** (V2) | 6 | Apache 2.0 | Compiles the 15 C39 loaders from a pinned factor; five exact local rewrites on the 62-qubit invsqrt, proven on all 640 local basis cases, with a broken negative control. | the flag-carry idea in the DQI line |
| 27 | [syed3000/vqcc-24-43-portfolio](https://www.kaggle.com/code/syed3000/vqcc-24-43-portfolio) | Syed Asad Ali | 3 | **24.47034** (V3) | 14 | Apache 2.0 | An earlier version of his portfolio (6b929acd, fc3ba816, a2427fcf); the decoder source SomeJoint V34 cites. | none |
| 28 | [heliosli/quantum-ai-v1](https://www.kaggle.com/code/heliosli/quantum-ai-v1) | Heliosli | 47 | **24.43253** (V47) | 125 | Apache 2.0 | The same three files as nicks037/submission-zip (04900d11, fc3ba816, 140b2511). | none |
| 29 | [nicks037/submission-zip](https://www.kaggle.com/code/nicks037/submission-zip) | EigenOS | 3 | **24.43253** (V3) | 0 | Apache 2.0 | The same three files as heliosli/quantum-ai-v1. | none |
| 30 | [dmitriigluzdov/quantum-circuit-compilation-from-source](https://www.kaggle.com/code/dmitriigluzdov/quantum-circuit-compilation-from-source) | Dmitrii Gluzdov | 53 | **24.34924** (V53) | 89 | Apache 2.0 | Builds from source; SomeJoint's 892-qubit DQI line (632b82b4), invsqrt bce2948f. Its 22:15 UTC run (version 53) not priced. | none |

The cheapest public files per task (watcher prices of 01:00 UTC, unsalted, default shots; invsqrt and DQI by file SHA-256, chemistry by our member id of its 15 angle circuits plus npz, with the npz SHA-256), with ours. "Shipped by" lists the notebooks whose outputs hold the same bytes, first shipper first, from our own entry compares:

| task | file | cost | reference / cost | qubits | Toffolis | DQI k on the LB | shipped by |
|---|---|---:|---:|---:|---:|---|---|
| invsqrt | `af469847` | 97,921.58 | 21.20855 | 62 | 1,281.66 |  | this zip; SomeJoint V34, yoyobar V28, Alex Chilton, Isabe11aM00re v66s33w V3 and V4, qwertykeypadapple V1, evgendvorkin, prvsiyan (22:49 UTC run) |
| invsqrt | `0104d1b4` | 97,921.68 | 21.20852 | 62 | 1,281.67 |  | Kirill Tymchishin V10 and Quantum Compilation 19 (versions 3 and 5), manwithacat Hedge Wizardry V19, V20, V22 and V23 and 150k version 113, kalidenaiarys, Isabe11aM00re v65wqq |
| invsqrt | `4ccef421` | 97,999.08 | 21.19177 | 62 | 1,282.16 |  | qiuqiuh V1 |
| invsqrt | `abd508c7` | 98,123.13 | 21.16498 | 62 | 1,284.17 |  | ayodejiibrahimlateef V4 |
| dqi | `fd0ef09e` (this zip, ours) | 375,360,199,395.52 at k 0 | 65.10936 | 891 | 396,904.56 | **0** (all 9 readings, section 3) | this zip |
| dqi | `993c7038` | 375,373,377,713.41 | 65.10708 | 891 | 396,918.49 | not read by us | yoyobar V28, Alex Chilton, Isabe11aM00re v66s33w V3 and V4, qwertykeypadapple V1, Kirill Tymchishin Quantum Compilation 19 (versions 3 and 5), prvsiyan (22:49 UTC run) |
| dqi | `748b01a7` | 375,374,174,093.81 | 65.10694 | 891 | 396,919.33 | 0 | SomeJoint V34, Kirill Tymchishin V10, kalidenaiarys, qiuqiuh V1, evgendvorkin |
| dqi | `06aa8ca2` | 375,375,248,713.26 | 65.10675 | 891 | 396,920.47 | 0 | isabe11am00re v65wqq and v58x, kawh1111 V5 |
| dqi | `fc3ba816` | 375,376,238,975.31 | 65.10658 | 891 | 396,921.52 | 0 | Syed Asad Ali's own-circuit portfolio V3 and his 24.43 portfolio, manwithacat Hedge Wizardry V19, V20, V22 and V23 and 150k version 113, ayodejiibrahimlateef V4, orecord V10 |
| dfthcsos | **HW-19 with our R55 weights** (npz `3d51e969`, this zip, ours) | 306,230,171.25 | 10.95777 | 427 | 15,277.00 | | this zip; submission 58003999 (24.73387) |
| dfthcsos | `21d6f276` (npz `8bf7a9d1`) | 306,711,859.83 | 10.94056 | 427 | 15,277.00 |  | Kirill Tymchishin Quantum Compilation 19 version 5 (00:12 UTC run): HW-19's angle files with Isabe11aM00re V4's npz; our 58004424 (24.72091) |
| dfthcsos | `7369cf78` (HW-19) (npz `4fe22e78`) | 306,723,130.32 | 10.94016 | 427 | 15,277.00 |  | manwithacat Hedge Wizardry version 23 (23:33 UTC run); our 58002211 (24.72061) |
| dfthcsos | `9fc378be` (npz `8bf7a9d1`) | 307,595,234.96 | 10.90914 | 427 | 15,321.00 |  | Isabe11aM00re v66s33w version 4 (23:25 UTC run): Syed Asad Ali's angle files with a new npz |
| dfthcsos | `c3a41b23` (npz `4fe22e78`) | 307,606,537.91 | 10.90874 | 427 | 15,321.00 |  | Syed Asad Ali's own-circuit portfolio V3 (21:28 UTC run, first), then Kirill Tymchishin Quantum Compilation 19 version 4 (21:44 UTC), prvsiyan (22:49 UTC run), manwithacat's 150k version 113 (23:17 UTC); our 58001479 (24.69692) |
| dfthcsos | `e2057d61` (HW-18) (npz `ddce9a5b`) | 308,604,860.13 | 10.87345 | 427 | 15,317.00 |  | manwithacat Hedge Wizardry version 22 (22:50 UTC run) |
| dfthcsos | `ee4aab64` (npz `b463690f`) | 309,206,676.09 | 10.85229 | 427 | 15,347.00 |  | Kirill Tymchishin Quantum Compilation 19 version 3 (20:48 UTC run); our 57998728 and version 17 of this notebook (24.65425) |
| dfthcsos | HW-19 with our R55 E weights (npz `182f23ff`, not in this zip) | 306,022,568.13 | 10.96520 | 427 | 15,277.00 | | ours, measured, not submitted (section 4) |

Unsalted, truncated to 5 decimals as the leaderboard does: this zip's invsqrt with the cheapest public chemistry (21d6f276) and the public DQI whose leaderboard k is known (748b01a7, k 0): **24.72061**; with our fd0ef09e at k 0 in place of 748b01a7: **24.72092**; this zip (fd0ef09e and our R55 weights): **24.73387**; with our R55 E weights in place of this zip's (not in this zip): 24.73946. The two invsqrt files at the top tie within our verifier's resolution (0.10 apart in cost at default shots).

## 3. The k on the leaderboard

**The rule.** The DQI cost is R(k) x qubits^2 x Toffolis, where k is the number of failed shots among the verifier's 102,400 and R is the verifier's repetition factor at the Clopper-Pearson bound: R(0) = 1.191260, R(1) = 1.196731 (+0.459%), R(2) = 1.201388 (+0.389%), R(3) = 1.205584. The score takes a cube root, so one failed shot costs 0.153%. Which shots a file meets is set by sha256(file hash + salt): the same bytes face the same tests on a split, and any byte change is a new draw.

**This file.** fd0ef09e and its base 993c7038 each failed 1 shot in 307,200 (3 paired seeds of 102,400 shots), both at the same seed; an independent review counted 6 failures in 614,400 shots for 748b01a7, the file below. Here salt A gives k = 0 (24.73387) and salt B gives k = 0 (24.73386). **On the hosts' Public salt it drew k = 0**: our submission 57994004 (same `dqi.kmb`, same `invsqrt.kmb`, older chemistry) read 24.59450, within 2e-6 of the k 0 prediction (24.594498, unsalted). Submissions 57996192, 57998065, 57998728, 58001479, 58002211, 58002838, 58003999 and 58004424 hold the same two files, so they meet the same draw: they read 24.61149, 24.61180, 24.65425, 24.69692, 24.72061, 24.65425, 24.73387 and 24.72091; where we logged a k 0 prediction, the reading lies within 1e-5 of it (for 58003999: 24.733872).

**What follows from it.**
1. The rule we registered before the draw still stands: an edit smaller than one failure does not pay for a new draw against a file with a measured k 0: against 748b01a7 (k 0) this edit is 0.0037% and breaks even at P(k 0) 0.9919. That is why our sub_036 build kept 748b01a7. Our hourly loop prices a member at equal k and shipped fd0ef09e at 17:58 UTC; that one draw came out k 0. A swap trades a known k for a new draw; this one landed well, which does not make the next swap a good bet. The chemistry has no such draw: its cost does not depend on the salt.
2. The final board scores the Private split with another salt, a new draw for every file, ours and everyone's. There no k is known in advance, and the cheaper file wins in expectation: fd0ef09e is 0.0035% cheaper than 993c7038 and 0.0037% cheaper than 748b01a7 at equal k. For these files at salt B, k = 1 reads 24.69611 and k = 2 reads 24.66416 (truncated, as the ladder above prints them).
3. Rank DQI files by their measured leaderboard k, then by unsalted cost. Our own record: our version 12 read 23.86954 on the leaderboard against 23.90603 at our salt (one failed shot there); Kirill Tymchishin's exact-gauge notebook (version 25) met k = 1 with DQI 807b5129; our sub_022 met k = 1 at salt A and k = 0 at salt B.

## 4. What is ours: the rewrite stack, measured

Each DQI step was checked with the official verifier at paired seeds (errors equal to the base at every seed), a bit-parallel differential simulator against the base (0 differing shots) and planted defects that went red. Each chemistry step was checked with the official verifier unsalted and at 3 fresh salts (equal cost to the last digit), on the official x86-64 build, and with planted defects that went red. A fresh reviewer agent repeated the checks where the review column says so. All are exact except the rare-branch cut.

| step | base | what it does | effect (DQI: Toffolis per shot) | review | leaderboard |
|---|---|---|---:|---|---|
| R41 product caching | SomeJoint's 892-qubit decoder | one Toffoli writes a repeated product onto a wire proven zero and idle; later uses become CNOT, CZ or three CNOTs; the copy is cleared by an X measurement | -2,577 (-0.638%), 7 paired seeds | HOLDS | 23.88529 (1 Nov) |
| R42 clearing by measurement (MBU) | the cached file | 24 clearing blocks replaced by an X measurement and a phase fix; 12 use manwithacat's HW-07 two-wire ladder | -171.0, 3 paired seeds | not reviewed | 23.90992 (2 Nov) |
| second caching pass | the MBU file | the pipeline again on its own output | -6.1 | not reviewed | **23.91003** (2 Nov) |
| R43 proven links | that file | 38 more cached products, each equality proven for every input (2,343 links by exhaustive evaluation, 37 by a CP-SAT miter) | -37.9 (reviewer -38.0 at 2 fresh salts) | HOLDS | not submitted |
| R47 dead Toffolis | R43 | 11 Toffolis whose control a solver proves zero on every input, 1,000,000 operations back | -11.000 | HOLDS | not submitted |
| R48 port to yoyobar's 892-qubit decoder | yoyobar, 2 Nov | one caching pass, then 11 proven-dead Toffolis removed and 33 proven chains | -21.1, then -43.9 (reviewer: -44.000 in every simulated configuration) | HOLDS | not submitted |
| R48b CP-SAT links | R48 | 5 more chains from links a CP-SAT solver proves | -4.8 to -5.1 (reviewer: -5.000 in simulation) | HOLDS | not submitted |
| R50 rare-branch cut (approximate) | R48b | 240 Toffolis in 17 rare branches removed; 16 firings in 33.5 million sampler shots, all on inputs where the base already fails; expected cost -0.052% against a -0.05% bar registered before the held-out pass | -240.000 | HOLDS (as registered) | not submitted (local 23.95305) |
| R51 rare-branch search | R50 | fail-coincident gates on our own file | best case -0.0227% against the -0.05% rule | closed at its feasibility stop | none |
| R52 port to the 891-qubit file | 748b01a7 | 15 unconditional cached chains | -15.000 exact; official verifier -15.035 pooled over 6 paired seeds | HOLDS | not shipped (section 3) |
| **R41 on 993c7038** (this zip) | yoyobar's 993c7038 | the R41 pipeline, run by our hourly loop on the newest public DQI | **-13.816** (3 paired seeds: -13.6, -14.1, -13.7; errors 1 / 1) | pipeline gates (R41 method HOLDS) | **24.59450** (57994004), then every reading in section 3 |
| R53 chemistry weight refit | manwithacat's HW-16 | W and H2_I refit at fixed words: descent along the active constraint surface (error_2, E_gap and a pinned eigen-block held) with exact restoration, 2e-7 Ha margins; the 15 angle files and every other npz key byte-identical | chemistry cost -0.0037% (310,821,125.36 to 310,809,516.04) | HOLDS | **24.61180** (57998065, against 24.61149 without it) |
| R54 on HW-17 | manwithacat's HW-17 | the R53 descent continued at HW-17's words | -0.0037% (310,780,568.95 to 310,769,136.66) | HOLDS | not submitted: a cheaper public chemistry came first |
| R54 K | Quantum Compilation 19 chemistry (our version 17) | the R54 weights at its words (the same words, checked) | -0.0029% (309,206,676.09 to 309,197,662.25) | cost re-measured by the reviewer | not submitted |
| R55 A, B | Syed Asad Ali's c3a41b23 | the R53 descent with a 3e-5 pin window and the pinned eigenspace re-identified live | A -0.0889%, B -0.1127% (307,606,537.91 to 307,259,903.99) | official x86-64 equal (B); not reviewed | not submitted: HW-19 came first |
| **R55 D** (this zip) | manwithacat's HW-19 | the same descent with error_1 held as a constraint as well, at HW-19's words (equal to c3a41b23's), from the npz's own W and H2_I; margins 2.002e-7, 2.002e-7 and 2.002e-7 Ha (error_1, error_2, E_gap) | **-0.16072%** (306,723,130.32 to 306,230,171.25; lambda_eff 47.019778 to 46.944209) | HOLDS (fresh salts, Mac and x86-64) | **24.73387** (58003999, against 24.72061 for 58002211 without it) |
| R55 E | manwithacat's HW-19 | D's descent run further (chained restarts) | -0.22840% (306,723,130.32 to 306,022,568.13; lambda_eff 46.912384) | HOLDS (fresh salts, Mac and x86-64) | not submitted; the auto loop formula's estimate at DQI k 0: 24.739464 |

A plain augmented-Lagrangian refit (our R10-A) ended above the start on HW-16, a nonsmooth corner with 8,507 weights at |w| < 1e-9; the descent along the constraint surface is what moved it. The same idea, a constrained lambda_eff refit at fixed words with the gates held, is manwithacat's HW-03 technique (his credit: anazemcev's projected L-BFGS); heliosli first showed the refit up to the error gate, as Syed Asad Ali credits.

The hourly loop that would have submitted the later DQI steps stopped on 2 November; when it restarted on 4 November the 891-qubit decoder was 0.45% cheaper than our best 892-qubit file (qubits^2 -0.22%, Toffolis -0.23%), and our caching finds only 13.8 to 15 Toffolis per shot on it (R52, R41 on 993c7038).

**invsqrt, earlier.** Our 63-qubit XAG (102,664.24, 27 October) and XAG2C (102,349.24, 28 October, 5 Toffolis fewer, equal on the official x86-64 build). XAG2C was public in our dataset from 29 October 00:06 UTC, and that day the top public bundles (heliosli, Ahmed Berat Ozer, Kirill Tymchishin, sigmaborov) shipped it. SomeJoint's genealogy for today's invsqrt reads "mrmeows and team selenium → Akmal Xodarev (busyaprime), 63 qubits → yoyobar with GPT-6 Astra, 62 qubits → ...". Today's file costs 97,921.70 at salt B, 4.33% below XAG2C.

**Our leaderboard path:** 22.86842 (29 October), 23.88529 (1 November), 23.91003 (2 November), 24.59450 (4 November, 17:58 UTC), 24.61149 (19:17 UTC), 24.61180 (20:31 UTC, with our R53 weights), 24.65425 (21:01 UTC), 24.69692 (23:26 UTC, Syed Asad Ali's chemistry c3a41b23), 24.72061 (5 November, 00:00 UTC, manwithacat's HW-19) and **24.73387** (00:42 UTC, this zip: HW-19 with our R55 weights).

## 5. Cost per task against Google's reference

| task | cost formula | Google's reference: qubits, Toffolis, cost | these files: qubits, Toffolis (unsalted), cost at salt B | reference / cost |
|---|---|---|---|---:|
| invsqrt | qubits x Toffoli-equivalent count (rotations included) | 260, 7,735, 2,076,774.23 | 62, 1,281.66, 97,921.70 | **21.2085** |
| DQI | R(k) x qubits^2 x Toffolis | 1,893, 5,725,108.38, 2.443946e+13 | 891, 396,904.56, 3.753602e+11 (k 0) | **65.1094** |
| chemistry | lambda_eff x Toffolis x qubits of the block encoding | 730, 93,237, 3,355,599,588.32 | 427, 15,277, 306,230,171.25 (lambda_eff 46.944209) | **10.9578** |

Geometric mean at salt B: **24.73386**; at salt A (DQI k = 0): **24.73387** (truncated to 5 decimals, as the leaderboard shows scores). The Toffoli column is the unsalted mean of our verifier; the salted counts are in the verifier lines printed above. The reference columns are our unsalted runs of the hosts' sample circuits; their cost on the leaderboard's salts is secret, so the metric here uses ours.

## 6. How this notebook checks itself, credits and licence

The hosts' metric code runs unchanged. A wrapper keeps a copy of each verifier's report (the lines printed after the scores); it returns the same report. The salts are ours: sha256 of a fixed text per split and task, so anyone can rerun them. The zip is written once from the dataset files, checked entry by entry, unpacked, and the metric reads the unpacked files.

| author | what | source | version | licence |
|---|---|---|---|---|
| **busyaprime** (Akmal Xodarev) | `dqi.kmb` fd0ef09e: our R41 exact product caching on yoyobar's 993c7038 (-13.816 Toffolis per shot); the W and H2_I arrays of `dfthcsos/submission.npz`: our R55 refit at HW-19's words and circuits (R53 method, -0.16072% chemistry cost against HW-19). Also ours: the field prices, the failure ladder, this notebook | [notebook](https://www.kaggle.com/code/busyaprime/lb-24-65425-top-30-qcc-notebooks-re-verified), [dataset](https://www.kaggle.com/datasets/busyaprime/33-qcc-v8-members) | this version (submission 58003999); dataset version 11 | Apache 2.0 |
| SomeJoint (Agniv Banerjee) | `invsqrt.kmb` af469847: their version 33 circuit with Kirill Tymchishin's two forced phase bits; the 892-qubit decoder line and narrow return under the DQI (SomeJoint V34); the fixed-word refit line behind the chemistry weights, as Kirill Tymchishin and qwertykeypadapple credit it | [notebook](https://www.kaggle.com/code/somejoint/quantum-circuits-24-65-local-gm-chem-refit), [qcc-ladder-parts](https://www.kaggle.com/datasets/somejoint/qcc-ladder-parts) | notebook V34 (af469847); V35 (as Kirill Tymchishin cites it); Kaggle version 36 at 21:42 UTC | Apache 2.0 |
| Alex Chilton (alexchilton) | the output `invsqrt.kmb` (and the 993c7038 base) were copied from; his rewrite of one accumulator site, five Toffolis as four, under af469847 (SomeJoint V34); with jday96314, the decoder design SomeJoint V34 names first | [notebook](https://www.kaggle.com/code/alexchilton/24-59-lb-verified-three-task-portfolio) | run of 4 Nov 15:59:32 UTC (his text: "v87, Kaggle v103") | Apache 2.0 |
| Kirill Tymchishin (kirilltym) | the two forced phase bits (a zero certificate before two HMRs) and five AND merges inside af469847, as SomeJoint V34 credits them; reused c3a41b23 in Quantum Compilation 19 version 4 (run 21:44:39 UTC), after Syed Asad Ali V3 shipped it first (21:28:43 UTC); his version 5 (run 00:12:57 UTC) audits HW-19's loaders with Isabe11aM00re V4's weights, priced in section 2 (not in this zip) | [Four Loaders](https://www.kaggle.com/code/kirilltym/quantum-circuits-four-loaders-eight-toffolis), [Quantum Compilation 19](https://www.kaggle.com/code/kirilltym/quantum-compilation-19) | V10; Quantum Compilation 19 versions 4 (run of 4 Nov 21:44:39 UTC) and 5 (run of 5 Nov 00:12:57 UTC) | Apache 2.0 (V10); Quantum Compilation 19: Apache 2.0 as its sources state |
| Syed Asad Ali (syed3000) | **first public release of the chemistry under this zip** (c3a41b23): `angle_k_0..3` byte for byte, and the npz whose U, H1_I, Hsym_lower, tree_edges and angle_words stay byte for byte (his own 8-group (8, 143, 45) table, as his V3 text says) and whose W and H2_I are the start of our descent; his text names its parts: marculera's DF-THC pipeline and Ozer's progressive rounding, with his own loader compiler, lattice-aware rounding, table and weight refit. Also the 891-qubit C1 decoder under 993c7038 (SomeJoint V34, yoyobar V28) and an invsqrt line | [own-circuit portfolio](https://www.kaggle.com/code/syed3000/vqcc-own-circuit-portfolio-notebook), [24.43 Portfolio](https://www.kaggle.com/code/syed3000/vqcc-24-43-portfolio) | own-circuit portfolio V3 (run of 4 Nov 21:28:43 UTC, scriptVersionId 365752919); V2 | Apache 2.0 (his text: "Public portfolio (Apache-2.0)") |
| manwithacat (James Barlow) | **HW-19, the chemistry circuits of this zip**: the 15 angle files byte for byte. HW-19 is his HW-18 padded-row step on Syed Asad Ali's new word table: qwertykeypadapple's kernel search re-run with the 12 never-read rows left free, loaders 4 to 14 at 280 Toffolis per pass instead of 282, loaders 0 to 3 kept as shipped (his text). His HW-03 technique, a constrained lambda_eff refit at fixed words with the error gates held as constraints and a step back onto them (his credit: anazemcev's projected L-BFGS), is the same idea our R53 method implements. HW-16 (V19) and HW-17 (V20) were the bases of our R53 and R54 refits; his HW-07 two-wire clean ladder is in our R42 rewrite | [notebook](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook), [dataset](https://www.kaggle.com/datasets/manwithacat/vqcc-hedge-wizardry) | Hedge Wizardry version 23 (HW-19, run of 4 Nov 23:33:23 UTC); V19 (HW-16); V20 (HW-17) | Apache 2.0 (his text names the licence of each part; the input dataset vqcc-apache-public-circuits) |
| qwertykeypadapple | the kernel search (`kernel_search.py`) that manwithacat ran unmodified for HW-19's loaders 4 to 14, as his HW-19 text credits it (relations admitted one at a time by pairing cost, on Lera's tensor-QROM compiler) | [QCC Kernel Search 24.65](https://www.kaggle.com/code/qwertykeypadapple/qcc-kernel-search-24-65), [portfolio dataset](https://www.kaggle.com/datasets/qwertykeypadapple/qcc-kernel-search-portfolio) | V1 and its dataset (as manwithacat cites them) | Apache 2.0 (his text: everything they wrote; the circuits keep their authors' terms) |
| Lera (marculera) | the DF-THC pipeline and the layout Syed Asad Ali's own (8, 143, 45) table is built in (as his text and manwithacat's HW-19 text name them), and the emitter HW-19's loaders are emitted with (manwithacat's credit) | [notebook](https://www.kaggle.com/code/marculera/df-thc-10x-compact-groups-from-the-hamiltonian), [dataset](https://www.kaggle.com/datasets/marculera/dfthc-compact-pipeline) | Compact Groups scriptVersionId 365256248 (as Kirill Tymchishin cites it); notebook v10 (as manwithacat cites it) | Apache 2.0 |
| Lera's own credits (as qwertykeypadapple V1 relays them) | Ahmed Berat Ozer (ahmedberatozer), kozykappa, Kozykorpesh and Sumit Chongder, Artem1410 (anazemcev), Phuc Thai, haideptry, SomeJoint, mrmeows, heliosli, lightningv08, Michael Rustad, k256net and Dmitrii Gluzdov; mrmeows's cached-monomial emitter design and SomeJoint's coded low bit behind her compiler | [Lera's notebook](https://www.kaggle.com/code/marculera/df-thc-10x-compact-groups-from-the-hamiltonian) | as relayed in qwertykeypadapple V1 | Apache 2.0 |
| Ahmed Berat Ozer (ahmedberatozer), heliosli | chemistry, as Syed Asad Ali V3 names them: Ozer's progressive rounding; heliosli first showed the weight refit up to the error gate | [Ozer](https://www.kaggle.com/code/ahmedberatozer/quantum-ai-df-thc-group-compression), [heliosli](https://www.kaggle.com/heliosli) | heliosli v60, as Syed Asad Ali's V3 text cites it (no link there); Ozer not versioned in his text | Apache 2.0 |
| heliosli, Dmitrii Gluzdov | heliosli: the scratch top-bit idea Lera's builder implements; Dmitrii Gluzdov: the public description of plan search and relation search on this compiler (as qwertykeypadapple V1 credits them) | [heliosli](https://www.kaggle.com/code/heliosli/the-dataset-is-public-now-enjoy), [Dmitrii Gluzdov](https://www.kaggle.com/code/dmitriigluzdov/quantum-circuit-compilation-from-source) | not versioned in the text | Apache 2.0 |
| qiuqiuh (Qiuqiu) | the cut of one accumulator's four Toffolis to two, made first, as SomeJoint V34 credits it | [notebook](https://www.kaggle.com/code/qiuqiuh/qcc-refresh-v65w-sx-sy7-inverse) | V1 (09:09 UTC, 4 Nov) | Apache 2.0 |
| yoyobar | 993c7038, the base of our `dqi.kmb`: one further CCZ saved on his 748b01a7, his second rewrite of Syed Asad Ali's decoder (yoyobar V28, with GPT-6 Astra as he credits it); the 62-qubit invsqrt rework in the invsqrt line | [notebook](https://www.kaggle.com/code/yoyobar/lb-22-99-invsqrt-101-62-qubits) | V28 (993c7038); V27 (748b01a7) | notebook Apache 2.0; circuits under the competition rules (section 6b) |
| Ali Haydar Ozdag (ahoirg) | the flag-carry idea in the DQI line, as SomeJoint V34 and yoyobar V28 credit it | [notebook](https://www.kaggle.com/code/ahoirg/qcc-reproducible-circuit-portfolio) | V2 (page at our 4 Nov read) | Apache 2.0 |
| mrmeows and team selenium, Ahmed Berat Ozer, Ehan Mallick | the start of the invsqrt line, the phase patch, two AND merges (SomeJoint V34 genealogy) | [mrmeows](https://www.kaggle.com/code/mrmeows/21-0-circuits-let-s-all-reach-the-plateau), [Ahmed Berat Ozer](https://www.kaggle.com/code/ahmedberatozer/quantum-ai-df-thc-group-compression), [Ehan Mallick](https://www.kaggle.com/code/ehanmallick/invsqrt-20-65-two-3-to-2-and-merges-on-y6225) | phase patch V15 (as Alex Chilton cites it); others not versioned in the chain | Apache 2.0 |
| Isabe11aM00re, Ayodeji (ayodejiibrahimlateef) | Isabe11aM00re: v66s33w version 4 (run 23:25:46 UTC), the first public ship in our pulls of the weight release 8bf7a9d1 on Syed Asad Ali's table, priced in section 2 (not in this zip); the family HW-17 builds on, as manwithacat V20 names it. Ayodeji: angle loaders 4 to 14 of HW-16, as manwithacat V19 credits them, and the first public notebook with Lera's compact-group part, as SomeJoint V34 credits it (bases of our R53 and R54 measurements; not in this zip) | [Isabe11aM00re](https://www.kaggle.com/code/isabe11am00re/qcc-v66s33w-submission), [Ayodeji](https://www.kaggle.com/code/ayodejiibrahimlateef/vqcc-24-56308-local) | v66s33w version 4 (page data 01:20 UTC); Ayodeji v4 (as V19 cites it) | Isabe11aM00re: her dataset LICENSE.md releases her own work under Apache-2.0 (as Kirill Tymchishin relays it); Ayodeji: Apache 2.0 |
| lightningv08 (Vladislav Lavrentev), matousakura | the kernel-relation compiler ideas and quotient pairing (his NOTICE credits Ahmed Berat Ozer and mrmeows) and the extended-relation formula behind HW-12 to HW-16, as manwithacat V19 credits them | [matousakura](https://www.kaggle.com/code/matousakura/best-of-public-portfolio-vqcc-24-0x-class); lightningv08 via [manwithacat V19](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook) | not versioned in V19 | Apache 2.0 |
| Google Quantum AI | the three verifiers and kickmix, unchanged; the metric code, verbatim | [competition data](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/data), [metric](https://www.kaggle.com/code/metric/google-quantum-ai-metric) | as mounted on 4 Nov | verifiers Apache 2.0 (`verifiers/LICENSE.txt`); metric as published on Kaggle |

Inherited lineage, as SomeJoint V34 names the fullest public chain: Agniv Banerjee (SomeJoint), Dmitrii Gluzdov, ViberTeam / Artem1410 / anazemcev, manwithacat, Phuc Thai (DePie), Kozykorpesh (kozykappa), Michael Rustad, Akmal Xodarev (busyaprime), marsyas, Sumit Chongder, Rudra Bhaskar, Zongao Bian, Mizero Lucky Gall, Gu et al. and Guang Hao Low. Each upstream notebook names further authors of its own parts; their notices stay with their files. The dataset's `provenance.json` gives every file's source, version and chain as each source states it.

**Versions.** This version (18): our DQI rewrite fd0ef09e and our R55 weights on manwithacat's HW-19 chemistry, with SomeJoint's invsqrt; the hosts' metric at two salts, the priced field map, the failure ladder and the refit history. Previous public version (17): LB 24.65425, our DQI rewrite with Kirill Tymchishin's Quantum Compilation 19 chemistry; earlier versions are in the version history.

---

## 🔑 Kern-Technik in 3 Sätzen

1. **Product Caching (R41):** Ein einziger Toffoli schreibt ein wiederkehrendes Produkt auf einen nachweislich nullen und idle Wire; alle späteren Verwendungen werden daraus zu billigen CNOT/CZ-Operationen, und die Kopie wird per X-Messung rückstandslos gelöscht — das spart hier 13.8 bis 2577 Toffolis pro Shot, ohne ein einziges Bit der Dekodierung zu ändern.
2. **Der Q²-Faktor dominiert:** Die DQI-Kosten sind R(k) × Qubits² × Toffolis, also zählt die Qubit-Breite doppelt — deshalb ist der Sprung von 892 auf 891 Qubits (−0.22 % in Q²) zusammen mit −0.23 % Toffolis der eigentliche Gewinn, und deshalb lohnt sich ein Toffoli-Sparen von 13.8/Shot nur, weil es auf derselben 891er-Basis passiert.
3. **Die Failure-Penalty entscheidet den Score:** k fehlgeschlagene Shots von 102,400 heben R von 1.191260 (k=0) auf 1.196731 (k=1); durch die Kubikwurzel im Score kostet ein einzelner Fehlschlag 0.153 %, und weil k vom Salt (sha256(file+salt)) gesetzt wird, tauscht man bei jedem Byte-Wechsel einen bekannten k gegen eine neue Lotterie — daher rankt man DQI-Dateien erst nach gemessenem Leaderboard-k, dann nach unsalted Cost.

## ⚠️ Häufigste Fehlerfalle

Den **Q²-Faktor zu unterschätzen** und nur auf Toffolis zu schauen. Ein Decoder, der 1 Qubit mehr braucht (892 statt 891), ist trotz weniger Toffolis teurer, weil Qubits² in der Kostenformel steht — busyaprimes eigener hourly loop hat genau das am 4. November neu bemerkt: der 891er war plötzlich 0.45 % günstiger als der beste 892er, und das Caching fand darauf nur noch 13.8–15 Toffolis/Shot. Zweitgefährlichste Falle: **ein Byte-Wechsel als kostenlosen Toffoli-Gewinn zu verbuchen**, obwohl er den DQI-k neu würfelt — eine Edit kleiner als ein Fehlschlag amortisiert sich gegen eine Datei mit gemessenem k=0 nicht (Break-even bei P(k=0)=0.9919).

## 📝 Lern-Notizen (füll das selbst aus)

- [ ] Decoding-Prinzip verstanden: Reed-Solomon-Syndrom über GF(2¹²), RS(4095, 4025); der Circuit muss 102,400 Test-Shots fehlerfrei (k=0) oder mit minimalem k überstehen.
- [ ] Cost-Formel R(k)×Q²×T internalisiert: R(0)=1.191260, R(1)=1.196731; Q² heißt, 891→892 Qubits ≈ +0.22 % Kosten; ein Fehlschlag ≈ 0.153 % Score (Kubikwurzel).
- [ ] Product Caching nachvollziehbar: Produkt auf nullen/idle Wire schreiben (1 CCX), später CNOT/CZ/3×CNOT, per X-Messung löschen; R41 = −2577 Toffolis, R41 auf 993c7038 = −13.816.
- [ ] Verbindung zu invsqrt/Chem: invsqrt = Q×Toffoli-äquivalent (kein Q²!), Chemistry = λ_eff×T×Q (linear in Q); nur DQI hat den quadratischen Q-Faktor → dort zählt Breite am meisten.
- [ ] Frage die ich noch habe: Warum bricht das Caching auf der 891er-Basis (nur 13.8–15 Toffolis) so viel früher ab als auf der 892er (2577)? — Vermutung: die 891er-Geometrie hat weniger nachweislich-nullen/idle Wires für wiederverwendbare Produkte.
