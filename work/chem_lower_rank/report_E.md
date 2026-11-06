# Chem Benchmark III — lower-rank DF-THC factorization: bounded feasibility probe

**Scope:** determine whether the external advisory's "smaller-rank factorization family"
(M: 143→126/130/134, G: 40→35/36, λ_eff barrier penalty ⇒ claimed Toffolis 15,629→13,200,
Q 428→412, λ_eff 47.05→45.20 ⇒ ratio 13.65× ⇒ GM +2.10) is **feasible on our hardware**
(Apple M3 Max, 16 cores, macOS, **no CUDA**) and **how much it can actually deliver**.
This is a bounded probe, not the full 7-day optimization. No Kaggle submissions made.

Tags: **[FAKT]** measured here · **[HYP]** extrapolated/model-based · **[SPEK]** speculation.

---

## 1. Setup status

| item | value |
|---|---|
| Python | 3.12.7 (`.venv`), 3.13.13 (`.venv-chem`) |
| jax | **0.12.0.1** (installed into `.venv`; already present in `.venv-chem`) |
| optax | **0.2.8** |
| backend | **cpu** (`jax.default_backend()` → `cpu`) — no CUDA, confirmed |
| smoke test | `jnp.ones(3)+1` → `[2.0, 2.0, 2.0]` PASS |
| numpy / scipy | present; official verifier + cost model import cleanly |

**Setup gate: PASS.** JAX/Optax run on CPU. Per-epoch cost measured at **43.9 ms/epoch**
(full params, shape (9,130,36)) **[FAKT]** — so ~2,000 epochs ≈ 1.5 min of pure stepping,
but see §5: convergence (not stepping speed) is the real bottleneck.

---

## 2. Baseline-repro gate — **PASS (exact)**

Official verifier on the current best (`work/frontier_scan/mwa2_unpacked/dfthcsos/`,
submission sha `d8c21eeb…`, npz sha `f5783ebc…`):

| metric | verifier output | published | match |
|---|---:|---:|:--:|
| error_1 | 10.2705 mHa | 10.27 mHa | ✓ |
| error_2 | **19.99965 mHa** | 19.99965 mHa | ✓ exact |
| E_gap | **3.9148992 Ha** | 3.9148992 Ha | ✓ exact |
| λ_eff | **47.0256 Ha** | 47.0256 Ha | ✓ exact |
| Toffolis | **15,585** | 15,585 | ✓ exact |
| Qubits | **428** | 428 | ✓ exact |
| ratio | 3355599588.3 / (47.0256·15585·428) = **10.6976×** | 10.6976× | ✓ |

Independent cross-checks (all agree):
- Numpy continuous metric path (`metrics_np.py`, no JAX): error_2=19.9997 mHa, E_gap=3.9148992, λ_eff=47.0256 **[FAKT]**.
- Cost model `SpinFreeData_V1` (`cost_estimate.py`): outer=317, inner=4086, givens=2250, heur_T=6653, heur_Q=388 — **matches the verifier's reported heuristic block exactly** **[FAKT]**.

**Gate verdict: PASS.** The metric path *and* the circuit-build path (existing `.kmb` angle
circuits + verifier) both reproduce the published numbers to full precision. Results below are trustworthy.

---

## 3. Structural findings (the physics of the problem)

### 3.1 The current best is pinned at the boundary *by design* **[FAKT]**
The continuous (pre-rounding) error_2 of the current best is **19.9997 mHa** — i.e. it already
sits essentially exactly on the 20 mHa acceptance line, and its E_gap=3.9148992 sits just above
the 3.914898 floor. The augmented-Lagrangian refit (notebook §5) deliberately *spent* the error
budget to push error_2 up to 20 in exchange for a lower λ_eff. Its natural fit is ~12 mHa, so
there is ~8 mHa of "error headroom" that was traded away.

### 3.2 Λ is 95% two-body → G is the lever **[FAKT]**
Decomposition of the current best: **λ_H1 (one-body) = 13.133 Ha (4.6%)**, **λ_H2 (two-body) = 271.260 Ha (95.4%)**, Λ=284.39.
Since λ_eff ≈ √(2·E_gap·Λ) with E_gap near its floor, cutting λ_eff means cutting Λ, and 95% of Λ
is the two-body term that scales with the number of (r,c) copies = R·G. **Lowering G directly attacks λ_eff.**
Lowering M (basis width) does *not* attack λ_H2 meaningfully (see 3.4).

### 3.3 There is NO error_2 rank cliff in the advisory grid **[FAKT, analytical]**
Matricizing the symmetry-shifted two-body target T=(pq|rs) gives a symmetric near-PSD matrix M_T.
The best achievable error_2 using K=R·G independent squares is the eigen-tail floor
`√(‖T‖²_F − Σ_{k≤K} λ_k²)` (‖T‖_F = 12.184 Ha, top-400 eigenpairs via ARPACK). This is a **hard lower
bound** on any grouped table's error_2:

| G | K=R·G | error_2 floor |
|--:|--:|--:|
| 39 | 351 | 7.46 mHa |
| 36 | 324 | 10.95 mHa |
| 35 | 315 | 12.81 mHa |
| 33 | 297 | 17.62 mHa |
| **32** | **288** | **20.51 mHa ← cliff** |
| 31 | 279 | 23.71 mHa |

**The error_2 cliff is at G≈32 (K≈288 squares).** The advisory's G=35/36 targets sit **7–9 mHa above**
the cliff with comfortable margin. So the binding constraint (error_2 ≤ 20 mHa) is satisfiable in
principle across the whole advisory grid. (M does not enter this floor at all — see 3.4.)

### 3.4 M (basis width) is *not* free — it sets each group's representable family **[FAKT, corrected]**
A group's copy matrices are X_{r,c} = Σ_b w_b^rc u_b^r(u_b^r)^T over its **shared** basis {u_b^r}. An
*overcomplete* (non-orthogonal) basis of M vectors spans a richer family of squares than a minimal one,
so **larger M → better per-group fit → lower error_2**; M is not redundant once M>76. Evidence:
importance-deleting basis vectors at fixed G=39 raised error_2 from 20 → 124 mHa (M=138), 216 mHa (M=134),
331 mHa (M=130), 460 mHa (M=126) **[FAKT, sub-table sweep]**. The current best (M=143) already pays a
~4.5 mHa grouping/finite-M penalty over the M→∞ floor (natural fit ~12 mHa vs floor 7.46 mHa at G=39).
**Consequence:** the advisory's *joint* M↓+G↓ reduction pushes error_2 up on **two** axes at once, so its
targets are tighter than the §3.3 floor alone suggests — feasible, but the margin must be earned by real
optimization, not assumed.

### 3.5 A *cost-model* qubit cliff at M=128 traps the advisory's M=126 target **[FAKT, validated model]**
The verifier's `SpinFreeData_V1` sets `b2 = ⌈log2(M)⌉ + chi + 1`. At M=128→129 this bit-width jumps
(7→8), which flips the optimal QROM batching (k2opt 5→4) and drops inner temporary qubits 574→303:

| M | b2 | k2opt | inner_temp | total Q (heur) |
|--:|--:|--:|--:|--:|
| 126 | 18 | 5 | 574 | **657** |
| 128 | 18 | 5 | 574 | 657 |
| **129** | **19** | **4** | **303** | **388** |
| 130–143 | 19 | 4 | 303 | 388 |

**M≤128 is charged 657 qubits vs 388 for M≥129.** The advisory lists **M=126** as a target — that lands
squarely in the penalized regime and collapses the ratio to ~8.3× (worse than doing nothing). **Any real
M-reduction must stay at M≥129.** This is a concrete error in the advisory.

---

## 4. Lower-rank results table

Two λ_eff columns: **λ_eff(scaled)** assumes the decomposition's linear-in-G behaviour
(λ_H1 fixed, λ_H2 ∝ G/C) **[HYP]**; **λ_eff(frozen-U)** is the *measured* conservative bound from a
frozen-basis weight refit **[FAKT]**. Toffolis/Q from the validated cost model + linear-in-A angles proxy
(anchored to the measured 8,932 angles-Toffolis at A=1363) **[HYP]**. Ratio = 3355599588.3/(λ_eff·T·Q).

| (M,G) | err_2 floor [FAKT] | λ_eff scaled [HYP] | λ_eff frozen-U [FAKT] | T_est | Q_est | ratio (scaled) | ΔGM vs 10.6976× |
|---|--:|--:|--:|--:|--:|--:|--:|
| (143,39) base | 7.46 m | 47.03 | 47.03 | 15,585 | 428 | 10.70× | +0.00 |
| (143,36) | 10.95 m | 45.26 | ~59 (inv.) | 15,319 | 428 | 11.31× | +0.46 |
| (143,35) | 12.81 m | 44.65 | — | 15,232 | 428 | 11.53× | +0.62 |
| (134,36) | 10.95 m | 45.26 | — | 14,770 | 428 | 11.73× | +0.76 |
| (134,35) | 12.81 m | 44.65 | — | 14,683 | 428 | 11.96× | +0.93 |
| **(130,35)** | **12.81 m** | **44.65** | — | **14,439** | **428** | **12.16×** | **+1.07** |
| (130,36) | 10.95 m | 45.26 | — | 14,526 | 428 | 11.93× | +0.90 |
| (126,35) ⚠ | 12.81 m | 44.65 | — | 12,883 | **697** | 8.37× | **−1.92** |
| (126,36) ⚠ | 10.95 m | 45.26 | — | 12,925 | **697** | 8.23× | −2.05 |

⚠ M=126 rows are trapped by the §3.5 qubit cliff (Q=697) — **do not pursue M=126**.

**error_1 and E_gap for the feasible shapes:** in the continuous limit error_1≈0 (the one-body rows are the
exact h1_prime eigenvectors); after 8-bit rounding it lands near the baseline's **~10 mHa** (well under the
20 mHa one-body gate), so **error_1 is never the binding constraint — error_2 is**. E_gap is pinned at the
barrier floor **≈3.9152 Ha** by the penalty for every valid shape (the current best sits at 3.9148992, just
above the verifier's 3.914898 strict floor). These two columns are therefore shape-independent and omitted
from the table above.

**Reading:** the single best *advisory-grid* shape avoiding the qubit cliff is **(130,35)** at an optimistic
**12.16× (ΔGM +1.07)**; the safer, higher-error-margin shapes cluster at **(134,36)=11.73× / (130,36)=11.93× /
(134,35)=11.96×** (ΔGM +0.76 to +0.93). All of these assume the *scaled* λ_eff holds — which our CPU runs could
not confirm (§5). The advisory's headline **13.65× / +2.10 GM is not reproduced**: it requires either M=126
(trapped by the qubit cliff) or ~2× more Toffoli reduction than the standard cost model yields at these shapes.

---

## 5. Training feasibility on the Mac (CPU)

- **Stepping is cheap** (43.9 ms/epoch) but **convergence is the wall — and it is a *seeding / local-minimum*
  wall, not a speed wall.** **[FAKT]**
- **Raw Adam diverges** from a far truncation seed: (9,130,36) went err2 836→90 mHa then **exploded to
  3,794 mHa at epoch 500**; best point after 1,500 epochs still invalid (err2 79.6 mHa). **[FAKT]**
- **Frozen-U weight refit** (U held at the current best, only W/H2_I moved) is stable but conservative:
  at G=36, 2,500 epochs → best **err2 44.1 mHa (still >20, invalid)**, **λ_eff ≈ 59** (worse than 47),
  Λ *rose* 284→312. Dropping copies forces the surviving weights to grow, raising λ_H2. **[FAKT]**
- **Full-parameter L-BFGS-B** (JAX grads, scipy line search) from the importance-truncation seed at
  (9,143,36): **converged in 167 function evals** (fast!) **but to a trapped local minimum** — best
  **err2 = 249.7 mHa** (12× over the limit), λ_eff 47.06, E_gap 3.9160, Λ 284.71, `valid_err2=False`.
  The deleted copies' information cannot be recovered by re-weighting the survivors; the optimizer settles
  where the gradient vanishes, far from a valid solution. **[FAKT]**
- **Progressive one-copy reduction also traps.** Dropping just *one* copy (G=39→38) from the current best
  already jumps the seed to **err2 = 285 mHa**; full L-BFGS-B then terminates (nfev=136) at **err2 = 188.5 mHa**
  (still 9× over the limit, `valid_err2=False`; λ_eff 47.03, E_gap 3.9160, Λ 284.31). The current best is a
  **razor-thin corner solution**: every single copy is load-bearing, so *no* lower-rank table can be derived
  from it by pruning — a valid lower-G table must be built **from scratch** with the notebook's compact seed. **[FAKT]**
- Every seed available to us (random, importance-truncation, frozen-U, one-copy-prune) lands in an **invalid basin**
  (err2 44–285 mHa). The notebook reached valid tables only with a **purpose-built compact
  Cholesky-clustered seed** (~651 mHa start, in the right basin) refined by **L-BFGS, 8 rounds × 60k
  iterations, on an A100/GPU** (~480k line-search iterations). That pipeline is **not present locally** and
  is **not affordable on this Mac CPU**. **[HYP from notebook + FAKT local failure]**

---

## 6. Rank-cliff location

- **error_2 floor cliff: G ≈ 32** (K ≈ 288 squares; the M→∞ floor crosses 20 mHa between G=33 and G=32). **[FAKT]**
- **finite-M penalty:** at any fixed G, reducing M raises error_2 above the floor (§3.4); the current best
  already pays ~4.5 mHa of this at M=143. So the *practical* error_2 cliff for a reduced-M table is at a
  **higher G** than 32 — the exact location needs a real (GPU-scale) optimization we cannot finish here. **[HYP]**
- **cost-model qubit cliff: M = 128** (M≤128 → 657 Q vs 388 for M≥129). **[FAKT]**
- The advisory's feared "hard rank cliff where M<138 cannot satisfy error_2≤20" is **not confirmed as a hard
  wall**: the M→∞ floor leaves 7–9 mHa of margin at G=35/36. But it is **not confirmed as safely clearable
  either**, because (a) finite-M adds error_2 pressure on top, and (b) every CPU seed we tried got trapped in
  an invalid basin (err2 44–250 mHa). The real cliffs are (i) G≈32 + finite-M margin for accuracy, and
  (ii) M=128 for qubit cost — neither where the advisory looked.

---

## 7. VERDICT — **PARTIAL** (feasible in principle; **not deliverable on this Mac CPU with available tools**)

**The plan is mathematically sound but the advisory's headline is not supported, and our hardware cannot close
the gap.**

1. **No hard accuracy wall in the advisory grid** — the M→∞ error_2 floor stays ≤20 mHa down to G≈32, so
   G=35/36 have 7–9 mHa of margin *before* finite-M penalties. **[FAKT]**
2. **But we cannot actually reach a valid lower-rank table on this Mac.** Every seed available locally
   traps in an **invalid basin**: Adam diverges (err2→3,794 mHa), frozen-U stalls at err2 44 mHa / λ_eff≈59,
   full L-BFGS-B "converges" to err2 249.7 mHa, and even pruning a *single* copy (G=39→38) leaves err2 188.5 mHa.
   The current best is a razor-thin corner solution; a valid lower-rank table must be built from scratch with the
   notebook's **compact Cholesky-clustered seed + GPU-scale L-BFGS (8×60k iters)** — neither present nor
   affordable here. **[FAKT]**
3. **The λ_eff gain is real in direction, unconfirmed in size.** 95% of Λ is two-body, so G↓ should cut
   λ_eff; the decomposition predicts λ_eff≈44.65–45.26 at G=35/36 (matching the advisory's 45.20), **but**
   the only runs we could complete show weights growing and λ_eff *rising* (~59) when U can't fully adapt.
   The true value sits somewhere in between and only a full GPU-scale optimization settles it. **[HYP]**
4. **The advisory's M=126 target is wrong** — it lands in the cost-model qubit cliff (657 Q vs 388) and would
   score ~8.3×, worse than the status quo. Retarget **M∈[129,134]**. **[FAKT]**
5. **Best realistic outcome if the full pipeline were run:** ratio **~11.3–12.2× (ΔGM ≈ +0.5 to +1.1)**,
   centred on (M≈130, G=35). The advisory's **13.65× / +2.10 GM is not reproduced** — it leans on the trapped
   M=126 and ~2× more Toffoli reduction than the standard cost model yields. **[HYP]**

**Effort to deliver a *verified* lower-rank submission:**
- **On this Mac CPU alone: not practical.** The binding cost is GPU-scale L-BFGS convergence from a compact
  seed (~480k line-search iterations per shape; ~5–8 h CPU *per shape* even if it converged, which our seeds
  show it does not) plus a **local circuit builder we lack** (`dqi_full/` ran on Kaggle/Linux; the notebook's
  `build/encode/quantize` pipeline is absent). Realistic total if forced onto CPU: **~1 week**, high risk of
  ending in invalid basins, for ΔGM ≈ +0.5 to +1.1.
- **With a borrowed GPU + the notebook pipeline ported:** ~1–2 days of compute for a few shapes, ΔGM ≈ +0.5
  to +1.1 (optimistic upper end ~+1.1 at M=130/G=35).

**Recommendation:** do **not** pursue the advisory as stated (M=126, 13.65×). If the team wants the upside,
the correct, de-risked plan is: (a) retarget **(M=130–134, G=35)**; (b) first confirm the λ_eff drop with one
*full* (unfrozen) L-BFGS convergence at G=36 on a **GPU** using the notebook's compact seed; (c) stand up the
local circuit builder before committing to the multi-shape sweep. The cheapest immediate experiment is to check
whether the *existing* M=143 table recompiles cheaper at effective M≥129 — but note §3.4 shows its basis vectors
are load-bearing, so that too needs a refit, not a deletion.

---

## Artifacts (all under `work/chem_lower_rank/`)
- `metrics_np.py` — numpy-only metric + cost path (validated against the verifier).
- `eigen_cliff.py` + `eig_top.npz` — matricized-target top-400 eigenpairs; rank floor.
- `cliff_location.py` — error_2 cliff scan (G≈32).
- `decompose_lambda.py` — λ_H1/λ_H2 split (95.4% two-body).
- `debug_cost.py` — the M=128 qubit-cliff components.
- `cost_estimate.py` — T/Q/ratio table for advisory shapes.
- `train_probe.py`, `refit_g.py`, `train_lbfgs.py` — CPU trainers (Adam / frozen-U / L-BFGS-B; `--start` chains steps).
- `sweep_subtables.py`, `build_grouped.py`, `compact_seed.py` — seed/construction experiments (the grouped/eigen seeds all failed to respect the shared-basis constraint → err2 700–58000 mHa; kept as negative evidence).
- trained/seed outputs: `run_130_36.npz` (Adam, diverged), `refit_143_36.npz` (frozen-U), `lbfgs_143_36.npz` (L-BFGS, trapped), `prog_38.npz` (one-copy prune, trapped), `seed_*.npz` (eigen seeds).
- logs: `log_130_36.txt`, `log_refit_36.txt`, `log_lbfgs_143_36.txt`.
