# Report B — invsqrt "tol−c pinning": mechanism, evidence, and how to grow c

Scope: Benchmark I (`invsqrt.kmb`, sha `e4ed188b…`, Q=62, C=1,589.26, cost 98,533.87, ratio 21.0768×).
Method: full-domain (3,133,452 x-values, 1 shot/x, seed 0) phase extraction from the kickmix simulator,
exact integer/Fraction arithmetic, and an independent reconstruction of the angle-refit LP.
All new files live under `work/p0_reports/` (scripts `step1…step10`, data in `work/p0_reports/data/`).
Tags: [FAKT] = measured/proven here or in cited public sources · [HYP] = plausible, needs build · [SPEK] = speculative.

---

## TL;DR

1. **tol(x) has a closed form:** `tol(x) = isqrt(2^80 // x) = floor(2^40/sqrt(x))` in units of 2⁻⁶⁴ turns, *exactly* for every legal x (proved §1, verified full-domain).
2. **The pinning is the minimax-refit ceiling, not an arithmetic accident.** The 41 rotation angles are the LP-optimal solution of `max c s.t. |err(x)| ≤ tol(x) − c ∀x`. Independent re-solve: **c\* = 58,597,852.7**; shipped circuit achieves **58,597,850** (gap 2.7 units = solver noise). Exactly **42 x-values are pinned** — one per LP variable (41 angles + c). [FAKT]
3. **Within the current architecture c is structurally maximal.** Adding taps (even zero-Toffoli address-bit taps) does not pay: best single tap f = 1.045 (net −6.6 Toffoli-eq), greedy 6 taps f = 1.149 (net −43.0). Break-even per added tap is f = 2.39. [FAKT]
4. **The real lever is n_rot, not c.** The 41 fine rotations cost 294.8 Toffoli-eq and carry the *entire* phase (the Clifford/T part is phase-neutral mod 1 for generic x — §2.1). Removing one rotation saves ≈ 7.19 Toffoli-eq regardless of c; doubling c saves only 5.74 Toffoli-eq total. Even c → absolute ceiling (10.6×) at fixed n_rot=41 buys only GM +0.41%.
5. **Two architecture moves grow c by 5.7–7.2× *and* kill most rotations at once:**
   - **P-A (recommended):** pure-dyadic kickback of the model output y (all weights 2ⁱ⁻⁴⁰ → Clifford/T only, n_rot = 0). Intrinsic min_margin **332,168,080 (5.67×c)**. Open cost: s-dependent bit routing, estimated 50–200 mean Toffolis → **GM +1.96% … +5.60%** even pessimistic. [HYP]
   - **P-B (fallback):** mrmeows' constant-seed model (128-entry table, 2 Newton steps, out_frac 26–27): intrinsic min_margin **366M–424M (6.25–7.24×c)**, worst ratio 0.53–0.64. Compiled cost unknown (table lookup is the risk). [HYP/SPEK]
   - Absolute ceiling for any circuit: c ≤ min_x tol(x) = **621,138,291 (10.6×c)** [FAKT].

**Recommendation:** skip further c-grinding inside the current architecture (expected ≤ GM +0.02%); pursue P-A with a 1–2 day go/no-go pre-experiment (bit-liveness audit + routing-cost prototype). Details §4–§6.

---

## 1. Q1 — Exact derivation of tol(x)

From `verify_submission_invsqrt.py::reference_values()` (lines 117–131), for beta = 1, precision_bits = 24:

```
num = 2^130,  den = 1,  shift = precision_bits + 1 = 25
r(x)     = isqrt(num // x)          = isqrt(2^130 // x)
target(x)= ((r + 1) >> 1) mod 2^64  = round-to-nearest(r/2)
tol(x)   = min(r >> 25, 2^63)       = floor(r / 2^25)
```

Both in units of 2⁻⁶⁴ turns. Since r ≈ 2^65/√x: target ≈ 2^64/√x (i.e. 1/√x turns) and tol ≈ 2^40/√x (i.e. 2⁻²⁴/√x turns = relative 2⁻²⁴).

**Exact closed form.** Claim: `tol(x) = isqrt(2^80 // x) = floor(2^40/√x)` for all x ≥ 1.

Proof sketch: (i) For integers A, x: `floor(A/√x) = isqrt(A² // x)` — standard: n = ⌊A/√x⌋ ⟺ n² ≤ A²/x < (n+1)² ⟺ n² ≤ ⌊A²/x⌋ < (n+1)². (ii) `isqrt(2^130//x) = 2^25 · isqrt(2^80//x)`: with n = isqrt(⌊2^80/x⌋), we have 2^50·n² ≤ ⌊2^130/x⌋ < 2^50·(n+1)², so the isqrt of ⌊2^130/x⌋ is exactly 2^25·n. Hence r(x) = 2^25·isqrt(2^80//x) and tol(x) = r>>25 = isqrt(2^80//x). [FAKT — identity verified on 200k random x + spot values; the three floors (⌊2^130/x⌋, isqrt, >>25) conspire exactly.]

Numbers: tol(1) = 2^40 = 1,099,511,627,776; tol(max_x=3,133,452) = **621,138,291** = 3.37e-11 turns (≥ the verifier's 2⁻⁴8-turns floor requirement). The verifier's ε budget: `ε = π·min_margin/2^64/n_rot`, split evenly over the 41 rotations; each costs `0.56·log2(1/ε) + 5.3` T.

Consequence used below: **tol(x) is (up to a ±1 floor) the same function 2^40/√x that scales the circuit's model output** — the tolerance landscape and the error landscape are "parallel" (§2.3).

---

## 2. Q2 — Why |error(x)| = tol(x) − c with constant c

### 2.1 Phase decomposition (extracted from the circuit)

The circuit text (kickmix, 47,535 ops) contains exactly 113 Z_POW gates: 32 Clifford-class, 40 T-class, **41 fine rotations** (hierarchy level ≥ 4, matching the verifier's n_rot). The 41 sit in two clusters — lines 15312–15632 (15 taps, qubit q28, weights 2⁻¹⁸…2⁻⁴ turns) and lines 25680–25920 (26 taps, qubits q50/q41/q40/q28, weights 2⁻³⁶…2⁻¹¹ turns) — each tap preceded by CSWAP(s) moving a bit into the accumulator and followed by `HMR` (clear-by-measurement). This is the "streamed two-shift phase carry" / double-buffer structure of the public lineage.

Control extraction: for each rotation j I perturbed its text angle by δ = 2⁻³⁰ half-turns (exact binary rational), re-simulated the full domain, and read `b_j(x) = (err_pert(x) − err(x)) / (δ·2^63) ∈ {0,1}`. All 41 columns verified with exact deltas (no anomalies). Phase is seed-independent (verified: two seeds, identical phases) because all measurement repairs are phase-only Cliffords and outcomes are seeded RNG independent of phase values.

With `A(x) := θ_exact(x) − target(x)` where θ_exact is the phase of the circuit with all 41 fine angles zeroed (one more full-domain simulation), the decomposition holds **exactly** (mod 2^64, checked on 300 random x, mismatch = 0):

```
err(x) = A(x) + Σ_j a_j·b_j(x)
```

with a_j the exact stored angles (Fractions of the text decimals, 2⁻¹²⁷-half-turn grid).

Findings:

- **|A(x)|/tol(x) = 2^24 ± 0.03 for all x ≥ 42** (the 63 deviating x's are exactly 2..41). I.e. A(x) = −target(x) + O(tol·1e-8): the Clifford/T part applies **zero net phase (mod 1 turn)** for generic x. Its role is repair/bookkeeping, not phasing. (For small/perfect-square x the exact part absorbs dyadic chunks: x=4 → 1/8 turn, x=9 → 1/12, x=16 → 1/8, x=25 → 3/40 — the "top-bit special handling".)
- **Therefore the entire phase 1/√x is carried by the 41 synthesized taps:** Σ a_j b_j(x) ≡ 1/√x + err(x) (mod 1), to within |err| ≤ tol − c.
- Tap identities (exact/near-exact matches against candidate Boolean functions of the official fixed-point model output y = p<<s): 14 taps are **raw y-bits** — y30…y36 with weights 2⁻¹⁰…2⁻⁴ (matches 99.97–100%) and y15…y21 with weights 2⁻²⁵…2⁻¹⁹ (99.94–99.999%); a further 3 taps (**rot38–40**) are near y-bit matches (↔ y36/y37/y38 at 99.96–99.996%); the remaining 24 are **quadratic forms** of pipeline/coefficient bits (the "direct phase taps … exact gated quadratics" of the public README), covering the unmatched weight ranges 2⁻³⁶…2⁻²⁶ plus the overlap band 2⁻¹⁸…2⁻¹¹ (streamed through both buffers).
- The near-dyadic angles are `a_j = 2⁻ᵏ + δ_j`: the δ_j (relative 1e-5…1e-3) are the refit offsets.

### 2.2 The pinning is the LP optimum (mechanism, confirmed)

Given the decomposition, the angle refit is the linear program

```
maximize    c
subject to  A(x) + Σ_j a'_j b_j(x) ≤ tol(x) − c      ∀x
            −A(x) − Σ_j a'_j b_j(x) ≤ tol(x) − c     ∀x
```

variables (a'_1…a'_41, c). At any optimum, every active constraint sits at exactly `|err| = tol − c` — a constant-c shelf by construction.

**My independent solve** (constraint generation: pool of tight constraints + full-domain separation, HiGHS; data: exact err, tol, B):

```
c*(current 41 controls) = 58,597,852.7 units of 2^-64 turns
active constraints      = 42   (= 41 angle variables + c, basic feasible solution)
shipped angles achieve  = 58,597,850   (gap 2.7 units = 4.6e-8 relative)
```

The 42 active x-values are exactly the observed pinned set (margins 58,597,850…58,597,855; the ±5 spread is float64/solver noise of the original refit — the shipped angles are *not* on a coarse grid: distances to the 2⁻²⁸-turn grid reach 0.5 steps, so the spread is numerical, not quantization).

**Independent confirmation from the public sources:** mrmeows' research package (`sota_mrmeows/sources/invsqrt_20p056_verified_source/…/research/scripts/fit_merged.py`) contains their own refit: identical formulation (maximize margin variable, constraints `±(F·d) + m ≤ t∓e`), identical constraint-generation loop (initial pool = 2048 evenly spaced + 2048 tightest, separation over the full domain, HiGHS), and the README states the guard-bit change "raises the minimum phase margin from 47,884,702 to 58,597,850" — our measured min_margin to the unit. Their merge experiments (fit1–fit8: removing 1…8 rotations and re-fitting) show the margin is a property of the 41-control partition: 40–36 rotations → 47,884,702; 35–33 → 39.0M/40.1M/36.0M, with rot_C savings of only 5.5 Toffoli-eq for the first removal then ~7.4 each — "No circuit implementing its required Boolean controls within the cost budget was emitted."

**Hypothesis verdicts:**
- (a) *common arithmetic structure*: **partially true, necessary but not sufficient.** tol(x) = ⌊2^40/√x⌋ and the tap sum Σ a_j b_j(x) ≈ 1/√x are functions of the *same* quantity 2^40/√x (the model output scale); the error landscape is parallel to the tolerance landscape, which is why a constant absolute offset c is even possible and why the active set clusters in M-space (§2.3). But parallelism alone would give |err|/tol ≈ const, not |err| = tol − c.
- (b) *grid rounding proportional to tol*: **rejected.** No such grid exists; the phase is on the 2⁻⁴⁰ grid only in the exact part (which is phase-neutral), and the pinned offsets are constant in absolute units, not grid-aligned.
- (c) *coincidence*: **refuted — single mechanism:** the minimax LP refit. The constant-c shelf is the active-set signature of that LP; the 42-point count equals the variable count; the shipped solution is optimal to 2.7 units.

### 2.3 Common property of the pinned x's

Full-domain scan: **exactly 42 x-values** have margin within ±5 of c\* (count stable for windows 5…5000):

```
x = 161, 221, 644, 792, 888, 3977, 12673, 13695, 52229, 54778, 58270,
    233129, 245849, 811088, 835671, 851985, 869138, 876464, 876528, 983396,
    1957852, 2072536, 2157629, 2226559, 2348855, 2380722, 2392131, 2474113,
    2484492, 2486670, 2539009, 2539011, 2539139, 2539141, 2925830, 3001932,
    3046270, 3055684, 3055941, 3063147, 3079485, 3099851
```

(signed errors mixed: 17 positive / 25 negative — a constant global shift cannot fix them, as already observed; the optimal shift makes things 3.7× worse, consistent with an interior LP optimum.)

Properties: s = (22−bitlen(x))//2 spans **0…7** (all normalization classes); normalized mantissa M = x·2^(2s)/2^20 spans **[1.867, 3.884]** — the upper ~75% of [1,4), i.e. away from M=1 where the seed is most accurate; 20 of 42 appear in the top-50-by-ratio list, the other 22 sit at large x (ratio 0.906–0.925) where tol is small but the *absolute* ceiling still binds. There is no single simple property (bucket, parity, factorization) — the pinned set is the LP active set, and its geometry inherits the base-residual landscape:

- the official fixed-point model's own error A_ref(x) = y·2⁻⁴⁰ − 1/√x peaks at **M\* ≈ 2.8726** (max |A_ref|/tol = 0.4769, a smooth peak along consecutive x ≈ 3,012,1xx and their /4-images) — inside the pinned M-range;
- dropped low output bits (weights ≤ 2⁻³⁷, not streamed) contribute a systematic bias ≈ 2⁻³⁶ turns = √x/4096 · tol(x) — 43% of tol at max_x, growing with x (explains the large-x pinned cluster);
- small-x special handling (dyadic absorption in the exact part) creates the isolated pinned points at x = 161…983,396.

Slack-layer thickness (how many x must be pushed through when growing c): slack < 2c: **619** x; < 3c: 4,229; < 4c: 16,251; median slack = 12.2c. The active layer is thin — growth is limited by a few hundred points, not by the bulk.

---

## 3. Q3 — Circuit lineage and arithmetic core (from public sources)

- **Core:** official Newton–Raphson fixed-point model (`nr_reference_circuit.fixed_point_model`): normalize x → x_norm (22 bits, M ∈ [1,4)); 4-case cubic Horner seed (17-bit coefficients, 14 delta bits) → y0 ≈ 2^17/√M; one NR step (28-bit square, 28-bit product, 29-bit result, exact final product) → p ≈ 2^30/√M; output y = p<<s, ideal phase y·2⁻⁴⁰ turns. Worst relative model error 2.84e-8 ≈ 0.477·tol (measured: max |A_ref|/tol = 0.4769).
- **Phase application:** streamed taps with HMR clear-by-measurement, double-buffered ("alternate the second phase pass between two buffers", "streamed two shift phase carries" — 15.75 notes); 44 → 41 fine rotations via "direct phase taps" (three sparse late taps moved into four early Boolean quadratic controls, 20.39 README); guard-bit change F15 → F15 XOR [Y1 AND (e1 XOR e2)] (+1 Toffoli) + refit raised c 47,884,702 → 58,597,850 (20.03 step, past 20×).
- **Our local additions (yoyobar timeline):** Q63 → Q62 reduction, four nonlinear-cone rewrites (−248 T), Özer one-Toffoli phase patch (−62 T), Mallick 3-to-2 AND merges, Kirill four-loaders eight-toffolis → current sha e4ed188b, mean executed Toffolis 1,289.29.
- **Measurement policy:** every measurement is a random X-basis outcome with phase-only Clifford repair; no measured function of x selects a branch (README) — which is why the tracked phase is deterministic per x (verified here) and only the Toffoli count varies with seed.
- **Open direction (mrmeows):** constant-seed model — 128-entry seed table (8 frac bits) + two narrow Newton steps (residual 24+2 guard, output fraction 26) — "passes the full domain numerical check at worst error/tolerance 0.617. That margin is the asset: spend it on cheaper circuits." Not compiled; model + sweep in `invsqrt_19p80_history_cache_research`.

---

## 4. Q4 — Ranked proposals to grow c (exact arithmetic)

Cost model (verifier): `C = mean_exec_Toffolis + (t_base + n_rot·(0.56·log2(1/ε) + 5.3))/4`, `ε = π·c/2^64/n_rot`, cost = Q·C, Q = 62. Current: 1,289.29 + (20.5 + 41·28.765)/4 = **1,589.26**; rotation block alone = **294.8 Toffoli-eq**. Reference invsqrt cost 2,076,774.233715282; sibling ratios (yoyobar local): DQI 61.056888, chem 9.934269 → GM baseline **23.3825**.

Marginal economics: removing one rotation saves ≈ 28.76 T = **7.19 Toffoli-eq** (independent of c); doubling c saves 41·0.56·log2(2)/4 = **5.74 Toffoli-eq total**. Break-even for adding one *free* (zero-Toffoli) tap: f = 2^(7.19/5.74) = **2.39×**.

| # | Proposal | New c | n_rot | ΔC (Toffoli-eq) | New C | New cost | New ratio | ΔGM | Status |
|---|----------|-------|-------|-----------------|-------|----------|-----------|-----|--------|
| 0 | shipped | 58,597,850 | 41 | — | 1,589.26 | 98,533.87 | 21.0768 | — | [FAKT] |
| 0′ | LP-polished angles only | 58,597,853 | 41 | ≈ 0 | 1,589.26 | 98,533.87 | 21.0768 | ≈ 0 | [FAKT] — nothing to gain |
| D | add 1 best free tap (case_third/bkt4) | 61,249,290 | 42 | +7.0 | 1,596.3 | 98,970 | 20.984 | −0.14% | [FAKT] dead end |
| D′ | add 6 free taps (greedy: bkt4, addr03, addr08, addr13, addr00, addr02) | 67,340,595 | 47 | +43.1 | 1,632.4 | 101,208 | 20.520 | −0.89% | [FAKT] dead end |
| E | c → absolute ceiling, n_rot fixed | 621,138,291 | 41 | −29.5 | 1,569.7 | 97,322 | 21.339 | +0.41% | [FAKT bound] unreachable in current arch |
| C | control swap (guard-bit precedent) | ~71M (f≈1.22) | 41 | +1 Toffoli − ~1.2 | ≈ 1,589 | ≈ 98,530 | ≈ 21.08 | +0.01–0.02% | [HYP] marginal; search space large |
| **A** | **pure-dyadic kickback of y** (P-A) | **332,168,080** (5.67×) | **0** | **−294.8 + R + ~5**, R = routing | 1,349–1,499 | 83,664–92,964 | **22.34–24.82** | **+1.96% … +5.60%** | [HYP] — see below |
| B | constant-seed rebuild (P-B) | 366M–424M (6.25–7.24×) | 0 (or ~26) | −294.8 + Δcore + ~5, Δcore unknown | 1,399–1,499 | 86,764–92,964 | 22.34–23.94 | +1.96% … +4.33% | [HYP/SPEK] |

**P-A detail (recommended).** The model output y = p<<s < 2^40 already exists in the pipeline; 14 of the 41 current taps are already raw y-bit taps with (near-)dyadic weights. Replace the whole tap section by a clean dyadic kickback: stream y-bits 4…39 (weights 2^(i−40): even 40−i → Clifford, odd → T; bottom 4 bits droppable but kept — they cost 2 T + 2 Clifford taps and preserve the full margin). Then n_rot = 0, ε irrelevant, and the error is exactly the model error A_ref: min_margin = **332,168,080** at x = 3,012,139 (worst ratio 0.4769) [FAKT, exact integers]. The only new engineering is **s-routing**: tap i must read y_i = p_{i−s}, so the source bit depends on s (≤ 10). Options: barrel-shift the p-register once before streaming (10 conditional shift stages × ~30 links ≈ 150 mean Toffolis worst case), or fold selection into the existing CSWAP routing (cheaper, unquantified). Estimate R ∈ [50, 200] mean Toffolis [HYP]; Q_peak must stay ≤ 62 (the y-register bits are already live during the current streaming — no new persistent qubits expected, but the shift workspace may peak). Even at R = 200 the move is worth GM +1.96%; at R = 50, GM +5.60% (ratio 24.82×). As a byproduct, c grows 5.67× and the design becomes robust to future core changes (margin headroom instead of a 0.9993 ceiling).

**P-B detail.** Exact-integer evaluation of the reconstructed constant-seed model (128-entry centered table, 8 frac bits, NR widths (16, 24+2, 26) per mrmeows' spec, plus variants):

| variant | worst ratio | min_margin | ×c |
|---|---|---|---|
| table, spec corner (16,24,26) | 0.6434 | 366,137,876 | 6.25 |
| pwq3 seed (16,24,26) | 0.5577 | 335,922,122 | 5.73 |
| table, guard 25 (16,25,26) | 0.5932 | 417,466,994 | 7.12 |
| table, out_frac 27 (16,24,27) | 0.5870 | 424,039,681 | 7.24 |
| table, seed_frac 9 (9,16,24,26) | 0.5264 | 405,910,338 | 6.93 |

[FAKT for the model margins; the compiled circuit is unproven.] y < 2^37 → fewer streamed bits than today; the 128-entry table lookup is the new cost center (most table bits are cheap threshold predicates of M — the same "joint coefficient decoder" structure the lineage already uses — but this is unquantified). P-B is strictly dominated by P-A *unless* P-A's s-routing turns out expensive and the constseed core routes cheaper (narrower registers). Keep as fallback/second track.

**Why not "add 1 bit of precision at a stage" (task candidate).** Any precision change modifies y → modifies the tap controls b_j(x) → the whole partition must be rebuilt; the margin gain is then bounded by the new model's intrinsic worst ratio, and the Toffoli cost (wider multipliers, ~O(width) ANDs per added bit) is paid immediately while the rotation-side saving is capped at 5.74·log2(f) with f limited by the new model's landscape. For the current core, adding result_bits 29→30 only adds a guard bit (p < 2^31 but the true value is < 2^40/√x < 2^40 — the extra bit never contributes to the phase mod 1); coef_bits/delta_bits improvements shrink A_ref's 0.477 peak by ~2–4× but the *shipped* circuit doesn't use A_ref as its error — it uses the tap partition, whose ceiling is set by the LP, not by A_ref. Net: dominated by P-A/P-B. [HYP, with the A_ref peak data in §2.3]

**Why not "targeted phase patch for the pinned class".** A patch = new control(s) + new rotation(s) = proposal D/C territory: the pinned points are the LP active set, so any patch must move all 42 simultaneously; one new parameter can balance at most two sub-families, and the repricing penalty (7.19 Toffoli-eq per added rotation) exceeds any achievable 5.74·log2(f) benefit (measured max f = 1.045 per tap). [FAKT]

---

## 5. Q5 — Any other cheap margin source?

- The 2 x at ratio 0.999–1.0 (x=161, 221) and 6 at 0.99–0.999 (x=644, 792, 888, 3977, 12673, 13695) **are pinned points** (part of the 42-active LP set) — not a separate source. [FAKT]
- Beyond the 42 pinned x's, **577** x's have slack in (c, 2c) (619 total < 2c minus the 42 pinned). [FAKT]
- Absolute ceiling c ≤ 621,138,291 (10.6×) is unreachable within the current control span (LP-optimal at 58.6M). [FAKT]
- Rotation-synthesis side: ε is already the largest the verifier allows given c; nothing to gain without growing c or shrinking n_rot. [FAKT]
- t_base = 20.5: mean executed T-class Z_POWs (static count 40); a dyadic redesign keeps ~the same order. No cheap win. [FAKT]
- Mean executed Toffolis (1,289.29) is a separate lever (cone rewrites etc.) — out of scope here; note that P-A's routing cost R is paid against it.

---

## 6. Recommendation

1. **Skip** further c-grinding inside the current architecture: LP gap to optimum is 2.7 units (worth ≈ 0.000003% of cost); best control swap ≈ GM +0.02%; tap additions are measured dead ends. Total realistic upside < GM +0.05%, effort days.
2. **Pursue P-A (pure-dyadic phase application)** as the primary direction. Pre-experiment (1–2 days, cheap):
   1. Bit-liveness audit: for each required y-bit 4…39, determine whether it (or an equivalent) is already streamable at a tap checkpoint in the current circuit (reuse the perturbation machinery: correlate candidate bit functions against the 27 unmatched controls).
   2. Prototype the s-routing (barrel shift vs folded CSWAP selection) in a kickmix builder on a reduced domain; measure mean executed Toffolis and Q_peak.
   3. Go/no-go: proceed if R ≤ 200 mean Toffolis and Q_peak ≤ 62 (guaranteed GM ≥ +1.96%; expected +3–5%). Full build then re-applies the measurement-based uncomputation stack (1–3 weeks).
3. **Keep P-B (constant-seed rebuild) as the parallel/fallback track** — it is mrmeows' explicitly published open direction ("If you compile it first, publish the flame chart"), its intrinsic margin (6.25–7.24×c) is the best identified, and its narrower registers may route cheaper if P-A's s-routing blows up. Do not start before the P-A pre-experiment result.
4. If both fail on cost: accept that c is structurally maximal for this architecture family and shift effort to the mean-Toffoli lever (out of scope here).

---

## Appendix — reproducibility

| artifact | path |
|---|---|
| rotation list (41 angles, lines, qubits) | `work/p0_reports/step1_rotations.json` (script `step1_circuit_structure.py`) |
| full-domain signed err(x), seed 0 | `work/p0_reports/data/err_orig.npy` (script `step2_extract_controls.py`, ~5 min) |
| control columns b_j(x), j=0..40 | `work/p0_reports/data/bcols/col_*.npy` (same script; perturbation δ = 2⁻³⁰ half-turns, exact-delta verified) |
| exact angles (Fractions) | `work/p0_reports/data/meta.json` |
| zero-angle simulation θ_exact, A_exact | `work/p0_reports/data/th_exact.npy`, `A_exact.npy` (ad-hoc script, ~4 s) |
| reference-model error A_ref, s array | `work/p0_reports/data/A_ref.npy`, `s_arr.npy` (script `step4a_reference_model.py`) |
| LP optimum c\* = 58,597,852.7 | `work/p0_reports/data/lp_result.json` (script `step5b_lp_delta.py`, ~90 s, HiGHS) |
| single-candidate values (28 candidates) | `work/p0_reports/data/step6_candidates.json` (script `step6_candidates.py`) |
| greedy forward selection trajectory | `work/p0_reports/data/step8_greedy.json` (script `step8_greedy.py`) |
| constseed exact margins | script `step9b_constseed_exact.py` (output in §4) |
| pinned set (42 x) | `work/p0_reports/data/pinned_set_42.json` |
| cost tables | script `step10_costs.py` (output in §4) |

Verification anchors: err matches `work/frontier_scan/p0_invsqrt_errors.json` top-10 exactly; decomposition err = A + Σa_jb_j exact (300 random x, mismatch 0); phase seed-independent (2 seeds, subset match); LP gap 2.7 units vs shipped min_margin 58,597,850.
