# DQI Shadow Builder — Status Report

**Date:** 2026-11-04
**Scope:** Foundation establishment + first tower-field port step (assessed, not executed)
**Repo:** `/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum`

---

## (a) True Baseline @ 102,400 shots

| metric | value |
|---|---:|
| status | **PASS** |
| value_errors / phase_errors | **0 / 0** |
| R (repetition_factor) | **1.19126** |
| Q (num_qubits) | **1,893** |
| T_mean (toffoli_count) | **5,725,109.3** |
| T_static (max_toffoli_count) | **5,725,461** |
| score = R·Q²·T_mean | **24,439,467,666,108** |
| ratio (reference/score) | **≈ 1.000** |
| reaction_depth | 170,757 |
| num_ops | 86,051,014 |
| circuit_sha256 | `5dfb9991…e9f98f` |

Reference numerator: 24,439,463,583,673 (Report A §1). Ratio is essentially 1.0 —
the reference decoder IS the competition baseline. `fc3ba816` achieves ratio 65.1
by reducing score to 375,376,238,975 (Q=891, T=396,922).

Gap decomposition: `(1893/891)² × (5,725,109/396,922) = 4.49 × 14.42 = 64.8 ≈ 65.1` ✓

Artifacts: `work/dqi_shadow/baseline_102k.json`, `run_baseline_102k.py`

---

## (b) Reference Structure Map Summary

**Total distinct GF(2¹²) arithmetic call sites in source: 14** (across 7 source locations)
**Total non-linear call sites (Toffoli-costly): 4 types**

| op type | source lines | stage(s) | calls in circuit | T/call | total T | % static |
|---|---|---|---:|---:|---:|---:|
| `ixor_gf2_mul` (controlled) | 351, 362 | Fwd+Rev EEA | 31,524 | 75 | 2,364,300 | 41.3% |
| `init_gf2_inverse_with_scaffold` | 579 | Chien/Forney | 4,095 | 315 | 1,289,925 | 22.5% |
| `init_gf2_div_with_scaffold` | 302 | Fwd+Rev EEA | 888 | 378 | 335,664 | 5.9% |
| `gf2_phase_by_product` | 583 | Chien/Forney | 4,095 | **0** | 0 | 0% |
| **non-linear total** | | | | | **3,989,889** | **69.7%** |
| control logic + integer arith | various | all | — | — | 1,735,572 | 30.3% |

Key findings:
- `gf2_phase_by_product` is **CZ-only** (0 Toffolis) — no port needed
- `gf2_imul`/`gf2_iadd`/`gf2_idiv` (by constant) are all **linear** (0 Toffolis)
- The only Toffoli-costly ops are: controlled mul, inverse, and division
- Full map: `work/dqi_shadow/reference_map.md`

---

## (c) First Port Step Result

**Target:** `ixor_gf2_mul` (highest-frequency mul site, lines 351/362)
**Verdict: NOT BENEFICIAL — port not executed.**

### Why

1. **Control overhead kills the advantage.** The tower Karatsuba decomposition
   (GF(2¹²)=GF(64)[z]/(z²+z+β)) requires 54 AND-pairs uncontrolled. With the
   `control=mul` qubit, each AND becomes a 4C-X gate costing 3–6 Toffolis:
   - Optimistic (shared ancilla pool): 54 × 3 = 162T
   - Pessimistic (1 ancilla per term): 54 × 6 = 324T
   - Current kickmix: **75T** ← already near-optimal

2. **Kickmix's 63T uncontrolled mul is close to the Boolean-rank lower bound** (~60 for m=12). No decomposition strategy beats it significantly.

3. **Representation mismatch:** `division.py` uses 24-qubit GF(2²⁴) registers;
   the reference decoder uses 12-qubit GF(2¹²) standard basis.

4. **Missing source:** `mul24_xor105` (the actual 105T schedule) is in the absent
   `field` module. Only the 126T comparison variant is visible.

### Redirected target (port step 2)

**`init_gf2_inverse_with_scaffold`** (315T × 4,095 calls = 22.5% of static T):
- Tower Itoh-Tsujii in GF(64) sub-field: ~5–7 GF(64) muls ≈ 90–126T
- No variable-qubit control (inside `push_condition` = classical condition)
- Expected saving: **~700K–1M Toffolis** (52–68% per call)

Artifacts: `work/dqi_shadow/port_step1.json`, `port_step1.md`

---

## (d) Next 3 Port Steps (priority order)

| step | target | current cost | tower estimate | calls | ΔT potential | effort |
|---|---|---:|---:|---:|---:|---|
| **2** | `init_gf2_inverse_with_scaffold` | 315T | ~100–150T | 4,095 | −700K to −1M T | 3–5 days |
| **3** | `init_gf2_div_with_scaffold` | 378T | ~200T | 888 | −157K T | 2–3 days |
| **4** | Basic pebbling pass (reduce Q) | Q=1893 | Q≈1200–1500 | — | ratio ×1.5–2.5 | 5–10 days |

Step 2 details:
- Implement GF(64) mul_xor (18 AND-pairs, Karatsuba) using kickmix `ccx`
- Implement GF(64) Itoh-Tsujii inverse: a⁶² = ((a³)⁴·a³)⁴·a² (3 muls + free squarings)
- Compose GF(2¹²) inverse via tower: (a+bz)⁻¹ = (a-bz)/(a²+b²z+a²β) [quadratic extension]
- Handle `push_condition` classical conditioning (no extra Toffoli overhead expected)
- Validate: 256-shot gate → 102,400-shot score

Step 3: division = multiply-by-inverse, reuses step 2's inverse kernel.

Step 4: lifetime analysis of ancilla registers; greedy wire-reuse scheduling.
This is where the 4.49× Q gap starts to close (1893 → ~1200).

---

## (e) Honest Assessment: Distance to Ratio ~5–15

**Current: ratio ≈ 1.0. Target: 5–15. Gap: 5–15×.**

Score = R · Q² · T. With R≈1.19 fixed (0 errors), need Q²·T to drop 5–15×.

| scenario | Q | T | Q²·T factor | ratio |
|---|---:|---:|---:|---:|
| baseline (now) | 1,893 | 5,725,109 | 2.05e13 | 1.0 |
| after steps 2+3 (tower inv+div) | 1,893 | ~4,600,000 | 1.64e13 | 1.25 |
| after step 4 (pebbling, Q→1400) | 1,400 | ~4,600,000 | 9.0e12 | 2.7 |
| aggressive pebbling (Q→1100) | 1,100 | ~4,200,000 | 5.1e12 | 4.8 |
| + algorithmic improvements (better EEA) | 1,100 | ~3,000,000 | 3.6e12 | 6.8 |
| + full width optimization (Q→900) | 900 | ~2,500,000 | 2.0e12 | 12.2 |

**Assessment:**
- **Ratio 5:** achievable with steps 2–4 + moderate pebbling. ~15–25 person-days. `[SPEK]`
- **Ratio 10:** requires aggressive width optimization (Q→~1000) + algorithmic changes. ~30–45 person-days. `[SPEK]`
- **Ratio 15:** approaches fc3ba816's architecture territory (extract/synthesis/convert/scan instead of synchronized EEA). Likely needs a different algorithm entirely. >45 person-days. `[SPEK]`
- **Ratio 65 (parity):** infeasible solo in 78 days (confirmed by Report H).

The shadow decoder's synchronized EEA architecture is fundamentally different from
fc3ba816's extract/synthesis/convert/scan pipeline. Even with perfect tower-field
arithmetic + optimal pebbling, the algorithmic ceiling of the EEA approach is
likely ratio ~10–20 (not 65). Reaching ratio 15+ may require switching to the
fc3ba816 algorithm structure, which is locked in the private base.

---

## (f) Top Risks

| # | risk | impact | likelihood | mitigation |
|---|---|---|---|---|
| 1 | **Width/pebbling scheduler** is the binding constraint for ratio >5; not visible in any public code | caps ratio at ~3–5 without it | HIGH | Basic greedy pebbling (step 4); accept lower ratio ceiling |
| 2 | Tower-field inverse implementation has subtle phase/basis bugs that only appear at 102,400 shots | wasted days debugging | MEDIUM | Exhaustive classical test on GF(64) before quantum port; 256-shot gate first |
| 3 | Shadow decoder's EEA architecture has a lower ratio ceiling than fc3ba816's extract/scan pipeline | can't reach ratio 15 even with perfect arithmetic | MEDIUM | Document ceiling early; pivot to algorithm change if needed |
| 4 | Merge with somejoint succeeds → shadow decoder work becomes leverage-only (not primary path) | effort redirected | LOW (positive) | Keep shadow decoder as artifact + negotiation asset regardless |
| 5 | 78-day window: merge decision point Nov 15–20; if merge fails, only ~60 days remain for solo track | compressed timeline | MEDIUM | Front-load steps 2–3 (inverse/div port) in first 2 weeks |

---

## File Index

```
work/dqi_shadow/
├── STATUS.md              ← this file
├── baseline_102k.json     ← Task 1: true baseline verifier output
├── baseline_102k_raw.json ← raw verifier stdout (failed run, memory issue)
├── baseline_102k_run.log  ← successful run log
├── run_baseline_102k.py   ← baseline script (patches _circuit_sha256 memory issue)
├── reference_map.md       ← Task 2: complete arithmetic call-site inventory
├── port_step1.json        ← Task 3: mul port assessment (NOT_BENEFICIAL)
├── port_step1.md          ← Task 3: detailed analysis + redirect to inverse
└── levers/
    └── README.md          ← Task 4: lever-measurement harness plan
```
