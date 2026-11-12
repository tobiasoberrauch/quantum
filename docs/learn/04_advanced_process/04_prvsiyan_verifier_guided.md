# Verifier-Guided Quantum Circuit Optimization – einen Leaderboard-Score als Fehler-Zahl lesen

> **Lernziel:** Was eine Leaderboard-Zahl in dieser Competition *kann und nicht kann*: wie man sie als Anzahl fehlgeschlagener DQI-Shots liest (die "Ladder"), warum ein sauberer öffentlicher Score nichts über den finalen Leaderboard sagt, warum zwei finale Picks *verschiedene* DQI-Bytes tragen sollten, und was die seltenen Decoder-Fehler in Toffolis kosten. Kein einziger Circuit ist von prvsiyan – der Beitrag ist die *Analyse* und das *Tooling* (`draw_report`), um Scores zu interpretieren.
> **Dauer:** ~35 Minuten
> **Quelle:** prvsiyan | 30 votes
> **Fokus:** Verification culture / Negative results / Credit chain

---

> **Hinweis:** Der Originaltext des Notebooks (Markdown **und** Code-Zellen) steht unten **auf Englisch, unverändert** ("as-is"). Deutsche Anmerkungen sind als 📌-Callouts dazwischen gesetzt. Reine Daten-Zellen (große Lookup-Tabellen) sind als kurzes, klar markiertes Exzerpt wiedergegeben.

**Local score with the official verifiers: 25.09600.** Every member file is the same bytes as in a public notebook whose badge shows a clean draw: the invsqrt file from Atakan Aldemir's [notebook](https://www.kaggle.com/code/atakanaldemir/qcc-early-measurement-and-domain-aware-inverse) (25.09592 on the public leaderboard), and the DQI file and the chemistry weights from Isabe11aM00re's [QCC v66s33w submission](https://www.kaggle.com/code/isabe11am00re/qcc-v66s33w-submission) (25.09058). The same bytes meet the same draws, so those badges pin this archive's public score to between 25.095965 and 25.095995 (the arithmetic is in the frontier section). The step over the best public notebook comes from combining other authors' files, not from a circuit of ours. This notebook's own public score is the one Kaggle shows on this page. It rebuilds the archive from public circuits, re-runs the three official verifiers on it, and then works through what a leaderboard number in this competition can and cannot tell you. None of the circuits is ours. Each is credited by name at the end.

| Task | Circuit | Cost | Ratio to reference |
|---|---|---:|---:|
| Invsqrt, 62 qubits | Atakan Aldemir `bbfa9675880e`: one redundant controlled swap deleted from maoxin123's `95621d7ee3e1`, which is Hosen42's measure-first rewrite on Syed Asad Ali's version-11 file | 95,957.89 | 21.6426 |
| DQI, 892 qubits | Isabe11aM00re `4432ec5fd63d`, on Kirill Tymchishin's `337cb0497b4d`, a measurement-order rewrite of Ahmed Berat Ozer's `77bace9de69c` | 374,735,446,629 | 65.2179 |
| Chemistry, 427 qubits | Syed Asad Ali's table and loaders, Isabe11aM00re's refinement of maoxin123's version-3 weights, `5bd3575736fd` | 299,662,438 | 11.1979 |

On 2026-11-07 at about 21:50 UTC the best public notebooks showed 25.09592 (Atakan Aldemir), 25.09058 (Isabe11aM00re) and 25.09052 (Kirill Tymchishin, Alex Chilton and yoyobar), and the top of the leaderboard showed 29.30. Version 30 of this notebook read 24.94111. Most of the step to 25.09 came from one task: Syed Asad Ali's rebuild of the invsqrt circuit, Hosen42's measure-first rewrite and Atakan Aldemir's deletion of a redundant swap cut its cost by 1.83 %. For each task this archive takes the cheapest public file whose public draw is known to be clean: Atakan Aldemir's invsqrt file and Isabe11aM00re's DQI file and weights. No public notebook carried this set when we checked. The distance to the leaderboard is far larger than anything that separates the public notebooks.

**What you can take from here**

1. How to read a board score as a count of failed DQI shots, with the ladder computed from the verifier's own functions.
2. Why a clean public score promises nothing about the final leaderboard, and how to compare DQI files instead.
3. Why two final picks should carry different DQI bytes, and what that is worth.
4. `draw_report`, one function you can point at your own `dqi.kmb`, and a live run of it on two current files.
5. What the rare decoder failures are worth, priced in Toffolis, so you can tell whether a fix pays.
6. Where the step from 24.94 to 25.09 came from, task by task, and one rewrite that worked in two tasks.

**Where to read next.** For what one DQI qubit is worth in Toffolis, read [Alex Chilton's portfolio notebook](https://www.kaggle.com/code/alexchilton/24-94-lb-verified-three-task-portfolio), which gives about 1,100 at 877 qubits, and [manwithacat's hedge notebook](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook), which gives about 960 at 889 qubits. For how each circuit works, read [Dmitrii Gluzdov's walkthrough](https://www.kaggle.com/code/dmitriigluzdov/quantum-circuit-compilation-from-source). For the invsqrt rebuild, read [Syed Asad Ali's notebook](https://www.kaggle.com/code/syed3000/vqcc-own-circuit-portfolio-notebook), for the check that removed a controlled swap, [Atakan Aldemir's notebook](https://www.kaggle.com/code/atakanaldemir/qcc-early-measurement-and-domain-aware-inverse), and for the measurement-order identity, [Kirill Tymchishin's notebook](https://www.kaggle.com/code/kirilltym/quantum-circuits-pi-gauge-weight-refinement). For the history of the frontier, read [manwithacat's frontier charts](https://www.kaggle.com/code/manwithacat/the-real-150k-was-the-friends-we-made).

**What the run does.** It finds every member in the pinned dataset `prvsiyan/vqcc-verified-best-of-circuits-1106a` by SHA-256 and size, writes `/kaggle/working/submission.zip` with a fixed layout, runs the three official verifiers on it with an empty salt, and then runs the DQI verifier on four published salts for two files. It trains, searches and tunes nothing. The four plumbing cells are collapsed: use Show hidden code to read them.

## How the score works

There are three benchmarks. Each verifier simulates a submitted circuit on many test inputs. If a required test fails, the submission is rejected. Otherwise the verifier returns a cost, and a lower cost is better.

For each benchmark the improvement is `baseline_cost / cost`, where the baseline is the competition's reference submission. The overall score is the **geometric mean** of the three improvements, that is the cube root of their product. A reference submission scores 1.0, and halving every cost scores 2.0. Because the mean is geometric, a 10 % gain on one benchmark is worth the same as a 10 % gain on any other.

Three details matter for this archive:

- **Invsqrt (62 qubits).** The cost is a Toffoli-equivalent count measured on the verifier's test shots: 62 qubits x 1,547.71 Toffoli-equivalents = 95,957.9.
- **DQI (892 qubits).** The cost is `R * Q^2 * T`, where `Q` is the qubit count, `T` is the mean Toffoli-like count per shot, and `R = ln 2 / -ln(1/2 + 2 sqrt(eps))` is a repetition factor. `eps` is a one-sided Clopper-Pearson upper bound on the failure rate at confidence 1 - 2^-128. A circuit with no failed shots out of 102,400 gives `eps` of about 8.66e-4 and `R` of about 1.1913. Failed shots are allowed, but each one raises `eps`, and so raises `R`. Here: 1.19126 x 892^2 x 395,356.0 = 374,735,446,629.
- **Chemistry (DFTHC-SOS, 427 qubits).** The verifier first checks the accuracy of the loaded words: `error_1` and `error_2` must each be at most 20 mHa, `Lambda` must exceed 49, and the SOS gap `E_gap` must exceed 3.914898 Ha. These checks depend only on the circuits and `submission.npz`, not on the salt. The margins in this archive are thin: `error_1` is 19.99999977 mHa, `error_2` is 19.99999978 mHa and `E_gap` is 3.9148980002 Ha, a margin of about 2.4e-10 Ha, so a different build of the verifier could reject it. Once the words pass, the cost is set by the circuits, the Givens tree and the factorization: here `lambda_eff` 46.891993 x 14,966 Toffolis x 427 qubits = 299,662,437.6.

> **📌 Prozess-Hinweis:** Die dünnen Chemie-Margins (2.4e-10 Ha über dem E_gap-Boden) sind ein bewusster Prozess-Point: prvsiyan warnt, dass ein *anderer Build des Verifiers* die Submission ablehnen könnte. Das ist die ehrliche Kehrseite des "verifizierten" Portfolios – Verifikation ist an den konkreten Verifier-Build gebunden.

```python
import glob
import hashlib
import json
import math
import shutil
import stat
import struct
import time
import tokenize
import zipfile
import zlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

WORK = Path('/kaggle/working')
RECEIPTS = WORK / 'receipts'
RECEIPTS.mkdir(parents=True, exist_ok=True)
import os as _os
_hits = []
for _d, _dirs, _files in _os.walk('/kaggle/input'):
    if 'verify_submission_invsqrt.py' in _files and _d.endswith('invsqrt'):
        _hits.append(Path(_d).parent.parent)
print('competition candidates:', _hits[:5])
COMP = _hits[0] if _hits else Path('/kaggle/input/competitions/google-verifiable-quantum-circuit-compilation')
ARCHIVE = WORK / 'submission.zip'
# Members by content: name, SHA-256, size. Authors and licences are in the credits table at the end.
PLAN = json.loads(r'''{
  "members": [
    {"name": "invsqrt.kmb", "sha256": "bbfa9675880e91fd43e5280a50f8ba0eeb4e0473fc98ba6284673407c927cd68", "size": 548450},
    {"name": "dqi.kmb", "sha256": "4432ec5fd63d7d70aab92d32f719d47539d0ff66ae0cb0b964c914e01fece431", "size": 529241631},
    {"name": "dfthcsos/angle_k_0.kmb", "sha256": "d3aab7479fe3b8510e3af3797a14ec8d9bfa226d7aa7717ae4e93f496d2d9538", "size": 390615},
    {"name": "dfthcsos/angle_k_1.kmb", "sha256": "4595e5dcc982295db2520c8497219e1768757edf3aa9e706fa44b1716f996ed2", "size": 381353},
    {"name": "dfthcsos/angle_k_2.kmb", "sha256": "77dec28c5ebffe723fb58717a31c017d66c44cbec220bc3cc5a15a2fff051aa3", "size": 385773},
    {"name": "dfthcsos/angle_k_3.kmb", "sha256": "8e137a014a1325450eaf9ec15bc824475b757b3a05bbc542eed9cccfd6b5ec53", "size": 383561},
    {"name": "dfthcsos/angle_k_4.kmb", "sha256": "d9f2a0d739142a1d20789352c617cccc702a8f0b4b17f91971e4e4ef3e6f6c3f", "size": 337382},
    {"name": "dfthcsos/angle_k_5.kmb", "sha256": "bd0886bb6c3d5c04f5e1fd29dbd2562d1c7e5b1a7406bc1abde6819093a0880e", "size": 338559},
    {"name": "dfthcsos/angle_k_6.kmb", "sha256": "12c0c6f92d708ff7d852f2c6f36a40ecf4369249fa1f0ab4527b08e0152e7558", "size": 338608},
    {"name": "dfthcsos/angle_k_7.kmb", "sha256": "93dc9742392a0dd6e754aebbbea1519014292a56b6908dfce5ae417f2cde73d6", "size": 335389},
    {"name": "dfthcsos/angle_k_8.kmb", "sha256": "d43bd96b88e6ef38c7ea9e697856646af4259889b75d1bc67a94a1768670b5a6", "size": 337289},
    {"name": "dfthcsos/angle_k_9.kmb", "sha256": "a5960a572c39a3996b3919eb8bc18066b8aa78d3fc83bc7435d7e5550de3a2a6", "size": 342755},
    {"name": "dfthcsos/angle_k_10.kmb", "sha256": "f28f2ead2b7eb3d45aadf4e0bb9f9399c7d8f016247d7020ae39dbd9c062cace", "size": 340218},
    {"name": "dfthcsos/angle_k_11.kmb", "sha256": "7b9094ddc215c6c7db223fe319e6d2a6f67c1669f412e4d3281c280723df5b81", "size": 337990},
    {"name": "dfthcsos/angle_k_12.kmb", "sha256": "d49dfbfdb8cff3c3d680e4ef65a3d1a01db7a2fc666f49a522d7f58f50305e78", "size": 337720},
    {"name": "dfthcsos/angle_k_13.kmb", "sha256": "cb7e48a7029323a6ec11c0f6dede5f5e0443f67da92e0e6554ff9120b8279efd", "size": 336880},
    {"name": "dfthcsos/angle_k_14.kmb", "sha256": "07fcdcb75d3a9e7f2573e057376ec20b7a56bf9a53fe7d7f00fb351614c2003f", "size": 336049},
    {"name": "dfthcsos/submission.npz", "sha256": "5bd3575736fdf340231b18dcbbe35f1ff9e0e8606f6081258aa54f4d0f9e59eb", "size": 1851004}
  ],
  "reference_costs": {"dfthcsos": 3355599588.3155365, "dqi": 24439463583672.93, "invsqrt": 2076774.233715282},
  "source_summary": {"invsqrt.kmb": "Atakan Aldemir bbfa9675880e (one domain-redundant CSWAP deleted from maoxin123 95621d7ee3e1)", "dqi.kmb": "Isabe11aM00re 4432ec5fd63d (on Kirill Tymchishin 337cb0497b4d, on Ahmed Berat Ozer 77bace9de69c)", "dfthcsos/*": "npz 5bd3575736fd (Isabe11aM00re, on maoxin123 v3 weights) with Syed Asad Ali v9 loaders (one unit)"},
  "predicted_gm": 25.09598
}''')
MEMBERS = PLAN['members']
REF_COSTS = PLAN['reference_costs']
print('planned members:', len(MEMBERS))
print('competition kickmix present:', (COMP / 'kickmix' / 'kickmix.so').exists(), '| verifiers present:', (COMP / 'verifiers').exists())
```

```python
def sha_and_size(zpath, name):
    h = hashlib.sha256()
    n = 0
    with zipfile.ZipFile(zpath) as z, z.open(name) as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
            n += len(chunk)
    return h.hexdigest(), n

# Every submission.zip attached as a kernel output. Members are found by content (SHA-256 and size), not by path.
zips = sorted(glob.glob('/kaggle/input/**/submission.zip', recursive=True))
print('submission.zip files attached:', zips)
source_for = {}
for zpath in zips:
    try:
        with zipfile.ZipFile(zpath) as z:
            names = set(z.namelist())
    except zipfile.BadZipFile:
        continue
    for m in MEMBERS:
        if m['name'] in source_for or m['name'] not in names:
            continue
        digest, size = sha_and_size(zpath, m['name'])
        if digest == m['sha256'] and size == m['size']:
            source_for[m['name']] = zpath
# Fallback: members published as loose files in an attached dataset (Kaggle unpacks uploaded zips).
# They are still matched by SHA-256 and size, then packed into a scratch zip so the writer below reads one format.
import pathlib
LOOSE_ZIP = pathlib.Path('/tmp/loose_members.zip')
loose = []
for m in MEMBERS:
    if m['name'] in source_for:
        continue
    for p in sorted(glob.glob('/kaggle/input/**/' + m['name'], recursive=True)):
        data = pathlib.Path(p).read_bytes()
        if hashlib.sha256(data).hexdigest() == m['sha256'] and len(data) == m['size']:
            loose.append((m['name'], p))
            break
if loose:
    with zipfile.ZipFile(LOOSE_ZIP, 'w', compression=zipfile.ZIP_STORED) as z:
        for name, p in loose:
            z.write(p, arcname=name)
    for name, _ in loose:
        source_for[name] = str(LOOSE_ZIP)
    print('located', len(loose), 'members as loose files in attached datasets')
missing = [m['name'] for m in MEMBERS if m['name'] not in source_for]
print('located', len(source_for), 'of', len(MEMBERS), 'members; missing:', missing)
assert not missing, missing
print('sources used:', sorted(set(source_for.values())))
```

> **📌 Prozess-Hinweis:** "Members by content, not by path" ist robustes Design: egal in welchem ZIP oder Dataset eine Datei liegt, sie wird nur genommen, wenn SHA-256 *und* Größe zum Plan passen. Das eliminiert die ganze Klasse von "falsche Datei montiert"-Fehlern.

```python
# Deterministic stored ZIP: fixed 1980-01-01 timestamps, fixed attributes, STORED, names sorted, UTF-8 flag.
# The bytes depend only on the member bytes and names, so the local build and this notebook give the same SHA-256.
ZIP_DOS_TIME = 0x0000
ZIP_DOS_DATE = (0 << 9) | (1 << 5) | 1
ZIP_VERSION = 20
ZIP_EXT_ATTR = (0o100644 << 16)

def member_chunks(zpath, name):
    with zipfile.ZipFile(zpath) as z, z.open(name) as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            yield chunk

def member_crc32(zpath, name):
    crc = 0
    for chunk in member_chunks(zpath, name):
        crc = zlib.crc32(chunk, crc)
    return crc & 0xffffffff

def write_stored_zip(out_path, rows):
    """rows: (name, source_zip, size, crc32) in the order to write."""
    entries = []
    offset = 0
    with open(out_path, 'wb') as out:
        for name, zpath, size, crc in rows:
            name_b = name.encode('utf-8')
            out.write(struct.pack('<IHHHHHIIIHH', 0x04034b50, ZIP_VERSION, 0x0800, 0, ZIP_DOS_TIME, ZIP_DOS_DATE,
                                  crc, size, size, len(name_b), 0))
            out.write(name_b)
            written = 0
            for chunk in member_chunks(zpath, name):
                out.write(chunk)
                written += len(chunk)
            assert written == size, (name, written, size)
            entries.append((name_b, crc, size, offset))
            offset += 30 + len(name_b) + size
        cd_start = offset
        cd_size = 0
        for name_b, crc, size, off in entries:
            central = struct.pack('<IHHHHHHIIIHHHHHII', 0x02014b50, ZIP_VERSION, ZIP_VERSION, 0x0800, 0,
                                  ZIP_DOS_TIME, ZIP_DOS_DATE, crc, size, size, len(name_b), 0, 0, 0, 0,
                                  ZIP_EXT_ATTR, off)
            out.write(central)
            out.write(name_b)
            cd_size += len(central) + len(name_b)
        out.write(struct.pack('<IHHHHIIH', 0x06054b50, 0, 0, len(entries), len(entries), cd_size, cd_start, 0))

rows = []
for m in sorted(MEMBERS, key=lambda t: t['name']):
    zpath = source_for[m['name']]
    rows.append((m['name'], zpath, m['size'], member_crc32(zpath, m['name'])))
write_stored_zip(ARCHIVE, rows)

with zipfile.ZipFile(ARCHIVE) as z:
    assert z.testzip() is None
    assert sorted(z.namelist()) == sorted(m['name'] for m in MEMBERS)
h = hashlib.sha256()
with open(ARCHIVE, 'rb') as f:
    for chunk in iter(lambda: f.read(1 << 20), b''):
        h.update(chunk)
ARCHIVE_SHA256 = h.hexdigest()
# Every member inside the new archive must hash to its planned SHA-256.
with zipfile.ZipFile(ARCHIVE) as z:
    for m in MEMBERS:
        d = hashlib.sha256()
        with z.open(m['name']) as f:
            for chunk in iter(lambda: f.read(1 << 20), b''):
                d.update(chunk)
        assert d.hexdigest() == m['sha256'], m['name']
print('wrote', ARCHIVE, ARCHIVE.stat().st_size, 'bytes; members', len(rows))
print('archive sha256', ARCHIVE_SHA256)
```

> **📌 Prozess-Hinweis:** Ein *deterministischer* Archiv-Writer ist entscheidend für Reproduzierbarkeit: derselbe Mitglieds-Satz erzeugt byte-identische ZIPs überall, also denselben SHA-256. Damit ist der lokale Build mit dem Kaggle-Run identisch nachweisbar.

```python
import pathlib
import sys
sys.path += [str(COMP / 'kickmix'), str(COMP / 'verifiers')]
import kickmix  # noqa: E402  (competition data, kickmix/)
from dfthcsos import verify as dfthcsos_verify  # noqa: E402
from dfthcsos.scoreinfra.reference import FACTORIZATION_KEYS, ORBITALS  # noqa: E402
from dqi import verify_submission_dqi  # noqa: E402
from invsqrt import verify_submission_invsqrt  # noqa: E402

# The metric's own reader functions, copied unchanged from the competition's metric cell by the builder.

ALLOWED_INSTRUCTIONS = {
    'X', 'CX', 'CCX', 'Z', 'CZ', 'CCZ', 'Z_POW', 'NEG', 'SWAP', 'CSWAP', 'R', 'HMR', 'BIT_INVERT', 'BIT_STORE0', 'BIT_STORE1',
    'PUSH_CONDITION', 'POP_CONDITION', 'INFO_TAG', 'DEBUG_PRINT',
}

MAX_QUBIT_OR_BIT_ID = 2**30 // 1536

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

RUN = Path('/tmp/reverify')
shutil.rmtree(RUN, ignore_errors=True)
RUN.mkdir(parents=True)

def extract_member(name):
    dest = RUN.joinpath(*Path(name).parts)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE) as z, z.open(name) as f, open(dest, 'wb') as g:
        shutil.copyfileobj(f, g, length=1 << 20)
    return dest

def checked_read(path, reader, spec):
    """Same guards as the metric's read(): regular file, no hard links, inside the scratch directory."""
    status = path.lstat()
    if not stat.S_ISREG(status.st_mode) or status.st_nlink > 1 or not path.resolve().is_relative_to(RUN.resolve()):
        raise ParticipantVisibleError(f'{path.name} must be a regular file')
    try:
        return reader(path, spec)
    except (ValueError, RuntimeError, OSError, EOFError, zipfile.BadZipFile, zlib.error, tokenize.TokenError) as err:
        raise ParticipantVisibleError(f'{path.name} is invalid: {err}') from err

results = {}
t_all = time.time()

# I. invsqrt: one circuit, n_p = 10, salt empty (the verifiers' default).
inv_path = extract_member('invsqrt.kmb')
t0 = time.time()
inv_circuit = checked_read(inv_path, read_circuit, 1)
inv_res = verify_submission_invsqrt.verify(inv_circuit, verify_submission_invsqrt.ProblemSpecInvSqrt.for_n_p(10), salt='')
results['invsqrt'] = {'score': float(inv_res['score']), 'verified_shots': int(inv_res['verified_shots']),
                      'seconds': round(time.time() - t0, 1)}
print('invsqrt', results['invsqrt'], flush=True)

# II. DQI: the metric's shot count (400 batches of 256 = 102,400 shots).
batches = max(1, verify_submission_dqi.DEFAULT_NUM_SHOTS // verify_submission_dqi.DEFAULT_BATCH_SIZE // 1)
dqi_spec = verify_submission_dqi.ProblemSpecDQI.benchmark_instance(
    num_shots=batches * verify_submission_dqi.DEFAULT_BATCH_SIZE)
dqi_path = extract_member('dqi.kmb')
t0 = time.time()
dqi_circuit = checked_read(dqi_path, read_circuit, dqi_spec.n + dqi_spec.m)
dqi_res = verify_submission_dqi.verify(dqi_circuit, dqi_spec, salt='')
results['dqi'] = {'score': float(dqi_res['score']), 'verified_shots': int(dqi_res['verified_shots']),
                  'seconds': round(time.time() - t0, 1),
                  'failures': {k: dqi_res[k] for k in dqi_res if k != 'score' and isinstance(dqi_res[k], (int, float, str))}}
print('dqi', {k: v for k, v in results['dqi'].items() if k != 'failures'}, flush=True)
print('dqi failure counts', {k: results['dqi']['failures'][k] for k in ('value_errors', 'phase_errors') if k in results['dqi']['failures']}, flush=True)

# III. Chemistry: the 15 ANGLE circuits and submission.npz, all from the attached dataset (one unit).
chem_names = [m['name'] for m in MEMBERS if m['name'].startswith('dfthcsos/')]
for name in chem_names:
    extract_member(name)
dfthcsos_dir = RUN / 'dfthcsos'
angle_paths = {p.stem: p for p in dfthcsos_dir.glob('angle_k_*.km[xb]')}
stems = [f'angle_k_{k}' for k in range(len(angle_paths))]
assert stems and sorted(angle_paths) == sorted(stems), 'dfthcsos/ must hold angle_k_0 ... angle_k_<n-1>, each once'
npz_spec = {
    'U': ('f', ('R', 'B', ORBITALS)),
    'W': ('f', ('R', 'B', 'C')),
    'H2_I': ('f', ('R', 'C')),
    'H1_I': ('f', ()),
    'Hsym_lower': ('f', (ORBITALS * (ORBITALS + 1) // 2,)),
    'tree_edges': ('iu', (ORBITALS - 1, 2)),
}
assert set(npz_spec) == {*FACTORIZATION_KEYS, 'tree_edges'}
t0 = time.time()
angle_circuits = [checked_read(angle_paths[s], read_circuit, dfthcsos_verify.QUBIT_CAP) for s in stems]
npz = checked_read(dfthcsos_dir / 'submission.npz', read_npz, npz_spec)
tree_edges = npz.pop('tree_edges')
df_res = dfthcsos_verify.verify(angle_circuits, npz, tree_edges, salt='',
                                shots_per_address=dfthcsos_verify.SHOTS_PER_ADDRESS)
results['dfthcsos'] = {'score': float(df_res['score']), 'verified_shots': int(df_res['verified_shots']),
                       'seconds': round(time.time() - t0, 1),
                       'metrics': {k: float(v) for k, v in df_res['metrics'].items()
                                   if isinstance(v, (int, float, np.floating))}}
print('dfthcsos', {k: v for k, v in results['dfthcsos'].items() if k != 'metrics'}, flush=True)
print('dfthcsos accuracy metrics', results['dfthcsos']['metrics'], flush=True)

tasks = ['invsqrt', 'dqi', 'dfthcsos']
gm = math.prod(REF_COSTS[t] / results[t]['score'] for t in tasks) ** (1 / 3)
receipt = {'status': 'PASS', 'salt': '', 'archive_sha256': ARCHIVE_SHA256, 'geometric_mean': gm,
           'per_task': results, 'reference_costs': REF_COSTS,
           'total_seconds': round(time.time() - t_all, 1)}
RECEIPTS.mkdir(parents=True, exist_ok=True)
(RECEIPTS / 'verification.json').write_text(json.dumps(receipt, indent=2, default=str) + '\n')
print('blend geometric mean (local official verifiers, empty salt):', gm, flush=True)
```

```python
from IPython.display import Image, Markdown, display

tasks = ['invsqrt', 'dqi', 'dfthcsos']
gm = receipt['geometric_mean']
ratio = {t: REF_COSTS[t] / results[t]['score'] for t in tasks}
lines = ['| Task | Cost (local, empty salt) | Ratio to reference |', '|---|---:|---:|']
lines += [f"| {t} | {results[t]['score']:,.4f} | {ratio[t]:.5f} |" for t in tasks]
lines.append(f'| geometric mean | | {gm:.5f} |')
table = '\n'.join(lines)
(RECEIPTS / 'per_task_table.md').write_text(table + '\n')
display(Markdown(table))

summary = {
    'archive': 'submission.zip',
    'archive_sha256': ARCHIVE_SHA256,
    'archive_bytes': ARCHIVE.stat().st_size,
    'members': len(MEMBERS),
    'salt': '',
    'local_geometric_mean': gm,
    'per_task_cost': {t: results[t]['score'] for t in tasks},
    'per_task_ratio': ratio,
    'source_summary': PLAN['source_summary'],
    'note': "Local numbers from the official verifiers with an empty salt. Leaderboard scores are the competition's to award.",
}
(RECEIPTS / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print('archive sha256', ARCHIVE_SHA256)
```

## The draw: what a leaderboard number can and cannot tell you

Three numbers look alike in this competition and answer different questions.

| Number | Where it comes from | What it tells you |
|---|---|---|
| Local score | Official verifiers, run by you, usually with an empty salt | The files pass, and their cost on one draw you can repeat |
| Public leaderboard | Kaggle, with one secret salt | The cost on one hidden draw |
| Final leaderboard | Kaggle, with a second secret salt | The cost on another hidden draw, which you see at the end |

**Who got here first.** Akmal Xodarev (busyaprime) set out how to read this in the section "The k on the leaderboard" of his [re-verification notebook](https://www.kaggle.com/code/busyaprime/lb-24-73387-top-30-qcc-notebooks-re-verified), including that the final split is a new draw and that the cheaper file wins in expectation. manwithacat (James Barlow) measures the draws in [DQI Salt Check](https://www.kaggle.com/code/manwithacat/dqi-salt-check-public-frontier) and ranks DQI files by a 48-draw mean. This section applies their rule to the current 892-qubit files and adds new measurements.

**How a draw is made.** The DQI verifier hashes the circuit's `.kmb` bytes with SHA-256, merges that with the salt, and seeds its 102,400 shots from the result (`_initial_seed` in `verify_submission_dqi.py`). The docstring of [the competition metric](https://www.kaggle.com/code/metric/google-quantum-ai-metric) says each leaderboard split has its own secret salt. So the same bytes meet the same shots on a split, any changed byte is a new draw on every split, and one file gets two separate draws from Kaggle.

**Why a draw matters.** The decoders at the public frontier miss a few rare inputs, so a shot can fail on a sound circuit. `k` failed shots move `eps`, and so `R`, up a fixed ladder. The cell below computes that ladder with the verifier's own functions. The score can only fall by whole rungs, which makes a board score readable: if you know your no-failure score, the gap tells you `k`.

```python
from functools import lru_cache

import matplotlib.pyplot as plt

SHOTS = batches * verify_submission_dqi.DEFAULT_BATCH_SIZE

@lru_cache(maxsize=None)
def rung(k):
    """The repetition factor R after k failed shots, from the verifier's own two functions."""
    eps = verify_submission_dqi.clopper_pearson_upper_bound(k, SHOTS)
    return verify_submission_dqi.repetition_overhead(eps)

R0 = rung(0)

def score_after(k, clean_score):
    """The three-task score when only DQI's R moves, from a no-failure score."""
    return clean_score * (R0 / rung(k)) ** (1 / 3)

def read_k(board_score, clean_score, largest=12):
    """The number of failed shots whose rung sits nearest to a board score, and the distance to that rung."""
    k = min(range(largest + 1), key=lambda n: abs(score_after(n, clean_score) - board_score))
    return k, abs(score_after(k, clean_score) - board_score)

local_k = dqi_res['value_errors'] + dqi_res['phase_errors']
clean_score = gm * (rung(local_k) / R0) ** (1 / 3)

ladder = ['| Failed shots | R | DQI cost | Score factor | This archive would read | Drop |', '|---:|---:|---:|---:|---:|---:|']
for k in range(6):
    after = score_after(k, clean_score)
    ladder.append(f'| {k} | {rung(k):.6f} | {100 * (rung(k) / R0 - 1):+.3f} % | {(R0 / rung(k)) ** (1 / 3):.6f} | {after:.5f} | {after - clean_score:+.5f} |')
display(Markdown('\n'.join(ladder)))

# Notebook, DQI file, its no-failure score, its public badge (read on 2026-11-06 and 2026-11-07).
BOARD_EXAMPLES = [
    ('atakanaldemir/qcc-17-product-dqi-reuse-at-892-qubits', '7b6cbb92a797', 24.94126, 24.87098),
    ('this notebook, version 29', 'b4bbf86d504e', 24.94099, 24.94099),
    ('this notebook, version 30', 'df65bd5bcf3e', 24.94111, 24.94111),
    ('kozykappa/google-quantum-ai-verifiable-quantum-circuit-comp', '337cb0497b4d', 25.068955, 25.06895),
    ('atakanaldemir/qcc-early-measurement-and-domain-aware-inverse', '337cb0497b4d', 25.09593, 25.09592),
    ('isabe11am00re/qcc-v66s33w-submission', '4432ec5fd63d', 25.090589, 25.09058),
    ('manwithacat/the-real-150k-was-the-friends-we-made', '2c94a1d57125', 25.091092, 25.02038),
]
readings = ['| Notebook | DQI file | No-failure score | Public badge | Failed shots read | Miss |', '|---|---|---:|---:|---:|---:|']
for name, sha12, clean, board in BOARD_EXAMPLES:
    k, miss = read_k(board, clean)
    readings.append(f'| {name} | `{sha12}` | {clean:.5f} | {board:.5f} | {k} | {miss:.1e} |')
display(Markdown('\n'.join(readings)))

ks = list(range(6))
ys = [score_after(k, 24.94126) for k in ks]
fig, ax = plt.subplots(figsize=(7.2, 3.7))
ax.step(ks, ys, where='mid', color='#2a78d6', linewidth=2)
ax.scatter(ks, ys, s=46, color='#2a78d6', edgecolor='#fcfcfb', linewidth=1.5, zorder=3)
ax.annotate('24.87098\nAtakan Aldemir public badge', (2, ys[2]), xytext=(2.35, ys[2] + 0.028), fontsize=9, color='#3d3d3a',
            arrowprops={'arrowstyle': '-', 'color': '#8a8a84', 'linewidth': 0.8})
ax.set_xlabel('Failed shots in the draw')
ax.set_ylabel('Score')
ax.set_xticks(ks)
for side in ('top', 'right'):
    ax.spines[side].set_visible(False)
ax.grid(axis='y', color='#e5e4df', linewidth=0.8)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(RECEIPTS / 'draw_ladder.png', dpi=130)
plt.close(fig)
display(Image(filename=str(RECEIPTS / 'draw_ladder.png')))
```

> **📌 Prozess-Hinweis:** Das ist der Kern-Trick des Notebooks. `rung(k)` nutzt *die Funktionen des Verifiers selbst* (`clopper_pearson_upper_bound`, `repetition_overhead`), nicht eine eigene Näherung. Damit ist die Ladder exakt so definiert wie der Grader. `read_k` invertiert sie: gib einen Board-Score und deinen Null-Fehler-Score, und du liest ab, wie viele Shots fehlgeschlagen sind.

**Reading the tables.** Atakan Aldemir's file `7b6cbb92a797` was the cheapest of the 71 DQI circuits in manwithacat's public list on 2026-11-06, and his [notebook](https://www.kaggle.com/code/atakanaldemir/qcc-17-product-dqi-reuse-at-892-qubits) gives 24.94126 as its estimate with no extra failed shot. Its public badge is 24.87098, and the two-failure rung of 24.94126 is 24.87098 to five decimals. So that draw had two failed shots, and nothing else is wrong with the file. [AlekseiProvorov's notebook](https://www.kaggle.com/code/leoprovorov/the-unbearable-lightness-of-quantum-circuits) carries the same `dqi.kmb` and shows the same badge. The same bytes meet the same public draw, so it carries the same two failed shots.

**The rows from 2026-11-07.** kozykappa's notebook gives 25.068955 as its no-failure score for `337cb0497b4d` and shows 25.06895, and Atakan Aldemir's gives 25.09593 for the same DQI file and shows 25.09592. Our empty-salt runs of Isabe11aM00re's DQI and chemistry files, with the invsqrt cost from maoxin123's own run of the same `95621d7ee3e1`, give 25.090589, and the badge is 25.09058. All three read k = 0. The miss of about 9.2e-6 in Isabe11aM00re's row is the change in the mean Toffoli count from one clean draw to another, while one failed shot would cost about 0.038. The last row is manwithacat's frontier notebook, whose output carries `2c94a1d57125` with a no-failure score of 25.091092 from its own run: its badge sits on the two-failure rung. A badge can come from an earlier version, so treat that row as a strong reading, not a proof.

Only read `k` this way when you hold a no-failure score for the exact files. Several notebooks sit near 24.87 for a different reason. Atakan Aldemir's [gap-3 notebook](https://www.kaggle.com/code/atakanaldemir/qcc-gap-3-residue-repair-and-c43-native-compiler) scaled a board score of 24.85585 by its chemistry cost ratio to reach 24.87121, and it shows 24.87121. Its no-failure score from its own costs is also 24.8712, so that badge reflects cost, not failed shots.

**How often does a draw fail?** The `manifest.csv` of manwithacat's dataset [VQCC public circuits](https://www.kaggle.com/datasets/manwithacat/vqcc-apache-public-circuits) lists a no-failure cost for every DQI file and a 48-draw mean cost for most recent ones, including these four. The next cell reads the failed shots behind those two columns, and then what they imply under a Poisson model. That is our reading of the columns, not a number in the manifest.

```python
# No-failure cost and 48-draw mean cost, from manifest.csv in manwithacat/vqcc-apache-public-circuits, read on 2026-11-06.
MEAN_OVER_48 = {
    '1ab3ac53d442': (374771517851.64, 375094353292.95),
    '768495b4ce0f': (374770691080.72, 375093380692.96),
    'b4bbf86d504e': (374767710993.62, 375090579527.95),
    '7b6cbb92a797': (374755600650.83, 375078260645.83),
}

def poisson_pmf(k, lam):
    return math.exp(-lam + k * math.log(lam) - math.lgamma(k + 1)) if lam > 0 else float(k == 0)

def over_draws(fn, lam, largest=30):
    """The mean of fn(k) when the failed shots in a draw are Poisson with mean lam."""
    return sum(poisson_pmf(k, lam) * fn(k) for k in range(largest + 1))

def poisson_tail_le(k, mu):
    return sum(poisson_pmf(j, mu) for j in range(k + 1))

def poisson_interval(k, draws, level=0.95):
    """Exact (Garwood) interval for failed shots per draw, by bisection on the Poisson tails."""
    alpha = (1 - level) / 2
    def solve(fn):
        lo, hi = 0.0, 10.0 * (k + 5)
        for _ in range(80):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if fn(mid) else (lo, mid)
        return lo
    lower = solve(lambda mu: 1 - poisson_tail_le(k - 1, mu) < alpha) if k else 0.0
    upper = solve(lambda mu: poisson_tail_le(k, mu) > alpha)
    return lower / draws, upper / draws

def failed_in_48(clean_cost, mean_cost):
    """The failed shots behind a 48-draw mean, when each sits alone in its draw."""
    return 48 * (mean_cost / clean_cost - 1) / (rung(1) / R0 - 1)

rows = ['| DQI file | No-failure cost | 48-draw mean | Mean / no-failure | Failed shots in 48 draws |', '|---|---:|---:|---:|---:|']
for sha12, (clean_cost, mean_cost) in MEAN_OVER_48.items():
    rows.append(f'| `{sha12}` | {clean_cost:,.0f} | {mean_cost:,.0f} | {mean_cost / clean_cost:.6f} | {failed_in_48(clean_cost, mean_cost):.2f} |')
display(Markdown('\n'.join(rows)))

failed48 = round(failed_in_48(*MEAN_OVER_48['b4bbf86d504e']))
lam48 = failed48 / 48
low48, high48 = poisson_interval(failed48, 48)

def at_rate(lam):
    """What a failure rate means for one DQI file and for two final picks with different bytes."""
    clean = poisson_pmf(0, lam)
    one = over_draws(lambda k: score_after(k, clean_score), lam)
    two = over_draws(lambda a: over_draws(lambda b: score_after(min(a, b), clean_score), lam, 12), lam, 12)
    return {'rate': lam, 'clean': clean, 'several': 1 - clean - poisson_pmf(1, lam), 'one': one, 'loss': clean_score - one,
            'two': two, 'gain': two - one, 'both_fail': (1 - clean) ** 2,
            'toffolis': (over_draws(lambda k: rung(k) / R0, lam) - 1) * dqi_res['toffoli_count']}

at_low, at_central, at_high = at_rate(low48), at_rate(lam48), at_rate(high48)

def line(label, key, form):
    return f'| {label} | ' + ' | '.join(format(r[key], form) for r in (at_low, at_central, at_high)) + ' |'

display(Markdown(
    f'All four rows are one measurement. The 48 draws are fixed and shared across files, so {failed48} failed shots in 48 draws is a single count, '
    f'and its exact 95 % interval gives the low and high columns below. The rows assume independent failures and use this archive\'s no-failure score for both picks.'))
display(Markdown('\n'.join([
    '| Reading | Low end | Central | High end |', '|---|---:|---:|---:|',
    line('Failed shots per draw', 'rate', '.3f'),
    line('Probability of a clean draw', 'clean', '.2f'),
    line('Probability of two or more failed shots', 'several', '.3f'),
    line('Mean score, one file', 'one', '.5f'),
    line('Mean loss against a clean draw', 'loss', '.5f'),
    line('Mean score, better of two files', 'two', '.5f'),
    line('Gain from the second file', 'gain', '.5f'),
    line('Probability that both files fail', 'both_fail', '.3f'),
    line(f'Mean Toffolis per shot the failures cost, out of {dqi_res["toffoli_count"]:,.1f}', 'toffolis', ',.0f'),
])))

cheap_gain = clean_score * ((MEAN_OVER_48['b4bbf86d504e'][1] / MEAN_OVER_48['7b6cbb92a797'][1]) ** (1 / 3) - 1)
display(Markdown(
    f'By 48-draw mean cost, `7b6cbb92a797` beats `b4bbf86d504e` by {cheap_gain:.5f} in score. '
    f'The central gain from a second file is {at_central["gain"] / cheap_gain:.0f} times that.'))
```

> **📌 Prozess-Hinweis:** `failed_in_48` invertiert die Ladder: aus dem Verhältnis (48-Draw-Mittel / Null-Fehler) liest man die Gesamtzahl fehlgeschlagener Shots über 48 Draws. `poisson_interval` (Garwood, exakt) gibt das 95 %-Konfidenzintervall. `at_rate` beantwortet dann die entscheidende Frage: **Was bringt eine zweite DQI-Datei mit anderen Bytes?** (`two` = Erwartungswert des besseren von zwei unabhängigen Draws; `gain` = `two − one`).

**What follows.** Point 1 is our reading of manwithacat's manifest. Point 2 rests on Akmal Xodarev's argument that the final split is a new draw. Points 3 to 5 are ours.

1. **The four rows share one failure count.** manwithacat's draws are fixed, so all four files meet the same shots, and each shows the same 9 single failures. Exact rewrites of one decoder should fail on the same inputs, and his [hedge notebook](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook) reports "the same 7 failing shots" for a sibling family. So this is one sample of the risk and not four. On Kaggle the files differ in cost and in which shots they meet.
2. **A clean public draw promises nothing for the final draw.** It is one sample from a shared failure rate. For the final leaderboard the cheaper file wins in expectation, so `7b6cbb92a797` stays ahead of `b4bbf86d504e` despite its badge. A team choosing final submissions should not drop a file for its public `k` alone.
3. **The top of the Code tab is selected on this draw.** A notebook near the top has `k = 0` on the public split, because a notebook that drew `k = 1` sits about 0.04 lower. On the final split each file draws again, so some of today's top notebooks will fall a rung with nothing changed.
4. **The failures have a price.** The Toffoli row above is the mean cost of the failures. A decoder change that removes them and adds fewer mean Toffolis per shot than that pays in expectation. The verifier charges the mean over shots, not the static count (for this file about 395,356 against 395,641), so a handler behind a measured condition is charged only when it runs. [DQI Salt Check](https://www.kaggle.com/code/manwithacat/dqi-salt-check-public-frontier) logs every failing shot to `failing_shots.jsonl`, which is the place to start on such a fix.
5. **Two final picks should carry different DQI bytes.** The [rules](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/rules) let a team select up to two final submissions. Two files with different `dqi.kmb` bytes meet different shots on the final split, so their draws are independent, and one failure no longer sets the result. Two picks with the same `dqi.kmb` bytes meet the same draw and hedge nothing. `b4bbf86d504e` and `7b6cbb92a797` are a pair of that kind. The table above assumes a team is ranked by the better of its picks, which is Kaggle's usual practice but is not spelled out on the rules page.

**One caution.** At the rate above, two failed shots in one draw is rare. `7b6cbb92a797` read two on the public split, and [Atakan Aldemir's notebook](https://www.kaggle.com/code/atakanaldemir/qcc-17-product-dqi-reuse-at-892-qubits) reports 0, 1, 0 and 2 failed shots in its four paired draws. Either that file was unlucky or failures cluster more than a Poisson model says. Version 30 of this notebook ran eight more draws for it and read one failed shot in eight, which fits the rate above. This version repeats four of them, which must give the same counts.

**What this notebook ships.** The Code tab shows the public split, so this notebook ships `4432ec5fd63d`, whose public draw is clean: the same bytes read 25.09058 in Isabe11aM00re's notebook. Syed Asad Ali's `2c94a1d57125` is cheaper at an empty salt (374,712,921,286 in the output of manwithacat's frontier notebook), but that notebook ships it with a no-failure score of 25.09109 and shows 25.02038, which is the two-failure rung to within 1e-5 (last row of the table above). The same bytes would meet the same two failed shots here, so it is not used. That is a choice about the public number. Any byte change would give a new draw, and the [metric's docstring](https://www.kaggle.com/code/metric/google-quantum-ai-metric) notes that each such re-roll costs a submission.

## Measure it yourself

`draw_report` runs the unchanged official DQI verifier once per salt and returns one row per draw. Point it at your own circuit before you spend a submission. A draw takes two to three minutes on Kaggle's CPU.

The run below uses the shipped file and the study file from the pinned dataset, on four salts anyone can repeat (`draw-01` to `draw-04`). Version 30 ran the study file on the same four salts and read 1, 0, 0 and 0 failed shots, so a match here checks the rule that the same bytes meet the same draw. Both are rewrites of one decoder by their authors' accounts, and they meet different shots on the same salt because their hashes differ. A time limit per file keeps the run bounded, and the archive is already written, so a problem here cannot affect it.

```python
import gc

SWEEP_SALTS = [f'draw-{i:02d}' for i in range(1, 5)]
SWEEP_MINUTES_PER_FILE = 12
STUDY_SHA = '7b6cbb92a7977dc7fd4917ae02496ea7ce51bd1114790e8ddadb1ccd5eda9ec3'
SHIPPED_SHA = next(m['sha256'] for m in MEMBERS if m['name'] == 'dqi.kmb')

def draw_report(circuit, spec, salts, minutes=60):
    """Run the official DQI verifier once per salt; stop starting new draws after `minutes`."""
    rows = []
    started = time.time()
    for salt in salts:
        if (time.time() - started) / 60 > minutes:
            print('time limit reached after', len(rows), 'draws', flush=True)
            break
        t0 = time.time()
        r = verify_submission_dqi.verify(circuit, spec, salt=salt)
        rows.append({'salt': salt, 'failed_shots': r['value_errors'] + r['phase_errors'], 'value_errors': r['value_errors'],
                     'phase_errors': r['phase_errors'], 'R': r['repetition_factor'], 'mean_toffolis': r['toffoli_count'],
                     'cost': float(r['score']), 'seconds': round(time.time() - t0, 1)})
        print(rows[-1], flush=True)
    return rows

def find_dqi_file(sha256):
    """The attached dqi.kmb with this SHA-256; the dataset holds each file under its own folder."""
    for path in sorted(glob.glob('/kaggle/input/**/dqi.kmb', recursive=True)):
        digest = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(1 << 20), b''):
                digest.update(chunk)
        if digest.hexdigest() == sha256:
            return Path(path)
    raise FileNotFoundError(sha256)

sweep = {}
sweep_notes = []
for sha256, loader in ((SHIPPED_SHA, lambda: dqi_circuit), (STUDY_SHA, lambda: read_circuit(find_dqi_file(STUDY_SHA), dqi_spec.n + dqi_spec.m))):
    try:
        sweep[sha256[:12]] = draw_report(loader(), dqi_spec, SWEEP_SALTS, SWEEP_MINUTES_PER_FILE)
    except Exception as err:
        sweep_notes.append(f'{sha256[:12]}: {type(err).__name__}: {err}')
        print('sweep stopped for', sweep_notes[-1], flush=True)
    dqi_circuit = None
    gc.collect()
_ = (RECEIPTS / 'dqi_draws.json').write_text(json.dumps({'salts': SWEEP_SALTS, 'draws': sweep, 'notes': sweep_notes}, indent=1) + '\n')
```

```python
if sweep:
    salts_run = [s for s in SWEEP_SALTS if any(r['salt'] == s for rows_ in sweep.values() for r in rows_)]
    head = '| Salt | ' + ' | '.join(f'`{sha12}` failed shots' for sha12 in sweep) + ' |'
    grid = [head, '|---|' + '---:|' * len(sweep)]
    for salt in salts_run:
        cells = [next((str(r['failed_shots']) for r in sweep[sha12] if r['salt'] == salt), '') for sha12 in sweep]
        grid.append(f'| {salt} | ' + ' | '.join(cells) + ' |')
    display(Markdown('\n'.join(grid)))

    stats = ['| File | Draws | Failed shots | Draws with a failure | Failed shots per draw | 95 % interval |', '|---|---:|---:|---:|---:|---:|']
    pooled_k = pooled_n = 0
    for sha12, rows_ in sweep.items():
        k, n = sum(r['failed_shots'] for r in rows_), len(rows_)
        pooled_k, pooled_n = pooled_k + k, pooled_n + n
        if n:
            low, high = poisson_interval(k, n)
            stats.append(f'| `{sha12}` | {n} | {k} | {sum(r["failed_shots"] > 0 for r in rows_)} | {k / n:.3f} | {low:.3f} to {high:.3f} |')
    if pooled_n:
        low, high = poisson_interval(pooled_k, pooled_n)
        stats.append(f'| both | {pooled_n} | {pooled_k} | {sum(r["failed_shots"] > 0 for rows_ in sweep.values() for r in rows_)} | {pooled_k / pooled_n:.3f} | {low:.3f} to {high:.3f} |')
    display(Markdown('\n'.join(stats)))
    if pooled_n:
        display(Markdown(f'These {pooled_n} draws give {pooled_k / pooled_n:.3f} failed shots per draw, with a 95 % interval of {low:.3f} to {high:.3f}, '
                         f'against {lam48:.3f} ({low48:.3f} to {high48:.3f}) read from the 48-draw column above. Draws are few, so a wide interval is the honest result.'))
for note in sweep_notes:
    print(note)
```

> **📌 Prozess-Hinweis:** `draw_report` ist das *Werkzeug*, das prvsiyan der Community hinterlässt – eine Funktion, die du auf deine eigene `dqi.kmb` zeigen kannst, um vor dem Ausgeben einer Submission zu sehen, wie viele Shots sie auf mehreren Salts fehlschlägt. Das ist "Verification-Driven Development": erst messen, dann entscheiden.

## What moved the frontier, and what did not

Version 30 of this notebook read 24.94111 on 2026-11-06. A day later the best public notebooks read 25.09. Measured per task with the official verifiers at an empty salt, this is where the step came from (change in the geometric mean from each task, 24.9411 to 25.0960):

| Task | Version 30 | Now | Cost change | Share of the geometric-mean gain |
|---|---:|---:|---:|---:|
| Invsqrt | 97,746.90 | 95,957.89 | -1.830 % | +0.618 % |
| DQI | 374,766,951,220 | 374,735,446,629 | -0.0084 % | +0.0028 % |
| Chemistry | 299,667,305.06 | 299,662,437.60 | -0.0016 % | +0.0005 % |

**1. Invsqrt moved the most, from a rebuild.** Syed Asad Ali reworked the 62-qubit circuit of the mrmeows, busyaprime and yoyobar line in several published steps: a deferred fan-in lookup, X-measurement plus a conditioned CZ in place of reverse ripples for the adder carries, carry-save merges, and a search over every small window of the compiled circuit that re-synthesises some of them with fewer products. [His notebook](https://www.kaggle.com/code/syed3000/vqcc-own-circuit-portfolio-notebook) states that each rewrite is proven exact on all 3,133,452 inputs and all measurement outcomes. [manwithacat's frontier table](https://www.kaggle.com/code/manwithacat/the-real-150k-was-the-friends-we-made) dates two of his files: `af846e54422c` (2026-11-07 06:40 UTC, mean Toffolis 1,281.48 down to 1,268.75) and `829b2b88d3b1` (13:15 UTC, 96,267.97). Then [Hosen42](https://www.kaggle.com/code/hosen42/vqcc-our-submission) found two runs of writes to wires that nothing reads before they are measured, and [maoxin123](https://www.kaggle.com/code/maoxin123/lb-25-09-syed-circuits-refit-chem-weights) shipped that rewrite as `95621d7ee3e1` (14:11 UTC, four Toffolis fewer). At 20:43 UTC [Atakan Aldemir](https://www.kaggle.com/code/atakanaldemir/qcc-early-measurement-and-domain-aware-inverse) deleted one controlled swap that his check over every legal input and every measurement branch shows to be redundant (`bbfa9675880e`, 95,957.89, one Toffoli-equivalent fewer, about 0.005 of the score). The whole step cut the invsqrt cost by 1.83 %, worth 0.62 % of the score and nearly all of the gain. Lesson, as last time: look for the large factor first.

**2. One identity, used in two tasks.** [Kirill Tymchishin's notebook](https://www.kaggle.com/code/kirilltym/quantum-circuits-pi-gauge-weight-refinement) writes out why it is safe. If a Toffoli writes `ab` into a wire `t` that is next measured in the X basis, the measurement only adds the phase `m_t (t + ab)`. Measuring `t` first and then applying CZ(a, b) when `m_t` is 1 gives the same phase for every outcome, with no Toffoli. Hosen42's invsqrt rewrite is the same idea for a run of writes. In DQI, Kirill Tymchishin applied it to the 14 such Toffolis in Ahmed Berat Ozer's `77bace9de69c`, which gives `337cb0497b4d`, and Isabe11aM00re's `4432ec5fd63d` has three static Toffolis fewer again. Syed Asad Ali's `2c94a1d57125` uses the same peephole on his own decoder.

**What we checked.** A backward pass over each file marks the values that are read before their wire is measured. It finds 14 Toffolis with an unread target in `77bace9de69c` and none in `337cb0497b4d` or `4432ec5fd63d`. In `95621d7ee3e1` and `bbfa9675880e` it finds five candidates, and each target is rotated (`Z_POW`) before its measurement, so it is read after all. On these files the identity has nothing left to take.

**3. The weight refit is still second order.** On Syed Asad Ali's loaders, Heliosli's version-15 weights give 299,667,305.06, maoxin123's version-3 weights give 299,662,440.61 and Isabe11aM00re's refinement of them gives 299,662,437.60. That is 4,867 cost units, 1.6e-5 of the cost and about 5.4e-6 of the score, and the last step is 3 units. The refit sits on the 20 mHa error gates and on the gap floor.

**4. The top of the Code tab, member by member.** Members are read from each notebook's current output and badges from the Code tab on 2026-11-07 at about 21:50 UTC. A badge can come from an earlier version, so the pairing is only safe where the numbers agree, as they do here.

| Notebook | `invsqrt.kmb` | `dqi.kmb` | Weights | Badge |
|---|---|---|---|---:|
| [Atakan Aldemir](https://www.kaggle.com/code/atakanaldemir/qcc-early-measurement-and-domain-aware-inverse) | `bbfa9675880e` | `337cb0497b4d` | `3be62649a775` | 25.09592 |
| [Isabe11aM00re](https://www.kaggle.com/code/isabe11am00re/qcc-v66s33w-submission) | `95621d7ee3e1` | `4432ec5fd63d` | `5bd3575736fd` | 25.09058 |
| [Kirill Tymchishin](https://www.kaggle.com/code/kirilltym/quantum-circuits-pi-gauge-weight-refinement) | `95621d7ee3e1` | `337cb0497b4d` | `3be62649a775` | 25.09052 |
| [Alex Chilton](https://www.kaggle.com/code/alexchilton/24-94-lb-verified-three-task-portfolio) | `95621d7ee3e1` | `337cb0497b4d` | `988c81b60421` | 25.09052 |
| [yoyobar](https://www.kaggle.com/code/yoyobar/lb-22-99-invsqrt-101-62-qubits) | `95621d7ee3e1` | `337cb0497b4d` | `988c81b60421` | 25.09052 |
| [maoxin123](https://www.kaggle.com/code/maoxin123/lb-25-09-syed-circuits-refit-chem-weights) | `95621d7ee3e1` | `77bace9de69c` | `3be62649a775` | 25.09022 |
| [kozykappa](https://www.kaggle.com/code/kozykappa/google-quantum-ai-verifiable-quantum-circuit-comp) | `829b2b88d3b1` | `337cb0497b4d` | `988c81b60421` | 25.06895 |

The badges follow the costs. Rows two to six share one invsqrt file and differ only in DQI and weights; the weights `3be62649a775` and `988c81b60421` differ by 0.01 cost units, which is why three notebooks tie.

**Why this archive should read about 25.0960.** Every file meets the same public draw in every archive that carries it. Atakan Aldemir's archive reads B_A = 25.09592, Kirill Tymchishin's B_K = 25.09052 and Isabe11aM00re's B_I = 25.09058, and each badge is the cube root of a product of three per-task ratios. In B_A x B_I / B_K the shared factors cancel: Kirill Tymchishin's invsqrt ratio cancels Isabe11aM00re's, and his DQI and weights ratios cancel Atakan Aldemir's. What is left is Atakan Aldemir's invsqrt with Isabe11aM00re's DQI file and weights, which is this archive, on the public draw. With each badge rounded to five decimals, that is between 25.095965 and 25.095995. Our empty-salt runs of the DQI and chemistry files, with the invsqrt cost from Atakan Aldemir's own empty-salt run, give 25.095996; the public draw differs only in the mean Toffoli counts. The method needs three badges whose files overlap like this, and it is exact up to their rounding.

**5. The risk is still larger than the gains.** One failed shot now costs about 0.038 of the score, about seven times the 0.0053 between the two best badges and several hundred times the 6e-5 between the second and the third. Every gain above is real on average, and any one of them can be hidden by a single draw.

**What we calibrated.** Where we hold the exact member files, the no-failure score agrees with the badge to about 1e-5: maoxin123's own run gives 25.09023 against 25.09022, the costs in Kirill Tymchishin's and Alex Chilton's notebooks give 25.09052 against 25.09052, kozykappa's run gives 25.068955 against 25.06895, Atakan Aldemir's run gives 25.09593 against 25.09592, and our runs of Isabe11aM00re's DQI and chemistry files, with maoxin123's invsqrt cost, give 25.090589 against 25.09058. A board score for a new file only follows from that rule if its DQI draw is also clean.

**Before that.** Version 30 traced the step from 24.84 to 24.94 the same way. There the large factor was chemistry: Syed Asad Ali's version-9 loaders cut 154 Toffolis (1.02 % of the cost), and the weight refits were a second-order term then too.

## Who wrote what: credits and licences

Each row names the circuit this archive uses for that benchmark, the people whose work it builds on, and the licence as the sources state it.

| Benchmark | Member in this archive | Credit | Licence as the sources state it |
|---|---|---|---|
| I. invsqrt, 62 qubits | `invsqrt.kmb`, sha256 prefix `bbfa9675880e`, 548,450 bytes | **Atakan Aldemir (atakanaldemir)** (`atakanaldemir/qcc-early-measurement-and-domain-aware-inverse`, version 2): one controlled swap deleted from `95621d7ee3e1` after a check over every legal input and every measurement branch, with an independent audit. On that file, **maoxin123** (`maoxin123/lb-25-09-syed-circuits-refit-chem-weights`, version 3) shipped **Hosen42**'s measure-first rewrite (`hosen42/vqcc-our-submission`) of two write-only runs in the version-11 file of **Syed Asad Ali (syed3000)** (`syed3000/vqcc-own-circuit-portfolio-notebook`): a deferred fan-in lookup, measured carry clean-up, carry-save merges, exact window re-synthesis and further rewrites he states are proven exact. **Kirill Tymchishin** checked the two windows independently. Lineage: **mrmeows** (team selenium), **busyaprime (Akmal Xodarev)**, **yoyobar**, with **Ahmed Berat Ozer**, **Ehan Mallick**, **SomeJoint (Agniv Banerjee)**, **Leo Tang** and others named in those notebooks. | Apache 2.0 on the notebook pages of Atakan Aldemir, maoxin123, Syed Asad Ali, Hosen42 and Kirill Tymchishin, read on 2026-11-07. The circuit keeps the upstream terms of its lineage and is not relicensed here. |
| II. DQI decoder, 892 qubits | `dqi.kmb`, sha256 prefix `4432ec5fd63d`, 529,241,631 bytes | **Isabe11aM00re** (`isabe11am00re/qcc-v66s33w-submission`, version 12): an update of `337cb0497b4d`, three static Toffolis fewer. `337cb0497b4d` is **Kirill Tymchishin (kirilltym)**'s measurement-order identity on 14 sites (`kirilltym/quantum-circuits-pi-gauge-weight-refinement`), applied to `77bace9de69c` of **Ahmed Berat Ozer (ahmedberatozer)** (dataset `ahmedberatozer/vqcc-v23-portfolio`, shipped by **ozertuu**): **Atakan Aldemir**'s 17 product reuses with the four chains of **daifanhao (MAIDANG)** rebuilt on them. Decoder line: **Syed Asad Ali**, with **SomeJoint (Agniv Banerjee)**'s narrow return, **Ali Haydar Ozdag**'s flag-carry idea, the clean AND ladders of **Khattar and Gidney (2024)** and product caching in the line of **busyaprime** and **yoyobar**. Earlier decoder line: **Alex Chilton**, **Leo Tang**, **mrmeows**, **manwithacat (James Barlow)**, **Dmitrii Gluzdov**, and the design of **jday96314 (QuantumAI)**. | **Credit only. Not Apache-2.0.** The decoder design comes from jday96314's repository, which states no licence according to the notices of Heliosli, daifanhao and Isabe11aM00re (we could not check it ourselves), and no author in the chain has relicensed it. The notebook pages of Isabe11aM00re, Kirill Tymchishin and ozertuu state Apache 2.0 for their code, and Ahmed Berat Ozer's dataset is licensed "other". This circuit is re-hosted with credit only. |
| III. DFTHC-SOS chemistry, 427 qubits | `dfthcsos/`: 15 angle circuits and `submission.npz`, sha256 prefix `5bd3575736fd`, 1,851,004 bytes | **Syed Asad Ali (syed3000)**: his own 8 x 143 x 44 word table and version-9 loader compiler, on **Lera (marculera)**'s DF-THC pipeline, **Ahmed Berat Ozer**'s progressive rounding and the pi-gauge and helper lineage of **Atakan Aldemir**, with loader integration by **Kirill Tymchishin**. Weights `W` and `H2_I`: **Isabe11aM00re** (start), **maoxin123** (chained refits with `dfthc_refit` by **manwithacat**), **Heliosli** (versions 14 and 15), **maoxin123** (versions 2 and 3), then **Isabe11aM00re**'s refinement of maoxin123's version-3 weights. The first public refit of the weights at fixed words was Heliosli's. | Apache 2.0 on the notebook pages of Syed Asad Ali, maoxin123, Kirill Tymchishin and Isabe11aM00re, and the dataset `isabe11am00re/qcc-v84337cb049akt21-circuits` is licensed Apache 2.0. The 15 loaders and the npz are one unit. |
| Study file, in the sweep only | `7b6cbb92a797`, stored as `dqi.kmb` at the top of the dataset, not in the archive | **Atakan Aldemir**: 17-route retained-product rewrite of Syed Asad Ali's `1ab3ac53d442`, with the same decoder lineage as row II. | Credit only, as for row II. |

**Reading the draw.** Akmal Xodarev (busyaprime) published the ladder reading of leaderboard scores and the final-split argument. manwithacat (James Barlow) published the salt check, the Poisson treatment and the 48-draw means quoted here, from a dataset released under Apache-2.0.

**Frontier records.** manwithacat's frontier table dates the invsqrt files quoted in the frontier section, and the member table there is read from the public outputs of the five notebooks it names.

**Organisers.** Google Quantum AI and Qualtran, for the task, the verifiers and kickmix, which keep their own terms.

Our contribution in this notebook is the selection and SHA-256 matching of the members, the member table of the top notebooks, the backward check of the measurement-order identity, the deterministic archive writer, the re-verification, `draw_report` and the two-file sweep, the reading of the `7b6cbb92a797` badge, the Toffoli price of the failures, the sum for two final picks and this write-up. The circuits belong to their authors.

> **📌 Prozess-Hinweis:** Die Lizenz-Differenzierung pro Datei (Apache-2.0 vs. "nur Credit") ist ein kritisches Detail. prvsiyan *weigert sich*, Apache-2.0 für die DQI-Dateien zu beanspruchen, weil jday96314's Repository keine Lizenz angibt. Das ist juristische Sorgfalt, die in einer Competition mit Prize-Eligibility-Fragen (Diskussion #756745) überlebenswichtig ist.

## An honest note on scores

The numbers printed by the code cells are **local**: official verifier code from the competition data, run with an empty salt unless a cell names another salt. The score at the top is the public leaderboard score of this notebook's own submission. Scores quoted from other notebooks belong to their authors and appear only as comparisons, read from their public badges or their own text on 2026-11-06 and 2026-11-07.

**What would change the result.** A different verifier build or kickmix binary could change the cost or reject the archive, and the chemistry margins are thin enough for that to matter. The final leaderboard is a separate draw, so this archive can read lower there with no change to its files.

**Licence.** The code and prose written for this notebook are Apache-2.0, the Kaggle default. The members keep the licences their sources state, and these differ by file, as the credits table sets out. No source gives Apache-2.0 for the DQI circuit files, so this notebook does not claim it for them: the decoder design is credit only (jday96314's repository states no licence, as reported in the notices of Heliosli and daifanhao). The chemistry circuits are Apache-2.0 as stated by their source notebooks. The dataset `prvsiyan/vqcc-verified-best-of-circuits-1106a` carries the same per-file statements. The notebook attaches no kernel outputs.

---

## 🧠 Prozess-Lektion

**Wie prvsiyan arbeitet – Verification-Driven Development und Score-Interpretation:**

1. **Der Beitrag ist die Analyse, nicht der Circuit.** prvsiyan baut keinen einzigen Circuit. Der Wert liegt darin, *was ein Leaderboard-Score bedeuten kann*: die Ladder (Score als Funktion fehlgeschlagener Shots), das Poisson-Risiko-Modell, und `draw_report`. *Lektion:* In einer saturierten Frontier ist das Verständnis der Metrik selbst ein Wettbewerbsvorteil – wer weiß, dass ein Badge "zwei fehlgeschlagene Shots" bedeutet, trifft bessere Entscheidungen.

2. **Nutze die Funktionen des Verifiers, nicht eigene Näherungen.** `rung(k)` ruft `clopper_pearson_upper_bound` und `repetition_overhead` direkt auf. Damit ist jede Schlussfolgerung exakt so definiert wie der Grader. *Lektion:* Wenn du ein System interpretierst, rufe seine eigenen Primitiven auf – nie eine Re-Implementierung, die driften kann.

3. **Invertiere die Metrik, um Beobachtungen zu erklären.** `read_k(board, clean)` nimmt einen Board-Score und sagt, wie viele Shots fehlgeschlagen sind. So wird ein mysteriöses Badge (24.87098) zu einer Erklärung ("zwei fehlgeschlagene Shots, sonst nichts falsch"). *Lektion:* Baue Inversions-Funktionen, die rohe Beobachtungen in Ursachen übersetzen.

4. **Robustheit durch Inhalt, nicht Pfad.** Mitglieder werden per SHA-256 + Größe gefunden; das ZIP wird deterministisch geschrieben (fixe Zeitstempel, sortierte Namen). Gleiche Bytes → gleicher Hash überall. *Lektion:* Reproduzierbarkeit ist ein Designziel, kein Nebenprodukt.

5. **Ehrlichkeit über Unsicherheit.** "Ein Badge kann von einer früheren Version kommen, also behandle diese Zeile als starke Lesung, nicht als Beweis." Und die Warnung, dass die Chemie-Margins dünn genug sind, dass ein anderer Verifier-Build ablehnen könnte. *Lektion:* Trenne klar zwischen "bewiesen", "stark gelesen" und "Vermutung".

6. **Das Tool hinterlassen.** `draw_report` ist eine Funktion, die jeder auf seine eigene `dqi.kmb` zeigen kann. *Lektion:* Wenn du etwas Neues verstehst, verpacke es als Werkzeug, das andere vor dem Teuren (einer Submission) benutzen können.

**Meta-Erkenntnis:** prvsiyan's Notebook ist das *Meta-Ebene*-Gegenstück zu Chilton's und manwithacat's: nicht "welcher Circuit ist am günstigsten", sondern "was kann ich aus einem Score überhaupt schließen?" – und "wie hedge ich den finalen Draw mit zwei verschiedenen DQI-Bytes?"

## 📝 Lern-Notizen

- [ ] Die drei Zahlen unterscheiden: lokaler Score / öffentlicher Leaderboard / finaler Leaderboard (jeder ein eigener Draw)
- [ ] `rung(k)` aus den Verifier-Funktionen bauen (Clopper-Pearson + repetition_overhead), nicht näherungsweise
- [ ] `read_k(board, clean)`: Board-Score → Anzahl fehlgeschlagener Shots invertieren
- [ ] Poisson-Modell: aus (48-Draw-Mittel / Zero-Failure) die Fehler-Zahl λ schätzen; Garwood-Intervall für 95 %
- [ ] `at_rate(lam)`: Wert einer zweiten DQI-Datei mit anderen Bytes (`two − one`) berechnen
- [ ] `draw_report(circuit, spec, salts)`: mehrere Salts laufen, bevor man eine Submission ausgibt
- [ ] Mitglieder per SHA-256 + Größe finden (nicht per Pfad); deterministisches ZIP schreiben
- [ ] Lizenz pro Datei differenzieren (Apache-2.0 vs. "nur Credit"); nie mehr beanspruchen als die Quelle angibt
- [ ] "Suche zuerst den großen Faktor": der 24.94→25.09 Schritt kam zu 0.618 % von invsqrt, kaum von DQI/Chemistry
- [ ] Messreihenfolge-Identität verstehen: CCX(a,b,t) + X-Messung(t) → mess t zuerst, dann CZ(a,b) konditioniert
