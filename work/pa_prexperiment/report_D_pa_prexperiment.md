# Report D — P-A go/no-go pre-experiment: invsqrt "pure-dyadic kickback"

Scope: Benchmark I (`invsqrt.kmb`, sha `e4ed188b…`, Q=62, C=1,589.26, cost 98,533.87, ratio 21.0768×).
Task: decide GO/NO-GO on Report B's proposal **P-A** — replace the 41 fine rotations by pure-dyadic
kickback of the model output `y = p<<s` (stream y-bits 4…39 at weights 2^(i−40)), with the open cost
being **s-routing** (tap i must read `y_i = p_{i−s}`, s ≤ 10 depends on x). Gate: proceed iff
**measured R ≤ 200 mean-executed Toffolis AND Q_peak ≤ 62**.
All new files under `work/pa_prexperiment/`. Tags: [FAKT] measured/proven here · [HYP] plausible, unproven · [SPEK] speculative.

---

## VERDICT: **NO-GO (as specified)** — two load-bearing premises of P-A are false

1. **`n_rot = 0` is FALSE. It is `n_rot = 33`.** [FAKT] Streaming y-bits i=4…39 at weights 2^(i−40)
   does **not** make the taps free. A dyadic weight is Clifford/T **only** when it is coarser than
   1/8 turn, i.e. only for i ≥ 37. Bits i=4…36 sit at Clifford-hierarchy level k = 40−i ∈ 4…36 →
   they are **synthesized rotations**, exactly like today's. Verified by building the 36 Z_POWs and
   letting kickmix count them: `num_z_pow(min_clifford_hierarchy_level=4) = 33`, level-3 (T) = 1,
   level-≤2 (Clifford) = 2 (`verify_nrot_claim.py`). Report B's "even 40−i → Clifford, odd → T, both
   free" misreads the hierarchy: 2^(−4) turn = 1/16 turn is **level 4 (rotation)**, not Clifford.
2. **The s-routing estimate R ∈ [50,200] is FALSE for the natural implementation.** [FAKT] The
   verifier's `mean_executed_Toffolis` counts **applied** toffoli-like gates (it respects
   measurement-conditioned blocks; unconditional data-controlled gates always count in full — confirmed
   by diagnostics and by the shipped circuit's seed-dependent 1,289.29 < static 1,487). A data-controlled
   barrel-shift of p by s is therefore **R = 585 applied Toffolis** (correct circuit, `y==p<<s` verified
   on 627,712 shots, `step3_shift_sim.py`) → **fails the R ≤ 200 gate by 2.9×**. The only way to get
   R ≈ 0 (measure s → classical branch → *uncontrolled* free-SWAP shift) is **blocked**: kickmix `HMR`
   is an **X-basis** measurement (random outcome on a definite data qubit), so s's value cannot be read
   into a branch bit (`circuit_builder.pybind.cc`: hmr = "X-basis measurement and Z-basis reset").

Even setting R aside, the corrected economics cap the upside at **ΔGM ≈ +1…+2.7%** (not Report B's
+1.96…+5.60%), because the rotation-side saving is only **70.5 Toffoli-eq** (n_rot 41→33, c 58.6M→332M),
not ~300. A net win additionally requires the 22 non-overlapping new y-bits to route at **R ≲ 118**
(break-even Δme ≈ +70 after removing ~48 Toffolis of dropped quadratic controls) — and a full pipeline-basis
search finds **no ≤2-gate form for any of them** (negative signal; see §3).

**Flip condition (precise):** GO iff a full dataflow trace/prototype shows the 19 non-constant new y-bits
route at **R ≤ 200** applied Toffolis total — ideally **≤ ~118** for a net economic win — e.g. via
"bit AND free-linear-form" identities of the kind the existing 14 raw-y taps use (y30 = q21·L at ~1 Toffoli),
or via a discovered Z-basis readout of s. Otherwise pivot to **P-B** (constant-seed model, intrinsic margin
6.25–7.24×c) or the mean-Toffoli lever.

---

## 1. What was reused / re-derived

- Reference fixed-point model re-run verbatim from `step4a_reference_model.py` → `p(x), s(x), y(x)=p<<s`
  on the full domain (3,133,452 x). Reproduced `A_ref.npy` **exactly**; min margin **332,168,080 @ x=3,012,139**,
  max |A|/tol **0.4769** (both match Report B). Saved `data/{p,s,y}.npy`.
- s-distribution (normalization classes): s=0 **66.5%**, s=1 **25.1%**, s=2 6.3%, s=3 1.6%, s≥4 <1%
  (s=10: only 3 x). E[s]=0.45, E[popcount(s)]=0.352, E[popcount(p)]=15.34.
- Existing 41 tap control columns `work/p0_reports/data/bcols/col_*.npy` (Report B perturbation machinery).
- Cost model re-implemented from `verify_submission_invsqrt.py`; baseline reproduces Report B to the unit
  (C=1,589.26, cost=98,533.86, ratio=21.0768, GM=23.3825).

## 2. Bit-liveness audit (per required y-bit i ∈ 4…39)

"Phase free?" = weight 2^(i−40) turn is Clifford/T (hier level ≤3) → **only i ≥ 37**.
"Already a tap control?" = exact/near match to one of the 41 existing control columns (Report B step7 + re-check here).
"New-routing cheap-form?" = ≤2-gate form (reuse / NOT / XOR-of-2 / AND-of-2) in the **full K=270 pipeline basis**
(x, s, case, c0–c3, seed y1–17, square, product z, correction, p bits + the 41 controls) — `step5b_full_basis.py`.

| i | wt (turns) | hier lvl | phase free? | already a tap control? | new-routing ≤2-gate form? |
|--:|-----------:|:--------:|:-----------:|:----------------------:|:-------------------------:|
| 4–14 | 2⁻³⁶…2⁻²⁶ | 36…26 | **NO** (rot) | no | **none found** (11 bits) |
| 15–21 | 2⁻²⁵…2⁻¹⁹ | 25…19 | **NO** (rot) | yes (near, 99.94–99.999%) | n/a (exists) |
| 22–29 | 2⁻¹⁸…2⁻¹¹ | 18…11 | **NO** (rot) | no | **none found** (8 bits) |
| 30–34 | 2⁻¹⁰…2⁻⁶ | 10…6 | **NO** (rot) | yes (near, 99.97–100%) | n/a (exists) |
| 35 | 2⁻⁵ | 5 | **NO** (rot) | **exact** (b13) | n/a (exists) |
| 36 | 2⁻⁴ | 4 | **NO** (rot) | **exact** (b14) | n/a (exists) |
| 37 | 2⁻³ | 3 (T) | **YES** | near (b13/b14/b38–40) | const 0 (5/300k) → droppable |
| 38 | 2⁻² | 2 (S) | **YES** | near | const 0 (0/300k) → droppable |
| 39 | 2⁻¹ | 1 (Z) | **YES** | near | const 0 (1/300k) → droppable |

Read-out:
- **33 bits (i=4…36) require synthesized rotations** — this is where `n_rot=33` comes from. Only i=37,38,39
  are phase-free, and those three are (near-)constant over the domain (nonzero only at the rarest, smallest-x
  values where tol is huge), so they are **droppable** at negligible error.
- **14 bits (i=15…21, 30…36) are already live tap controls** → their routing is already paid in the 1,289.29.
- **19 bits (i=4…14, 22…29) need NEW s-aware routing** and **none has a ≤2-gate form** in the full pipeline
  basis. They are the entire content of the open cost R. (Caveat: this search cannot see "bit AND free-linear-form"
  structures — the exact shape of the existing y30=q21·L identity — so "none found" is a negative signal, not a proof
  of impossibility.)

## 3. s-routing cost R — measurements

| option | mechanism | R (applied Toffolis) | method | gate R≤200 |
|--------|-----------|:--------------------:|:------:|:----------:|
| **(a)** data-controlled barrel shift | 4 stages (shift 1/2/4/8), d·(W−1) CSWAPs each, W=40, all unconditional | **585.0** | **[FAKT]** simulated, `y==p<<s` on 627,712 shots | **FAIL (×2.9)** |
| **(a′)** measure s → classical branch → uncontrolled free-SWAP shift | would be R≈0 (SWAPs are free CNOTs) | blocked | **[FAKT]** HMR is X-basis ⇒ s value unreadable | n/a (unbuildable as-is) |
| **(b)** folded per-tap s-selection (extend existing muxes) | 19 new bits × per-bit s-mux | **57 … 190+** | **[HYP]** full-basis search: 0/19 have ≤2-gate form; generic 11-way s-mux lower bound ≈10 T/bit ⇒ ≥190; "bit·linear-form" identities (cf. existing y30≈1 T) ⇒ ~3 T/bit ⇒ ~57 | **unproven** |

Notes:
- Option (a) is *correct* (verified) but *expensive* precisely because the cost model charges **applied** gates:
  every one of the 585 CSWAPs is reached on every shot even though s≠0 for only ~33% of x and s≥2 for <9%.
- Option (b) reuses the existing scattered per-tap CSWAP muxes (observed ~2–4 CSWAP + 1 CCX per raw-y tap in the
  shipped circuit, e.g. y30 control = `CCX q21 q1 q28` with q1 a free 15-CX linear form ⇒ ~1 Toffoli). Whether the
  19 new bits admit comparable identities is the single open question.

## 4. Corrected economics (n_rot = 33, c = 332,168,080)

Rotation side (fixed once n_rot and c are set): ε = πc/2⁶⁴/33 = 1.714e-12, per-rotation = 27.188 T,
rotation-side = (t_base + 33·27.188)/4 = **229.43** Toffoli-eq (t_base ≈ 20.5 held). **Saving vs current 299.97 = 70.54.**
Mean-exec side: Δme = R(new 19-bit s-routing) − Q_removed(dropped 24 quadratic + 3 near-y controls, est. ≈48).

| Δme | mean_exec | C | cost | ratio | GM | **ΔGM** |
|----:|----------:|------:|-------:|-------:|-------:|--------:|
| −100 | 1,189.29 | 1,418.72 | 87,960 | 23.610 | 24.284 | **+3.86%** |
| −50 | 1,239.29 | 1,468.72 | 91,060 | 22.807 | 24.006 | **+2.66%** |
| 0 | 1,289.29 | 1,518.72 | 94,160 | 22.056 | 23.739 | **+1.52%** |
| +50 | 1,339.29 | 1,568.72 | 97,260 | 21.353 | 23.484 | **+0.43%** |
| +100 | 1,389.29 | 1,618.72 | 100,360 | 20.693 | 23.240 | **−0.61%** |
| +200 | 1,489.29 | 1,718.72 | 106,560 | 19.489 | 22.780 | **−2.58%** |
| +585 (opt a) | 1,874.29 | 2,103.72 | 130,430 | 15.923 | 21.296 | **−8.92%** |

Break-even (ΔGM=0) at **Δme ≈ +70**, i.e. **R(new routing) ≲ 118** given Q_removed ≈ 48.
- Option (a): Δme ≈ +537 ⇒ **ΔGM −8.9%** (clear loss).
- Option (b) best case (R≈57, identities exist): Δme ≈ +9 ⇒ **ΔGM ≈ +1.3%**.
- Option (b) worst case (R≈190, generic muxes): Δme ≈ +142 ⇒ **ΔGM ≈ −1.3%** (loss).

So **even a passing option-(b) is worth only ~+1…+2% GM**, roughly half of Report B's claim, and only if the
per-bit identities exist.

## 5. Q_peak

Option (a) in-place shift reuses the p-register (30 qubits) + 10 spare high-y qubits + s-bits + accumulator;
Report B notes the y-register bits are already live during streaming, so no new *persistent* qubits are expected
(prototype used 44 qubits in isolation). Option (b) reuses existing mux infrastructure + a few linear-form scratch
qubits (free CXs). **Q_peak ≤ 62 is plausibly satisfiable for both** — it is *not* the binding constraint; R is.
(Confirm the 10 spare high-y qubits in the full build.)

## 6. Next steps (if pursued)

1. **Decisive half-day measurement (do before any build):** extend the expression search to
   "bit AND free-linear-form" and small-mux forms over the full pipeline basis, **or** prototype 2–3 of the 19 new
   y-bit taps (e.g. y_22, y_25, y_10) inside the actual circuit and measure their marginal applied-Toffolis.
   - avg ≤ ~6 T/bit ⇒ R ≤ ~115 ⇒ **revisit as modest GO** (ΔGM ~+1–2%).
   - avg ≥ ~10 T/bit ⇒ R ≥ ~190 ⇒ **confirm NO-GO**.
2. If NO-GO holds: pivot to **P-B** (constant-seed model; intrinsic margin 366M–424M = 6.25–7.24×c, its own open
   cost is the 128-entry table lookup) or the **mean-Toffoli lever** (cone rewrites; out of scope here).
3. Do **not** start the full P-A build on the current evidence.

## Appendix — artifacts

| artifact | path |
|---|---|
| n_rot=33 empirical check (36 Z_POWs, kickmix counts) | `verify_nrot_claim.py` |
| reference model p/s/y + s-distribution (full domain) | `step1_model.py`, `data/{p,s,y}.npy` |
| bit-liveness audit + barrel-shift link-count | `step2_audit_routing.py`, `data/step2_results.json` |
| **option-(a) shift simulation (R=585, correctness)** | `step3_shift_sim.py`, `data/step3_shift_sim.json` |
| applied-vs-firing Toffoli counting diagnostics | `diag_toffoli_count.py`, `diag2.py` |
| corrected economics sweep | `step4_economics.py`, `data/step4_economics.json` |
| ≤2-gate form search (limited then full K=270 basis) | `step5_expression_search.py`, `step5b_full_basis.py`, `data/step5{,b}_expr.json` |
| shift-region / normalization inspection | `dump_tap_regions.py`, `find_shifts.py` |

Verification anchors: reference model reproduces `A_ref.npy` exactly (min margin 332,168,080 @ x=3,012,139);
cost-model baseline reproduces Report B (C=1,589.26, ratio=21.0768, GM=23.3825); option-(a) shift verified
`y==p<<s` on 627,712 shots; kickmix `num_z_pow(min_clifford_hierarchy_level=4)=33` for the 36 dyadic weights.

---

## Close-out (follow-up)

Timeboxed follow-up to the round-1 NO-GO-as-specified. Two tasks: (1) decisive P-A routing
measurement, (2) quantify the alternatives. All new files under `work/pa_prexperiment/`; nothing built,
nothing submitted. Tags: [FAKT] measured here · [HYP] plausible/unproven · [SPEK] speculative.

### Task 1 — FINAL P-A routing verdict: **CONFIRMED-NO-GO**

Built the generic DNF s-router **in-circuit** (kickmix, applied-Toffoli counting validated in round 1) for
the shared s-decode `eq_k=(s==k), k=0..10` plus every new y-bit accumulator, and measured the marginal
applied Toffolis per bit. `y_i = p_{i-s} = OR_k [(s==k) AND p_{i-k}]`; a bit contributes one CCX per valid
`k` (those with `0 <= i-k <= 29`). Low bits have **fewer** terms than 11 — the round-1 "11/bit" extrapolation
over-counted them.

Measured per-bit marginal applied Toffolis (`task1_proto.py`, `task1_all19.py`; correct=True on 157,696 shots):

| i | valid s-terms (k) | marginal applied Toffolis | tag |
|--:|:-----------------:|:-------------------------:|:----:|
| 4 | 5 (k=0..4) | 5 | [FAKT] (in all-19 build) |
| 5 | 6 | 6 | [FAKT] |
| 6 | 7 | 7 | [FAKT] |
| 7 | 8 | 8 | [FAKT] |
| 8 | 9 | 9 | [FAKT] |
| 9 | 10 | 10 | [FAKT] |
| 10 | 11 | **11.0** | [FAKT] measured solo |
| 11–14 | 11 each | 11 ×4 | [FAKT] (in all-19 build) |
| 22 | 11 | **11.0** | [FAKT] measured solo |
| 23–24 | 11 each | 11 ×2 | [FAKT] (in all-19 build) |
| 25 | 11 | **11.0** | [FAKT] measured solo |
| 26–29 | 11 each | 11 ×4 | [FAKT] (in all-19 build) |
| — | **shared s-decode** (eq_0..eq_10) | **33** | [FAKT] |
| | **R_total (all 19 bits)** | **221** | [FAKT] |

- **R_total = 221 applied Toffolis** [FAKT] = 33 (decode) + 188 (Σ per-bit terms). Measured directly by building
  all 19 accumulators together (`task1_all19.py`, total 221.00, correct=True); equals the term-count sum exactly.
- **Correction to round 1:** the extended search (`task1_search.py`, SUB=12,000) flagged `y_22 = XOR2(b00,b33)`
  (a free form → would have given R=231, "1/19 cheap"). Full-domain verification (`task1_y22_diag.py`) shows
  `b00^b33` agrees on 12,000/12,000 sampled rows but **disagrees on 19/3,133,452 full-domain rows (0.0006%)** →
  a near-miss, **not** an identity. So `y_22` is generic; **0/19** new bits admit a ≤2-gate form. All-generic
  R=221 stands.
- **Verdict:** R_total=221 [FAKT] exceeds the gate (R≤200) by 1.1× and break-even (R≲118) by 1.9×.
  **CONFIRMED-NO-GO.** ΔGM at R=221 (Q_removed≈48 [HYP]): mean_exec 1,462.29, C=1,691.72, ratio 19.800,
  GM 22.901 → **ΔGM = −2.06%** [FAKT arithmetic]. Even the optimistic mixed case (R=231) is −2.25%; the
  break-even point R=118 gives ΔGM +0.01% (confirms §4's break-even). P-A is a net loss under any measured routing.

### Task 2a — P-B (constant-seed) compiled-cost bound

Report B's flagged risk was "compiled cost unknown (table lookup)." Bounded the table now:

- **Seed-table lookup = 144 applied Toffolis** [FAKT]. kickmix native QROM `init_lookup`+`del_lookup`,
  128-entry × 8-bit, 7-bit address, unstructured values = an **upper bound** (Report B notes most table bits are
  cheap threshold predicates of M → real cost ≤ 144). Cost is dominated by the address→one-hot decode; output-width
  loading is free CNOTs — `128×8=144`, `128×16=144`, `64×8=72`, `256×8=279` (`task2_pb_table.py`).
- **What is NOT yet bounded (the exact missing measurement):** the **two narrow Newton steps** (NR widths
  (16, 24+2, 26) per mrmeows' spec) and P-B's own streamed/s-routing bit count. Report B's P-B economics put
  C=1,399–1,499 (vs 1,589.26), i.e. Δcore≈105–205 new mean-exec Toffolis; the table (≤144) sits inside that
  Δcore, so the **residual unknown is the 2 NR steps' compiled cost + Q_peak**. To close P-B: compile those 2
  narrow steps + the table, measure mean_executed_Toffolis and Q_peak, then ratio vs 21.0768×.
- **Why P-B still wins despite higher mean-exec:** the gain is on the **rotation side** (−294.8 Toffoli-eq,
  because constant-seed gives y<2³⁷ → far fewer streamed bits), which dominates the +Δcore. Expected
  **ΔGM = +1.96%…+4.33%** [HYP, Report B] — now with its main risk (table) quantified at ≤144 [FAKT].

### Task 2b — Mean-Toffoli lever: floor + top candidate

Mapped the shipped circuit's toffoli-like ops by region/condition (`task2_toffoli_map.py`):

- Static toffoli-like = **1,487** (CCX 1,147 + CSWAP 201 + CCZ 139); **1,233 unconditional** + **254 (17.1%)**
  inside ≥1 PUSH_CONDITION (fractional applied) → mean-executed 1,289.29 [FAKT].
- **The NR multiplier core dominates**: peak bucket 273 ops at lines 24,000–26,000; core ≈ **700 of the 1,289**
  mean-executed Toffolis [FAKT region map].
- **Lineage slack is already spent.** yoyobar 62Q cone rewrites, Özer phase patch, Mallick two 3→2 AND merges,
  and Kirill four-loaders-eight-toffolis are all *in* the shipped circuit — no easy remaining rewrite there [HYP].
- **Plausible floor:** ~1,100–1,200 mean-executed [HYP]. Cutting below that requires a numerical-model change
  (narrower multipliers / coarser rotations), which needs margin headroom the **current** circuit lacks (its margin
  is exactly c). So the standalone mean-Toffoli lever on today's circuit is near-exhausted.
- **ΔGM sensitivity** (rotation side held at 299.97): +2.19%/100T, +4.59%/200T, +7.22%/300T [FAKT arithmetic].
- **Top concrete change = P-B** (Task 2a). P-B's narrower NR widths (16, 24+2, 26) + constant seed *are* the
  multiplier narrowing, and its 6.25–7.24×c intrinsic margin makes that narrowing safe — the current circuit
  cannot narrow without breaking correctness. The mean-Toffoli lever is therefore **subsumed into P-B**, not a
  separate play.

### Bottom line

- **P-A: CONFIRMED-NO-GO.** R_total=221 [FAKT] > gate 200, > break-even 118; ΔGM −2.06%. Do not build.
- **Best invsqrt investment: P-B (constant-seed rebuild).** Its one flagged risk (table lookup) is now bounded
  ≤144 applied Toffolis [FAKT]; expected ΔGM +1.96%…+4.33% [HYP], driven by the rotation-side saving (−294.8)
  and unlocked by the 6.25–7.24×c margin. Residual unknown = the 2 narrow Newton steps' compiled cost + Q_peak.
- **Next (bounded, ~half-day, no full build):** compile P-B's 2 narrow NR steps (16, 24+2, 26) + the 128-entry
  table, measure mean_executed_Toffolis and Q_peak, and recompute ratio/GM against 21.0768×.

#### Follow-up artifacts

| artifact | path |
|---|---|
| in-circuit generic s-router, per-bit marginals (i=10,22,25 = 11.0; T_decode=33) | `task1_proto.py`, `data/task1_proto.json` |
| extended algebraic search (K=270 basis; forms const/reuse/NOT/XOR2/AND2/A·L/(A&B)\|C) | `task1_search.py`, `data/task1_search.json` |
| **definitive all-19-bit router (R_total=221, correct=True)** | `task1_all19.py`, `data/task1_all19.json` |
| y_22 full-domain XOR2 refutation (19-row near-miss) | `task1_verify_full.py`, `task1_y22_diag.py`, `data/task1_y22_diag.json` |
| P-B QROM table bound (128×8 = 144 applied Toffolis) | `task2_pb_table.py` |
| shipped-circuit toffoli region/condition map (static 1487, NR core ≈700) | `task2_toffoli_map.py` |
| final GM arithmetic (R=221 → ΔGM −2.06%; lever +2.19%/100T) | `task_final_gm.py` |
