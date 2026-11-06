# DQI T‑Sprint — Report A: Cost Map & Ranked Modifications

**Target:** `work/frontier_scan/mwa_unpacked/dqi.kmb` · sha256 `fc3ba81614e1016f7fbc6c58bc229243fc0c26aa5de601caef7d280e7d14dad9`
**Objective:** reduce mean executed Toffolis **T ≥ 10%** via legitimate circuit improvement.
**Scope rule:** implement a modification only if concretely implementable **and** expected saving > 5% of T. Only `.venv/bin/python` (numpy/scipy/kickmix); read‑only except new files under `work/dqi_t_sprint/`.
**Tag legend:** `[FAKT]` = directly measured from the .kmb or official verifier output · `[HYP]` = reasoned from structure/source, not independently confirmed · `[SPEK]` = estimate/speculation, order‑of‑magnitude only.

---

## 0. Verdict (BLUF)

- **No `.kmb`‑surgery‑only modification reaches the 5% implementation threshold.** Every safe local lever was measured and is either zero or far below 5% (§4, §5).
- The single largest real opportunity is the **forward/inverse asymmetry**: the three `un*` blocks carry **48,863 more Toffolis (12.3%)** than their forward counterparts. Removing it would alone exceed the 10% objective — but it requires **re‑running the private builder core**, which imports ~40 unpublished modules and **cannot be executed here** (`[FAKT]` import barrier, `[SPEK]` saving).
- The circuit is already at the **Q↔T Pareto knee** for its architecture family (`[FAKT]` liveness, `[HYP]` knee claim inherited from `WIDTH_ANALYSIS.md`).
- **Recommendation:** treat Report A as the evidence base for a builder‑level project, not a surgery project. Top‑3 in §7.

---

## 1. Baseline (official verifier) `[FAKT]`

Source: `work/dqi_full/output/summary.json` (block `dqi`, sha matches target).

| field | value |
|---|---|
| status | PASS |
| num_qubits (Q) | **891** |
| toffoli_count (**mean executed T**) | **396,921.516328125** |
| max_toffoli_count (static 3q ops) | **397,194** |
| repetition_factor (R) | **1.1912604648115832** |
| score = R·Q²·T | **375,376,238,975.31** |
| ratio (reference / score) | **65.1066** |
| value_errors / phase_errors | **0 / 0** |
| verified_shots | 102,400 |
| reaction_depth | 5,867 |
| num_ops | 58,336,043 |

Reference numerator (GM basis): `24,439,463,583,672.93`; three‑block GM = `(21.0321 · 65.1066 · 10.6976)^{1/3}` = **24.46794**.

**Mean vs max gap = 272.5 (0.069%).** Decomposed from `shot_operation_counts` over 102,400 shots: mean CCX = 382,384.0 (static 382,647, −263.0/shot), mean CCZ = 1,473.5 (static 1,483, −9.5/shot), CSWAP = 13,064.0 (exact). The gap is shot‑dependent skipping of 3q gates whose controls are `|0⟩` on a given classically‑drawn error pattern — **not** conditional gates. There are **zero** `CCX_IF/CCZ_IF/CSWAP_IF` in the file (`[FAKT]`, full type census below). Reducing static 3q ops therefore reduces scored T ~1:1.

### Full op‑type census `[FAKT]`
```
0x31 CCX          382,647     0x21 CX        51,928,496     0xa1 CX_IF       237,752
0x30 CCZ            1,483     0x20 CZ            3,325     0xa0 CZ_IF       809,366
0x32 CSWAP         13,064     0x22 SWAP      1,583,742     0xc2 BIT_INVERT_IF 2,818,196
0x50 HMR           79,399     0x11 X          250,314     0x90 Z_IF          44,771
0x12 R             55,876     0x40 BIT_STORE0  108,872     0x06 INFO_TAG     17,876
0x01 ?                 56     0x10 Z                198     0x80/0x81 cond-stack  554/56
```
Conditional **3q** ops: **0**. All 397,194 Toffolis are unconditional.

---

## 2. Cost map: block → Toffoli → source

Block boundaries and per‑block 3q counts from `block_analysis.json` (tree‑based INFO_TAG attribution; roots match the task's top‑level figures exactly). `%` is of static T = 397,194.

| block | stream frac | static Toffolis (n3) | % T | CCX / CCZ / CSWAP | root (untagged) | sub‑tags |
|---|---|---:|---:|---|---:|---|
| extract | 0.045–0.113 | **59,595** | 15.0% | 59,403 / 0 / 192 | 53,361 | inverse24 ×29, multiply v ×12, inverse12 ×2 |
| synthesis | 0.113–0.206 | **31,637** | 8.0% | 31,613 / 0 / 24 | 31,521 | inverse12 ×2 |
| convert | 0.206–0.304 | **60,796** | 15.3% | 55,947 / 0 / 4,849 | 54,330 | aligned_route ×26, inverse12 ×49, full_head_product ×3 |
| scan | 0.304–0.706 | **44,275** | 11.1% | 44,275 / 0 / 0 | 44,275 | gf_iadd ×8,050 (n3=0) |
| unconvert | 0.706–0.796 | **62,711** | 15.8% | 56,669 / 256 / 5,786 | 55,831 | aligned_route ×26, inverse12 ×49, full_head_product ×3, head_pivot ×24, head_phase ×3 |
| unsynthesis | 0.796–0.894 | **40,556** | 10.2% | 40,260 / 272 / 24 | 38,468 | inverse12 ×36 |
| unextract | 0.894–0.994 | **97,624** | **24.6%** | 94,480 / 955 / 2,189 | 97,508 | inverse12 ×2, gf_iadd ×186 |
| initial / uninitial / mask_projection / restore_masks | — | 0 | 0% | — | — | (CX/CZ/X only) |
| **total** | | **397,194** | 100% | 382,647 / 1,483 / 13,064 | 375,294 | 21,900 |

Root (untagged core) = 375,294 (94.5%); sub‑tags = 21,900 (5.5%).

### Source attribution `[HYP]` (tag→file; the builder emits INFO_TAG strings from a private base, so file mapping is inferred from the public deltas in `work/dqi_sources/`)

| block / sub‑tag | inferred source construct | delta files referencing it |
|---|---|---|
| extract | `exp.decoder.extract` (forward extraction) | companion.py, audit.py, nonzero_consume16.py, direct_forney.py |
| synthesis | `exp.decoder.synthesis` | synthesis_noflag.py, norm_deferred_flag_return.py |
| convert / unconvert | `convert_safe(b,A,B,reverse=…)` | conversion.py, direct_converter.py, convert.py |
| ├ aligned_route, head_pivot | converter routing/pivot helpers | direct_converter.py |
| ├ full_head_product, head_phase | head product/phase schedules | (private base) |
| scan | Forney scan loop, `gf2_iadd` + `root_character` | direct_forney.py (`scan`, `root_character`) |
| inverse12 (products/scalar/norm) | `phase_inverse12_quantum64` (exp.jet24.kernel) | direct_forney.py, division.py, inverse20.py, local_norm.py, lowwidth.py, narrow_gauge.py |
| inverse24 (products/scalar/norm) | 24‑bit inverse tower | division.py, inverse20.py |
| multiply v | field multiply (classical‑conditioned CX, Toffoli‑free) | direct_forney.py (`classical_product`) |

Note: `direct_forney.py` is a *candidate* delta that fuses convert+scan+unconvert into one Forney phase; the shipped circuit retains the separate convert/scan/unconvert blocks, so it is **not** the generator of the current stream (`[HYP]`).

---

## 3. Structural findings

### 3.1 Forward / backward asymmetry — the headline `[FAKT]` numbers, `[HYP]` cause
Forward half (extract+synthesis+convert+scan) = **196,303** (49.4%). Backward half (unconvert+unsynthesis+unextract) = **200,891** (50.6%). `scan` (44,275) has no inverse counterpart and is excluded from the pairing below. Matched pairs:

| pair | forward | inverse | inverse overhead | % over own forward |
|---|---:|---:|---:|---:|
| extract → unextract | 59,595 | 97,624 | **+38,029** | +63.8% |
| synthesis → unsynthesis | 31,637 | 40,556 | **+8,919** | +28.2% |
| convert → unconvert | 60,796 | 62,711 | **+1,915** | +3.2% |
| **matched total** | 152,028 | 200,891 | **+48,863** | **+32.1%** (= 12.3% of all T) |

`mirror_compare.json`: the `un*` blocks are **not** reverse replays of their forwards (0% prefix match; e.g. extract↔unextract fwd=59,595 vs rev=97,624, match=0). `[HYP]` cause: working qubits are **reused** between the forward and inverse halves, so the inverse cannot simply replay the forward in reverse — it must **recompute** intermediates to drive the 840 syndrome qubits back to `|0⟩` while emitting the MBUC phase p(s). This is dirty‑ancilla uncompute overhead.

### 3.2 Pebbling dominates the CCX pool `[FAKT]`
From `pebbling.py` (CCX classified by target freshness):

| category | CCX count | % of CCX (382,647) |
|---|---:|---:|
| pebbled (`peb_ccx`, recomputed rather than held) | **267,210** | **69.8%** |
| single compute then reset | 114,967 | 30.0% |
| single, no reset | 270 | 0.07% |

Per block `peb_ccx`: extract 40,090 · unextract 67,046 · convert 59,036 · synthesis 45,488 · unconvert 34,154 · unsynthesis 21,396 · scan 0 (scan is all single‑then‑reset). Pebbling trades extra Toffolis for width; Q is fixed at 891 so the builder chose it to fit the width budget.

### 3.3 Width is at the Pareto knee `[FAKT]` liveness, `[HYP]` knee
Inherited from `WIDTH_ANALYSIS.md` (older 892Q sibling, same architecture): peak concurrent live qubits = declared Q under **three independent liveness models**; 30 passive‑holder working qubits are parked untouched for 48–49M ops (75% of the stream) while 10 churners cycle as scan scratch. Field evidence: "fewer working qubits ⇔ more Toffolis" (hengck23's 889Q decoder scored worse on higher T). `[HYP]` the 891Q circuit sits at the same knee.

### 3.4 Local cancellation scan = 0 `[FAKT]`
`cancel_scan.py` / `cancel_scan2.py`:
- **Lever A** — strictly adjacent identical 3q gates (self‑inverse ⇒ `g g = I`): **0 pairs**.
- **Lever A2** — commuting‑separated identical 3q gates (cancel iff no intervening op touches any of the 3 qubits): checked **all 187,696** consecutive same‑signature pairs with gap ≤ 2,000 ops → **0 cancellable**. Gap histogram: ≤50: 32,767 · ≤100: 68,196 · ≤500: 146,953 · ≤2000: 187,696 · ≤100k: 285,914 (of 302,972 total consecutive same‑sig pairs). The dense wiring (~65k ops/qubit) plus the fact that a pebbled intermediate's "use" always touches its target makes clean intervals measure zero.
- **Conclusion:** the builder emits no locally redundant 3q gates. There is nothing free at the surgery level.

### 3.5 Outcome‑independence + basis‑state contract `[FAKT]`
Verifier inputs are always **basis states** (classically drawn error patterns). Mid‑circuit HMR/R is therefore legal, but kickmix HMR/R is **X‑basis** (random outcome, phase += q·outcome) so syndrome values **cannot** be copied to classical memory — the `un*` blocks are required for *coherent* syndrome restoration (the "delete `un*`, restore classically" plan is dead). Circuit is **outcome‑independent**: 0 phase mismatches across 4 sim seeds × 256 shots (`test_independence.py`). `CZ_IF` (809,366) never conditions on E‑register bits, consistent with MBUC phase p(s) carried by outcome‑controlled corrections.

### 3.6 Repeated‑signature ceiling (loose) `[FAKT]` ceiling, `[SPEK]` realization
Distinct 3q signatures: **94,222**; appearing ≥2×: 40,498; max multiplicity 2,013. Naive repeat ceiling `Σ(count−1)` = **302,972** (76.3% of T). This is dominated by **loop repetition** (the same working‑qubit gate re‑issued per syndrome register / scan point on *different* data), so it is **not** a caching bound. Realizable product‑caching is limited by *free wires*, not repeats — prior art (busyaprime, older 892Q) found only **2,787 Toffolis (0.62%)** via symbolic wire‑function hashing (`[FAKT]` on old circuit, `[SPEK]` on current).

---

## 4. Ranked modifications with arithmetic

Score sensitivity: ratio ∝ 1/T, GM ∝ ratio^{1/3}. Base ratio 65.1066, GM 24.46794.

| # | lever | ΔT (Toffolis) | % of T | ratio → | GM → | ΔGM | feasible by | tag |
|---|---|---:|---:|---:|---:|---:|---|---|
| 1 | **Remove inverse overhead** (make `un*` as cheap as forward) | −48,863 | **−12.3%** | 74.22 | 25.56 | **+1.09** | builder re‑run | `[SPEK]` |
| 2 | **De‑pebble** onto temporally‑free wires (pool = 267,210 peb_ccx) | −? (realizable fraction unknown) | up to −67% pool | — | — | — | builder re‑schedule | `[SPEK]` |
| 3 | **Product caching** (free‑wire AND reuse) | −~2,787 (prior art) | **−0.70%** | 65.56 | 24.50 | +0.03 | `.kmb` surgery | `[FAKT]`‑old / `[SPEK]`‑cur |
| 4 | **Local cancellation** (A + A2) | −0 | 0% | — | — | — | `.kmb` surgery | `[FAKT]` = 0 |
| 5 | **Q reduction**, late‑start trio 889/890/891 | ~0 (ΔT≈0) | 0% | 65.20 (via Q′=889) | 24.52 | +0.05 | `.kmb` surgery | `[SPEK]`, off‑objective (Q not T) |

Worked arithmetic (row 1): removing the full 48,863 excess (≈12.30% of static, ~1:1 on scored mean) ⇒ T′ ≈ 396,921.5 − 48,827 = 348,094 → ratio = 65.1066·(396,921.5/348,094) = 74.22 → GM = 24.46794·(74.22/65.1066)^{1/3} = 24.46794·1.0446 = **25.56**. (This is a *ceiling*: it assumes the inverse becomes exactly as cheap as the forward; some inverse work is irreducible.)
Row 3: T′ = 396,921.5−2,787 = 394,134.5 → ratio 65.56 → GM 24.50.
Reference thresholds: **−5% T** ⇒ GM +0.42 (24.89); **−10% T** ⇒ GM +0.87 (25.34).

**Only row 1 clears the 10% objective and row 1 is the only row that clears 5%; none of rows 3–5 clear 5%.** Row 2 could clear 10% *if* a large fraction of the 267k pebbled CCX were de‑pebbleable, but the realizable fraction is unknown and the work is a builder re‑schedule.

---

## 5. Why no surgery‑only lever reaches 5%

1. **Local redundancy is exactly zero** (`[FAKT]` §3.4): no adjacent or commuting‑separated identical 3q gates to delete.
2. **Caching is wire‑limited, not repeat‑limited** (`[FAKT]` §3.6 + prior art): the 302,972 repeat ceiling is loop artefact; realizable ≈ 0.7%.
3. **The big pools (inverse overhead 48,863; pebbling 267,210) are architectural**, produced by the private builder's uncompute/pebbling scheduler. Editing them means re‑wiring tens of thousands of gates with global lifetime constraints — i.e. re‑implementing the builder, which **cannot run here** (`[FAKT]`: the 25 `dqi_sources/*.py` deltas import ~40 unpublished modules such as `exp.decoder.*`, `exp.jet24.kernel`, `converter`, `mh`).
4. **Width is the binding constraint** (`[FAKT]` liveness): de‑pebbling needs free wires; at the peak all 52 working values coexist, and freeing any of them costs ≥ its producing ladder in Toffolis (break‑even ≈ 893 Toffoli/qubit, `WIDTH_ANALYSIS.md` §7) — net‑negative except the tiny Q‑only trio play (row 5).

---

## 6. Verification evidence index

| claim | evidence | tag |
|---|---|---|
| Baseline T/Q/R/ratio/errors | `work/dqi_full/output/summary.json` (sha `fc3ba816…`) | `[FAKT]` |
| Op census, 0 conditional 3q | type histogram over `rd.types` | `[FAKT]` |
| Block n3 / roots / subs | `block_analysis.json` (tree INFO_TAG attribution) | `[FAKT]` |
| Inverse overhead 48,863 | block n3 differences | `[FAKT]` |
| Pebbling 267,210 (69.8% CCX) | `pebbling.json` | `[FAKT]` |
| `un*` ≠ reverse(forward) | `mirror_compare.json` (match=0) | `[FAKT]` |
| Adjacent / commuting cancellation = 0 | `cancel_scan.py`, `cancel_scan2.py` | `[FAKT]` |
| Repeat ceiling 302,972 (loose) | `cancel_scan.py` | `[FAKT]` |
| Outcome‑independence (0 mismatch, 4 seeds×256) | `test_independence.py` | `[FAKT]` |
| Basis‑state contract, HMR X‑basis | `sim.h`, verifier input model | `[FAKT]` |
| Product caching ≈ 2,787 (0.62%) | busyaprime notebook (older 892Q) | `[FAKT]`‑old / `[SPEK]`‑cur |
| Width at Pareto knee | `WIDTH_ANALYSIS.md` (older 892Q sibling) | `[HYP]` |
| Inverse‑overhead cause = dirty‑ancilla uncompute | structural reasoning | `[HYP]` |
| Row 1/2 savings magnitudes | arithmetic on `[FAKT]` pools | `[SPEK]` |

No modification was implemented (none met the >5% + concretely‑implementable bar), so no *new* circuit claim is made; all circuit claims above cite the existing official verifier JSON or direct .kmb measurement.

---

## 7. Top‑3 recommendations

1. **(Builder‑level, highest value) Attack the inverse overhead (−48,863 T, −12.3%, +1.08 GM).** Make `unextract`/`unsynthesis` uncompute by *reversing* the forward computation on retained (not reused) intermediates, or share the forward's pebble tree with the inverse. This is the only lever that clears the 10% objective. Requires the private builder core (`exp.decoder.*`, `exp.jet24.kernel`) — out of reach for `.kmb` surgery here. **Action:** stand up the builder in an environment that has the unpublished modules; prototype a "retained‑intermediate uncompute" for `unextract` first (largest single gap, +38,029).
2. **(Builder‑level) De‑pebble against the width slack.** 267,210 CCX (69.8%) are pebbled. Re‑run the pebbling scheduler to hold intermediates on the 30 passive‑holder wires during their long idle spans instead of recomputing. Realizable fraction unknown — needs a lifetime/width co‑optimization pass in the builder. **Action:** instrument the builder to report, per pebbled AND, the free‑wire span available; de‑pebble whenever span ≥ lifetime.
3. **(Surgery‑level, small but concrete) Product caching on free wires (~−2,787 T, −0.7%).** Below the 5% bar alone, but it is the only lever implementable purely at `.kmb` level and could be banked as a verified increment while the builder work proceeds. **Action:** symbolic eval‑vector pass (random 0/1 point evaluations per wire) to find repeated CCX control‑pair products with a provably idle copy wire; emit a `.kmb` writer/surgery tool; verify with the official verifier (`--num-shots 256` quick check for value/phase errors, then 102,400 for final JSON).

**Bottom line:** the cost is architectural, not local. Surgery finds nothing ≥5%; the ≥10% target lives in the builder's uncompute + pebbling decisions.
