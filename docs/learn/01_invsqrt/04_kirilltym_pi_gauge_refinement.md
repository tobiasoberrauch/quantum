# Quantum Circuits | Pi-Gauge & Weight Refinement — Carry Erasure

> **Lernziel:** Die **Carry-Erasure**-Technik auf Gate-Ebene verstehen: wie ein *Compute → Measure(HMR) → conditional Phase(CZ)*-Uncompute-Muster durch eine gemeinsame Carry-Wire mit **batchtem** Measure+Phase ersetzt wird (Mean Toffolis `1253.6 → 1245.1`), plus die KMB-Binary-Codec-Funktionen zum Lesen/Schreiben von Circuit-Bytes.
> **Dauer:** ~15 Minuten lesen
> **Quelle:** kirilltym | Votes: – (im lokalen Kernel-Dump nicht enthalten)
> **Technik:** Carry chains / Uncompute→Reset (Carry Erasure) + KMB-Codec
> **Level:** Fortgeschritten

---

# Quantum Circuits | Pi-Gauge & Weight Refinement
## Carry erasure, a redundant swap and three DQI cache routes

This composition combines the carry port independently checked in [our V22](https://www.kaggle.com/code/kirilltym/quantum-circuits-pi-gauge-weight-refinement?scriptVersionId=366737647), [Atakan V2's domain-aware swap deletion](https://www.kaggle.com/code/atakanaldemir/qcc-early-measurement-and-domain-aware-inverse?scriptVersionId=366721329), and the DQI cache routes and fixed-word factor refinement shipped by [Isabe V12](https://www.kaggle.com/code/isabe11am00re/qcc-v66s33w-submission?scriptVersionId=366712739). The 15 angle loaders remain unchanged from our completed checks.

[Özer V15](https://www.kaggle.com/code/ozertuu/25-136-starter-notebook?scriptVersionId=366740074) already published this combination. All 18 selected member hashes match its physically downloaded archive. Our contribution here is the readable reconstruction and independent checks of the combined inverse, the two complete DQI streams and the new factor. We do not claim an additional circuit improvement over that published combination.

Our independently measured local estimate is **25.13665179**, including the actual verifier errors and repetition penalty. The latest checked official public-notebook leader is Özer V15 at **25.13665**; our V22 has **25.13115**. A new official result requires Kaggle evaluation. These are public-notebook comparisons, separate from the overall team leaderboard.

## Why these changes can be composed

The new inverse removes `CSWAP q23 q6 q28` at zero-based source index 25929 from our checked carry port. Every preceding instruction is identical to the checked newer inverse. The first carry patch begins later, at source index 28146. At the swap checkpoint our independent audit found `q23 & (q6 ^ q28) = 0` for every legal input on three fixed measurement histories. Thus the swap acts trivially on those reached states. Flipping q6 at that fixed checkpoint deliberately violates the contract and activates the swap on 16,320 inputs. Atakan's broader domain compiler is credited separately; our finite histories are not a proof over every measurement branch.

The DQI update has three cache routes in six exact ordered-stream hunks. It retains a product in a spare wire, uses Clifford transfers, and later clears the cache by X measurement and a conditional phase correction. Such a rewrite needs the claimed product, clean-wire and lifetime relations at the reached program points. We compared the two complete streams on fixed decoder trajectories and separately ran the unchanged original verifier. These finite checks do not establish universal product or lifetime invariants.

The prior 14 measurement-order identities remain in the DQI lineage. Their equality of basis-state phase exponents, `a*m_a + (t+a*b)*m_t = t*m_t + a*b*m_t + a*m_a`, retains its stated distinct-wire and measurement-coupling conditions. New classical cache bits are internal; shared outcomes are coupled by unchanged operation identity in our comparison.

## Independent verification

| Component | Original trials | Qubits | Measured cost |
|---|---:|---:|---:|
| **Carry and domain inverse** | **200,540,928** | **62** | **95,492.95** |
| Three-route DQI | 102,400 | 892 | 374,735,803,217.46 |
| Fixed-word chemistry refinement | 78,080 | 427 | 299,662,437.60 |

> **🔥 Key Learning Point (InvSqrt):** Der Inverse-Circuit kostet nach Carry-Erasure + Domain-Swap-Deletion **95,492.95** bei 62 Qubits / 200,540,928 Shots. Die MPS-Kampagne deckte alle **3,133,452** legalen Inputs auf drei fixen Historien ab — kein Out-of-Tolerance-Phase und kein dirty Reset. Der gelöschte Swap war durchgehend inaktiv; das fixe Aktivierungs-Negative änderte 16,320 Inputs.

The inverse MPS campaign covered all 3,133,452 legal inputs on three fixed histories, with no out-of-tolerance phase or dirty reset. The deleted swap was inactive throughout; the fixed activation negative changed 16,320 inputs. The new DQI campaign streamed both complete circuits on 2,048 fixed decoder trajectories: quantum values, common classical results and phase agreed. Omitting the preregistered first new cache-correction CZ caused **277 phase mismatches**. New internal classical bits are not treated as outputs. The new factor has exactly nine keys; its five common arrays are unchanged, W and H2_I have 6,292 and 44 changed elements, every float representation is finite, and a first-weight LSB negative detected one identity mismatch.

Each changed component then received one complete unchanged ORIGINAL call, with exact hashes and salts fixed beforehand and an exclusive local marker before the call. All 18 source-member guards, all 14 original-source pins and all 15 loader canonical exports remain enforced. Physical audit archives preserve the actual reports and source identities. The initial inverse runner's import-shadowing failure occurred before its tensor campaign; its original runner, preregistration and failure remain preserved. No numerical result was retried for PASS.

The DQI original report contains **0 value / 0 phase errors**, with full repetition factor **1.191260465**. All observed errors and penalties remain priced. The inherited approximate decoder and its known rare failure families are retained. External Atakan reports for our previous 337cb DQI include two value failures on a stress draw and deliberately selected replay counterexamples; these are external reports, not our new measurements or population-rate estimates. No universal correctness or final-leaderboard guarantee follows from a finite clean draw. Official grading component counts are not read or inferred here. Packaging invokes no numerical MPS or original verifier.

```python
# KMB-Binary-Codec: liest ein .kmb (Kickmix Binary) deterministisch in Gate-Text
# um und kann es wieder encodieren. Wichtig für das Verständnis des Circuit-Formats:
# - MAGIC-Header, Version=2, nq<=128, nb<=200000, nr<=100
# - Packete 0..11 (Registers, Ops, Target-Arrays, Angles)
# - Opcode-Bitfeld: base = opcode & 0x7F (Gate-Typ), arity = (opcode & 0x30)>>4,
#   Bit 0x40 = Bit-Ziel, Bit 0x80 = "if"-Bedingung
import hashlib
import json
import mmap
import os
from pathlib import Path
import shutil
import struct
import tempfile
import zipfile

import numpy as np

INPUT = Path("/kaggle/input")
WORK = Path("/kaggle/working")
MAGIC = bytes.fromhex("d750c7d5c329d326e3cc9f6834f2b8bf")
SPEC = {'baseline': '77bace9de69cc6023fb58eda1c58dc70cb0966e5d420c09c2afb12e2fb536b92',
 'candidate': '4432ec5fd63d7d70aab92d32f719d47539d0ff66ae0cb0b964c914e01fece431',
 'chemistry_factor': '5bd3575736fdf340231b18dcbbe35f1ff9e0e8606f6081258aa54f4d0f9e59eb',
 'inverse': '13b5bf7a18bce52a19c17e929869b852c0a1bb58d1d49bd7781570cc9ca762c9',
 'num_bits': 200003,
 'num_ops': 58287028,
 'original_source_aggregate': '7180d2a65d5802e441f5ba1911052c13666dd5245394f0f313d39da38a937bfe',
 'static_toffoli_like': 395641}
ORIGINAL_PATHS = ['verifiers/dfthcsos/__init__.py', 'verifiers/dfthcsos/example_submission/angle_k_reference_circuit.py', 'verifiers/dfthcsos/scoreinfra/__init__.py', 'verifiers/dfthcsos/scoreinfra/circuits.py', 'verifiers/dfthcsos/scoreinfra/costs_prepare.py', 'verifiers/dfthcsos/scoreinfra/dfthc_math.py', 'verifiers/dfthcsos/scoreinfra/reference.py', 'verifiers/dfthcsos/verify.py', 'verifiers/dqi/__init__.py', 'verifiers/dqi/dqi_reference_circuit.py', 'verifiers/dqi/verify_submission_dqi.py', 'verifiers/invsqrt/__init__.py', 'verifiers/invsqrt/nr_reference_circuit.py', 'verifiers/invsqrt/verify_submission_invsqrt.py']

def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def aggregate(entries):
    encoded = "".join(name + "\0" + value + "\n" for name, value in sorted(entries.items()))
    return hashlib.sha256(encoded.encode()).hexdigest()


def member_hashes(archive):
    names = archive.namelist()
    assert len(names) == len(set(names)) == 18
    result = {}
    for name in names:
        with archive.open(name) as stream:
            result[name] = hashlib.file_digest(stream, "sha256").hexdigest()
    return result

SOURCE_PINS = { … 18 SHA-256-Pins für angle_k_*.kmb, submission.npz, dqi.kmb, invsqrt.kmb … }
SOURCE_ARCHIVE_SHA256 = '801dc4d159e102dc7a16f1501be0b7901558d28da224861ff891eb4b642e430a'

from collections import Counter
SOURCE_COMMIT = "9a0c11a4ee7697c082fbf8f2e1e8bf4a71fcb453"
BASE_NAMES = {0: 'NEG', 1: 'POP_CONDITION', 16: 'Z', 17: 'X', 18: 'R', 19: 'Z_POW',
  32: 'CZ', 33: 'CX', 34: 'SWAP', 48: 'CCZ', 49: 'CCX', 50: 'CSWAP',
  64: 'BIT_STORE0', 65: 'BIT_STORE1', 66: 'BIT_INVERT', 80: 'HMR'}

def escape_name(name):
    escapes = {"\n": "n", "\r": "r", "#": "P", '"': "Q", "\\": "B"}
    return "".join("\\" + escapes[c] if c in escapes else c for c in name)

def half_turns_decimal(low, high):
    """Exact integer transcription of FixedPrecisionAngle128's text codec."""
    value = low | (high << 64)
    denominator = 1 << 128
    integer = value >> 127
    remainder = (value << 1) & (denominator - 1)
    digits = []
    while remainder:
        digit, remainder = divmod(remainder * 10, denominator)
        digits.append(str(digit))
    return str(integer) + "." + ("".join(digits) or "0")

def read_inverse(path):
    raw = Path(path).read_bytes()
    position = 0

    def take(size):
        nonlocal position
        assert size >= 0 and position + size <= len(raw), "Truncated payload"
        result = raw[position:position + size]
        position += size
        return result

    def unpack(fmt):
        return struct.unpack(fmt, take(struct.calcsize(fmt)))

    def packet(kind, size=None):
        actual, count = unpack("<QQ")
        assert actual == kind, ("Packet order", actual, kind)
        assert size is None or count == size, ("Packet size", kind, count, size)
        return take(count)

    assert take(16) == MAGIC, "Unsupported magic"
    version, nq, nb, nr = unpack("<IIII")
    assert version == 2 and nq <= 128 and nb <= 200000 and nr <= 100
    no, n3, n2, n1, nbit, ncond, nangle, ntag, nchar = unpack("<9Q")
    assert no <= 200000 and not (ntag or nchar), "Outside inverse scope"
    assert all(n <= no for n in (n3, n2, n1, nbit, ncond, nangle))
    registers, lines = [], []
    for index in range(nr):
        payload = packet(0)
        assert len(payload) >= 8
        name_size, count = struct.unpack_from("<II", payload)
        assert len(payload) == 8 + name_size + 4 * count
        name = payload[8:8 + name_size].decode("utf-8")
        targets = struct.unpack_from(f"<{count}I", payload, 8 + name_size)
        contents = []
        for target in targets:
            kind, wire = ("q", target & 0x7FFFFFFF) if target & 0x80000000 else ("b", target)
            assert wire < (nq if kind == "q" else nb), "Register target outside header"
            contents.append(kind + str(wire))
            lines.append(f"APPEND_TO_REGISTER {kind}{wire} r{index}")
        if name:
            lines.append(f'REGISTER r{index} "{escape_name(name)}"')
        elif not contents:
            lines.append(f"REGISTER r{index}")
        registers.append(dict(name=name, contents=contents))
    ops = packet(1, no)
    arrays = []
    for kind, count in enumerate((n3, n3, n3, n2, n2, n1, nbit, ncond), 2):
        arrays.append(struct.unpack(f"<{count}I", packet(kind, 4 * count)))
    angle_bytes = packet(10, 16 * nangle)
    angles = [half_turns_decimal(*pair) for pair in struct.iter_unpack("<QQ", angle_bytes)]
    assert packet(11, 8) == bytes(8)
    assert position == len(raw), "Trailing data"
    indices = [0] * 8
    angle_index = 0
    condition_depth = 0
    counts = Counter()

    def item(which, bound):
        at = indices[which]
        assert at < len(arrays[which]), "Payload underflow"
        value = arrays[which][at]
        indices[which] += 1
        assert value < bound, "Operation target outside header"
        return value

    for opcode in ops:
        if opcode == 0x81:
            name = "PUSH_CONDITION"
            condition_depth += 1
        else:
            base = opcode & 0x7F
            assert base in BASE_NAMES, ("Unsupported operation", opcode)
            assert not (base == 1 and opcode & 0x80)
            name = BASE_NAMES[base]
            if name == "POP_CONDITION":
                assert condition_depth > 0, "Condition stack underflow"
                condition_depth -= 1
        targets = []
        arity = (opcode & 0x30) >> 4
        if arity == 3:
            targets = [f"q{item(j, nq)}" for j in (0, 1, 2)]
        elif arity == 2:
            targets = [f"q{item(j, nq)}" for j in (3, 4)]
        elif arity == 1:
            targets = [f"q{item(5, nq)}"]
        assert len(set(targets)) == len(targets), "Qubit control collision"
        if opcode & 0x40:
            targets.append(f"b{item(6, nb)}")
        if name == "Z_POW":
            assert angle_index < len(angles), "Angle payload underflow"
            targets.append(angles[angle_index])
            angle_index += 1
        if opcode & 0x80:
            targets.extend(["if", f"b{item(7, nb)}"])
        lines.append(" ".join([name, *targets]))
        counts[name + ("_IF" if opcode & 0x80 else "")] += 1
    assert indices == list(map(len, arrays)), "Unused payload data"
    assert angle_index == len(angles), "Unused angle data"
    assert condition_depth == 0, "Unclosed condition stack"
    text = "\n".join(lines) + "\n"
    return text, dict(binary_sha256=hashlib.sha256(raw).hexdigest(),
                      text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                      num_qubits=nq, num_bits=nb, operations=no,
                      counts=dict(counts), registers=registers,
                      angle_payload_sha256=hashlib.sha256(angle_bytes).hexdigest(),
                      source_commit=SOURCE_COMMIT)

def encode_like(raw,lines,bits):
    # Re-encodiert geänderte Gate-Text-Zeilen zurück ins KMB-Format (nq==62,
    # alte Bits==70003, 48 Z_POW-Rotationen bleiben erhalten).
    version,nq,oldbits,nreg,*oldcounts=struct.unpack_from('<4I9Q',raw,16)
    assert version==2 and nq==62 and oldbits==70003
    at=104
    for _ in range(nreg):
        kind,n=struct.unpack_from('<2Q',raw,at);assert kind==0;at+=16+n
    register_end=at;packets=[]
    for kind in range(1,12):
        k,n=struct.unpack_from('<2Q',raw,at);assert k==kind;at+=16;packets.append(raw[at:at+n]);at+=n
    assert at==len(raw)
    arrays=[bytearray() for _ in range(9)];reverse={v:k for k,v in BASE_NAMES.items()};nr=0
    counts=[0]*9
    for line in lines:
        op,*args=line.split()
        if op in ('REGISTER','APPEND_TO_REGISTER'):continue
        cond=None
        if 'if' in args:
            assert args[-2]=='if';cond=int(args[-1][1:]);args=args[:-2]
        if op=='PUSH_CONDITION':opcode=0x81;assert cond is not None
        else:opcode=reverse[op]|(0x80 if cond is not None else 0)
        arrays[0].append(opcode);counts[0]+=1
        arity=(opcode&0x30)>>4
        target=[int(a[1:]) for a in args[:arity]];assert all(0<=q<nq for q in target)
        for j,q in enumerate(target):
            dest=j+1 if arity==3 else j+4 if arity==2 else 6
            arrays[dest]+=struct.pack('<I',q)
        if arity:counts[4-arity]+=1
        if opcode&0x40:
            assert args[-1].startswith('b');v=int(args[-1][1:]);assert v<bits
            arrays[7]+=struct.pack('<I',v);counts[4]+=1
        if cond is not None:
            assert cond<bits;arrays[8]+=struct.pack('<I',cond);counts[5]+=1
        nr+=op=='Z_POW'
    assert nr==oldcounts[6]==48
    counts[6:]=oldcounts[6:]
    result=bytearray(raw[:16])+struct.pack('<4I9Q',2,nq,bits,nreg,*counts)+raw[104:register_end]
    for j,payload in enumerate(arrays+[packets[9],packets[10]],1):result+=struct.pack('<2Q',j,len(payload))+payload
    return result
```

### Die Carry-Erasure-Patches (`CARRY_PATCHES`)

> **Das ist die Kern-Technik.** Es gibt **91 Patches**, die den Inverse-Circuit an exakten Source-Indizes umschreiben. Das wiederkehrende Muster:
>
> **Vorher (Uncompute per Measure):**
> ```
> CX  q28 q40          # Compute: Ergebnis in q40
> HMR q40 b341         # Messung + Reset von q40 → Bit b341
> CZ  q44 q14 if b341  # Conditional Phase, gesteuert vom Messergebnis
> ```
> **Nachher (Carry-Erasure, batcht über gemeinsame Carry-Wires q57/q61):**
> ```
> CX  q40 q61          # Ergebnis auf Carry-Wire q61 schieben (Swap via 2×CX)
> CX  q61 q40
> … (später, gebündelt:)
> HMR q61 b0           # EINE Messung der Carry
> CZ  q44 q14 if b0    # ALLE Conditional Phases auf denselben Carry-Outcome b0
> CZ  q57 q14 if b0
> …
> ```
>
> Statt pro Bit ein eigenes `HMR`+`CZ-if` zu fahren, wird das Ergebnis auf eine dedizierte Carry-Wire verschoben und dort **einmal** gemessen; alle Phasen-Korrekturen hängen an diesem einen Outcome. Das spart Mean Toffolis (`1253.6 → 1245.1`). Die ersten Patches (repräsentativ; vollständige Liste der 91 Einträge in der Quelle):

```python
# Repräsentative Anfangs-Patches von CARRY_PATCHES (vollständig: 91 Einträge,
# Source-Index 'at' ab 28146 aufwärts; alle folgen demselben Muster).
CARRY_PATCHES = [
 {'at': 28146, 'matching_block_length': 375, 'new': ['HMR q61 b70003'], 'old': []},
 {'at': 28176, 'matching_block_length': 375, 'new': ['HMR q57 b308'], 'old': []},
 {'at': 28261, 'matching_block_length': 375,
  'new': ['CX q40 q61', 'CX q61 q40'],
  'old': ['CX q28 q40', 'HMR q40 b341', 'CZ q44 q14 if b341']},
 {'at': 28266, 'matching_block_length': 375,
  'new': ['CX q28 q57', 'CX q57 q28'],
  'old': ['CX q21 q28', 'HMR q28 b341', 'CZ q43 q54 if b341']},
 {'at': 28322, 'matching_block_length': 375,
  'new': ['Z q61', 'Z q60', 'CZ q60 q55', 'CZ q61 q55', 'CZ q60 q61'],
  'old': ['X q54', 'X q14', 'X q55', 'CX q21 q43', 'CX q21 q54', 'CCX q43 q54 q28',
          'CX q21 q28', 'CX q28 q44', 'CX q28 q14', 'CZ q28 q55', 'CZ q28 q60',
          'CZ q55 q60', 'CX q60 q55', 'CCZ q44 q14 q55', 'CX q60 q55', 'CX q28 q14',
          'CX q28 q44', 'CX q21 q28', 'HMR q28 b456', 'CZ q43 q54 if b456',
          'CX q21 q54', 'CX q21 q43', 'X q54', 'X q14', 'X q55']},
 {'at': 28348, 'matching_block_length': 375,
  'new': ['HMR q61 b0', 'CZ q44 q14 if b0', 'CZ q57 q14 if b0', 'CZ q44 q57 if b0',
          'Z q44 if b0', 'Z q57 if b0', 'HMR q57 b0', 'CZ q43 q54 if b0',
          'CZ q21 q54 if b0', 'CZ q43 q21 if b0', 'Z q43 if b0', 'Z q21 if b0'],
  'old': []},
 # … 85 weitere Patches (at 28418 … 29789), identisches Muster …
]
```

```python
# EXPECTED_MEMBERS: die 18 Ziel-Hashes (invsqrt.kmb = 13b5bf7a…, dqi.kmb = 4432ec5f…,
# submission.npz = 5bd35757…). Ruft build_submission() auf und verifiziert alles.
EXPECTED_MEMBERS = {'dfthcsos/angle_k_0.kmb': 'd3aab747…',  # … (15 angle_k_*.kmb)
 'dfthcsos/submission.npz': '5bd3575736fdf340231b18dcbbe35f1ff9e0e8606f6081258aa54f4d0f9e59eb',
 'dqi.kmb': '4432ec5fd63d7d70aab92d32f719d47539d0ff66ae0cb0b964c914e01fece431',
 'invsqrt.kmb': '13b5bf7a18bce52a19c17e929869b852c0a1bb58d1d49bd7781570cc9ca762c9'}
output = build_submission(INPUT, WORK, EXPECTED_MEMBERS)
print(f"{output.name} | {output.stat().st_size:,} bytes | SHA-256 {digest(output)}")
print("Both all18 source manifests and all18 selected output members verified.")
```

```python
# Plot: links die drei unabhängigen Inverse-Messungen (Mean Toffolis), rechts die
# lokalen/offiziellen Scores. Zeigt den Effekt der Carry-Erasure quantitativ.
import matplotlib.pyplot as plt
fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), constrained_layout=True)
counts = [1253.617141265049, 1246.1175704392872, 1245.1180290289672]
for row, value in enumerate(counts):
    axes[0].scatter(value, row, s=65, color="#157f73" if row==2 else "#3978a8")
    axes[0].annotate(f"{value:,.3f}", (value,row), xytext=(0,10), textcoords="offset points", ha="center", fontsize=9)
axes[0].set_yticks(range(3), ["V21 inverse", "V22 carry port", "Carry + domain"])
axes[0].set_ylim(2.5,-0.6)
axes[0].set_xlim(min(counts)-2, max(counts)+2)
axes[0].set_xlabel("Mean Toffolis, original verifier")
axes[0].set_title("Independent inverse measurements")
axes[0].grid(axis="x", alpha=0.2)
scores = [25.13115, 25.13665, 25.136651794040066]
for row, value in enumerate(scores):
    axes[1].scatter(value, row, s=65, facecolors="white" if row==2 else "#3978a8", edgecolors="#157f73" if row==2 else "#3978a8", linewidths=1.8)
    axes[1].annotate(f"{value:.8f}" if row==2 else f"{value:.5f}", (value,row), xytext=(0,10), textcoords="offset points", ha="center", fontsize=9)
axes[1].set_yticks(range(3), ["V22 official", "Özer V15 official", "This version local"])
axes[1].set_ylim(2.5,-0.6)
margin=max(0.0002,(max(scores)-min(scores))*0.2)
axes[1].set_xlim(min(scores)-margin,max(scores)+margin)
axes[1].set_xlabel("Geometric mean of reference / cost")
axes[1].set_title("Local and official results")
axes[1].grid(axis="x", alpha=0.2)
for ax in axes:
    ax.ticklabel_format(axis="x", style="plain", useOffset=False)
fig.savefig(WORK / "verification_overview.png", dpi=160)
plt.show()
```

> **📊 Cost-Delta (InvSqrt):** Mean Toffolis `V21 1253.617 → V22 carry port 1246.118 → Carry+domain 1245.118`. Score `V22 official 25.13115 → Özer V15 25.13665 → This version local 25.13665179`.

## Sources and attribution

- [Our V22](https://www.kaggle.com/code/kirilltym/quantum-circuits-pi-gauge-weight-refinement?scriptVersionId=366737647) independently ported Hosen V5's carry erasure onto the newer Syed/Maoxin inverse. [Atakan V2](https://www.kaggle.com/code/atakanaldemir/qcc-early-measurement-and-domain-aware-inverse?scriptVersionId=366721329) identified the domain-redundant controlled swap. We combine these exact data edits and independently check the resulting `13b5bf7a` inverse.
- [Özer V15](https://www.kaggle.com/code/ozertuu/25-136-starter-notebook?scriptVersionId=366740074) published this same inverse and complete combination before this release. Its actual archive's all18 hashes match our selected members. We claim independent reconstruction, audit and integration here, not a new improvement over that combination.
- [Isabe V12](https://www.kaggle.com/code/isabe11am00re/qcc-v66s33w-submission?scriptVersionId=366712739) supplies `4432ec5f` DQI, three cache routes beyond our earlier `337cb049` measurement-order composition, and the `5bd35757` fixed-word factor refinement. The 15 Syed loaders remain byte-identical. Its factor's extra keys are retained and strictly checked.
- Google Quantum AI and Qualtran supply the original SDK and verifiers. All inherited notices and direct earlier credits below remain preserved. Code and original prose here retain Apache-2.0; upstream compiled artifacts retain their separate scopes and notices within the reviewed in-platform reuse. This does not relicense upstream generators, reproduce unpublished producers or establish prize eligibility.

### Retained lineage

[Hosen V4](https://www.kaggle.com/code/hosen42/vqcc-our-submission?scriptVersionId=366537593) and [V5](https://www.kaggle.com/code/hosen42/vqcc-our-submission?scriptVersionId=366583334) supply the carry-erasure method. [Maoxin V3](https://www.kaggle.com/code/maoxin123/lb-25-09-syed-circuits-refit-chem-weights?scriptVersionId=366625778) supplies the newer inverse base and prior weights, retaining [Syed V11](https://www.kaggle.com/code/syed3000/vqcc-own-circuit-portfolio-notebook?scriptVersionId=366611575), the mrmeows → busyaprime → yoyobar inverse line and Hosen's earlier measure-first windows.

The DQI lineage includes our 14 measurement-order rewrites on [Özer V5](https://www.kaggle.com/code/ozertuu/24-9412-sota-multi-task-quantum-frontier-v6?scriptVersionId=366545371), Atakan Aldemir, MAIDANG / daifanhao, Syed Asad Ali, SomeJoint / Agniv Banerjee, Ali Haydar Özdağ and James Day / jday96314. The decoder keeps its separate inherited scopes; the notebook's Apache label is not a blanket licence for the decoder or its producer.

The chemistry lineage includes Lera / marculera, Özer's progressive rounding, Heliosli's fixed-word refit idea, Maoxin, Isabe11aM00re, James Barlow / manwithacat and Atakan's π-gauge, with Syed's exact table and 15 loaders. The earlier V21 and V22 attribution files remain preserved verbatim as historical notices; this section describes the current selection.

## Verification records

The following reports are the preserved independent results. Their original fields and penalties are retained.

> **Kern-Receipts aus `VERIFICATION`** (vollständige Dicts inkl. aller per-Operation-Shot-Zählungen, Preregistrations, Audit-Archive und Salt-Hashes in der Quelle):
>
> | Komponente | Qubits | Cost (score) | Shots | Fehler | Repetition |
> |---|---:|---:|---:|---:|---:|
> | Inverse (carry+domain, `13b5bf7a`) | 62 | **95,492.95** | 200,540,928 | – | – |
> | DQI (`4432ec5f`) | 892 | 374,735,803,217.46 | 102,400 | 0 / 0 | 1.191260465 |
> | Chemistry (`5bd35757`) | 427 | 299,662,437.60 | 78,080 | – | – |
>
> Zusätzlich: `bootstrap_failure` (PRE_NUMERICAL_BOOTSTRAP_FAILURE — Import-Shadowing vor der Tensor-Kampagne, dokumentiert), `chemistry_preregistration`, `dqi`-Report, MPS-Kampagnen-Records.

## Conclusion

The combined inverse costs 95,492.95; the independently checked DQI and chemistry costs give a local estimate of 25.13665179, with every measured error and penalty retained. The component hashes match the published Özer V15 composition. This version adds our own complete verification receipts, readable reconstruction, fixed negatives and explicit limits to the original notebook. Its official score is determined by Kaggle after submission.

> *(Hinweis: Cell 9 `NOTICE_TEXT` enthält die vollständigen Apache-2.0-Lizenztexte + 8 Credit-/Provenance-Dateien (CARRY_DOMAIN_COMPOSITION_CREDITS.md, CARRY_PORT_CREDITS.md, ISABE_V19_*, MAOXIN_V3_*, OZER_V23_*, Q18_*, SAMANYU2_*, YOYO_V36_*). Für das Lernen sind die obigen „Sources and attribution“-Abschnitte die verdichtete Form; der Volltext ist in der Quelle.)*

---

## 🔑 Kern-Technik in 3 Sätzen

**Carry Erasure** ersetzt das teure Uncompute-Muster `Compute(CX) → Measure(HMR) → conditional Phase(CZ if bit)` durch eine dedizierte Carry-Wire (q57/q61): das Ergebnis wird per zwei CXs dorthin geschoben und **einmal** gemessen, woran dann alle Phasen-Korrekturen gebündelt hängen — das senkt die Mean Toffolis von `1253.6` auf `1245.1` (Cost `95,492.95`). Zusätzlich wird der domain-redundante `CSWAP q23 q6 q28` gelöscht, weil `q23 & (q6^q28)=0` auf allen erreichten Zuständen gilt (Audit über 3,133,452 Inputs). Der KMB-Codec (`read_inverse`/`encode_like`) zeigt, wie Circuit-Bytes deterministisch gelesen/gepatcht werden — jede Änderung ist ein exakter, hash-geprüfter Daten-Hunk, kein Generator-Lauf.

## 📝 Lern-Notizen (füll das selbst aus)

- [ ] Technik verstanden: Carry-Erasure = batchtes Measure+Phase über gemeinsame Carry-Wire statt pro-Bit-Uncompute
- [ ] Cost-Delta nachvollziehbar: 1253.6 → 1246.1 (carry port) → 1245.1 (+domain swap) Mean Toffolis; Cost 95,492.95
- [ ] Könnte ich das selbst bauen?: teilweise/weil… (Codec klar; die 91 Patches erfordern aber exakte Source-Hashes + MPS-Audit)
- [ ] Verbindung zu anderen Notebooks: baut auf 02 (62Q `034c7c2a`) auf; 05 zeigt die Quadratic-Variante; 06 die Readout-Variante
- [ ] Frage die ich noch habe: Warum ist HMR (Measure+Reset) günstiger als vollständiges Uncompute per inversen Gates?
