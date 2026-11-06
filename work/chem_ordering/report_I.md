# Report I — Strategy 4: similarity-sorted reordering of the 143 THC leaf indices

**VERDICT: DEAD.** A similarity-sorted ordering does **not** beat the shipped ordering and does **not** clear the 7,875-content-CCX scrambled-attractor gate. Under the best available compiler (mrmeows `rank_parity`, J5/lb5 — the config matching mwa2's 128 Q cap), **every** tested similarity ordering (NN-TSP multi-seed + 2-opt, popcount sort, value sort, Gray-code sort, leading-bit-run sort) compiles to **exactly the same cost as a random permutation** (content 7,875 / static 9,735), i.e. **+550 static CCX worse than shipped** (content 7,325 / static 9,185). Confirmed at the **real-circuit level** (kickmix builds, symbolic oracle PASS on all 45 loaders). The best ordering is **SHIPPED (identity)** → total Toffolis unchanged at **15,585** (mwa2 real) → **ΔGM = 0** vs the current 10.6976× chemistry ratio. Strategy 4 adds nothing over Subagent C's random/structured permutations.

Date: 2026-11-03 · Subagent I · Repo: `/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum`
Tested artifact: `work/frontier_scan/mwa2_unpacked/dfthcsos/` (npz sha f5783ebc, somejoint "ladder" release; submission sha d8c21eeb)
Compiler: mrmeows `rank_parity` (`sota_mrmeows/sources/dfthcsos_8p5558_complete_with_compiler/.../compiler/`) — the only local compiler. mwa2's actual manwithacat/somejoint compiler is **not** in the repo (searched `work/`, `sota_mrmeows/`).

---

## 1. Row-table extraction — confirms C [FAKT]

Loaded `submission.npz`; schema identical to C's §2:

| key | shape | role |
|---|---|---|
| `angle_words` | (1363, 75) i64 | 76 one-body rows + 9·143 two-body rows in (ρ,b) order; 8-bit words |
| `W` | (9, 143, 39) f64 | lowercase weights; b-axis = the 143 leaf index |
| `U` | (9, 143, 76) f64 | exact two-body vectors (diagnostic) |
| `tree_edges` | (75, 2) i64 | Givens tree |
| `brot` | () i64 | 8 |

D = 1363 = N(76) + R(9)·B(143). Loader structure (C §3): 15 circuits × J=5 angles × 8 bits; loader *k* compiles the delta table `words[:,5k:5k+5] ⊕ words[:,5k−5:5k]` over D addresses (n_sel=11 bits).

**Calibration check (must match C):** running C's exact pipeline (`canonical_gauge → delta_batch(J=5) → coefficients(brot=8, lb=5) → zero_invalid → plan_zeroed`) on the **shipped** ordering reproduces C's numbers bit-for-bit: **static CCX = 9,185 (content 7,325 + fixed 1,860)**, kernels_sum = 470. A single random permutation reproduces C's scrambled attractor **exactly**: content 7,875 / static 9,735. [FAKT]

Config: D=1363, A=43 high blocks, B=32 low, n_sel=11, cache=62, fixed CCX/loader=124, q_circuit=124 (≤128 cap). [FAKT]

## 2. Candidate orderings generated

The permutation π acts on the b-axis **consistently across all R=9 ρ-blocks** (row `N+ρ·B+b → N+ρ·B+π[b]`); one-body rows 0..75 untouched. Gauge-invariant per C's proof.

Similarity distance used for NN-TSP: aggregate Hamming distance between leaf signatures, computed on the **encoded (gauged) bits** — each leaf *b* has signature = its R=9 rows × 75 words × 8 bits = 5,400 bits; `d(b,b′)=Σ_{ρ,word,bit} XOR`. Mean off-diagonal = 2,679.65 / 5,400 bits (min 0, max 2,844). [FAKT]

| # | candidate | construction | adjacency path length (Σ d of consecutive leaves) |
|---|---|---|---|
| c | **shipped** (baseline) | identity | 379,086 |
| r | random_ref | `default_rng(20261103).permutation(143)` (C's seed) | 380,921 |
| a | **NN-TSP** | nearest-neighbour PATH from all 143 seeds + 4 passes 2-opt | **365,016** (raw NN 365,259) |
| b1 | sort_popcount | argsort by total bit-count of full 9-block signature | — |
| b2 | sort_popcount_r0 | argsort by bit-count of ρ=0 block | — |
| b3 | sort_value_r0 | argsort by integer value of ρ=0 signature (first 64 bits) | — |
| b4 | sort_gray_r0 | argsort by Gray code of that value | — |
| b5 | sort_leadbit_run | argsort by (highest set-bit position, then value) of ρ=0 | — |

Key point: the NN-TSP ordering is a **genuinely better** adjacency ordering than shipped (path length 365,016 < 379,086, ~3.7% shorter; below the random baseline 380,510). So the hypothesis is tested at its strongest — a real similarity improvement — not a degenerate one. [FAKT]

## 3. Compiled-cost comparison [FAKT real builds + PROXY]

Static CCX per loader = `transformed_paired_products` (content) + 124 (fixed cache). Counted Toffoli = 2× static (forward+reverse). The plan-only proxy was **validated against real kickmix builds** for the three representative orderings (all 45 loaders, symbolic oracle PASS): proxy static == native build Toffoli exactly. [FAKT]

| ordering | type | content CCX | static CCX | native Toffoli (real build) | counted T (2×) | Δstatic vs shipped | clears 7,875 gate? | beats shipped? |
|---|---|---|---|---|---|---|---|---|
| **shipped** | baseline | **7,325** | **9,185** | **9,185** | 18,370 | — | n/a | n/a (it IS shipped) |
| random_ref | scramble | 7,875 | 9,735 | — | 19,470 | **+550** | NO (= gate) | NO |
| **NN-TSP** | similarity | 7,875 | 9,735 | **9,735** | 19,470 | **+550** | NO (= gate) | NO |
| sort_popcount | similarity | 7,875 | 9,735 | **9,735** | 19,470 | **+550** | NO (= gate) | NO |
| sort_popcount_r0 | similarity | 7,875 | 9,735 | — | 19,470 | +550 | NO | NO |
| sort_value_r0 | similarity | 7,875 | 9,735 | — | 19,470 | +550 | NO | NO |
| sort_gray_r0 | similarity | 7,875 | 9,735 | — | 19,470 | +550 | NO | NO |
| sort_leadbit_run | similarity | 7,875 | 9,735 | — | 19,470 | +550 | NO | NO |

Per-loader content CCX (the mechanism):

| ordering | loaders k0–k3 | loaders k4–k14 | kernels found (sum) |
|---|---|---|---|
| shipped | 525 each | **475 each** (−50 discount × 11) | 470 |
| every other (NN-TSP, sorts, random) | 525 each | 525 each (uniform) | 524–525 |

**The shipped ordering is the only one where the compiler finds nullspace kernels that drop 11 of 15 loaders from 525 → 475 content CCX (−550 total).** Every non-shipped permutation — random *or* similarity-sorted — collapses to the uniform 525 attractor. Notably the permutations find *more* kernels (524–525 vs 470) yet cost more: the heuristic discovers relations on scrambled tables but cannot factor them into a cheaper basis (C §4.2, reproduced here). [FAKT]

### Calibration caveat (absolute numbers) [FAKT + HYP]
mrmeows angle-static for shipped = 9,185 ≈ **2.06×** mwa2's measured 4,466 (verify_baseline.json: `angles_toffoli_per_pass=4466`, `angles_toffoli=8932`). mwa2's loaders were compiled with a better (absent) compiler. **Absolute costs are not transferable; the relative ranking within mrmeows is valid** (C §4, reproduced). Any cross-compiler extrapolation below is tagged [HYP].

## 4. Gauge invariance of the tested orderings [FAKT]

Ran the verifier's own metric function (`evaluate_dfthc_angle_words`) on the NN-TSP / random / popcount-permuted word tables with consistently permuted weights. Max |Δ| vs baseline per metric:

| ordering | error_1 | error_2 | Lambda | E_SOS | E_gap | λ_eff |
|---|---|---|---|---|---|---|
| nn_tsp | +3.1e-16 | −3.5e-18 | +5.7e-14 | 0 (exact) | 0 (exact) | +7.1e-15 |
| random_ref | +9.1e-16 | −6.9e-18 | +5.7e-14 | 0 (exact) | 0 (exact) | +7.1e-15 |
| sort_popcount | +4.7e-16 | +3.5e-18 | +5.7e-14 | 0 (exact) | 0 (exact) | +7.1e-15 |

Baseline: error_1=10.27047 mHa, error_2=19.99965 mHa, λ_eff=47.025649827374934, E_gap=3.9148992 — all within C's float-noise bound (≤6e-14 Ha). **No hidden metric regression** in any candidate; the gauge symmetry (C §1) holds for Strategy-4 orderings too. [FAKT]

## 5. GM arithmetic [HYP for cross-compiler scale]

Best ordering = **shipped** → it is the current submission → **no change**.

- Best ordering total Toffolis (mwa2 real): **15,585** (angles 8,932 + heuristic 6,653), Q=428, λ_eff=47.0256, score 313,678,954.0955, chemistry ratio **10.6976×**.
- **ΔGM vs 10.6976×: 0.** There is no ordering that improves on shipped, so nothing to gain.

Counterfactual — if a similarity sort were (wrongly) adopted, scaled to mwa2-real terms assuming proportional cross-compiler behaviour [HYP]:
- Δangle-static (mrmeows) = +550 (+5.988%) → mwa2-scaled ≈ +267 static / **+535 counted** angle Toffoli.
- Chemistry T_total: 15,585 → 16,120 (**+3.43%**); Q pinned at 428 (angles at 128 cap, no pebbling room — C §5); λ_eff gauge-invariant (§4).
- Chemistry ratio: 10.6976 / 1.0343 = **≈10.34×** (−3.3%).
- Portfolio GM (C's calibration: 1% chemistry-T ↔ 0.33% GM): **≈ −1.1% GM.**

So the similarity route has **expected value ≤ 0** (realistically negative), identical in kind to C's random permutations. [HYP]

## 6. Why the hypothesis fails here [SPEK]

The hypothesis ("adjacent rows differ in few bits → fewer gates") describes a **naive sequential-delta QROM**. The actual mrmeows compiler costs are driven by the **rank of the H×L ANF tensor** after nullspace-kernel search, not by raw address adjacency. Making consecutive leaves similar (NN-TSP path 365,016 < shipped 379,086) does not lower those tensor ranks — it merely reshuffles which generic-rank pattern appears, landing on the same uniform 525 attractor as any scramble. The shipped ordering's advantage is a **co-design artifact**: its specific leaf layout lets the kernel search factor 11 loaders down to rank giving 475 content CCX. That structure is destroyed by *any* reordering, similarity or not. Beating it would require solving mwa2 authors' original word+weight+circuit co-design problem better — not re-sorting their shipped rows.

## 7. Recommendation: ABANDON Strategy 4 [SPEK]

- Keep the shipped ordering. Do not submit any reordered variant.
- Consistent with C: random, structured, **and now similarity-sorted** permutations are all dead (all ≥ the 7,875 attractor, all +550 static CCX vs shipped under the best available compiler).
- Residual value: confirms the gauge orbit's cost floor is set by the co-design, not by adjacency; the 7,875 attractor remains the correct "not worth compiling" gate (C §6.3).

## 8. Reproduction

```bash
cd /Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum
# candidate orderings + proxy cost table (~12 s):
.venv/bin/python work/chem_ordering/ordering_test.py
# real kickmix builds for shipped / NN-TSP / popcount (~8 s, symbolic oracle PASS):
.venv/bin/python work/chem_ordering/build_confirm.py
# gauge invariance of the tested orderings (~8 s):
.venv/bin/python work/chem_ordering/gauge_check.py
```

Artifacts: `work/chem_ordering/{ordering_results.json, build_confirm_results.json, gauge_check_results.json}`.
