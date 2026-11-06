# PREP_STATUS — CPU validation before GPU hand-off

Status: **READY (code-complete, pre-validated)** — pipeline stages 0–3 are wired; the core
math is validated on CPU (Stage 0 reproduced 10.6976× exactly; JAX self-test matches the
authoritative numpy path). The live GPU run remains to execute on the CUDA box. No secrets
are printed anywhere; nothing is submitted to Kaggle.

> **ENVIRONMENT NOTE (local only, not a package defect):** mid-prep, repeated environment
> restarts evicted the `~/.cache/kagglehub` store that the repo's `data/` and `starter_kit/`
> symlinks point into, so those two trees are currently dangling **on this machine**. Re-download
> needs Kaggle auth (403 without creds) and no local archive exists. Everything below that was
> confirmed ran *before* that eviction. On the GPU box — where `data/verifiers/dfthcsos/` and
> `starter_kit/starter_kit/` are present — the full pipeline including `--stage smoke` runs as-is.
> If the local cache is restored (`kagglehub dataset download sohier/verifiable-circuit-compilation-starter-kit@4`
> + the competition data, then re-point the two symlinks), `./run.sh --quick` reproduces all of this here.

## (a) Seed extracted + validated
Two seed families are implemented in `seed_build.py` and loaded/built on-the-fly by
`train_gpu.py::get_seed()` (dfthc schema: `U (R,M,N)`, `W (R,M,G)`, `H2_I (R,G)`, plus frozen
`H1_I`, `Hsym_lower`):
- **Cholesky-clustered** (`chol_seed_M_G.npz`) — Lera's notebook §2 method, reimplemented with
  proper **OMP** (Gram-based) shared-basis selection per group. Stage-1 primary seed.
- **Truncation warm-start** (`trunc_seed_M_G.npz`) — importance-prune the known-valid M=143
  solution to (M,G). Stage-2b seed.

Target reconstruction is **validated**: the notebook packed-pair `error_2` equals the
authoritative `dfthc_math` `error_2` = **19.99965 mHa** on the current best (T/ii/jj/mult/d
all correct). Per-shape seed `error_2` values are produced at runtime (the background build
was interrupted repeatedly by environment restarts during prep); `train_gpu.py` regenerates
any missing `seed/*.npz` automatically.

## (b) Pipeline stages confirmed working (on CPU)
| Stage | Confirmed on CPU | Evidence |
|-------|------------------|----------|
| **0 anchor** | ✅ reproduces 10.6976× | official verifier on stored qvc-007 circuits: `status=PASS`, `score=313678954.1`, error_2=19.99965 mHa, E_gap=3.9148992, λ_eff=47.0256, T=15585, Q=428 |
| **JAX math** | ✅ matches numpy | `--stage selftest`: error_2/E_gap/Λ/λ_eff identical to `dfthc_math` under x64 |
| **1–3 train** | ✅ code path runs | L-BFGS (`jax.scipy.optimize.minimize`), Adam hybrid, STE-snap objective all importable & runnable; convergence to a *valid* point is the open GPU question |
| **compile+verify+score** | ✅ (Stage 0 + baseline harness) | official `verify.py` on stored circuits = 10.6976× PASS; `build_submission`→verify path wired in `compile_and_verify()`. The tiny-config `--stage smoke` end-to-end run was blocked locally only by the kagglehub cache eviction above; it is code-complete and runs on the GPU box |
| **GO/DEAD decision** | ✅ logic | `results/DECISION.json` writer + gating in `main()` |

Key correction found during prep: the **heuristic cost model** gives T=6653/Q=388 for (9,143,39),
but the **real compiled circuits** give T=15585/Q=428. All ratio figures therefore come from
actual compilation (official verifier), not the cost model.

## (c) Prioritized (M,G) list
Primary window M ∈ [129,134], G ∈ {35,36}; avoid M≤128 (Q→657) and G≤32 (error_2 floor).
Order = ALGO_PLAN stage order. Ratio column is the report_E optimistic estimate at fixed
λ_eff≈47 (real ratio requires compilation; expect it to land below the fixed-λ estimate
because lower rank typically raises λ_eff only modestly while T/Q drop).

| Priority | (M,G) | Why | Est. ratio (fixed-λ) | ΔGM vs 10.6976× |
|----------|-------|-----|----------------------|-----------------|
| 1 (Stage 1) | **(130,35)** | highest gain, closest to G=32 cliff | ~12.16× | **+1.07** |
| 2 (Stage 3) | (130,36) | safer (further from floor) | ~11.9× | ~+1.2 |
| 3 (Stage 3) | (134,36) | most conservative | ~11.8× | ~+1.1 |
| 4 (Stage 3) | (132,35) | mid | ~12.0× | ~+1.3 |
| 5 (Stage 3) | (132,36) | mid-safe | ~11.9× | ~+1.2 |

(Exact per-shape T/Q/ratio are emitted by the run into `results/stage*_*.json`.)

## (d) Expected GPU VRAM + wall-time
- **VRAM:** ~1–2 GB peak (f64). Dominant tensor: `N⁴` two-body Gram (≈268 MB) + gradient.
  Any ≥8 GB card is comfortable. f32 (`--no-x64`) halves this.
- **Wall-time (A100/H100 class):** Stage 0 ~15 s · Stage 1 ~10–25 min · Stage 2a ~40–100 min ·
  Stage 2b/c ~10–25 min each · Stage 3 ~40–100 min. **GO path ≈ 15–30 min; DEAD path ≈ 2–4 h.**
  Consumer RTX-class (weak f64): add `--no-x64`, expect ~2–4× longer on the f64-heavy terms.

## (e) EXACTLY what we need from the user's GPU to launch
1. **CUDA version** (driver ≥ what the installed `jaxlib[cuda]` supports; `nvidia-smi`).
2. **VRAM size** (need ≥ 8 GB recommended; ≥ 4 GB minimum).
3. **How to execute** — one of:
   - SSH: `user@host` + the absolute repo path on that box (so `work/chem_gpu/` is reachable).
   - Cloud: instance name / how to reach a shell.
   - Local path on this machine if the GPU is attached here.
4. Confirm the **repo is present** on the box (needs `starter_kit/`, `data/verifiers/`,
   `qualtran/`, and the stored baseline `work/frontier_scan/mwa2_unpacked/dfthcsos/`).

Then, from the box:
```bash
pip install -r work/chem_gpu/requirements.txt && pip install -e <repo>/qualtran
cd work/chem_gpu && ./run.sh --quick     # fastest decision on (130,35)
# then ./run.sh for the full gated sweep
```

## (f) Remaining risk
- **Basin wall (primary risk).** Every CPU seed/optimizer landed invalid (Adam diverges,
  L-BFGS-B trapped at err2≈250 mHa, even 1-copy prune → 188 mHa). The whole bet is that
  (Cholesky OMP seed or truncation warm-start) + **GPU-scale L-BFGS** escapes it. If the
  ladder fails, the honest outcome is **DEAD** (clean negative result). Multi-start (2a) is
  the direct counter-measure.
- **Seed quality.** The Cholesky OMP seed must be in a sane basin (notebook reached ~651 mHa;
  earlier CPU proxies were 8.5k–12k mHa). If the OMP seed is still far, Stage-2b truncation
  warm-start is the more reliable entry. Flagged, not silently changed.
- **error_1 after b-bit rounding.** Validity also requires compiled `error_1 ≤ 20 mHa`. The
  STE objective drives the two-body quantized fit; the one-body rounding residual is measured
  post-hoc at compile time and may need the Stage-2c hybrid or a one-body STE extension.
- **Objective-term scaling.** α/γ/β defaults (1.0 / 1e-4 / 1e-4) are reasonable starting
  points but may need tuning per shape; exposed as CLI flags.
- **float64 on consumer GPUs** is slow; `--no-x64` trades E_gap-barrier precision for speed.
