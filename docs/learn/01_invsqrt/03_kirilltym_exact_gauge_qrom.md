# Smaller circuits, honest costs

> **Lernziel:** Die **Cost-Methodik** des Tracks verstehen: wie ein vollständiger Original-Verifier-Receipt (Shots, Qubits, Mean Toffolis, Repetition-Faktor) in den geometrischen Mittelwert `S = (∏ C_ref/C)^(1/3)` eingeht — plus die 63Q-Inverse-Baseline als Referenz.
> **Dauer:** ~12 Minuten lesen
> **Quelle:** kirilltym | Votes: – (im lokalen Kernel-Dump nicht enthalten)
> **Technik:** Cost-Methodik / Gauge-Vergleich (+ Inverse-Baseline-Receipt)
> **Level:** Mittel → Fortgeschritten

> ⚠️ **Wichtiger Hinweis (veralteter Slug):** Der Ordner heißt `kirilltym__quantum-circuits-exact-gauge-5-word-qrom`, aber die **aktuelle** Version dieses Notebooks trägt den Titel *„Smaller circuits, honest costs“* und behandelt primär den **DQI-Decoder-Vergleich** (4 öffentliche Decoder) plus ein **Chemie-Phasen-Audit (Mac MPS)**. Für den InvSqrt-Track ist es relevant, weil es (a) die **63Q-Inverse-Baseline** (`busyaprime`, 200,540,928-Shot-Receipt) dokumentiert und (b) die **Cost-/Evidenz-Hierarchie** zeigt, die in allen anderen Notebooks wiederverwendet wird.

---

# Smaller circuits, honest costs

**Our latest confirmed Public Score is 22.79549 (V24).** This update asks two concrete questions: does a smaller decoder actually cost less after its failure penalty, and do the chemistry loaders preserve phase for every allowed measurement outcome?

We compare four public DQI circuits using our own complete official-verifier receipts. Chemistry comes from Atakan's new source-built portfolio; its improved factor and compiler plans remain credited to their authors. Our contribution is independent validation, a Mac MPS symbolic phase audit with a deliberately broken control, exact-byte integration and the readable comparison below.

| Part | Original work | Evidence used here |
|---|---|---|
| 63Q inverse square root | busyaprime, on mrmeows | Our unchanged 200,540,928-shot receipt, bound by SHA-256 |
| Decoder alternatives | Mudit, SomeJoint, Atakan, hengck23 | Our full 102,400-shot result for each, including every error |
| Learned chemistry and 15 loaders | Atakan, Heliosli, Dmitrii Gluzdov, on SomeJoint | Fresh 78,080-shot check plus all-address symbolic MPS audit |

The resulting geometric means are **local estimates**, not new official Public Scores. Kaggle measures again with its own samples. This notebook runs on **CPU / accelerator None**, with internet off.

## 1. Why the smallest decoder can lose

DQI costs `Q² × mean Toffolis × repetition penalty`. Atakan's 888Q policy repairs the previously reported targeted phase regression in SomeJoint's 889Q architecture, but its extra operations can outweigh the saved qubit. We retain its full result alongside both public controls.

hengck23's alternative uses projective extraction, rolling continuants, a one-product tail, and the streamed converter. It deliberately omits some guards in rare low-weight branches. **It is an approximate decoder and fails on parts of a uniform weight sweep.** Its author discloses this limitation; we retain it here. The original metric permits failures and charges their measured repetition penalty. A sampled PASS is not an exact-correctness proof.

Each new policy receives one complete original check at the predeclared salt `oct29-round9-independent`, without salt retries or discarded errors. The 895Q historical control retains its earlier `oct29-round7-independent` check. Original circuit-dependent sample generation is preserved, so equal salts do not mean identical logical inputs between different hashes. Selection uses complete measured cost; the table does not establish the true population-optimal policy.

```python
# Setup: Thread-Limits, Pfade, Salt. Definiert sha256()-Helper.
import os
os.environ.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
from pathlib import Path, PurePosixPath
import hashlib, json, zipfile, tempfile, shutil, sys, math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, FileLink

INPUT = Path("/kaggle/input")
WORK = Path("/kaggle/working")
SALT = "oct29-round9-independent"

def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()
```

### Die vier DQI-Decoder im Vergleich (Kern-Daten aus `POLICY_REPORTS`)

> Das Notebook speichert für jeden Decoder einen kompletten Verifier-Report inkl. aller per-Operation-Shot-Zählungen (`shot_operation_counts`), SHA-256 und Qubit/Bit-Zahlen. Für das Lernen sind die **Cost-relevanten Felder** entscheidend — hier als Tabelle:

| Policy | Qubits | Mean Toffolis | Value/Phase Err | Repetition-Faktor | DQI-Cost (score) |
|---|---:|---:|---:|---:|---:|
| 895Q · Mudit (V24 control) | 895 | 432,438.88 | 0 / 0 | 1.191260465 | 412,645,903,413.52 |
| 889Q · SomeJoint | 889 | 437,947.50 | 0 / 0 | 1.191260465 | 412,318,006,028.23 |
| 888Q · Atakan repair | 888 | 438,992.75 | 0 / 0 | 1.191260465 | 412,372,797,078.20 |
| **889Q · hengck23 (SELECTED)** | **889** | **433,784.72** | 0 / 0 | 1.191260465 | **408,398,843,362.99** |

> **🔥 Learning Point:** Der *kleinste* Decoder (888Q, Atakan) ist **nicht** der billigste — seine Extra-Operationen überwiegen das gesparte Qubit. hengck23 (889Q) gewinnt mit dem niedrigsten Mean-Toffoli-Wert (433,784) trotz identischem Repetition-Faktor. → *„Width alone does not determine cost.“*

Weitere gepinnte Konstanten im Notebook (vollständig in Quelle):
- `SOURCE_ARCHIVE_SHA256 = df8490c7…f742a` + 18 `SOURCE_MEMBERS`/`SELECTED_MEMBERS` (SHA-256 je `.kmb`/`.npz`).
- `EXPECTED_CHEMISTRY`: status PASS, score **339,728,082.34**, λ_eff 48.5596, toffoli 16,270, Q **430**, brot 8, batch 5, 15 Circuits, 78,080 shots; metrics error_1≈0.0199997, error_2≈0.0199997, E_gap 3.9149.
- `MPS_PROOF`: device mps, PASS, **36,600** basis trajectories, alle 15 Batches 0 value/0 phase failures, seconds 81.48.
- `NEGATIVE_CONTROL`: device mps, **FAIL**, 2,440 trajectories, Batch 0 → **152 phase_failures** (bewusst entferntes Cleanup-CZ).

## 2. Authenticate data before using it

Inputs are pinned to Atakan's **V3 / run 363508203**, SomeJoint's **V21 / run 363462588**, our research-assets **V9**, and hengck23's `dqi_iter014.kmb` with the exact published hash. Atakan's frozen archive supplies the new chemistry and unchanged inverse circuit. Only the selected decoder may be replaced. Every one of the 18 output members is checked again.

These inputs are circuit **data**. No competitor Python, build wrapper or verifier fork is executed by this notebook. The optional local audit below is our own readable source.

```python
# Authentifiziert alle Inputs: prüft offizielle Verifier-Hashes, extrahiert das
# gepinnte Source-Archiv, ersetzt nur den gewählten Decoder, verifiziert alle
# 18 Mitglieder erneut gegen SELECTED_MEMBERS.
COMP = next(
    p.parents[2]
    for p in INPUT.rglob("verify_submission_invsqrt.py")
    if p.parents[2].name == "google-verifiable-quantum-circuit-compilation"
)
ASSETS = next(p.parent for p in INPUT.rglob("oct29_manifest.json"))
asset_manifest = json.loads((ASSETS / "oct29_manifest.json").read_text())
for name, expected in asset_manifest["official_inputs"].items():
    assert sha256(COMP / name) == expected, name
source_archive = next(
    p
    for p in INPUT.rglob("submission.zip")
    if "qcc-888q-repair-and-native-chemistry-co-design" in str(p)
    and sha256(p) == SOURCE_ARCHIVE_SHA256
)
SUB = Path(tempfile.mkdtemp(prefix="measured-portfolio-"))
with zipfile.ZipFile(source_archive) as archive:
    assert set(archive.namelist()) == set(SOURCE_MEMBERS)
    for name, expected in SOURCE_MEMBERS.items():
        member = PurePosixPath(name)
        assert not member.is_absolute() and ".." not in member.parts
        blob = archive.read(name)
        assert hashlib.sha256(blob).hexdigest() == expected, name
        target = SUB / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
if SELECTED_MEMBERS["dqi.kmb"] != SOURCE_MEMBERS["dqi.kmb"]:
    decoder_source = next(
        p
        for p in INPUT.rglob("dqi_iter014.kmb")
        if sha256(p) == SELECTED_MEMBERS["dqi.kmb"]
    )
    shutil.copyfile(decoder_source, SUB / "dqi.kmb")
actual = {
    p.relative_to(SUB).as_posix(): sha256(p) for p in SUB.rglob("*") if p.is_file()
}
assert actual == SELECTED_MEMBERS
assert MPS_PROOF["circuit_hashes"] == {
    k: v for k, v in actual.items() if k.startswith("dfthcsos/angle_")
}
print("Authenticated 18 members; selected:", SELECTED_POLICY)
```

## 3. Use complete checks, with an explicit scope

The original Google Quantum AI verifier and input files are authenticated above. Chemistry is checked afresh with all 78,080 shots, unchanged reference integrals, accuracy bounds and gap floor. The numerical factor is close to the acceptance boundary, so this check matters.

The unchanged inverse circuit uses our own complete 200,540,928-shot receipt. The selected decoder uses the independent complete 102,400-shot receipt displayed above, tied to its exact hash. These static receipts are reused openly; this saved run does not claim to repeat them or add independent evidence. Both new decoders were checked once before release, and every observed failure is retained.

```python
# Führt die echten Checks aus: lädt den Inverse-Receipt (200,540,928 shots),
# den Decoder-Report und startet den frischen Chemie-Verifier (78,080 shots).
# Zeigt eine Task/Shots/Q/Cost-Tabelle.
sys.path[:0] = [str(COMP / "kickmix"), str(COMP / "verifiers")]
import kickmix as km
from dfthcsos import verify as chemistry

inverse_report = json.loads((ASSETS / "new_inv_full.json").read_text())
assert (
    inverse_report["status"] == "PASS" and inverse_report["verified_shots"] == 200540928
)
assert inverse_report["circuit_sha256"] == actual["invsqrt.kmb"]
decoder_report = POLICY_REPORTS[SELECTED_POLICY]
assert decoder_report["status"] == "PASS" and decoder_report["verified_shots"] == 102400
assert decoder_report["circuit_sha256"] == actual["dqi.kmb"]
chemistry_report = chemistry.verify(str(SUB / "dfthcsos"), salt=SALT)
assert (
    chemistry_report["status"] == "PASS" and chemistry_report["verified_shots"] == 78080
)
assert chemistry_report["submission_sha256"] == EXPECTED_CHEMISTRY["submission_sha256"]
assert math.isclose(
    chemistry_report["score"], EXPECTED_CHEMISTRY["score"], rel_tol=1e-12
)
reports = {
    "invsqrt": inverse_report,
    "dqi": decoder_report,
    "dfthcsos": chemistry_report,
}
display(
    pd.DataFrame(
        [
            {
                "Task": t,
                "Shots": r["verified_shots"],
                "Q": r["num_qubits"],
                "Cost": r["score"],
            }
            for t, r in reports.items()
        ]
    )
)
```

## 4. Compare the whole bill

The table holds the newly verified chemistry and unchanged inverse cost fixed, isolating the decoder choices. The historical 895Q measurement used a different declared salt. Costs include the confidence/repetition factor even when zero errors were observed. None of these rows is a new official competition result.

```python
# Rechnet den lokalen geometrischen Mittelwert pro Decoder, hält Chemie+Inverse
# fest, und zeichnet ein Horizontal-Bar-Chart „Local GM“. Speichert CSV+PNG.
reference = asset_manifest["reference_costs"]
fixed_product = (
    reference["invsqrt"]
    / inverse_report["score"]
    * reference["dfthcsos"]
    / chemistry_report["score"]
)
rows = []
for label, result in POLICY_REPORTS.items():
    rows.append(
        {
            "Policy": label,
            "Q": result["num_qubits"],
            "Mean Toffolis": result["toffoli_count"],
            "Value errors": result["value_errors"],
            "Phase errors": result["phase_errors"],
            "Repetition factor": result["repetition_factor"],
            "DQI cost": result["score"],
            "Local GM": (fixed_product * reference["dqi"] / result["score"]) ** (1 / 3),
        }
    )
comparison = pd.DataFrame(rows)
display(comparison)
local_gm = (fixed_product * reference["dqi"] / decoder_report["score"]) ** (1 / 3)
print(f"Selected local GM {local_gm:.8f}; previous confirmed Public Score 22.79549.")
fig, ax = plt.subplots(figsize=(9, 4), layout="constrained")
ax.barh(
    comparison["Policy"],
    comparison["Local GM"],
    color=[
        "#a3abb5" if p != SELECTED_POLICY else "#177e89" for p in comparison["Policy"]
    ],
)
for i, row in comparison.iterrows():
    ax.text(row["Local GM"], i, f' {row["Local GM"]:.6f}', va="center")
ax.set(
    xlim=(comparison["Local GM"].min() - 0.005, comparison["Local GM"].max() + 0.012),
    xlabel="Local verifier geometric mean",
    title="Width alone does not determine cost",
)
fig.savefig(WORK / "decoder_comparison.png", dpi=160)
plt.show()
comparison.to_csv(WORK / "decoder_comparison.csv", index=False)
```

## 5. Check phase for every measurement outcome

[The competition host's contract](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion/753092) requires the reachable forward/reverse word states at every valid address. It does not require arbitrary incoming target words. The encoded `bit7 == bit6` domain is explicit.

Our Mac MPS audit follows the **actual exported gate text**, on all 1,220 addresses and both reachable incoming batches. Classical wire values are independent of measurements. Every HMR event gets its own formal variable; its phase coefficient starts with the measured wire value. A single-bit-conditioned CZ adds the product of its wire values to that coefficient. Every coefficient and constant phase must vanish, final words must match, and address/scratch must be restored. A reset is accepted only on a provably zero wire. For this supported gate family that covers every HMR assignment, not just two sampled histories.

All 15 loaders pass, across 36,600 address/traversal cases. Removing one real cleanup CZ must leave words correct but fail the phase check; its report is retained below. This establishes the named reachable-state property for these exact gate streams. It is **not** an arbitrary-target XOR proof, a general quantum simulator, or a proof of the complete DQI decoder. The full native chemistry check independently complements it.

The readable function below runs on Mac MPS after downloading `mac_audit_inputs`; it is not called by the Kaggle CPU run. This audit follows standard measurement/phase semantics, with independent implementation here. Related public all-HMR reachable audits by mrmeows, Ahmed and Atakan are credited below.

```python
# Gibt die fertigen MPS-Ergebnisse aus: Proof (PASS, 36,600 Fälle) und das
# negative Control (FAIL, 152 phase_failures nach entferntem CZ).
print(
    "MPS symbolic proof:",
    MPS_PROOF["status"],
    MPS_PROOF["basis_trajectories"],
    "address/traversal cases",
)
print(
    "Deliberately removed CZ:", NEGATIVE_CONTROL["status"], NEGATIVE_CONTROL["batches"]
)
```

```python
# Das Herzstück des Phase-Audits: symbolische MPS-Basis-Trajektorien über den
# tatsächlich exportierten Gate-Text. Jede HMR-Instanz bekommt eine eigene formale
# Phasen-Koeffizienten-Variable; am Ende müssen alle Koeffizienten + konstante
# Phase verschwinden, Words/Address/Scratch wiederhergestellt sein. Läuft auf Mac
# MPS (nicht im Kaggle-CPU-Run). Vollständige Funktion:
def run_symbolic_mps_audit(data_dir):
    """MPS packed basis trajectories of the actual published J5 loaders.
    All valid addresses; both reachable incoming words; independent symbolic HMR coefficients.
    The complete unchanged native verifier is separate.
    """
    import os

    os.environ["OMP_NUM_THREADS"] = "1"
    import torch, numpy as np, json, re, time
    from pathlib import Path
    from collections import Counter

    torch.set_num_threads(1)
    assert torch.backends.mps.is_available()
    t = time.monotonic()
    dev = "mps"
    root = Path(data_dir)
    MASK = (1 << 63) - 1
    with np.load(root / "submission.npz") as z:
        words = (
            torch.from_numpy(z["angle_words"].copy()).to(dev, dtype=torch.int64) & 255
        )
    A, columns = words.shape
    N = A * 2
    W = (N + 62) // 63
    ids = torch.arange(W * 63, device=dev, dtype=torch.int64).reshape(W, 63)
    addr = ids % A
    cases = ids // A
    weights = torch.ones(63, device=dev, dtype=torch.int64) << torch.arange(
        63, device=dev, dtype=torch.int64
    )

    def pack(bits):
        return (bits * weights).sum(-1)

    sel = torch.stack([pack((addr >> j) & 1) for j in range(11)])
    phase_coefficients = []
    phase_bits = {}
    FULL = torch.full((W,), MASK, device=dev, dtype=torch.int64)
    payload = json.loads((root / "angle_kmxs.json").read_text())
    records = []
    for k in range(15):
        text = payload["angle_k_" + str(k)]
        lines = text.splitlines()
        current = words[:, k * 5 : k * 5 + 5]
        previous = words[:, (k - 1) * 5 : k * 5] if k else torch.zeros_like(current)
        current = current[addr.reshape(-1)].reshape(W, 63, 5).permute(2, 0, 1)
        previous = previous[addr.reshape(-1)].reshape(W, 63, 5).permute(2, 0, 1)
        target = torch.where(((cases % 2) == 0)[None], previous, current)
        target_bits = torch.stack(
            [pack((target[j] >> b) & 1) for j in range(5) for b in range(8)]
        )
        q = torch.zeros((128, W), device=dev, dtype=torch.int64)
        q[:11] = sel
        q[11:51] = target_bits
        bits = {}
        phase = torch.zeros(W, device=dev, dtype=torch.int64)
        phase_coefficients = []
        phase_bits = {}
        ordinal = 0
        ops = []
        for line in lines:
            a = line.split()
            if not a or a[0] in ["APPEND_TO_REGISTER", "REGISTER", "INFO_TAG"]:
                continue
            op = a[0]
            qs = [int(x[1:]) for x in a[1:] if re.fullmatch(r"q\d+", x)]
            cond = a[a.index("if") + 1 :] if "if" in a else []
            ops.append((op, qs, cond, a))
        i = 0
        while i < len(ops):
            op, qs, cond, a = ops[i]
            active = FULL if not cond else FULL.clone()
            assert not cond or (
                op == "CZ" and len(cond) == 1
            ), "Nonlinear measurement dependence not supported"
            if op == "CX" and not cond:
                control = qs[0]
                targets = [qs[1]]
                i += 1
                while (
                    i < len(ops)
                    and ops[i][0] == "CX"
                    and not ops[i][2]
                    and ops[i][1][0] == control
                ):
                    targets.append(ops[i][1][1])
                    i += 1
                targets = [v for v, n in Counter(targets).items() if n % 2]
                if targets:
                    tt = torch.tensor(targets, device=dev)
                    q[tt] ^= q[control][None, :]
                continue
            if op == "R":
                # Record actual output and phase below; never suppress errors for scoring.
                assert (
                    not (q[qs[0]] & active).any().item()
                ), "Reset would discard live information"
                q[qs[0]] &= ~active
            elif op == "X":
                q[qs[0]] ^= active
            elif op == "CX":
                q[qs[1]] ^= q[qs[0]] & active
            elif op == "CCX":
                q[qs[2]] ^= q[qs[0]] & q[qs[1]] & active
            elif op == "HMR":
                b = next(x for x in a[1:] if re.fullmatch(r"b\d+", x))
                phase_bits[b] = len(phase_coefficients)
                phase_coefficients.append(q[qs[0]].clone())
                q[qs[0]] = 0
            elif op == "CZ":
                term = q[qs[0]] & q[qs[1]]
                if cond:
                    phase_coefficients[phase_bits[cond[0]]] ^= term
                else:
                    phase ^= term
            else:
                raise ValueError((op, a))
            i += 1
        delta = words[:, k * 5 : k * 5 + 5] ^ (
            words[:, (k - 1) * 5 : k * 5] if k else torch.zeros_like(words[:, :5])
        )
        expected = target ^ delta[addr.reshape(-1)].reshape(W, 63, 5).permute(2, 0, 1)
        expected_bits = torch.stack(
            [pack((expected[j] >> b) & 1) for j in range(5) for b in range(8)]
        )
        assert torch.equal(q[:11], sel), (k, "address")
        assert not q[51:].any().item(), (k, "scratch")
        valid = ids < N

        def count(mask):
            return int(
                (((mask[:, None] >> torch.arange(63, device=dev)) & 1).bool() & valid)
                .sum()
                .item()
            )

        output_mask = (
            (q[11:51] ^ expected_bits)
            .bitwise_or(torch.zeros_like(expected_bits))
            .sum(0)
            if False
            else torch.zeros(W, device=dev, dtype=torch.int64)
        )
        for row in q[11:51] ^ expected_bits:
            output_mask |= row
        phase_bad = count(phase)
        for coeff in phase_coefficients:
            phase_bad += count(coeff)
        first = None
        flags = (
            (output_mask[:, None] >> torch.arange(63, device=dev)) & 1
        ).bool() & valid
        if bool(flags.any().item()):
            flat = int(torch.nonzero(flags.flatten())[0].item())
            wi, bi = divmod(flat, 63)
            first = {
                "address": int(addr[wi, bi].item()),
                "target": [int(target[j, wi, bi].item()) for j in range(5)],
                "traversal_case": int((cases[wi, bi] % 2).item()),
                "actual": [
                    sum(
                        ((int(q[11 + j * 8 + b, wi].item()) >> bi) & 1) << b
                        for b in range(8)
                    )
                    for j in range(5)
                ],
                "expected": [int(expected[j, wi, bi].item()) for j in range(5)],
            }
        records.append(
            {
                "batch": k,
                "value_failures": count(output_mask),
                "phase_failures": phase_bad,
                "first_value_counterexample": first,
            }
        )
        print(json.dumps(records[-1]), flush=True)
    torch.mps.synchronize()
    report = {
        "device": "mps",
        "status": (
            "FAIL"
            if any(r["value_failures"] or r["phase_failures"] for r in records)
            else "PASS"
        ),
        "scope": "Exact AtakanV3 / learned angle co-design 15 ANGLE streams; all1220 addresses, both reachable incoming batches, every independent HMR formal coefficient. Values, phase, address and scratch checked; no arbitrary-target claim.",
        "basis_trajectories": N * 15,
        "phase_method": "Every HMR event has its own formal variable; final phase coefficient of each must vanish. All classical gates are measurement independent; only single-bit-conditioned CZ allowed.",
        "batches": records,
        "seconds": time.monotonic() - t,
    }
    (root / "symbolic_phase_mps_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)
```

## 6. Export exactly the verified bytes

Only 18 authenticated production members enter `submission.zip`. Receipts, the comparison, credits, and Mac audit inputs remain separate outputs. Running this cell does not make a competition submission. Numerical boundaries and stochastic DQI failures remain relevant when Kaggle grades the archive.

```python
# Exportiert exakt die 18 verifizierten Bytes in submission.zip (deterministisch),
# schreibt verified_release.json und exportiert die Mac-Audit-Inputs (.kmx + json).
assert {
    p.relative_to(SUB).as_posix(): sha256(p) for p in SUB.rglob("*") if p.is_file()
} == SELECTED_MEMBERS
archive_path = WORK / "submission.zip"
with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
    for name in sorted(SELECTED_MEMBERS):
        info = zipfile.ZipInfo(name, date_time=(2026, 10, 29, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, (SUB / name).read_bytes())
with zipfile.ZipFile(archive_path) as archive:
    assert archive.testzip() is None
    assert {
        n: hashlib.sha256(archive.read(n)).hexdigest() for n in archive.namelist()
    } == SELECTED_MEMBERS
receipt = {
    "archive_sha256": sha256(archive_path),
    "members": actual,
    "reports": reports,
    "decoder_comparison": POLICY_REPORTS,
    "mps_proof": MPS_PROOF,
    "negative_control": NEGATIVE_CONTROL,
    "salt": SALT,
    "local_geometric_mean": local_gm,
    "official_public_score": None,
}
(WORK / "verified_release.json").write_text(json.dumps(receipt, indent=2))
mac_inputs = WORK / "mac_audit_inputs"
mac_inputs.mkdir(exist_ok=True)
angle_texts = {}
for k in range(15):
    circuit = km.Circuit.from_file(str(SUB / f"dfthcsos/angle_k_{k}.kmb"), format="kmb")
    target = mac_inputs / f"angle_k_{k}.kmx"
    circuit.to_file(str(target), format="kmx")
    angle_texts[f"angle_k_{k}"] = target.read_text()
(mac_inputs / "angle_kmxs.json").write_text(json.dumps(angle_texts))
shutil.copyfile(SUB / "dfthcsos/submission.npz", mac_inputs / "submission.npz")
print("Archive SHA-256:", receipt["archive_sha256"])
display(FileLink(str(archive_path)))
```

## Credits and licences

- **hengck23:** [DQI iteration 014 / notebook V1, run 363497772](https://www.kaggle.com/code/hengck23/dqi-kmb-at-59-56854?scriptVersionId=363497772), [binary dataset](https://www.kaggle.com/datasets/hengck23/hengck23-dqi-59-57). Projective extraction/reverse, rolling continuants, tail/head folds, streamed-converter integration and explicit rare-weight approximations. Generator is not supplied by the author; we use the unchanged public binary and do not claim its invention or a source rebuild.
- **Atakan Aldemir:** [888Q and chemistry V3, run 363508203](https://www.kaggle.com/code/atakanaldemir/qcc-888q-repair-and-native-chemistry-co-design?scriptVersionId=363508203). Learned angle/factor co-design, constrained coefficients, native emitter and node-policy repair. The default source archive supplies the selected chemistry and 888Q comparison.
- **SomeJoint / Agniv Banerjee and their credited research team:** [889Q V21, run 363462588](https://www.kaggle.com/code/somejoint/quantum-circuits-22-77-local-gm-889-qubit-dqi?scriptVersionId=363462588), paired charts, inverse19 reverse, streamed synthesis and head schedule; [earlier streamed decoder V20, run 363324999](https://www.kaggle.com/code/somejoint/quantum-circuits-22-75-local-gm-897-qubit-dqi?scriptVersionId=363324999). Their R8/B143/C60 chemistry factorization and words underpin this portfolio.
- **Mudit Chaturvedi / muchat007:** [895Q V3, run 363366074](https://www.kaggle.com/code/muchat007/895q-streamed-decoder-measured-node-choices?scriptVersionId=363366074), historical measured-width control.
- **Heliosli:** [V20, run 363468177](https://www.kaggle.com/code/heliosli/the-dataset-is-public-now-enjoy?scriptVersionId=363468177), paired product plan reductions; **Dmitrii Gluzdov:** [V34, run 363471947](https://www.kaggle.com/code/dmitriigluzdov/quantum-circuit-compilation-from-source?scriptVersionId=363471947), distinct loader reduction and numerical-factor lineage. These public reductions are not our synthesis gains.
- **Ahmed Berat Özer:** [V12, run 363485081](https://www.kaggle.com/code/ahmedberatozer/quantum-ai-df-thc-group-compression?scriptVersionId=363485081), joint coefficient/gauge and reachable-phase research, reviewed as a public control. His factor is not substituted silently for Atakan's.
- **Akmal Xodarev / busyaprime, on mrmeows / team selenium:** [63Q inverse V9, run 363321323](https://www.kaggle.com/code/busyaprime/lb-22-72431-22x-cheaper-than-google-s-circuits?scriptVersionId=363321323), unchanged arithmetic; earlier Phuc Thai / DePie and marsyas lineage.
- **mrmeows:** [public open circuits and phase-audit lineage](https://www.kaggle.com/datasets/mrmeows/qcc-1375-open-circuits). **Alex Chilton:** [public portfolio](https://www.kaggle.com/code/alexchilton/22-57-lb-verified-three-task-portfolio), Schur decoder lineage. **manwithacat:** [public diagnostics](https://www.kaggle.com/code/manwithacat/the-real-150k-was-the-friends-we-made), phase/failure study lineage.
- **Kirill Tymchishin:** independent native full comparisons at declared conditions, the MPS formal-coefficient implementation and mutation test, exact-byte integration and this explanation. Our earlier gauge formulation is separately credited by downstream authors; no public circuit gain here is relabelled as ours.
- **Tanuj Khattar / Google Quantum AI:** [official reachable-state ruling](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion/753092), original tasks, Kickmix and unchanged verifiers. Earlier design chains include Ahmed, Alex, jday96314, ViberTeam / Artem1410 / anazemcev, Phuc Thai, Kozykorpesh, Michael Rustad, lightningv08, marculera and others named by the linked sources.

New integration/audit code is Apache-2.0; upstream components retain their notices and licences. The original jday96314 repository has no explicit licence; this notebook redistributes no source from it and claims no blanket licence over that history. Published compiled circuit data are reused with attribution. No complete inverse/decoder generator is claimed here.

```python
# Schreibt die Credits + direkten Versions-Links nach CREDITS.txt (vollständiger
# Text identisch zur obigen Markdown-Sektion).
(WORK / "CREDITS.txt").write_text(
    "## Credits and licences\n\n- **hengck23:** … (identisch zur obigen Sektion) …"
)
print("Credits and direct version links retained.")
```

---

## 🔑 Kern-Technik in 3 Sätzen

Der Score ist der **geometrische Mittelwert** der drei Reference/Cost-Verhältnisse `S=(∏ C_ref/C)^(1/3)` — und jede Cost enthält den **Repetition-Faktor** (Confidence-Penalty), selbst wenn 0 Fehler beobachtet wurden. Das zentrale Gegenintuitive: Der kleinste Decoder (888Q) ist nicht der billigste, weil Extra-Gates das gesparte Qubit überwiegen — *„width alone does not determine cost“*. Das Mac-MPS-Phase-Audit führt den Gate-Text **symbolisch** aus (jede HMR = eigene formale Phasenvariable, alle Koeffizienten müssen verschwinden) und beweist damit die *reachable-state*-Eigenschaft über 36,600 Fälle statt zwei Stichproben.

## 📝 Lern-Notizen (füll das selbst aus)

- [ ] Technik verstanden: Cost = Q×(Toffolis+T/4) × Repetition-Faktor; Score = GM der drei Tasks
- [ ] Cost-Delta nachvollziehbar: 888Q (438,992 Toffolis) > 889Q hengck23 (433,784) trotz mehr Qubits
- [ ] Könnte ich das selbst bauen?: MPS-Audit ja (logikklar); Decoder-Vergleich ja (nur Receipts nötig)
- [ ] Verbindung zu anderen Notebooks: liefert die 63Q-Inverse-Baseline + Cost-Methodik für 02/04/05/06
- [ ] Frage die ich noch habe: Wie wirkt sich der Repetition-Faktor exakt auf den Final-Score aus (Formel)?
