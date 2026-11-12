# QCC | Verified Portfolio + DF-THC Retraining Study

> **Lernziel:** Systematisches Retraining von DF-THC-Faktorisierungen bei kleineren (R,B,C): der Trade-off zwischen weniger Zwei-Körper-Vektoren (günstigere QROMs, A = 76 + R·B) und steigendem kontinuierlichem Fehler-Floor — plus die zwei Hebel, die kleine R überhaupt erst nutzbar machen.
> **Dauer:** ~12 Minuten lesen
> **Quelle:** DePie (phucthaiv02) · 31 votes
> **Technik:** Factorization / Weight Refit / Rounding (systematisches Retraining)
> **Level:** Fortgeschritten

---

A simple, fully verified submission for **Verifiable Quantum Circuit Compilation**: for every task we take the
cheapest circuit that passed our own independent checks, and we document what we measured along the way.

**Estimated score 11.440** (geometric mean of reference/cost, computed from our own full-mode verifier runs;
the leaderboard uses a secret salt, so dqi in particular can move a little).

| task | cost (our full-mode runs) | vs reference | source |
|---|---|---|---|
| invsqrt | 136796 | 15.182× | ours (EXP-226a) |
| dqi | 9.67976e+11 | 25.248× | ours (EXP-250a) |
| dfthcsos | 8.59175e+08 | 3.906× | ours (EXP-233b) on ahmedberatozer's R24/60/30 v3 factorization (dataset labelled other); gauge idea from haideptry |

Our checks for every circuit: official verifier in **full mode on ≥ 2 salts** (often 4–5, one at 4× shots),
a separate red-team pass (extra salts, metric file checks, determinism), and a sha256 check below so the zip
contains exactly the verified bytes.

## Approach per task

**invsqrt.** Our port of Dmitrii Gluzdov's 84-qubit construction (public notebook, Apache-2.0; circuits/invsqrt/mux84.py rebuilds his circuit byte-for-byte), itself built on the Sumit Chongder / anazemcev / Kozykorpesh / Zongao Bian lineage: one-bit normalisation, a quadratic segment QROM with signed-digit Horner rows, a grouped curvature lookup erased by measurement, a virtual lowest accumulator bit, deferred high-word erasure with a joint ANF phase repair, exact-domain CCX rewrites and LP-calibrated rotations. **Our additions (EXP-221):** carry-save outer rows (the 11 narrowest rows add into part of the low word plus a 2-bit counter, folded in once; counter range proven over all x), removal of the derivative's bit-0 wire by refitting K1's parity in 116 segments (with a new LP calibration), CCX leaves in the curvature lookup, a 1-bit Cuccaro prefix on the two full-width rows, and extra exact-domain passes including a measurement-based (HMR + conditioned CZ) rewrite that is exact on both outcomes. Q 84 → 82, 1537.5 → 1405 Toffoli-eq: 155,798 → 141,462 (−9.2%). **Then:** a one-bit normalisation ladder with a margin refit (EXP-222a, 140,719) and a fused phase stage (marsyas's idea: CSWAPs for output shifts 1 and 2, one temporary per rotation read; EXP-225a, 138,095). **Then (EXP-226a):** a phase mask that drops phase terms fixed by the masked domain, phase rotations moved to Clifford positions where the angle allows, and constant curvature blocks: 136,796 (worst_err/tol 0.99979).

**dqi.** SomeJoint (Agniv Banerjee)'s 932-qubit continued-fraction (J-fraction) Reed–Solomon decoder, which reuses the 840-qubit syndrome bank as workspace (public notebook, Apache-2.0), with manwithacat's 70-position classical-mask projection: 70 classical field words λ chosen from a Vandermonde system absorb the measured masks at positions 0..69 into a known syndrome phase, so the Forney scan skips them (Q 932, mean Toffolis 1,418,897, 0 failures). **Our addition (EXP-118c, our port in circuits/dqi/jfrac/ rebuilds the public circuit byte-for-byte):** free the 12-qubit extraction buffer right after its measurement, a lean Forney scan without the constant-1 word and with a one-qubit-shorter zero chain, and the 35 gap flags packed into two 6-bit level pointers (at most two gaps occur; 3+ gaps ≈ 6e-8 per shot): Q 932 → 898 for +3,872 static Toffolis, cost 1.468e12 → 1.373e12 (worst of 6 salts). **Then (EXP-119a):** the extraction handles two continued-fraction levels per series reciprocal (E' = ((1+a1x)f + c1)/x² = f·f1; one normalised reciprocal of E' gives the second level, the next tail follows from an in-place division by (1+a1x); gap repair as pair modes plus three controlled one-word corrections), with outputs identical to upstream: mean Toffolis 1.42M → 1.08M at Q 898, cost 1.046e12 (worst of 6 salts). Our earlier dqi (EXP-117b, v8 above) removed most of V4's phase failures: an exact model of its Berlekamp–Massey stage traced them to a 1-slot reversal-stack overflow, clipped discrepancy windows and the borrow loan at d = −2 (failures ≈ 8 → ≈ 1 per 102,400; cost 1.743e12 → 1.728e12 at the mean), but the J-fraction decoder's far smaller Q wins under the Q² price. **Then (EXP-124b):** fused partial gap rotations (a 5-word prefix by g1, then the suffix by g1⊕g2) and gap flags recomputed from the bank words instead of stored: Q 886, 9.938e11. **Then (EXP-250a, preset l873):** low-peak GF(2¹²) inverses for the scale and continued-division steps, a leaner Forney scan (lean2) and a measurement-based gap toggle: Q 873, T_mean 1.061M, 9.680e11 (worst of 9 salts).

**dfthcsos.** SomeJoint's R26 build on Ahmed Berat Özer's group-compressed DF-THC factorization (public notebooks; code Apache-2.0, the R26 factorization dataset is labelled "other"): λ_eff 48.807, T 31,860, Q 656 with four-address angle loaders (128 qubits each). **Our addition (EXP-223a):** the verifier reads only the weights w and offsets W from submission.npz, so we keep all 25 circuits byte-identical and re-fit (w, W) with the words fixed (joint λ_eff fit under error_2 ≤ 19.94 mHa, Gram-preserving C rotation, offset re-optimisation): λ_eff 48.807 → 47.747, cost 1.02007e9 → 9.9791e8. **Then (EXP-231c):** we rebuild the 25 circuits from the same words with our own four-address generator (circuits/dfthcsos/qrom.py, fouraddr2): a paired bilinear combine (one Toffoli on two shifted bank wires gives two cross terms; 82 → 42 per circuit), a pruned ANF erase (37 → 31) and the redundant sign bit of each signed-gauge word freed for walk monomials (→ 27): ANGLES Toffolis 25,900 → 23,400, T 31,860 → 29,360, cost 9.196e8. Our previous dfthcsos (EXP-218a, EXP-220a; table below) used the R32 factorization: a joint (w, W) refit with the circuits fixed (the verifier reads only w and W from the npz), then our own four-address QROM generator on discretely re-optimised words (λ_eff 47.888, cost 1.16151e9). **Now (EXP-233b):** Ahmed Berat Özer's smaller R24/B60/C30 v3 factorization (dataset labelled "other"), re-encoded into signed-gauge words, our (w, W) refit, new one-body rows, and an orthogonal C-gauge per block that lowers Λ2 at a fixed Gram (idea from haideptry, our own implementation: exact pair sweeps, Cayley descent, seeded basin hopping), built with fouraddr2: λ_eff 47.426, T 27,616, Q 656, cost 8.592e8.

## Measured results across our versions

Local estimates (our verifier runs, not leaderboard scores). Each column is reference cost / our cost.

| version | invsqrt | dqi | dfthcsos | score |
|---|---|---|---|---|
| sample submission | 1.000 | 1.000 | 1.000 | **1.000** |
| v1: Sumit invsqrt port, f2=9 (ours) | 11.485 | 1.000 | 1.000 | **2.256** |
| v2: + public dqi / dfthcsos (Kozykorpesh) | 11.485 | 9.491 | 1.327 | **5.249** |
| v3: + anazemcev invsqrt/dqi, our banked-ANF + λ-refit (EXP-214b) | 12.614 | 10.591 | 1.446 | **5.780** |
| v4: our retrained 50/48/30 factorization (EXP-211i2) | 12.614 | 10.591 | 2.116 | **6.563** |
| v5: best public circuit per task (leaderboard 8.06654) | 13.330 | 14.023 | 2.815 | **8.073** |
| v6: + our w/W refit of the 32/60/30 dfthcsos (leaderboard 8.12145) | 13.330 | 14.023 | 2.873 | **8.128** |
| v7: our invsqrt q82n (EXP-222a) + our fouraddr dfthcsos (EXP-220a) | 14.758 | 14.023 | 2.889 | **8.425** |
| v8: + our V4 phase-failure fixes for dqi (EXP-117b, worst of 6 salts) | 14.758 | 14.040 | 2.889 | **8.428** |
| v9: + public J-fraction dqi (manwithacat) and R26 dfthcsos (somejoint) | 14.758 | 16.646 | 3.290 | **9.314** |
| v10: + our w/W refit of the R26 dfthcsos (EXP-223a; leaderboard 9.38293) | 14.758 | 16.646 | 3.363 | **9.383** |
| v11: + our J-fraction q898 dqi (EXP-118c) | 14.758 | 17.800 | 3.363 | **9.595** |
| v12: + our J-fraction pair extraction (EXP-119a; leaderboard 10.52187) | 14.758 | 23.366 | 3.363 | **10.506** |
| v13: + our fused-phase invsqrt (EXP-225a) | 15.039 | 23.366 | 3.363 | **10.572** |
| v14: + our fouraddr2 QROM for dfthcsos (EXP-231c; leaderboard 10.88048) | 15.039 | 23.366 | 3.649 | **10.864** |
| **current: best verified circuit per task** | 15.182 | 25.248 | 3.906 | **11.440** |

## Our own dfthcsos study: fewer two-body vectors

The ANGLE QROMs dominate T_total and scale with A = 76 + R·B rows, so we retrained DF-THC factorizations at
smaller (R, B) with the organisers' starter-kit trainer on a Kaggle GPU (continuing from anazemcev's
factorization with decreasing λ-weight ρ = 1e-4 → 1e-5 → 3e-6 → 1e-6). Two observations made this work:

1. At small ρ the trainer reports a large E_gap, but that comes only from the identity offsets W, which do
   **not** enter error_2. Re-optimising W (plus a Gram-preserving sparse rotation of the C index) brings E_gap
   back to its floor at fixed error: e.g. 56/54/30 went from λ_eff 91.6 to 48.7.
2. 10-bit encoding with progressive rounding + exact word-level coordinate descent costs only ~2–3 mHa, and a
   joint (w, W) refit then spends the remaining error budget (down to 19.94 mHa) on λ_eff.

All rows: full-mode PASS on ≥ 2 salts; banked-ANF ANGLE QROM (J 5, brot 10) unless noted.

| version | R/B/C | λ_eff | T_total | Q_total | cost | vs reference |
|---|---|---|---|---|---|---|
| EXP-214b (anazemcev factorization + our λ-refit) | 65/60/30 | 47.3704 | 71,958 | 681 | 2.3213e+09 | 1.446× |
| EXP-211e2 (retrained) | 56/54/30 | 47.9269 | 58,149 | 680 | 1.8951e+09 | 1.771× |
| EXP-211j2 (retrained) | 52/50/30 | 48.1767 | 51,501 | 680 | 1.6872e+09 | 1.989× |
| EXP-211i2 (retrained) | 50/48/30 | 48.2476 | 48,330 | 680 | 1.5856e+09 | 2.116× |
| EXP-211n2 (retrained) | 48/46/30 | 48.4455 | 45,314 | 680 | 1.4928e+09 | 2.248× |
| EXP-215a (EXP-211n2 + our port of the four-address QROM) | 48/46/30 | 48.4455 | 42,510 | 660 | 1.3592e+09 | 2.469× |
| EXP-218a (Ahmed's 32/60/30 circuits + our w/W refit) — submitted | 32/60/30 | 48.0938 | 36,911 | 658 | 1.1681e+09 | 2.873× |
| EXP-220a (Ahmed's 32/60/30 factorization, our words + our fouraddr generator) | 32/60/30 | 47.8883 | 36,861 | 658 | 1.1615e+09 | 2.889× |

Going further (48/46 → 46/44) the continuous error floor rises above what quantization leaves room for, and
lower ρ raises Λ. Ahmed Berat Özer's group dropping reaches R = 32 with B = 60, which is better still
(1.192e9); EXP-218a refits its weights, and EXP-220a (our best dfthcsos) rebuilds its circuits
with our generator from re-optimised words.

We also checked the cost model's other big lever: at brot ≤ 7 the shared temporary qubits drop from 543 to
271. With our encoder the errors after 7-bit quantization were 66–72 mHa (error_2) and 58–60 mHa
(error_1) against the 20 mHa limit, so that lever stays out of reach for now.

> **Code (DE):** Baut submission.zip aus den verifizierten Circuits: PLAN pinnt je Task Quelle, Slug, SHA-256 und Cost; content_sha256() prüft Datei- oder Ordner-Bytes exakt; source_root() findet die Bytes unter /kaggle/input (ggf. aus einem ZIP); erst wenn alle SHA-256 stimmen, wird gepackt.

```python

# Build submission.zip from the verified circuits (exact bytes, checked by sha256).
import glob, hashlib, json, os, shutil, zipfile
from pathlib import Path

PLAN = json.loads("""{
 "invsqrt": {
  "source": "dataset",
  "slug": "qcc-best-invsqrt-circuit",
  "rel": "invsqrt.kmb",
  "sha256": "5482422b1c0f2f6814f2b87eb00010f96e31cf38b288522a70ad1f39f9cda6b9",
  "credit": "ours (EXP-226a)",
  "cost": 136796.32254747115
 },
 "dqi": {
  "source": "dataset",
  "slug": "qcc-best-dqi",
  "rel": "dqi.kmb",
  "sha256": "77947749aa4e56a1ee65095c5f3a87aab25689d37256f9e03cc6526b9ccbafde",
  "credit": "ours (EXP-250a)",
  "cost": 967976019171.5812
 },
 "dfthcsos": {
  "source": "dataset",
  "slug": "qcc-best-circuits",
  "rel": ".",
  "sha256": "8261438c79dfdd633180f7d20c50feb8db0601058da3a7c55b4d60da4f17776f",
  "credit": "ours (EXP-233b) on ahmedberatozer's R24/60/30 v3 factorization (dataset labelled other); gauge idea from haideptry",
  "cost": 859175239.3534045
 }
}""")

def content_sha256(p: Path) -> str:
    """sha256 of a file, or of a folder's (relative path, bytes) stream (same as our ledger)."""
    h = hashlib.sha256()
    if p.is_dir():
        for f in sorted(x for x in p.rglob("*") if x.is_file()):
            h.update(f.relative_to(p).as_posix().encode()); h.update(f.read_bytes())
    else:
        h.update(p.read_bytes())
    return h.hexdigest()

def source_root(task):
    e = PLAN[task]
    if e["source"] == "dataset":
        hits = [Path(h) for h in glob.glob(f"/kaggle/input/**/{e['slug']}", recursive=True) if Path(h).is_dir()]
        return Path(hits[0])
    hits = [Path(h) for h in glob.glob(f"/kaggle/input/**/{e['slug']}", recursive=True) if Path(h).is_dir()]
    root = hits[0]
    if not (root / e["rel"]).exists() and (root / "submission.zip").exists():  # circuits only inside the zip
        ext = Path("/kaggle/working/extracted") / e["slug"]
        if not ext.exists():
            with zipfile.ZipFile(root / "submission.zip") as z:
                z.extractall(ext)
        root = ext
    return root

work = Path("/kaggle/working/submission")
shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
for task, e in PLAN.items():
    src = source_root(task) / e["rel"]
    assert content_sha256(src) == e["sha256"], f"{task}: bytes differ from the verified circuit"
    dst = work / (task if src.is_dir() else f"{task}{src.suffix}")
    (shutil.copytree if src.is_dir() else shutil.copy2)(src, dst)
    print(f"{task:9s} sha256 ok  {e['sha256'][:16]}  cost {e['cost']:.6g}  <- {e['credit']}")

out = Path("/kaggle/working/submission.zip")
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(work.rglob("*")):
        if f.is_file() and not f.name.endswith(".provenance.json"):
            z.write(f, f.relative_to(work).as_posix())
names = zipfile.ZipFile(out).namelist()
assert sum(n.startswith("invsqrt.") for n in names) == 1 and sum(n.startswith("dqi.") for n in names) == 1
assert "dfthcsos/submission.npz" in names and any(n.startswith("dfthcsos/angle_k_0.") for n in names)
shutil.rmtree(work); shutil.rmtree("/kaggle/working/extracted", ignore_errors=True)
print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB, {len(names)} files)")

```

## Credits and licence

All circuits used here come from public notebooks released under Apache-2.0; we did not change their bytes
(the sha256 check above enforces it). Upstream credits, as listed by those notebooks: Dmitrii Gluzdov, Artem
(anazemcev / ViberTeam), Kozykorpesh, Ahmed Berat Özer, Sumit Chongder, Zongao Bian, LightningV08,
Mizero Lucky Gall, Alex Chilton, Kirill Tymchishin, Gu et al. (reversible RS decoder), Guang Hao Low (dfthc
starter kit). This notebook is released under Apache-2.0.

---

## 🔑 Kern-Konzept in 3 Sätzen

Die ANGLE-QROMs dominieren T_total und skalieren mit A = 76 + R·B Zeilen, also lohnt es sich, DF-THC-Faktorisierungen bei kleinerem (R,B) neu zu trainieren. Zwei Beobachtungen machen das erst möglich: (1) Bei kleinem ρ meldet der Trainer einen großen E_gap, der aber nur von den Identity-Offsets W kommt, die gar nicht in error_2 eingehen — W neu zu optimieren (plus Gram-erhaltende C-Rotation) bringt E_gap auf seinen Floor zurück (z. B. 56/54/30: λ_eff 91.6 → 48.7). (2) 10-Bit-Encoding mit progressivem Rounding + exaktem word-level Coordinate Descent kostet nur ~2–3 mHa, und ein gemeinsamer (w,W)-Refit gibt dann das restliche Fehlerbudget (bis 19.94 mHa) für λ_eff aus.

## 📐 Die Zahlen die zählen

| Parameter | Wert | Bedeutung |
|-----------|------|-----------|
| Score (GM) | 11.440 | Reference/cost, eigene Full-Mode-Läufe |
| dfthcsos (best) | EXP-233b: λ_eff 47.426, T 27,616, Q 656, cost 8.592e8 | Ahmeds R24/B60/C30 v3 |
| A (QROM-Zeilen) | 76 + R·B | skaliert T_total |
| 65/60/30 (anazemcev+refit) | λ_eff 47.3704, T 71,958, Q 681 | Ausgangspunkt |
| 48/46/30 (retrained) | λ_eff 48.4455, T 45,314, Q 680 | kleineres (R,B) |
| 32/60/30 (Ahmed) | λ_eff 47.8883, T 36,861, Q 658 | Group-Dropping |
| E_gap-Trick | 56/54/30: λ_eff 91.6 → 48.7 | W-Neuoptimierung + Gram-C-Rotation |
| Rounding-Kosten | ~2–3 mHa (10-bit) | + exaktes Coordinate Descent |
| brot ≤ 7 | Temp-Qubits 543→271, aber e2 66–72 mHa | außerhalb der 20-mHa-Grenze |
| ρ-Abfolge | 1e-4 → 1e-5 → 3e-6 → 1e-6 | λ-Gewicht beim Retraining |

## 📝 Lern-Notizen (füll das selbst aus)

- [ ] DF-THC Factorization verstanden: ...
- [ ] (R,B,C) Tabelle nachvollziehbar: ...
- [ ] Loader-Kosten verstanden: ...
- [ ] λ_eff und was es physikalisch bedeutet: ...
- [ ] Verbindung zu invsqrt/DQI: ...
- [ ] Frage die ich noch habe: ...
