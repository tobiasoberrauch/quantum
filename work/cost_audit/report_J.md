# Cost Audit J — Authoritative Gate Price List (all 3 verifiers)

Scope: extract the EXACT per-gate price for every op type, per benchmark, straight from the
official verifiers + the kickmix cost counters they call. Tag every price **[FAKT]** with the
file:line that defines it. Empirically re-confirmed against the installed kickmix library via
`work/cost_audit/probe_pricing.py`.

## 0. The real "shared cost model" is kickmix, not costs.py

The task pointed at `starter_kit/verifier/costs.py` as "the shared cost model with
T_PER_TOFFOLI=4 and the rotation formula". **Correction:** that file
(`starter_kit/starter_kit/verifier/costs.py`, identical copy at
`data/verifiers/dfthcsos/scoreinfra/costs_prepare.py`) is the **DFTHC-SOS state-preparation
heuristic** (`SpinFreeData_V1`: `QR`, `QI`, `outer_state_prep`, `inner_state_prep`,
`givens_rotations`). It has no `T_PER_TOFFOLI` and no rotation-synthesis formula.

The authoritative per-gate pricing lives in **two places**:

1. **kickmix `OperationStatistics`** — the counters every verifier reads.
   `qualtran/kickmix/src/kickmix/py/operation_statistics.pybind.cc`:
   - `num_toffoli_like()` = `CCX + CCX_IF + CCZ + CCZ_IF + CSWAP + CSWAP_IF` **[FAKT L118–122]**.
     Docstring: "The number of Toffoli-like (`CCX`, `CCZ`, and `CSWAP`) operations. Includes both
     unconditional … and classically conditioned … operations." **[FAKT L276–304]**.
     → **CSWAP counts as ONE Toffoli-like, not three.**
   - `num_t_like()` = `z_pow_level_counts[3]` (Z_POW at Clifford-hierarchy level 3 = T/T⁻¹) **[FAKT L128–130]**.
   - `num_z_pow(min_level, max_level)` = sum of Z_POW over levels **[FAKT L140–148]**.
   - `num_non_clifford()` = `num_toffoli_like() + num_z_pow(3)` **[FAKT L124–126]** (not used by any score).

2. **Each verifier chooses which counters enter its score.** Only `num_toffoli_like` (all 3), plus
   `num_t_like` + `num_z_pow(≥4)` (invsqrt only) are ever priced. Everything else is 0.

### Clifford-hierarchy level of a Z_POW angle (half turns)
From `num_z_pow` docstring **[FAKT operation_statistics.pybind.cc L382–389]** and
`FixedPrecisionAngle128::clifford_hierarchy_level` **[FAKT fixed_precision_angle_128.h L21–22]**,
empirically confirmed by the probe:

| half-turns | level | meaning | priced? |
|---|---|---|---|
| 0.0 | 0 | identity | FREE |
| 1.0 | 1 | Pauli Z | FREE |
| 0.5 / 1.5 | 2 | Clifford S / S⁻¹ | FREE |
| odd × 0.25 | 3 | T / T⁻¹ | **1 T** (invsqrt only) |
| odd × 2^(1−k), k≥4 | ≥4 | non-Clifford rotation | **rotation cost** (invsqrt only) |
| 0.1 (non-dyadic) | 128 | worst-case rotation | **rotation cost** (invsqrt only) |

### Conditional (`_IF`) / condition-stack counting — the exploitable lever
Every op is counted by `new_op_counters[kind].masked_increments(cond)` **[FAKT sim.h L507–509]**,
where `cond` is the AND of the active `PUSH_CONDITION` stack and the `if b` bit for `_IF` ops
**[FAKT sim.h L315–319, L380–385, L485–496]**. Consequence (probe-confirmed):
a `CCX … if b` contributes **0** on shots where `b=0` and **1** where `b=1`; the score uses the
**mean over shots**, so a Toffoli conditioned on a rarely-set bit costs `P(b=1) < 1` on average.
`INFO_TAG` is forced to always-count (`cond = ~TWord{}`) **[FAKT sim.h L493–497]** but it is free
anyway. **All three verifiers read the SIMULATOR's executed (condition-aware) count, not the static
circuit count** — invsqrt **[FAKT verify_submission_invsqrt.py L298]**, dqi **[FAKT
verify_submission_dqi.py L391–392]**, dfthcsos **[FAKT scoreinfra/circuits.py L556]**.

---

## Benchmark I — invsqrt (`data/verifiers/invsqrt/verify_submission_invsqrt.py`)

Scored metric (quoted):
```
toffolis = toffoli_count + t_count / T_PER_TOFFOLI            # L324
t_count  = t_base + (n_rot * rotation_t_count(eps) if n_rot else 0)   # L323
score    = circuit.num_qubits * toffolis                     # L327
```
with `T_PER_TOFFOLI = 4` **[FAKT L65]**, `rotation_t_count(eps) = 0.56*log2(1/eps) + 5.3`
**[FAKT L148–149]**, and the per-shot means `toffoli_count = mean num_toffoli_like` **[FAKT L317]**,
`t_base = mean num_t_like` **[FAKT L318]**, `n_rot = mean num_z_pow(≥4)` **[FAKT L319]**.

**Where ε comes from** (dynamic, per-submission — NOT a constant):
```
eps = math.pi * min_margin / 2**64 / n_rot if n_rot else None   # L320
```
`min_margin` = smallest `(tol(x) − |error(x)|)` over all shots, in 2⁻⁶⁴-turn units **[FAKT
L295, L313]**. Derivation from the docstring **[FAKT L36–38]**: each rotation may add `2ε` radians;
`n_rot · 2ε ≤ 2π · min_margin·2⁻⁶⁴` ⇒ `ε = π·min_margin·2⁻⁶⁴/n_rot`. More leftover phase tolerance
⇒ larger ε ⇒ cheaper rotations.

Note on the task's phrasing "C = mean_Toffolis + (t_count + Σ_rot synthesis)/4": the rotation
synthesis term `n_rot·rotation_t_count(eps)` is **already inside** `t_count` (L323), so the correct
form is `C = toffolis = mean_Toffolis + t_count/4` with `t_count = t_base + n_rot·rot(eps)`.
"Q_peak" is actually `circuit.num_qubits` = the circuit's **declared total width** (static), not a
temporal peak **[FAKT L327, L334]**.

| gate/op | price in C (= `toffolis`) | notes |
|---|---|---|
| CCX, CCX_IF | 1 (mean) | `num_toffoli_like` **[FAKT L317]**; `_IF` fires only where bit=1 |
| CCZ, CCZ_IF | 1 (mean) | ditto |
| CSWAP, CSWAP_IF | **1 (mean)** | **one Toffoli-like, not 3** **[FAKT op_stats L118–122]** |
| T-gate (Z_POW lvl 3) | 1/4 | `t_base/4`, T_PER_TOFFOLI=4 **[FAKT L318,L324,L65]** |
| Rotation (Z_POW lvl ≥4) | rot(eps)/4 = (0.56·log2(1/eps)+5.3)/4 each | **[FAKT L319,L323,L148–149,L320]** |
| Z_POW lvl 0/1/2 (id/Z/S) | **0** | below level 3, never counted |
| CX, CX_IF | **0** | not in any priced counter |
| CZ, CZ_IF | **0** | |
| SWAP, SWAP_IF | **0** | free 2-qubit routing |
| X, X_IF | **0** | |
| Z, Z_IF | **0** | (Pauli-Z as a gate; distinct from Z_POW) |
| R, R_IF | **0** | measurement-based reset/dephase |
| HMR, HMR_IF | **0** | measurement-based uncompute |
| BIT_STORE0/1, BIT_INVERT (+_IF) | **0** | classical-bit ops |
| NEG, NEG_IF | **0** | global phase flip |
| INFO_TAG | **0** | always-counted but free |
| PUSH/POP_CONDITION | **0** | free; makes inner ops conditional |
| DEBUG_PRINT* | **0** | |

**Free resource (I):** the entire Clifford + measurement set (CX, CZ, SWAP, X, Z, R, HMR, BIT_*,
NEG) costs 0 in C. The single biggest lever to save a priced Toffoli = **conditional Toffolis**
(`CCX … if b` / `PUSH_CONDITION`): spend free HMR/R to create condition bits, AND several of them
so the Toffoli fires on a rare branch → average cost `P(fire) ≪ 1`. Caveat: every added qubit
raises `circuit.num_qubits`, i.e. the Q multiplier, so free prep is free in C but **not** in the
final `Q·C`.

---

## Benchmark II — dqi (`data/verifiers/dqi/verify_submission_dqi.py`)

Scored metric (quoted):
```
rep_factor = repetition_overhead(eps_plus)        # L415
toffolis   = sum(num_toffoli_like) / num_shots    # L416  (mean EXECUTED Toffolis per shot)
score      = rep_factor * (num_qubits ** 2) * toffolis   # L420
```
- `R(eps) = ln(2) / -ln(1/2 + 2*sqrt(eps))` **[FAKT L130–136]**, `R(0)=1`.
- `eps_plus = clopper_pearson_upper_bound(total_errors, num_shots, log2_delta)` **[FAKT L408,
  L139–171]**, one-sided Clopper-Pearson at confidence `1 − 2^log2_delta`,
  `DEFAULT_LOG2_DELTA = -128.0` ⇒ confidence `1 − 2⁻¹²⁸` **[FAKT L58]**.
- **Z_POW is FORBIDDEN** (raises if present) **[FAKT L349–350]** — so there are no T-gates or
  rotations to price here; the only priced op class is Toffoli-like.
- `num_qubits = circuit.num_qubits` (declared width) **[FAKT L417, L438]**.

**Only CCX/CCZ/CSWAP (+_IF) count as Toffolis** — `num_toffoli_like` **[FAKT op_stats L118–122]**,
read from the simulator (executed, condition-aware) **[FAKT L391–392, L416]**. CX, CZ, SWAP, X, Z,
R, HMR, BIT_*, NEG all contribute **0**.

| gate/op | price in T (= `toffolis`) | notes |
|---|---|---|
| CCX, CCX_IF | 1 (mean) | `num_toffoli_like` **[FAKT L416]** |
| CCZ, CCZ_IF | 1 (mean) | |
| CSWAP, CSWAP_IF | **1 (mean)** | one, not 3 **[FAKT op_stats L118–122]** |
| Z_POW (any level) | **FORBIDDEN** | raises **[FAKT L349–350]** |
| CX, CX_IF | **0** | |
| CZ, CZ_IF | **0** | |
| SWAP, SWAP_IF | **0** | |
| X, X_IF | **0** | |
| Z, Z_IF | **0** | |
| R, R_IF | **0** | |
| HMR, HMR_IF | **0** | |
| BIT_STORE0/1, BIT_INVERT (+_IF) | **0** | |
| NEG, NEG_IF | **0** | |
| INFO_TAG | **0** | |
| PUSH/POP_CONDITION | **0** | free; makes inner Toffolis conditional |
| DEBUG_PRINT* | **0** | |

**Free resource (II):** same free set as (I), minus Z_POW (illegal). Biggest lever = conditional
Toffolis. Caveat is sharper here: score ∝ `Q²`, so each added qubit for free prep costs **2×**
relative to saving one Toffoli unit — free prep must clear `ΔT/T > 2·ΔQ/Q` to pay off.

---

## Benchmark III — dfthcsos (`data/verifiers/dfthcsos/verify.py` + `scoreinfra/`)

Scored metric (quoted, module docstring **[FAKT verify.py L53–60]** and `score_from_metrics`
**[FAKT L546–555]**):
```
score      = lambda_eff * T_total * Q_total
lambda_eff = sqrt(E_gap * (2*Lambda - E_gap))          # L347–350 (of loaded words)
T_total    = ANGLES_Toffolis                            # sim num_toffoli_like, U_T + U_T†
           + outer_state_prep() + inner_state_prep()    # SpinFreeData_V1 heuristic (incl. _dag)
           + 2*(N-1)*(2*brot-1)                         # Givens rotations
Q_total    = outer_persistent + inner_persistent        # SpinFreeData_V1
           + J*brot                                     # persistent angle-word registers
           + max(outer_temp, inner_temp, angles_temp)   # shared temporary workspace
```
- `ANGLES_Toffolis` = mean `num_toffoli_like` per shot over forward+reverse pass
  **[FAKT scoreinfra/circuits.py L556]** (executed, condition-aware).
- Heuristic Toffolis/qubits from `SpinFreeData_V1(R,B,C,N=76,chi=KEEP_BITS=10,beta=brot)`
  **[FAKT verify.py L436–468, L139]**; `givens_rotations = 2*(N-1)*(2*beta-1)`
  **[FAKT costs_prepare.py L141–147]**.
- **Z_POW is FORBIDDEN** in the ANGLE_k circuits (raises before simulating)
  **[FAKT scoreinfra/circuits.py L419–430]**.
- `angles_temp = max_k ANGLE_k.num_qubits − selection − J*brot` **[FAKT verify.py L405–408]**;
  ANGLE_k circuits capped at `QUBIT_CAP = 128` qubits **[FAKT verify.py L134, L553]**.
- What counts as "Toffolis" here = **CCX/CCZ/CSWAP (+_IF)** only, same `num_toffoli_like`
  **[FAKT op_stats L118–122]**. The heuristic block is a **fixed formula** (independent of which
  free gates you use inside the circuits).

| gate/op | price in T_total | notes |
|---|---|---|
| CCX, CCX_IF | 1 (mean, ANGLE_k circuits) | `num_toffoli_like` **[FAKT circuits.py L556]** |
| CCZ, CCZ_IF | 1 (mean) | |
| CSWAP, CSWAP_IF | **1 (mean)** | one, not 3 **[FAKT op_stats L118–122]** |
| Z_POW (any level) | **FORBIDDEN** | raises **[FAKT circuits.py L419–430]** |
| CX, CX_IF | **0** | free inside ANGLE_k |
| CZ, CZ_IF | **0** | |
| SWAP, SWAP_IF | **0** | |
| X, X_IF | **0** | |
| Z, Z_IF | **0** | |
| R, R_IF | **0** | |
| HMR, HMR_IF | **0** | |
| BIT_STORE0/1, BIT_INVERT (+_IF) | **0** | |
| NEG, NEG_IF | **0** | |
| INFO_TAG | **0** | |
| PUSH/POP_CONDITION | **0** | free; makes inner Toffolis conditional |
| DEBUG_PRINT* | **0** | |
| (state-prep + Givens) | fixed heuristic | not gate-dependent; `SpinFreeData_V1` **[FAKT costs_prepare.py L103–147]** |

**Free resource (III):** same free set as (II). Biggest lever = conditional Toffolis inside the
ANGLE_k circuits. Caveat: added workspace qubits raise `angles_temp` ⇒ `Q_total` (linear), and the
128-qubit cap on ANGLE_k bounds how much free prep fits without rejection.

---

## Findings & flags

1. **CSWAP = 1 Toffoli, NOT 3.** `[FAKT operation_statistics.pybind.cc L118–122]` — `num_toffoli_like`
   sums `CSWAP` once, alongside `CCX`/`CCZ`. Any cost model (ours or the advisory's) that prices
   CSWAP at 3 Toffolis is **3× overpriced** on every CSWAP. Probe: single `CSWAP` → `toffoli_like=1`.

2. **The advisory's "CNOT=0, HMR=0, Toffoli=1" is CORRECT as a price list but INCOMPLETE for
   invsqrt.** CX=0 and HMR=0 hold in all three benchmarks `[FAKT probe; op_stats L118–122]`.
   "Toffoli=1" holds as *one unit of the priced metric per executed CCX/CCZ/CSWAP* in all three.
   BUT invsqrt **also prices T-gates (=1, i.e. ¼ C) and arbitrary rotations (≈(0.56·log2(1/ε)+5.3)/4
   C each)** `[FAKT invsqrt L318–324, L148–149]`; dqi and dfthcsos **ban Z_POW entirely**
   `[FAKT dqi L349–350; circuits.py L419–430]`. So the flat "Toffoli=1" picture is complete only
   for dqi/dfthcsos.

3. **"Toffoli=1" is an AVERAGE, and that is the exploitable asymmetry.** All three scores use the
   **simulator's executed count**, where a `_IF`/`PUSH_CONDITION` Toffoli contributes only on shots
   whose condition bit is set `[FAKT sim.h L507–509; invsqrt L298; dqi L391; circuits.py L556]`.
   Probe: `CCX … if b` with b=0 → 0, b=1 → 1. So Strategy 5's "free CNOT/HMR prep to save
   Toffolis" works **only insofar as** the free HMR/R/CX/BIT ops build condition bits that are
   rarely set, turning unconditional Toffolis into rarely-firing conditional ones. The floor is the
   branch probability: a Toffoli needed on branches of total probability p cannot cost less than p.
   It is **not** "arbitrarily free" — you cannot drive a *useful* Toffoli's cost to 0.

4. **Free gates are free in the Toffoli metric but NOT in the qubit metric — the hidden tax on
   Strategy 5.** Adding qubits for "free CNOT/HMR prep" raises the Q factor in every score:
   invsqrt `Q·C` (linear) `[FAKT invsqrt L327]`, dqi `R·Q²·T` (**quadratic**) `[FAKT dqi L420]`,
   dfthcsos `λ_eff·T·Q_total` (linear, plus a hard 128-qubit cap on ANGLE_k) `[FAKT verify.py L555,
   L134]`. Net-win thresholds: invsqrt/dfthcsos need `ΔT/T > ΔQ/Q`; **dqi needs `ΔT/T > 2·ΔQ/Q`**.
   The advisory omits this trade-off.

5. **No per-benchmark asymmetry among the free gates.** CX, CZ, SWAP, X, Z, R, HMR, BIT_*, NEG,
   INFO_TAG, PUSH/POP_CONDITION are 0 in **all three** benchmarks (probe-confirmed). The only
   cross-benchmark differences are: (a) invsqrt additionally prices T + rotations; (b) dqi &
   dfthcsos forbid Z_POW; (c) the Q exponent (1 vs 2 vs 1) and the 128-qubit cap differ. SWAP is
   **free everywhere** (never in `num_toffoli_like`).

6. **Conditional variants do NOT change the base price** — `CCX` and `CCX_IF` both sit in
   `num_toffoli_like` at weight 1 `[FAKT op_stats L118–122]`; the `_IF`/condition-stack only scales
   the *executed* count by the condition's firing probability `[FAKT sim.h L315–319, L507–509]`.
   So conditionals are strictly ≤ the unconditional price, never more.

7. **ε in invsqrt is dynamic, not a constant.** `ε = π·min_margin·2⁻⁶⁴/n_rot`
   `[FAKT invsqrt L320]` depends on the leftover phase tolerance after simulation error. A circuit
   with more phase margin gets larger ε ⇒ cheaper rotation synthesis. This couples rotation cost to
   accuracy headroom — worth exploiting (leave margin where it is cheap).

### Single biggest "free resource" per benchmark
- **(I) invsqrt:** conditional Toffolis (`CCX/CCZ/CSWAP … if b` under `PUSH_CONDITION`), powered by
  free HMR/R to mint condition bits — drives a priced Toffoli's average cost toward its branch
  probability. Secondary: free Cliffords (CX/CZ/SWAP) to cut T-gate count in rotation synthesis.
- **(II) dqi:** same conditional-Toffoli lever, but the `Q²` penalty makes free-prep qubits 2×
  costly — prefer conditionals that reuse existing qubits over new ones.
- **(III) dfthcsos:** same lever inside ANGLE_k, bounded by the 128-qubit cap; the heuristic
  state-prep/Givens cost is fixed, so only the ANGLE_k Toffolis are reducible.
