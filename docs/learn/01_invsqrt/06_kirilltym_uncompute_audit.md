# Quantum Circuits | Conditional Uncompute Audit

> **Lernziel:** Das **Conditional-Uncompute / Readout-Rewrite**-Prinzip verstehen: wie 48 *controlled swaps* vor dem Readout durch ein **messbasiertes** X-Basis-Schema ersetzt werden (invertierbare Outcome-Map + eine `CZ`-Phasenkorrektur pro Pair) — und wie die unveränderte 62Q-Inverse (`034c7c2a`, Cost `95,345.55`) als Referenz-Receipt in so einem Audit verankert wird.
> **Dauer:** ~12 Minuten lesen
> **Quelle:** kirilltym | Votes: – (im lokalen Kernel-Dump nicht enthalten)
> **Technik:** Uncompute vs Reset (Conditional Uncompute / measurement-based readout)
> **Level:** Fortgeschritten

---

# Quantum Circuits | Conditional Uncompute Audit

This release combines the inverse and chemistry from Maoxin V1 with the exact DQI circuit in Özer V70. The two published versions scored **25.14981** and **25.14871** respectively. The previous release of this notebook scored **25.08000** despite a full independent DQI run with zero observed errors. This version preserves that result in the comparison records and checks the new DQI bytes separately.

The packager reproduces Özer's DQI from Maoxin's exact public archive and keeps all 17 other members. Kaggle scores the combination separately.

## Replace 48 controlled swaps before readout

For a controlled swap on basis bits `a,b` with control `c`, let `r,s` be the following X-basis measurement outcomes. Set `d = a XOR b` with one CX. Measure `b` with `u = r XOR s`, apply `CZ(c,d)` when `u=1`, then measure `d` with `v=r`. The output bits are `(r,s)=(v,u XOR v)`.

Both forms contribute the phase exponent `r*d XOR (r XOR s)*b XOR (r XOR s)*c*d`. The outcome map is invertible. Each of the four verified windows contains 12 disjoint pairs and preserves the common control. Applying these windows to the Maoxin DQI produces the exact SHA-256 of Özer V70 and removes 48 Toffoli-like gates.

The paired MPS run checked the full ordered streams on 2,048 trajectories, including all quantum values, classical values and phase. Disabling the first new phase correction produced one phase mismatch. The separate full original verifier used its preregistered inputs and full repetition factor.

> **🔑 Technik (Uncompute→Readout):** Statt einen CSWAP zu *computen* und später zu *uncomputen* (teuer, braucht Toffolis), wird er **gemessen**: `d=a⊕b` (1×CX), dann X-Basis-Messungen liefern `u=r⊕s`, `v=r`, und genau eine `CZ(c,d) if u` korrigiert die Phase. Die Outcome-Map `(r,s)↦(v,u⊕v)` ist invertierbar → keine Information geht verloren. 4 Fenster × 12 Paare = **48 Toffoli-artige Gates entfernt**.

## Independent full verification

| Component | Trials | Value / phase | Cost |
| --- | ---: | ---: | ---: |
| DQI, Maoxin baseline | 102,400 | 0 / 0 | 374,735,803,217.46 |
| DQI, Özer readout | 102,400 | 0 / 0 | 374,690,183,327.03 |
| **Inverse, exact receipt** | **200,540,928** | See report | **95,345.55** |
| Chemistry, exact receipt | 78,080 | See report | 299,654,755.44 |

> **🔥 Key Learning Point (InvSqrt):** Die Inverse ist hier der **unveränderte** Receipt `034c7c2a`: 62 Qubits, Cost **95,345.55**, 200,540,928 Shots. Sie dient als stabile Referenz, während das eigentliche Release den DQI-Readout austauscht.

The DQI runs use separate fixed samples. Each cost includes its full repetition factor. The inverse, chemistry and loader bytes match the previous independently checked release.

```python
# Plot: links die statischen DQI-Toffoli-Gates (Maoxin 395,641 -> Özer 395,593,
# d.h. -48), rechts den vollen Repetition-Faktor beider (identisch 1.191260465).
from pathlib import Path
import matplotlib.pyplot as plt

fig, (gates, costs) = plt.subplots(1, 2, figsize=(10, 3.8), layout="constrained")
labels = ["Maoxin baseline", "Özer readout"]
colors = ["#64748b", "#13766e"]
gates.scatter([395641, 395593], [0, 1], c=colors, s=85)
gates.set_yticks([0, 1], labels)
gates.set_xticks([395593, 395641], ["395,593", "395,641"])
gates.set_xlim(395575, 395659)
gates.set_ylim(-0.45, 1.45)
gates.set_title("Static DQI Toffoli-like gates")
gates.grid(axis="x", alpha=0.25)

factors = [1.1912604648115832, 1.1912604648115832]
error_labels = ['0 / 0', '0 / 0']
costs.barh(labels, factors, color=colors, height=0.5)
for i, (factor, error_label) in enumerate(zip(factors, error_labels, strict=True)):
    costs.text(0.035, i, f"{factor:.6f}   {error_label}", va="center", color="white")
costs.set_xlim(0, max(factors)*1.12)
costs.set_title("Full repetition factor")
costs.set_xlabel("Value / phase errors shown on bars")
fig.savefig(Path("/kaggle/working/verification_overview.png"), dpi=120)
plt.show()
```

## Sources and attribution

- [Maoxin V1](https://www.kaggle.com/code/maoxin123/lb-25-1498-combined-invsqrt-refit-chem?scriptVersionId=367139607) provides the inverse, refitted chemistry weights and baseline DQI bytes. Its inverse credits Hosen42 and its chemistry credits James Barlow, Isabe and Syed Asad Ali.
- [Özer V70](https://www.kaggle.com/code/ozertuu/25-137-starter-notebook?scriptVersionId=367110918) provides the exact four-window readout rewrite. Our contribution is deterministic reconstruction from Maoxin's public archive, the paired measurement proof and checks, and the independent full verification.
- [Our V4](https://www.kaggle.com/code/kirilltym/quantum-circuits-conditional-uncompute-audit?scriptVersionId=367159320) preserves the comparison with the earlier decoder composition. [Our Q19 V23](https://www.kaggle.com/code/kirilltym/quantum-circuits-pi-gauge-weight-refinement?scriptVersionId=366775847) holds our earlier exact baseline DQI receipt.
- Google Quantum AI and Qualtran supply the competition specifications, SDK and verifiers. This notebook's own readable packager uses Apache-2.0. Inherited circuit and data licences retain their original scopes and notices. The notebook reuses already-public compiled outputs as hash-checked data within this competition.

```python
# Pins + Transport-Plan: PINS/ORIGINAL_PINS (SHA-256 aller 18 Mitglieder + 14
# Verifier-Quellen), SOURCES (Maoxin-Archiv), TRANSPORT_PLAN (die exakten Byte-
# Patches, die Maoxin-DQI 4432ec5f -> Özer-DQI 4e9b50b1 umschreiben: Header +
# 11 Pakete mit hex before/after-Hunks), FACTOR_SCHEMA (Chemie-NPZ-Layout).
PINS = {'dfthcsos/angle_k_0.kmb': 'd3aab747…',  # … (15 angle_k_*.kmb)
 'dfthcsos/submission.npz': 'd994cd720a6f4718560e5dfe16a52c3fe0a2a7126122e410d70f7b876d300b4b',
 'dqi.kmb': '4e9b50b1ee34b3eaf2b7f394873c2dd3dad4cddbdd1f12a348b4323b5eb41771',
 'invsqrt.kmb': '034c7c2a54d51e13aff6e62ec4c14997d3968b6c11122146c57290b1a1b8c7e2'}

ORIGINAL_PINS = { … 14 SHA-256 der offiziellen Verifier-Quellen (invsqrt/dqi/dfthcsos) … }

SOURCES = {'maoxin': {'pins': { … all18 Maoxin-Mitglieder … },
             'sha256': '55eec7537872f663400ab2a96ceb651ac44529445c27f6e537eea5a57c138c23',
             'version': 367139607}}

TRANSPORT_PLAN = {'baseline_header': 'd750c7d5…', 'baseline_sha256': '4432ec5f…',
 'candidate_header': 'd750c7d5…', 'candidate_sha256': '4e9b50b1…',
 'packets': {'1': {'new_length': 58287124, 'old_length': 58287028,
                   'patches': [{'offset': 16083438, 'before': '3232…5050', 'after': '2150a050c2…'},
                               # … 3 weitere Patches in Packet 1 …]},
             # … Pakete 2..11 (hex before/after-Hunks an exakten Offsets) …}}

FACTOR_SCHEMA = {'H1_I': {'descr': '<f4', 'shape': []},
 'H2_I': {'descr': '<f8', 'shape': [8, 44]},
 'Hsym_lower': {'descr': '<f4', 'shape': [2926]},
 'U': {'descr': '<f8', 'shape': [8, 143, 76]},
 'W': {'descr': '<f8', 'shape': [8, 143, 44]},
 'angle_words': {'descr': '<i8', 'shape': [1220, 75]},
 'tree_edges': {'descr': '<i8', 'shape': [75, 2]}}
```

```python
# Patch-Logik: wendet den gepinnten TRANSPORT_PLAN deterministisch auf ein KMB an.
# Liest das DQI-Layout (Magic + 11 Pakete), kopiert unveränderte Bytes, ersetzt
# exakt die before/after-Hex-Hunks und verifiziert das Ergebnis per SHA-256.
"""Apply a finite, pinned packet patch to a public KMB circuit as data."""
import hashlib
import struct


def dqi_file_digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_dqi_layout(stream):
    header = stream.read(104)
    assert header[:16].hex() == "d750c7d5c329d326e3cc9f6834f2b8bf"
    version, qubits, bits, registers = struct.unpack_from("<4I", header, 16)
    assert version == 2 and qubits == 892
    for _ in range(registers):
        tag, length = struct.unpack("<QQ", stream.read(16))
        assert tag == 0
        stream.seek(length, 1)
    register_end = stream.tell()
    packets = {}
    for expected_tag in range(1, 12):
        tag, length = struct.unpack("<QQ", stream.read(16))
        assert tag == expected_tag
        packets[tag] = (stream.tell(), length)
        stream.seek(length, 1)
    assert stream.tell() == stream.seek(0, 2)
    return header, register_end, packets


def copy_dqi_bytes(source, destination, count):
    assert count >= 0
    while count:
        block = source.read(min(count, 1 << 20))
        assert block
        destination.write(block)
        count -= len(block)


def apply_dqi_patch(baseline, destination, plan):
    assert dqi_file_digest(baseline) == plan["baseline_sha256"]
    with baseline.open("rb") as source, destination.open("xb") as result:
        header, register_end, packets = read_dqi_layout(source)
        assert header.hex() == plan["baseline_header"]
        result.write(bytes.fromhex(plan["candidate_header"]))
        source.seek(104)
        copy_dqi_bytes(source, result, register_end - 104)
        for tag, (start, length) in packets.items():
            entry = plan["packets"][str(tag)]
            assert length == entry["old_length"]
            result.write(struct.pack("<QQ", tag, entry["new_length"]))
            source.seek(start)
            cursor = 0
            output_bytes = 0
            for patch in entry["patches"]:
                offset = patch["offset"]
                copy_dqi_bytes(source, result, offset - cursor)
                before = bytes.fromhex(patch["before"])
                after = bytes.fromhex(patch["after"])
                assert source.read(len(before)) == before
                result.write(after)
                output_bytes += offset - cursor + len(after)
                cursor = offset + len(before)
            copy_dqi_bytes(source, result, length - cursor)
            assert output_bytes + length - cursor == entry["new_length"]
    assert dqi_file_digest(destination) == plan["candidate_sha256"]
```

```python
# Build-Logik: montiert aus dem Maoxin-Archiv die exakte 18-Mitglieder-Submission,
# wendet den DQI-Patch an, prüft Chemie-NPZ-Schema (finite Floats) und alle Hashes.
"""Assemble the exact verified circuit and chemistry archive on Kaggle."""
import os
from pathlib import Path
import shutil
import tempfile
import zipfile
import numpy as np

INPUT = Path("/kaggle/input")
WORK = Path("/kaggle/working")


def member_hashes(archive):
    names = archive.namelist()
    assert len(names) == len(set(names)) == 18
    result = {}
    for name in names:
        with archive.open(name) as stream:
            result[name] = hashlib.file_digest(stream, "sha256").hexdigest()
    return result


def mounted_sources():
    paths = {}
    for path in INPUT.rglob("submission.zip"):
        checksum = dqi_file_digest(path)
        for name, source in SOURCES.items():
            if checksum == source["sha256"]:
                assert name not in paths
                paths[name] = path
    assert set(paths) == set(SOURCES)
    return paths


def check_original_source_hashes():
    roots = [p.parents[2] for p in INPUT.rglob("verify_submission_dqi.py")
             if all((p.parents[2] / n).is_file() for n in ORIGINAL_PINS)]
    assert len(roots) == 1
    assert {name: dqi_file_digest(roots[0] / name) for name in ORIGINAL_PINS} == ORIGINAL_PINS


def copy_member(archive, name, path):
    with archive.open(name) as source, path.open("xb") as dest:
        shutil.copyfileobj(source, dest)


def build_submission():
    check_original_source_hashes()
    mounted = mounted_sources()
    destination = WORK / "submission.zip"
    assert not destination.exists()
    with tempfile.TemporaryDirectory(dir=WORK) as directory:
        scratch = Path(directory)
        transport_dqi = scratch / "transport.kmb"
        dqi = scratch / "dqi.kmb"
        with zipfile.ZipFile(mounted["maoxin"]) as archive:
            assert member_hashes(archive) == SOURCES["maoxin"]["pins"]
            copy_member(archive, "dqi.kmb", transport_dqi)
            apply_dqi_patch(transport_dqi, dqi, TRANSPORT_PLAN)
            members = {"dqi.kmb": dqi}
            for name in sorted(PINS.keys() - members.keys()):
                path = scratch / name.replace("/", "__")
                copy_member(archive, name, path)
                assert dqi_file_digest(path) == PINS[name], name
                members[name] = path
        with np.load(members["dfthcsos/submission.npz"], allow_pickle=False) as factor:
            assert set(factor.files) == set(FACTOR_SCHEMA)
            for name, spec in FACTOR_SCHEMA.items():
                array = factor[name]
                assert array.dtype.str == spec["descr"] and list(array.shape) == spec["shape"], name
                if array.dtype.kind == "f":
                    assert np.isfinite(array).all(), name
        pending = scratch / "submission.zip"
        with zipfile.ZipFile(pending, "x") as archive:
            for name, path in sorted(members.items()):
                entry = zipfile.ZipInfo(name)
                entry.compress_type = zipfile.ZIP_DEFLATED
                with path.open("rb") as source, archive.open(entry, "w") as out:
                    shutil.copyfileobj(source, out)
        with zipfile.ZipFile(pending) as archive:
            assert member_hashes(archive) == PINS
        os.link(pending, destination)
    return destination
```

```python
# Führt den Build aus und druckt Name, Größe und SHA-256 der fertigen submission.zip.
output = build_submission()
print(output.name, output.stat().st_size, dqi_file_digest(output))
print("ALL18_SHA256", PINS)
```

## Preserved verification records and notices

> **`VERIFICATION`-Receipts (Zelle 8, vollständig in Quelle).** Cost-relevante Felder:
>
> | Record | Qubits | Cost (score) | Shots | Value/Phase | Repetition |
> |---|---:|---:|---:|---:|---:|
> | **unchanged_inverse** (`034c7c2a`) | **62** | **95,345.55433569** | 200,540,928 | – | – |
> | prior_full_DQI_control (`4432ec5f`) | 892 | 374,735,803,217.46 | 102,400 | 0 / 0 | 1.191260465 |
> | V4_DQI (`e1354c89`) | 892 | 374,688,243,257.04 | 102,400 | 0 / 0 | 1.191260465 |
> | new_DQI (`4e9b50b1`, Özer readout) | 892 | 374,690,183,327.03 | 102,400 | 0 / 0 | 1.191260465 |
> | unchanged_chemistry (`d994cd72`) | 427 | 299,654,755.44 | 78,080 | – | – |
>
> Inverse-Details: `toffoli_count 1242.74`, `max_toffoli_count 1405`, `num_ops 36,477`, `reaction_depth 740`, `rotation_count 41`, `worst_error_over_tolerance 0.99932`, `worst_x 161`. `V4_official_score 25.08`, `best_Q18_before_release 25.14775`.
>
> `new_DQI_MPS`: device mps, PASS, **2048 lanes**, 4 windows, **48 swapped_pairs**, `fixed_negative_phase_mismatches 1` (bewusst deaktivierte erste Phasenkorrektur). `new_DQI_attempt`: salt `nov9-target18-maoxin-ozer-readout-independent`, 1 attempt, COMPLETE_PHYSICAL_AUDIT.

```python
# Schreibt die kompletten VERIFICATION-Receipts nach verification_summary.json.
import json
VERIFICATION = { … (siehe obige Tabelle; vollständige Dicts inkl. shot_operation_counts,
               MPS-Records, Attempt-/Audit-Archive, Salt-Hashes) … }
Path("/kaggle/working/verification_summary.json").write_text(json.dumps(VERIFICATION, indent=2) + "\n")
```

> *(Zelle 9 `NOTICE_TEXT` enthält die vollständigen Apache-2.0-Lizenztexte + Provenance-/Credit-Dateien: APACHE-2.0.txt, CARRY_DOMAIN_COMPOSITION_CREDITS.md, CARRY_PORT_CREDITS.md, ISABE_V19_CREDITS.md, ISABE_V19_LICENSE.md, MAOXIN_V3_CREDITS.md, OZER_V23_CREDITS.md, Q18_CONDITIONAL_UNCOMPUTE_CREDITS.md, Q18_HELIOS26_DQI_CREDITS.md, Q18_V4_CREDITS.md, Q18_V5_CREDITS.md, SAMANYU2_CREDITS.md, SAMANYU2_LICENSE.txt, YOYO_V36_CREDITS.md, YOYO_V36_LICENSE_SCOPE.md. Für das Lernen sind die obigen „Sources and attribution“-Abschnitte die verdichtete Form; der Volltext ist in der Quelle.)*

## Conclusion

The exact Özer decoder saves 48 Toffoli-like gates relative to the Maoxin baseline. The combined archive preserves the independently verified inverse, chemistry and angle loaders. The reports record the full repetition factors and keep the previous official V4 result.

---

## 🔑 Kern-Technik in 3 Sätzen

Ein **controlled swap** vor dem Readout wird nicht computed+uncomputed, sondern **gemessen**: `d=a⊕b` (1×CX), X-Basis-Messungen ergeben `u=r⊕s`, `v=r`, und eine einzige `CZ(c,d) if u=1` liefert die korrekte Phase — die Outcome-Map ist invertierbar, also geht keine Information verloren. Vier Fenster à 12 Paare entfernen so **48 Toffoli-artige Gates** (395,641 → 395,593) und reproduzieren exakt den SHA-256 von Özer V70. Die unveränderte 62Q-Inverse (`034c7c2a`, Cost **95,345.55**, 200,540,928 Shots) bleibt als Referenz-Receipt erhalten — ein Audit trennt strikt „geprüft“ von „neu gemessen“.

## 📝 Lern-Notizen (füll das selbst aus)

- [ ] Technik verstanden: messbasierter Readout ersetzt CSWAP-Uncompute (invertierbare Outcome-Map + 1 CZ/Paar)
- [ ] Cost-Delta nachvollziehbar: DQI 395,641 → 395,593 Gates (-48); Inverse unverändert 95,345.55
- [ ] Könnte ich das selbst bauen?: teilweise/weil… (Readout-Mathematik klar; exakte Byte-Patches brauchen aber die gepinnten Source-Archive)
- [ ] Verbindung zu anderen Notebooks: „Uncompute vs Reset“-Thema verbindet 04 (Carry-Erasure), 05 (Free-Coin) und 06 (Readout)
- [ ] Frage die ich noch habe: Warum ist die Outcome-Map `(r,s)↦(v,u⊕v)` invertierbar — welche Eigenschaft von X-Basis-Messungen nutzt das?
