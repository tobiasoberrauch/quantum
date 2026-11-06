# Lever-Measurement Harness — Plan

Once the shadow decoder is modifiable (tower-field inverse/division ported, basic
pebbling added), this document describes HOW to measure the two major optimization
levers identified in Report H §5.

## Source

Report H §5 (`work/dqi_builder_recon/report_H_builder_feasibility.md`), Report A §3–4
(`work/dqi_t_sprint/report_A.md`), WIDTH_ANALYSIS (`work/dqi_sources/WIDTH_ANALYSIS.md`).

## Lever 1: Inverse-Overhead Removal (THE lever)

### What it is

The `un*` blocks (unextract, unsynthesis, unconvert) carry **+48,863 Toffolis (12.3%
of fc3ba816's T)** over their forward counterparts. The largest single gap is
**unextract: +38,029 T** (63.8% over its forward).

In the shadow decoder, the analogous structure is:
- Forward EEA (222 iters) → Reverse EEA (222 iters): the reverse IS the adjoint
- Chien/Forney has no explicit inverse (it's a one-shot phase kickback)
- The "inverse overhead" in the shadow decoder manifests as the full reverse EEA cost

### Two variants

#### Variant 1: Retain-don't-reuse [REJECT]

Keep forward intermediates alive across the middle so the inverse replays in exact
reverse. Trades T for Q (more qubits held longer).

**Why reject:** Q is at the strict Pareto knee (WIDTH_ANALYSIS §4). Break-even for
freeing k qubits ≈ k×893 Toffolis. Every measured free-qubit scenario is net-negative
except the late-start trio (+0.054 GM). In the shadow decoder (Q=1893), we have more
width headroom, but the principle holds: holding intermediates increases Q² in the
score denominator.

**Measurement protocol (if ever revisited):**
1. Modify reverse EEA to skip recomputation, reuse forward pebbles
2. Measure new Q and T
3. Compute Δratio = R·Q'²·T' vs R·Q²·T
4. Expect: ΔT < 0 but ΔQ > 0, net ratio change ≈ 0 or negative

#### Variant 2: Shared-pebble-tree [VIABLE]

Schedule the inverse to **reuse the same pebbled values** the forward produced,
eliminating the recompute at **no peak-width cost**. The key insight: if a value was
pebbled (computed, used, uncomputed) in the forward, the inverse can re-pebble it
using the same wire at the same time, avoiding the full recompute.

**Mechanism:**
1. Instrument the forward EEA to record which values are pebbled and their lifetimes
2. In the reverse EEA, instead of recomputing from scratch, re-derive the pebbled
   values from still-live registers (where possible) or re-pebble on the same wires
3. Net effect: reverse EEA cost drops from full-recompute to partial-recompute

**Expected delta (ceiling):** Remove full +48,863 → ratio ×1.14 (for fc3ba816).
For the shadow decoder: remove ~50% of reverse EEA cost → ΔT ≈ -1M T (estimate).
Realistic capture: 50–80% of ceiling.

**Measurement protocol:**
1. Build shadow decoder with instrumented pebbling (record all alloc/free events)
2. Identify values that are computed in forward AND needed in reverse
3. Modify reverse to reuse (share) these values via the same wire allocation
4. Run 256-shot correctness gate (0 val/phase errors required)
5. Run 102,400-shot verifier for true score
6. Record: ΔT, ΔQ, Δratio vs unmodified shadow decoder

### Verification protocol (both levers)

```
1. Build modified circuit
2. 256-shot verifier: MUST report 0 value_errors AND 0 phase_errors
   (status will be FAIL due to Clopper-Pearson at n=256, but errors must be 0)
3. If step 2 passes: 102,400-shot verifier for true R·Q²·T
4. Compare score to baseline (this shadow decoder's unmodified score)
5. Record in levers/results.json
```

**Critical:** Seed is derived from circuit SHA-256. Every modified circuit draws its
OWN deterministic test set. NO shot-by-shot diff vs the original is possible. Rely on
full re-verification each time.

---

## Lever 2: De-Pebbling

### What it is

267,210 CCX gates (69.8% of fc3ba816's CCX) are **recomputed-not-held**: the value
is computed, used once, then uncomputed (pebbled) rather than kept alive on a wire.
"De-pebbling" means: hold the value on an idle wire instead of recomputing it later.

Saves Toffolis (no recompute) at the cost of Qubits (wire must be |0⟩ for the
value's entire lifetime).

### Why likely small

WIDTH_ANALYSIS §4 shows:
- 30 passive-holder wires are **value-live through the stream** (coverage 1.00)
- 10 churner wires are |0⟩ only 0–2% of scan duration
- Truly-idle wires (|0⟩ for a long enough span to hold a pebbled value) are **scarce**

In the shadow decoder (Q=1893, much wider than fc3ba816's Q=891), there may be MORE
idle wires available. This is where the shadow decoder could actually show a de-pebbling
advantage that fc3ba816 can't exploit.

### Measurement protocol

1. Instrument shadow decoder: track |0⟩-ness of every ancilla wire over time
2. Identify wires that are |0⟩ for ≥ K consecutive Toffoli-depth steps
3. For each pebbled value with lifetime ≤ K: try holding it on the idle wire
4. Measure: ΔT (saved recomputes) vs ΔQ (wires now occupied)
5. Compute net ratio change
6. Iterate: greedy assignment of values to idle wires, maximizing ΔT/ΔQ

### Expected delta

For fc3ba816: likely small (scarce idle wires). `[HYP]`
For shadow decoder (Q=1893): potentially larger (more width headroom). `[SPEK]`
Ceiling: save all 267,210 CCX → T drops by ~45% → ratio ×~2.7 (but Q increases).
Realistic: 5–20% of pool → ΔT ≈ -15K to -55K.

---

## Measurement Infrastructure

### Files to create (when implementing)

```
work/dqi_shadow/levers/
├── README.md              ← this file (plan)
├── results.json           ← accumulated measurement results
├── measure_inverse.py     ← Lever 1 instrumentation + measurement
├── measure_depebble.py    ← Lever 2 wire-liveness analysis
└── shadow_decoder_v*.py   ← modified decoder versions (one per lever attempt)
```

### Result schema (results.json)

```json
{
  "lever": "inverse_overhead_shared_pebble",
  "version": "shadow_v2",
  "baseline": {
    "Q": 1893,
    "T_mean": 5725109.3,
    "T_static": 5725461,
    "R": 1.1913,
    "score": 24439467666108.3,
    "ratio": 1.0
  },
  "modified": {
    "Q": null,
    "T_mean": null,
    "T_static": null,
    "R": null,
    "score": null,
    "ratio": null
  },
  "delta": {
    "dT": null,
    "dQ": null,
    "dratio": null,
    "dGM": null
  },
  "correctness_256": {"value_errors": null, "phase_errors": null},
  "correctness_102k": {"value_errors": null, "phase_errors": null},
  "notes": ""
}
```

### Prerequisites

- [ ] Tower-field inverse ported (port step 2) — makes the decoder modifiable
- [ ] Basic pebbling pass implemented — enables wire-liveness tracking
- [ ] 102,400-shot baseline measured ✓ (done: `baseline_102k.json`)
