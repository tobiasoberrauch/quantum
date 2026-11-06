# Report F — P-B (constant-seed invsqrt) measurement: GO/NO-GO for a full build

Scope: Benchmark I (`invsqrt`, reference cost 2,076,774.233715282). Current SOTA
`work/frontier_scan/mwa_unpacked/invsqrt.kmb` (sha `e4ed188b`): Q=62, mean-executed Toffolis
1,289.29, n_rot=41, C=1,589.26, cost 98,533.87, **ratio 21.0768×**, GM 23.3825.
Task: measure P-B (mrmeows' constant-seed rebuild) mean_executed_Toffolis + Q_peak, recompute
ratio/GM, and give a GO/NO-GO for a full build. All new files under `work/invsqrt_pb/`. Nothing submitted.
Tags: [FAKT] measured/proven here · [HYP] plausible/unproven · [SPEK] speculative.

---

## VERDICT: **NO-GO (measured)** — P-B is ~34× worse than current SOTA; reverses Report B's optimistic estimate

A prior session already built P-B (a correctness-first foundation, 4 variants) under
`work/constseed_build/` and ran the **official verifier on the full domain** (all 3,133,452 x × 64 shots
= 200,540,928 shots). This report **independently verifies** those numbers (loads each `.kmb`, re-reads
static op statistics, scans for conditional Toffolis, recomputes the official cost model) rather than
trusting the prior `REPORT.md`. Every figure below reproduces.

| variant (file) | status | Q_peak | mean-exec Toffolis | n_rot | C | score=Q·C | **ratio** | **ΔGM** |
|---|:--:|--:|--:|--:|--:|--:|--:|--:|
| **PRIMARY** lookup, all-persistent (`invsqrt_constseed_lookup.kmb`) | PASS | **384** | **8,581** | 34 | 8,812.2 | 3,383,896 | **0.6137×** | **−69.2%** |
| lookup, hybrid N1-transient (`invsqrt_constseed_lookup_hybrid.kmb`) | PASS† | 324 | 11,315 | 34 | 11,546.2 | 3,740,978 | 0.5551× | −70.2% |
| raw Horner, all-persistent (`invsqrt_constseed.kmb`) | PASS | 509 | 9,434 | 34 | 9,665.2 | 4,919,602 | 0.4221× | −72.8% |
| raw Horner, transient (`invsqrt_constseed_current.kmb`) | PASS | 425 | 15,656 | 34 | 15,887.2 | 6,752,073 | 0.3076× | −75.6% |
| *(current SOTA, for reference)* | PASS | 62 | 1,289.29 | 41 | 1,589.26 | 98,534 | 21.0768× | — |

† hybrid row was subset-verified by the prior session; numerics identical (same worst err/tol 0.5139).

**All four P-B variants score ≤ 0.614×** — i.e. *worse than the official reference* (1.0×) and **~34–68×
worse than current SOTA** (21.0768×). Worst err/tol 0.5139 (PASS, < 1.0), so the circuits are *correct*;
they are simply far too large/expensive. **P-B is a definitive NO-GO.**

### ΔGM basis (base-independent)
Only the invsqrt task ratio changes (21.0768× → 0.6137× for PRIMARY). GM scales by
`(0.6137/21.0768)^{1/3} = 0.3077`, so **ΔGM = −69.2% regardless of the portfolio base GM**. Anchored
absolutely: base 23.3825 → 7.195; base 24.45812 → 7.526; base 24.48523 → 7.534. (I anchor the project to
23.3825, consistent with Reports D/B; the ΔGM is identical from either stated base.)

---

## What was measured, and how it is trustworthy

- **Applied vs static counting.** A conditional-toffoli scan (validated on the current SOTA circuit, which
  yields static 1,487 / conditional 254 — matching the P-A map exactly) finds **0 conditional Toffolis in
  every P-B variant**. Hence every shot executes exactly the static CCX count: **mean-executed == static ==
  8,581** (PRIMARY). This also matches the official verifier's `toffoli_count == max_toffoli_count == 8581`.
  So the applied count is established by two independent methods (static scan + official full-domain run);
  no reduced-domain re-simulation is needed, and a reduced-domain run would be *exact*, not coarse.
- **Domain.** Prior session ran the **full domain** (stronger than the requested reduced domain). Because Q
  and the Toffoli count are x-independent (below), the full and reduced domains give identical numbers.
- **Cost model.** Recomputed from `verify_submission_invsqrt.py`: `C = mean_Toffolis + (t_base +
  n_rot·(0.56·log2(1/ε)+5.3))/4`, `score = Q·C`, `ratio = 2,076,774.23/score`, with the official
  `rotation_eps = 1.7438e-12`. Reproduces the verifier's C=8,812.23 / score=3,383,896 to the unit.

## Component costs — PRIMARY (each [FAKT] measured directly)

Built minimal circuits running only each component (widths fixed by the validated spec ⇒ data-independent):

| component | CCX | detail |
|---|--:|---|
| (a) seed lookup | **551** | 512-entry × 8-bit ROM, 9-bit address, `init_lookup`+`del_lookup` (phase-safe uncompute) |
| (b) Newton #1 (n1=16) | **2,600** | SS=S²; Q1=(x·SS)>>20; C1=3·2¹⁶−Q1; P1=(S·C1)>>8 (forward+inverse) |
| (c) Newton #2 (g=26) | **4,644** | sq2=P1²; Q2=(x·sq2)>>28; C2=((3·2²⁶)−Q2)>>1; P2=(P1·C2)>>16 (forward+inverse) |
| normalize / select / build_k / denormalize / phase-adj | 786 | 8,581 − (551+2,600+4,644) |
| **total CCX** | **8,581** | |
| phase streaming (dyadic/T) | 231.2 Toffoli-eq | 34 synthesized rotations (hier≥4) + 1 T; lives in C's rotation term, not CCX |
| **C** | **8,812.2** | 8,581 + 231.2 |

**The two Newton steps are 7,244 CCX = 84% of the total** (Newton#2 alone = 4,644 = 54%). This is the
root cause of the failure. Note the ROM is **512 entries** (not 128): the seed S depends on
`(interval, k)`, not `k` alone, so the address is 9 bits (`inter·128+k`, inter∈{0,1,2,3}) — still only 551 CCX.

## Blocker analysis (what must improve to flip to GO)

GO requires ratio > 21.0768× by a meaningful margin (≥ +1% GM ⇒ ratio ≳ 21.7×) **and** Q_peak ≤ 62.
Two independent blockers, both ~6× over budget:

1. **Q_peak = 384** (budget 62) — must drop **84%**. Root cause: the two Newton steps keep wide
   *persistent* product registers (up to 34 bits: `prod_q1`=34, `prod_p1`=24, `sq2`=34, `prod_q2`=29,
   `prod_p2`=31) live simultaneously at the Newton#2 peak. The best variant (hybrid, making Newton#1's
   multiplies transient) only reaches **Q=324** — still 5.2× over budget. Reaching Q≤62 would require
   abandoning the two-step exact-arithmetic core (the validated P-B spec itself).
2. **mean-executed Toffolis = 8,581** (current 1,289) — at Q=62 it must fall to **≤ ~1,358** (−84%) just to
   *match* current; at P-B's own Q=384 it must fall to **≤ 256.6** (−97%) to match. Root cause: two Newton
   steps ≈ double the current single-step core, and the exact-arithmetic column cutoffs widen products to
   34 bits. No uncomputation/caching stack fixes a structural width+doubling deficit.

Bounding argument (task point 5): Q is a **static allocation** property (`circuit.num_qubits`), identical for
every x — there is no x-specific peak. The live-width high-water mark is inside Newton#2 (Newton#1 persistent
products co-live with Newton#2 registers), and it is the same 384 on the full domain and on any subset. The
measurement is therefore exact, not a coarse reduced-domain estimate.

## Why Report B's optimistic estimate (+1.96%…+4.33%) was wrong

Report B estimated P-B at C=1,399–1,499 (Δcore≈100–200, n_rot→0/~26, Q≤62). The compiled circuit refutes all three:

1. **n_rot is 34, not 0/~26.** The constant-seed output is 37 bits (F=out_frac+N_P+1=26+10+1); 34 of those
   need synthesized rotations. Rotation-side saving is only ~69 Toffoli-eq (299.97→231.2), **not** the 294.8
   Report B assumed.
2. **Δcore is ~7,300, not ~100–200.** The two narrow Newton steps compile to 7,244 CCX (84% of total) — the
   "narrow" widths (16, 24+2, 26) still produce 34-bit exact-arithmetic product registers. Report B's
   "reconstructed model" evaluated the *numerics* (margin 6.25–7.24×c) but never costed the *arithmetic*.
3. **Q is 384, not ≤62.** Persistent wide products across two sequential Newtons set the floor at ~384
   (324 best-case hybrid). The 62-qubit regime is unreachable within the validated spec.

The intrinsic margin (6.25–7.24×c) is real and useful *numerically*, but it buys precision headroom, not
smaller multipliers — the two-step core is intrinsically wide, so the margin cannot be spent down to the
current architecture's Q/C envelope.

## Bottom line

- **P-B = NO-GO (measured, all 4 variants).** Best ratio **0.6137×** vs current **21.0768×** (~34× worse);
  **ΔGM ≈ −69%**. Q_peak 384 and mean-Toffolis 8,581 both exceed budget by ~6×.
- This **reverses the P-A close-out recommendation**, which had favored P-B on Report B's *uncompiled*
  optimistic estimate. Now that both are measured: **P-A is NO-GO** (R=221, ΔGM −2.1%) **and P-B is
  NO-GO** (0.614×, ΔGM −69%).
- The only remaining lever is the **mean-Toffoli grind on the current single-step architecture** (NR core ≈700
  of the 1,289; lineage rewrites largely spent per the P-A close-out) — small upside, near the architecture
  ceiling. **Current SOTA (21.0768×) should be treated as near-optimal for this family; do not start a P-B
  full build.**

## Artifacts (this report, under `work/invsqrt_pb/`)

| artifact | path |
|---|---|
| independent static scan of all 4 `.kmb` (Q, static CCX, conditional CCX, T, n_rot) | `verify_static.py`, `data/static_scan.json` |
| official cost-model recompute + scanner sanity + blocker arithmetic | `final_costs.py`, `data/pb_costs.json` |
| per-component CCX (lookup / Newton#1 / Newton#2) | `component_breakdown.py`, `data/pb_components.json` |
| prior build + full-domain official verify (source of the measured circuits) | `work/constseed_build/{build_constseed_circuit.py, verify_full_lookup.json, REPORT.md}` |

Verification anchors: conditional-toffoli scanner reproduces current-SOTA 1,487/254; PRIMARY C=8,812.23 /
score=3,383,896 / Q=384 / mean-T=8,581 all reproduce the official full-domain verifier
(`verify_full_lookup.json`, 200,540,928 shots, worst err/tol 0.5139 @ x=1,001,881, sha
`57f2dd0b…`).
