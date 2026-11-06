# DQI Width/Liveness Analysis — can 892 Q be reduced by re-timing ancilla lifetimes?

**Date:** 2026-11-02 · **File:** `work/lb_scan/sub_v17/dqi.kmb` · **SHA-256:** `e3928244a1c18b48972349314711427e67e9cc53a023296f57524d2cb67c3adb`
**Tool:** `work/dqi_sources/width_liveness.py` (streaming .kmb SOA parser, zero-copy mmap+numpy) · results JSON: `width_liveness_results.json`
**Baseline:** Q=892, mean Toffolis T=398,138.69, R=1.19126, ratio 64.76× (verifier log `verify_dqi_full_v17.log`, 102,400 shots, 0 errors)

## Verdict (BLUF)

**Renumbering/reuse cannot go below 892 — and 892→~860 is infeasible from public source.** 892 is a *strict* lower bound on the declared qubit count of this op stream under any renumbering or lifetime reuse — confirmed by three independent liveness models (naive first/last, R/HMR-split, and value-only where |0⟩ qubits are provably inert to phase gates). The peak is **not** dominated by idle ancillas: it is the contractual 840-qubit syndrome floor plus a 52-qubit working set in which **all 52 hold live values simultaneously** during `convert` sub-windows (0.202–0.218, 0.274–0.291) and the `unconvert` spike (0.740–0.749). The builder already pebbles aggressively (10 registers cycle as scan Toffoli scratch while 30+ hold state untouched for up to 49M ops).

- **892→~860: infeasible.** Freeing 32 working qubits requires duplicating ≥ ~20k Toffolis of producing work vs a Q² gain of ~28.1k Toffoli-equivalents *only in the most optimistic accounting*; every measured multi-qubit scenario is net-negative (10 churners: net factor 1.0418, ΔGM −0.32).
- **Realistic Q′ = 892**, net width reduction **0%**, ΔGM ≈ 0 — *with one small open probe*: the late-start trio q889/890/891 has Toffoli-free producers (extT3=0) and only 31–37 binding-region legs; if their producing networks are re-runnable after 0.291/0.749, Q′=889 at ΔT≈0 → ratio 65.20×, **ΔGM +0.054**. Feasibility not decidable at .kmb level (needs targeted symbolic pass on the three producers or the builder core). Expected value small; do not block on it.
- For reference: 892→860 at *unchanged* T would be worth **+0.59 GM** (23.9467→24.537); the absolute ceiling (all 52 working qubits gone, T unchanged) is **+0.98 GM**. Both foreclosed by the architecture.

## 1. Confirmed peak Q = 892

| source | value |
|---|---|
| .kmb header (`num_qubits`) | **892** |
| max qubit id used (any op target) | 891 (= 892−1, no unused ids) |
| official verifier log | `num_qubits: 892`, sha matches |
| naive peak concurrent liveness (this analysis) | **892** |
| refined peak (lifetimes split at R/HMR) | **892** |
| value-only peak (phase-inert \|0⟩ sharing allowed) | **892** |

Header: num_ops=64,168,150 · num_bits=104,140 · 3q-ops=453,312 (= `max_toffoli_count`, worst-case shot) · 2q-ops=58,957,489 · 1q-ops=573,134 · R/HMR ops=203,236 · qubits ever reset=880/892.

Register convention (from `KMB_REGISTER_TARGETS` packets): **S0…S69** = 70 syndrome registers × 12 qubits = ids **0…839** (the 840-qubit contractual floor: inputs restored, outputs returned). The 52 working ancillas are ids **840…891**, in no named register.

## 2. Circuit structure (from 17,764 INFO_TAG ops, 84 distinct tags)

| region | stream frac | static Toffolis | % of 453,312 |
|---|---|---:|---:|
| mask_projection (phase-only setup) | 0.000–0.037 | 0 | 0.0% |
| initial (syndrome load) | 0.037–0.041 | 0 | 0.0% |
| extract (inverse24/12 norm/scalar/products, multiply v) | 0.041–0.110 | 62,451 | 13.8% |
| synthesis | 0.110–0.197 | 31,224 | 6.9% |
| **convert** (head_pivot ×112, aligned_route ×50, full_head_product_stream ×8) | **0.197–0.292** | **59,573** | **13.1%** |
| scan (gf_iadd ×8,205) | 0.292–0.659 | 44,264 | 9.8% |
| **unconvert** | **0.659–0.754** | **75,689** | **16.7%** |
| unextract (companion_*, reverse * ×20 each) | 0.754–0.994 | 179,335 | 39.6% |
| uninitial + restore_masks (syndrome HMR measure-out) | 0.994–1.000 | 776 | 0.2% |

The two *binding* regions for width (where all 52 working qubits are simultaneously value-live) are **convert** and the **unconvert spike**; together they hold 29.8% of all static Toffolis.

## 3. Liveness results

**Naive model** (live = [first touch, last touch], all conditional ops assumed to execute):
peak = 892 over a *single continuous plateau* from op 3,411,845 (5.317%) to op 62,797,242 (97.864%) — i.e. from the moment the last late-start working qubit (q891) first appears until the last syndrome HMR. Every working qubit's span covers ≥95% of the stream (first value touch 4.1–5.3%, last 97.9–99.5%), so there is **no movable block per qubit**: the 52 working ancillas are persistent scratch registers, not transient intermediates.

**Value-only model** (segments split at R/HMR; |0⟩ stretches inert — the true renumbering bound, since Z/CZ/CCZ on |0⟩ are identity):
peak = 892, attained in 620 plateau runs totaling 5,448,499 ops (8.49% of stream), concentrated at:
- convert: sustained runs 0.202–0.218 (×2, span 241,698 each) and 0.274–0.291 (spans up to 371,756)
- unconvert: 0.740–0.749 (×2, span 241,698 each)
- plus small runs at 0.053–0.063 (late-start qubits coming online) and 0.85–1.0.

Working-only value-live profile (of 52): 25 @0.05 → 30 @0.10 → 39 @0.15 → **52 @0.20–0.29** → 42 @0.30–0.65 (scan) → 40 @0.70 → 34 @0.72 → **52 @0.74** (unconvert spike) → 48 @0.76–0.85 → 49 @0.90 → 46 @0.95 → 36 @0.99.

Syndrome floor (empirical): all 840 syndrome qubits value-live from 0.63% (mask_projection phase touches precede the 3.7% load) to 99.85% (uninitial HMR). Contractually irreducible.

**Idle-at-peak (naive peak midpoint = op 33,104,543, 51.6%, inside scan):** all 52 working qubits are naive-live there (their spans cover it), but only **42 are value-live**; of those 42, ~19 are *passive holders* — untouched for 23M–49M consecutive ops around the peak (q841/q865: zero touches for ~75% of the entire stream while holding a value). The other 10 working qubits (the churners) are |0⟩ at the peak instant. So the peak is NOT caused by busy ancillas sitting idle — it is caused by 52 simultaneously *held values*, most of them deliberately parked (pebbling). The actionable subset is identified in §4/§7 by binding-region Toffoli footprint.

### 20-phase histogram (live qubits at phase midpoint)

| ph | frac | naive | refined | value-only |
|--:|---|--:|--:|--:|
| 0 | 0.000–0.050 | 840 | 840 | 0 |
| 1 | 0.050–0.100 | 892 | 870 | 870 |
| 2 | 0.100–0.150 | 892 | 879 | 879 |
| 3 | 0.150–0.200 | 892 | 879 | 879 |
| 4 | 0.200–0.250 | 892 | 880 | 880 |
| 5 | 0.250–0.300 | 892 | **892** | **892** |
| 6 | 0.300–0.350 | 892 | 880 | 880 |
| 7–13 | 0.350–0.700 | 892 | 880 | 880 |
| 14 | 0.700–0.750 | 892 | 888 | 888 |
| 15–16 | 0.750–0.850 | 892 | 885 | 885 |
| 17 | 0.850–0.900 | 892 | 889 | 889 |
| 18 | 0.900–0.950 | 892 | 880 | 880 |
| 19 | 0.950–1.000 | 892 | 864 | 864 |

## 4. Working-set anatomy (52 qubits, three classes)

Value-coverage per region (fraction of the region during which the qubit *holds* a value — a qubit keeps its value from set until R/HMR even when untouched) plus Toffoli (3q-op) leg counts per region:

| class | count | qubits | behavior |
|---|--:|---|---|
| **active-worker** | 12 | 840, 842, 843, 844, 846, 848, 853, 859, 863, 873, 876, 879 | 45k–65k touches in scan, **0 Toffoli legs in scan** (pure CX/CZ/SWAP routing); value-live ≥0.95 in every region; convert coverage 1.00 |
| **passive-holder** | 30 | 841, 845, 847, 849, 850, 852, 855, 856, 857, 858, 860, 862, 865, 866, 869, 870, 872, 874, 877, 878, 880, 883, 884, 885, 886, 887, 888, 889, 890, 891 | value-live through scan (coverage 1.00) with **≤5k touches** (many exactly 0 — e.g. q841, q865 hold a value untouched for 48–49M ops, 75% of the stream); convert coverage 0.56–1.00 |
| **churner** | 10 | 851, 854, 861, 864, 867, 868, 871, 875, 881, 882 | the **scan Toffoli workhorses**: 20k–40k touches in scan incl. 6,036–8,048 Toffoli legs each (76,456 of scan's ≤132,792 3q legs), but value-live only 0–2% of scan (set→use→reset bursts); synthesis 0.97, convert 0.70–0.86, unconvert 0.57–0.78, unextract 0.78–0.93 |

This is deliberate pebbling by the builder: during scan, 10 registers cycle as Toffoli scratch while 42 others hold state (12 actively routed, 30 passively). The three **late-start** qubits 889/890/891 (first value touch at 5.317% — what pins the naive plateau start) are passive-holders with **extT3 = 0**: their values are produced by Toffoli-free (X/CX/SWAP) networks, and their binding-region Toffoli footprints are minimal (convT3+uncvT3 = 37/33/31).

Per-candidate Toffoli legs in the two binding regions (convT3 + uncvT3), ascending — the lower bound on re-derivation cost if a qubit's own legs dominate its producer:

| q | convT3 | uncvT3 | sum | class |
|--:|--:|--:|--:|---|
| 841 | 0 | 0 | **0** | passive-holder (cov 1.00/1.00) |
| 865 | 0 | 0 | **0** | passive-holder (cov 1.00/1.00) |
| 891 | 18 | 13 | 31 | passive-holder, late-start |
| 890 | 14 | 19 | 33 | passive-holder, late-start |
| 889 | 18 | 19 | 37 | passive-holder, late-start |
| 877 | 19 | 23 | 42 | passive-holder |
| 844 | 51 | 20 | 71 | active-worker |
| 879 | 68 | 24 | 92 | active-worker |
| 876 | 102 | 42 | 144 | active-worker |
| 878 | 258 | 18 | 276 | passive-holder |
| 849 | 376 | 39 | 415 | passive-holder |
| 847 | 530 | 38 | 568 | passive-holder |
| 840 | 408 | 167 | 575 | active-worker |
| … | | | | |
| 850 | 904 | 516 | 1,420 | passive-holder |
| 882 | 977 | 645 | 1,622 | churner |
| 851 | 1,152 | 861 | 2,013 | churner |
| 868 | 814 | 1,315 | 2,129 | churner |
| 861 | 433 | 2,658 | 3,091 | churner |
| 871 | 688 | 2,550 | 3,238 | churner |
| 867 | 1,833 | 1,685 | 3,518 | churner |
| 875 | 831 | 4,763 | 5,594 | churner |
| **10 churners** | **8,306** | **17,791** | **26,097** | |

## 5. Why renumbering alone cannot help

Q in the DQI cost is the header `num_qubits` = max id + 1. Renumbering (reusing ids across non-overlapping lifetimes) is semantically free and its optimum is the clique number of the lifetime-overlap graph = max concurrent live segments. All three models give **892**: even allowing |0⟩ qubits to share ids arbitrarily, there exist moments (convert 0.274–0.291, unconvert 0.740–0.749) where 840 syndrome + 52 working values are all simultaneously held. No permutation of ids reaches below 892. There are also no unused ids to drop.

## 6. Why "move the block" re-timing cannot help

Re-timing without recomputation = moving a qubit's value-holding window so it doesn't overlap the peak. That is impossible for any of the 52: every working qubit's window is bounded by its own producer and consumer ops (set in extract/synthesis, consumed in convert/scan/unconvert/unextract), and moving the window earlier or later collides with those. Moving it *out* of a binding region means not holding the value there — which is exactly recomputation (§7). And the working set cannot absorb itself: at the peak instants all 52 values are simultaneously needed (the 12 active workers' routed state, the passive holders' parked field elements, and the churners' burst values all coexist by construction of the transform). The builder's pebbling (30+ qubits parked untouched for tens of millions of ops) shows width was already optimized within this algorithmic structure; the residual 892 is the structure's concurrency requirement, not a packing artifact.

## 7. Recomputation scenarios vs break-even

**Cost model note:** DQI's T counts *Toffolis only* (dynamic CCX/CCZ/CSWAP; static 453,312 = worst-case shot). CX/CZ/SWAP/X/Z/R/HMR are **free in the cost formula** — so re-deriving a value whose producer is Toffoli-free costs ~0 in T (it adds ops/reaction-depth, which are not scored, and must be re-verified for correctness).

Break-even: freeing k qubits saves (1−(892−k)²/892²)·T ≈ k·893 Toffolis; added recomputation must stay below that. A freed qubit must be |0⟩ at **every** peak instant: convert runs [0.202–0.218] ∪ [0.274–0.291] **and** the unconvert spike [0.740–0.749] → typically 2 re-derivations (re-set after 0.291 and after 0.749), each costing ≈ its producing ladder.

| scenario | Q′ | ΔT (added Toffolis) | net cost factor (Q′/Q)²·(T′/T) | ratio | ΔGM (of 23.9467) |
|---|--:|--:|--:|--:|--:|
| baseline | 892 | 0 | 1.00000 | 64.760 | — |
| free q889/890/891 (Toffoli-free producers, 2 re-sets each) | 889 | ~0 (if producers re-runnable) | 0.99329 | 65.198 | **+0.0538** |
| free q841 or q865 (0 binding-region legs; 2× extract ladder ≈ 1,024–1,110) | 891 | +1,024…1,110 | 1.0003…1.0005 | 64.73…64.72 | −0.003…−0.004 |
| free 1 cheapest churner (q864, real dup cost) | 891 | +1,471 | 1.00145 | 64.667 | −0.0115 |
| free 2 cheapest (q864+q881) | 890 | +3,147 | 1.00339 | 64.541 | −0.0270 |
| free 3 cheapest | 889 | +5,092 | 1.00599 | 64.374 | −0.0476 |
| free all 10 churners | 882 | +26,097 | 1.04179 | 62.162 | **−0.3246** |
| dream: 892→860, T unchanged | 860 | 0 | 0.92954 | 69.669 | +0.5904 |
| ceiling: 892→840, T unchanged | 840 | 0 | 0.88681 | 73.026 | +0.9784 |

Notes:
- ΔT figures are *lower bounds*: duplicating a role means re-executing every 3q-op of its producing/consuming ladders, including shared legs on other qubits; the table's per-qubit leg counts exclude those shared legs.
- The only potentially net-positive row is the late-start trio (889/890/891): their values are produced by Toffoli-free networks (extT3 = 0) and they carry 31–37 binding-region legs. Feasibility hinges on **data availability**: the producing network's inputs (syndrome bits / other held values) must still be present at the two re-set points (post-0.291, post-0.749). Not decidable at .kmb level — needs a targeted symbolic pass on those three producers or the builder core. Even if fully successful: +0.054 GM (892→889). If the producers depend on transient intermediates, cost ≥ their consuming-ladder Toffolis → net-negative like all other rows.
- 892→860 would require freeing 32 qubits. Only 6 candidates have binding-region footprints < 150 legs; the remaining 26 each cost ≥ 276 legs × 2 re-sets, and their combined duplication (≫ 20k Toffolis) exceeds the Q² gain (≈ 28.1k Toffoli-equivalents) only in the most optimistic shared-leg accounting — realistically far worse. **Infeasible.**
- The public lineage already explored this axis: hengck23's 889-Q decoder (840+49) scored worse (ratio 59.85× vs 64.76×) because its T was higher; SomeJoint's 892-Q + busyaprime's caching is the known public optimum. Fewer working qubits ⇔ more Toffolis has been empirically confirmed by the field.

## 8. Concrete re-timing plan (what it would take, and why it mostly isn't worth it)

The only structurally plausible plans, in order of expected value:

**Plan A — free the late-start trio (889/890/891): the only potentially positive play.**
1. Their values are produced by Toffoli-free networks after 5.317% and they carry only 31–37 Toffoli legs across both binding regions.
2. Mechanism: add R (free) at ~0.200 and ~0.738; re-run their producing networks (CX/SWAP/X only → ΔT ≈ 0) just before their first post-window consumer (~0.292, ~0.750).
3. Gate: verify the producers' inputs are still available at those re-set points (targeted symbolic pass on the three producing sub-circuits, or builder core). If any producer reads a transient intermediate → abort (cost flips negative).
4. Expected: Q′=889, ΔT≈0, ratio 65.20×, **ΔGM +0.054** (23.9467→~24.00). Risk: added ops change reaction depth and must pass full official verification (new salt draws).

**Plan B — free a passive holder with zero binding-region legs (q841/q865).** Same mechanism, but each re-set re-runs an extract ladder with ~512–555 own Toffoli legs (×2 re-sets ≈ 1,024–1,110 > 893 break-even) → **net-negative as measured**; only viable if shared-leg accounting or a single re-set applies (their values may not be needed in both binding regions — check consumer positions first).

**Plan C — free churners / multi-qubit reductions (the 860 dream).** Requires serializing the 52-lane transform into ≤42 concurrent lanes with re-derivation passes: best case Q′=882 at ΔT ≥ +26,097 → net factor 1.0418, **ΔGM −0.32**. Strictly dominated by doing nothing. Not recommended.

What *would* be needed to make width pay beyond Plan A: an in-place basis transform whose scratch requirement is ≤ 42 concurrent field-element lanes throughout convert **and** unconvert, with re-derivation cost < 893 Toffolis per lane eliminated. That is an algorithmic redesign of the decoder's transform layer (private builder core territory; the 25 `dqi_sources/*.py` deltas import ~40 unpublished modules and cannot be executed here). At .kmb level the evidence says the current 52-lane parallel transform with 10-register scan pebbling is already at the Q↔T Pareto knee for this architecture family.

## 9. Reproduce

```bash
cd /Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum
python3 work/dqi_sources/width_liveness.py work/lb_scan/sub_v17/dqi.kmb \
    --json work/dqi_sources/width_liveness_results.json
# ~45 s, <2 GB RAM (mmap views; no full file load)
```

Cross-checks performed: sha256 of analyzed file matches verifier log; header counts match verifier log (`num_qubits 892`, `num_bits 104140`, `num_ops 64,168,150`, static 3q-ops = `max_toffoli_count` 453,312); methodology reproduces declared width exactly on the independent 62-Q `invsqrt.kmb` (peaks 62/62/62).
