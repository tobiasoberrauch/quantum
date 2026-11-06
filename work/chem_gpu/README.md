# DF-THC lower-rank GPU training package (`work/chem_gpu/`)

Portable, GPU-ready trainer to push the FeMoCo76o113e DF-THC factorization to a
**lower rank** than the current best (qvc-007: `(R,M,G)=(9,143,39)`, ratio **10.6976×**)
while staying valid (`error_2 ≤ 20 mHa`). Drop this directory onto any CUDA box that has
the repo, `pip install`, and run `./run.sh`.

The plan is staged and **gated** — later stages only run if the gate opens. See
[`ALGO_PLAN.md`](ALGO_PLAN.md) (the approved plan, verbatim) and [`PREP_STATUS.md`](PREP_STATUS.md)
(what was validated on CPU before hand-off).

## Goal & bar
Beat **10.6976×** (qvc-007) at a lower rank. Target window: **M ∈ [129,134], G ∈ {35,36}**.
Forbidden: M ≤ 128 (qubit cliff, Q→657) and G ≤ 32 (error_2 floor). Expected best
≈ **12.16×** at (130,35) (+1.07 GM), pending real compilation.

## Staged flow (gated)
| Stage | What | Runs when | Output |
|-------|------|-----------|--------|
| **0** | Baseline anchor: reproduce 10.6976× on the stored qvc-007 circuits via the official verifier | always | `results/stage0_anchor.json` |
| **1** | PRIMARY (130,35): Cholesky seed → L-BFGS → compile+verify | after Stage 0 passes | `results/stage1_130_35_chol.json` |
| **2a** | Multi-start: N diverse Cholesky seeds × L-BFGS | only if Stage 1 invalid | `results/stage2_*` |
| **2b** | Warm-start: truncate valid M=143 → (130,35) → L-BFGS | only if 2a invalid | `results/stage2_*` |
| **2c** | Hybrid: Adam preconditioner → L-BFGS | only if 2b invalid | `results/stage2_*` |
| **3** | Sweep (130,36),(134,36),(132,35),(132,36) with the winning recipe | only if ≥1 valid from 1–2 | `results/stage3_*` |
| **DECISION** | **GO** (≥1 valid, ratio>10.6976×) or **DEAD** (ladder fails) | always | `results/DECISION.json` |

If Stage 0 does **not** reproduce 10.6976×, the run STOPS with `DECISION=BLOCKED`
(the pipeline is broken before any lower-rank output can be trusted).

## Objective (JAX, STE-aware)
Trainable: `U (R,M,N)`, `w (R,M,G)`, `H2_I (R,G)` (frozen: `Hsym_lower`, `H1_I`, `S`, integrals).
```
objective = error_2(quantized)                 # two-body fit on DECODED b-bit-rounded Givens vectors
          + alpha * max(0, 3.9152 - E_gap)     # accuracy barrier
          + gamma * ||w||_1                    # sparsity (Z := w)
          + beta  * GF2_soft_entropy(words)    # compile-friendliness of the grouped angle tables
```
Givens angles are snapped to `brot`-bit integers with a straight-through estimator (STE), so
training optimizes the *quantized* solution directly. Optimizer: multi-restart **L-BFGS-B**
(`jax.scipy.optimize.minimize`), ~8 rounds × up to 60k iters. Plain Adam is avoided as the
primary optimizer (measured to diverge from CPU seeds); it appears only as the Stage-2c
preconditioner.

## Setup on a fresh CUDA box
```bash
# 1) get the repo + this dir (work/chem_gpu/) onto the box
# 2) install dependencies
pip install -r work/chem_gpu/requirements.txt
pip install -e <repo>/qualtran            # provides qualtran AND kickmix (needed to compile+verify)
# 3) confirm JAX sees the GPU
python -c "import jax; print(jax.devices())"
```
`train_gpu.py` auto-detects the repo root two levels above `work/chem_gpu/`
(override with `export QUANTUM_REPO=/path/to/repo`).

## Launch
```bash
cd work/chem_gpu
./run.sh --quick      # FASTEST decision: Stage 0 -> Stage 1 only  ((130,35) primary)
./run.sh              # full gated pipeline: 0 -> 1 -> [2 if invalid] -> [3 if valid]
```
Useful flags (pass after the mode word, e.g. `./run.sh --quick --maxiter 20000`):
`--max-rounds 8 --maxiter 60000 --n-starts 4 --alpha 1.0 --gamma 1e-4 --beta 1e-4
--brot 8 --x64/--no-x64`.

## Expected wall-time (one modern datacenter GPU, A100/H100 class, x64)
| Stage | Estimate | Notes |
|-------|----------|-------|
| 0 | ~15 s | official verifier simulates 15 stored circuits |
| 1 | ~10–25 min | L-BFGS usually early-stops in 2–4 rounds; +~30 s compile/verify |
| 2a | ~40–100 min | 4 multi-starts × Stage-1 cost |
| 2b / 2c | ~10–25 min each | single L-BFGS pass |
| 3 | ~40–100 min | 4 shapes × winning recipe |
| **full (GO path)** | **~15–30 min** | Stage 1 succeeds → light Stage 3 |
| **full (DEAD path)** | **~2–4 h** | entire ladder runs |

Consumer GPU (RTX-class, weak float64): add `--no-x64` to halve time, accepting a noisier
E_gap barrier (see Risks). VRAM: **~1–2 GB** peak (f64); the dominant term is the
`N⁴` two-body tensor (≈268 MB) plus its gradient. Any ≥8 GB card is comfortable.

## Reading results
- `results/DECISION.json` — the verdict: `GO` (with best shape/ratio/ΔGM/recipe) or `DEAD`
  (with best error_2 per stage as basin-wall evidence) or `BLOCKED` (Stage 0 failed).
- `results/stageN_<M>_<G>_<seed>.json` — per-run record: continuous metrics
  (error_2, E_gap, Λ, λ_eff), compiled metrics (error_1, Toffolis, Qubits, score, ratio, ΔGM),
  validity flag, L-BFGS history, recipe.
- A point is **valid** iff `error_2 ≤ 20 mHa` **and** `gap_in_domain` **and** the compiled
  `error_1 ≤ 20 mHa` **and** `ratio > 10.6976×`.

## Files
- `train_gpu.py` — staged/gated JAX trainer (Stages 0–3, GO/DEAD, self-test, smoke test).
- `run.sh` — launcher (self-test gate → staged pipeline).
- `seed_build.py` — builds the Cholesky-clustered (Stage-1) and truncation (Stage-2b) seeds;
  `train_gpu.py` calls it on-the-fly when a `seed/*.npz` is missing.
- `seed/` — prebuilt seeds (U,W,H2_I,H1_I,Hsym_lower per shape).
- `ALGO_PLAN.md` — approved staged plan (source of truth). `PREP_STATUS.md` — CPU validation log.
- `baseline_e2e_test.py`, `_stage0_anchor.py` — CPU validation harnesses (kept for reference).
- `requirements.txt` — pinned deps.
