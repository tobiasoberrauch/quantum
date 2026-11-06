# ALGO_PLAN — DF-THC lower-rank GPU run (staged, gated)

Approved algorithm prioritization for the chem lower-rank GPU run (qvc-007 → qvc-009).
This document is the durable, reviewable source of truth. `train_gpu.py` implements it;
`run.sh` orchestrates the gating. **Do not deviate silently** — if a stage is infeasible
as specified, flag it in the report rather than changing the plan.

Baseline bar (qvc-007): error_2 = 19.99965 mHa, E_gap = 3.9148992, λ_eff = 47.0256,
T = 15585, Q = 428, **ratio = 10.6976×**. Any lower-rank result must beat this.

---

## Staged run plan (gated — later stages only run if the gate opens)

### STAGE 0 — Baseline anchor (must reproduce first, always runs)
Confirm the current M=143 / G=39-40 solution reproduces error_2=19.99965 mHa, ratio
10.6976× (our qvc-007 chem). This is the bar any lower-rank result must beat. If Stage 0
does NOT reproduce 10.6976×, STOP and report (the pipeline is broken before we trust any
lower-rank output).

### STAGE 1 — PRIMARY bet: (M=130, G=35)
- Seed: Lera's compact Cholesky-clustered seed (the one extracted/validated).
- Optimizer: **L-BFGS** (JAX, ~8 rounds × 60k line-search iterations). Do NOT use plain
  Adam (measured to diverge: err2→3794 mHa from CPU seeds).
- Composite objective:
  (i) accuracy barrier `max(0, 3.9152 − E_gap)`;
  (ii) hard validity gate `error_2 ≤ 20 mHa` (a point counts as "valid" ONLY if this holds);
  (iii) sparsity `γ·‖Z‖₁`;
  (iv) GF(2)-relation/entropy regularizer on the grouped angle tables (compile-friendliness);
  (v) STE snap of Givens angles to b-bit integers.
- Success criterion: converges to a VALID point (error_2 ≤ 20 mHa) with λ_eff ≥ 47 and
  ratio > 10.6976×. Expected best ≈ 12.16× (+1.07 GM).
- Why (130,35) first: highest expected gain AND closest to the G=32 cliff — if it works,
  the safer shapes (130,36)/(134,36) follow easily.

### STAGE 2 — FALLBACK ladder (runs ONLY if Stage 1's best error_2 > 20 mHa, i.e. invalid basin)
In order; stop at the first stage that yields a valid point:
- a. **Multi-start:** N diverse Cholesky-clustered seeds (vary clustering scheme, cluster
  count, random orthogonal rotations of the seed) × L-BFGS each; keep the best valid point.
  Directly attacks the basin-selection problem.
- b. **Warm-start from valid M=143:** take our known-valid M=143 solution, importance-
  prune/truncate to M=130, THEN re-optimize with L-BFGS. (Naive truncate-without-reopt blew
  err2 to 124 mHa, but truncate→reopt from a valid start may recover.)
- c. **Hybrid:** Adam with small LR as a preconditioner (few steps to settle into a basin) →
  hand off to L-BFGS for refinement. Alternative within this stage: ALS (alternating least
  squares) for the linear tensor sub-problems, often more stable than full L-BFGS for the
  pure fit.

### STAGE 3 — Remaining shapes (runs ONLY after Stage 1 or 2 yields ≥1 valid point)
Sweep (130,36), (134,36), (132,35/36) with the winning recipe. AVOID M≤128 (qubit cliff
Q→657) and G≤32 (error_2 floor).

---

## Decision rule (the run MUST end in exactly one of these, written to results/)
- **GO:** at least one (M,G) converges valid (error_2 ≤ 20 mHa) with ratio > 10.6976× →
  emit that factorization (W, χ, Z tensors + full metrics: error_1, error_2, E_gap, Λ,
  λ_eff) for compilation into qvc-009. Report the best (M,G), its ratio, ΔGM vs 10.6976×,
  and the exact recipe (stage + seed variant) that worked.
- **DEAD:** the entire ladder (Stages 1–2) fails to produce any valid point at the target
  shapes → declare chem lower-rank DEAD (clean negative result, like invsqrt/DQI-surgery).
  Report the best error_2 achieved per stage as evidence it is a basin wall, not a tuning
  issue.

---

## Implementation mapping (where each stage lives)
| Plan item | Code | Output |
|-----------|------|--------|
| Stage 0 anchor | `train_gpu.py::stage0_anchor()` | `results/stage0_anchor.json` |
| Stage 1 primary (130,35) | `train_gpu.py::stage1_primary()` | `results/stage1_130_35.json` |
| Stage 2a multi-start | `train_gpu.py::stage2a_multistart()` | `results/stage2a_<shape>.json` |
| Stage 2b truncation warm-start | `train_gpu.py::stage2b_warmstart()` | `results/stage2b_<shape>.json` |
| Stage 2c hybrid Adam→L-BFGS | `train_gpu.py::stage2c_hybrid()` | `results/stage2c_<shape>.json` |
| Stage 3 sweep | `train_gpu.py::stage3_sweep()` | `results/stage3_<shape>.json` |
| GO/DEAD decision | `train_gpu.py::decide()` | `results/DECISION.json` |
| Gating orchestration | `train_gpu.py::main()` / `run.sh` | — |

## Objective terms (JAX, float32 training / float64 final verify)
- Trainable params: `U (R,M,N)`, `w (R,M,G)` (lowercase weights), `H2_I (R,G)` (identity
  offsets). Frozen: `Hsym_lower`, `H1_I` (→ β₁), `S`, reference integrals.
- Derived: `W_rc = H2_I − Σ_b w` ; `w_B = W_rc + Σ_b w = H2_I`.
- `error_2 = ‖Σ_rc X_rc⊗X_rc − tei − S-shift‖_F` (X_rc from normalized U rows).
- `E_gap = E_upper − E_SOS`; `λ_eff = √(E_gap·(2Λ − E_gap))` when `0 < E_gap < 2Λ`.
- Objective = `error_2 + α·max(0, 3.9152 − E_gap) + γ·‖w‖₁ + β·GF2(words)`, with STE-snap
  rounding of the encoded Givens angles to `brot`-bit words feeding the GF(2) term.
- **Z (sparsity term)** is interpreted as the continuous weight tensor `w` (‖w‖₁). Flagged
  in the report — the plan text uses "Z" without defining it; `w` is the natural
  two-body coefficient tensor to sparsify.
- Validity gate (ii) is enforced at evaluation (a point is "valid" iff error_2 ≤ 20 mHa),
  and also enters the objective as part of the accuracy pressure via the E_gap barrier.

## Cliffs / forbidden region
- M ≤ 128 → qubit cliff (Q jumps 388 → 657). Avoid.
- G ≤ 32 → error_2 floor (cannot reach ≤ 20 mHa). Avoid.
- Target window: **M ∈ [129,134], G ∈ {35,36}**.
