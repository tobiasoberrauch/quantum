# Report C — Chemistry: S_143 leaf-index gauge permutation

**Verdict: ABANDON** (permutation hypothesis tested; symmetry holds exactly, but no tested reordering improves compiled loader cost — all 25 are strictly worse).

Date: 2026-11-03 · Subagent C · Repo: `/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum`
Tested artifact: `work/frontier_scan/mwa2_unpacked/dfthcsos/` (npz sha f5783ebc, somejoint "ladder" release)

---

## 1. Make-or-break result

**The S_143 leaf-index permutation is an exact gauge symmetry of the factorization metrics.** [FAKT]

20 random permutations π of the B=143 THC leaf index, applied consistently to `W[:, b, :]` (weights) **and** to the two-body rows of the angle-word table (row `76 + ρ·143 + b`), leave every scored metric invariant to float64 reordering noise:

| metric | baseline (Ha) | max \|Δ\| over 20 perms | limit / margin |
|---|---|---|---|
| error_1 | 0.010270472386659672 (10.27047 mHa) | 9.1e-16 | ≤ 0.020 → margin 9.7 mHa |
| error_2 | 0.019999650033498264 (19.99965 mHa) | 1.0e-17 | ≤ 0.020 → margin 3.5e-4 mHa ≫ noise by 10¹³ |
| Lambda | 284.3927855703766 | 5.7e-14 | > 49.0 |
| E_SOS | −22144.188249200004 | **0 (bit-exact)** | — |
| E_gap | 3.9148992000045837 | **0 (bit-exact)** | > 3.914898 |
| λ_eff | 47.025649827374934 | 7.1e-15 | — |

Bit-exact: 0/20 (einsum contraction order changes last ulps), but all deltas are ≤ 6e-14 Ha = pure floating-point summation-order noise, not structure. Why it must hold: every use of the b-index in the metric path is permutation-invariant — `X^(ρc) = Σ_b w_b u_b u_bᵀ` (sum over b), `λ_h2` (L1-norm + sum over b), `W_native = H2_I − Σ_b w_b` (sum over b). error_1 additionally pairs one-body rows by |overlap| assignment, so row order/sign is irrelevant there too. [FAKT, code: `starter_kit/starter_kit/verifier/dfthc_math.py`]

Baseline cross-check: full official verifier run on the original directory → `PASS`, score **313,678,954.0955252**, T=15,585, Q=428, λ_eff=47.025649827374934, angles_T=8,932, heuristic_T=6,653, angles_qubits=128 — identical to published numbers. Direct computation from the npz `angle_words` reproduces all metrics exactly ⇒ **npz angle_words == words the circuits load**. [FAKT, `work/p0_reports/verify_baseline.json`]

## 2. npz schema [FAKT]

| key | shape | dtype | role in verifier |
|---|---|---|---|
| `U` | (9, 143, 76) | f64 | **not used for metrics** — only its last dim (N=76) is checked; exact (unquantized) two-body vectors, diagnostic |
| `W` | (9, 143, 39) | f64 | lowercase weights w^(ρbc); b-axis = the 143 leaf index |
| `H2_I` | (9, 39) | f64 | w_B = W_native + Σ_b w; W_native = H2_I − Σ_b w |
| `H1_I` | () | f32 | **ignored** — replaced by fixed competition shift (`FeMoCo76o113e.fixed_shifts.npz`, sha-checked) |
| `Hsym_lower` | (2926,) | f32 | **ignored** — same fixed shift (S, β₁) |
| `angle_words` | (1363, 75) | i64 | diagnostic copy of the loaded words: 76 one-body rows + 9·143 two-body rows in (ρ,b) order; 8-bit words (brot=8) |
| `tree_edges` | (75, 2) | i64 | Givens tree, rooted at 0, parent-before-child (validated) |
| `brot` | () | i64 | 8 |

R=9 groups, B=143 leaves, C=39 copies, N=76 orbitals, η=113 electrons, E_upper=−22140.27335.
`HASHED_NPZ_KEYS = (U, W, H2_I, H1_I, Hsym_lower, tree_edges)` feed only the simulator seed, not the deterministic metrics. [FAKT, `data/verifiers/dfthcsos/scoreinfra/{reference,circuits}.py`]

Verifier flow: circuits are simulated (kickmix, 64 shots/address) to recover words + Toffolis; metrics come from recovered words + npz weights. A permuted npz with un-recompiled circuits would still pass the metric gates (gauge), but a real submission requires recompiling the 15 loaders for the permuted tables. [FAKT]

## 3. Word-table extraction [FAKT]

Directly available: `angle_words` (1363×75, brot=8) in the npz, validated equal to circuit output via the full verifier run (§1). Loader structure: 15 circuits × J=5 angles × 8 bits; each loader k compiles the delta table `words[:, 5k:5k+5] ⊕ words[:, 5k−5:5k]` over D=1363 addresses (11 selection bits).

## 4. GF(2) relation counts: current vs permuted

Method: ran the local mrmeows `rank_parity` compiler planner (same pipeline as `work/chem_recompile.py`) on the current table, 20 random permutations, 4 structured permutations (rev-b, rho-pair-swap, rev-b+rho-swap, b→7b mod 143), at config J=5/lb=5 (A=43 high blocks, B=32 low, cache=62, 124Q, max_kernels=32767). Cost model verified against `build()`: static CCX per loader = `transformed_paired_products` + 2·cache; verifier counted Toffoli = 2× static (forward+reverse). [FAKT]

**Calibration caveat:** this config's absolute cost (9,185 static) is ~2× mwa2's measured 4,466 static — mwa2's loaders were compiled with a better compiler (manwithacat kernel-relation search + somejoint ladder; SOTA layout 126Q with borrowed word bits, per memory notes 2026-10-31). Absolute numbers are not transferable; **relative ranking within one fixed compiler is valid**. [FAKT + SPEK]

| ordering | static CCX (J5_lb5) | Δ vs current | kernels found |
|---|---|---|---|
| **current** | **9,185** (content 7,325 + fixed 1,860) | — | 470 (35×4 loaders k0–3, 30×11 k4–14) |
| 20 random perms (all identical!) | 9,735 (content 7,875) | **+550 (+6.0%)** | 524–525 |
| rev_b | 9,735 | +550 | 524 |
| rho_swap | 9,654 | +469 | 470 |
| rev_b_rho_swap | 9,666 | +481 | 470 |
| b7mod | 9,735 | +550 | 524 |

Config sweep (perm0 / rho_swap): J3_lb5 (108Q): 10,873 / +627 / +484 · J4_lb5 (116Q): 9,669 / +596 / +464 · J5_lb5 (124Q): 9,185 / +550 / +469. lb≤4 infeasible (>128Q). **Permutation is worse in every feasible config.** [FAKT]

Two structural observations:
1. **All 20 random permutations converge to exactly the same cost (7,875 content CCX).** Scrambling destroys the co-design structure completely and identically — the permuted tables look statistically generic to the compiler. The current table's +550 CCX advantage comes from specific exploitable structure, not luck. [FAKT]
2. Permutations find *more* nullspace kernels (524–525 vs 470) yet cost more: the heuristic planner discovers relations on scrambled tables but cannot factor them into a cheaper basis. Relation count alone is not the cost driver. [FAKT]
3. Global ANF degree over the 11 address bits: all 75 word bits have degree exactly 11, current and permuted alike — no low-degree (RM(1)) structure exists at the full-address level; the exploitable structure lives in the compiler's H×L tensor split. [FAKT]

## 5. Expected Toffoli delta & arithmetic

- Score = λ_eff · T_total · Q_total. λ_eff gauge-invariant (§1). Q_total pinned at 428: all 15 loaders sit exactly at the 128Q cap (memory 2026-11-03 P0-audit: "kein Pebbling-Spielraum"), temporary workspace dominated by the fixed heuristic part (303Q). So Δscore/score = ΔT/T. [FAKT]
- Observed under the tested compiler: ΔT_angles = +1,100 counted Toffoli for every permutation (+7.1% of T_total) — **expected gain from permute-and-recompile is negative**. [FAKT]
- History shows diminishing returns already extracted: manwithacat kernel search 16,071→15,629 (−442), somejoint ladder →15,585 (−44). [FAKT, memory notes]
- Portfolio context: chemistry ratio 10.6976×; a hypothetical −1% on chemistry T would move portfolio GM by ≈ +0.33%. The permutation route offers ≤ 0% in expectation. [SPEK]
- Key argument: the gauge orbit {all reorderings of the shipped table} is a subset of the design space the original authors had when they co-designed words+weights+circuits. They shipped this ordering after running their own kernel-relation search. Beating it requires solving their co-design problem better — an intelligent search over 143! orderings targeting the actual (unavailable) compiler — not a recompile. [SPEK]

## 6. Recommendation: **ABANDON** [SPEK]

- Symmetry holds (hypothesis part 1: confirmed, useful knowledge — see below).
- Cost side fails: 25/25 tested orderings × 3 feasible configs all worse (+464…+627 static CCX). No free lunch; the shipped ordering is already the co-designed optimum of its lineage.
- Effort to even test the top candidate end-to-end (recompile 15 loaders + verifier 2–5 min + submission budget 1/5 left) buys expected value ≤ 0.

Residual value of the result:
1. The gauge proof removes a constraint from any future word-redesign work: weights can always be re-permuted to match new word orderings at zero metric risk (margin to error_2 limit: 3.5e-4 mHa vs 1e-11 mHa noise). [FAKT]
2. If a future session obtains mwa2's actual compiler (manwithacat/somejoint), the right experiment is a *structured* ordering search (affine address maps, block locality), not random permutations — random scrambling is proven dead. [SPEK]
3. The "all permutations identical" attractor (7,875) is a usable baseline: any proposed ordering must beat 7,875 under the mrmeows planner before it is worth compiling. [FAKT]

## 7. Reproduction

```bash
cd /Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum
# gauge symmetry (20 perms, ~15 s):
.venv/bin/python work/p0_reports/gauge_test.py
# official verifier baseline (~2-5 min):
.venv/bin/python data/verifiers/dfthcsos/verify.py work/frontier_scan/mwa2_unpacked/dfthcsos
# compiler ranking (20 random perms, ~30 s):
.venv/bin/python work/p0_reports/recompile_rank_test.py
# structured perms + ANF profile (~10 s):
.venv/bin/python work/p0_reports/structure_test.py
# config sweep J∈{3,4,5}×lb∈{3,4,5} (~45 s):
.venv/bin/python work/p0_reports/config_sweep.py
```

Artifacts: `work/p0_reports/{gauge_test_results.json, verify_baseline.json, recompile_rank_results.json, structure_results.json}`.
