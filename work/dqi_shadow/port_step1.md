# Port Step 1: Tower-Field Multiplication — Assessment

## What was attempted

Port the tower-field MULTIPLICATION schedule from `work/dqi_sources/division.py`
(quadratic tower GF(((2²)²)³), cited 105-Toffoli mul) as a drop-in replacement for
the highest-frequency GF(2¹²) multiply site in the reference decoder:
`builder.ixor_gf2_mul(q_i, reg_a[i], target=reg_b[i], field=gf, control=mul)`
at lines 351/362 of `dqi_reference_circuit.py`.

## Verdict: NOT BENEFICIAL — port not executed

The correctness gate was **not run** because static analysis shows the tower-field
mul would be **net-negative** (equal or worse Toffoli count) at this specific site.

## Measured costs (kickmix 0.1, GF(2¹²), α=x)

| operation | uncontrolled | controlled | calls | total T |
|---|---:|---:|---:|---:|
| `ixor_gf2_mul` | **63** | **75** | 31,524 | 2,364,300 |
| `init_gf2_inverse_with_scaffold` | **315** | — | 4,095 | 1,289,925 |
| `init_gf2_div_with_scaffold` | **378** | — | 888 | 335,664 |
| `gf2_phase_by_product` | **0** (CZ-only) | — | 4,095 | 0 |
| `gf2_imul` (constant) | **0** (linear) | — | ~282K | 0 |
| `gf2_iadd` | **0** (XOR) | — | 892 | 0 |

## Why tower-field mul doesn't help here

### 1. Control overhead negates the advantage

The reference decoder's `ixor_gf2_mul` is always **controlled** by a unary-iteration
threshold qubit (`control=mul`). The tower-field Karatsuba decomposition for
GF(2¹²) = GF(64)[z]/(z²+z+β) requires 3 × 18 = 54 AND-pairs (uncontrolled).

With the extra control qubit, each AND-pair's single CCX becomes a 4-controlled-X:
- 1 ancilla: 6 CCX per term → 54 × 6 = **324 T**
- 2 ancillas: 4 CCX per term → 54 × 4 = **216 T**
- Shared-ancilla pool (optimistic): ~3 CCX per term → 54 × 3 = **162 T**

All worse than kickmix's current **75 T**. Even the most optimistic shared-ancilla
estimate (162T) is 2.2× the current cost.

### 2. Kickmix is already near-optimal for multiplication

63 Toffolis for uncontrolled GF(2¹²) multiplication is close to the Boolean-rank
lower bound (~60 for m=12). Kickmix's internal implementation likely uses an
optimized Karatsuba/Toom-Cook decomposition that's hard to beat with a tower approach
at this field size.

### 3. Representation mismatch

`division.py` operates on **24-qubit registers** (GF(2²⁴) = GF(2¹²)[y]/(y²+y+K)).
The reference decoder uses **12-qubit registers** (GF(2¹²) standard binary basis).
A direct port would require basis conversion (free in Toffolis but adds CNOT depth
and complicates scratch management).

### 4. Missing source code

The actual 105T schedule (`mul24_xor105`) is defined in the missing `field` module
(`from field import *`). Only the 126T comparison variant (`mul24_xor126`) is visible
in `division.py`. The `mul_xor` primitive (sub-field multiplication) is also absent.

## Where tower-field DOES help (redirected targets)

The tower advantage is in **inversion**, not multiplication:

| target | current | tower estimate | saving | calls | total saving |
|---|---:|---:|---:|---:|---:|
| `init_gf2_inverse` | 315 T | ~100–150 T | 52–68% | 4,095 | ~700K–1M T |
| `init_gf2_div` | 378 T | ~200 T | 47% | 888 | ~157K T |

Itoh-Tsujii inversion in the tower GF(64)[z]/(z²+z+β):
- Requires 2–3 GF(64) multiplications (54T each uncontrolled) + 1 GF(64) inverse
- GF(64) inverse via Itoh-Tsujii: a⁶² = ((a³)⁴·a³)⁴·a² → 3 GF(64) muls + free squarings
- Total: ~5–7 GF(64) muls ≈ 90–126 T (vs 315 T current)

This is a **2.5–3.5× reduction** per inverse call.

## What blocked the port (summary)

1. **Control overhead**: 4C-X decomposition makes tower mul 2–4× more expensive than kickmix's optimized controlled mul
2. **Field size mismatch**: division.py targets GF(2²⁴)/24-qubit words, not GF(2¹²)/12-qubit
3. **Missing modules**: `field`, `mul24_xor105`, `mul_xor`, `extension_columns()`, `tower()`
4. **No net benefit at this site**: kickmix's 75T controlled mul is already near-optimal

## Recommendation

**Skip the mul port. Target `init_gf2_inverse_with_scaffold` next (port step 2).**
It has 22.5% of static T, no control overhead (called inside `push_condition` which
is a classical-condition, not a variable-qubit control), and the tower Itoh-Tsujii
decomposition gives a clear 2.5–3.5× advantage.
