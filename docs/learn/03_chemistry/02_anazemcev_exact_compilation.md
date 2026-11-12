# Quantum Circuits | Source & Exact Compilation

> **Lernziel:** Wie man die DF-THC-Angle-Lookups komplett aus lesbarem Quellcode baut — signed Givens-Gauge (bit9 = bit8), four-address Difference-Banks und five-scratch Pebbling unter der 128Q-Limitierung, plus der numerische Faktor-Gauge (orthogonale Cayley-Schritte).
> **Dauer:** ~35 Minuten lesen
> **Quelle:** Artem1410 (anazemcev) · 29 votes
> **Technik:** Word Table / Loaders (four-address banks, signed gauge, pebbling) + numerischer Faktor-Gauge
> **Level:** Fortgeschritten

---

This notebook builds the complete submission from readable code and a small public numerical dataset. V4 combines the **signed-Givens four-address lookup** and **curvature checkpoint** published by Kozykorpesh with our full-domain arithmetic compiler, certified rotation calibration and numerical factor gauge. The source decoder includes Dmitrii Gluzdov's V6 memory schedule and Kozykorpesh's exact symbolic lowering, building on Gu et al.

The changes address three different resource objectives:

| Component | Priced resource | This release |
|---|---|---|
| Inverse square root | Qubits times Toffoli-equivalent cost | 90Q schedule, five exact gate replacements, calibrated rotations |
| DQI | Repetition penalty times qubits squared times mean Toffolis | 1789Q source-built decoder and conservative symbolic lowering |
| Chemistry | Effective normalization times total Toffolis times total qubits | Signed angle gauge, four-address banks and five-scratch pebbling |

Every default Run All executes all three **unchanged official full verifiers**. Integer identities, phase certificates and physical checks have different scopes; none substitutes for the final checks.

The comparison snapshot is **24 October 2026**: Kozykorpesh V3 scored **6.68108**, and Mizero's new calibration notebook scored **6.37294**. Our previous V3 produced a full-verifier projection of **6.280714**, without a competition submission. The new result below is also labelled as a projection until its exact notebook version is submitted. The native badge may initially show this notebook's original V1 score **5.67004**.

All inputs are public. No submitted circuit archive or large Toolbox binary is downloaded. The development salt is fixed, and circuit hashes or salts are never searched for favorable samples.

## Reproducible inputs

The numerical input is [`femoco_public_words.npz`, public dataset V2](https://www.kaggle.com/datasets/dmitriigluzdov/vqcc-femoco-public-factorization/versions/2), released under Apache 2.0. The 1,350,093-byte file contains 3,976 rows of 75 ten-bit angle words, weights `W[65,60,30]`, and identity offsets `H2_I[65,30]`. Its exact SHA-256 and array shapes are checked below. The competition Input supplies the fixed Hamiltonian shifts and official circuit/verifier libraries.

No precompiled decoder or previous submission archive is needed. The decoder is regenerated for the competition's field polynomial, and the chemistry vectors are reconstructed from the checked angle words. All large circuit files are produced inside this run.

> **Code (DE):** Prüft den öffentlichen numerischen Input (femoco_public_words.npz): SHA-256 + Array-Formen (3976×75 Words, W[65,60,30], H2_I[65,30]).

```python

# notebook: hide_input
paths = list(INPUT.rglob('femoco_public_words.npz')) if INPUT.exists() else []
if not paths:
    local_input = Path(os.environ.get('QCC_PUBLIC_WORDS', str(PROJECT_ROOT / 'research/dmitrii_source_20261023/public_data/femoco_public_words.npz')))
    paths = [local_input] if local_input.exists() else []
if len(paths) != 1:
    raise FileNotFoundError('Attach the public FeMoCo factorization dataset listed in Input.')
PUBLIC_WORDS = paths[0]
assert digest(PUBLIC_WORDS) == '9afd0ca5e90dd1740fe713e4ac1c26736184ea9bc4d4b57a6eeefafd608ee193'
with np.load(PUBLIC_WORDS, allow_pickle=False) as data:
    assert data['words'].shape == (3976, 75) and data['W'].shape == (65, 60, 30)
    assert data['H2_I'].shape == (65, 30)
save_json(REPORTS / 'public_input.json', {'source': 'dmitriigluzdov/vqcc-femoco-public-factorization',
    'file': PUBLIC_WORDS.name, 'sha256': digest(PUBLIC_WORDS), 'bytes': PUBLIC_WORDS.stat().st_size})
print('Checked public input: 3,976 addresses, 75 angles, physical weights and offsets.')

```

## 1. Arithmetic: erase, reuse, and certify

The oracle applies $e^{2\pi i/\sqrt{x}}$ while restoring its 22-bit input. We retain the explicit calibrated 256-row coefficient table credited to Kozykorpesh, and the Sumit/Rudra/Alex arithmetic lineage.

Kozykorpesh's new schedule measures two Gray-coded curvature bits after their last forward use. Their wires can serve as carry workspace during the outer polynomial calculation. Small Boolean circuits reconstruct the bits for reversal; the measurement phases are repaired together at the end. The normalized input's known top bit also supplies clean workspace. These are reversible lifetime changes, rather than a new polynomial fit.

Our exact-domain compiler evaluates reachable Boolean functions on every allowed input, $1\leq x\leq3,133,452$. It accepts an identity only after full truth-vector comparison. Five Clifford replacements reduce the structural schedule from 1454 to 1449 static Toffolis while preserving instruction order and measurement cleanup.

Following Mizero and lightningv08, angle calibration adjusts the phase linearly through each rotation's activation bit. This release applies fixed integer corrections, bound to the source and output circuit hashes. A fresh exhaustive scan checks the rewritten phase and two reproducible measurement traces. It removes one synthesized rotation, leaving **44**. The optional fitter remains in the source; the default build applies the selected corrections deterministically.

The complete 200,540,928-shot official check below separately checks phase, input restoration and scratch cleanup. Resource counts and the final cost come from that check.

> **Code (DE):** [invsqrt] signed_digit_invsqrt_v3.py — Hauptmodul des exakten invsqrt-Compilers (916 Zeilen): signed-digit Horner, 90Q-Schedule, fünf exakte Clifford-Ersätze.

```python

%%writefile src/signed_digit_invsqrt_v3.py
# SPDX-License-Identifier: Apache-2.0
# New derivative-split integration; original upstream notices retained below.
# Sumit Chongder: centered signed-digit generator and integer pipeline,361357149.
# Rudra Bhaskar: derivative split, top-carry reuse, static-high checkpoint,361445283.
# https://www.kaggle.com/code/rudrabhaskar/highest-public-score-direct-polynomial-phasing?scriptVersionId=361445283
# Alex Chilton: shared prefix and empty-target temporary-AND shifts,361472684.
# Kirill Tymchishin: exact Rudra/Alex integration used as the95Q source baseline,361491814.
# https://www.kaggle.com/code/kirilltym/quantum-circuits-qrom-tower42?scriptVersionId=361491814
# Kozykorpesh: explicit8,19,27,1 coefficient model,datasetVersionId21136269.
# Our changes: generic exact coefficient widths/left shifts, normalized-input
# borrowing on this derivative schedule, and the proven original-input rewrite.
# The derivative split and its precision calibrations are credited upstream.

# SPDX-License-Identifier: Apache-2.0
# Arithmetic research candidate. Retained upstream attribution:
# Sumit Chongder: readable centered signed-digit generator and integer pipeline.
# https://www.kaggle.com/code/sumitchongder/notebook2f196e646b?scriptVersionId=361357149
# anazemcev / Artem1410: early high-word phase, folded carry and normalized-input borrowing.
# https://www.kaggle.com/code/anazemcev/quantum-circuits-signed-digit-memory?scriptVersionId=361422248
# Kozykorpesh: exact reachable-domain calibration, Cfg(8,19,27,1), explicit table.
# https://www.kaggle.com/code/kozykappa/quantum-ai-compact-arithmetic-banked-qrom?scriptVersionId=361456406
# Quantum Circuit Toolbox datasetVersionId 21136269, code/domain_tables.py and coefficients.json.
# Alex Chilton: shared prefix flags and temporary-AND moves into zero destinations.
# https://www.kaggle.com/code/alexchilton/where-the-toffolis-go-anatomy-a-cheaper-invsqrt?scriptVersionId=361472684


# [DE] … (Modul gesamt 916 Zeilen; hier nur der Kopf — vollständiger Quelltext im Original-Notebook / Dataset.)

```

> **Code (DE):** [invsqrt] portable_exact_domain.py — exakte Domain-Compiler-Primitiven (Boolean-Funktionen über alle erlaubten Inputs 1..3.133.452).

```python

%%writefile src/portable_exact_domain.py
"""Portable exact-domain inverse-square-root Clifford compiler.

Requires the credited signed_digit_invsqrt_v3 module on sys.path, NumPy and
kickmix. The default entry point regenerates from readable source and explicit
coefficient data; it has no filesystem layout, fixture or network dependency.
Full truth-vector equality certifies every selected replacement over every
x=1..3,133,452. Classical branches join exact equal functions or unknown.
"""
from __future__ import annotations
import os
os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
from collections import Counter
import json
import re
import numpy as np
import kickmix as km

MAX_X = 3_133_452

class Known:
    """Immutable truth vector. Samples only reject matches; equality is exact."""
    __slots__ = ('v', 'signature')
    sample = None



# [DE] … (Modul gesamt 292 Zeilen; hier nur der Kopf — vollständiger Quelltext im Original-Notebook / Dataset.)

```

> **Code (DE):** [invsqrt] scheduled_arithmetic90.py — die 90-Qubit-Schedule für die Arithmetik.

```python

%%writefile src/scheduled_arithmetic90.py
# SPDX-License-Identifier: Apache-2.0
# Kozykorpesh public V3/run361677445, https://www.kaggle.com/code/kozykappa/quantum-ai-lb-score-6-68108?scriptVersionId=361677445
# Source-only adaptation: explicit coefficients supplied by caller; no Toolbox or binary input.
# Original notices and credited Sumit/Rudra/Alex/Kirill/Artem lineage retained below.
# SPDX-License-Identifier: Apache-2.0
# Retained source credits: Sumit Chongder (signed digits/Gidney arithmetic),
# Rudra Bhaskar (derivative split), Alex Chilton (prefix/AND shifts),
# Kirill Tymchishin (integration), Kozykorpesh (calibrated coefficients),
# anazemcev / Artem1410 (memory schedule and input-domain borrowing).
# This module retains the required arithmetic from the supplied 5.77242 notebook.
import math
from fractions import Fraction
import numpy as np
import kickmix as km
W=22; MB=21; DB=14; NSEG=128; MAX_X=3133452
NSTAGES=[(4,16),(3,8),(2,4),(1,2),(0,1)]


class Cfg:
    def __init__(self, f2, f1, fyr, gy, drop2=()):
        self.f2, self.f1, self.fyr, self.gy = f2, f1, fyr, gy
        self.fy = fyr + gy
        self.w2 = f2 - 1
        self.sh2 = [f2 + 22 - i - f1 for i in range(DB)]


# [DE] … (Modul gesamt 282 Zeilen; hier nur der Kopf — vollständiger Quelltext im Original-Notebook / Dataset.)

```

> **Code (DE):** [invsqrt] schedule_support90.py — Support-Helfer der Schedule.

```python

%%writefile src/schedule_support90.py
# SPDX-License-Identifier: Apache-2.0
# Kozykorpesh public V3/run361677445, https://www.kaggle.com/code/kozykappa/quantum-ai-lb-score-6-68108?scriptVersionId=361677445
# Source-only adaptation: explicit coefficients supplied by caller; no Toolbox or binary input.
# Original notices and credited Sumit/Rudra/Alex/Kirill/Artem lineage retained below.
# Optimized shift adapted from Dmitrii Gluzdov V6/run361592338; original arithmetic credits retained.
import numpy as np

def optimized_shift(b,flags,word,L,inverse,prune=True):
 stages=[(1,1),(2,2),(3,4),(4,8)];occ=[];n=L
 for k,d in stages:
  occ.append(min(n,L+2) if prune and k==4 else n);n=min(n+d,len(word))
 seq=list(enumerate(stages));seq=seq[::-1] if inverse else seq
 for j,(k,d) in seq:
  indices=range(occ[j]) if inverse else reversed(range(occ[j]))
  for i in indices:
   if i+d<len(word):
    zero_boundary = i+d >= L+sum(amount for _,amount in stages[:j])
    if zero_boundary:
     if inverse:b.cx(word[i+d],word[i]);b.del_and(flags[k],word[i],word[i+d])
     else:b.init_and(flags[k],word[i],word[i+d]);b.cx(word[i+d],word[i])
    else:b.cswap(flags[k],word[i],word[i+d])


def mobius_transform(table):
    """Packed-output Boolean truth table <-> ANF coefficient table over GF(2)."""
    result = list(map(int, table))
    if not result or len(result) & (len(result) - 1):
        raise ValueError("truth-table length must be a power of two")
    n = (len(result) - 1).bit_length()
    for bit in range(n):
        step = 1 << bit
        for start in range(0, len(result), 2 * step):
            for offset in range(step):
                result[start + step + offset] ^= result[start + offset]
    return result

```

> **Code (DE):** [invsqrt] fusion_schedule90.py — Fusion der Schedule-Stufen.

```python

%%writefile src/fusion_schedule90.py
# SPDX-License-Identifier: Apache-2.0
# Kozykorpesh public V3/run361677445, https://www.kaggle.com/code/kozykappa/quantum-ai-lb-score-6-68108?scriptVersionId=361677445
# Source-only adaptation: explicit coefficients supplied by caller; no Toolbox or binary input.
# Original notices and credited Sumit/Rudra/Alex/Kirill/Artem lineage retained below.
"""Deferred diagonal feed-forward and live-range reduction for VQCC.
SPDX-License-Identifier: Apache-2.0
Builds on the attributed signed_digit_lab and banked_lab implementations.
"""
from fractions import Fraction
from functools import lru_cache
import numpy as np
import kickmix as km
import scheduled_arithmetic90 as H
from schedule_support90 import optimized_shift
from schedule_support90 import mobius_transform


def xor_many_toffoli(b,a,c,targets):
    targets=list(targets)
    if not targets:return
    first=targets[0]
    for t in targets[1:]:b.cx(first,t)
    b.ccx(a,c,first)
    for t in reversed(targets[1:]):b.cx(first,t)


# [DE] … (Modul gesamt 246 Zeilen; hier nur der Kopf — vollständiger Quelltext im Original-Notebook / Dataset.)

```

> **Code (DE):** [invsqrt] selected_schedule90.py — Auswahl der finalen Schedule.

```python

%%writefile src/selected_schedule90.py
# SPDX-License-Identifier: Apache-2.0
# Kozykorpesh signed-curvature lifetime schedule, V3/run361677445.
# https://www.kaggle.com/code/kozykappa/quantum-ai-lb-score-6-68108?scriptVersionId=361677445
# Caller supplies the explicit public Kozy coefficient table, already retained
# in our attributed signed_digit_invsqrt_v3 module. No Toolbox data is required.
import hashlib
import io
import json
from pathlib import Path
import fusion_schedule90 as F


SELECTED_OPTIONS = dict(delay_high=True, gray_checkpoint=True,
                        curve_count=2, late_coarse=0)


def build_selected(cfg, tables):
    """Return the raw selected public schedule and its provenance report.

    Apply the existing exact-domain compiler and fixed calibrated rotations
    separately; their canonical source/output hashes bind those transformations.
    """
    if (cfg.f2, cfg.f1, cfg.fyr, cfg.gy, sorted(cfg.drop2)) != (8, 19, 27, 1, [5]):
        raise ValueError("This schedule is pinned to the explicit 256-row Kozy model")
    choices_path = Path(__file__).with_name("boolean_choices90.json")
    choices = json.loads(choices_path.read_text())
    circuit, report = F.build(cfg, tables, boolean_choices=choices, **SELECTED_OPTIONS)
    stream = io.BytesIO()
    circuit.to_file(stream, format="kmb")
    report.update(upstream_version=3, upstream_run_id=361677445,
                  method="Gray curvature checkpoint with two early erased bits and deferred joint ANF correction",
                  boolean_choices_sha256=hashlib.sha256(choices_path.read_bytes()).hexdigest(),
                  raw_circuit_sha256=hashlib.sha256(stream.getvalue()).hexdigest(),
                  table_source="Caller-supplied explicit public Kozy integer triples",
                  selected_options=SELECTED_OPTIONS,
                  verification_status="Requires exact-domain compilation, phase certificate and full official check")
    return circuit, report

```

> **Code (DE):** [invsqrt] boolean_choices90.json — die gewählten Boolean-Identitäten (die fünf exakten Gate-Ersätze).

```python

%%writefile src/boolean_choices90.json
{
  "coarse4": {
    "ands": 16,
    "order": [
      4,
      5,
      0,
      7,
      1,
      2,
      6,
      3
    ],
    "polarity": 84
  },
  "coarse5": {
    "ands": 7,
    "order": [
      0,
      1,
      2,
      3,
      4,
      5,
      6,
      7
    ],
    "polarity": 0
  },
  "coarse6": {
    "ands": 11,
    "order": [
      7,
      6,
      5,
      3,
      0,
      1,
      2,
      4
    ],
    "polarity": 144
  },
  "curve4": {
    "ands": 15,
    "order": [
      4,
      5,
      3,
      0,
      2,
      1,
      6,
      7
    ],
    "polarity": 127
  },
  "curve5": {
    "ands": 8,
    "order": [
      0,
      7,
      6,
      5,
      1,
      2,
      3,
      4
    ],
    "polarity": 61
  },
  "curve6": {
    "ands": 9,
    "order": [
      5,
      4,
      7,
      2,
      1,
      0,
      3,
      6
    ],
    "polarity": 249
  }
}

```

> **Code (DE):** [invsqrt] upstream_functions.py — übernommene Upstream-Funktionen (Sumit/Rudra/Alex-Linie).

```python

%%writefile src/upstream_functions.py
# SPDX-License-Identifier: Apache-2.0
# Original algorithm and functions: mizeroluckygall, Kaggle Rotation Calibration V3.
# Pinned primary source: https://www.kaggle.com/code/mizeroluckygall/quantum-circuits-rotation-calibration-39-char?scriptVersionId=361537580
# Upstream credits lightningv08, Quantum Circuits | Memory & Algebra, for exhaustive phase calibration.
# Exact function bodies extracted verbatim; notebook setup, Input scan and packaging omitted.
# Apache-2.0 confirmed from anonymous pinned Kaggle license footer (see upstream_primary_license.json).
from decimal import Decimal, localcontext
from fractions import Fraction
import math
import numpy as np
from scipy.optimize import linprog
UNIT = 2 ** 64

def parse_kmx(text):
    """Return (lines, rotations); rotation = dict(line, qubit, t, cond, counted)."""
    lines = text.splitlines()
    rots = []
    for i, line in enumerate(lines):
        tok = line.split('#')[0].split()
        if not tok or tok[0] != 'Z_POW':
            continue
        cond = tok[tok.index('if') + 1] if 'if' in tok else None
        t = Fraction(Decimal(tok[2]))
        counted = (t * 4).denominator != 1          # finer than T: a synthesized rotation
        rots.append(dict(line=i, qubit=tok[1], t=t, cond=cond, counted=counted))
    return lines, rots


def instrument(lines, rots, first_record_qubit):
    """Copy of the circuit where rotation j becomes CX qubit -> record_j."""
    out = list(lines)
    for j, r in enumerate(rots):
        rec = f'q{first_record_qubit + j}'
        out[r['line']] = f"CX {r['qubit']} {rec}" + (f" if {r['cond']}" if r['cond'] else '')
    return '\n'.join(out) + '\n'


def theta_units(t):
    """Z_POW exponent (half turns) -> phase units (2^-64 turn), exact if representable."""
    v = t * (UNIT // 2)
    return int(round(v)), v.denominator == 1


def exponent_text(t):
    """Exact decimal text for a dyadic exponent, in kickmix's no-exponent format."""
    with localcontext() as ctx:
        ctx.prec = 400
        d = Decimal(t.numerator) / Decimal(t.denominator)
    s = format(d, 'f')
    if '.' not in s:
        s += '.0'
    return s


def rewrite(lines, rots, deltas_units, dropped):
    out = list(lines)
    remove = set()
    for j, r in enumerate(rots):
        if j in dropped:
            remove.add(r['line'])
            continue
        if deltas_units.get(j, 0):
            t = r['t'] + Fraction(int(deltas_units[j]), UNIT // 2)
            out[r['line']] = f"Z_POW {r['qubit']} {exponent_text(t)}" + (f" if {r['cond']}" if r['cond'] else '')
    return '\n'.join(l for i, l in enumerate(out) if i not in remove) + '\n'


def fit(err_units, tol_units, bits, free, fixed_shift_units, *, bound_units, scale=2.0 ** 28,
        start=4096, add=400, max_iter=60, verbose=True):
    """Maximise m s.t. |err + shift + B[:,free] d| <= tol - m for every input.

    err_units: int64 signed error of the current circuit; tol_units: uint64;
    bits: (n_inputs, n_rot) uint8; fixed_shift_units: float array added to err
    (the effect of dropping rotations). Returns (deltas, margin_units).
    """
    n = len(err_units)
    e = (err_units.astype(np.float64) + fixed_shift_units) / scale
    tol = tol_units.astype(np.float64) / scale
    Bf = bits[:, free].astype(np.float64)
    k = len(free)
    active = set(np.linspace(0, n - 1, start, dtype=np.int64).tolist())
    active.update(np.argsort(tol - np.abs(e))[:start].tolist())
    for it in range(max_iter):
        ii = np.fromiter(sorted(active), dtype=np.int64)
        A = np.vstack([np.c_[Bf[ii], np.ones(len(ii))], np.c_[-Bf[ii], np.ones(len(ii))]])
        b = np.r_[tol[ii] - e[ii], tol[ii] + e[ii]]
        res = linprog(np.r_[np.zeros(k), -1.0], A_ub=A, b_ub=b,
                      bounds=[(-bound_units / scale, bound_units / scale)] * k + [(None, None)], method='highs')
        if not res.success:
            raise RuntimeError(res.message)
        d, m = res.x[:k], res.x[k]
        corrected = e + Bf @ d
        slack = tol - np.abs(corrected)
        worst = float(slack.min())
        if verbose:
            print(f'    LP iter {it}: rows {len(ii):6d}  lp margin {m*scale:.4g}  true margin {worst*scale:.4g} units', flush=True)
        if worst >= m - 1e-9 * max(1.0, abs(m)):
            break
        active.update(np.argpartition(slack, add)[:add].tolist())
    return np.rint(d * scale).astype(np.int64), worst * scale


def exact_margin(err_units, tol_units, bits, deltas_full_units):
    """Integer check of the final, rounded corrections over every input."""
    shift = bits.astype(np.int64) @ deltas_full_units.astype(np.int64)
    corrected = err_units.astype(np.int64) + shift
    slack = tol_units.astype(np.int64) - np.abs(corrected)
    return int(slack.min()), int(np.argmin(slack))


def collect(km, IV, spec, text, rots, *, batch=16384, seed=20261023, log=print):
    """Simulate every input: true phase error (units) and every rotation's bit."""
    c0 = km.Circuit(text)
    Q = c0.num_qubits
    ci = km.Circuit(instrument(text.splitlines(), rots, Q))
    xr, _ = IV.validate_registers(c0, spec)
    rec = km.array([km.q(Q + j) for j in range(len(rots))])
    xs = np.arange(1, spec.max_x + 1, dtype=np.uint64)
    n = len(xs)
    phase = np.empty(n, dtype=np.uint64)
    bits = np.empty((n, len(rots)), dtype=np.uint8)
    s0 = km.Simulator(batch_size=batch, seed=seed, debug_print=False)
    s1 = km.Simulator(batch_size=batch, seed=seed + 1, debug_print=False)
    for start in range(0, n, batch):
        x = np.resize(xs[start:start + batch], batch)
        take = min(batch, n - start)
        for s, c in ((s0, c0), (s1, ci)):
            s.clear_for_shot(); s.write_across_shots(xr, IV.to_bits(x, spec.width)); s.do(c)
        phase[start:start + take] = [IV.half_turns_to_units(s0.read_shot_phase(j)) for j in range(take)]
        bits[start:start + take] = s1.read_across_shots(rec)[:, :take].T
        if start // batch % 40 == 0:
            log(f'  simulated {start + take:,}/{n:,}')
    target, tol = IV.reference_values(spec, xs)
    err = (phase - np.asarray(target, dtype=np.uint64)).view(np.int64)
    return xs, err, np.asarray(tol, dtype=np.uint64), bits, Q


def search(err, tol, bits, rots, report, rotation_t_count, *, max_drop=8, log=print):
    """Try dropping 0..max_drop smallest rotations; return candidates with cost estimates."""
    counted = [j for j, r in enumerate(rots) if r['counted']]
    weight = {j: abs(float(min(rots[j]['t'] % 2, 2 - rots[j]['t'] % 2))) for j in counted}
    order = sorted(counted, key=lambda j: weight[j])
    Qn, tof, tcount = report['num_qubits'], report['toffoli_count'], report['t_count']
    theta = np.array([theta_units(r['t'])[0] for r in rots], dtype=np.float64)

    def estimate(n_rot, margin_units):
        if margin_units <= 0:
            return float('inf')
        eps = math.pi * (margin_units / UNIT) / n_rot
        return Qn * (tof + (tcount + n_rot * rotation_t_count(eps)) / 4)

    m0, _ = exact_margin(err, tol, bits, np.zeros(len(rots), dtype=np.int64))
    base = estimate(len(counted), m0)
    log(f'baseline: {len(counted)} rotations, margin {m0:.6g} units, estimated cost {base:,.3f} '
        f'(verifier reported {report["score"]:,.3f})')
    rows = [dict(drop=0, dropped=[], deltas=np.zeros(len(rots), dtype=np.int64), margin=m0, estimate=base, fitted=False)]
    for k in range(0, max_drop + 1):
        dropped = order[:k]
        free = [j for j in counted if j not in dropped]
        shift = -(bits[:, dropped].astype(np.float64) @ theta[dropped]) if dropped else np.zeros(len(err))
        bound = max([4 * abs(theta[j]) for j in dropped] + [2.0 ** 36])
        log(f'drop {k}: ' + (', '.join(f'{float(rots[j]["t"]):.3e}' for j in dropped) or 'none'))
        try:
            d_free, _ = fit(err, tol, bits, free, shift, bound_units=bound, verbose=False)
        except RuntimeError as exc:
            log(f'    LP failed: {exc}'); continue
        deltas = np.zeros(len(rots), dtype=np.int64)
        deltas[free] = d_free
        for j in dropped:
            deltas[j] = -int(theta_units(rots[j]['t'])[0])
        m, worst_i = exact_margin(err, tol, bits, deltas)
        est = estimate(len(free), m)
        log(f'    exact margin {m:.6g} units, estimated cost {est:,.3f}')
        rows.append(dict(drop=k, dropped=dropped, deltas=deltas, margin=m, estimate=est, fitted=True))
        if m <= 0:
            break
    return rows

```

> **Code (DE):** [invsqrt] portable_calibration.py — zertifizierte Rotations-Kalibrierung (nach Mizero/lightningv08).

```python

%%writefile src/portable_calibration.py
# SPDX-License-Identifier: Apache-2.0
# Adapted from mizeroluckygall, Quantum Circuits | Rotation Calibration, V3:
# https://www.kaggle.com/code/mizeroluckygall/quantum-circuits-rotation-calibration-39-char?scriptVersionId=361537580
# Upstream credits lightningv08, Quantum Circuits | Memory & Algebra, for
# exhaustive phase calibration. See upstream_functions.py for unchanged bodies.
# Local changes: explicit Circuit/spec API, strict supported-circuit audit,
# chunked LP scans and integer products, canonical hash checks, independent
# measurement replay, and report-only output without verifier/submission calls.
"""Exhaustive rotation calibration for a supported basis-state phase oracle.

``calibrate(circuit, IV, spec, output_path, baseline_report=None)`` accepts the
unchanged official inverse-square-root verifier module IV. It does not search
Inputs, read ZIPs, contact Kaggle, or call IV.verify. Its output requires a full
official verification before use. No verifier salt/hash is optimized.

Only unconditioned, exactly representable Z_POW rotations are calibrated.
Before the final rotation, classical conditions may guard diagonal phases;
arithmetic is deterministic on basis states and HMR resets its target.
After the final rotation the original cleanup may contain conditional arithmetic.
This excludes arbitrary quantum
circuits whose rotation controls can depend on measurement outcomes.
"""
from __future__ import annotations



# [DE] … (Modul gesamt 385 Zeilen; hier nur der Kopf — vollständiger Quelltext im Original-Notebook / Dataset.)

```

> **Code (DE):** [invsqrt] invsqrt_calibration.json — die fixen Integer-Korrekturwerte der Kalibrierung.

```python

%%writefile src/invsqrt_calibration.json
{
  "sourceCircuitSha256": "343ae65e25032fca924c4c3d719478bba9871631ead110bfaa47bc52e01daa76",
  "candidateCircuitSha256": "97f12b109eb17346991ca33e5604963a11eff1b2098586e048d1fd103de55b7c",
  "droppedOriginalRotationIndices": [
    18
  ],
  "deltasPhaseUnits": [
    15503389,
    7204717,
    -18590236,
    14903209,
    -5832939,
    -13433149,
    97059903,
    93233282,
    -28395803,
    -282842922,
    -72641001,
    -1763289056,
    -1814996023,
    130343098,
    -17034870096,
    0,
    0,
    0,
    -134217728,
    8097276,
    1815847,
    4491724,
    -10991042,
    5870512,
    -17519882,
    -4641899,
    10843453,
    -2449327,
    6247377,
    -1806161,
    -5052034,
    23508591,
    -26351233,
    -10145084,
    -14057994,
    -4128602,
    10688249,
    -5051023,
    -37412180,
    729297823,
    -718326109,
    -678507807,
    -5547184257,
    -14622195669,
    -12662101646,
    -68719476736,
    -68719476736,
    -68719476736
  ],
  "phaseUnitsPerTurn": 18446744073709551616,
  "maxX": 3133452,
  "marginUnits": 73326605,
  "officialVerificationRun": false
}

```

> **Code (DE):** [invsqrt] Build-Aufruf: kompiliert den invsqrt-Circuit aus den Modulen oben und speichert den Report.

```python

# notebook: hide_input
import signed_digit_invsqrt_v3 as core
import selected_schedule90
import portable_exact_domain as domain_compiler
import portable_calibration as phase_calibration
cfg,tables,table_origin=core.load_or_build_tables()
integer_certificate=core.exhaustive_certificate(cfg,tables)
assert integer_certificate['pass'] and integer_certificate['tested_inputs']==3133452
save_json(REPORTS/'invsqrt_integer_certificate.json',{**integer_certificate,
    'scope':'Fixed integer model before angle calibration; full quantum verification follows.'})
raw_inverse,schedule_report=selected_schedule90.build_selected(cfg,tables)
assert schedule_report['raw_circuit_sha256']=='5cb5837936858ccd63dd160dd4df4031abad5dbf057ce873434e9708cd337b9e'
structural_inverse,domain_report=domain_compiler.optimize_circuit(raw_inverse)
structural_path=PUBLIC/'inverse_structural.kmb'
structural_inverse.to_file(str(structural_path),format='kmb')
assert digest(structural_path)=='343ae65e25032fca924c4c3d719478bba9871631ead110bfaa47bc52e01daa76'
fixed_deltas=json.loads((SRC/'invsqrt_calibration.json').read_text())
inv_candidate=phase_calibration.apply_fixed_calibration(structural_inverse,fixed_deltas,
    FINAL/'invsqrt.kmb',km=km)
assert digest(FINAL/'invsqrt.kmb')=='97f12b109eb17346991ca33e5604963a11eff1b2098586e048d1fd103de55b7c'
stats=inv_candidate.operation_statistics()
assert (inv_candidate.num_qubits,stats.num_toffoli_like,stats.num_t_like,
        stats.num_z_pow(min_clifford_hierarchy_level=4))==(90,1449,1,44)
inverse_build_report={'selected_sha256':digest(FINAL/'invsqrt.kmb'),
    'source_before_calibration_sha256':digest(structural_path),
    'schedule':schedule_report,'exact_gate_replacements':len(domain_report.replacements),
    'compiler_replacements':domain_report.replacements,'compiler_counts':dict(domain_report.counts),
    'selected_resources':{'qubits':90,'static_toffoli':1449,'rotations':44},
    'full_official_verification':'Required below; this build report does not replace it.'}
save_json(REPORTS/'invsqrt_build.json',inverse_build_report)
display(pd.DataFrame([
    {'Variant':'Kozy checkpoint schedule','Qubits':90,'Static Toffolis':1454,'Rotations':45},
    {'Variant':'Full-domain exact compilation','Qubits':90,'Static Toffolis':1449,'Rotations':45},
    {'Variant':'Certified fixed angle calibration','Qubits':90,'Static Toffolis':1449,'Rotations':44}]))
del raw_inverse,domain_report
gc.collect()

```

> **Code (DE):** [invsqrt] Verifikation/Protokoll des invsqrt-Builds.

```python

# notebook: hide_input
import io
phase_started=time.perf_counter()
fixed_bytes=(SRC/'invsqrt_calibration.json').read_bytes()
fixed_deltas=json.loads(fixed_bytes)
fixed_data_sha=hashlib.sha256(json.dumps(fixed_deltas,sort_keys=True,separators=(',',':')).encode()).hexdigest()
assert fixed_data_sha=='d7c16d21ae8f516b0d4b66e3057802c3e545048a1d3906dc8656e82ca41a8f37'
assert fixed_deltas['sourceCircuitSha256']==digest(PUBLIC/'inverse_structural.kmb')
assert fixed_deltas['candidateCircuitSha256']==digest(FINAL/'invsqrt.kmb')
assert fixed_deltas['phaseUnitsPerTurn']==2**64 and fixed_deltas['maxX']==3133452
stream=io.BytesIO();inv_candidate.to_file(stream,format='kmx')
phase_text=stream.getvalue().decode()
_,rotation_instructions=phase_calibration.parse_kmx(phase_text)
phase_audit=phase_calibration.audit_supported(phase_text,rotation_instructions)
phase_x,error_units,tolerance_units,activation_bits,phase_Q=phase_calibration.collect(
    km,IV,IV.ProblemSpecInvSqrt.for_n_p(10),phase_text,rotation_instructions,
    batch=16384,seed=20261023,replay_measurements=True,log=print)
margin,worst_index=phase_calibration.exact_margin(error_units,tolerance_units,
    activation_bits,np.zeros(len(rotation_instructions),dtype=np.int64))
assert margin==73326605 and int(phase_x[worst_index])==2489983 and len(phase_x)==3133452
rotation_calibration_report={'diagnostic_status':'PASS','full_domain_inputs':len(phase_x),
    'margin_units':margin,'worst_x':int(phase_x[worst_index]),'num_qubits':phase_Q,
    'source_circuit_sha256':fixed_deltas['sourceCircuitSha256'],
    'candidate_circuit_sha256':fixed_deltas['candidateCircuitSha256'],
    'fixed_delta_data_sha256':fixed_data_sha,'fixed_delta_file_sha256':digest(SRC/'invsqrt_calibration.json'),
    'static_toffoli_count':1449,'rotation_count':44,'raw_t_count':1,
    'phase_units_per_turn':2**64,'fixed_measurement_phase_traces_per_input':2,
    'structural_audit':phase_audit,'lp_refit':False,
    'rotation_eps_from_margin':math.pi*margin/2**64/44,
    'official_verifier_run_by_this_diagnostic':False,
    'elapsed_seconds':time.perf_counter()-phase_started}
save_json(REPORTS/'rotation_calibration.json',rotation_calibration_report)
print(f"Fresh all-domain phase certificate PASS: {len(phase_x):,} inputs; margin {margin} integer units.",flush=True)
del phase_x,error_units,tolerance_units,activation_bits,phase_text,rotation_instructions,structural_inverse
gc.collect()

```

## 2. Chemistry: a signed gauge creates cheaper banks

A Givens tree reconstructs each real orbital vector from quantized angles. Kozykorpesh observed that changing each reconstructed vector's overall sign preserves its outer product. Choosing consistent signed rotations makes angle bit9 equal bit8. Our adapter checks this identity and reconstructs **all 3976 vectors**, bounding their component drift up to a row sign. The physical verifier still checks both Hamiltonian error tolerances.

Four neighboring addresses are represented by one base word and three differences. Each difference needs only nine independent bits per angle, because its two high bits agree. Three angles therefore fit in 30 output wires plus 81 difference-bank wires. A depth-first Boolean evaluation uses five scratch wires, selectively recomputing monomials to stay within the **128Q cap**. Measurement-based ANF cleanup restores the bank while preserving dirty output targets.

The resulting 25 circuits each use 128Q and 1129 Toffolis. Together with the unchanged state-preparation and Givens overhead, the model gives **661 total qubits and 65244 Toffolis**. Our existing orthogonal numerical gauge preserves the augmented factor Gram and lowers the effective normalization slightly further. The original shifts and acceptance thresholds are retained.

Both the signed gauge and bank architecture are credited to Kozykorpesh. Our source adapter regenerates them from the small public dataset and requires fresh physical and full circuit verification.

> **Code (DE):** [Chemie] banked_angles_v3.py — QROM-Maschinerie: difference_tables (Basis-Wort + Differenzen), mobius_transform (ANF), del_lookup_anf (messbasierte ANF-Rücksetzung), init_banked_truncated_anf (Bank-Load), build_qroam2. Kern der 'four-address banks'.

```python

%%writefile src/banked_angles_v3.py
"""Truncated ANF bank loading and split ANF erasure for exact ANGLES XOR.

The contiguous prefix of1988 high addresses uses1976 nonlinear monomials
versus1986 unary products. All legal rows are certified unchanged. A precise
polynomial extension defines the other60 rows and is used for cleanup too.

Own follow-up: eleven-bit measurement correction uses 83 Toffoli instead of88,
using a split Boolean algebraic normal form and measurement-erased products.

SPDX-License-Identifier: Apache-2.0

Banked QROM construction adapted from Kozykorpesh / Sumit Chongder:
https://www.kaggle.com/code/kozykappa/quantum-ai-compact-arithmetic-banked-qrom?scriptVersionId=361433617
https://www.kaggle.com/code/sumitchongder/notebook2f196e646b?scriptVersionId=361357149
Read through Kirill Tym's public quantum-circuits-qrom-tower42 v10 source.

Our change: allocate only nonzero difference columns. Optionally conjugate the
target by a reversible CNOT change of basis, reducing the difference bank to
its GF(2) column rank. The same change is applied to BOTH lookup tables. Thus
the input target can be arbitrary: T^-1(T z XOR T f(a)) = z XOR f(a).
No coefficient, angle word, address, or measurement branch is approximated.

Numeric/profile operations work without kickmix. Circuit building/testing
requires the competition's Linux kickmix package.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from math import ceil
from pathlib import Path

import numpy as np


def batch_deltas(words, J=5):
    words = np.asarray(words, dtype=np.int64)
    nv, na = words.shape
    padded = np.zeros((nv, ceil(na / J) * J), dtype=np.int64)
    padded[:, :na] = words
    batches = padded.reshape(nv, -1, J).transpose(1, 0, 2)
    result = batches.copy()
    result[1:] ^= batches[:-1]
    return result


def pack(row, brot):
    return sum(int(value) << (j * brot) for j, value in enumerate(row))


def _change_basis(values, operations):
    result = list(values)
    for source, target in operations:
        result = [value ^ (((value >> source) & 1) << target)
                  for value in result]
    return result


def difference_tables(delta, brot=10, mode="zero"):
    """Return packed d0, compact dd, and exact reversible output transforms."""
    if mode not in {"baseline", "zero", "linear"}:
        raise ValueError("mode must be baseline, zero, or linear")
    delta = np.asarray(delta, dtype=np.int64)
    if delta.ndim != 2 or len(delta) < 4:
        raise ValueError("expected at least four address rows")
    if np.any(delta < 0) or np.any(delta >= (1 << brot)):
        raise ValueError("angle word out of range")
    A, J = delta.shape
    width = J * brot
    d0 = [pack(row, brot) for row in delta[::2]]
    d1 = [pack(delta[2 * h + 1], brot) if 2 * h + 1 < A else value
          for h, value in enumerate(d0)]
    dd = [a ^ b for a, b in zip(d0, d1)]
    paired = delta[::2].copy()
    paired[:len(delta[1::2])] ^= delta[1::2]
    if A & 1:
        paired[-1] = 0
    bit_columns = ((paired[:, :, None] >> np.arange(brot)) & 1).reshape(H := len(d0), width).T
    packed_columns = np.packbits(bit_columns.astype(np.uint8), axis=1, bitorder="little")
    columns = [int.from_bytes(column.tobytes(), "little") for column in packed_columns]
    active = [bit for bit, column in enumerate(columns) if column]
    unique = len(set(columns) - {0})
    basis = {}
    operations = []
    reduced = columns.copy()
    for bit, original in enumerate(columns):
        column = original
        relation = 0
        while column:
            pivot = column.bit_length() - 1
            if pivot not in basis:
                basis[pivot] = (column, relation ^ (1 << bit))
                break
            value, combination = basis[pivot]
            column ^= value
            relation ^= combination
        if not column:
            # Independent coordinates retain their original values. A dependent
            # coordinate is zeroed by XORing only independent coordinates into it.
            # In particular, identical columns need just one CNOT each way.
            operations.extend((source, bit) for source in range(width)
                              if (relation >> source) & 1)
            reduced[bit] = 0
    rank = len(basis)
    if mode == "linear":
        d0 = _change_basis(d0, operations)
        transformed_dd = _change_basis(dd, operations)
        active = [bit for bit, column in enumerate(reduced) if column]
    else:
        transformed_dd = dd
        operations = []
        if mode == "baseline":
            active = list(range(width))
    compact = [sum(((value >> bit) & 1) << target
                   for target, bit in enumerate(active))
               for value in transformed_dd]
    # A complete integer certificate of the table identity for every legal a.
    reconstructed = [sum(((value >> target) & 1) << bit
                         for target, bit in enumerate(active)) for value in compact]
    restored = _change_basis(
        [d0[a // 2] ^ (reconstructed[a // 2] if a & 1 else 0)
         for a in range(A)], reversed(operations))
    assert restored == [pack(row, brot) for row in delta]
    return d0, compact, active, operations, {
        "rows": A, "width": width, "active_columns": sum(bool(c) for c in columns),
        "unique_nonzero_columns": unique, "gf2_rank": rank,
        "bank_width": len(active), "basis_cnot_count": 2 * len(operations),
        "integer_table_certificate": "PASS", "mode": mode,
    }


def mobius_transform(table):
    """Packed-output Boolean truth table <-> ANF coefficient table over GF(2)."""
    result = list(map(int, table))
    if not result or len(result) & (len(result) - 1):
        raise ValueError("truth-table length must be a power of two")
    n = (len(result) - 1).bit_length()
    for bit in range(n):
        step = 1 << bit
        for start in range(0, len(result), 2 * step):
            for offset in range(step):
                result[start + step + offset] ^= result[start + offset]
    return result


def del_lookup_anf(builder, *, table, address, target, low_bits=None):
    """Clear table[address] with exact conditional ANF phase correction.

    `target` must contain the given lookup value and remain allocated. Extra
    scratch is allocated only when the reset target is too narrow. Clean target
    wires are reused internally; all target and extra scratch finish at zero.
    """
    import kickmix as km
    address = list(address)
    target = list(target)
    n = len(address)
    if len(table) != 1 << n:
        raise ValueError("lookup table must cover the complete address space")
    if n < 2:
        raise ValueError("split ANF cleanup expects at least two address bits")
    low_bits = n // 2 if low_bits is None else low_bits
    if not 0 < low_bits < n:
        raise ValueError("both address halves must be nonempty")
    if any(value < 0 or value >= (1 << len(target)) for value in table):
        raise ValueError("lookup value does not fit the target")
    coefficients = mobius_transform(table)
    assert mobius_transform(coefficients) == list(table), "exact ANF identity failed"
    measurements = builder.alloc_bits(len(target))
    builder.hmr(km.array(target), measurements)
    parity = builder.alloc_bits(1)[0]

    low_count = 1 << low_bits
    high_bits = n - low_bits
    retained_masks = [mask for mask in range(1, low_count) if mask.bit_count() > 1]
    scratch_count = len(retained_masks) + high_bits - 1
    extra = builder.alloc_qubits(max(0, scratch_count - len(target)))
    scratch = target + list(extra)
    low = {1 << bit: address[bit] for bit in range(low_bits)}
    for mask, qubit in zip(retained_masks, scratch):
        bit = mask.bit_length() - 1
        parent = mask ^ (1 << bit)
        builder.init_and(low[parent], address[bit], qubit)
        low[mask] = qubit
    carries = scratch[len(retained_masks):scratch_count]

    def correct(high_mask, high_qubit):
        for low_mask in range(low_count):
            coefficient = coefficients[low_mask | (high_mask << low_bits)]
            if not coefficient:
                continue
            builder.bit_store(parity, False)
            while coefficient:
                bit = (coefficient & -coefficient).bit_length() - 1
                builder.cx(measurements[bit], parity)
                coefficient &= coefficient - 1
            if not low_mask and not high_mask:
                builder.neg_if(parity)
                continue
            builder.push_condition(parity)
            if not low_mask:
                builder.z(high_qubit)
            elif not high_mask:
                builder.z(low[low_mask])
            else:
                builder.cz(low[low_mask], high_qubit)
            builder.pop_condition()

    def walk(mask, highest_bit, control):
        correct(mask, control)
        for bit in range(highest_bit + 1, high_bits):
            child_mask = mask | (1 << bit)
            if not mask:
                walk(child_mask, bit, address[low_bits + bit])
            else:
                child = carries[mask.bit_count() - 1]
                builder.init_and(control, address[low_bits + bit], child)
                walk(child_mask, bit, child)
                builder.del_and(control, address[low_bits + bit], child)

    walk(0, -1, None)
    for mask in reversed(retained_masks):
        bit = mask.bit_length() - 1
        parent = mask ^ (1 << bit)
        builder.del_and(low[parent], address[bit], low[mask])
    builder.free(extra)
    return {"address_bits": n, "low_bits": low_bits, "high_bits": high_bits,
            "retained_products": len(retained_masks), "traversal_carries": high_bits - 1,
            "anf_toffoli": (1 << low_bits) - low_bits - 1 + (1 << high_bits) - high_bits - 1,
            "scratch_count": scratch_count, "anf_table_identity": "PASS"}


def init_banked_truncated_anf(builder, *, d0, dd, address, target, bank, scratch):
    """XOR d0[h] into target, dd[h] into bank; return the completed dd table.

    Requires `mobius_transform` in the surrounding module (anf_cleanup.py).
    Legal h ranges from zero through len(d0)-1. `scratch` is clean and remains
    clean. All target bits may start arbitrary; bank initialization is the
    caller's usual clean lookup bank.
    """
    import kickmix as km
    address, target, bank, scratch = map(list, (address, target, bank, scratch))
    H, n, W = len(d0), len(address), len(target)
    if len(dd) != H or H > (1 << n) or H <= (1 << (n - 1)):
        raise ValueError("expected a nonempty prefix using every address bit")
    if len(scratch) < n - 1:
        raise ValueError("need n-1 clean traversal carry wires")
    original = [int(first) | (int(second) << W) for first, second in zip(d0, dd)]
    coefficients = mobius_transform(original + [0] * ((1 << n) - H))
    coefficients[H:] = [0] * ((1 << n) - H)
    completed = mobius_transform(coefficients)
    assert completed[:H] == original, "truncated ANF changed a legal table row"
    assert mobius_transform(completed) == coefficients
    outputs = target + bank

    def load(mask, control):
        value = coefficients[mask]
        targets = [outputs[bit] for bit in range(len(outputs)) if (value >> bit) & 1]
        if targets:
            if control is None:
                builder.x(km.array(targets))
            else:
                builder.cx(control, km.array(targets))

    def walk(mask, highest_bit, control):
        load(mask, control)
        for bit in range(highest_bit + 1, n):
            child_mask = mask | (1 << bit)
            if child_mask >= H:
                continue
            if not mask:
                walk(child_mask, bit, address[bit])
            else:
                child = scratch[mask.bit_count() - 1]
                builder.init_and(control, address[bit], child)
                walk(child_mask, bit, child)
                builder.del_and(control, address[bit], child)

    walk(0, -1, None)
    return [value >> W for value in completed], {
        "legal_high_addresses": H, "address_bits": n,
        "nonlinear_products": H - 1 - n,
        "previous_unary_products": H - 2,
        "exact_legal_table_identity": "PASS",
        "extension_mobius_identity": "PASS",
        "completed_high_addresses": (1 << n) - H,
        "max_required_carries": n - 1,
    }


def build_qroam2(delta, brot=10, *, mode="zero", return_report=False):
    """Exact banked XOR oracle; same public register contract as upstream."""
    import kickmix as km
    delta = np.asarray(delta, dtype=np.int64)
    A, J = delta.shape
    nbits = (A - 1).bit_length()
    H = (A + 1) // 2
    hbits = nbits - 1
    W = J * brot
    d0, dd, active, transforms, report = difference_tables(delta, brot, mode)
    b = km.CircuitBuilder()
    sel = b.create_quantum_register(nbits, "selection")
    words = [b.create_quantum_register(brot, f"word_{j}") for j in range(J)]
    tgt = [q for word in words for q in word]
    for source, target in transforms:
        b.cx(tgt[source], tgt[target])
    B = b.alloc_qubits(len(active))
    hreg = sel[1:nbits]
    anc = b.alloc_qubits(hbits - 1)
    completed_dd, load_report = init_banked_truncated_anf(
        b, d0=d0, dd=dd, address=hreg, target=tgt, bank=B, scratch=anc)
    report["anf_bank_load"] = load_report
    b.free(anc)
    for bank_bit, target in enumerate(active):
        b.ccx(sel[0], B[bank_bit], tgt[target])
    if active:
        table = completed_dd
        report["anf_cleanup"] = del_lookup_anf(b, table=table, address=hreg, target=B)
    b.free(B)
    for source, target in reversed(transforms):
        b.cx(tgt[source], tgt[target])
    circuit = b.finish_circuit()
    report.update(num_qubits=circuit.num_qubits,
                  static_toffoli=int(circuit.operation_statistics().num_toffoli_like))
    return (circuit, report) if return_report else circuit


def profile(words, brot=10, Js=(4, 5, 6, 7)):
    return {str(J): [difference_tables(delta, brot, "linear")[-1]
                    for delta in batch_deltas(words, J)] for J in Js}


def test_random_targets(circuits, deltas, *, brot=10, repeats=8, seed=20261023):
    """Every legal address, random dirty targets, HMR phase and scratch checks.

    This is simulation evidence; the exhaustive integer identity is separately
    certified above. This test is not a proof over all measurement branches.
    The full official verifier remains the acceptance check for the family.
    """
    import kickmix as km
    from dfthcsos.scoreinfra.circuits import register_layout, _check_state
    rng = np.random.default_rng(seed)
    layout = register_layout(circuits)
    A = len(deltas[0])
    addresses = np.tile(np.arange(A, dtype=np.int64), repeats)
    address_bits = ((addresses[None, :] >> np.arange(len(layout.selection))[:, None]) & 1).astype(bool)
    sim = km.Simulator(batch_size=len(addresses), debug_print=False,
                       seed=seed, counting_operations=True)
    sim.use_same_registers_as(circuits[0])
    place_values = np.int64(1) << np.arange(brot)
    toffolis = []
    for k, (circuit, delta) in enumerate(zip(circuits, deltas)):
        sim.clear_for_shot()
        sim.write_across_shots(layout.selection, address_bits)
        dirty = rng.integers(0, 1 << brot, size=(len(addresses), len(layout.words)), dtype=np.int64)
        for j, word in enumerate(layout.words):
            sim.write_across_shots(word, ((dirty[:, j][None, :] >> np.arange(brot)[:, None]) & 1).astype(bool))
        before = sim.operation_statistics().num_toffoli_like
        sim.do(circuit)
        _check_state(sim, circuit, layout, address_bits, f"random-target ANGLE_{k}")
        result = np.stack([place_values @ sim.read_across_shots(word).astype(np.int64)
                           for word in layout.words], axis=1)
        assert np.array_equal(result, dirty ^ delta[addresses]), f"ANGLE_{k} wrong XOR"
        toffolis.append((sim.operation_statistics().num_toffoli_like - before) / len(addresses))
    return {"status": "PASS", "addresses": A, "repeats": repeats,
            "shots_per_circuit": len(addresses), "num_circuits": len(circuits),
            "random_target_xor": "PASS", "unchanged_selection": "PASS",
            "clean_workspace": "PASS", "zero_observed_phase_errors": True,
            "toffoli_per_circuit": toffolis, "toffoli_per_pass": sum(toffolis),
            "full_official_verification": "PENDING", "seed": seed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("words", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--mode", choices=("baseline", "zero", "linear"), default="zero")
    parser.add_argument("--J", type=int, default=5)
    parser.add_argument("--brot", type=int, default=10)
    parser.add_argument("--profile-only", action="store_true")
    parser.add_argument("--repeats", type=int, default=8)
    args = parser.parse_args()
    words = np.loadtxt(args.words, delimiter=",", dtype=np.int64)
    args.output.mkdir(parents=True, exist_ok=True)
    report = {"source_csv": str(args.words), "source_csv_sha256": hashlib.sha256(args.words.read_bytes()).hexdigest(),
              "shape": list(words.shape), "brot": args.brot, "J": args.J, "mode": args.mode,
              "profiles": profile(words, args.brot)}
    if not args.profile_only:
        deltas = batch_deltas(words, args.J)
        circuits, resources = [], []
        for k, delta in enumerate(deltas):
            circuit, resource = build_qroam2(delta, args.brot, mode=args.mode, return_report=True)
            if circuit.num_qubits > 128:
                raise ValueError(f"ANGLE_{k} exceeds the 128-qubit cap")
            path = args.output / f"angle_k_{k}.kmb"
            circuit.to_file(path, format="kmb")
            resource.update(k=k, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size)
            circuits.append(circuit)
            resources.append(resource)
            print(json.dumps(resource), flush=True)
        report["circuits"] = resources
        report["random_target_test"] = test_random_targets(circuits, deltas, brot=args.brot, repeats=args.repeats)
        toffoli = 8794 + 2 * report["random_target_test"]["toffoli_per_pass"]
        report["estimate_using_unchanged_c5_coefficients"] = {
            "full_system_qubits": 631 + args.J * args.brot,
            "full_system_toffoli": toffoli, "lambda_eff": 47.558542335159316,
            "estimated_cost": (631 + args.J * args.brot) * toffoli * 47.558542335159316,
            "label": "RESOURCE ESTIMATE; full official verifier pending"}
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf8")
    print(json.dumps({key: value for key, value in report.items() if key != "profiles" and key != "circuits"}, indent=2), flush=True)


if __name__ == "__main__":
    main()

```

> **Code (DE):** [Chemie] gauge_generator.py — reproduzierbarer exakter DFTHC-Gauge aus dem öffentlichen Input: log_depth_tree_edges (offizieller Givens-Baum), decode_words (Vektoren aus Winkeln), cayley_stage (orthogonale Cayley-Schritte minimieren die spaltenweise L1-Summe bei erhaltener Gram-Matrix). Das ist der 'numerical factor gauge'.

```python

%%writefile src/gauge_generator.py
"""Reproducible exact DFTHC gauge from public numerical input, NumPy only.

SPDX-License-Identifier: Apache-2.0

Input and initial factorization: Dmitrii Gluzdov's public Apache-2.0 dataset
https://www.kaggle.com/datasets/dmitriigluzdov/vqcc-femoco-public-factorization/versions/2
The C30 factor and original sparse-factor work trace to k256.dev and
Kozykorpesh, as credited by the accompanying notebook/source notices.
The log-depth tree and vector decoding follow the organizers' reference.

Own optimization: simultaneous orthogonal Cayley moves reduce the squared
column L1 sum. The augmented [W; H2_I] Gram is preserved; no angle words,
Hamiltonian integrals, symmetry shifts, or acceptance thresholds are changed.
This file imports no research modules or previously saved factorization.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np

PUBLIC_SHA256 = "9afd0ca5e90dd1740fe713e4ac1c26736184ea9bc4d4b57a6eeefafd608ee193"
SHIFTS_SHA256 = "7b7facf63fe35a9d9d3d00787ffdb700c863fa845fe4724d7f7c54778151cd87"
FACTORIZATION_KEYS = ("U", "W", "H2_I", "H1_I", "Hsym_lower", "tree_edges")


def log_depth_tree_edges(n=76):
    """Parent-before-child breadth-first order of the official Givens tree."""
    edges, level, depth = [], [0], 0
    while len(edges) < n-1:
        nxt = []
        for label in level:
            nxt.append(label)
            child = label+(1 << depth)
            if child < n:
                edges.append((label, child))
                nxt.append(child)
        level, depth = nxt, depth+1
    return np.asarray(edges, dtype=np.int64)


def decode_words(words, edges, brot=10):
    """Apply the ordered rotations to e0, matching official vector decoding."""
    angles = np.asarray(words, dtype=np.float64)/(1 << (brot-1))
    vectors = np.zeros((len(words), words.shape[1]+1), np.float64)
    vectors[:, 0] = 1.0
    for j, (parent, child) in enumerate(edges):
        parent_value, child_value = vectors[:, parent].copy(), vectors[:, child].copy()
        theta = np.pi*angles[:, j]
        cosine, sine = np.cos(theta), np.sin(theta)
        vectors[:, parent] = cosine*parent_value-sine*child_value
        vectors[:, child] = sine*parent_value+cosine*child_value
    return vectors


def column_l1_square(a, epsilon=0.0):
    absolute = np.sqrt(a*a+epsilon*epsilon) if epsilon else np.abs(a)
    return np.sum(absolute.sum(axis=1)**2, axis=1)


def cayley_stage(a, iterations, epsilon):
    """Orthogonal right rotations, with separate line searches for each rho."""
    r, _, c = a.shape
    eye = np.broadcast_to(np.eye(c), (r, c, c))
    best, best_loss = a.copy(), column_l1_square(a)
    rates = np.full(r, 0.5)
    history = []
    for iteration in range(iterations):
        absolute = np.sqrt(a*a+epsilon*epsilon)
        gradient = 2*absolute.sum(axis=1)[:, None, :]*a/absolute
        raw = a.swapaxes(1, 2) @ gradient
        skew = 0.5*(raw-raw.swapaxes(1, 2))
        initial = column_l1_square(a, epsilon)
        accepted = np.zeros(r, bool)
        next_a, trial_rates = a.copy(), rates.copy()
        for _ in range(12):
            matrix = skew*(0.5*trial_rates)[:, None, None]
            # For skew K, (I+K)^(-1)(I-K) is orthogonal.
            rotation = np.linalg.solve(eye+matrix, eye-matrix)
            trial = a @ rotation
            good = (column_l1_square(trial, epsilon) < initial-1e-13) & ~accepted
            next_a[good] = trial[good]
            accepted |= good
            trial_rates[~accepted] *= 0.5
            if accepted.all():
                break
        a = next_a
        rates = np.minimum(3.0, np.maximum(1e-5, trial_rates*1.2))
        actual = column_l1_square(a)
        improved = actual < best_loss
        best[improved], best_loss[improved] = a[improved], actual[improved]
        if iteration % 40 == 0:
            history.append({"iteration": iteration, "best_l1_square": float(best_loss.sum())})
    return best, history


def generate(public_npz, fixed_shifts_npz, *, copies=30, iterations=100):
    """Return (factorization, unchanged angle words, algebraic build report).

    Dependencies are NumPy, the checksummed public v2 NPZ, and the official
    fixed shifts NPZ. Fresh official verification is a separate caller step.
    """
    started = time.monotonic()
    source, shifts_source = Path(public_npz), Path(fixed_shifts_npz)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == PUBLIC_SHA256
    assert hashlib.sha256(shifts_source.read_bytes()).hexdigest() == SHIFTS_SHA256
    assert copies == 30 and iterations == 100, "reviewed candidate uses C30 and100 iterations/stage"
    with np.load(source, allow_pickle=False) as archive:
        words = archive["words"].astype(np.int64)
        w, h2 = archive["W"].copy(), archive["H2_I"].copy()
    assert words.shape == (3976, 75) and w.shape == (65, 60, 30) and h2.shape == (65, 30)
    assert np.all((words >= 0) & (words < 1024))
    assert np.isfinite(w).all() and np.isfinite(h2).all()
    original_words = words.copy()
    edges = log_depth_tree_edges()
    u = decode_words(words[76:], edges).reshape(65, 60, 76)
    assert np.max(np.abs(np.linalg.norm(u, axis=-1)-1)) < 1e-12
    a = np.concatenate([w, h2[:, None, :]], axis=1)
    original_gram = a @ a.swapaxes(1, 2)
    baseline = float(column_l1_square(a).sum())
    stages = []
    for epsilon in (0.0005, 0.00005, 0.000005):
        a, history = cayley_stage(a, iterations, epsilon)
        stages.append({"epsilon": epsilon, "history": history,
                       "l1_square": float(column_l1_square(a).sum())})
    final = float(column_l1_square(a).sum())
    drift = float(np.max(np.abs(a @ a.swapaxes(1, 2)-original_gram)))
    assert drift < 1e-8 and final < baseline
    # h1 is unchanged. Retain its original encoded eigenvectors: a redundant
    # eigendecomposition could choose different signs and alter angle words.
    assert np.array_equal(words, original_words), "all3976x75 integer angle words must be unchanged"
    with np.load(shifts_source, allow_pickle=False) as archive:
        fixed = {key: archive[key].copy() for key in ("H1_I", "Hsym_lower")}
    data = {"U": u, "W": a[:, :-1, :], "H2_I": a[:, -1, :],
            "tree_edges": edges, **fixed}
    report = {"public_input_sha256": PUBLIC_SHA256, "fixed_shifts_sha256": SHIFTS_SHA256,
              "R_B_C": [65, 60, 30], "brot": 10, "iterations_per_stage": iterations,
              "baseline_l1_square": baseline, "final_l1_square": final,
              "augmented_gram_max_drift": drift,
              "all_3976x75_angle_words_unchanged": True,
              "angle_words_sha256_int64": hashlib.sha256(words.astype("<i8").tobytes()).hexdigest(),
              "stages": stages, "seconds": time.monotonic()-started,
              "numpy_version": np.__version__,
              "correctness_label": "Algebraic invariants checked; full official verifier not invoked by generate()"}
    return data, words, report


def save_factorization(path, data):
    """Save only the public factorization contract and its organizer tree."""
    np.savez(path, **{key: data[key] for key in FACTORIZATION_KEYS})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("public_npz", type=Path)
    parser.add_argument("fixed_shifts_npz", type=Path)
    parser.add_argument("output_npz", type=Path)
    args = parser.parse_args()
    result, words, report = generate(args.public_npz, args.fixed_shifts_npz)
    args.output_npz.parent.mkdir(parents=True, exist_ok=True)
    save_factorization(args.output_npz, result)
    report["output_npz_sha256"] = hashlib.sha256(args.output_npz.read_bytes()).hexdigest()
    args.output_npz.with_suffix(".build.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)

```

> **Code (DE):** [Chemie] signed_fourbank.py — Signed-Givens four-address QROM: canonicalize (signierter Winkel-Gauge, erzwingt bit9=bit8), pebbled_init (five-scratch pebbling mit selektivem Re-Compute), build (4 Adressen → 1 Basis + 3 Differenzen à 9 Bits). Kern der günstigeren Banks.

```python

%%writefile src/signed_fourbank.py
"""Signed-Givens four-address QROM, adapted from Kozykorpesh V3.

SPDX-License-Identifier: Apache-2.0
Pinned primary source:
https://www.kaggle.com/code/kozykappa/quantum-ai-lb-score-6-68108?scriptVersionId=361677445
The signed-angle gauge, four-address decomposition and selective five-scratch
pebbles originate in that source. The exact ANF eraser is our credited
banked_angles_v3 (Sumit/Kozykorpesh/Kirill/anazemcev lineage).

Our adapter uses the small public words and our existing Gram-gauged factor;
no Toolbox binary, cached QROM output or training checkpoint is required.
The all-row sign certificate bounds the decoded-vector change. Full official
verification is a separate required check for the generated family.
"""
from functools import lru_cache
import numpy as np
import kickmix as km
import banked_angles_v3 as B


def canonicalize(data, angle_words, brot=10):
    """Return signed words/physical factor, preserving each vector up to sign.

    Adapted from Kozykorpesh gauge_qrom.canonicalize. Removing numerical
    zero branches is accepted only if every reconstructed row passes the
    explicit component-wise sign certificate below.
    """
    from dfthcsos.scoreinfra.dfthc_math import reconstruct_u_vectors
    out={key:np.array(value,copy=True) for key,value in data.items()}
    words_in=np.asarray(angle_words,dtype=np.int64)
    if brot!=10 or words_in.ndim!=2:
        raise ValueError('Expected a two-dimensional 10-bit angle table.')
    edges=np.asarray(data['tree_edges'],dtype=np.int64)
    u=reconstruct_u_vectors(words_in/(1<<(brot-1)),edges)
    n=u.shape[1]
    if len(words_in)!=n+int(np.prod(data['U'].shape[:-1])):
        raise ValueError('Angle rows do not match the factor dimensions.')
    assert np.array_equal(u[n:].reshape(data['U'].shape),data['U'])
    a=u.copy();angles=np.empty_like(words_in,dtype=np.float64)
    for j,(p,q) in reversed(list(enumerate(edges))):
        norm=np.hypot(a[:,p],a[:,q])
        sign=np.where(np.abs(a[:,p])<1e-12,np.where(a[:,q]>0,-1,1),np.where(a[:,p]<0,-1,1))
        angles[:,j]=np.where(norm<1e-12,0,np.arctan2(a[:,q]*sign,a[:,p]*sign))
        a[:,p]=np.where(norm<1e-12,0,norm*sign);a[:,q]=0
    words=np.rint(angles*((1<<(brot-1))/np.pi)).astype(np.int64)%(1<<brot)
    assert not np.any(((words>>9)^(words>>8))&1),'Signed-angle identity failed'
    decoded=reconstruct_u_vectors(words/(1<<(brot-1)),edges)
    row_sign=np.where((u*decoded).sum(axis=1)<0,-1,1)
    drift=float(np.max(np.abs(decoded*row_sign[:,None]-u)))
    if drift>1e-11:
        raise ArithmeticError(f'Signed Givens gauge drift {drift}')
    out['U']=decoded[n:].reshape(data['U'].shape)
    out['angle_words']=words
    report={'rows_checked':len(words),'angles_per_row':words.shape[1],
        'max_component_drift_up_to_row_sign':drift,
        'redundant_bit_identity':'bit9 = bit8',
        'W_unchanged':np.array_equal(out['W'],data['W']),
        'H2_I_unchanged':np.array_equal(out['H2_I'],data['H2_I']),
        'H1_I_unchanged':np.array_equal(out['H1_I'],data['H1_I']),
        'Hsym_lower_unchanged':np.array_equal(out['Hsym_lower'],data['Hsym_lower']),
        'source':'Kozykorpesh V3/run361677445, canonicalize adapted to public input',
        'physical_invariance':'Each one-body and factor vector is identical up to a row sign; its outer product is invariant. W and shifts are unchanged.',
        'full_official_verification':'PENDING'}
    return out,report


def xor_and(b,left,right,targets):
    targets=list(targets)
    if not targets:return
    q=targets[0]
    for t in targets[1:]:b.cx(q,t)
    b.ccx(left,right,q)
    for t in reversed(targets[1:]):b.cx(q,t)

def pebbled_init(b,table,address,outputs,scratch):
    address,outputs,scratch=map(list,(address,outputs,scratch))
    H,n=len(table),len(address)
    coefficients=B.mobius_transform(list(table)+[0]*((1<<n)-H))
    coefficients[H:]=[0]*((1<<n)-H)
    completed=B.mobius_transform(coefficients)
    assert completed[:H]==table
    stats={'monomial_ands':0,'recomputed_ands':0,'pebble_sites':0,'direct_leaf_ands':0,'scratch':len(scratch)}
    @lru_cache(None)
    def children(mask,last):return tuple((mask|(1<<j),j) for j in range(last+1,n) if (mask|(1<<j))<H)
    @lru_cache(None)
    def need(mask,last):
        return max([1+need(c,j) for c,j in children(mask,last) if children(c,j)]+[0])
    def targets(mask):
        v=coefficients[mask]
        return [outputs[j] for j in range(len(outputs)) if (v>>j)&1]
    def walk(mask,last,control,path,free):
        erased=[]
        if mask.bit_count()==5 and need(mask,last)>len(free):
            m=need(mask,last)-len(free)
            assert 0<m<=len(path)-1
            erased=path[:m]
            for a,c,t in reversed(erased):b.del_and(a,c,t);free.append(t)
            stats['pebble_sites']+=1
        ts=targets(mask)
        if ts:
            if control is None:b.x(km.array(ts))
            else:b.cx(control,km.array(ts))
        for child,j in children(mask,last):
            if not mask:
                walk(child,j,address[j],path,free)
            elif not children(child,j):
                ts=targets(child)
                if ts:xor_and(b,control,address[j],ts);stats['direct_leaf_ands']+=1
            else:
                assert free,('scratch exhausted',mask,j,len(path))
                t=free.pop();b.init_and(control,address[j],t);stats['monomial_ands']+=1
                walk(child,j,t,path+[(control,address[j],t)],free)
                b.del_and(control,address[j],t);free.append(t)
        for a,c,t in erased:
            free.remove(t);b.init_and(a,c,t);stats['recomputed_ands']+=1
    walk(0,-1,None,[],scratch.copy())
    return completed,stats

def build(delta,brot=10,return_report=False):
    delta=np.asarray(delta,dtype=np.int64);A,J=delta.shape
    assert brot==10 and J==3 and A%4==0
    assert not np.any(((delta>>9)^(delta>>8))&1)
    W=10*J;BW=9*J;H=A//4;n=(A-1).bit_length()
    packed=[B.pack(row,10) for row in delta]
    ds=[[],[],[]];base=[]
    compact=lambda row:sum(((row>>(j*10))&511)<<(j*9) for j in range(J))
    for h in range(H):
        v=packed[4*h:4*h+4];base.append(v[0])
        ds[0].append(compact(v[0]^v[1]));ds[1].append(compact(v[0]^v[2]))
        ds[2].append(compact(v[0]^v[1]^v[2]^v[3]))
    def expand(v):
        return sum((((v>>(9*j))&511)|(((v>>(9*j+8))&1)<<9))<<(10*j) for j in range(J))
    restored=[base[h]^expand((ds[0][h] if a&1 else 0)^(ds[1][h] if a&2 else 0)^(ds[2][h] if (a&3)==3 else 0)) for h in range(H) for a in range(4)]
    assert restored==packed
    values=[base[h]|(ds[0][h]<<W)|(ds[1][h]<<(W+BW))|(ds[2][h]<<(W+2*BW)) for h in range(H)]
    b=km.CircuitBuilder();sel=b.create_quantum_register(n,'selection')
    tgt=[q for j in range(J) for q in b.create_quantum_register(10,f'word_{j}')]
    bank=list(b.alloc_qubits(3*BW));scratch=b.alloc_qubits(5)
    completed,stats=pebbled_init(b,values,sel[2:],tgt+bank,scratch);b.free(scratch)
    both=b.alloc_qubits(1)[0];b.init_and(sel[0],sel[1],both)
    for s,ctl in enumerate((sel[0],sel[1],both)):
        for j in range(J):
            for k in range(9):
                ts=[tgt[j*10+k]]+([tgt[j*10+9]] if k==8 else [])
                xor_and(b,ctl,bank[s*BW+j*9+k],ts)
    b.del_and(sel[0],sel[1],both);b.free(both)
    erase=B.del_lookup_anf(b,table=[v>>W for v in completed],address=sel[2:],target=bank,low_bits=5)
    b.free(km.array(bank));c=b.finish_circuit()
    report={'num_qubits':c.num_qubits,'static_toffoli':int(c.operation_statistics().num_toffoli_like),'table_identity':'PASS','init':stats,'cleanup':erase}
    assert c.num_qubits<=128
    return (c,report) if return_report else c

```

> **Code (DE):** [Chemie] Build: erzeugt den Gauge, kanonisiert die signed words, baut 25 Lookup-Circuits (je 128Q, 1129 Toffolis) und prüft alle Invarianten.

```python

# notebook: hide_input
import gauge_generator
import signed_fourbank
import banked_angles_v3 as banked
fixed_shifts=COMP/'verifiers/dfthcsos/FeMoCo76o113e.fixed_shifts.npz'
factor,original_words,gauge_report=gauge_generator.generate(PUBLIC_WORDS,fixed_shifts,copies=30,iterations=100)
chem_data,sign_gauge_report=signed_fourbank.canonicalize(factor,original_words,brot=10)
angle_words=chem_data['angle_words']
assert sign_gauge_report['rows_checked']==3976
assert sign_gauge_report['max_component_drift_up_to_row_sign']<1e-11
assert np.array_equal(chem_data['W'],factor['W']) and np.array_equal(chem_data['H2_I'],factor['H2_I'])
chem_folder=FINAL/'dfthcsos';chem_folder.mkdir(exist_ok=True)
gauge_generator.save_factorization(chem_folder/'submission.npz',chem_data)
save_json(REPORTS/'gauge_build.json',gauge_report)
save_json(REPORTS/'signed_gauge.json',sign_gauge_report)
EXPECTED_ANGLE_COUNT=25
deltas=banked.batch_deltas(angle_words,3)
assert len(deltas)==EXPECTED_ANGLE_COUNT
angle_reports=[]
for index,delta in enumerate(deltas):
    circuit,report=signed_fourbank.build(delta,10,return_report=True)
    path=chem_folder/f'angle_k_{index}.kmb'
    circuit.to_file(str(path),format='kmb')
    assert circuit.num_qubits==128 and report['static_toffoli']==1129
    angle_reports.append({'index':index,'sha256':digest(path),**report})
    del circuit
save_json(REPORTS/'banked_build.json',{'angles':angle_reports,'angle_count':len(angle_reports),
    'max_angle_qubits':max(row['num_qubits'] for row in angle_reports),
    'method':'Signed-Givens gauge, four-address banks and five-scratch pebbling',
    'full_official_check_required':True})
print('Built 25 signed four-address lookups: 128Q and 1129 Toffolis each.',flush=True)
del factor,original_words,chem_data,angle_words,deltas
gc.collect()

```

## 3. DQI: source-level memory scheduling

The decoder is the published reversible Reed–Solomon construction of **Gu et al.**, ported to the competition field by **Dmitrii Gluzdov**. His V6 schedule borrows idle template words, streams sweep evaluation, and recreates a field norm rather than retaining it. Kozykorpesh's symbolic runtime folds identities using exact Boolean forms and conservative invalidation across native operations.

The pinned baseline rebuilds to **1789Q and 445229 static Toffolis**. Its canonical circuit hash must match before verification. Approximate decoder support assumptions remain part of the credited algorithm; they are not labelled as all-input correctness proofs. The full official verifier measures both value and phase errors and includes the resulting repetition penalty.

That penalty matters because the task objective is $R Q^2 T$. A structural reduction in $Q$ has a quadratic benefit. A different sampled error count alone does not establish a better decoder, so the development salt is fixed and hashes are never selected for favorable samples.

> **Code (DE):** [DQI] dqi_driver.py — Treiber, der den Decoder aus den gen_dqi_v6-Modulen baut.

```python

%%writefile src/dqi_driver.py
"""Full source decoder build with exact symbolic lowering (Apache-2.0)."""
import os,sys,pathlib,json,time,gc

def build(destination,work):
    src=pathlib.Path(__file__).resolve().parent
    work=pathlib.Path(work);work.mkdir(parents=True,exist_ok=True)
    os.environ['DQI_BORROW']='affine'
    if str(src/'gen_dqi_v6') not in sys.path:sys.path.insert(0,str(src/'gen_dqi_v6'))
    import gu_formula_derivation as F
    t,_=F.run_b12();assert F.certify_kt(t['KT12'],F.FIELD)
    c=json.loads((src/'gen_dqi_v6/ref/gu_constants.json').read_text());c.update(t)
    path=work/'dqi_constants.json';path.write_text(json.dumps(c));os.environ['DQI_CONSTANTS']=str(path)
    import gu_port as G,run_gu_port as RG,round2_gadgets as R2
    import importlib
    G=importlib.reload(G);R2=importlib.reload(R2)
    import symbolic_runtime as S
    G.Builder=S.SymbolicBuilder;G.declare_registers=S.declare_registers
    G.borrow_template=RG.borrow_template
    R2.install(G,top_first=True,pebble_last=True,norm_pebble=True,compact_from=70)
    source=(src/'gen_dqi_v6/round2_gadgets.py').read_text()
    # Sweep emits native array operations. Mark every write conservatively.
    source=source[source.index('def lean_sweep('):]
    source=source.replace('b.physical[q]','b.wire(q)').replace('b.physical[root]','b.wire(root)').replace('b.physical[loc[0]]','b.wire(loc[0])').replace('b.physical[ps[h]]','b.wire(ps[h])')
    source=source.replace("raw.cx(arr([q for word in words for q in word]),arr([q for _ in words for q in target]))", "raw.cx(arr([q for word in words for q in word]),arr([q for _ in words for q in target]));b.invalidate(target)")
    source=source.replace("tr=A.open('tree',11);", "b.invalidate(val);tr=A.open('tree',11);")
    source=source.replace("linear=[('L',tuple(w[k] for w in ebw),0,(val[k],)) for k in range(12)]", "linear=[('L',tuple(w[k] for w in ebw),0,(val[k],)) for k in range(12)]")
    source=source.replace("raw.del_and(b.wire(root),arr(om),arr(loc))", "raw.del_and(b.wire(root),arr(om),arr(loc));b.forms[loc[0]]=S.ZERO")
    source=source.replace("raw.init_and(b.wire(root),arr(om),arr(loc))", "raw.init_and(b.wire(root),arr(om),arr(loc));b.invalidate(loc)")
    source=source.replace("raw.cx(arr([w[k] for w in omw]),arr(om*len(omw)))", "raw.cx(arr([w[k] for w in omw]),arr(om*len(omw)));b.invalidate(om)")
    source=source.replace("if factor!=1:raw.gf2_imul(factor,target=reg,field=gf)", "if factor!=1:raw.gf2_imul(factor,target=reg,field=gf)")
    ns={'S':S};exec(source,ns)
    def native_sweep(b,E,A,omw,ebw,abw):
        qs=[q for r in omw+ebw+abw for q in r]
        b.suspended=True
        ns['stream_sweep'](b,E,A,omw,ebw,abw)
        b.invalidate(qs)
        b.suspended=False
    G.emit_sweep=native_sweep
    start=time.monotonic();b,_=G.build();b.k.free(b.measurement)
    cir=b.k.finish_circuit();cir.to_file(str(destination),format='kmb')
    report={'num_qubits':cir.num_qubits,'toffoli_count':int(cir.operation_statistics().num_toffoli_like),'ops':len(cir),'build_seconds':time.monotonic()-start,'elided':b.elided,'folded':b.folded,'symbolic_products':len(b.products)}
    return report

```

> **Code (DE):** [DQI] selected_decoder.py — Auswahl des finalen Decoders.

```python

%%writefile src/selected_decoder.py
"""Notebook-facing wrapper for Kozykappa V3's readable DQI source.

Place upstream dqi_driver.py and its gen_dqi_v6/ directory beside this file.
The competition kickmix package must already be on sys.path. This wrapper
performs source generation only; use the unchanged official full verifier.
"""
from hashlib import sha256
from pathlib import Path

EXPECTED_SHA256 = '529b075009f7758abeda83a63407f0c1feeb51dd70631ae4335dfd28721b7e08'
EXPECTED_QUBITS = 1789
EXPECTED_TOFFOLIS = 445229


def build_selected(destination, work):
    import dqi_driver
    destination = Path(destination)
    destination.parent.mkdir(exist_ok=True, parents=True)
    report = dqi_driver.build(destination, Path(work))
    digest = sha256()
    with destination.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    actual = digest.hexdigest()
    assert actual == EXPECTED_SHA256, (actual, EXPECTED_SHA256)
    assert report['num_qubits'] == EXPECTED_QUBITS, report
    assert report['toffoli_count'] == EXPECTED_TOFFOLIS, report
    return report | {'sha256': actual, 'upstream': 'Kozykappa V3 / run361677445'}

```

> **Code (DE):** [DQI] port_runtime.py — symbolisches Runtime für die Identitäts-Faltung (Kozykorpesh).

```python

%%writefile src/gen_dqi_v6/port_runtime.py
# SPDX-License-Identifier: Apache-2.0
"""Small explicit adapter for Gu et al.'s published source to official kickmix.

Integer wire handles and LIFO ownership match the published builder. Physical
kickmix qubits stay allocated while this adapter accounts for their lifetimes;
every recycle emits the same reset as the authors' Builder. Named replay holds
are checked, so the journal cannot silently alias live scratch.
"""
from contextlib import contextmanager
import json, os, pathlib, time
import kickmix as km
from ref.gu_classical import GF2n, f2_matinv, f2_transpose, parity
from ref.gu_linear import linear_in_place


def load_contract(_):
    contract=json.loads((pathlib.Path(__file__).parent/'ref/gu_contract.json').read_text())
    # The paper uses 0x10eb. The competition uses 0x1053. All arithmetic
    # formulas are regenerated from this field; no field labels are conflated.
    contract['gf_poly']=km.GF2Field(12).modulus
    return contract


class Journal:
    """Gu et al., uncompute.bennett.Journal; pure conjugate choreography."""
    def __init__(self): self._steps=[];self.recording=True
    def mark(self):return len(self._steps)
    def step(self, fwd, rev=None):
        fwd()
        if self.recording:self._steps.append((fwd,rev if rev is not None else fwd))
    def defer(self, fwd, rev=None):self._steps.append((fwd,rev if rev is not None else fwd))
    def forward(self,since=0,until=None):
        for fwd,_ in self._steps[since:until]:fwd()
    def reverse(self,since=0,until=None):
        for _,rev in reversed(self._steps[since:until]):rev()


class Builder:
    def __init__(self):
        self.k=km.CircuitBuilder()
        self.physical=[]
        self.free_qubits=[];self.free_set=set();self.active=set()
        self.errors=[self.k.create_classical_register(12,name=f'E{j}') for j in range(4095)]
        # Published emitter uses each HMR outcome only for the immediately
        # following phase repayments, before the next HMR. Reusing one live
        # classical bit preserves that ordering and avoids dead classical ids.
        self.measurement=self.k.alloc_bits(1)[0]
        self.phase_stats=[];self.gate_counts={}
        self.phase_name='init';self.started=time.monotonic()
        self.owners={};self.live_profile={};self.current_phase=None
        self.progress=pathlib.Path(os.environ['BRIDGE_OUT'])/'build_progress.json' if 'BRIDGE_OUT' in os.environ else None

    def qubit(self):
        if self.free_qubits:
            q=self.free_qubits.pop();self.free_set.remove(q)
        else:
            q=len(self.physical);self.physical.append(self.k.alloc_qubits(1)[0])
        assert q not in self.active
        self.active.add(q)
        self._profile()
        return q
    def qubits(self,n):return [self.qubit() for _ in range(n)]
    def reclaim(self,qs):
        qs=list(qs);want=set(qs)
        assert len(want)==len(qs) and want<=self.free_set, ('reclaim live ids',want-self.free_set)
        self.free_qubits[:]=[q for q in self.free_qubits if q not in want]
        self.free_set-=want;self.active.update(want)
        self._profile()
    def recycle(self,q):
        assert q in self.active,('recycle not active',q)
        self.k.reset(self.physical[q])
        self.active.remove(q);self.free_qubits.append(q);self.free_set.add(q)
        self.owners.pop(q,None)
    def recycle_all(self,qs):
        for q in qs:self.recycle(q)
    def _profile(self,force=False):
        if self.current_phase is None:return
        p=self.live_profile.setdefault(self.current_phase,{'peak_active':0,'peak_physical':0})
        p['peak_physical']=max(p['peak_physical'],len(self.physical))
        if len(self.active)>p['peak_active'] or (force and len(self.active)==p['peak_active']):
            p['peak_active']=len(self.active)
            counts={}
            for q in self.active:
                name=self.owners.get(q,'unclaimed')
                counts[name]=counts.get(name,0)+1
            p['owners_at_peak']=counts
    def claim(self,name,qs):
        for q in qs:self.owners[q]=name
        self._profile(force=True)
    def release(self,name,qs):
        for q in qs:self.owners.pop(q,None)
    def release_recycle(self,name,qs):self.recycle_all(reversed(qs))
    def _gate(self,name,*qs,cond=None):
        if cond is not None:self.k.push_condition(cond)
        self.gate_counts[name]=self.gate_counts.get(name,0)+1
        getattr(self.k,name)(*[self.physical[q] for q in qs])
        if cond is not None:self.k.pop_condition()
    def x(self,q,cond=None):self._gate('x',q,cond=cond)
    def z(self,q,cond=None):self._gate('z',q,cond=cond)
    def cx(self,c,t,cond=None):self._gate('cx',c,t,cond=cond)
    def cz(self,a,b,cond=None):self._gate('cz',a,b,cond=cond)
    def ccx(self,a,b,t,cond=None):self._gate('ccx',a,b,t,cond=cond)
    def ccz(self,a,b,c,cond=None):self._gate('ccz',a,b,c,cond=cond)
    def swap(self,a,b,cond=None):self._gate('swap',a,b,cond=cond)
    def cswap(self,c,a,b,cond=None):self._gate('cswap',c,a,b,cond=cond)
    def neg(self,cond=None):
        assert cond is not None
        self.k.neg_if(cond)
    def hmr(self,q):
        self.k.hmr(self.physical[q],self.measurement)
        return self.measurement
    @contextmanager
    def phase(self,name):
        self.k.info_tag('@enter:'+name)
        self.phase_name=name
        prev=self.current_phase;self.current_phase=name
        self._profile()
        before=dict(self.gate_counts)
        t=time.monotonic()
        p={'phase':name,'elapsed':t-self.started,'physical_qubits':len(self.physical),'active_qubits':len(self.active)}
        print(json.dumps(p),flush=True)
        if self.progress:self.progress.write_text(json.dumps(p,indent=2))
        yield
        self.k.info_tag('@exit:'+name)
        self.phase_stats.append({'phase':name,'seconds':time.monotonic()-t,
                                 'gates':{k:v-before.get(k,0) for k,v in self.gate_counts.items()}})
        self.live_profile[name]['exit_active']=len(self.active)
        self.current_phase=prev


def declare_registers(b,decls):
    regs={}
    for index,(_,width) in enumerate(decls):
        assert not b.free_qubits
        start=len(b.physical)
        reg=b.k.create_quantum_register(width,name=f'S{index}')
        b.physical.extend(reg)
        qs=list(range(start,start+width));b.active.update(qs)
        regs[f'S{index}']=qs
    return regs


def assert_metrics(b,_):
    return b.gate_counts.get('ccx',0)+b.gate_counts.get('cswap',0)+b.gate_counts.get('ccz',0)


def emit_and_report(b):
    raise RuntimeError('Use run_gu_port.py; no implicit publication or emission destination.')

```

> **Code (DE):** [DQI] gu_formula_derivation.py — Herleitung der Gu-Formeln (reversibles Reed-Solomon).

```python

%%writefile src/gen_dqi_v6/gu_formula_derivation.py
# SPDX-License-Identifier: Apache-2.0
# Gu et al., deterministic field formula derivation, adapted imports.
#!/usr/bin/env python3
"""Regenerate constants.json for the dqi-reed-solomon discovered circuit.

main() reruns every search and writes constants.json.  The searches, in
file order:

  Formulas     the multiplication formulas and tower maps (KT12, KT6,
               KT3, CUBE3Q, PAIR3, LIN).  Deterministic; seconds.
  BM windows   the per-round coefficient windows (IMAXV, KMSV, KMMV).
               search.c samples the full Berlekamp-Massey recursion over
               403.2M weight-law draws (56 fixed seeds, 7.2M draws each)
               and counts, per (round, slot), how often the slot changes
               state.  Each window is the smallest one whose clipped
               slots all have mass under 4e-5 per draw.  About 2.7
               CPU-hours; the seeds run on a thread pool (3.5 min on 56
               cores).
  Psi windows  the cofactor windows of the Psi route: per CR op, the
               minimal cyclic interval covering the union support where
               the op acts, over 400k law draws (16 fixed seeds) plus
               the w = 0 anchor and every w = 1 position.  BM runs under
               the freshly derived BM windows.



# [DE] … (Modul gesamt 696 Zeilen; hier nur der Kopf — vollständiger Quelltext im Original-Notebook / Dataset.)

```

> **Code (DE):** [DQI] gu_port.py — Port des reversiblen Reed-Solomon-Decoders von Gu et al. auf das Wettbewerbsfeld (1838 Zeilen).

```python

%%writefile src/gen_dqi_v6/gu_port.py
# SPDX-License-Identifier: Apache-2.0
# Adapted from andigu/uncompute by Gu et al.; see REPORT.md and ref/gu_README.md.
#!/usr/bin/env python3
"""dqi-reed-solomon discovered circuit: fused-Q truncated Berlekamp-Massey
decode at (m, n, b) = (4095, 70, 12), then a half-degree Bezout pass that
turns the per-point Forney division into a precomputed Psi = 1/sigma'
mod sigma, so the Chien/Forney sweep costs 23 Toffoli per point (root
test 11 + a rank-12 gated pairing 12) instead of 80.  Built natively on
uncompute.Builder.

The BM body runs the (2,2,3)-tower field arithmetic under the measured
window schedule and stores no accepted discrepancy: the scale identity
sigma_0 * DEL == 1 replaces it (README).
The Psi route (stages 5-7) holds the Bezout pair in the syndrome TAIL,
zeroed by extending the in-place omega transform to all 70 rows.

Layout (flat):
  circuit.py         the tables (field, formulas, schedule; loaded from
                    constants.json), the circuit layer (term lists,
                    emitter, Psi-route gadgets, sweep body), and build(),
                    the stage sequence with its phase marks and cost pins.
  constants.json    every searched value: the formula tables, the BM
                    windows (bm_windows), the Psi windows (psi_windows).
  gen_constants.py  reruns every search and writes constants.json; it


# [DE] … (Modul gesamt 1838 Zeilen; hier nur der Kopf — vollständiger Quelltext im Original-Notebook / Dataset.)

```

> **Code (DE):** [DQI] round2_gadgets.py — Gadgets der zweiten Optimierungsrunde.

```python

%%writefile src/gen_dqi_v6/round2_gadgets.py
# SPDX-License-Identifier: Apache-2.0
"""Round-two reversible scheduling changes; original algebra: Gu et al.

The quotient swap schedule, early Euclid quotient parking, and early linear
root erasure were developed in this workspace (OpenAI Codex, 2026-10-23).
"""
from contextlib import contextmanager


def install(G,top_first=False,pebble_last=False,norm_pebble=False,compact_from=70):
    @contextmanager
    def quotient(self, ctl, bb_l):
        E=self.E
        if self.A.round>=compact_from:
            with compact_quotient(G,self,ctl,bb_l) as mq:yield mq
            return
        if pebble_last and self.A.round==68:
            with pebble_quotient(G,self,ctl,bb_l,full=norm_pebble) as mq:yield mq
            return
        with G.opened(E,'pq',G.B) as pv:
            E.mac(G.prod_rt(pv,self.Dw,self.SIG[0]))
            with G.opened(E,'dinv',G.B) as dv, G.chain_live(E,pv,dv):
                # The quotient occupies p's register; swap back before erasing
                # the inversion scaffold, whose source is the original p.


# [DE] … (Modul gesamt 276 Zeilen; hier nur der Kopf — vollständiger Quelltext im Original-Notebook / Dataset.)

```

> **Code (DE):** [DQI] run_gu_port.py — Build-Aufruf des Gu-Ports.

```python

%%writefile src/gen_dqi_v6/run_gu_port.py
# SPDX-License-Identifier: Apache-2.0
"""Build the paper-source port with arbitrary classical phase masks.

The published source's fixed mask and loop emitter are replaced by an
in-place Chien scan. The decoder and all constants are generated from
source for the competition field, never translated from binary circuits.
"""
import argparse, hashlib, json, os, pathlib, time, traceback
os.environ['OMP_NUM_THREADS']='1'
import kickmix as km


def borrow_template(b,E,A,bm,dW):
    """Route the final template's two high zero words into a scratch loan.

    The common completed recurrence leaves words d and d+1, modulo 37,
    zero in the cyclic template bank. Routing these into fixed words 35
    and 36 permits a 24-qubit loan. This is an approximate support claim,
    tested by check_borrow.py and the official verifier, not an assertion
    for all inputs. The inverse route restores the remaining template.
    """
    import gu_port as G
    bb=bm.final_bb_l
    def swaps(v):


# [DE] … (Modul gesamt 231 Zeilen; hier nur der Kopf — vollständiger Quelltext im Original-Notebook / Dataset.)

```

> **Code (DE):** [DQI] symbolic_runtime.py — symbolische Laufzeit mit konservativer Invalidation.

```python

%%writefile src/gen_dqi_v6/symbolic_runtime.py
"""Exact bounded symbolic partial evaluation for reversible kickmix emission.

Every form is an XOR of independent formal atoms, including constant atom 0.
An AND of forms is interned as a fresh atom; no independence assumption is
used to infer equalities. Oversized forms are forgotten into unique atoms,
which loses optimization opportunities but cannot create false equalities.
HMR returns a wire to zero and permits immediate physical reuse. Declared
input registers remain pinned. No input examples enter this compiler.
SPDX-License-Identifier: Apache-2.0
"""
import kickmix as km
import port_runtime as R

ZERO=frozenset()
ONE=frozenset((0,))
Base=R.Builder

class SymbolicBuilder(Base):
    def __init__(self):
        super().__init__()
        self.forms=[];self.pinned=set();self.atom_id=0;self.products={}
        self.elided={};self.folded={};self.max_native=0
        self.limit=48

    def atom(self):
        self.atom_id+=1
        return frozenset((self.atom_id,))

    def xor(self,a,c):
        v=a^c
        return v if len(v)<=self.limit else self.atom()

    def product(self,a,c):
        if not a or not c:return ZERO
        if a==ONE:return c
        if c==ONE or a==c:return a
        if a^c==ONE:return ZERO
        # Canonical complemented inputs share the same nonlinear atom.
        ac=0 in a;cc=0 in c
        aa=a-ONE;bb=c-ONE
        key=(aa,bb) if tuple(sorted(aa))<=tuple(sorted(bb)) else (bb,aa)
        if key not in self.products:self.products[key]=self.atom()
        v=self.products[key]
        if ac:v=self.xor(v,bb)
        if cc:v=self.xor(v,aa)
        if ac and cc:v=self.xor(v,ONE)
        return v

    def wire(self,q):
        if self.physical[q] is None:
            self.physical[q]=self.k.alloc_qubits(1)[0]
            if self.forms[q]==ONE:self.k.x(self.physical[q])
        return self.physical[q]

    def qubit(self):
        if self.free_qubits:
            q=self.free_qubits.pop();self.free_set.remove(q)
            assert self.forms[q]==ZERO
        else:
            q=len(self.physical);self.physical.append(None);self.forms.append(ZERO)
        assert q not in self.active
        self.active.add(q)
        return q

    def _constant(self,q):
        if q in self.pinned or self.forms[q] not in (ZERO,ONE):return
        if self.physical[q] is not None:
            if self.forms[q]==ONE:self.k.x(self.physical[q])
            self.k.free(self.physical[q]);self.physical[q]=None

    def recycle(self,q):
        assert q in self.active
        if self.forms[q]:
            # Retain actual reset semantics on every approximate path.
            self.k.reset(self.wire(q))
        if self.physical[q] is not None:self.k.free(self.physical[q])
        self.physical[q]=None;self.forms[q]=ZERO
        self.active.remove(q);self.free_qubits.append(q);self.free_set.add(q)
        self.owners.pop(q,None)

    def _native(self,name,qs,cond):
        if cond is not None:self.k.push_condition(cond)
        self.gate_counts[name]=self.gate_counts.get(name,0)+1
        getattr(self.k,name)(*[self.wire(q) for q in qs])
        if cond is not None:self.k.pop_condition()

    def _gate(self,name,*qs,cond=None):
        if getattr(self,'suspended',False):
            self._native(name,qs,cond)
            if name not in ('z','cz','ccz'):
                changed=qs[-2:] if name in ('swap','cswap') else qs[-1:]
                self.invalidate(changed)
            return
        fs=[self.forms[q] for q in qs]
        def skip():self.elided[name]=self.elided.get(name,0)+1
        def fold(n,qq):
            self.folded[name+'->'+n]=self.folded.get(name+'->'+n,0)+1
            self._gate(n,*qq,cond=cond)
        if name in ('z','cz','ccz'):
            if any(f==ZERO for f in fs):skip();return
            keep=[q for q,f in zip(qs,fs) if f!=ONE]
            if len(keep)<len(qs):
                if not keep:
                    if cond is None:
                        # Global half-turn retained explicitly using one bit.
                        q=self.k.alloc_qubits(1)[0];self.k.x(q);self.k.z(q);self.k.x(q);self.k.free(q)
                    else:self.k.neg_if(cond)
                else:fold(('z','cz','ccz')[len(keep)-1],keep)
                return
            self._native(name,qs,cond);return
        if name in ('cx','ccx','cswap'):
            n=1 if name in ('cx','cswap') else 2
            if any(f==ZERO for f in fs[:n]):skip();return
            if name=='cx' and fs[0]==ONE:fold('x',qs[1:]);return
            if name=='ccx':
                if fs[0]==ONE:fold('cx',qs[1:]);return
                if fs[1]==ONE or fs[0]==fs[1]:fold('cx',(qs[0],qs[2]));return
                if fs[0]^fs[1]==ONE:skip();return
            if name=='cswap':
                if fs[1]==fs[2]:skip();return
                if fs[0]==ONE:fold('swap',qs[1:]);return
        if name=='swap' and fs[0]==fs[1]:skip();return
        if name=='swap' and cond is None and not any(q in self.pinned for q in qs):
            a,c=qs;self.physical[a],self.physical[c]=self.physical[c],self.physical[a]
            self.forms[a],self.forms[c]=fs[1],fs[0]
            skip();return
        self._native(name,qs,cond)
        if name=='x':updates={qs[0]:self.xor(fs[0],ONE)}
        elif name=='cx':updates={qs[1]:self.xor(fs[1],fs[0])}
        elif name=='ccx':updates={qs[2]:self.xor(fs[2],self.product(fs[0],fs[1]))}
        elif name=='swap':updates={qs[0]:fs[1],qs[1]:fs[0]}
        elif name=='cswap':
            delta=self.product(fs[0],self.xor(fs[1],fs[2]))
            updates={qs[1]:self.xor(fs[1],delta),qs[2]:self.xor(fs[2],delta)}
        else:raise ValueError(name)
        for q,f in updates.items():
            self.forms[q]=f if cond is None else self.atom()
            self._constant(q)

    def hmr(self,q):
        self.k.hmr(self.wire(q),self.measurement)
        self.forms[q]=ZERO
        self._constant(q)
        return self.measurement

    def invalidate(self,qs):
        # Direct native field operations bypass this adapter. Conservatively
        # forget their outputs; no value-based optimization may cross them.
        for q in qs:self.forms[q]=self.atom()

def declare_registers(b,decls):
    regs=R.declare_registers(b,decls)
    assert not b.forms
    b.forms=[b.atom() for _ in b.physical]
    b.pinned.update(q for v in regs.values() for q in v)
    return regs

```

> **Code (DE):** [DQI] ref/gu_classical.py — klassische Referenzimplementierung (Gu et al.).

```python

%%writefile src/gen_dqi_v6/ref/gu_classical.py
"""uncompute.classical — classical math shared by circuits and their checks.

Nothing here touches a Builder: these are the pure-Python models and
table-builders whose OUTPUTS enter emitted circuits (lookup tables, linear
layers, test vectors, reference values): GF(2^n) scalar arithmetic and
GF(2) linear-map helpers. One exp/log-table field (``GF2n``) serves every
finite-field circuit. ``poly`` is always the full reduction polynomial
including the x^n term (e.g. 0x13 for GF(16)).
"""


# ---- GF(2^n) scalar arithmetic ---------------------------------------------


def _clmul_mod(a, b, n, poly):
    """Return a * b in GF(2^n) mod ``poly`` (LSB-first schoolbook + reduce)."""
    prod = 0
    for i in range(n):
        if (a >> i) & 1:
            prod ^= b << i
    for bit in range(2 * n - 2, n - 1, -1):
        if (prod >> bit) & 1:
            prod ^= poly << (bit - n)
    return prod & ((1 << n) - 1)


class GF2n:
    """GF(2^n) mod ``poly``, by exp/log tables over a primitive element.

    ``gen`` is the smallest primitive element, so ``gen == 2`` (the element
    x) whenever x is primitive. ``exp[k] = gen^k`` for k in [0, 2*order):
    the table repeats once, so ``exp[log[a] + log[b]]`` needs no modulo.
    ``log[a]`` is the exponent k with gen^k = a, for nonzero a. ``log[0]`` is 0, a
    placeholder: callers test for zero first. Hot loops may index ``exp``
    and ``log`` directly. The constructor raises ValueError when ``poly``
    is not irreducible of degree n. Tables cost O(2^n), so n stays small.
    """

    __slots__ = ("exp", "gen", "log", "n", "order")

    def __init__(self, n, poly):
        self.n = n
        self.order = order = (1 << n) - 1  # multiplicative group order
        for gen in range(1, 1 << n) if poly >> n == 1 else ():
            exp, x = [1], gen
            while x != 1 and len(exp) < order:
                exp.append(x)
                x = _clmul_mod(x, gen, n, poly)
            if x == 1 and len(exp) == order:
                break
        else:
            raise ValueError(f"poly {poly:#x} is not irreducible of degree {n}")
        self.gen = gen
        self.exp = exp + exp
        self.log = [0] * (order + 1)
        for k, v in enumerate(exp):
            self.log[v] = k

    def mul(self, a, b):
        """Return a * b."""
        if a == 0 or b == 0:
            return 0
        return self.exp[self.log[a] + self.log[b]]

    def pow(self, a, e):
        """Return a^e for any integer e. 0^0 is 1; 0^e is 0 otherwise."""
        if a == 0:
            return int(e == 0)
        return self.exp[self.log[a] * e % self.order]

    def inv(self, a):
        """Return a^-1. The inverse is totalized: 0 maps to 0."""
        return self.exp[self.order - self.log[a]] if a else 0

    def sqrt(self, a):
        """Return the unique square root, a^(2^(n-1))."""
        return self.exp[(self.log[a] << (self.n - 1)) % self.order] if a else 0

    def trace(self, a, k=None):
        """Return a + a^2 + a^4 + ... + a^(2^(k-1)).

        ``k=None`` means k = n: the absolute trace, 0 or 1 for every a.
        For a in the subfield GF(2^k), k dividing n, the same sum is the
        subfield trace to GF(2).
        """
        t = 0
        for _ in range(self.n if k is None else k):
            t ^= a
            a = self.mul(a, a)
        return t


# ---- GF(2) linear-map helpers ----------------------------------------------


def parity(x):
    """GF(2) parity of an int's bits."""
    return x.bit_count() & 1


def f2_rows_of(fn, n):
    """Return the rows of the GF(2)-linear map ``fn`` on n-bit ints.

    Row i is a packed int: bit j is set when input bit j feeds output
    bit i (LSB-first, the layout ``gadgets.linear_xor`` takes). The call
    checks linearity over all 2^n inputs and raises AssertionError on a
    nonlinear ``fn``, which would otherwise yield a silently wrong
    matrix.
    """
    cols = [fn(1 << j) for j in range(n)]
    for v in range(1 << n):
        image = 0
        for j in range(n):
            if (v >> j) & 1:
                image ^= cols[j]
        assert fn(v) == image, "map is not GF(2)-linear"
    return [sum((((cols[j] >> i) & 1) << j) for j in range(n)) for i in range(n)]


def f2_matinv(rows, n):
    """Inverse of the n x n GF(2) matrix ``rows`` (LSB-first packed ints)
    by partial-pivot Gauss-Jordan; asserts invertibility.
    """
    A = list(rows)
    I = [1 << i for i in range(n)]
    for col in range(n):
        piv = None
        for r in range(col, n):
            if (A[r] >> col) & 1:
                piv = r
                break
        assert piv is not None, "singular matrix"
        A[col], A[piv] = A[piv], A[col]
        I[col], I[piv] = I[piv], I[col]
        for r in range(n):
            if r != col and ((A[r] >> col) & 1):
                A[r] ^= A[col]
                I[r] ^= I[col]
    return I


def f2_transpose(rows, n):
    """Transpose of the n x n GF(2) matrix ``rows`` (LSB-first packed
    ints).
    """
    return [sum(((rows[r] >> c) & 1) << r for r in range(n)) for c in range(n)]

```

> **Code (DE):** [DQI] ref/gu_linear.py — lineare Referenz (Gu et al.).

```python

%%writefile src/gen_dqi_v6/ref/gu_linear.py
"""GF(2) linear-layer synthesis.

Source: conventional Gauss-Jordan row elimination, emitted as the reversed
elimination schedule — the textbook in-place CNOT/SWAP realization of an
invertible F2 matrix, as used across the finite-field literature. ``linear_xor`` is the textbook
out-of-place form: one CNOT per set matrix entry.
"""


def linear_in_place(b, qs, rows):
    """Apply the invertible GF(2) matrix ``rows`` to register ``qs`` in
    place: qs <- rows * qs. ``rows[i]`` is the packed-int row i (bit j =
    column j, little-endian to match register order).

    Synthesis is leftmost-pivot Gauss-Jordan elimination recorded and
    emitted in reverse: 0 Toffoli, only CX and SWAP; no ancillas. Raises
    (via the identity assert) if the matrix is singular.
    """
    n = len(qs)
    a = list(rows)
    assert len(a) == n
    ops = []
    for col in range(n):
        pivot = next(r for r in range(col, n) if (a[r] >> col) & 1)
        if pivot != col:
            a[col], a[pivot] = a[pivot], a[col]
            ops.append(("swap", col, pivot))
        for r in range(n):
            if r != col and (a[r] >> col) & 1:
                a[r] ^= a[col]
                ops.append(("cx", col, r))
    assert a == [1 << i for i in range(n)], "singular matrix"
    for kind, i, j in reversed(ops):
        (b.swap if kind == "swap" else b.cx)(qs[i], qs[j])


def linear_xor(b, src, dst, rows):
    """XOR the GF(2) matrix-vector product onto a second register:
    dst ^= rows * src. ``rows[i]`` is the packed-int row i (bit j =
    column j), for example from :func:`uncompute.classical.f2_rows_of`.

    Emits one CX per set matrix entry in row-major order: for each dst
    bit i, for each src bit j. 0 Toffoli; no ancillas. ``src`` and
    ``dst`` must be disjoint.
    """
    for i, row in enumerate(rows):
        for j in range(len(src)):
            if (row >> j) & 1:
                b.cx(src[j], dst[i])

```

> **Code (DE):** [DQI] ref/gu_constants.json — Feld-Konstanten/Templates (1975 Zeilen, reine Daten).

```python

%%writefile src/gen_dqi_v6/ref/gu_constants.json
{
 "KT12": [
  [
   [
    0,
    8,
    9
   ],
   [
    0,
    8,
    9
   ],
   [
    0,
    7,
    10,
    11
   ]
  ],
  [
   [
    6,
    7,


# [DE] … (Modul gesamt 1975 Zeilen; hier nur der Kopf — vollständiger Quelltext im Original-Notebook / Dataset.)

```

> **Code (DE):** [DQI] ref/gu_contract.json — Contract/Hashes der Referenz.

```python

%%writefile src/gen_dqi_v6/ref/gu_contract.json
{
 "_provenance": "Task-defining derived constants shared by grader.py and every circuit. grader.py re-derives all of them from its inline definitions and asserts equality with this file at import. c_stream_hex = counter-mode SHA-256 over c_tag (block i = SHA-256(tag || u32le(i))), truncated to 6143 bytes = the 49140-bit fixup vector c (bit k = bit k%8 of byte k/8; the top 4 bits of the last byte are unused); weight_cum_2p16 = the exact DQI weight law |w_k|^2 of Jordan et al. (2025), arXiv:2408.08292, at this instance (m=4095, l=35, p=2016/4096), quantized to a /2^16 grid by largest-remainder rounding (entry k = P(weight <= k) * 2^16).",
 "gf_poly": 4331,
 "m": 4095,
 "n_synd": 70,
 "b": 12,
 "w_max": 35,
 "c_tag": "kickmix/rs-decode-4095/fixup-c/v1",
 "c_stream_hex": "0ab02275411d99401427df155f38df3d98dc8cd245edf6c545c44fbdfa580586048e10430b242a866358f792f5d4bf309aa3b5df457ec1be714f477bb3674d87bfe6f1e5be30e94aebbc685caf06703c256d6fde56cf1a71a44b26dd3a7f4d39f6ee5a39ed36d49a8e7c160a82ce95c221a9fbc6191b503d5c06976bb53878ace4318e6992c5f4932f6671be9cb705bf20019f44b90345f3b313d959710822c65345a2e2ec8bc270038e5582285d76fe1f53be1cccfe381d130665f33d1269c7aa3dd34878ea8d00369625db16895818731b0694f61f915d05c3f9b62b3008ce551248aa11fb39a8ea189aadb70f573e5f0ef48b8bb73acd01aad27897b0d5b18284284238aca81eed501a557a884a7091224220db6414a2b7c794c187ef6a883e7b375c5b0b0b1497d28aa0f35cfce019afeba54fbb98dc521625e100829b51b15495d8fdf1cfe2175d92668f20a62456ce4ef718b26360f2e83f44de3d452b8a131aac6dca7ef463c96510ca780ff5f76dd3e45894651052e7fae51261b65be4d020647db7f45b233d3bbb4d5941e0b7c303ceb613f3c2ed9b11127a1858f12416d6c957bc5cc58e7f1cb655790578fc64db0720c70190f95ed1c662b81b5e29405e9fa3d8e3ed252853155b5b487dd1c3c8b72771712cb8980b4844211d343db065d60d8e31040e0ebd116bd0a434b38eeede887faad8f4f2a616040b6d605648772342a892f8c571728216671979de87050e3d6a76888b24c3111f257fdb13e5ee92fcc2d851abe85ee3bd80c57404144c2a6fe4049a4a9e8ec74a4642cc8c8eb760b801f14692371add6298127eda4508e4ceb9cfd363d1b55bee8157b116f12c938d5b3f37e147c57f065155e7a4c290fbb4f616acabf0a8ade65294356083304276d56d35790d8bd9b7103f70276ff89d187c0fff73a8fe23cdab99d92f4a176725d43ee8043ce2bb852ec84f834419c4a2ef968aab729a62f09ca081e5041af453a53d7ab399c41cff68e56d30e04bdd4aca3eae09ea16ff96fc3f00fe200aee77e275a3b05f2d6c623b746950fd294fc60bb42826113566cab8358d1a435bdd025cb1905a301f7dd71957c9359f73feb93af6325b84a6628b5097d1ef7d6a8c05949ec66b7a682fcc69ce76c3d736d2e1db88c89c012af8565fd7cfbdcc1f9cb26c73d6af71a4020d6b5edab892539c62e98d81bd7ba114f960e45cc78ca2946d77cec0d232a8bf397e99d9e112c5a576887f718850303d3aba9d958b55b913c9d310a20ff7e946688e5f8f9f01230dc26900594e93581a93a08a2d294d7c9349dc211ef66b729810e3bac545d94aec168270882dbd225bce7af21585fd6d572ccb3ded7903f0211145fb0132d56c07a4834fdbe997c99ed61d9bf391754c75726fcf4896af7d205cabebafee5d8d34a9f7d091ce5557a7c984cbd73076dbc76526668476a9b55c610bb68614be2662ae4e9d4cd823c6fabd7ccf627e672e56dff4555987168ba7b87be4b69cfcd78f6e3a6a2d6faf054b2c5787bbcc92688bdbe59ba6f0925b9d38922df8398022f27dac378b1e19b616eb65215350707341357c5cc4f006b3e12b073a03a1bd8edd06af7e31562effd6ba689130ea72f39106d075d09312625897741a7a82f00a0f5f0b91618ed22da815ad6a3e446e7621b9889c96eedc287785751985ee5622ecd80bfe2324893ba8656c290b3faa2b7c8726515f5e605809a7ae4b6e04fb3fd6ef0165eb01b0b0e6d8dc38b3bb7e7f18a6c983611e8ee601ce55a8897aa244a68d3ddcc1241a28d039874c1c352fbd99e505eb00d5e490d2b033fd4e8472a94a8ef947766e5881e1bba7513e899785b82148119f06676350d4ddb8f35905c53b0e05781d5ea6aa819c5152e4b9d3e4662dfbb5295467af2246af9b3743229f5f4a13edaae3860a99309a7fbd7a5c91d9b373f0cc597e30b9194cb5b3d491c27c6cb227f71939d0d836c588830e39e3e6b8436bcc9af6c76f07513b37cdf63ef37e1c1045a5d333a0c19c3960d02e9cbc2c0b1c196bab8c8ebdb7267dc1daa55e4820a3f351c0aa0e97850d9c8bc887faf4805cff561e93b4c1a25bdb8dd100180360855298b7f7e64bdcfc158a5fef4bdd811832c8e6266accde6f332df161e7ddb2d1627546c966da622d0a6a1a045251dda529b4e10fdd14f9f3fc94ea45ea3b29a56564ec9d30fd8c0f736b5ab7d7a1a45175347d391328170d559dc0da5c6d661a4513bfab803fa1eed3d2c658575ac5de52e6ae74a1addfdcb2d598e96826fd625147491b9bfa2ba270d531600ce2791e32e7fdf4fd7ec1152ee6596894c6e917c6f94e1e79094a82bdac1d5ae4b10c7062256cbc754c2fdc6546080c7242eeca80418cb10fb089f721e9e3552b2f9d0686533d9113d338883f246ac8e5e8028108797952b041ed934c65ec9d541c0d4766682e260e735627b2463d899c1bffe99c9337cf959e2947d01a91cd2d88951029cbc4726991190d1fae04117573905c8619b0afaca7163ef533e9c3bf8c279602488cdc0636c114e28697799b0242cbb310c3f557b0d9e6428ebe3d635d201d5ee183ece5400056943ba890e490a219f4e33bed5809bfea2c74138bfcb3aec67fca982aca9890de419c6054cb0c95f0504c01000fd05e86efab211b4fc7a722712c4f483d72b440065ed3869230623924e3254b2ebb7ffa29f4beea6bba9dc32f3572f78b749fba1540009a0b657aae24fea3d77241ce786ac68618c44c84a19b5f650c1217be19568c28ce5a95316de929f113b876c480456e73eaf94d1c5e1abe81d1f70ade42b87df32f0f7dc56520e7cca6679efe320c0ec1340e9a3f249871f8c7bc36c2e57920e5a2fe96917adf1c9c56809a733e7179246429092cac1a9ca5ffe668fb23a69579de104d3e08e86ce1b0f7bed3abf800608fd02853221cdcafab1ff8dd6eb9aa6577af77df9b3e774a62094f23a6cda60b64a54d1577c1fe0526087b86b3aac84d67db4a937bac13469a330e1fc28974cd2d60c07221de0980b1d46a7102317a381f951c8f0029ab2199b0f5a3fbbb5947cd25c291bff0dd37b635628d2882ff3ed73ad8bdeff3c9444ff97ebe21bb543cc5c3f7f1a0608c5ae28b6a5b591f43895cc088a078ed465f0dd8b289219ee1d1d4df353087b2e96d18c400ce7a8ac5d1e30e3920c5aba753d67e198bd51c57fb90f20ccd518f44a3162213e50f67f712e16d5fab5cbe32f585a817b10cb3e68f53c71c04d9c5a400be6701178f1681a9dc073511118eb668819290697a180380eaae3b68af08fddefdfe233f8cdda37eb90ae6d625b0119d54722ba4ccf62d2b44b272aae1d98ab954130e59e7240cc72dd9566459a2af5dca2ad2663dc4b6b8a48dc68b33ac575ffbd46da82f1bc31223c7e280853a6a2c6667152a3875a6d77f41a54a1f9f6e518f50e6a4e1ae06e81e77fd5461fe87516818a9a67a388e6b8ef41b03d521fb1034a59ce4ada4037844b815f00fe1560aa615052a02c2ec5d288bb441b905aa8fd78c1978632a4288d010b4d2357ec48a2535b827ebab108f2eba026a136043874363916cbd300a02b7624163bd7d2dc4688de111a94d5bce2c0f9b332d3b0f647ca94359d80c7785709942fb553165eb24e09489ba8fcbcb8992b89ab24f715dab250fdb51ccfcf0c2f5aded499a106c45fabd22542baa0c722e78c3e8196136a8ff93c46a1bda8222b6119a90c61fce032b382c52b6f308160d6190c85dabd93b633291969ddcb30b13e3bbf401dcd656944523181086bf5cede9ce66e756c3190df3dcdf268fb9b07dc642d2497625c7f87625780a537318fb5f719d12c384d3baa14094de38c440784b0036ef5e4ec873486ccb35baeab9185f9f5a53227e2e61540c8df2db7428a74aab497e16f4ec9c6ff63083339ad26d2e674b33d7f737f3a391302fa8fa367e8b035d78bc9db74145c5e6d338c8706bf0f70f7f39402d6c29d69760985f4ab54c30b1df29c6d26d3d7ecfd02749718c1decc5ecd7f8b5b007d3a533568217aba921f1bb56bf3c0ec82f1f4ae28acab500338de9a704893b5a33965a295a37f11649a90ce06b37ca0086a7f600e92a3d92a0462726bef2b5cf16818d28ff44cbc6742c4d8c5db383d3e35767c0849797bc2d1d54b3d733128bcf61a2c1f81534abce1170909592c2a4318ab53dcdf6b2c722cf992502ee3d08d460540359df9120a36e0414cbd9e144ad4c62c51f8b5873c3d9c6d6c1ee2e7e58bc40a9eabed857f9c53e5c5174237f5ba8dbe14e6219fb2f85b6364f4c81c295852a54401b57ee9354589283509e880decb0e6aa301a1def95506622fc0d37b6b91ebf5483cf4ea53ec2d452a37b440825beb96070c9d5b9c01485ffa779ba8b06c308b5e50185e335cb4016c4ea86c77878b08fdda99c0bc7376c3845b8c563ea2baff72fe7bf4e5bf2a7522dc4f9527baeeaff5c77dc5b7faa9a731e15d261e264b5ed30c278553b620c43e75addc70145f0c08d5db037d14057e143e5ae55b3fd973f818b008c45b063ee7f0c4f28554af92d6881f1efbc612e6af829525b2dd0f1fe2dc8ab2e4c31deb697699e88ea4fb4d43eea3519bf91730d96a1b554e484d8d95b58be290897ff641b71fd2d786d5ce4062e78b28545b30874b9eb30d9d8b4189919a29ecbc470c907b21ad5964034bbbbcc608d665b028b75627d00c411477fa3fbc78c34727cad31de8db8789d547fbe4a9431c9e03bb61f9e2b993cf127d0bb8402d2da817e9ae35e86134a57d5ce7061f2628b4db18f5d61c4ca8e5955fa126419b45f108dd81969e197473ec06ec736b48b9dd8bb838149042cfd9d9fabfd6b75282936f2ba24ee84b85751a0b1f8892b7a29f0e4c4d35f4d3d6efad602f8794954811d6d59145b2cd0d3d9ee5a2bd88c82664a98aa6a137a6d5046c7c6b23ab544478771b14b8e147e6ecc9a3146b438fffd9c86c708eaf915afb0b05f7b33e666780a4345ee7782624cd3db51ae1dce6e079662ff726a2d54527407eb4b983b9b5592a765a74f5f35cd608b97dc534dec3cbefc1430182a568386ff09755a5034aa2a3b6ea291a0483651f75e8b92bbc3260097ab5121708df9369315e86cb1f1a0a666252263294569115fd5169f034c9ce46897d736d6616cc11d407866bdb0af5c826c534763e810b70b0cae816603fa99ff3148ae17ad2122048cd2384950842d8d4608b32aacc304d5ab4b93f038db83fc45fbc2205d33a780717fc75aaf463f3793952d9a01cc9bb5c7755e4817b2d81d6f0a7a069c2e8d034f26e75ff8f36fa35e82613048e899c022b3b5abe3e2228f41edb25dc7235090644bbcff1287861e6cb545f5903839132f9e397768fc5e3e9160bb188a10c79f511e201e12de36e1b237a47d46bd41293f61e53fa0706ca447d2883ccdea8bc2f8b53eda7d61523bc576ecb381b1139dd286eaaa79fcd22a911554391573776c3a8fbae6ebac203bd993787145b13540582a3e2150de032895e61f3544e1a32ba84bbf95e240d38fae0080528fb1ce9dfdba196e3939b5045c9d6e2ca3a4867e4facc9ef2d620330a235550a489692818542786e256264f3aeb72e565ae46e83f73354573122d7ebf9fe345bdb3d67069e2664c4cdc128bdc43809b1660239411809d4f1cad42a99821bdb111c6c4a6ba41b0145db04198f034803f56c3deee1f3a4334bd9ec37db9bea24c66f342be2512d07a959d1c00a7d36f4c44963df8b22b6b788fca5fccef9871d555af82b8b27a06497a60bf24052cfdbdca7d18731c4cc5c561ede0102fc3679699111c8def6ea7df0701983c3a3722b3fdd6438de336cf7421e2029e40ecbd63c8a2c2479607df55d68b8fcf62941fb3c0a3bc3c21e86fb4e6b4c058b5a5282607640000c2adffb79de8f25d3a25dabebc26b9fe5be6943cd854be634a4e07556a68dc7c999312d4e0f77eded93dc454d44028fe10345e778444bda4c7af6593b650ff63909740c66a34329453ee46eb5014b6ee339ae734eec6c065218f0f22eb5eb4fd2836b7175b9bffe4a85c23dad53e6ab3625ef316e34c31718f3171d38328a143bc28af58184054690e4f16e279a1e5de044c1ac8a1ff5518c13242ddbcbcb97e30c580356bd466f4156a98c66f9a24976765aa396043f3f76e2184e963892e5bb4288c181a48d50aca0da0e99642692948934fdd30d892a3ed225438253abce27472fe1e62c3f2e9bcd01dc34ada72f0ba0ee50210881e25a522ba2b40e5b55695f0e9a0e094957d33e326df57c3fa48ee6931253939b782b015dac6e591fbda9b78d5b83e08d3ac8cc638e0a802762292ce095e51b16ecceee95b5323ea8fc2254a74b5c737ec217301ea14cc44703dec852603056d6dab998e6c34f8f3276216bf10a2e114c56f11d471c49858a95c272dddfcd5c86ae19e4f516b5f7a0a0ab7f7d414de68c0167ea71bbfb1afcec51614a1c0e2c51a4196c6ed44834776d14eda80fc0b446c8c7870990a0c6d1840f3d224d23151bf7fd36bf7e859c6c4c75b1f83bd01171514a438971ffbe5691a9d5b26a121270243eb6183ee60ac4c0b386ad3ce4b5a6d8f2cdc7c61de41d278aa9c473470a54aa27a80d78e9e22e51225f7b47dc3ad97017cc571350a622a9f895f66690773f8770f724f5cd86af9ded84d26972c80b88afd8e02684ac49c41b7d8875daa700f75b56909eb0e4d7c07ce7fbc92d5686aaaab86d53e3b5e5ff626c9b15052f919071c095b044cc3c3ddf194abcc128c07012584c735058b93544f4f736059c37ef3b1c1203c82c33396523b5b3a48b193e6eaff66cf2c88ab8506cfcc90d1e84011d78aa201b63f75ab435eb3326a81edb1531f95dbc19defdce72a66db0530b290fd42d194abd3961af6af54e9ee4ce9ccf5f37f08ab3bb6a9187e4da74675ee1ed963be6dbafb355a106e1656073e433302ca784d59cc10285000cfda8466c27247c1fc4f35bd5daaf2727c6c8e15b10713ac46528be2bba8bb0c4c9bf57109750cef993e2691d12c15d226923027d6f38b735caf4842d2dd8328519591248e5e5e23a533975ffc71276678415c397bdf9b99aee7d853c66fb6ceb3fab015b05e5c51bc8adb2064c629ae9acdead63edde2f1f35f95f40dce4bbe537121356477ef6135da2039e08a1af7db68903ca2bcb14bba9963c5d9df629a0d80dd13162016ecec5ca8fb0794315e2f4293fb3e652e6ca659a13cf45286983da01110f5731577bd14ffb461ace093b5170b405bfed241a957950cc1f5fe3e3914293c86c7e9e786fd464637b4b5980cb99b2fd06e43a535dd665df1c903e9a059ae9e71562cf1ee5fa018b7b8f341a2cd19580d79f915f3fa1ae22ced811a628535f60b823969a3e9b99a926adb1f3696035876d07f149aee05d5b73a714854aa6a1d26ccc926eabd32fbe985e881ba461280c98eee75e87b9af58b447ef6b01da8b6703f832963ecb4ac70fc43098274fbc58e417bdcc17056eb2359cb2d81e439d658a81ba959147d385cd207b10c7d73cd59494d2e4c33f22e6e573d1ea6ec390f7f9c218df196536b5c71fbda6807f8847c6fb5a88ced5e53cac46ac1a9dce71328ce65d41e50d084cc585c431699be3af7587ff6ae1a0aa76da0c70cc0dc4aa7cf3bdf767cc40a23e38e4e2a307214bd3025fbb84876f9d764c08bce44776088ae9b02a502bddb463cfbb8b2eec454e0c1e5159ab5b7a872ec35cce3461ccebc03a666fbcea8d3afce5decc4f61375bee4125eaaf2386655ae2554f7323b1dc22b200da6d6cdb77b64bff6676aa9c45386050d8f6a7025e5b7e765661a06f6eee5e57a330601196a6476a76bca9c2563a4e8738fc183a44b541cc1c42d64856007af7fa2f71cae4504078d187ba875b01f3826e15e98c48946e5b68812268860126a31fc6661f8608d61f5bc44b556f5fd9223aed2f61d55c31c3569716bbc473711812563e566163a93be589a35e469711e1f3b356e5357def24ba087e77b16adf5df3054251731c318a97dd1494ac9b81dbed2050295f336515f4ef346e0ed172f519824a95319f3f6a017ddf495b014e24f37420c7b7125ea9d6766bdc2dafacc2d7aa8363894dc73c5d36008f563a692622c35a55fd100c1e59580fa75589d4fb77f27088b4257b0cb33a400d1be219b69f230b24b3397caaf5ead6d74de2493e5259ed4b1696ea8a9c47c9a1196e8b107282d30ee31527f5b5c7c8e225641b8d78228727e915080279b56c2687cc4b87734c17560911323eeb6dc0c79fa914166968f54099075349fd578dbde760b4642004f9276e5c0fd2a2e4e6f0107c463784c7d42f085232994bd70e924767bc8ccba72c7f4d19ebf8c7839f72911f5354f22b2a305da91ef5fb5c623eb1d55566b4e4d781e87a4df56eea7bd89d0d8c4e3e1ca647baa1c106751cdb66ddb72da2a69e9bb4b366515f3a6db3fa4c9d2bf097e3b5f14caadbf64b2bf119b1b951cd1379299e3af7823a8a4e03c12ef861ad48b13839867a8c3bdb7119cc79b0f0521533f52475dfab5d10c430cb1b57ee6ece34c3b085fbbdb4ae080c7f63a3596cc3088cad73e5fd2fa90d02311540ed63b07c1c3a0be14f88fbf5f5280d9c5ca02c0408f1a2be67837f1af3eb134e57fc8b1b30ac1be1",
 "c_popcount": 24492,
 "c_stream_sha256": "8fcd44e5a419ea29d84bb443d75f10dc9ac85dde2085b7851d92cd198eb3785a",
 "weight_cum_2p16": [
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  1,
  4,
  13,
  41,
  121,
  333,
  843,
  1963,
  4199,
  8230,
  14737,
  24027,
  35550,
  47605,
  57694,
  63723,
  65536
 ]
}

```

> **Code (DE):** [DQI] ref/GU_LICENSE — Apache-2.0-Lizenztext von Gu et al.

```python

%%writefile src/gen_dqi_v6/ref/GU_LICENSE

                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "[]"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright [yyyy] [name of copyright owner]

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

```

> **Code (DE):** [DQI] ref/GU_COMMIT.txt — gepinnter Commit der Referenz.

```python

%%writefile src/gen_dqi_v6/ref/GU_COMMIT.txt
64b5a13aa249f1360846657392e6c66817b26d0f

```

> **Code (DE):** [DQI] Build-Aufruf: kompiliert den DQI-Decoder und prüft den Circuit-Hash.

```python

# notebook: hide_input
import contextlib
import selected_decoder
with (REPORTS/'dqi_source_build.log').open('w') as stream:
    with contextlib.redirect_stdout(stream):
        dqi_build_report=selected_decoder.build_selected(FINAL/'dqi.kmb',PUBLIC/'dqi')
save_json(REPORTS/'dqi_build.json',dqi_build_report)
assert dqi_build_report['num_qubits']==1789 and dqi_build_report['toffoli_count']==445229
assert dqi_build_report['sha256']=='529b075009f7758abeda83a63407f0c1feeb51dd70631ae4335dfd28721b7e08'
print(f"Decoder built from source: {dqi_build_report['num_qubits']}Q, {dqi_build_report['toffoli_count']:,} static Toffolis.",flush=True)
gc.collect()

```

> **Code (DE):** [DQI] Verifikation/Protokoll des DQI-Builds.

```python

# notebook: hide_input
EXPECTED_CIRCUIT_MEMBERS={'dfthcsos/angle_k_0.kmb': '6cc00e27b56f78bb69ca40f45fe57b4a8328e0c4cc37f8af0b938a4b634c1d70', 'dfthcsos/angle_k_1.kmb': '108a225439c916348496d374e5ce5452a140cd9abeaa176a48ccd02acbf9c455', 'dfthcsos/angle_k_2.kmb': 'e3091b0c2779a398c998586c43eb734fdc4309c2243917f2f338e4547174fa53', 'dfthcsos/angle_k_3.kmb': 'a48d7f26fc1b170452142d3aa6938f4554e9c317f288cff376356565e456fa1a', 'dfthcsos/angle_k_4.kmb': 'b639446b1e3efc8c3eefc630ea6388d24ae47c771cfea29790f45796621cceb2', 'dfthcsos/angle_k_5.kmb': '2140c1061a2f2e01db067656818847b4e4ba892816cdb824fb5a523d80d3c896', 'dfthcsos/angle_k_6.kmb': '211ce282122182aeafd3ce43dff5c5e039a4dbbbbc577839e5e769287f948cf3', 'dfthcsos/angle_k_7.kmb': '579d46c3131c46e346bf8a9db0ea83f565fdf00036b84990ff0a113ce6258f83', 'dfthcsos/angle_k_8.kmb': 'f13bf934f9c2296da4274e1d70e76d0572f52ad7d2191ec20ae7b347bada01d3', 'dfthcsos/angle_k_9.kmb': '951a31c552bf3fd2ee02dbe83169a4d83f4bfda0f623b1886e4f36136032569d', 'dfthcsos/angle_k_10.kmb': '8d731cb690f1319109593d72e39a5cdf2ef1c1f08d8846441a589341ac9d00e1', 'dfthcsos/angle_k_11.kmb': '395283ed0d2216cfd5a9a5d03c47e63bc467b95df176686239a4a548035472be', 'dfthcsos/angle_k_12.kmb': 'ae22d3c2030c06fe7f95739933e7a2c54556eda5ef94fd7a224d8a18913d4c63', 'dfthcsos/angle_k_13.kmb': '9bff1f9855937a6a301dd588bad8997dec213bcdcbb678ac190678b227d6b53b', 'dfthcsos/angle_k_14.kmb': 'cc1a49a71cd866d9f47a5973723208e937baf3996e0b90ef8d904f0b58ca8223', 'dfthcsos/angle_k_15.kmb': '20a6ddcf3cb0b0a35e44f35b15de2ae4886e7d4a95ad3add97154f7712faec37', 'dfthcsos/angle_k_16.kmb': 'fd83f84b5147f3f19d8ca352daa069891a23a4694047784d28f02454110456e0', 'dfthcsos/angle_k_17.kmb': '2a0f204ded1c90d4d59acf4ee38e1f3897bf2aa4adf1c877dcf3f848b9f049b3', 'dfthcsos/angle_k_18.kmb': '80366632dbf956a576176552fac45f5b2a889bcc047582fb99e658942784e228', 'dfthcsos/angle_k_19.kmb': '86a060743dbc76ee0132a7e8a1e1a826c92dbe6e3498cd3392aee3d42f3909dc', 'dfthcsos/angle_k_20.kmb': '93dea10520740578e157449197e08f10013767dbe6be2a934ca6990513d241e2', 'dfthcsos/angle_k_21.kmb': '3833ed6285cd5b33dea84add2570f9ba902ba291495668286d49d5fc54045a31', 'dfthcsos/angle_k_22.kmb': '81c3212cd0bb1065645089799fcdc67a294558268cc0b62aa0ef356c6286f7de', 'dfthcsos/angle_k_23.kmb': '119377ffd98218f55cfa7e816411d5bc11fccd1f20636d75913d88e4e9715a6d', 'dfthcsos/angle_k_24.kmb': '45eef871de2aecdb13b17bd96cdc2ec2a6993b887dba24fa7ecc2c6cddcd6066', 'invsqrt.kmb': '97f12b109eb17346991ca33e5604963a11eff1b2098586e048d1fd103de55b7c', 'dqi.kmb': '529b075009f7758abeda83a63407f0c1feeb51dd70631ae4335dfd28721b7e08'}
for name,expected_sha in EXPECTED_CIRCUIT_MEMBERS.items():
    assert digest(FINAL/name)==expected_sha,name
print('All 27 deterministic circuit files reproduce the selected source build.',flush=True)

```

## Full verification and the complete objective

Each task is checked once with the unchanged official verifier and its full shot count: **200,540,928** for inverse square root, **102,400** for DQI, and **254,464** for chemistry. The portfolio is the geometric mean of reference-cost gains.

The ZIP is created only after all three checks pass. Every one of its **28 members** is rehashed from the archive. Producing the ZIP does not submit it: the native competition submission is a separate action linked to this exact successful notebook version.

> **Code (DE):** metric_preflight.py — Preflight-Check der Metrik vor der Finalverifikation.

```python

%%writefile metric_preflight.py
"""Official Kaggle metric v10 readers, unchanged except formatting.
Source: https://www.kaggle.com/code/metric/google-quantum-ai-metric
Adapter preflight_directory only checks the file contract; task verification is separate.
"""
import json
import math
import pathlib
import random
import stat
import sys
import time
import tokenize
import zipfile
import zlib
from collections.abc import Callable, Mapping
from typing import Any
import numpy as np
import pandas as pd
ALLOWED_INSTRUCTIONS = {'X', 'CX', 'CCX', 'Z', 'CZ', 'CCZ', 'Z_POW', 'NEG', 'SWAP', 'CSWAP', 'R', 'HMR', 'BIT_INVERT', 'BIT_STORE0', 'BIT_STORE1', 'PUSH_CONDITION', 'POP_CONDITION', 'INFO_TAG', 'DEBUG_PRINT'}
MAX_QUBIT_OR_BIT_ID = 2 ** 30 // 1536
MAX_NPZ_BYTES = 2 ** 26

class ParticipantVisibleError(Exception):
    pass

def read_circuit(path: pathlib.Path, max_registers: int) -> Any:
    """Return a submitted .kmx or .kmb circuit as a kickmix.Circuit; raise ValueError unless it is fit to verify.

    kickmix validates a file as it parses it, within limits that keep parsing cheap, but simulating
    takes memory that grows with the largest qubit and bit ids, which kickmix allows up to ~5e8,
    so those are capped at MAX_QUBIT_OR_BIT_ID. kickmix also allows a million registers, at
    ~110 bytes each even if empty, so a circuit may have at most `max_registers`, the most its
    benchmark needs. Every register must be named: the dfthcsos verifier crashes on an unnamed one.
    """
    import kickmix
    circuit = kickmix.Circuit.from_file(path, format=path.suffix.removeprefix('.'))
    unsupported = set(circuit.operation_statistics()) - ALLOWED_INSTRUCTIONS
    if unsupported:
        raise ValueError(f'unsupported instructions {sorted(unsupported)}')
    largest_id = max(circuit.num_qubits, circuit.num_bits) - 1
    if largest_id >= MAX_QUBIT_OR_BIT_ID:
        raise ValueError(f'qubit or bit id {largest_id} is above the limit of {MAX_QUBIT_OR_BIT_ID - 1}')
    if circuit.num_registers > max_registers:
        raise ValueError(f'{circuit.num_registers} registers, above the limit of {max_registers} for this benchmark')
    if not all((isinstance(name, str) for name in circuit.register_data)):
        raise ValueError('every register needs a name, given by its REGISTER line')
    return circuit

def read_npz(path: pathlib.Path, spec: Mapping[str, tuple[str, tuple[int | str, ...]]]) -> dict[str, np.ndarray]:
    """Return the arrays `spec` names from an .npz; raise ValueError unless each is a plain number array as specified.

    `spec` maps each key to the numpy dtype kinds it may have, such as 'f' for floats, and its shape,
    in which a string names a dimension of any positive size that must agree wherever it recurs.

    Each array's header is a Python literal of its dtype and shape, which np.load trusts: a few KB
    of deflated zeros can claim a terabyte-sized array, and the dtype can be anything numpy can
    describe, from structured and nested types to Python objects that need unpickling. So the
    headers are read first, and the arrays loaded only if each is a plain number type of its kind,
    not big-endian, with its shape, and they total at most MAX_NPZ_BYTES. Only format 1.0 headers,
    which numpy.savez writes, are accepted, and numpy refuses any over 10 KB before parsing it.
    """
    dimensions: dict[str, int] = {}
    total = 0
    with zipfile.ZipFile(path) as archive:
        members = {name.removesuffix('.npy'): name for name in archive.namelist()}
        missing = [key for key in spec if key not in members]
        if missing:
            raise ValueError(f'{path.name} has no {missing}')
        for key, (kinds, expected_shape) in spec.items():
            with archive.open(members[key]) as member:
                if np.lib.format.read_magic(member) != (1, 0):
                    raise ValueError(f'{key} in {path.name} is not in .npy format 1.0, which numpy.savez writes')
                shape, _, dtype = np.lib.format.read_array_header_1_0(member)
            if dtype.kind not in kinds or dtype.names is not None or dtype.subdtype is not None or (dtype.byteorder == '>'):
                raise ValueError(f'{key} in {path.name} has dtype {dtype}, not a plain number type of numpy kind {kinds!r}')
            matches = len(shape) == len(expected_shape) and all((size > 0 and size == (dimensions.setdefault(expected, size) if isinstance(expected, str) else expected) for size, expected in zip(shape, expected_shape, strict=True)))
            if not matches:
                raise ValueError(f'{key} in {path.name} has shape {shape}, not {expected_shape} with its named dimensions as in {dimensions}')
            total += math.prod(shape) * dtype.itemsize
    if total > MAX_NPZ_BYTES:
        raise ValueError(f'the arrays in {path.name} take {total:,} bytes, above the limit of {MAX_NPZ_BYTES:,}')
    with np.load(path, allow_pickle=False) as npz:
        return {key: np.array(npz[key]) for key in spec}

def find_one(root: pathlib.Path, name: str, description: str, is_dir: bool=False) -> pathlib.Path:
    """The one path called `name` (a glob) under `root`, where the submission unpacked; raise ParticipantVisibleError otherwise."""
    paths = [path for path in root.rglob(name) if path.is_dir() == is_dir and '__MACOSX' not in path.relative_to(root).parts]
    if len(paths) != 1:
        raise ParticipantVisibleError(f'The submission must contain exactly one {description}, found {len(paths)}.')
    return paths[0]


def preflight_directory(directory):
    root = pathlib.Path(directory).resolve()
    inv_path = find_one(root, 'invsqrt.km[xb]', 'inverse circuit')
    dqi_path = find_one(root, 'dqi.km[xb]', 'DQI circuit')
    chemistry = find_one(root, 'dfthcsos', 'chemistry directory', is_dir=True)
    inv = read_circuit(inv_path, 1)
    inv_qubits = inv.num_qubits
    del inv
    decoder = read_circuit(dqi_path, 4095 + 70)
    decoder_qubits = decoder.num_qubits
    del decoder
    angles = sorted(chemistry.glob('angle_k_*.km[xb]'))
    if not angles or {p.stem for p in angles} != {f'angle_k_{i}' for i in range(len(angles))}:
        raise ValueError('Angle circuits must have consecutive numbering with no duplicate formats')
    angle_widths = []
    for path in angles:
        circuit = read_circuit(path, 128)
        if circuit.num_qubits > 128:
            raise ValueError('ANGLE circuit exceeds the 128-qubit cap')
        angle_widths.append(circuit.num_qubits)
        del circuit
    specification = {
        'U': ('f', ('R', 'B', 76)), 'W': ('f', ('R', 'B', 'C')),
        'H2_I': ('f', ('R', 'C')), 'H1_I': ('f', ()),
        'Hsym_lower': ('f', (2926,)), 'tree_edges': ('iu', (75, 2))
    }
    npz_path = find_one(chemistry, 'submission.npz', 'factorization')
    arrays = read_npz(npz_path, specification)
    paths = [inv_path, dqi_path, *sorted(angles, key=lambda p: int(p.stem.rsplit('_', 1)[1])), npz_path]
    return {'status': 'PASS', 'scope': 'Official file readers and archive layout; separate task PASS required',
            'invsqrt_qubits': inv_qubits, 'dqi_qubits': decoder_qubits,
            'angle_qubits': angle_widths, 'factorization_shape': list(arrays['W'].shape),
            'archive_members': [str(p.relative_to(root)).replace('\\', '/') for p in paths]}

```

> **Code (DE):** Fährt die drei offiziellen Full-Verifikatoren (200.540.928 / 102.400 / 254.464 Shots) — nur wenn RUN_FULL_VERIFICATION=True.

```python

if not RUN_FULL_VERIFICATION:
    raise RuntimeError('This release requires full verification before producing a submission archive.')

# Verify the changed arithmetic first; each complete official task check runs once.
inv_result = measured('invsqrt_full', lambda: IV.verify(inv_candidate,
    IV.ProblemSpecInvSqrt.for_n_p(10), salt=SALT, max_workers=WORKERS))
assert inv_result['status'] == 'PASS' and inv_result['verified_shots'] == 200_540_928
del inv_candidate; gc.collect()
print(f'Full inverse-square-root PASS: {inv_result["verified_shots"]:,} shots; {inv_result["wall_seconds"]:.1f}s.', flush=True)

chemistry_result = measured('chemistry_full', lambda: verify_chemistry(FINAL / 'dfthcsos', salt=SALT))
assert chemistry_result['status'] == 'PASS'
assert chemistry_result['verified_shots'] == 254_464
assert chemistry_result['num_circuits'] == EXPECTED_ANGLE_COUNT
print(f'Full chemistry PASS: {chemistry_result["verified_shots"]:,} shots; {chemistry_result["wall_seconds"]:.1f}s.', flush=True)

decoder = km.Circuit.from_file(str(FINAL / 'dqi.kmb'), format='kmb')
dqi_result = measured('dqi_full', lambda: DV.verify(decoder,
    DV.ProblemSpecDQI.benchmark_instance(), salt=SALT, max_workers=WORKERS))
assert dqi_result['status'] == 'PASS' and dqi_result['verified_shots'] == 102_400
del decoder; gc.collect()
print(f'Full DQI PASS: {dqi_result["verified_shots"]:,} shots; {dqi_result["wall_seconds"]:.1f}s.', flush=True)

implementation_path = Path('metric_preflight.py').resolve()
module_spec = importlib.util.spec_from_file_location('metric_preflight', implementation_path)
preflight = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = preflight
module_spec.loader.exec_module(preflight)
file_contract = measured('archive_preflight', lambda: preflight.preflight_directory(FINAL))
assert file_contract['status'] == 'PASS'

results = {'invsqrt': inv_result, 'dqi': dqi_result, 'dfthcsos': chemistry_result}
cost_rows = []
for name, result in results.items():
    cost_rows.append({'Task': name, 'Status': result['status'], 'Qubits': result['num_qubits'],
                      'Measured cost': result['score'], 'Reference cost': REFERENCE_COSTS[name],
                      'Gain vs reference': REFERENCE_COSTS[name] / result['score'],
                      'Verifier seconds': result['wall_seconds'], 'Shots': result['verified_shots']})
cost_table = pd.DataFrame(cost_rows)
display(cost_table.style.format({'Measured cost': '{:,.3f}', 'Reference cost': '{:,.3f}',
                                'Gain vs reference': '{:.4f}x', 'Verifier seconds': '{:.1f}'}))
projected_score = math.prod(row['Gain vs reference'] for row in cost_rows) ** (1/3)
print(f'Projected combined score from this run: {projected_score:.6f}')
print('This is not an independently observed Kaggle leaderboard score.')
save_json(REPORTS / 'portfolio.json', {'projected_score': projected_score, 'task_costs': cost_rows,
                                    'observed_kaggle_score': None,
                                    'projection_salt': SALT, 'environment': environment})

```

> **Code (DE):** Erstellt die Ergebnis-Tabelle der drei Tasks aus den Verifikator-Reports.

```python

task_labels = {'invsqrt': 'Inverse square root', 'dqi': 'DQI decoder', 'dfthcsos': 'Chemistry'}
task_order = ['invsqrt', 'dqi', 'dfthcsos']
measured_gains = []
for task in task_order:
    result = results[task]
    assert result['status'] == 'PASS' and math.isfinite(result['score']) and result['score'] > 0
    measured_gains.append({'task': task, 'label': task_labels[task],
        'measured_cost': float(result['score']), 'reference_cost': REFERENCE_COSTS[task],
        'gain': REFERENCE_COSTS[task] / result['score'], 'qubits': int(result['num_qubits']),
        'verified_shots': int(result['verified_shots']),
        'mean_toffoli_count': float(result['toffoli_count']),
        'max_toffoli_count': result.get('max_toffoli_count'),
        'rotation_count': result.get('rotation_count'),
        'toffoli_equivalent': result.get('toffoli_equivalent')})

checked_projection = math.prod(row['gain'] for row in measured_gains) ** (1/3)
assert math.isclose(checked_projection, projected_score, rel_tol=1e-12)

fig, ax = plt.subplots(figsize=(9, 3.5))
bars = ax.barh([row['label'] for row in measured_gains], [row['gain'] for row in measured_gains],
    color=[COLORS['blue'], COLORS['green'], COLORS['orange']], height=0.56)
ax.axvline(1, color=COLORS['muted'], linewidth=1, linestyle='--')
for bar, row in zip(bars, measured_gains):
    ax.text(bar.get_width() + 0.15, bar.get_y() + bar.get_height()/2,
        f"{row['gain']:.3f}x  |  {row['qubits']:,}Q", va='center')
ax.set(xlabel='Reference task cost / full-verified task cost',
    xlim=(0, max(row['gain'] for row in measured_gains) * 1.23),
    title='Measured component gains in this Run All')
ax.invert_yaxis()
ax.grid(axis='x', alpha=0.15)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(FIGURES / 'portfolio_measured_gains.png', dpi=180, bbox_inches='tight')
plt.show()
plt.close(fig)

inverse_runtime_resources = {
    'Qubits': int(results['invsqrt']['num_qubits']),
    'Mean Toffolis': float(results['invsqrt']['toffoli_count']),
    'Max static Toffolis': int(results['invsqrt']['max_toffoli_count']),
    'Synthesized rotations': int(results['invsqrt']['rotation_count']),
    'Toffoli-equivalent cost per qubit': float(results['invsqrt']['toffoli_equivalent']),
    'Measured task cost': float(results['invsqrt']['score']),
}
print('Selected arithmetic: fresh full-official-verifier measurements')
display(pd.DataFrame([inverse_runtime_resources]).style.format(precision=3).hide(axis='index'))


comparison_snapshot_utc='2026-10-24'
score_evidence=pd.DataFrame([
    {'Revision':'Our separate Signed-Digit Memory','Value':5.77242,'Evidence':'Observed competition score','Run':'361502374'},
    {'Revision':'Our previous source V3','Value':6.280713692702279,'Evidence':'Full-verifier projection; not submitted','Run':'361586741'},
    {'Revision':'Mizero calibration V1','Value':6.37294,'Evidence':'Observed competition score','Run':'361675142'},
    {'Revision':'Kozykorpesh signed-gauge V3','Value':6.68108,'Evidence':'Observed competition score','Run':'361677445'},
    {'Revision':'This source V4','Value':checked_projection,'Evidence':'Current full-verifier projection before native submission','Run':'Current'}
])
display(score_evidence.style.format({'Value':'{:.6f}'}).hide(axis='index'))
print(f'V4 full-verifier projection: {checked_projection:.6f}. A competition score requires the separate native submission.')
print("The notebook badge may initially show V1's 5.67004; it identifies a different archive.")
save_json(REPORTS/'portfolio_comparison.json',{'revision':'V4','component_gains':measured_gains,
    'selected_inverse_resources':inverse_runtime_resources,'source_comparison_snapshot_utc':comparison_snapshot_utc,
    'score_evidence':score_evidence.to_dict('records'),'new_projected_score':checked_projection,
    'new_observed_competition_score':None,'new_submission_id':None})

```

> **Code (DE):** Prüft, dass alle 25 dfthcsos angle_k_*.kmb + submission.npz im Submit-Ordner sind.

```python

expected_angle_members = {f'dfthcsos/angle_k_{index}.kmb' for index in range(EXPECTED_ANGLE_COUNT)}
expected_archive_members = {'invsqrt.kmb', 'dqi.kmb', 'dfthcsos/submission.npz'} | expected_angle_members
assert set(file_contract['archive_members']) == expected_archive_members
assert len(file_contract['archive_members']) == 3 + EXPECTED_ANGLE_COUNT

manifest = []
for name in file_contract['archive_members']:
    path = FINAL / name
    manifest.append({'file': name, 'bytes': path.stat().st_size, 'sha256': digest(path)})
save_json(REPORTS / 'submission_manifest.json', manifest)
archive_path = WORK / 'submission.zip'
with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for row in manifest:
        archive.write(FINAL / row['file'], row['file'])
with zipfile.ZipFile(archive_path) as archive:
    assert sorted(archive.namelist()) == sorted(row['file'] for row in manifest)
    for row in manifest:
        with archive.open(row['file']) as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == row['sha256'], row['file']
print(f'Verified submission.zip: {archive_path.stat().st_size / 2**20:.2f} MiB; {len(manifest)} entries.')
print('Creating this archive does not submit it to the competition.')

# The verified archive and final members are reviewable outputs. Only the
# temporary build directory is removed, after every archived hash matched.
if PUBLIC.exists():
    resolved_work = WORK.resolve()
    resolved_build = PUBLIC.resolve()
    if (PUBLIC.is_symlink() or PUBLIC.name != 'build'
            or resolved_build.parent != resolved_work or resolved_build == resolved_work):
        raise ValueError('Temporary build cleanup must stay in the direct WORK/build directory.')
    if PUBLIC.is_dir():
        shutil.rmtree(resolved_build)
gc.collect()

```

> **Code (DE):** Packt submission.zip (28 Mitglieder) erst nach allen PASS und rehasht jedes Mitglied aus dem Archiv.

```python

# notebook: hide_input
required_shots={'invsqrt':200540928,'dqi':102400,'dfthcsos':254464}
member_hashes={row['file']:row['sha256'] for row in manifest}
expected_members={'invsqrt.kmb','dqi.kmb','dfthcsos/submission.npz'} | {
    f'dfthcsos/angle_k_{i}.kmb' for i in range(EXPECTED_ANGLE_COUNT)}
assert set(member_hashes)==expected_members and len(member_hashes)==28
for name,row in results.items():
    assert row['status']=='PASS' and row['verified_shots']==required_shots[name]
    if name!='dfthcsos':assert row['circuit_sha256']==member_hashes[name+'.kmb']
assert results['dfthcsos']['num_circuits']==25
with zipfile.ZipFile(archive_path) as archive:
    assert set(archive.namelist())==expected_members and len(archive.namelist())==28
    for name in archive.namelist():
        with archive.open(name) as stream:
            assert hashlib.file_digest(stream,'sha256').hexdigest()==member_hashes[name]
release_receipt={'revision':'V4','revision_status':'FULL_VERIFIED_BEFORE_NATIVE_SUBMISSION',
    'new_projected_score':projected_score,'new_observed_competition_score':None,
    'new_submission_id':None,'competition_submission_performed_by_notebook':False,
    'all_full_checks':{key:{'status':r['status'],'score':r['score'],'verified_shots':r['verified_shots']}
        for key,r in results.items()},
    'development_salt':SALT,'archive_file':archive_path.name,'archive_bytes':archive_path.stat().st_size,
    'archive_sha256':digest(archive_path),'member_count':28,'member_sha256':member_hashes,
    'archive_member_hashes_rechecked':True,
    'phase_calibration_report_sha256':digest(REPORTS/'rotation_calibration.json'),
    'signed_gauge_report_sha256':digest(REPORTS/'signed_gauge.json'),
    'historical_badge_v1':5.67004,
    'comparison_snapshot':{'date_utc':'2026-10-24','kozy_v3_actual':6.68108,
        'kozy_submission_id':57583144,'mizero_v1_actual':6.37294,'mizero_submission_id':57582994},
    'source_only_inputs':'Official competition plus public FeMoCo numerical dataset V2; no Toolbox circuits or binary oracle.'}
save_json(REPORTS/'release_receipt.json',release_receipt)
print('V4 complete: three fresh full official PASS checks and all 28 archived hashes rechecked.')
print(f'Full-verifier projection: {projected_score:.6f}. Competition score is obtained only by native submission.')

```

> **Code (DE):** Legt Lizenz-/Attributions-Dateien neben die erzeugten Artefakte.

```python

# Retain the license and attribution beside the generated artifacts.
(WORK / 'LICENSE').write_text('\n                                 Apache License\n                           Version 2.0, January 2004\n                        http://www.apache.org/licenses/\n\n   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION\n\n   1. Definitions.\n\n      "License" shall mean the terms and conditions for use, reproduction,\n      and distribution as defined by Sections 1 through 9 of this document.\n\n      "Licensor" shall mean the copyright owner or entity authorized by\n      the copyright owner that is granting the License.\n\n      "Legal Entity" shall mean the union of the acting entity and all\n      other entities that control, are controlled by, or are under common\n      control with that entity. For the purposes of this definition,\n      "control" means (i) the power, direct or indirect, to cause the\n      direction or management of such entity, whether by contract or\n      otherwise, or (ii) ownership of fifty percent (50%) or more of the\n      outstanding shares, or (iii) beneficial ownership of such entity.\n\n      "You" (or "Your") shall mean an individual or Legal Entity\n      exercising permissions granted by this License.\n\n      "Source" form shall mean the preferred form for making modifications,\n      including but not limited to software source code, documentation\n      source, and configuration files.\n\n      "Object" form shall mean any form resulting from mechanical\n      transformation or translation of a Source form, including but\n      not limited to compiled object code, generated documentation,\n      and conversions to other media types.\n\n      "Work" shall mean the work of authorship, whether in Source or\n      Object form, made available under the License, as indicated by a\n      copyright notice that is included in or attached to the work\n      (an example is provided in the Appendix below).\n\n      "Derivative Works" shall mean any work, whether in Source or Object\n      form, that is based on (or derived from) the Work and for which the\n      editorial revisions, annotations, elaborations, or other modifications\n      represent, as a whole, an original work of authorship. For the purposes\n      of this License, Derivative Works shall not include works that remain\n      separable from, or merely link (or bind by name) to the interfaces of,\n      the Work and Derivative Works thereof.\n\n      "Contribution" shall mean any work of authorship, including\n      the original version of the Work and any modifications or additions\n      to that Work or Derivative Works thereof, that is intentionally\n      submitted to Licensor for inclusion in the Work by the copyright owner\n      or by an individual or Legal Entity authorized to submit on behalf of\n      the copyright owner. For the purposes of this definition, "submitted"\n      means any form of electronic, verbal, or written communication sent\n      to the Licensor or its representatives, including but not limited to\n      communication on electronic mailing lists, source code control systems,\n      and issue tracking systems that are managed by, or on behalf of, the\n      Licensor for the purpose of discussing and improving the Work, but\n      excluding communication that is conspicuously marked or otherwise\n      designated in writing by the copyright owner as "Not a Contribution."\n\n      "Contributor" shall mean Licensor and any individual or Legal Entity\n      on behalf of whom a Contribution has been received by Licensor and\n      subsequently incorporated within the Work.\n\n   2. Grant of Copyright License. Subject to the terms and conditions of\n      this License, each Contributor hereby grants to You a perpetual,\n      worldwide, non-exclusive, no-charge, royalty-free, irrevocable\n      copyright license to reproduce, prepare Derivative Works of,\n      publicly display, publicly perform, sublicense, and distribute the\n      Work and such Derivative Works in Source or Object form.\n\n   3. Grant of Patent License. Subject to the terms and conditions of\n      this License, each Contributor hereby grants to You a perpetual,\n      worldwide, non-exclusive, no-charge, royalty-free, irrevocable\n      (except as stated in this section) patent license to make, have made,\n      use, offer to sell, sell, import, and otherwise transfer the Work,\n      where such license applies only to those patent claims licensable\n      by such Contributor that are necessarily infringed by their\n      Contribution(s) alone or by combination of their Contribution(s)\n      with the Work to which such Contribution(s) was submitted. If You\n      institute patent litigation against any entity (including a\n      cross-claim or counterclaim in a lawsuit) alleging that the Work\n      or a Contribution incorporated within the Work constitutes direct\n      or contributory patent infringement, then any patent licenses\n      granted to You under this License for that Work shall terminate\n      as of the date such litigation is filed.\n\n   4. Redistribution. You may reproduce and distribute copies of the\n      Work or Derivative Works thereof in any medium, with or without\n      modifications, and in Source or Object form, provided that You\n      meet the following conditions:\n\n      (a) You must give any other recipients of the Work or\n          Derivative Works a copy of this License; and\n\n      (b) You must cause any modified files to carry prominent notices\n          stating that You changed the files; and\n\n      (c) You must retain, in the Source form of any Derivative Works\n          that You distribute, all copyright, patent, trademark, and\n          attribution notices from the Source form of the Work,\n          excluding those notices that do not pertain to any part of\n          the Derivative Works; and\n\n      (d) If the Work includes a "NOTICE" text file as part of its\n          distribution, then any Derivative Works that You distribute must\n          include a readable copy of the attribution notices contained\n          within such NOTICE file, excluding those notices that do not\n          pertain to any part of the Derivative Works, in at least one\n          of the following places: within a NOTICE text file distributed\n          as part of the Derivative Works; within the Source form or\n          documentation, if provided along with the Derivative Works; or,\n          within a display generated by the Derivative Works, if and\n          wherever such third-party notices normally appear. The contents\n          of the NOTICE file are for informational purposes only and\n          do not modify the License. You may add Your own attribution\n          notices within Derivative Works that You distribute, alongside\n          or as an addendum to the NOTICE text from the Work, provided\n          that such additional attribution notices cannot be construed\n          as modifying the License.\n\n      You may add Your own copyright statement to Your modifications and\n      may provide additional or different license terms and conditions\n      for use, reproduction, or distribution of Your modifications, or\n      for any such Derivative Works as a whole, provided Your use,\n      reproduction, and distribution of the Work otherwise complies with\n      the conditions stated in this License.\n\n   5. Submission of Contributions. Unless You explicitly state otherwise,\n      any Contribution intentionally submitted for inclusion in the Work\n      by You to the Licensor shall be under the terms and conditions of\n      this License, without any additional terms or conditions.\n      Notwithstanding the above, nothing herein shall supersede or modify\n      the terms of any separate license agreement you may have executed\n      with Licensor regarding such Contributions.\n\n   6. Trademarks. This License does not grant permission to use the trade\n      names, trademarks, service marks, or product names of the Licensor,\n      except as required for reasonable and customary use in describing the\n      origin of the Work and reproducing the content of the NOTICE file.\n\n   7. Disclaimer of Warranty. Unless required by applicable law or\n      agreed to in writing, Licensor provides the Work (and each\n      Contributor provides its Contributions) on an "AS IS" BASIS,\n      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or\n      implied, including, without limitation, any warranties or conditions\n      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A\n      PARTICULAR PURPOSE. You are solely responsible for determining the\n      appropriateness of using or redistributing the Work and assume any\n      risks associated with Your exercise of permissions under this License.\n\n   8. Limitation of Liability. In no event and under no legal theory,\n      whether in tort (including negligence), contract, or otherwise,\n      unless required by applicable law (such as deliberate and grossly\n      negligent acts) or agreed to in writing, shall any Contributor be\n      liable to You for damages, including any direct, indirect, special,\n      incidental, or consequential damages of any character arising as a\n      result of this License or out of the use or inability to use the\n      Work (including but not limited to damages for loss of goodwill,\n      work stoppage, computer failure or malfunction, or any and all\n      other commercial damages or losses), even if such Contributor\n      has been advised of the possibility of such damages.\n\n   9. Accepting Warranty or Additional Liability. While redistributing\n      the Work or Derivative Works thereof, You may choose to offer,\n      and charge a fee for, acceptance of support, warranty, indemnity,\n      or other liability obligations and/or rights consistent with this\n      License. However, in accepting such obligations, You may act only\n      on Your own behalf and on Your sole responsibility, not on behalf\n      of any other Contributor, and only if You agree to indemnify,\n      defend, and hold each Contributor harmless for any liability\n      incurred by, or claims asserted against, such Contributor by reason\n      of your accepting any such warranty or additional liability.\n\n   END OF TERMS AND CONDITIONS\n\n   APPENDIX: How to apply the Apache License to your work.\n\n      To apply the Apache License to your work, attach the following\n      boilerplate notice, with the fields enclosed by brackets "[]"\n      replaced with your own identifying information. (Don\'t include\n      the brackets!)  The text should be enclosed in the appropriate\n      comment syntax for the file format. We also recommend that a\n      file or class name and description of purpose be included on the\n      same "printed page" as the copyright notice for easier\n      identification within third-party archives.\n\n   Copyright [yyyy] [name of copyright owner]\n\n   Licensed under the Apache License, Version 2.0 (the "License");\n   you may not use this file except in compliance with the License.\n   You may obtain a copy of the License at\n\n       http://www.apache.org/licenses/LICENSE-2.0\n\n   Unless required by applicable law or agreed to in writing, software\n   distributed under the License is distributed on an "AS IS" BASIS,\n   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.\n   See the License for the specific language governing permissions and\n   limitations under the License.\n', encoding='utf-8')
(WORK / 'NOTICE').write_text("Quantum Circuits resource labs (2026)\nOriginal experiments, explanations and added implementations: anazemcev / ViberTeam.\nReleased under the Apache License, Version 2.0, subject to upstream notices.\n\nAttribution and dependencies\n\nGoogle Quantum AI competition authors: task specifications, reference circuits,\nKickmix simulator and unchanged official verification/file-reader code.\nhttps://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation\n\nRudra Bhaskar: direct polynomial phasing, retained coefficient table and\nlow-memory arithmetic adapted by the inverse-square-root implementation.\nhttps://www.kaggle.com/code/rudrabhaskar/direct-polynomial-phasing-verified-search?scriptVersionId=361364488\n\nLightningV08: compressed normalization flags.\nhttps://www.kaggle.com/code/lightningv08/quantum-circuits-memory-algebra\n\nSumit Chongder: open centered signed-digit inverse-square-root generator,\ncoefficient fitting, integer pipeline and arithmetic, retained and credited.\nhttps://www.kaggle.com/code/sumitchongder/notebook2f196e646b?scriptVersionId=361357149\nAdded adaptation: split high-word phasing, allocation after normalization,\nfolded final carry, and borrowing a proven constant input bit as clean carry.\nThe later 92-qubit revision reduces curvature precision F2 from 10 to 9,\nregenerates the coefficient table, and certifies the complete promised input\ndomain. Its same-table ordinary-schedule comparison has 102 qubits; the\noriginal Sumit coefficient table and 103-qubit circuit remain credited above.\n\nKozykappa: physical ensemble compression, sparse column rotations, and prior\npublic work on reachable-control simplification and clean-wire allocation.\nhttps://www.kaggle.com/code/kozykappa/quantum-circuits-sparse-sos-factors-and-circuit\n\nKozykorpesh / Kozykappa: two-address banked XOR QROM construction, adapted\nfrom Sumit's public arithmetic and used for the chemistry angle lookup.\nhttps://www.kaggle.com/code/kozykappa/quantum-ai-compact-arithmetic-banked-qrom?scriptVersionId=361433617\nKirill Tymchishin v10: integration of our public arithmetic/decoder/factors\nwith that banked lookup, which supplies the comparison baseline for this release.\nhttps://www.kaggle.com/code/kirilltym/quantum-circuits-qrom-tower42?scriptVersionId=361453242\nAdded adaptation: omit zero difference-bank columns and apply an exact\nreversible CNOT change of output basis for dependent columns. Both tables\nare transformed, preserving the XOR oracle on arbitrary input targets.\n\nk256.dev: public compiled DQI decoder and starting chemistry factorization.\nThe decoder's original generator is not included in that publication.\nhttps://www.kaggle.com/code/k256net/claude?scriptVersionId=361337610\n\nAccessible public dependency mirror: Kirill Tymchishin, version 7, labelled\nApache 2.0 by Kaggle. Both reused artifacts are pinned by SHA-256. This mirror\nlabel alone does not establish the full upstream ownership chain.\nhttps://www.kaggle.com/code/kirilltym/quantum-circuits-qrom-tower42?scriptVersionId=361358116\n\nAdded changes: split-phase scheduling and separate stage caches for invsqrt;\nindependent bounded Boolean-polynomial circuit simplification for DQI;\nalternating sparse rotations and effective-norm optimization for chemistry;\nlayout/precision experiments, resource explanations and full verification reports.\n\nThe scored archive, generated candidates and public dependencies are identified\nseparately in the notebook's reports. No endorsement by upstream authors is implied.\n\nCalibrated arithmetic revision\n\nKozykorpesh: published explicit calibrated integer coefficients and open\nexact-domain minimax regeneration, plus transitive AND implications.\nhttps://www.kaggle.com/code/kozykappa/quantum-ai-compact-arithmetic-banked-qrom?scriptVersionId=361456406\n\nAlex Chilton: shared prefix normalization and empty-target temporary-AND\nshift moves with measurement-based inverse and phase correction.\nhttps://www.kaggle.com/code/alexchilton/where-the-toffolis-go-anatomy-a-cheaper-invsqrt?scriptVersionId=361472684\n\nOur additions in this revision: use the promised input bound to replace\nmutually exclusive inverted-top-bit ANDs by affine logic; algebraic-normal-\nform lookup and measurement-phase cleanup for the exact chemistry words;\na fast C++ binary implementation of Kozykorpesh's implication pass with\nvalidated globally-clean conditional facts. The resulting DQI binary is\nidentical to Kozykorpesh's published output, not a new decoder design.\nThe original generator/compiled-input limits and notices above still apply.\n\nFinal derivative-split integration\n\nRudra Bhaskar: derivative residual/coarse representation, top-carry reuse,\nand static-high phase checkpoint generator, published under Apache-2.0.\nhttps://www.kaggle.com/code/rudrabhaskar/highest-public-score-direct-polynomial-phasing?scriptVersionId=361445283\nKirill Tymchishin v11: integration of that generator with Alex Chilton's\nnormalization and empty-target shift schedules; the 95-qubit baseline.\nhttps://www.kaggle.com/code/kirilltym/quantum-circuits-qrom-tower42?scriptVersionId=361491814\nOur final integration generalizes the derivative-split widths for the\nexplicit Kozykorpesh table, borrows one normalized constant input bit as\nan adder carry, and applies the promised-input top-bit affine identity.\nThe three ablation rows retain the same coefficient model.\n\nSource & Exact Compilation release\n\nThe sections above retain the history and notices of the earlier resource labs.\nThis release targets the existing public vqcc-banked-clean-staging notebook.\nIts decoder is generated from the newly credited sources below; it does not\nrequire the earlier compiled-decoder dependency or a previous submission ZIP.\n\nA. Gu, A. H. Kemeny, S. F. Yelin and M. D. Lukin: reversible Reed-Solomon\ndecoder, shared-path Berlekamp-Massey recurrence, in-place evaluator,\nhalf-degree Bezout pass, tower-field arithmetic, compressed reversal history,\nand approximation-window policy. Apache License, Version 2.0; the original\nsource notices and separate GU_LICENSE are retained.\nhttps://arxiv.org/abs/2610.22367\nhttps://github.com/andigu/uncompute/tree/64b5a13aa249f1360846657392e6c66817b26d0f\n\nDmitrii Gluzdov: competition-field formula derivation, Kickmix adapter,\nrecord-reading phase sweep and readable source-built portfolio. Apache-2.0.\nAdapted source V3, run 361529794:\nhttps://www.kaggle.com/code/dmitriigluzdov/quantum-circuit-compilation-from-source?scriptVersionId=361529794\nThe separately scored V1, run 361509836, returned 6.12847 for submission\n57567302. V1 and V3 contain identical embedded generator modules.\nhttps://www.kaggle.com/code/dmitriigluzdov/quantum-circuit-compilation-from-source?scriptVersionId=361509836\n\nDmitrii's public FeMoCo numerical input, dataset V2 / source 21143008,\nis published under Apache-2.0. Original factor refinement traces to k256.dev,\nKozykorpesh and Artem1410/anazemcev; the input's provenance credits remain.\nhttps://www.kaggle.com/datasets/dmitriigluzdov/vqcc-femoco-public-factorization/versions/2\nfemoco_public_words.npz SHA-256:\n9afd0ca5e90dd1740fe713e4ac1c26736184ea9bc4d4b57a6eeefafd608ee193\n\nOur added implementations in this release, Apache-2.0:\n- Full-domain arithmetic compiler: exhaustive Boolean truth vectors over the\n  original promised input domain certify five Clifford replacements. The\n  credited coefficient table, phases, measurements and integer model remain.\n- Numerical gauge generator: simultaneous orthogonal transformations of W\n  and H2_I reduce the normalization objective, with a bound on augmented-Gram\n  drift and unchanged angle words under the original physical checks.\n- DQI exact simplification and symbolic scratch-lifetime packing: unregistered\n  wires are reused only after conservative proof of a globally clean state;\n  the placement pass preserves register IDs, gate order and phase corrections.\n  The decoder algorithm and field port remain credited to Gu et al. and\n  Dmitrii Gluzdov. Compiler reports distinguish structural certificates from\n  full official candidate verification.\n\nHistorical Kaggle scores identify their exact upstream or earlier archives.\nNew cost-derived projections are labelled separately; creating an archive\ndoes not submit it to the competition or establish an observed score.\n\nSource & Exact Compilation: deferred arithmetic and phase calibration\n\nDmitrii Gluzdov, source V4 / run361569612: deferred coefficient-register\ndemolition and shared algebraic-normal-form measurement phase repair.\nThe scheduling origin is credited there to the Gaussian circuit of Gu et al.\nOur adaptation keeps the narrower fixed coefficient/carry schedule and its\nexisting normalization, applies the full-domain compiler, and combines the\ntwo coefficient repairs after their measurement phases have commuted through\nthe intervening reversible arithmetic. Apache License, Version2.0.\nhttps://www.kaggle.com/code/dmitriigluzdov/quantum-circuit-compilation-from-source?scriptVersionId=361569612\n\nmizeroluckygall, Quantum Circuits | Rotation Calibration, V3/run361537580:\nfull-input rotation activation collection, cutting-plane linear programming,\nexact integer phase-margin checks and removal of small rotations. That\npublication also credits lightningv08's Memory & Algebra work for exhaustive\nphase calibration. Apache License, Version2.0. Original function bodies and\nsource references are retained beside the adapted portable module.\nOur changes give the routines an explicit circuit API, add a conservative\nsupported-circuit guard, bound matrix-scan memory, retain exact dyadic\ncorrections and require independent phase replay and full official checking.\nThe phase optimization uses the full legal input domain rather than a\nfavorable verifier salt or circuit hash.\nhttps://www.kaggle.com/code/mizeroluckygall/quantum-circuits-rotation-calibration-39-char?scriptVersionId=361537580\nhttps://www.kaggle.com/code/lightningv08/quantum-circuits-memory-algebra\n\n\nSource & Exact Compilation V4: signed-gauge and curvature schedule\n\nKozykorpesh V3/run361677445, Apache2.0:\nhttps://www.kaggle.com/code/kozykappa/quantum-ai-lb-score-6-68108?scriptVersionId=361677445\nGray-curvature checkpoints and reload plans, signed-Givens gauge,\nfour-address difference banks, selective scratch pebbling, symbolic DQI\nlowering, and the source context for the portable adapters used in V4.\nThe attributed Sumit/Rudra/Alex/Kirill/Artem arithmetic lineage is retained.\n\nDmitrii Gluzdov V6/run361592338, Apache2.0:\nhttps://www.kaggle.com/code/dmitriigluzdov/quantum-circuit-compilation-from-source?scriptVersionId=361592338\nCompact inverse-norm schedules, template-word loans and streamed sweep,\nbuilding on the credited Gu decoder and earlier competition-field port.\n\nOur V4 modifications: explicit small-public-input arithmetic adapters;\nfive full-domain Clifford reductions on the new schedule; newly hash-bound\ninteger rotation calibration; small-input signed-vector reconstruction\ncertificate; integration with our orthogonal factor gauge and ANF cleanup;\nfresh full-verifier and complete28-member source/archive receipts.\nNo upstream algorithm is claimed as our invention.\n", encoding='utf-8')
print('LICENSE and NOTICE written beside the reports and submission archive.')

```

## Sources, attribution and reproducibility

- [Competition, official verifiers and rules](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/rules).
- Kozykorpesh, [signed-gauge portfolio V3/run361677445](https://www.kaggle.com/code/kozykappa/quantum-ai-lb-score-6-68108?scriptVersionId=361677445), Apache 2.0. The Gray-curvature checkpoint, Boolean reload plans, signed Givens gauge, four-address banks, selective five-scratch pebbling, and exact symbolic decoder runtime originate there. Its observed score was6.68108, submission57583144. We retain the original notices and identify our changes.
- Dmitrii Gluzdov, [source-built portfolio V6/run361592338](https://www.kaggle.com/code/dmitriigluzdov/quantum-circuit-compilation-from-source?scriptVersionId=361592338), Apache 2.0, for the competition-field port, compact inverse schedules, template loans and streaming sweep. Its observed score was6.35100.
- Gu et al., [paper](https://arxiv.org/abs/2610.22367) and [andigu/uncompute, pinned commit64b5a13](https://github.com/andigu/uncompute/tree/64b5a13aa249f1360846657392e6c66817b26d0f), Apache 2.0. The reversible decoder, field algorithms and approximate support policy are credited there; the separate GU_LICENSE is included.
- Mizero Lucky Gall, [rotation calibration V3/run361537580](https://www.kaggle.com/code/mizeroluckygall/quantum-circuits-rotation-calibration-39-char?scriptVersionId=361537580), Apache 2.0, for the full-input activation collection, cutting-plane LP and integer angle corrections. The source credits lightningv08's [Memory & Algebra](https://www.kaggle.com/code/lightningv08/quantum-circuits-memory-algebra). Our port adds explicit circuit APIs, bounded memory, structural applicability guards and independent phase replay. Mizero's [new V1/run361675142](https://www.kaggle.com/code/mizeroluckygall/quantum-circuits-rotation-calibration?scriptVersionId=361675142) scored6.37294; it is a comparison, not a circuit-binary input.
- Sumit Chongder, [signed-digit arithmetic](https://www.kaggle.com/code/sumitchongder/notebook2f196e646b?scriptVersionId=361357149); Rudra Bhaskar, [derivative split](https://www.kaggle.com/code/rudrabhaskar/highest-public-score-direct-polynomial-phasing?scriptVersionId=361445283); Alex Chilton, [normalization and shifts](https://www.kaggle.com/code/alexchilton/where-the-toffolis-go-anatomy-a-cheaper-invsqrt?scriptVersionId=361472684); Kirill Tymchishin, [schedule integration](https://www.kaggle.com/code/kirilltym/quantum-circuits-qrom-tower42?scriptVersionId=361491814). Their notices remain in the arithmetic modules.
- Dmitrii's [public numerical dataset V2](https://www.kaggle.com/datasets/dmitriigluzdov/vqcc-femoco-public-factorization/versions/2), Apache 2.0, builds on k256.dev, Kozykorpesh and Artem1410's FeMoCo factorization work. Input SHA256 is checked before use.
- Our [separate scored release5.77242](https://www.kaggle.com/code/anazemcev/quantum-circuits-signed-digit-memory?scriptVersionId=361502374) and [previous source V3](https://www.kaggle.com/code/anazemcev/quantum-circuits-source-exact-compilation?scriptVersionId=361586741) document the borrowed carry, promised-input reductions, full-domain compiler, polynomial ANF cleanup, numerical gauge and guarded phase-calibration integration. V4 ports the new public schedules to this small-input source build and combines them with five exact arithmetic reductions and newly bound calibrated angles.
- Gidney, [Halving the cost of quantum addition](https://quantum-journal.org/papers/q-2018-06-18-74/), for temporary ANDs and measurement-based erasure.

The code and changes are Apache2.0; original attribution and license texts are retained. AI assistants helped with research, implementation and review. All inputs are public and every final byte is hashed. The source and reports remain available beside the archive. Default verification is fresh, full and official; a notebook projection is distinct from an observed competition score.

---

## 🔑 Kern-Konzept in 3 Sätzen

Ein Givens-Baum rekonstruiert jeden Orbital-Vektor aus quantisierten Winkeln; ändert man das Gesamtzeichen eines Vektors, bleibt sein Outer-Produkt — und damit die Hamiltonian — unverändert. Dieser signierte Gauge erzwingt, dass Winkel-Bit 9 gleich Bit 8 ist, wodurch jede Differenz zwischen vier Nachbaradressen nur noch 9 statt 10 Bits braucht und vier Adressen in ein Basis-Wort plus drei Difference-Banks passen. Mit fünf Scratch-Wires und selektivem Re-Compute (Pebbling) bleibt jeder der 25 Lookup-Circuits unter der 128Q-Limitierung (je 1129 Toffolis), während ein numerischer Cayley-Gauge die Gram-Matrix erhält und λ_eff weiter senkt.

## 📐 Die Zahlen die zählen

| Parameter | Wert | Bedeutung |
|-----------|------|-----------|
| Input | femoco_public_words.npz (3976×75, brot=10) | öffentlicher numerischer Satz (Apache-2.0), SHA-geprüft |
| (R,B,C) | 65 / 60 / 30 | Faktorisierung des öffentlichen Inputs |
| Signed Gauge | bit9 = bit8 | Gesamt-Vektorzeichen → Outer-Produkt invariant |
| Four-address bank | 1 Basis + 3 Differenzen × 9 Bit | vier Adressen in einem Wort |
| Scratch / Cap | 5 Scratch-Wires / 128Q | Pebbling hält jeden Circuit unter dem Limit |
| Circuits | 25 × 128Q × 1129 Toffolis | je Lookup |
| Total (Modell) | 661 Qubits, 65,244 Toffolis | inkl. State-Prep + Givens-Overhead |
| λ_eff (Estimate) | 47.5585 | mit unveränderten c5-Koeffizienten |
| Full-Verifikation | 254,464 Shots (chem) | offizieller Verifikator, unverändert |
| Vergleich (24.10.2026) | Kozykorpesh V3 6.68108, V3-Projektion 6.280714 | Snapshot vor diesem Release |

## 📝 Lern-Notizen (füll das selbst aus)

- [ ] DF-THC Factorization verstanden: ...
- [ ] (R,B,C) Tabelle nachvollziehbar: ...
- [ ] Loader-Kosten verstanden: ...
- [ ] λ_eff und was es physikalisch bedeutet: ...
- [ ] Verbindung zu invsqrt/DQI: ...
- [ ] Frage die ich noch habe: ...
