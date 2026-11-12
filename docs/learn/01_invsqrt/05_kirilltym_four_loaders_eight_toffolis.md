# Checked compact groups, quadratic inverse and second cache

> **Lernziel:** Die **Quadratic-Inverse**-Optimierung verstehen: (a) ein phasenfreies X/CX/CCX-Fenster mit **quadratischen** Booleschen Funktionen (max_degree 2), das via *affine-conjugated merge* die CCX-Zahl von 4→2 senkt; (b) **Free-Coin-HMR-Cleanups** (q21 ist vor `b417`/`b418` nachweisbar 0 → messen + `BIT_STORE0`); (c) der **26-Wire-ANF-Grenzwertbeweis**, der Gleichheit der Basis-Permutationen belegt.
> **Dauer:** ~20 Minuten lesen
> **Quelle:** kirilltym | Votes: – (im lokalen Kernel-Dump nicht enthalten)
> **Technik:** Quadratic Inverse (CCX-Merge) + Free-Coin Uncompute + ANF-Beweis
> **Level:** Fortgeschritten

> ⚠️ **Slug-Hinweis:** Ordner `kirilltym__quantum-circuits-four-loaders-eight-toffolis`; aktueller Titel *„Checked compact groups, quadratic inverse and second cache“*. InvSqrt-relevant ist der **quadratic inverse**-Teil (Zellen 1, 6–8, 19–26); Chemie/DQI sind Kontext.

---

# Checked compact groups, quadratic inverse and second cache

This update keeps our exact checked inverse and integrates **Lera / marculera's compact-group chemistry**, publicly transported by **Ayodeji**, with **Agniv Banerjee / SomeJoint's** weight refit and **Yoyo's** second cache edit. Circuit, compiler and weight gains belong to those authors. Our contribution is the independent data audit, MPS phase/value checks, complete original native receipts and integration. No contestant generator is executed.

Both changed components passed one new complete, unchanged original check: chemistry **78,080 shots** and DQI **102,400 shots**. Our DQI trial observed **1 value error and 0 phase errors**, still PASS under the official approximate decoder metric. Its repetition penalty and cost are retained. Consequently our measured local geometric mean is **24.55666045**, not a promise of a new Public Score. The unchanged inverse reuses our exact-hash 200,540,928-shot PASS.

Our V9 received official **24.56849**. Yoyo V27 received **24.56851** with seventeen files byte-identical to V9 and only DQI changed to748b; our audit checked its actual downloaded archive. That official comparison motivates selecting this public DQI variant despite the higher cost in our separate independent trial. We do not retry its salt or replace the observed error with somebody else's zero-error report. Fresh Kaggle grading is still needed.

## 1. Composition and derivation

**Inverse.** Start with the exact Isabe V5 inverse and apply the two public SomeJoint HMR windows, then require original SDK serialization to reproduce the exact public `1511…` binary and `03252…` canonical stream. Apply Syed's public five-to-four decode to recover our V7 canonical stream. Every edit is an ordinary readable gate list below; no contestant generator is executed.

For a phase-free X/CX/CCX window, each output wire is a square-free Boolean polynomial in the boundary bits: X adds 1, CX adds its control polynomial, and CCX adds the product of its two control polynomials. Equal output polynomials on every wire prove equal basis permutations, hence the same linear quantum operation on arbitrary superpositions. We check all 26 wire polynomials for Qiu's complete 82-to-95-line window. It contains 3 CCX before and 1 after; the full credited site goes from 4 to 2 after Leo's first merge and Qiu's further affine-conjugated merge. The resource gain is theirs.

Our conservative zero certificate on the V7 stream proves q21=0 immediately before each selected HMR, b417 and b418, over its symbolic input and branch histories. Qiu's window is earlier, phase-free and has the identical complete boundary map, so those facts transfer compositionally. HMR on |0> contributes no input-dependent phase. Each outcome is an internal, non-output bit; a following BIT_STORE0 fixes its cleanup branch. The zero certificate proves these selected zero facts, while the full-program comparison and native accuracy check have the separate scopes reported below. Both HMRs stay in place, and the official verifier, salt and sample generator are untouched.

**Current chemistry.** Replace the previous (9,143,39) factor/306–292 loaders with Lera's (8,143,45) compact-group table and its fifteen compiled loaders, then use SomeJoint's public W/H2_I refit. We transport the exact public data; the unpublished compact-group/compiler/refit generator is not rebuilt. The full original verifier recovers the loaded words and evaluates the unchanged Hamiltonian, shifts, accuracy limits and gap floor. Q falls428→427, T15525→15459; lambda rises47.0214→47.1847, while their product cost falls 312443243.840475→311465857.0666053. All15 changed binaries receive a new audit.

**Current DQI.** The original SDK finds exactly five changed regions between 06aa and748b; the streams agree exactly outside those regions. The edit transports a cached product and replaces one CCZ by CZ, HMR and its conditional CZ correction. For outcome m, erasing cached p contributes (-1)^(m*p); the final correction contributes (-1)^(m*c*d). They cancel when the transported starting product equals the ending product c*d, with the specified carriers clean. Our320-case MPS kernel checks every local boundary assignment satisfying that condition and both HMR outcomes. Removing the new final conditional CZ yields0 value/16 phase failures. This conditional kernel is not a proof of global product equality or whole DQI correctness. The new full original sample has1 value error; the metric prices it rather than imposing universal zero error. The complete receipt is below.

```python
# Setup: Thread-Limits, Pfade, sha256()-Helper.
import os
os.environ.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
from pathlib import Path
import hashlib, json, math, re, shutil, sys, tempfile, time, zipfile
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, FileLink

INPUT, WORK = Path("/kaggle/input"), Path("/kaggle/working")

def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()
```

> **Gepinnte Daten (Zelle 3):** `SOURCE_PINS` (isabe/syed/somejoint34 mit exakten ZIP- + all18-Mitglieder-Hashes), `SELECTED_MEMBERS` (18 Ziel-Hashes), und die Canonical-Hashes `EXPECTED_CANONICAL = ea4f8e67…`, `V7_CANONICAL = 2b954f97…`, `V8_CANONICAL = 7b4000ab…`, `SOURCE_CANONICAL = {somejoint: 03252c11…, syed: …}` sowie `EXPECTED_LOADER_CANONICAL` (15 Loader-Hashes). Vollständig in der Quelle.

```python
# Extrahiert die gepinnten öffentlichen Archive, verifiziert jedes der 18 Mitglieder
# per SHA-256, behält nur die für den Build nötigen Dateien und lädt SDK+Verifier.
archive_hashes = {p: sha256(p) for p in INPUT.rglob("submission.zip")}
folders, actual_sources = {}, {}
for label, pin in SOURCE_PINS.items():
    matching = [p for p, h in archive_hashes.items() if h == pin["archive"]]
    assert len(matching) == 1, (label, "Pinned ZIP missing; reject unexpected latest bytes")
    source = matching[0]
    folder = Path(tempfile.mkdtemp(prefix="exact-" + label + "-"))
    with zipfile.ZipFile(source) as archive:
        assert len(archive.namelist()) == len(set(archive.namelist())) == 18
        assert set(archive.namelist()) == set(pin["members"])
        for name, expected in pin["members"].items():
            with archive.open(name) as stream:
                assert hashlib.file_digest(stream, "sha256").hexdigest() == expected, (label, name)
            needed = ((label == "isabe" and name == "invsqrt.kmb")
                      or (label == "syed" and name == "invsqrt.kmb")
                      or (label == "somejoint34" and (name.startswith("dfthcsos/") or name == "dqi.kmb")))
            if needed:
                target = folder / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))
    folders[label] = folder
    actual_sources[label] = dict(path=str(source), archive_sha256=sha256(source), **pin)
competition = next(p.parents[2] for p in INPUT.rglob("verify_submission_invsqrt.py"))
sys.path[:0] = [str(competition / "kickmix"), str(competition / "verifiers")]
import kickmix as km
from invsqrt import verify_submission_invsqrt as original_inverse
from dfthcsos import verify as original_chemistry

display(
    pd.DataFrame(
        [dict(Source=k, Version=v["version"], ZIP=v["archive"]) for k, v in SOURCE_PINS.items()]
    )
)
```

## 2. Open edits and exact SDK reconstruction

The first data stage correctly rejected a newer mounted SomeJoint archive, before any native call. The volatile input was removed. We reconstruct the same exact public1511 bytes from pinned Isabe data and the two open HMR edits, with mandatory original SDK binary/canonical assertions. This changes source plumbing, not the selected circuit, salt, shots or scientific check conditions. All eighteen members of every mounted public archive are still checked.

Below are Syed's decode window, SomeJoint's HMR windows and Qiu's complete quadratic window. The local bounded ANF proof is recomputed as symbolic algebra in the saved run; MPS and full native checks are completed receipts.

The new SomeJointV34 input is separately pinned by exact ZIP/all18 member hashes. It supplies compiled chemistry/DQI data only. A changed volatile mount still stops before any verifier or submission; no hash assertion is weakened. The two small independent data readers agree on every original loader stream, and new original SDK exports match all fifteen canonical hashes.

### Das Quadratic-Fenster (Qiu) — repräsentativer Auszug

> `OLD_GATE_DATA` / `NEW_GATE_DATA` sind die vollständigen Gate-Listen des Fensters (je ~80–95 Zeilen, in Zelle 6). Struktur: ein **CX-Fan-out** berechnet eine Parität in `q14`, ein `X q14` flippt sie, dann wird uncomputed — flankiert von **2 CCX**. `SLICE_PINS` fixiert `before_sha256 = 1433af21…` / `after_sha256 = 976fa2f1…`. `HMR_RECONSTRUCTION` belegt die exakte SDK-Parität (Isabe `3827…` → SomeJoint `1511…` binary / `03252…` canonical) plus die zwei öffentlichen HMR-Fenster.

```python
# QIU_INTEGRATION (Auszug): der quadratische Merge. max_degree 2, peak_monomials 22,
# 26 Boundary-Wires. old_range [18970,19052] (82 Zeilen) -> new_range [18970,19065] (95 Zeilen).
# Vollständige old_gate_data/new_gate_data + Stats in der Quelle.
QIU_INTEGRATION = {'status': 'PASS',
 'method': 'Exact bounded square-free Boolean ANF for the complete phase-free X/CX/CCX public window; all boundary wires arbitrary/dirty',
 'public_qiu_binary_sha256': '4ccef421a4ebcd30e1c518666099d1831910132da5f5241b368bbd99deaebcc3',
 'boundary_map': 'identical for every wire; no phase operations, measurement, reset, bit write or guard in span',
 'old_stats': {'wires': [14,20,21,22,25,27,33,34,36,37,38,40,41,43,44,45,48,50,51,53,54,55,56,57,58,59],
               'peak_monomials': 22, 'max_degree': 2},
 'new_stats': {'wires': [14,20,21,22,25,27,33,34,36,37,38,40,41,43,44,45,48,50,51,53,54,55,56,57,58,59],
               'peak_monomials': 22, 'max_degree': 2},
 'old_range': [18970, 19052], 'new_range': [18970, 19065]}

# Repräsentativer Anfang des OLD-Fensters (Parität in q14 via CX-Fan-out, 2 CCX):
OLD_GATE_DATA = [
    "CCX q14 q40 q50",
    "CX q43 q40", "CX q59 q14", "CX q58 q14", "CX q56 q14", "CX q55 q14",
    "CX q54 q14", "CX q53 q14", "CX q51 q14", "CX q48 q14", "CX q45 q14",
    "CX q44 q14", "CX q43 q14", "CX q41 q14", "CX q38 q14", "CX q37 q14",
    # … CX-Fan-out über alle Boundary-Wires …
    "X q14",
    "CCX q40 q14 q50",
    "X q14",
    "CX q58 q14", "CX q57 q14", "CX q56 q14", "CX q55 q14", "CX q54 q14",
    # … Uncompute des Fan-outs …
]
# NEW_GATE_DATA beginnt analog mit dem CX-Fan-out ("CX q59 q14", "CX q58 q14", …)
# und hat am Ende 1 statt 3 CCX (affine-conjugated shared-target merge).
```

```python
# FREE-COIN-ZERTIFIKAT: beweist symbolisch, dass q21==0 unmittelbar vor den
# ausgewählten HMR (b417, b418) ist — über einen konservativen affinen/opaken
# Produkt-Abstraktionszustand (alle 22-Bit-Inputs, alle Branch/HMR-Historien).
# Fügt nach jedem ausgewählten HMR ein BIT_STORE0 ein (Cleanup-Branch fixieren).
def certify_and_specialize_free_coins(raw):
    lines = raw.splitlines()
    zero, one = frozenset(), frozenset({0})
    next_atom = 100
    products = {}

    def unknown():
        nonlocal next_atom
        next_atom += 1
        return frozenset({next_atom})

    def product(a, b):
        if not a or not b:
            return zero
        if a == one:
            return b
        if b == one or a == b:
            return a
        key = frozenset((a, b))
        if key not in products:
            products[key] = unknown()
        return products[key]

    q = [unknown() if i < 22 else zero for i in range(62)]
    stack = []
    certificates = []
    selected = {"b417", "b418"}
    for line_number, line in enumerate(lines):
        tokens = line.split()
        if not tokens:
            continue
        op = tokens[0]
        if op == "PUSH_CONDITION":
            stack.append(q.copy())
            continue
        if op == "POP_CONDITION":
            before = stack.pop()
            q = [a if a == b else unknown() for a, b in zip(before, q)]
            continue
        wires = [int(t[1:]) for t in tokens[1:] if re.fullmatch(r"q\d+", t)]
        if op == "HMR" and tokens[-1] in selected:
            assert not stack and tokens == ["HMR", "q21", tokens[-1]]
            assert q[21] == zero, ("Cannot prove selected measured qubit zero", line_number, q[21])
            certificates.append(dict(line=line_number, gate=line, symbolic_value=[], condition_depth=0,
                                     proof="Conservative affine/opaque-product abstract state is identically zero for all 22-bit inputs and all branch/HMR histories, scratch initially zero."))
        old = q.copy()
        if op == "X":
            q[wires[0]] ^= one
        elif op == "CX":
            q[wires[1]] ^= q[wires[0]]
        elif op == "CCX":
            q[wires[2]] ^= product(q[wires[0]], q[wires[1]])
        elif op in ("R", "HMR"):
            q[wires[0]] = zero
        elif op == "SWAP":
            a, b = wires
            q[a], q[b] = q[b], q[a]
        elif op == "CSWAP":
            c, a, b = wires
            difference = product(q[c], q[a] ^ q[b])
            q[a] ^= difference
            q[b] ^= difference
        elif op in ("Z", "CZ", "CCZ", "NEG", "Z_POW", "REGISTER", "APPEND_TO_REGISTER", "INFO_TAG", "BIT_STORE0", "BIT_STORE1", "BIT_INVERT"):
            pass
        else:
            raise ValueError((line_number, line))
        if "if" in tokens:
            q = [a if a == b else unknown() for a, b in zip(old, q)]
    assert not stack and len(certificates) == 2
    assert not any(line.startswith("APPEND_TO_REGISTER b417 ") or line.startswith("APPEND_TO_REGISTER b418 ") for line in lines)
    output = []
    for line in lines:
        output.append(line)
        if line in ("HMR q21 b417", "HMR q21 b418"):
            output.append("BIT_STORE0 " + line.split()[-1])
    candidate = "\n".join(output) + "\n"

    return candidate, certificates
```

```python
# REKONSTRUKTIONS-PIPELINE: Isabe-Kanonical -> +2 SomeJoint-HMR-Fenster -> exakte
# 1511-Bytes (SDK-Parity) -> Syed 5-to-4 Decode -> V7 -> Free-Coin-Zertifikat -> V8
# -> Qiu-Quadratic-Merge -> Candidate. Jeder Schritt per SHA-256 gegen Canonical-Pins.
submission = Path(tempfile.mkdtemp(prefix="four-loaders-v10-"))
(submission / "dfthcsos").mkdir()
isabe_canonical = WORK / "isabe_source_inverse.kmx"
km.Circuit.from_file(str(folders["isabe"] / "invsqrt.kmb"), format="kmb").to_file(str(isabe_canonical), format="kmx")
assert sha256(isabe_canonical) == HMR_RECONSTRUCTION["source_isabe_canonical_sha256"]
assert sha256(folders["isabe"] / "invsqrt.kmb") == HMR_RECONSTRUCTION["source_isabe_binary_sha256"]
base = isabe_canonical.read_text()
for window in HMR_RECONSTRUCTION["windows"]:
    left, right = "\n".join(window["before"]) + "\n", "\n".join(window["after"]) + "\n"
    assert base.count(left) == 1
    base = base.replace(left, right)
assert hashlib.sha256(base.encode()).hexdigest() == HMR_RECONSTRUCTION["expected_somejoint_canonical_sha256"]
derived_kmx, derived_kmb = WORK / "derived_somejoint1511.kmx", WORK / "derived_somejoint1511.kmb"
derived_kmx.write_text(base)
km.Circuit.from_file(str(derived_kmx), format="kmx").to_file(str(derived_kmb), format="kmb")
assert sha256(derived_kmb) == HMR_RECONSTRUCTION["expected_somejoint_binary_sha256"]
derived_roundtrip = WORK / "derived_somejoint1511_roundtrip.kmx"
km.Circuit.from_file(str(derived_kmb), format="kmb").to_file(str(derived_roundtrip), format="kmx")
assert sha256(derived_roundtrip) == HMR_RECONSTRUCTION["expected_somejoint_canonical_sha256"]
source_texts = {"somejoint": base}
syed_canonical = WORK / "syed_source_inverse.kmx"
km.Circuit.from_file(str(folders["syed"] / "invsqrt.kmb"), format="kmb").to_file(str(syed_canonical), format="kmx")
assert sha256(syed_canonical) == SOURCE_CANONICAL["syed"]
source_texts["syed"] = syed_canonical.read_text()
old_slice, new_slice = "\n".join(OLD_GATE_DATA) + "\n", "\n".join(NEW_GATE_DATA) + "\n"
assert hashlib.sha256(old_slice.encode()).hexdigest() == SLICE_PINS["before_sha256"]
assert hashlib.sha256(new_slice.encode()).hexdigest() == SLICE_PINS["after_sha256"]
assert base.count(old_slice) == source_texts["syed"].count(new_slice) == 1
v7_text = base.replace(old_slice, new_slice)
assert hashlib.sha256(v7_text.encode()).hexdigest() == V7_CANONICAL
v8_text, selected_zero_facts = certify_and_specialize_free_coins(v7_text)
assert hashlib.sha256(v8_text.encode()).hexdigest() == V8_CANONICAL

qiu_old, qiu_new = QIU_INTEGRATION["old_gate_data"], QIU_INTEGRATION["new_gate_data"]
old_map, old_stats = phase_free_anf(qiu_old)
new_map, new_stats = phase_free_anf(qiu_new)
assert old_map == new_map
assert old_stats == QIU_INTEGRATION["old_stats"] and new_stats == QIU_INTEGRATION["new_stats"]
qiu_old_text, qiu_new_text = "\n".join(qiu_old) + "\n", "\n".join(qiu_new) + "\n"
assert hashlib.sha256(qiu_old_text.encode()).hexdigest() == QIU_INTEGRATION["old_span_sha256"]
assert hashlib.sha256(qiu_new_text.encode()).hexdigest() == QIU_INTEGRATION["new_span_sha256"]
assert v7_text.count(qiu_old_text) == v8_text.count(qiu_old_text) == 1
public_qiu = v7_text.replace(qiu_old_text, qiu_new_text)
assert hashlib.sha256(public_qiu.encode()).hexdigest() == QIU_INTEGRATION["public_qiu_canonical_sha256"]
public_kmx, public_kmb = WORK / "public_qiu_inverse.kmx", WORK / "public_qiu_inverse.kmb"
public_kmx.write_text(public_qiu)
km.Circuit.from_file(str(public_kmx), format="kmx").to_file(str(public_kmb), format="kmb")
assert sha256(public_kmb) == QIU_INTEGRATION["public_qiu_binary_sha256"]
public_roundtrip = WORK / "public_qiu_roundtrip.kmx"
km.Circuit.from_file(str(public_kmb), format="kmb").to_file(str(public_roundtrip), format="kmx")
assert sha256(public_roundtrip) == QIU_INTEGRATION["public_qiu_canonical_sha256"]
candidate_text = v8_text.replace(qiu_old_text, qiu_new_text)
assert hashlib.sha256(candidate_text.encode()).hexdigest() == EXPECTED_CANONICAL
canonical = WORK / "selected_inverse.kmx"
canonical.write_text(candidate_text)
km.Circuit.from_file(str(canonical), format="kmx").to_file(str(submission / "invsqrt.kmb"), format="kmb")
inverse_circuit = km.Circuit.from_file(str(submission / "invsqrt.kmb"), format="kmb")
roundtrip = WORK / "selected_inverse_roundtrip.kmx"
inverse_circuit.to_file(str(roundtrip), format="kmx")
assert sha256(roundtrip) == EXPECTED_CANONICAL
shutil.copyfile(folders["somejoint34"] / "dqi.kmb", submission / "dqi.kmb")
for name in SELECTED_MEMBERS:
    if name.startswith("dfthcsos/"):
        shutil.copyfile(folders["somejoint34"] / name, submission / name)
assert {name: sha256(submission / name) for name in SELECTED_MEMBERS} == SELECTED_MEMBERS
print("Exact26-wire ANF boundary identity, original SDK public/candidate parity and all18 member hashes: PASS")
print("Transferred certified zero facts:", selected_zero_facts)
```

## 3. Reachable loaders and measurement phases

All **1,220 valid addresses**, both reachable incoming five-word batches and all fifteen actual streams were checked: **36,600 trajectories**. All91,500 words satisfy bit7=bit6. This is the reachable forward/reverse contract clarified by [host Tanuj Khattar](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion/753092), not an arbitrary-target XOR claim.

For every HMR event our MPS engine introduces an independent formal phase coefficient. Every final coefficient and the constant phase vanish; address and scratch restore, and every R acts on zero. The preregistered negative removes the first conditional CZ in batch4, **CZ q123 q3 if b0**:0 value and 152 formal phase-coefficient failures over2,440 cases. These are not native grading error counts and do not reuse the old292-family negative6/2726.

The older guarded-CZ reader first rejected these new bytes because its scope required128 qubits: batches7 and13 use126. Its assertion was retained. The existing stricter opcode-limited loader reader already supports up to128 and agreed exactly with our independent inverse-format codec on all15 streams. These streams need no PUSH/CZ/POP normalization. Original SDK canonical exports subsequently matched every original stream, before full native.

```python
# Normalisiert Loader-CZ-Streams (PUSH/POP -> explizite "if"-Bedingungen) und
# exportiert alle 15 Loader als .kmx; prüft die CCX-Zählung pro Batch.
def normalize_loader_cz(text):
    guard, normalized = None, []
    for line in text.splitlines():
        fields = line.split()
        if fields[0] in ("REGISTER", "APPEND_TO_REGISTER"):
            assert guard is None
            normalized.append(line)
        elif fields[0] == "PUSH_CONDITION":
            assert guard is None and len(fields) == 3 and fields[1] == "if"
            assert re.fullmatch(r"b\d+", fields[2])
            guard = fields[2]
        elif fields[0] == "POP_CONDITION":
            assert guard is not None and len(fields) == 1
            guard = None
        elif guard is not None:
            assert fields[0] == "CZ" and len(fields) == 3
            normalized.append(line + " if " + guard)
        else:
            assert fields[0] in ("X", "CX", "CCX", "R", "HMR", "CZ")
            if "if" in fields:
                assert fields[0] == "CZ" and len(fields) == 5 and fields[3] == "if"
            normalized.append(line)
    assert guard is None
    return "\n".join(normalized) + "\n"


loader_texts, original_loader_texts, export_rows = {}, {}, []
export_dir = WORK / "mps_loader_inputs"
export_dir.mkdir(exist_ok=True)
shutil.copyfile(submission / "dfthcsos/submission.npz", export_dir / "submission.npz")
for k in range(15):
    name = f"angle_k_{k}"
    output = export_dir / (name + ".kmx")
    km.Circuit.from_file(str(submission / "dfthcsos" / (name + ".kmb")), format="kmb").to_file(
        str(output), format="kmx"
    )
    assert sha256(output) == EXPECTED_LOADER_CANONICAL[str(k)], k
    original_loader_texts[name] = output.read_text()
    loader_texts[name] = normalize_loader_cz(output.read_text())
    (export_dir / (name + ".normalized.kmx")).write_text(loader_texts[name])
    export_rows.append(
        dict(batch=k, CCX=sum(l.startswith("CCX ") for l in loader_texts[name].splitlines()),
             canonical_sha256=sha256(output))
    )
assert [row["CCX"] for row in export_rows] == [307, 307, 307, 307, 285, 285, 285, 282, 285, 285, 285, 285, 285, 284, 285]
(export_dir / "angle_kmxs.json").write_text(json.dumps(loader_texts))
display(pd.DataFrame(export_rows))
```

### Independent Mac MPS comparisons and negative controls

The functions below are readable reproduction tools. Numerical tensors use Mac MPS with no CPU fallback; the Kaggle CPU saved run does not invoke them. Our completed receipts record each audit, its exact bytes and scope.

The retained inverse has the previous all3,133,452-input MPS comparisons at two deterministic HMR streams plus forced selected coins, local4096-case HMR windows and the exact26-wire ANF identity. This is not numerical enumeration of every whole-program HMR history. Its fixed missingCCX negative failed input restoration in both streams before a phase count was assigned.

The new compact427 audit and its0/152 negative have their own records; no old40890-case proof transfers to changed binaries. The new748b cache audit has320 conditional cases and0/16 negative failures. Global cache equality remains INCOMPLETE. Historical06aa80/negative4 and unselected2e72400-case audits remain explicitly historical. Old receipt NOTRUN/PENDING labels describe their preregistration time; later original PASS markers record completion.

> **MPS-Audit-Engines (Zellen 12–18):** `run_symbolic_mps_audit` (symbolische Phasen-Koeffizienten pro HMR, wie in Notebook 03), `compare_free_coin_inverse_mps` (Inverse-Vergleich auf 3,133,452 Inputs), `audit_hmr_windows_mps` (4096-Fall-HMR-Fenster), `audit_loader_negative_mps` (entferntes `CZ q123 q3 if b0` → 0 value / **152 phase**), `audit_historical_unselected_dqi_kernels_mps` und `audit_selected_second_cache_mps`. Letztere zeigt die Phasen-Kompensation explizit:

```python
# DQI-Cache-Kernel: prüft, dass Erasure des gecachten Produkts p bei Outcome m
# (-1)^(m*p) und die finale Korrektur (-1)^(m*c*d) sich exakt aufheben, wenn
# Startprodukt == Endprodukt c*d und Carrier clean sind. Negative Control:
# Entfernen von "CZ q844 q852 if b101622" -> 0 value / 16 phase failures.
def audit_selected_second_cache_mps():
    import os
    os.environ["PYTORCH_ENABLE_MPS_FALLBACK"]="0"
    import torch
    torch.set_num_threads(1)
    assert torch.backends.mps.is_available(), "Mac MPS required; no CPU fallback"
    receipt=SELECTED_DQI_MPS_RECEIPT
    names=receipt["preregistration"]["boundary_wires"]
    scratch=receipt["preregistration"]["scratch"]
    old,new=receipt["kernels"][0]["old"],receipt["kernels"][0]["new"]
    n=len(names)
    cases=torch.arange(1<<(n+1),device="mps",dtype=torch.int64)
    a,b,c,d=[(cases>>j)&1 for j in range(4)]
    cases=cases[(a&b)==(c&d)]
    def simulate(lines):
        q={name:((cases>>j)&1).clone() for j,name in enumerate(names)}
        q.update({name:torch.zeros_like(cases) for name in scratch})
        m=(cases>>n)&1;phase=torch.zeros_like(cases)
        for line in lines:
            op,*tokens=line.split();wires=[x for x in tokens if x.startswith("q")]
            if op=="CCX":q[wires[2]]^=q[wires[0]]&q[wires[1]]
            elif op=="CX":q[wires[1]]^=q[wires[0]]
            elif op=="SWAP":q[wires[0]],q[wires[1]]=q[wires[1]],q[wires[0]]
            elif op in ("Z","CZ","CCZ"):
                term=torch.ones_like(cases)
                for wire in wires:term&=q[wire]
                if "if" in tokens:assert tokens[-1]=="b101622";term&=m
                phase^=term
            elif op=="HMR":
                assert tokens[-1]=="b101622";phase^=q[wires[0]]&m;q[wires[0]]=torch.zeros_like(cases)
            else:raise ValueError(line)
        return torch.stack([q[name] for name in names+scratch]),phase
    expected,phase=simulate(old);actual,actual_phase=simulate(new)
    assert torch.equal(expected,actual) and torch.equal(phase,actual_phase)
    removed="CZ q844 q852 if b101622"
    broken,broken_phase=simulate([line for line in new if line!=removed])
    failures=dict(value_failures=int((expected!=broken).any(0).sum().item()),phase_failures=int((phase!=broken_phase).sum().item()))
    assert failures==dict(value_failures=0,phase_failures=16)
    return dict(cases=int(cases.numel()),negative=failures,scope=receipt["scope"])
```

## 4. Complete original native receipts and exact reuse

Chemistry passed the unchanged original default **78,080-shot** check once at `nov4-v10-compact427-independent`; its actual family SHA is4c2fe44e…. DQI passed the unchanged original default **102,400-shot** check once at `nov4-v10-yoyo748b-independent`, with **1 value/0 phase errors**, repetition factor **1.1967314991687559** and cost **377098226037.6405**. Approximation is part of the official metric. No error is masked and no salt is retried. Each LOCAL attempt1 was recorded before the sole remote call. Both complete original reports, conditions and PASS/attempt1 markers were downloaded.

The exact unchanged0104 inverse reuses our V9 original200,540,928-shot PASS at `nov4-v9-qiu-coins-independent`. The original Hamiltonian, fixed shifts, bounds, gap floor, spec, sample generator, shots, errors and penalties are preserved. Different hashes/salts are separate trials, not paired samples. This saved run checks bytes, original SDK serialization and original verifier source hashes, then exports completed receipts; it starts no new native verification. The data-stage preregistration fields remain historical; the complete original reports and markers provide the finished status.

> **`FULL_REPORTS` (Zelle 20, 162 KB — hier die Cost-relevanten Felder):**
>
> | Task | Status | Cost (score) | Qubits | Shots | Fehler | Repetition |
> |---|---|---:|---:|---:|---:|---:|
> | **invsqrt** (`0104…`) | PASS | **97,921.54** | **62** | 200,540,928 | – | – |
> | dfthcsos (`4c2fe44e…`) | PASS | 311,465,857.07 | 427 | 78,080 | – | – |
> | dqi (`748b`) | PASS | 377,098,226,037.64 | 891 | 102,400 | **1 value / 0 phase** | 1.196731499 |
>
> Chemie-Metrics: λ_eff 47.1847, toffoli 15,459, batch 5, 15 Circuits.

```python
# Verifiziert, dass die FULL_REPORTS-Hashes zu den gewählten Mitgliedern passen,
# dass die Original-Verifier-Quellen unverändert sind, und zeigt Task/Shots/Cost/Salt.
assert FULL_REPORTS["invsqrt"]["circuit_sha256"] == SELECTED_MEMBERS["invsqrt.kmb"]
assert FULL_REPORTS["dqi"]["circuit_sha256"] == SELECTED_MEMBERS["dqi.kmb"]
assert FULL_REPORTS["dfthcsos"]["submission_sha256"] == "4c2fe44e0ae4289e50a37428a5770b7ecbde184da0fa2aaed0b844ee15cc94b0"
actual_verifiers = {str(p.relative_to(competition)):sha256(p) for p in (competition / "verifiers").rglob("*.py")}
assert actual_verifiers == ORIGINAL_VERIFIER_HASHES
for task, shots in [("invsqrt", 200540928), ("dfthcsos", 78080), ("dqi", 102400)]:
    assert FULL_REPORTS[task]["status"] == "PASS" and FULL_REPORTS[task]["verified_shots"] == shots
    (WORK / ("full_" + task + "_report.json")).write_text(json.dumps(FULL_REPORTS[task], indent=2))
display(pd.DataFrame([dict(Task=k, Status=v["status"], Shots=v["verified_shots"], Cost=v["score"], Salt=RECEIPT_SALTS[k]) for k,v in FULL_REPORTS.items()]))
print("Complete chemistry metrics:", FULL_REPORTS["dfthcsos"]["metrics"])
print("DQI sampled errors:", FULL_REPORTS["dqi"]["value_errors"], FULL_REPORTS["dqi"]["phase_errors"])
print("DQI repetition penalty:", FULL_REPORTS["dqi"]["repetition_factor"])
```

## 5. Factual comparison and the decoder audit boundary

Every selected cost below comes from our own complete original receipt, including the newly observed DQI error and its repetition penalty. Our local GM24.55666045 is below V9's local forecast; the separate06aa/fullreceipt combination would forecast24.59417398, but those are independent samples. We select748b because YoyoV27's actual official24.56851 exceeds ourV9's 24.56849 with17 identical members and only that DQI changed. Its public grading evidence is separate from our new native trial. New chemistry is also independently checked. We retain all observations, including lower official V8, and make no claim about unread official component error counts.

The inherited decoder is approximate. Its rare high-weight approximation and David Pilný's reported weight16 baseline failure are disclosed; we have not reproduced that specific full input. The conditional320-case kernel does not close global cache equality: the earlier bounded ANF budget was exceeded, SAT was not run, and equality remains INCOMPLETE. This is neither a whole-DQI proof nor a native FAIL. Our original native status is PASS with1/0 errors. Finite samples, whether0/0 or1/0, do not establish universal correctness.

> **📊 InvSqrt-Cost-Progression (aus `V5_REPORTS`/`V7_REPORTS`/`V8_REPORTS`/`V9_REPORTS`, alle 62 Q / 200,540,928 Shots):**
>
> | Version | Inverse-Cost | Mean Toffolis | max Toffolis | t_count | Official Score |
> |---|---:|---:|---:|---:|---:|
> | Four Loaders V5 | 98,309.06 | 1287.16 | 1542 | 14.50 | 24.50427 |
> | Four Loaders V7 | 98,123.17 | 1284.17 | 1539 | 14.50 | 24.55164 |
> | Four Loaders V8 | 98,045.64 | 1283.67 | 1539 | 11.50 | 24.52069 |
> | Four Loaders V9 | **97,921.54** | **1281.66** | 1537 | 11.50 | **24.56849** |
>
> Alle: `worst_error_over_tolerance = 0.99932`, `worst_x = 161`, `rotation_count = 41`.

```python
# REFERENCE_COSTS + lokaler geometrischer Mittelwert; baut die Vergleichstabelle
# V5/V7/V8/V9/Selected und druckt den lokalen Kandidaten-GM (nicht offiziell).
REFERENCE_COSTS = dict(
    invsqrt=2076774.233715282, dfthcsos=3355599588.3155375, dqi=24439463583672.93
)


def local_geometric_mean(reports):
    return math.prod(REFERENCE_COSTS[k] / reports[k]["score"] for k in REFERENCE_COSTS) ** (1 / 3)


table = pd.DataFrame(
    [
        dict(Portfolio="Four Loaders V5", Inverse=V5_REPORTS["invsqrt"]["score"], Chemistry=V5_REPORTS["dfthcsos"]["score"], DQI=V5_REPORTS["dqi"]["score"], LocalGM=local_geometric_mean(V5_REPORTS), OfficialPublicScore=24.50427, Evidence="our previous full receipts"),
        dict(Portfolio="Four Loaders V7", Inverse=V7_REPORTS["invsqrt"]["score"], Chemistry=V7_REPORTS["dfthcsos"]["score"], DQI=V7_REPORTS["dqi"]["score"], LocalGM=local_geometric_mean(V7_REPORTS), OfficialPublicScore=24.55164, Evidence="our previous full exact-hash receipts"),
        dict(Portfolio="Four Loaders V8", Inverse=V8_REPORTS["invsqrt"]["score"], Chemistry=V8_REPORTS["dfthcsos"]["score"], DQI=V8_REPORTS["dqi"]["score"], LocalGM=local_geometric_mean(V8_REPORTS), OfficialPublicScore=V8_OFFICIAL_SCORE, Evidence="our full receipts and observed Kaggle result; component grading error counts not read"),
        dict(Portfolio="Four Loaders V9", Inverse=V9_REPORTS["invsqrt"]["score"], Chemistry=V9_REPORTS["dfthcsos"]["score"], DQI=V9_REPORTS["dqi"]["score"], LocalGM=local_geometric_mean(V9_REPORTS), OfficialPublicScore=24.56849, Evidence="our completed original receipts; exact Kaggle V9 result"),
        dict(Portfolio="This checked composition", Inverse=FULL_REPORTS["invsqrt"]["score"], Chemistry=FULL_REPORTS["dfthcsos"]["score"], DQI=FULL_REPORTS["dqi"]["score"], LocalGM=local_geometric_mean(FULL_REPORTS), OfficialPublicScore=None, Evidence="new full original chemistry78080 andDQI102400 receipts; DQI1value/0phase and penalty retained; exact inverse reused"),
    ]
)
display(table)
table.to_csv(WORK / "factual_comparison.csv", index=False)
print("Local candidate GM (not official):", local_geometric_mean(FULL_REPORTS))
print("Confirmed public leader when this update began: YoyoV27/365630305, official24.56851; exact downloaded archive audited. Fresh grading required.")
```

```python
# Zwei-Panel-Plot: links Chemie (V9 (9,143,39) Q428/T15525 -> compact (8,143,45)
# Q427/T15459), rechts Yoyo-Second-Cache (320 MPS Fälle PASS, Original 102400
# Shots PASS 1/0 R=1.196731499, globale Cache-Gleichheit INCOMPLETE).
fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), layout="constrained")
for ax in axes: ax.axis("off")
axes[0].text(.5,.92,"Checked compact-group chemistry",ha="center",weight="bold",fontsize=13)
axes[0].text(.22,.59,"Previous V9\n(9,143,39)\nQ428 · T15525",ha="center",va="center",fontsize=11,bbox=dict(boxstyle="round,pad=.7",fc="#e1edf5",ec="#64748b"))
axes[0].text(.78,.59,"Selected compact\n(8,143,45)\nQ427 · T15459",ha="center",va="center",fontsize=11,bbox=dict(boxstyle="round,pad=.7",fc="#d4eee7",ec="#64748b"))
axes[0].annotate("",xy=(.6,.59),xytext=(.4,.59),arrowprops=dict(arrowstyle="->",lw=2,color="#64748b"))
axes[0].text(.5,.2,"Lera / Ayodeji compiled data + SomeJoint refit\nOur36600-case formal-phase audit + original78080 PASS",ha="center",fontsize=10)
axes[1].text(.5,.92,"Yoyo second cache: separate evidence",ha="center",weight="bold",fontsize=13)
axes[1].text(.5,.66,"320 local MPS cases: PASS\nAssumes endpoint product equality and clean carriers",ha="center",va="center",fontsize=11,bbox=dict(boxstyle="round,pad=.65",fc="#f5ebcf",ec="#64748b"))
axes[1].text(.5,.35,"Original102400 shots: PASS\n1 value / 0 phase errors · R=1.196731499",ha="center",va="center",fontsize=11,bbox=dict(boxstyle="round,pad=.65",fc="#e1edf5",ec="#64748b"))
axes[1].text(.5,.1,"Global cache equality remains INCOMPLETE",ha="center",fontsize=10)
fig.savefig(WORK/"checked_composition.png",dpi=170)
plt.show()
```

## 6. Exact output and evidence

Only the eighteen required competition members enter submission.zip. The original compiled data, complete hashes, canonical exports, full reports, scientific conditions, MPS/negative/incomplete records and attribution remain separately readable. Every factor array, including optional metadata, is copied byte for byte. The ZIP has fixed member order/timestamps and deterministic compression; packaging does not change any selected circuit bytes.

Earlier float-gauge/offset-noise, GF2-span-zero, scratch62→62, phase-merge0 and bounded HMR reuse scans remain negative/incomplete history. We do not select unverified further transformations or execute unpublished generators.

```python
# Schreibt verification_receipt.json / conditions / source_pins / MPS-Reports und
# packt exakt die 18 Mitglieder deterministisch in submission.zip (SHA-geprüft).
receipt = dict(
    status="PASS",
    verification_mode="Our completed original full exact-hash receipts; current run validates bytes/SDK serialization",
    source_pins=actual_sources,
    selected_members=SELECTED_MEMBERS,
    full_reports=FULL_REPORTS,
    conditions=FULL_CONDITIONS,
    receipt_salts=RECEIPT_SALTS,
    mps_reports=MPS_REPORTS,
    incomplete_cache_audit=CACHE_AUDIT,
    official_public_score_this_version=None,
    warning="Local GM and successful Save&Run are not an official competition submission or score",
)
receipt["quadratic_window_proof"] = QIU_INTEGRATION
receipt["exact_hmr_source_recipe"] = HMR_RECONSTRUCTION
receipt["prior_v8_official_score"] = V8_OFFICIAL_SCORE
receipt["prior_v8_local_reports"] = V8_REPORTS
(WORK / "verification_receipt.json").write_text(json.dumps(receipt, indent=2))
(WORK / "verification_conditions.json").write_text(json.dumps(FULL_CONDITIONS, indent=2))
(WORK / "source_pins.json").write_text(json.dumps(actual_sources, indent=2))
for name, value in MPS_REPORTS.items():
    (WORK / (name + ".json")).write_text(json.dumps(value, indent=2))
output = WORK / "submission.zip"
with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
    for name in sorted(SELECTED_MEMBERS):
        info = zipfile.ZipInfo(name, date_time=(2026, 11, 4, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, (submission / name).read_bytes(), compresslevel=1)
with zipfile.ZipFile(output) as archive:
    assert len(archive.namelist()) == 18 and archive.testzip() is None
    assert {name: hashlib.sha256(archive.read(name)).hexdigest() for name in archive.namelist()} == SELECTED_MEMBERS
manifest = dict(archive_sha256=sha256(output), members=SELECTED_MEMBERS,
                local_gm=local_geometric_mean(FULL_REPORTS), official_public_score=None)
(WORK / "output_manifest.json").write_text(json.dumps(manifest, indent=2))
print(json.dumps(manifest, indent=2))
display(FileLink(str(output)))
receipt["prior_v9_official_score"] = 24.56849
receipt["selected_dqi_observed_value_errors"] = 1
(WORK / "verification_receipt.json").write_text(json.dumps(receipt, indent=2))
```

## 7. Credits and licence scopes

Current chemistry is **Lera / marculera's compact-group table and fifteen compiled loaders**, publicly transported by **Ayodeji** [V3/365612298](https://www.kaggle.com/code/ayodejiibrahimlateef/vqcc-24-56308-local?scriptVersionId=365612298), with **Agniv Banerjee / SomeJoint's W/H2_I refit** [V34/365647181](https://www.kaggle.com/code/somejoint/quantum-circuits-24-59-local-gm-chem-refit?scriptVersionId=365647181), exact output dataset21676999. Lera's public [compact-groups notebook/365256248](https://www.kaggle.com/code/marculera/df-thc-10x-compact-groups-from-the-hamiltonian?scriptVersionId=365256248) records the pipeline lineage. SomeJoint credits Ahmed Berat Özer, kozykappa, Artem1410/anazemcev, Michael Rustad, Kozykorpesh, Sumit Chongder and Phuc Thai. These public outputs carry upstream Apache-2.0 scopes as stated in their source notices; we execute neither their generators nor optimizers. Our new work is the independent all15-stream audit/original SDK parity/full78080 check and integration.

Current DQI748b is **Yoyo / yoyobar's second cache edit**, directly audited in [V27/365630305](https://www.kaggle.com/code/yoyobar/lb-22-99-invsqrt-101-62-qubits?scriptVersionId=365630305), exact output dataset21674961, transported byte-identically by SomeJointV34. Its gain is Yoyo's; our contribution is the independently downloaded SDK delta, conditional320-case audit/negative and one original102400-shot receipt, including the observed1value/0phase error and penalty. The unchanged inverse remains the V9 composition credited below; old chemistry85c4/Syed306292 and06aa are historical here, not selected.

* **Agniv Banerjee / SomeJoint:** [V32 / 365444796](https://www.kaggle.com/code/somejoint/quantum-circuits-24-53-local-gm-window-merges?scriptVersionId=365444796), exact public output dataset21651900. Here those exact1511 bytes are reconstructed by original SDK from Isabe3827 and his two open HMR windows; his volatile input is not mounted. Two new measured-product reuse windows, normalization and phase-split carries are his public gains. His public notebook uses Apache-2.0; inherited components retain their upstream terms.
* **Syed Asad Ali / syed3000:** [Own Circuit V2 / 365469277](https://www.kaggle.com/code/syed3000/vqcc-own-circuit-portfolio-notebook?scriptVersionId=365469277), dataset21655186. Public five-to-four decode and 306/292 compiler outputs, including the inherited 891Q approximate decoder family. [V1 / 365434474](https://www.kaggle.com/code/syed3000/vqcc-own-circuit-portfolio-notebook?scriptVersionId=365434474) provides the preceding compiler/decode reference. These are public compiled circuits; we do not claim a rebuild of an unpublished generator. Public notebook code is Apache-2.0, with historical DQI design terms separately scoped below.
* **Isabe11aM00re:** [V5 / 365423520](https://www.kaggle.com/code/isabe11am00re/qcc-v58x-submission?scriptVersionId=365423520), dataset21649221. The prior V7 `65ec…` W/H2_I refit belongs to Isabe; the historical V9 factor was Heliosli's fixed-word refit. Her dataset LICENSE.md releases her own work under Apache-2.0 and retains every other component's upstream terms.
* **Leo Tang / leotang09:** [V11 /365535779](https://www.kaggle.com/code/leotang09/vqcc-t7421-submission?scriptVersionId=365535779), first single-accumulator merge on our public V7 composition, public inverse53000387. Credit for that CCX reduction belongs to Leo. Original public notebook code scope Apache-2.0; inherited circuit terms stay upstream.
* **Qiuqiu / qiuqiuh:** [V1 /365561504](https://www.kaggle.com/code/qiuqiuh/qcc-refresh-v65w-sx-sy7-inverse?scriptVersionId=365561504), exact public inverse4ccef421a4ebcd30e1c518666099d1831910132da5f5241b368bbd99deaebcc3. Further affine-conjugated shared-target merge on Leo's stream. Its complete82/95-line gate window is open above, independently proved equal and integrated with our two retained coin cleanups. Public compiled KMB was extracted as data only; no claim to execute or rebuild the unpublished merge_invsqrt_quadratic.py generator. Original public notebook code Apache-2.0; inherited component scopes remain separate.
* **Malachi W. Moody:** [VQCC Open Notes V2 /365560814](https://www.kaggle.com/code/malachiwmoody/vqcc-open-notes?scriptVersionId=365560814), public free-coin method/scan and b417 observation, crediting Syed's earlier cleanup idea. We independently certify the two zero facts and retain both HMRs with two subsequent BIT_STORE0 instructions; his reported measurements are not our receipts.
* **Heliosli:** [V5 /365542459](https://www.kaggle.com/code/heliosli/the-dataset-is-public-now-enjoy?scriptVersionId=365542459), public 85c4 W/H2_I refit on the exact inherited word table. Historical V9 bytes were transported by Yoyo V26; Heliosli's refit gain is separately credited, and inherited scopes remain unchanged.
* **Yoyo / yoyobar:** [V22 /365400493](https://www.kaggle.com/code/yoyobar/lb-22-99-invsqrt-101-62-qubits?scriptVersionId=365400493), public cache-edit lineage. Historical06aa is transported here by pinned IsabeV5 and was used in ourV7. The later [V26 /365568445](https://www.kaggle.com/code/yoyobar/lb-22-99-invsqrt-101-62-qubits?scriptVersionId=365568445) input still transports Helios85c4 factor; its2e72 DQI is historical unselected here. Its full0/0 sample and V8's lower official portfolio result remain recorded. The cache method belongs to Yoyo; public notebook code is Apache-2.0, inherited decoder/source terms remain separate.
* **Kirill Tymchishin:** independent gate-data integration, strict source/SDK pinning, new complete original native receipts, Mac MPS phase/value audits and negative controls, readable presentation. [Our V5 / 365421181](https://www.kaggle.com/code/kirilltym/quantum-circuits-four-loaders-eight-toffolis?scriptVersionId=365421181) records our five earlier dirty-seven-wire 3-to-2 windows inspired by **Ehan Mallick**, [V3 / 364178963](https://www.kaggle.com/code/ehanmallick/invsqrt-20-65-two-3-to-2-and-merges-on-y6225?scriptVersionId=364178963); the other two earlier windows are Syed's. New public quadratic/decode/compiler/HMR/cache/refit gains are credited above. Our new contribution is the complete26-wire ANF window audit, transferred zero facts, MPS/full-native checks and exact integration.
* **James Barlow / manwithacat:** [V102 / 365446709](https://www.kaggle.com/code/manwithacat/the-real-150k-was-the-friends-we-made?scriptVersionId=365446709) independently published the earlier 293-loader/Isabe refit composition. His HW15 constrained refit was selected in our V5; that different refit is no longer selected here. **Alex Chilton** supplied prior exact public portfolio transport and published receipts. **David Pilný** reported the decoder baseline counterexample described above.
* **Earlier inverse lineage:** mrmeows / team selenium, Akmal Xodarev / busyaprime, Yoyo, Ahmed Berat Özer, Ehan Mallick, Phuc Thai / DePie, Dmitrii Gluzdov and marsyas; [Alex Chilton's exact public chain / 365314766](https://www.kaggle.com/code/alexchilton/24-43-lb-verified-three-task-portfolio?scriptVersionId=365314766) preserves their credited assembly. Our earlier [V2 / 365314315](https://www.kaggle.com/code/kirilltym/quantum-circuits-four-loaders-eight-toffolis?scriptVersionId=365314315) records our distinct-third-target identity. These historical links explain provenance rather than a new contribution claim.
* **Chemistry lineage:** [Lera / marculera / 365256248](https://www.kaggle.com/code/marculera/df-thc-10x-compact-groups-from-the-hamiltonian?scriptVersionId=365256248), Ahmed Berat Özer's progressive rounding, Syed's lattice-aware word table/compiler, SomeJoint's schedules, and the separately credited weight refits. [Syed portfolio / 365270654](https://www.kaggle.com/code/syed3000/vqcc-24-43-portfolio?scriptVersionId=365270654), Apache-2.0, records the inherited table/891Q decoder/deferred fan-in lineage.
* **DQI and broader upstream lineage:** jday96314 / QuantumAI, SomeJoint, Ali Haydar Özdağ / ahoirg, Alex Chilton, mrmeows, Dmitrii Gluzdov, ViberTeam / Artem1410 / anazemcev, manwithacat, Phuc Thai, Kozykorpesh / kozykappa, Michael Rustad, busyaprime, marsyas, Sumit Chongder, Rudra Bhaskar, Zongao Bian, Mizero Lucky Gall, Gu et al. and Guang Hao Low, as credited upstream. Isabe's upstream notice states that the historical DQI design repository has no established licence: only its already-public compiled circuit is used here; no blanket Apache relicensing or reuse of that source generator is asserted.
* **Google Quantum AI / Qualtran:** original Kickmix SDK and competition verifiers. Our data-only format study pinned [Qualtran commit9a0c11a4](https://github.com/quantumlib/Qualtran/tree/9a0c11a4ee7697c082fbf8f2e1e8bf4a71fcb453), retaining Apache-2.0 source notices. Original SDK exports bind the actual binaries to the precise local audit scopes and full receipts.

Public binary/data outputs are used with explicit provenance and their upstream scopes. Contestant Python/Rust optimizers and launch scripts were neither imported nor executed. The deleted discussion754677 is not cited as a host ruling or a licence grant.

> *(Zelle 30 `CREDITS_TEXT` ist der selbe Credit-Text als Python-String, der nach `CREDITS.md`/`LICENSE_SCOPES.txt` geschrieben wird.)*

## 8. Result

The exact retained quadratic inverse is combined with checked compact-group chemistry and Yoyo's second cache edit. Both changed components have our new MPS audits and complete original PASS receipts. The DQI value error, its priced penalty, negative controls, incomplete global equality and lower historical official scores remain explicit. The saved output contains exactly the18 asserted members; only subsequent Kaggle grading supplies a new score.

---

## 🔑 Kern-Technik in 3 Sätzen

Ein **phasenfreies X/CX/CCX-Fenster** lässt sich durch seine **quadratischen Booleschen Polynome** (max_degree 2) charakterisieren: gleiche Output-Polynome auf allen 26 Boundary-Wires beweisen dieselbe lineare Quantenoperation — so wird Qius 82→95-Zeilen-Merge (CCX 4→2) exakt verifiziert, ohne den Generator auszuführen. **Free-Coin-HMRs** nutzen, dass q21 vor `b417`/`b418` nachweisbar `|0⟩` ist (konservatives affines Abstraktionszertifikat): das Messen kostet keine input-abhängige Phase, ein folgendes `BIT_STORE0` fixiert den Cleanup-Branch. Zusammengenommen senkt das die Inverse-Cost von `98,309.06` (V5) auf `97,921.54` (V9) bei konstant 62 Qubits.

## 📝 Lern-Notizen (füll das selbst aus)

- [ ] Technik verstanden: Quadratic-Window (ANF max_degree 2) + Free-Coin-Zertifikat + 26-Wire-Grenzwertbeweis
- [ ] Cost-Delta nachvollziehbar: Inverse 98,309 → 97,921 (V5→V9); CCX 4→2; t_count 14.5→11.5
- [ ] Könnte ich das selbst bauen?: nein/weil… (Beweis-Methodik klar, aber exakte Source-Hashes + MPS-Infra nötig)
- [ ] Verbindung zu anderen Notebooks: 04 (Carry-Erasure) und 05 (Quadratic) sind komplementäre Uncompute-Sparungen; 06 baut auf derselben 62Q-Linie auf
- [ ] Frage die ich noch habe: Warum ist „global cache equality“ INCOMPLETE, obwohl 320 MPS-Fälle PASS sind?
