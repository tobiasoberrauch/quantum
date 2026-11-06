# Report H — Feasibility & Roadmap: Solo Reconstruction of the DQI Circuit Builder

**Scope:** determine IF and HOW we can reconstruct a *modifiable* DQI builder from scratch
(no private base) so we can (i) reproduce the current best circuit `fc3ba816` and (ii) apply the
known optimization levers — entirely solo, within ~78 days. **This is a scope/feasibility report,
not an implementation.** Nothing was built or submitted.

**Target (ground truth):** `work/frontier_scan/mwa_unpacked/dqi.kmb` · sha256
`fc3ba81614e1016f7fbc6c58bc229243fc0c26aa5de601caef7d280e7d14dad9` · Q=891 · static T=397,194 ·
mean T=396,921.5 · R=1.1913 · score=3.754e11 · ratio **65.1066** `[FAKT]` (Report A §1).

**Tag legend:** `[FAKT]` = directly measured here or read from an official artifact ·
`[HYP]` = reasoned from structure/source, not independently confirmed · `[SPEK]` = estimate,
order-of-magnitude only.

---

## 0. Verdict (BLUF)

- **Solo reconstruction to a state where we can *bank* the inverse-overhead lever (i.e. produce a
  circuit that beats `fc3ba816`) is INFEASIBLE within ~78 days.** The gate is reaching
  near-parity (pre-lever ratio ≳ 57), which requires re-implementing somejoint's private
  tower-field + pebbling/width IP. That is a research-level effort exceeding the window. `[SPEK]`
- **A correct, modifiable shadow decoder is trivially available today** — the public
  `data/verifiers/dqi/dqi_reference_circuit.py` builds one in 22 s and it is functionally correct
  (0 value/phase errors). But it is **Q=1893, static T=5,725,461** — ~65× worse than `fc3ba816`.
  Optimizing it toward parity *is* the mwa project. `[FAKT]` (my build)
- **The 25 public deltas are NOT standalone builders.** They are monkey-patch layers
  (`private_rebind(cv, p.base.replacements, p.ROOT)`) over a private `ported`/`p` base whose
  `playbook/kit/` + `exp/decoder/` tree is **absent from the repo**. None of the deltas can run
  without rebuilding that base. `[FAKT]` (code inspection + `find`)
- **Recommended path:** merge with somejoint as the PRIMARY route to banking the lever (he has the
  builder today). Run a **parallel solo shadow-decoder build (option c)** as de-risking + merge
  leverage + a publishable artifact, targeting a correct tower-field decoder at ratio ~5–15 in
  30–45 person-days. Do **not** commit to full bottom-up parity reconstruction (option a) as the
  primary path. `[SPEK]`
- **Merge-vs-reconstruct crossover:** merge dominates immediately. Reconstruction becomes the
  primary path only if the merge fails by ~Nov 15–20 *and* we relax the goal from "beat `fc3ba816`"
  to "have a modifiable builder + artifact + leverage." `[SPEK]`

---

## 1. Asset audit — what we actually have (and the pivotal discovery)

### 1.1 The reference decoder is a runnable shadow builder `[FAKT]`

`data/verifiers/dqi/dqi_reference_circuit.py` (public, ships with the verifier) contains a complete
standalone Reed–Solomon MBUC decoder built directly on kickmix:

- `ProosAndZalkaDecoder.build_syndrome_decoding_mbuc(...)` — three stages: forward synchronized
  Extended Euclidean Algorithm (EEA) → Chien search + Forney MBUC phase → reverse synchronized EEA.
- `build_reference_circuit(m=4095, n=70, degree=12)` → a full `km.Circuit`.
- Uses kickmix subs: `gf2_iadd`, `gf2_imul`, `gf2_idiv`, `init_gf2_div_with_scaffold`,
  `del_gf2_div_with_scaffold`, `init_gf2_inverse_with_scaffold`, `ixor_gf2_mul`,
  `gf2_phase_by_product`, `unary_iteration`, `cswap`, `flip_if_equal/less_than`, `iadd/isub`,
  `left/right_rotate`, `bit_store`, `push/pop_condition`.

I built it (`.venv/bin/python`, 22 s) and ran the official verifier on 256 shots:

| metric | reference decoder | `fc3ba816` (target) | ratio |
|---|---:|---:|---:|
| Q (num_qubits) | **1893** | 891 | 2.12× wider |
| static Toffoli-like | **5,725,461** | 397,194 | 14.4× more |
| num_ops | 86,051,014 | 58,336,043 | 1.48× |
| reaction_depth | 170,757 | 5,867 | 29× deeper |
| value/phase errors (256 shots) | **0 / 0** (correct) | 0 / 0 | — |

The 256-shot run reports `status: FAIL` **only** because the Clopper–Pearson bound at n=256 is
eps_plus≈0.293 even with zero errors (see §5.3); the circuit itself is functionally correct.

**Gap decomposition (clean):** `(1893/891)² × (5.725e6/3.972e5) = 4.49 × 14.41 = 64.7 ≈ 65.1`.
So somejoint's 65× advantage over the published baseline splits into **4.49× from width**
(pebbling/lifetime scheduler) and **14.4× from Toffoli count** (tower-field arithmetic + efficient
kernels + algorithm choice). Both factors live in the private base. `[FAKT]` arithmetic on measured
numbers; `[HYP]` attribution of each factor.

**Implication:** the competition baseline (reference numerator 2.444e13, Report A §1) is
≈ the reference decoder (implied ratio ~1.2). `fc3ba816` is a 65× improvement over the naive
published algorithm. Solo reconstruction must close most of that 65× to be useful. `[SPEK]`

### 1.2 The target circuit's block structure `[FAKT]` (measured here)

Extracted all INFO_TAG labels from the `.kmb` (`work/dqi_builder_recon/list_info_tags.py` →
`info_tags.json`). **23 semantic blocks** (each emitted as `@enter:`/`@exit:` pairs = 46 raw tags,
matching the task's "46 named blocks"). Top-level phases (11) + recurring kernel sub-tags (12):

| semantic block | occ | stream frac | role |
|---|--:|---|---|
| mask_projection | 1 | 0.000–0.041 | phase-only setup (0 Toffolis) |
| initial | 1 | 0.041–0.045 | syndrome load (CX only) |
| **extract** | 1 | 0.045–0.113 | forward extraction (59,595 T) |
| **synthesis** | 1 | 0.113–0.206 | error-locator/evaluator synthesis (31,637 T) |
| **convert** | 1 | 0.206–0.304 | representation convert (60,796 T) |
| **scan** | 1 | 0.304–0.706 | Forney scan / Chien (44,275 T) |
| **unconvert** | 1 | 0.706–0.796 | inverse convert (62,711 T) |
| **unsynthesis** | 1 | 0.796–0.894 | inverse synthesis (40,556 T) |
| **unextract** | 1 | 0.894–0.994 | inverse extraction (**97,624 T**) |
| uninitial | 1 | 0.994–0.998 | syndrome HMR measure-out |
| restore_masks | 1 | 0.998–1.000 | final cleanup |
| inverse24 {norm,scalar,products} | 29 each | within extract | 24-bit inverse tower |
| inverse12 {norm,scalar,products} | 169 each | across fwd+inv | `phase_inverse12_quantum64` |
| multiply v | 12 | within extract | classical-conditioned field multiply |
| aligned_route | 26 | convert/unconvert | converter routing helper |
| full_head_product | 3 | convert/unconvert | head product schedule |
| gf_iadd | 8050 (scan) + 186 (unextract) | scan/unextract | `gf2_iadd` (kickmix sub) |
| head_pivot / head_phase | 24 / 3 | unconvert | head pivot/phase schedules |

Forward half (extract+synthesis+convert+scan) = 196,303 T (49.4%); backward half
(unconvert+unsynthesis+unextract) = 200,891 T (50.6%). Matched-pair inverse overhead:
**unextract +38,029 · unsynthesis +8,919 · unconvert +1,915 = +48,863 total (12.3% of T)** `[FAKT]`
(Report A §3.1).

### 1.3 The 25 deltas are patches, not builders `[FAKT]`

Import analysis (`work/dqi_builder_recon/analyze_imports.py` → `import_analysis.json`): the 25 deltas
(+ `width_liveness.py`) import **61 distinct private modules** after deduplicating local cross-imports
(`division`, `lowwidth`, `frozen_chart`, `overlap_prefix`, `scalar_compact_v3`, `local_norm`) and
stdlib. Representative call sites prove the patch pattern:

```python
# blocked_three_noscratch.py
cv = p.install_dot_cache(p.install_base_zero(p.install_undo_zeros(
        p.install_child_inverse(p.install_retained_gaps(p.make_converter())))))
cv = private_rebind(cv, p.base.replacements, p.ROOT)

# scalar_compact_v3.py
cv      = private_rebind(p.convert_safe, p.base.replacements, p.ROOT)
decoder = private_rebind(p.install_factorized_boundary(decoder), p.base.replacements, p.ROOT)
```

Every delta reaches into `ported` (`p.*`) / `exp.decoder.*` / `field` / `common` — none of which
exist locally. `direct_forney.py` sets `ROOT = Path(__file__).resolve().parents[3];
sys.path[:0] = [ROOT/'playbook/kit', ROOT/'playbook/kit/decoder']`; `find . -type d -name playbook`
and `-path "*exp/decoder*"` return **nothing**. The base tree is genuinely absent. `[FAKT]`

---

## 2. Module inventory & dependency graph

Grouping the 61 missing modules by **functional capability** (many names are aliases of the same
underlying functionality) yields **4 build layers**. Build order is bottom-up; each layer depends on
all layers below it.

### Layer 1 — Field-arithmetic core (GF(2^m) + tower) `[HYP]` scope, `[FAKT]` API surface
The foundation everything else calls. Modules: `field`, `exp.decoder.common`, `common`, `kernels`,
`exp.arithmetic`, `exp.arithmetic.division`, `exp.arithmetic.lowwidth`, `virtual_norm`,
`lowclean_norm5`, `structured_log65`, `constant_scale`, `logscale7`, `schur_scalar`.

Required API (inferred from call sites across `division.py`, `direct_forney.py`, `lowwidth.py`):
- Constructors/decomposition: `field(n)`, `tower(n) -> (to, frm, K)`, `extension_columns()`,
  `square_columns(k)`, `inverse_columns(cols)`, `bits(x)`, `tensor(n)`.
- Quantum primitives: `mul_xor(b,x,y,z)`, `phase_product(b,x,y,mask)`, `linear_inplace(b,x,M)`,
  `linear_xor(b,x,out,M)`, `inverse(b,x)`, `erase_product`, `erase_inverse`.
- Internal tower helpers: `_norm_xor`, `_inverse_keep_norm`, `_erase_inverse_with_norm`,
  `_erase_norm`, `_phase_norm`.
- Classical-conditioned: `zero_flag`, `phase_zero`, `classical_transpose`, `combine`, `cx`,
  `divmodp`, `eev/einv/emul/pmul`, `linear_words`, `K`, `gf`, `mul/inv/power/scale`,
  `zero_hold/zero_free`.

**Estimate: 1,500–3,000 LOC.** This is well-understood math (quadratic tower
GF(((2²)²)³)); `division.py` already gives concrete tower mul (105 T) and div (321 T) schedules to
port. Lowest risk of the four layers. `[SPEK]`

### Layer 2 — Inverse/multiply/divide/norm kernels `[HYP]` scope
Modules: `exp.jet24.kernel` (`phase_inverse12_quantum64`), `exp.jet24` (`jet`: RAW, TO6),
`exp.mul99.kernels` (`mul24_xor99`), `exp.mul99.phase36` (`phase_classical_parity`,
`phase_inverse36_pivot`), `exp.mul99.schedules` (`multiply_forward99`, `divide_zero_bridge414`,
`divide_lowwidth369`, `multiply_zero_forward99`), `exp.inverse19_joint.kernel`
(`inverse_initialized`), `exp.inverse_search` (`inverse3_virtual`, `norm_forms`, `expose_pair`),
`exp.fold_cached_norm.phase34` (`phase_inverse34`), `exp.noscratch.kernels`
(`mul_xor_noscratch`), `exp.noscratch.schedules` (`norm_xor_noscratch`,
`inverse_stream_noscratch`, `classical_transpose`), `norm_cache`, `exact_subs`
(`phase_inverse12_virtual_nonzero`, `phase_inverse6_quad4`, `inverse6_joint18_12extra`, SCALES,
UNSCALES).

These are the expensive cores behind the `inverse12`/`inverse24`/`multiply v` sub-tags. `division.py`
shows the inverse recursion (`erase_inverse_releasing`, 9/45/153 T recursion) and the norm-based
divide. **Estimate: 2,000–4,000 LOC.** Medium risk — the exact width/pebbling choices per kernel
are not fully recoverable from the deltas. `[SPEK]`

### Layer 3 — Decoder stages (the algorithm) `[HYP]` scope, **highest risk**
Modules: `exp.decoder` (base: `vandermonde`, `embedding_matrix`, `evaluation_coefficients`,
`expose_eval`, `quotient_terms`, `ck`), `exp.decoder.extract` (`constants`), `exp.decoder.synthesis`,
`exp.convert_short_hankel` (`q_inverse`, `_short_scope`), `exp.partial_gauge` (`forward`,
`reverse_compact`, `boundary_forward/reverse`, `zero_compact[_free]`), `exp.partial_gauge.scalar`
(`divide117`), `exp.partial_gauge.tail` (`divide_safe138`, `multiply_safe165`,
`controlled_linear_xor`), plus flat helpers `column_double_tail`, `column_hole`, `pivot_bridge`,
`pivot_rotate`, `homogeneous_pivot`, `homogeneous_update`, `jet_character`, `gauge_return`,
`block_phase`, `streamed`, `retained_core_safe27`, `core90`.

These emit the **extract / synthesis / convert / scan** top-level blocks. `direct_forney.py` gives
the *scan* structure (`scan()` → `root_character()` × 4095 → `phase_inverse12_quantum64`), but it is
a *candidate* fusion, not the shipped generator (Report A §2 note). extract/synthesis/convert live
only in the missing base. **Estimate: 3,000–6,000 LOC.** Highest risk — this is the core algorithmic
IP; the deltas reveal API + partial logic but not the stage bodies. `[SPEK]`

### Layer 4 — Builder glue + width/pebbling scheduler + patch mechanism `[HYP]` scope
Modules: `ported` (`make_converter`, `convert_safe`, `decode`, `install_base_zero`,
`install_child_inverse`, `install_dot_cache`, `install_factorized_boundary`,
`install_retained_gaps`, `install_undo_zeros`, `triple_square_phase`, `base.replacements`, `ROOT`),
`ported_exact_cycle`, `final_decoder` (`_bez_monic`, `external_chain_step`, `external_scalar_step`,
`external_square24`, `guarded`), `final_decoder.conversion` (`clear_flag`), `converter` (`clone`),
`direct_kernels` (`selected`, `shifted_conv`, `shifted_product`), `measured_heads` (`make_converter`),
`decode_combo`, `decode_q8q9`, `rebind_graph` (`private_rebind`), `reverse_root_lifetime`,
`scalar_projection_multi`, `replay_erase`, `padded_fused_return`, `baseline`.

This is where the circuit is assembled **and** where the pebbling/lifetime/width decisions that
produce Q=891 are made. The `private_rebind` mechanism is how the deltas hot-swap functions.
**Estimate: 2,000–4,000 LOC + the width scheduler (hard to bound).** Highest *uncertainty* — the
scheduler is not visible in any delta. `[SPEK]`

### Total & build order
- **Bottom-up order:** Layer 1 (field) → Layer 2 (kernels) → Layer 3 (decoder stages) →
  Layer 4 (glue + width scheduler + rebind). Each layer validated before the next.
- **Grand total: ~8,500–17,000 LOC** of intricate quantum-circuit code, plus the width scheduler.
- **Validation oracle:** the `.kmb` gate streams (ground truth) for block-level structural checks,
  and the **official verifier** (correctness + T/Q) as the authoritative gate. Bit-exact reproduction
  of `fc3ba816` is neither required nor realistic; the bar is a *correct* circuit with T/Q ≤ target.
  `[HYP]`

---

## 3. Block → module mapping

Using §1.2 (blocks) + §2 (layers) + Report A §2 (source attribution):

| block | emitting module(s) | layer | re-implementable from public deltas alone? |
|---|---|---|---|
| mask_projection / initial / uninitial / restore_masks | `ported` glue (setup/load/HMR-out) | 4 | No (glue), but trivial logic (0 Toffolis) |
| **extract** | `exp.decoder.extract` (+ `companion.py`, `audit.py`, `nonzero_consume16.py` patches) | 3 | **No** — stage body in base; deltas are patches |
| **synthesis** | `exp.decoder.synthesis` (+ `synthesis_noflag.py`, `norm_deferred_flag_return.py`) | 3 | **No** — stage body in base |
| **convert** | `exp.convert_short_hankel` / `ported.convert_safe` (+ `conversion.py`, `direct_converter.py`, `convert.py`) | 3 | **No** — `convert_safe` body in base |
| **scan** | Forney loop (`direct_forney.py` `scan`/`root_character`) + `exp.decoder.common` + `exp.jet24.kernel` | 2+3 | **Partially** — structure is public, but needs Layer 1 field core + Layer 2 inverse kernel |
| **unconvert / unsynthesis / unextract** | adjoint of convert/synthesis/extract (base emits the `un*` via the reuse/recompute scheduler) | 3+4 | **No** — the inverse overhead *is* the scheduler behavior we want to change |
| inverse12 {norm,scalar,products} | `exp.jet24.kernel.phase_inverse12_quantum64` (+ `local_norm.py`, `narrow_gauge.py`, `lowwidth.py`) | 2 | **Partially** — recursion visible in `division.py`; exact schedule in base |
| inverse24 {norm,scalar,products} | 24-bit inverse tower (`division.py`, `inverse20.py`) | 1+2 | **Mostly** — `division.py` is the closest public artifact |
| multiply v | classical-conditioned field multiply (`direct_forney.classical_product`) | 1 | **Mostly** — public |
| aligned_route / full_head_product / head_pivot / head_phase | converter routing/head schedules (`direct_converter.py` + base) | 3+4 | **No** — schedules in base |
| gf_iadd | `gf2_iadd` — **kickmix sub, public** | (kickmix) | **Yes** — already available |

**Summary:** no top-level block is fully re-implementable from the public deltas alone. The recurring
kernels (inverse24, multiply v, gf_iadd) are the most recoverable; the extract/synthesis/convert
stage bodies and the width/pebbling scheduler are locked in the missing base. `[HYP]`

---

## 4. Reconstruction strategy options, ranked

Ranked by (expected value ÷ effort) for the *actual goal* (bank a lever that beats `fc3ba816`).

### Option (c) — Shadow builder (RECOMMENDED as the solo track) `[SPEK]`
Build a **new** decoder from the published algorithm targeting the same spec, then optimize.
**Starting point already exists:** `dqi_reference_circuit.py` (Q=1893, T=5.7M, correct).

- **Plan:** (1) keep the reference as the correctness backbone; (2) swap its kickmix GF(2¹²)
  arithmetic for **tower-field** GF(((2²)²)³) schedules ported from `division.py` (Layer 1);
  (3) add a basic **pebbling/lifetime pass** to cut Q toward ~1000–1200; (4) instrument and apply
  the levers (§5) on our own modifiable code.
- **Effort:** correct+tower-field at ratio ~3–10: **15–25 person-days**; width-optimized at ratio
  ~10–20: **40–60 person-days**. `[SPEK]`
- **Validation:** incremental — each layer checked against classical field tables (kickmix
  `GF2Field`) on random inputs, then the full official verifier (102,400 shots) at each milestone.
  Block-level structure compared to the `.kmb` as a sanity reference (not a bit-exact gate).
- **Risk:** LOW for correctness (reference is proven); MEDIUM for reaching useful efficiency.
  **Critical caveat:** even at ratio ~20, applying the inverse lever (~×1.14) yields ~23 — still far
  below 65. So option (c) **does not by itself beat `fc3ba816`**; its value is modifiability,
  lever prototyping, a publishable artifact, and merge leverage. `[SPEK]`

### Option (b) — Hybrid (kickmix subs for arithmetic, re-implement control flow + scheduler) `[SPEK]`
Reuse kickmix `gf_arithmetic`/`iadd`/`lookup`/`multi_control_x`/`unary_iteration` for the arithmetic
cores; re-implement only the decoder control flow + pebbling/uncompute scheduler.

- **Reality check:** kickmix `gf_arithmetic` is **direct GF(2^m)**, not tower-field. The tower-field
  advantage (free-CNOT basis isomorphism) is *not* in kickmix — it is somejoint's custom work
  (`division.py`). So option (b) degenerates into "option (c) + reinvent the tower field + reinvent
  the width scheduler," i.e., it still must close the 14.4× T and 4.49× Q gaps.
- **Effort:** to parity, **70–120 person-days**, HIGH risk (same critical path as (a)). `[SPEK]`
- **Verdict:** not meaningfully cheaper than (a) for the parity goal; only sensible as a *partial*
  path that stops short of parity (≈ option c's ceiling).

### Option (a) — Full bottom-up reimplementation, validated block-by-block against the `.kmb` `[SPEK]`
Rebuild Layers 1→4 to reproduce `fc3ba816`'s architecture (extract/synthesis/convert/scan +
tower field + pebbling at the Q=891 knee), then apply levers.

- **Effort:** **90–150 person-days** to reach parity (ratio ≳ 57) and bank the lever. Exceeds the
  78-day window for a solo engineer with high probability.
- **Validation:** block-by-block against the `.kmb` gate streams (structural) + official verifier
  (authoritative). Bit-exact match is not required; T/Q ≤ target is.
- **Risk:** HIGH. Two independent hard sub-problems must both succeed: (i) recover the 14.4×
  Toffoli efficiency (tower field + kernels + algorithm), and (ii) recover the 4.49× width
  efficiency (pebbling/lifetime scheduler — **not visible in any delta**). Failure of either caps
  us below parity.
- **Verdict:** the "pure" answer to the task, but the least efficient use of 78 days given the goal.

### Ranking for the goal
**(c) > (b) > (a)** for *expected value per day within 78 days*, because (c) reaches a correct,
modifiable, lever-testable decoder fastest and its ceiling is bounded by the same parity wall that
(a)/(b) hit — but (c) gets us there with far less risk and produces leverage either way. Only if we
explicitly accept "beat `fc3ba816` or nothing" does (a) become the target, and even then it is
likely infeasible in-window. `[SPEK]`

---

## 5. Lever integration plan (once a modifiable builder exists)

Score sensitivity: ratio ∝ 1/T, GM ∝ ratio^{1/3}. Base ratio 65.1066, GM contribution 24.46794.
Report A §4 arithmetic reused.

### 5.1 Inverse-overhead removal — THE lever `[FAKT]` pools, `[SPEK]` capture
- **Target:** the +48,863 Toffolis (12.3% of T) carried by `un*` over their forwards. Start with
  **unextract** (+38,029, the largest single gap).
- **Mechanism (two variants):**
  1. *Retain-don't-reuse:* keep the forward's intermediate registers alive across the middle so the
     inverse replays the forward in exact reverse (uncompute = forward cost). Trades T for Q —
     **net-negative here** because Q is at the strict knee (§5.4). Reject as primary.
  2. *Shared pebble tree:* schedule the inverse to reuse the same pebbled values the forward
     produced, eliminating the recompute, at **no peak-width cost**. This is the viable variant and
     is exactly what a modifiable uncompute/pebbling scheduler enables.
- **Expected delta (ceiling):** remove full +48,863 → T′≈348,094 → ratio 74.22 → GM 25.56
  (**+1.09 GM**). Realistic capture 50–80% (some inverse work is irreducible — the MBUC phase p(s)
  emission is inherently one-directional) → **+0.5 to +0.9 GM**. `[SPEK]`
- **Verify:** rebuild → quick correctness run (≥2048 shots, expect 0 val/phase err) → full
  102,400-shot official verifier for the true R·Q²·T. Note the seed is derived from the circuit
  SHA-256, so **every modified circuit draws its own deterministic test set** — no shot-by-shot diff
  against the original is possible; rely on full re-verification. `[FAKT]` (verifier source)

### 5.2 De-pebbling `[FAKT]` pool, `[HYP]` realizable fraction
- **Pool:** 267,210 CCX (69.8% of CCX) are recomputed-not-held.
- **Catch:** holding a pebbled intermediate on an idle wire requires a wire that is |0⟩ for the
  intermediate's whole lifetime. WIDTH_ANALYSIS §4 shows the 30 passive-holders are **value-live
  through the stream** (coverage 1.00) and the 10 churners are |0⟩ only 0–2% of scan — so truly-idle
  wires are scarce. Realizable fraction is therefore **low/uncertain**; this lever is likely small
  (Report A marks it `[SPEK]`). Prototype after 5.1. `[HYP]`

### 5.3 Verification gotcha: R is shot-count-dependent `[FAKT]` (measured)
`R(eps) = ln2 / -ln(1/2 + 2√eps)`; `eps_plus` (Clopper–Pearson, log2_delta=−128) shrinks with n, so
R is strongly shot-count-dependent even at zero errors. Computed: n=256 → eps_plus≈0.293 (FAILS the
<1/16 gate); n=2048 → eps_plus≈0.042, R≈7.5 (passes gate but score inflated ~6×); **n=102,400 →
eps_plus≈8.7e-4, R≈1.19** (matches `fc3ba816`). Therefore:
- **Correctness smoke:** any n with 0 errors (even 256) proves no value/phase bug.
- **True score/R:** **must use 102,400 shots** (the default). Never compare scores across runs with
  different n. `[FAKT]`

### 5.4 Width is the binding constraint (why retain-don't-reuse loses) `[FAKT]`/`[HYP]`
WIDTH_ANALYSIS (892-Q sibling, same architecture): Q is a **strict lower bound** under three
independent liveness models; break-even for freeing k qubits ≈ k·893 Toffolis; every measured
free-qubit scenario is net-negative except the late-start trio (889/890/891, +0.054 GM, ΔT≈0).
So any lever that trades T for Q is capped; the inverse lever must be the **no-width-cost** variant
(5.1.2). `[HYP]` extends the 892-sibling conclusion to the 891 target.

### 5.5 Tower-field & trace-folded parity `[HYP]`
Tower-field arithmetic (GF(((2²)²)³)) is **already inside `fc3ba816`** (it is part of what we would
*reproduce*, not a new lever to apply on top). Trace-folded parity + HMR uncompute of intermediate
registers is a further optimization to prototype once the builder is modifiable; expected delta
unknown, treat as secondary. `[HYP]`

---

## 6. Honest verdict, critical path, minimum viable milestone

### 6.1 Is solo reconstruction feasible in ~78 days to bank the inverse-overhead lever?
**No — infeasible with high confidence for the *banking* goal.** Banking the lever means producing a
circuit that beats `fc3ba816` (post-lever ratio > 65.1), which requires pre-lever ratio ≳ 57, i.e.
near-parity. Near-parity requires closing a 65× gap over the published baseline that decomposes into
a 14.4× Toffoli factor and a 4.49× width factor — both concentrated in the private base's
tower-field kernels and pebbling/width scheduler, neither of which is recoverable from the 25
patch-only deltas. Realistic solo effort to parity: **90–150 person-days**, exceeding the window.
`[SPEK]`

**What IS feasible in ~78 days:** a correct, modifiable, tower-field shadow decoder at ratio ~5–20
(option c), with the inverse-overhead and de-pebbling levers **prototyped and measured on our own
code** — demonstrating the mechanisms and producing a publishable artifact, but not yet beating
`fc3ba816`. `[SPEK]`

### 6.2 Critical path
1. **Width/pebbling scheduler (Layer 4)** — the single biggest unknown; not visible in any delta;
   gates the 4.49× Q factor. *Biggest risk.*
2. **Tower-field kernels (Layers 1–2)** — gates the 14.4× T factor; partially recoverable from
   `division.py`. *Medium risk.*
3. **Decoder stage bodies (Layer 3)** — extract/synthesis/convert; recoverable from paper + `.kmb`
   structure but labor-intensive. *Medium risk.*

If any of (1) or (2) stalls, we cap below parity and the lever cannot bank an improvement.

### 6.3 Minimum viable milestone (recommended definition of "done" for the solo track)
> **A correct, modifiable shadow decoder (kickmix-based, tower-field arithmetic, basic pebbling)
> that PASSES the official verifier at 102,400 shots (R≈1.19, 0 value/phase errors) at ratio ~5–15,
> with the inverse-overhead removal (5.1.2) and de-pebbling (5.2) levers implemented and their ΔT
> measured on that decoder.**

Effort: **~30–45 person-days.** This is the honest floor that creates real option value (leverage +
artifact + de-risking) without betting the window on parity. A stretch sub-milestone: "reproduce the
extract+synthesis forward half structurally against the `.kmb`" as a checkpoint inside the build.

---

## 7. Reconstruction (solo) vs. inheriting the builder (merge)

### 7.1 Time-to-lever
- **Merge (somejoint):** he has the builder *today*. Integrate → apply inverse-overhead to unextract
  first → verify. **~1–2 weeks** to a bankable lever (assuming cooperation + rule-compliant transfer
  post-team-formation). `[SPEK]`
- **Reconstruct (solo):** **90–150 person-days** to parity + lever; **infeasible in-window.** `[SPEK]`

### 7.2 Where merge dominates
Merge dominates for the *banking* goal at essentially **t=0**: the asset (the builder) exists in his
hands now and does not exist in ours at any realistic in-window date. The only scenario where
reconstruction is preferred is if the merge is refused/blocked **and** we relax the goal to
"modifiable builder + artifact + leverage" rather than "beat `fc3ba816`."

### 7.3 Crossover point (concrete)
- **If somejoint responds positively within ~2 weeks (by ~Nov 15–20):** form team before Jan 13,
  inherit the builder, pivot *all* solo effort to applying levers on it. Reconstruction effort
  drops to near-zero (keep only the verification infra).
- **If no response by ~Nov 15–20:** shift the solo track from "parity reconstruction" to "shadow
  decoder for leverage" (option c, §6.3 milestone). Continue merge outreach in parallel (notebook
  comment fallback per the outreach draft). The shadow decoder then (a) is a publishable
  milestone-eligible artifact, (b) strengthens any later negotiation ("we can reconstruct X% of your
  builder"), and (c) de-risks the final-polish window if the merge never materializes.
- **Hard deadline:** merges close **2027-01-13**; final submit **2027-01-19**. Any parity
  reconstruction that is not done by ~Jan 4 cannot be verified + submitted safely. This effectively
  rules out option (a) as a banking path regardless of effort. `[FAKT]` (deadlines) + `[SPEK]`
  (buffer)

### 7.4 Bank-now item independent of both
Report A's surgery-level **product caching (~−2,787 T, −0.7%, +0.03 GM)** needs no builder and can be
banked while the above plays out. Small, but it is the only in-window lever that doesn't depend on
either the merge or parity reconstruction. `[FAKT]`-old/`[SPEK]`-cur.

---

## 8. Evidence index

| claim | evidence | tag |
|---|---|---|
| Target baseline T/Q/R/ratio/errors | Report A §1 (official verifier JSON, sha `fc3ba816…`) | `[FAKT]` |
| Reference decoder Q=1893, T=5,725,461, correct | my build + 256-shot verifier run (`reference_build.json`, `reference_verify.json`) | `[FAKT]` |
| Gap = 4.49× (width) × 14.4× (Toffoli) = 64.7 ≈ 65.1 | arithmetic on the two measured circuits | `[FAKT]` |
| 23 semantic blocks / 46 raw tags; per-block T | `list_info_tags.py` → `info_tags.json` | `[FAKT]` |
| 61 missing private modules; call-site API surface | `analyze_imports.py` → `import_analysis.json` | `[FAKT]` |
| Deltas are `private_rebind` patches over `ported` base | `blocked_three_noscratch.py`, `scalar_compact_v3.py`, `inverse_character_width.py` | `[FAKT]` |
| Base tree (`playbook/kit`, `exp/decoder`) absent | `find . -type d` (empty) | `[FAKT]` |
| Inverse overhead +48,863 (12.3%); unextract +38,029 | Report A §3.1, `block_analysis.json` | `[FAKT]` |
| Pebbling 267,210 CCX (69.8%) | Report A §3.2, `pebbling.json` | `[FAKT]` |
| Q at strict lower bound (3 liveness models); break-even ~893 T/qubit | WIDTH_ANALYSIS §1,§5,§7 (892-Q sibling) | `[FAKT]`/`[HYP]`(→891) |
| Tower-field mul 105T / div 321T schedules | `division.py` | `[FAKT]` |
| Forney scan → `root_character` × 4095 → `phase_inverse12_quantum64` | `direct_forney.py` | `[FAKT]` |
| R shot-count dependence (7.5 @256 vs 1.19 @102,400) | measured via verifier `repetition_overhead`/`clopper_pearson` | `[FAKT]` |
| Layer LOC estimates, milestone effort, crossover timing | reasoned from the above | `[SPEK]` |

**Artifacts written (this task):** `work/dqi_builder_recon/{analyze_imports.py, import_analysis.json,
list_info_tags.py, info_tags.json, build_reference.py, reference_build.json, verify_reference.py,
reference_verify.json, reference.kmb, report_H_builder_feasibility.md}`. All scripts guard
nullable/empty params before use. No secrets printed; nothing submitted.
