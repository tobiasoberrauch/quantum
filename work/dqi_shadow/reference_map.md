# Reference Decoder Structure Map — GF(2¹²) Arithmetic Call Sites

Source: `data/verifiers/dqi/dqi_reference_circuit.py` (647 lines)
Circuit: `ProosAndZalkaDecoder.build_syndrome_decoding_mbuc()`
Parameters: m=4095, n=70, degree=12, n_iters=222, t=35, block_length=4095

## Critical Insight: Toffoli Cost Classification

In characteristic-2 fields, **addition is XOR** and **multiplication by a constant
is a linear (CNOT-only) transformation**. Therefore:

| kickmix sub | Toffoli cost | Tower-field port needed? |
|---|---|---|
| `gf2_iadd` | **0** (XOR) | No — already free |
| `gf2_imul` (by constant) | **0** (linear) | No — already free |
| `gf2_idiv` (by constant) | **0** (linear) | No — already free |
| `ixor_gf2_mul` (var × var) | **>0** (quadratic) | **YES** |
| `init/del_gf2_div_with_scaffold` (var ÷ var) | **>0** | **YES** |
| `init/del_gf2_inverse_with_scaffold` (var⁻¹) | **>0** | **YES** |
| `gf2_phase_by_product` (phase from var×var) | **>0** | **YES** |

Only the **non-linear** (bilinear/quadratic) sites benefit from tower-field arithmetic.

---

## Complete Call-Site Inventory

### Group A: Variable×Variable Multiplication (`ixor_gf2_mul`)

| # | Line | Code | Stage | Calls in circuit | PORT? |
|---|---:|---|---|---:|:---:|
| A1 | 351 | `builder.ixor_gf2_mul(q_i, reg_a[i], target=reg_b[i], field=gf, control=mul)` | Reverse EEA (`is_adjoint=True`) | ~15,762 | ✅ |
| A2 | 362 | `builder.ixor_gf2_mul(q_i, reg_a[i], target=reg_b[i], field=gf, control=mul)` | Forward EEA (`is_adjoint=False`) | ~15,762 | ✅ |

**Total: ~31,524 calls.** Highest-frequency non-linear site.
Context: inside `_multiply_and_add_or_sub` → `sweep_positions()`, one call per
polynomial coefficient position where `multiplies=True` (i.e., `i < lim_a or i >= 2`).
Controlled by `mul` qubit (unary-iteration-derived threshold flag).

### Group B: Variable Division (`init/del_gf2_div_with_scaffold`)

| # | Line | Code | Stage | Calls | PORT? |
|---|---:|---|---|---:|:---:|
| B1 | 302 | `builder.init_gf2_div_with_scaffold(reg_b[index], reg_a[index], field=gf)` | Fwd+Rev EEA | 888 | ✅ |
| B2 | 305 | `builder.del_gf2_div_with_scaffold(reg_b[index], reg_a[index], target=ratio, scaffold=scaffold, field=gf)` | Fwd+Rev EEA | 888 | ✅ |

**Total: 888 init + 888 del = 1,776 calls.**
Context: inside `_multiply_and_add_or_sub` → `accumulate_quotient()`, called twice
per EEA iteration (leading coefficient + trailing coefficient) × 222 iters × 2 (fwd+rev).
Computes `ratio = reg_b[index] / reg_a[index]` (leading-coefficient ratio for EEA step).

### Group C: Variable Inverse (`init/del_gf2_inverse_with_scaffold`)

| # | Line | Code | Stage | Calls | PORT? |
|---|---:|---|---|---:|:---:|
| C1 | 579 | `builder.init_gf2_inverse_with_scaffold(sigma_prime, target=sigma_prime_inv, field=gf)` | Chien/Forney | 4,095 | ✅ |
| C2 | 587 | `builder.del_gf2_inverse_with_scaffold(sigma_prime, target=sigma_prime_inv, scaffold=inverse_chain, field=gf)` | Chien/Forney | 4,095 | ✅ |

**Total: 4,095 init + 4,095 del = 8,190 calls.**
Context: inside `_chien_search_and_forney_mbuc()`, once per codeword position j.
Computes `sigma_prime_inv = 1/sigma_prime` for Forney's formula.

### Group D: Phase-by-Product (`gf2_phase_by_product`)

| # | Line | Code | Stage | Calls | PORT? |
|---|---:|---|---|---:|:---:|
| D1 | 583 | `builder.gf2_phase_by_product(located, sigma_prime_inv, mask=error_mbuc[j], field=gf)` | Chien/Forney | 4,095 | ✅ |

**Total: 4,095 calls.**
Context: inside `_chien_search_and_forney_mbuc()`, applies the MBUC phase
`(-1)^{popcount(located · sigma_prime_inv · error_mbuc[j])}` per position.

### Group E: Constant Multiplication (`gf2_imul`) — NO PORT NEEDED

| # | Line | Code | Stage | Calls | PORT? |
|---|---:|---|---|---:|:---:|
| E1 | 599 | `builder.gf2_imul(step, target=reg_b[k], field=gf)` | Chien/Forney | ~282,486 | ❌ (0 T) |

**Total: ~282,486 calls but ZERO Toffolis** (multiplication by a field constant
is a fixed linear map = CNOT network only).

### Group F: Constant Division (`gf2_idiv`) — NO PORT NEEDED

| # | Line | Code | Stage | Calls | PORT? |
|---|---:|---|---|---:|:---:|
| F1 | 603 | `builder.gf2_idiv(gf.pow(step, num_positions-1), target=reg_b[k], field=gf)` | Chien/Forney (end) | 69 | ❌ (0 T) |

**Total: 69 calls, ZERO Toffolis.** Undoes accumulated constant multiplications.

### Group G: Field Addition (`gf2_iadd`) — NO PORT NEEDED

| # | Line | Code | Stage | Calls | PORT? |
|---|---:|---|---|---:|:---:|
| G1 | 119 | `builder.gf2_iadd(n, target=n_A)` | Init | 1 | ❌ (0 T) |
| G2 | 120 | `builder.gf2_iadd(n+1, target=n_B)` | Init | 1 | ❌ (0 T) |
| G3 | 304 | `builder.gf2_iadd(ratio, target=q_i, field=gf, control=control)` | Fwd+Rev EEA | 888 | ❌ (0 T) |
| G4 | 133 | `builder.gf2_iadd(n+1, target=n_B)` | Cleanup | 1 | ❌ (0 T) |
| G5 | 134 | `builder.gf2_iadd(n, target=n_A)` | Cleanup | 1 | ❌ (0 T) |

**Total: 892 calls, ZERO Toffolis** (GF(2^m) addition = bitwise XOR).

---

## Summary by Stage

| Stage | Non-linear sites (PORT) | Linear sites (free) |
|---|---|---|
| **Forward EEA** (222 iters) | A2 (~15,762 mul), B1+B2 (444 div) | G3 (444 iadd) |
| **Chien/Forney MBUC** (4095 positions) | C1+C2 (8,190 inv), D1 (4,095 phase) | E1 (~282K imul), F1 (69 idiv) |
| **Reverse EEA** (222 iters) | A1 (~15,762 mul), B1+B2 (444 div) | G3 (444 iadd) |
| **Init/Cleanup** | — | G1,G2,G4,G5 (4 iadd) |

## Exact Set to Replace with Tower-Field Equivalents

**Priority order (by Toffoli impact):**

1. **`ixor_gf2_mul`** (lines 351, 362) — ~31,524 controlled variable×variable muls
   - Current cost: kickmix direct GF(2¹²) mul ≈ 1000+ T each (estimate)
   - Tower target: 105 T each (from division.py schedule)
   - **Potential saving: ~30M Toffolis** (if current is ~1000T)

2. **`init/del_gf2_inverse_with_scaffold`** (lines 579, 587) — 8,190 variable inverses
   - Current cost: kickmix direct GF(2¹²) inverse ≈ 2000+ T each (estimate)
   - Tower target: ~321 T each (from division.py `divide_via_norm`)
   - **Potential saving: ~14M Toffolis**

3. **`init/del_gf2_div_with_scaffold`** (lines 302, 305) — 1,776 variable divisions
   - Current cost: kickmix direct GF(2¹²) div ≈ 3000+ T each (estimate)
   - Tower target: ~321 T each
   - **Potential saving: ~4M Toffolis**

4. **`gf2_phase_by_product`** (line 583) — 4,095 phase-by-product ops
   - Current cost: kickmix direct ≈ 500+ T each (estimate)
   - Tower target: ~50 T each (phase-only, no data output)
   - **Potential saving: ~2M Toffolis**

**Grand potential: ~50M Toffolis saved** (vs current static 5.7M — wait, that's
impossible. The current circuit has only 5,725,461 static Toffolis total.)

Correction: the per-call costs above must be much lower than my estimates. The
total static T is 5.7M across ALL operations. With ~44K non-linear calls, the
average non-linear op costs ~130 T. The tower-field advantage is therefore
modest in absolute terms for this circuit — the big win is in the private builder
which has far more arithmetic (extract/synthesis/convert stages).

## Non-Arithmetic Kickmix Subs Used (for completeness)

These are control-flow / data-movement primitives, NOT field arithmetic:
- `unary_iteration` — pebble-based iteration cursor (lines 318–321, 399–401)
- `cswap` — Fredkin gate for polynomial coefficient swaps (lines 354, 358, 427, 478)
- `flip_if_equal` / `flip_if_less_than` — comparison flags (multiple sites)
- `iadd` / `isub` — integer add/sub on degree registers (multiple sites)
- `left_rotate` / `right_rotate` — bit rotation for polynomial shifts (lines 155, 161, 516–520)
- `bit_store` — classical bit initialization (line 573)
- `push_condition` / `pop_condition` — conditional stack for MBUC (lines 574, 594)
- `init_and` / `del_and` — AND-gate synthesis for control logic (multiple sites)
- `hmr` — Hadamard-Measure-Restore (not in reference, but in division.py)
