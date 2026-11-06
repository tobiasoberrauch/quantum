# Track A — invsqrt product-caching probe (busyaprime method)

**Verdict: NEGATIVE RESULT.** busyaprime's product-caching / measurement-based-uncomputation
yields **~0 static Toffoli savings** on the current best-public 62-qubit invsqrt circuit — far
below the ~50 threshold. No improvement was implemented or submitted.

Target circuit: `work/lb_scan/sub_v15/invsqrt.kmb`
(SHA-256 `bce2948ff24e20fe59666d131f7fc4316a905103937272c52fdd39d494b6fe47`, unchanged).
Baseline (already measured by lead): cost **100568.4991945597**, ratio 20.6503,
1495 static Toffolis, 1325.48 mean executed, worst_error_over_tolerance 0.9993237694056958.

---

## (a) Was busyaprime's builder code found?

**No — not in the specified public notebooks.** Reimplemented the symbolic repeat-finder
independently from his published method description.

- `busyaprime/lb-22-72431-22x-cheaper-than-google-s-circuits` → **404** (slug does not exist).
- `busyaprime/23-906-local-gm-exact-product-caching-892q-dqi` → **404** (slug does not exist).
- `busyaprime/lb-23-91003-exact-dqi-rewrites-at-892-qubits` (the one we had) → method
  description (markdown) + SHA-check/verify/zip code only. **No builder code.**
- `manwithacat/vqcc-hedge-wizardry-notebook` → pulled OK; it's an entry-collection that imports a
  `kickmix_tools.py` utility from its attached **dataset** (not the notebook). The HW-07 ladder and
  shared tooling live in the 210 MB dataset `manwithacat/vqcc-hedge-wizardry`, not fetched here.
- Most likely home of the real builder: busyaprime's own dataset `busyaprime/33-qcc-v8-members`
  (cited in his credits) or `kickmix_tools.py`. Neither pulled (heavy; and the method is fully
  specified in prose, so it does not change the invsqrt answer).

Method reimplemented exactly as described: per-wire Boolean-function tracking over GF(2)
(inputs + measurement outcomes + classical masks = fresh variables; CNOT = XOR; AND = new product),
group Toffoli-like gates by identical control-product signature + identical execution condition.

## (b) Candidate repeat-chains on the 62Q invsqrt

Exact symbolic pass (`symbolic_pass.py`, int-bitmask ANF, no cap on controls; ran in ~5 s):

| metric | value |
|---|---|
| ops | 47,281 |
| Toffoli-like | 1,495 = 1,153 CCX + 141 CCZ + 201 CSWAP |
| fresh symbolic vars | 919 |
| max ANF size seen | **1,572,864 monomials** (deep ripple-carry adder internals) |
| CCX groups with exact controls | 19, **all size 1** → **0 chains** |
| CCZ groups | 0 → **0 chains** |
| CSWAP shared-control groups | 6 (sizes 11,10,10,10,9,2) — **not cacheable**, see below |
| repeated (c1,c2) wire-name pairs | 309 |
| repeated exact (c1,c2,t) triples | 210 |
| name-pairs verified to be true product repeats | **0** |

**Genuine product-repeat chains: 0.**

Why the 309/210 name repeats are *not* repeats: qubits are pebbled/reused, so the same wire names
hold **different Boolean functions** at different times. Confirmed two independent ways:
1. Exact symbolic ANF comparison of all simple-control CCX gates → 19 distinct signatures, none shared.
2. Simulation spot-checks (prefix circuits, same explicit seed + same x-batch; mechanism validated
   with a positive control diff=0 / negative control diff=119): every top repeated pair differs.
   - compute-phase pairs: `q14,q15` diff=353, `q14,q16` diff=345, `q14,q18` diff=334, …
   - uncompute-phase exact triples (late loop, e.g. `q14,q15,q20` ×10 @ lines 44341…45199):
     `q14,q15` diff=153, `q14,q18` diff=168, `q26,q37` diff=11 → all **DIFFERENT**.

The 6 CSWAP "chains" are **flag-controlled rotations** (the normalize/denormalize bit-reversals:
one flag wire q42–q46 read as control by many distinct swaps, e.g. `CSWAP q46 q0 q5 / q1 q4 / …`).
Reading a shared control is free; there is no recomputed product, so these are **false positives**
for caching (my grouping key was control-ANF, which lumps them together).

## (c) Estimated static Toffoli savings

**~0.** The only number the raw grouping produced (46, from the CSWAP flag-rotation groups) is
invalid for the reasons above. No CCX/CCZ product is computed more than once, so there is nothing
to cache. This is far below the ≥~50 bar.

## (d) Free-wire feasibility

Moot — there are no repeat-chains to place. For completeness: the circuit has 62 qubits with only
40 scratch (q22–q61), heavily time-multiplexed (pebbled); free wires would be the binding constraint
exactly as busyaprime found at 892 qubits. Even a handful of placeable chains would compete for the
same idle wires.

## (e) Negative result — reasons

1. **Structure is compute-once / clear-by-measurement, not compute-twice.** The circuit already uses
   the Gidney trick pervasively: **897 HMR + 93 R** gates (measurement-based uncomputation via
   `del_and` = HMR + conditional CZ). Every AND product is computed once and cleared by X-basis
   measurement, never recomputed. There is no "recompute-to-clear" ladder to replace (the DQI's 24
   sites / −240 Toffolis have no invsqrt analogue).
2. **Multiplier partial products are all unique.** Column-truncated Horner/multiplier rows use
   distinct (control, source) pairs; exact ANF comparison confirms 0 shared products among the 19
   simple-control CCX gates, and simulation confirms the 309 complex/name-repeated ones differ.
3. **Carries are position-specific huge functions** (up to 1.57 M monomials) — two distinct carries
   being identical is structurally impossible, and spot-checks confirm the late-phase loop reuses
   qubits with different data, not the same function.
4. **CSWAPs are rotations, not products** — shared control, distinct targets; nothing to cache.

Conclusion: busyaprime's gains on DQI came from (i) 24 recompute-to-clear ladders and (ii) 2,340
repeated flag-products in an *iterative decoder*. The one-shot Newton–Raphson invsqrt pipeline has
neither. **No safe static-Toffoli improvement is available from this technique family on invsqrt.**

---

## Artifacts (all under `work/invsqrt_caching/`)
- `invsqrt.kmx` — text dump of the live .kmb (read-only copy for analysis).
- `symbolic_pass.py` — exact GF(2) ANF repeat-finder (v3, int-bitmask monomials).
- `analysis.json` — full pass output (groups, chains, name-pair cross-check).
- `diag.py`, `diag2.py` — control-complexity diagnostics.
- `spotcheck.py` — prefix-simulation spot-checks of repeated name-pairs/triples.
- `vqcc-hedge-wizardry-notebook.ipynb` — pulled manwithacat notebook (HW-07 context).

## Next steps (for the lead)
- If the exact builder is wanted for other tracks: pull dataset `busyaprime/33-qcc-v8-members`
  or `manwithacat/vqcc-hedge-wizardry` (210 MB) and look for `kickmix_tools.py`.
- invsqrt cost is dominated by the 1,153 CCX multiplier/adder Toffolis; further gains would need
  algorithmic/pebbling changes (different track), not product caching.
- The 1495→1325.48 mean-executed gap (~170 conditional Toffolis) is a separate lever (condition
  pruning), out of scope here.
