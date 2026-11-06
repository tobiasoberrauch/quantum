#!/usr/bin/env python3
"""Build the RAW constant-seed (pwq3) invsqrt circuit for Benchmark I.

Implements the independently-verified numerical model in
``work/invsqrt_constseed_model.py`` (``constseed_error``, ``seed_mode='pwq3'``,
``n1_frac=16, n2_guard=24, out_frac=26``) as a kickmix circuit, following the
official reference builder idioms in
``data/verifiers/invsqrt/nr_reference_circuit.py``.

Pipeline (integer truncation matching the model; worst err/tol 0.5577 exact /
0.5139 with the column cutoffs below):
  1. normalize: x -> x_norm = x << (2s), flags = unary s.
  2. seed (pwq3): k = 7 address bits (interval-muxed bit-slice of x_norm);
     cubic in kk=k/128 evaluated at AB=18 internal bits via magnitude+subtraction
     Horner; S = top 8 bits (units of 2^-8).
  3. Newton #1 (n1=16): Q1=(x_norm*S*S)>>20; C1=3*2^16-Q1; P1=(S*C1)>>8.
  4. Newton #2 (g=26): sq2=P1*P1; Q2=(x_norm*sq2)>>28; C2=((3*2^26)-Q2)>>1;
     P2=(P1*C2)>>16   [== (P1<<10 * C2)>>26, folded].
  5. denormalize: y1=P2<<s (F=37 bits); phase y1/2^37 turns.

Column-truncated multipliers keep product columns >= L (L chosen per multiply so
the dropped low columns carry < half an LSB at the model width -- see
find_cutoffs.py); the result is a slice of a transient product register.
Uncomputed in reverse (measurement-based HMR) so x is restored and every
scratch qubit returns to |0>.
"""
from __future__ import annotations

import os
import sys

import kickmix as km
import numpy as np
from fractions import Fraction

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from invsqrt_constseed_model import _PWQ3_COEFS, N_P, WIDTH, MAX_X  # noqa: E402

# ---------------------------------------------------------------------------
# Widths (fixed by the validated model spec) + column cutoffs (find_cutoffs.py)
# ---------------------------------------------------------------------------
AB = 18          # internal fractional bits for the seed cubic
SF = 8           # seed fractional bits
N1 = 16          # Newton #1 fractional bits
G = 26           # Newton #2 fractional bits (n2_guard + 2)
OUT = 26         # output fractional bits
F = OUT + N_P + 1  # 37 phase-register bits

# Per-multiply column cutoffs: (shift, L, W) with W = shift + out_bits - L.
# Q1=(xn*SS)>>20, P1=(S*C1)>>8, Q2=(xn*sq2)>>28, P2=(P1*C2)>>16.
Q1_SH, Q1_L, Q1_W = 20, 3, 34
P1_SH, P1_L, P1_W = 8, 1, 24
Q2_SH, Q2_L, Q2_W = 28, 26, 29
P2_SH, P2_L, P2_W = 16, 12, 31
SQ2_W = 2 * (N1 + 1)          # 34 (full P1^2)
SS_W = 2 * SF                 # 16 (full S^2)
PROD_W = max(Q1_W, P1_W, Q2_W, P2_W, SQ2_W)  # 34 transient pool

# Coefficient MAGNITUDES per interval, units of 2^-AB.
# Model cubic seed = a + b*kk + c*kk^2 + d*kk^3 (a,c>0, b,d<0).
# Circuit (all-positive multiplies + subtraction):
#   td=Dm*kk; r2=C-td; tr2=r2*kk; r1=Bm-tr2; tr1=r1*kk; r0=A-tr1  (== seed)
COEFS = []
for (a, b, c, d) in _PWQ3_COEFS:
    COEFS.append({
        'A': int(round(a * 2**AB)),
        'B': int(round(-b * 2**AB)),
        'C': int(round(c * 2**AB)),
        'D': int(round(-d * 2**AB)),
    })


def _seed_S(inter: int, k: int) -> int:
    """Exact circuit integer arithmetic for one (interval, k): S = top8(r0), 8 bits.

    Mirrors _mul_kk ((X*k)>>7) + magnitude/subtraction Horner on AB-bit registers, so the
    ROM values are bit-identical to what the Horner workspace used to emit (verified: 0
    mismatches vs the model over all x, and S depends on (inter,k), not k alone).
    """
    A, B, C, D = (COEFS[inter][n] for n in 'ABCD')
    m = (1 << AB) - 1
    td = (D * k) >> 7
    r2 = (C - td) & m
    tr2 = (r2 * k) >> 7
    r1 = (B - tr2) & m
    tr1 = (r1 * k) >> 7
    r0 = (A - tr1) & m
    return r0 >> (AB - SF)


# 512-entry seed ROM: index = inter*128 + k, inter = 2*top + (t_a ^ t_b) in {0,1,2,3}.
ROM_TABLE = [_seed_S(i, k) for i in range(4) for k in range(128)]


# ---------------------------------------------------------------------------
# Low-level helpers (adapted from nr_reference_circuit.py)
# ---------------------------------------------------------------------------
def _add_row(builder, inverse, control, terms, target, scratch, subtract=False):
    """target += control * sum(2^index source) (or -= when subtract!=inverse)."""
    sources = km.array([q for q, _ in terms])
    products = km.array([scratch[i] for _, i in terms])
    low = min(i for _, i in terms)
    builder.init_and(control, sources, products)
    if subtract != inverse:
        builder.isub(scratch[low:len(target)], target=target[low:])
    else:
        builder.iadd(scratch[low:len(target)], target=target[low:])
    builder.del_and(control, sources, products)


def _mul_kk(builder, inverse, X, k, out, scratch):
    """out = (X * k) >> 7 ; X `len(X)` bits, k 7 bits, out `len(out)` bits."""
    n, m = len(X), len(out)
    for j in range(7):
        lo = max(0, 7 - j)
        hi = min(n, m + 7 - j)
        terms = [(X[i], i + j - 7) for i in range(lo, hi)]
        if terms:
            _add_row(builder, inverse, k[j], terms, out, scratch)


def _mul(builder, inverse, A, B, sh, L, result, prod, scratch):
    """result ^= ((A*B)>>sh); `prod` (width W=len(prod)) holds A*B cols>=L.

    Forward builds `prod` then XORs the slice into `result`; inverse XORs the
    slice out (clearing `result`) then subtracts to clear `prod`. `prod` must
    persist between the forward and inverse calls.
    """
    na, nb, W = len(A), len(B), len(prod)
    off = sh - L

    def rows(inv):
        for i in range(na):
            lo = max(0, L - i)
            hi = min(nb, L + W - i)
            terms = [(B[j], i + j - L) for j in range(lo, hi)]
            if terms:
                _add_row(builder, inv, A[i], terms, prod, scratch)

    if not inverse:
        rows(False)
        builder.cx(prod[off:off + len(result)], result)
    else:
        builder.cx(prod[off:off + len(result)], result)
        rows(True)


def _mul_transient(builder, A, B, sh, L, result, pool, scratch):
    """result ^= ((A*B)>>sh); `pool` (|0> in and out) holds A*B cols>=L transiently.

    Builds `pool`, XORs the slice into `result`, then clears `pool` -- all in ONE call, so
    `pool` need not persist between the forward and inverse multiplies. The slice CNOT is
    self-inverse and the product is rebuilt identically each call, so the SAME body is used
    forward (adds the slice) and inverse (removes it). Costs 2x the row-adds of `_mul`
    (build+clear per call) but frees the product register for reuse.
    """
    na, nb, W = len(A), len(B), len(pool)
    off = sh - L

    def rows(inv):
        for i in range(na):
            lo = max(0, L - i)
            hi = min(nb, L + W - i)
            terms = [(B[j], i + j - L) for j in range(lo, hi)]
            if terms:
                _add_row(builder, inv, A[i], terms, pool, scratch)

    rows(False)
    builder.cx(pool[off:off + len(result)], result)
    rows(True)


def _square_int(builder, inverse, X, sq, scratch):
    """sq = X * X (exact, all bits below len(sq)). Diagonal CNOT, doubled cross."""
    n = len(X)
    diag = [i for i in range(n) if 2 * i < len(sq)]
    controls = km.array([X[i] for i in diag])
    targets = km.array([sq[2 * i] for i in diag])
    if not inverse:
        builder.cx(controls, targets)
    for i in range(n):
        terms = [(X[j], i + j + 1) for j in range(i + 1, n) if i + j + 1 < len(sq)]
        if terms:
            _add_row(builder, inverse, X[i], terms, sq, scratch)
    if inverse:
        builder.cx(controls, targets)


def _sub_into(builder, inverse, src, dst):
    """dst -= src (forward) / dst += src (inverse)."""
    if inverse:
        builder.iadd(src, target=dst)
    else:
        builder.isub(src, target=dst)


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------
def _flag_zero_pair(builder, inverse, x, flag):
    top_pair = x[-2:]
    builder.x(top_pair)
    if inverse:
        builder.del_and(top_pair[0], top_pair[1], flag)
    else:
        builder.init_and(top_pair[0], top_pair[1], flag)
    builder.x(top_pair)


def _normalize(builder, inverse, x, flags):
    for kk in (reversed(range(len(flags))) if inverse else range(len(flags))):
        lanes = (x[2 * kk::2], x[2 * kk + 1::2])
        if inverse:
            for lane in lanes:
                builder.right_rotate(lane, 1, control=flags[kk])
            _flag_zero_pair(builder, inverse, x, flags[kk])
        else:
            _flag_zero_pair(builder, inverse, x, flags[kk])
            for lane in lanes:
                builder.left_rotate(lane, 1, control=flags[kk])


def _select(builder, inverse, x, sel):
    """sel[0]=t_a=!top&third, sel[1]=t_b=top&second."""
    top, second, third = x[WIDTH - 1], x[WIDTH - 2], x[WIDTH - 3]
    if inverse:
        builder.del_and(top, second, sel[1])
        builder.x(top)
        builder.del_and(top, third, sel[0])
        builder.x(top)
    else:
        builder.x(top)
        builder.init_and(top, third, sel[0])
        builder.x(top)
        builder.init_and(top, second, sel[1])


def _load_coefs(builder, x, sel, coefs):
    """Self-inverse Clifford load of the selected interval's magnitudes."""
    top = x[WIDTH - 1]
    ta, tb = sel[0], sel[1]
    for name, reg in zip(('A', 'B', 'C', 'D'), coefs):
        t0, t1, t2, t3 = (COEFS[i][name] for i in range(4))
        builder.gf2_iadd(t0, target=reg, control=True)
        builder.gf2_iadd(t0 ^ t2, target=reg, control=top)
        builder.gf2_iadd(t0 ^ t1, target=reg, control=ta)
        builder.gf2_iadd(t2 ^ t3, target=reg, control=tb)


def _build_k(builder, x, k, d, prod):
    """Self-inverse interval-muxed address: k_j = x[12+j]^(top&(x[12+j]^x[13+j]))."""
    top = x[WIDTH - 1]
    for j in range(7):
        lo, hi = x[12 + j], x[13 + j]
        builder.cx(lo, d)
        builder.cx(hi, d)                 # d = lo ^ hi
        builder.cx(lo, k[j])              # k[j] = lo
        builder.init_and(top, d, prod)    # prod = top & d
        builder.cx(prod, k[j])            # k[j] = lo ^ (top & d)
        builder.del_and(top, d, prod)
        builder.cx(lo, d)
        builder.cx(hi, d)                 # d -> |0>


def _seed_compute(builder, inverse, coefs, k, temps, scratch):
    """Evaluate the seed cubic chain (magnitude+subtraction Horner). coefs=[A,B,C,D].

    Forward leaves coefs holding (r0, r1, r2, D) and temps holding (td, tr2, tr1);
    inverse restores coefs to their originals and clears temps. Neither touches S --
    the caller extracts S = top 8 bits of r0 (=coefs[0]) with a self-inverse CNOT so
    it can undo the workspace while keeping the seed.
    """
    A, B, C, D = coefs
    td, tr2, tr1 = temps
    if not inverse:
        _mul_kk(builder, False, D, k, td, scratch)      # td = (D*k)>>7
        _sub_into(builder, False, td, C)                # C  = r2 = C - td
        _mul_kk(builder, False, C, k, tr2, scratch)     # tr2 = (r2*k)>>7
        _sub_into(builder, False, tr2, B)               # B  = r1 = B - tr2
        _mul_kk(builder, False, B, k, tr1, scratch)     # tr1 = (r1*k)>>7
        _sub_into(builder, False, tr1, A)               # A  = r0 = A - tr1
    else:
        _sub_into(builder, True, tr1, A)                # A += tr1 -> A_orig
        _mul_kk(builder, True, B, k, tr1, scratch)      # clear tr1
        _sub_into(builder, True, tr2, B)                # B += tr2 -> B_orig
        _mul_kk(builder, True, C, k, tr2, scratch)      # clear tr2
        _sub_into(builder, True, td, C)                 # C += td  -> C_orig
        _mul_kk(builder, True, D, k, td, scratch)       # clear td


def _newton1(builder, inverse, x, S, SS, C1reg, P1, prod_q1, prod_p1, scratch):
    """SS=S^2; Q1=(x*SS)>>20 (into C1reg[:17]); C1=3*2^16-Q1 (in place); P1=(S*C1)>>8."""
    if not inverse:
        _square_int(builder, False, S, SS, scratch)
        _mul(builder, False, x, SS, Q1_SH, Q1_L, C1reg[:17], prod_q1, scratch)
        builder.x(C1reg)
        builder.iadd((3 << N1) + 1, target=C1reg)       # C1reg = C1
        _mul(builder, False, S, C1reg, P1_SH, P1_L, P1, prod_p1, scratch)
    else:
        _mul(builder, True, S, C1reg, P1_SH, P1_L, P1, prod_p1, scratch)
        builder.isub((3 << N1) + 1, target=C1reg)
        builder.x(C1reg)                                # C1reg = Q1
        _mul(builder, True, x, SS, Q1_SH, Q1_L, C1reg[:17], prod_q1, scratch)
        _square_int(builder, True, S, SS, scratch)


def _newton1_transient(builder, inverse, x, S, SS, C1reg, P1, pool, scratch):
    """_newton1 with transient multiplies into a shared `pool` (|0> in and out), so the
    product register need not persist across Newton #2. Identical numerics to _newton1."""
    if not inverse:
        _square_int(builder, False, S, SS, scratch)
        _mul_transient(builder, x, SS, Q1_SH, Q1_L, C1reg[:17], pool, scratch)
        builder.x(C1reg)
        builder.iadd((3 << N1) + 1, target=C1reg)       # C1reg = C1
        _mul_transient(builder, S, C1reg, P1_SH, P1_L, P1, pool, scratch)
    else:
        _mul_transient(builder, S, C1reg, P1_SH, P1_L, P1, pool, scratch)
        builder.isub((3 << N1) + 1, target=C1reg)
        builder.x(C1reg)                                # C1reg = Q1
        _mul_transient(builder, x, SS, Q1_SH, Q1_L, C1reg[:17], pool, scratch)
        _square_int(builder, True, S, SS, scratch)


def _newton2(builder, inverse, x, P1, y1, sq2, C2reg, prod_q2, prod_p2, scratch):
    """sq2=P1^2; Q2=(x*sq2)>>28 (into C2reg[:27]); C2=((3*2^26)-Q2)>>1 (in place);
    P2=(P1*C2)>>16 -> y1[:27]."""
    p2 = y1[:OUT + 1]  # 27 bits
    if not inverse:
        _square_int(builder, False, P1, sq2, scratch)
        _mul(builder, False, x, sq2, Q2_SH, Q2_L, C2reg[:27], prod_q2, scratch)
        builder.x(C2reg)
        builder.iadd((3 << G) + 1, target=C2reg)        # C2reg = T = 3*2^26 - Q2
        _mul(builder, False, P1, C2reg[1:], P2_SH, P2_L, p2, prod_p2, scratch)
    else:
        _mul(builder, True, P1, C2reg[1:], P2_SH, P2_L, p2, prod_p2, scratch)
        builder.isub((3 << G) + 1, target=C2reg)
        builder.x(C2reg)                                # C2reg = Q2
        _mul(builder, True, x, sq2, Q2_SH, Q2_L, C2reg[:27], prod_q2, scratch)
        _square_int(builder, True, P1, sq2, scratch)


def _denormalize(builder, inverse, flags, y1):
    wp = len(y1) - len(flags) - 1
    for kk in (reversed(range(len(flags))) if inverse else range(len(flags))):
        lane = y1[kk:kk + wp + 2]
        if inverse:
            builder.right_rotate(lane, 1, control=flags[kk])
        else:
            builder.left_rotate(lane, 1, control=flags[kk])


def _phase_by_bits(builder, y):
    f = len(y)
    with builder.mark('phase_by_bits'):
        for j in range(f):
            builder.z_pow(y[j], Fraction(2) ** (j - f + 1))


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def build() -> km.Circuit:
    """Forward/reverse mirror. Every register is allocated once and freed once; the
    seed workspace (coefs/temps/k/sel/S) and the four persistent product registers all
    stay live across the Newton block, which sets the peak-qubit count.

    NOTE (why the seed workspace cannot be freed before Newton): S = top8(r0) is cleared
    phase-safely only by the self-inverse CNOT ``cx(coefs[0][AB-SF:], S)`` while coefs[0]
    still holds r0. Restoring B,C (so they could be freed early) runs ``_seed_compute``
    inverse, which mutates coefs[0] away from r0 -- so the whole seed workspace must span
    Newton. A ``builder.reset(S)`` shortcut was tried and REJECTED: kickmix's ``R`` op
    injects a data-dependent half-turn (``phase ^= qubit & rng``, sim.h) that a bare reset
    cannot cancel the way ``del_and``'s HMR+CZ pair does, corrupting the tracked phase.
    """
    builder = km.CircuitBuilder()
    x = builder.create_quantum_register(WIDTH, name='x')
    flags = builder.alloc_qubits(N_P)                       # 10
    scratch = builder.alloc_qubits(PROD_W)                  # 34 (shared AND pool, persists)

    # ================= forward: normalize + seed (lookup-table QROM) =================
    _normalize(builder, False, x, flags)
    sel = builder.alloc_qubits(2)                           # t_a, t_b (interval selectors)
    k = builder.alloc_qubits(7)                             # interval-muxed 7-bit sub-address
    S = builder.alloc_qubits(SF)                            # 8-bit seed (persists to N1-inverse)
    inter_low = builder.alloc_qubits(1)[0]                  # inter_low = t_a ^ t_b
    _select(builder, False, x, sel)
    _build_k(builder, x, k, scratch[0], scratch[1])
    builder.cx(sel[0], inter_low)
    builder.cx(sel[1], inter_low)                           # inter_low = t_a ^ t_b
    address = km.array([*k, inter_low, x[WIDTH - 1]])       # addr = inter*128 + k (9 bits)
    builder.init_lookup(table=ROM_TABLE, address=address, target=S)   # S = ROM[addr]

    # ================= forward: Newton (persistent product registers) =================
    SS = builder.alloc_qubits(SS_W)                         # 16
    C1reg = builder.alloc_qubits(N1 + 2)                    # 18 (Q1 then C1)
    P1 = builder.alloc_qubits(N1 + 1)                       # 17
    prod_q1 = builder.alloc_qubits(Q1_W)                    # 34 (x*SS cols>=L)
    prod_p1 = builder.alloc_qubits(P1_W)                    # 24 (S*C1 cols>=L)
    y1 = builder.alloc_qubits(F)                            # 37 (P2 = y1[:27])
    sq2 = builder.alloc_qubits(SQ2_W)                       # 34
    C2reg = builder.alloc_qubits(G + 2)                     # 28 (Q2 then T/C2)
    prod_q2 = builder.alloc_qubits(Q2_W)                    # 29 (x*sq2 cols>=L)
    prod_p2 = builder.alloc_qubits(P2_W)                    # 31 (P1*C2 cols>=L)
    _newton1(builder, False, x, S, SS, C1reg, P1, prod_q1, prod_p1, scratch)
    _newton2(builder, False, x, P1, y1, sq2, C2reg, prod_q2, prod_p2, scratch)
    _denormalize(builder, False, flags, y1)
    _phase_by_bits(builder, y1)

    # ================= uncompute (exact reverse) =================
    _denormalize(builder, True, flags, y1)
    _newton2(builder, True, x, P1, y1, sq2, C2reg, prod_q2, prod_p2, scratch)
    _newton1(builder, True, x, S, SS, C1reg, P1, prod_q1, prod_p1, scratch)
    builder.del_lookup(table=ROM_TABLE, address=address, target=S)   # clear S (phase-safe)
    builder.cx(sel[0], inter_low)
    builder.cx(sel[1], inter_low)                           # clear inter_low -> |0>
    builder.free(inter_low)
    _build_k(builder, x, k, scratch[0], scratch[1])  # self-inverse -> clears k
    _select(builder, True, x, sel)           # clears sel
    _normalize(builder, True, x, flags)

    for r in (flags, sel, k, S, SS, C1reg, P1, prod_q1, prod_p1,
              y1, sq2, C2reg, prod_q2, prod_p2, scratch):
        builder.free(r)
    return builder.finish_circuit()


def build_hybrid() -> km.Circuit:
    """Lookup seed + hybrid Newton. Newton #1 multiplies are transient (a per-phase product
    pool, freed between the two Newtons); Newton #2 stays persistent; Newton #2's registers
    are freed before Newton #1-inverse so they never overlap the pool. This removes Newton #1's
    two persistent product registers (58 qubits) from the Newton #2 peak -> Q < 350 at a modest
    CCX cost (Newton #1 multiplies go 2x -> 4x row-adds)."""
    builder = km.CircuitBuilder()
    x = builder.create_quantum_register(WIDTH, name='x')
    flags = builder.alloc_qubits(N_P)                       # 10
    scratch = builder.alloc_qubits(PROD_W)                  # 34 (shared AND pool, persists)

    # ================= forward: normalize + lookup seed =================
    _normalize(builder, False, x, flags)
    sel = builder.alloc_qubits(2)
    k = builder.alloc_qubits(7)
    S = builder.alloc_qubits(SF)                            # persists to N1-inverse
    inter_low = builder.alloc_qubits(1)[0]
    _select(builder, False, x, sel)
    _build_k(builder, x, k, scratch[0], scratch[1])
    builder.cx(sel[0], inter_low)
    builder.cx(sel[1], inter_low)                           # inter_low = t_a ^ t_b
    address = km.array([*k, inter_low, x[WIDTH - 1]])       # addr = inter*128 + k
    builder.init_lookup(table=ROM_TABLE, address=address, target=S)

    # ================= forward: Newton #1 (transient pool) =================
    SS = builder.alloc_qubits(SS_W)                         # 16
    C1reg = builder.alloc_qubits(N1 + 2)                    # 18
    P1 = builder.alloc_qubits(N1 + 1)                       # 17
    pool_f = builder.alloc_qubits(max(Q1_W, P1_W))          # 34 transient product pool
    _newton1_transient(builder, False, x, S, SS, C1reg, P1, pool_f, scratch)
    builder.free(pool_f)                                    # freed before Newton #2

    # ================= forward: Newton #2 (persistent products) =================
    y1 = builder.alloc_qubits(F)                            # 37
    sq2 = builder.alloc_qubits(SQ2_W)                       # 34
    C2reg = builder.alloc_qubits(G + 2)                     # 28
    prod_q2 = builder.alloc_qubits(Q2_W)                    # 29
    prod_p2 = builder.alloc_qubits(P2_W)                    # 31
    _newton2(builder, False, x, P1, y1, sq2, C2reg, prod_q2, prod_p2, scratch)
    _denormalize(builder, False, flags, y1)
    _phase_by_bits(builder, y1)

    # ================= uncompute (reverse) =================
    _denormalize(builder, True, flags, y1)
    _newton2(builder, True, x, P1, y1, sq2, C2reg, prod_q2, prod_p2, scratch)
    # Free Newton #2 registers BEFORE Newton #1-inverse so they don't overlap the pool.
    builder.free(y1)
    builder.free(sq2)
    builder.free(C2reg)
    builder.free(prod_q2)
    builder.free(prod_p2)
    pool_i = builder.alloc_qubits(max(Q1_W, P1_W))          # reuses freed qubits
    _newton1_transient(builder, True, x, S, SS, C1reg, P1, pool_i, scratch)
    builder.free(pool_i)
    builder.del_lookup(table=ROM_TABLE, address=address, target=S)   # clear S (phase-safe)
    builder.cx(sel[0], inter_low)
    builder.cx(sel[1], inter_low)                           # clear inter_low -> |0>
    builder.free(inter_low)
    _build_k(builder, x, k, scratch[0], scratch[1])  # self-inverse -> clears k
    _select(builder, True, x, sel)           # clears sel
    _normalize(builder, True, x, flags)

    for r in (flags, sel, k, S, SS, C1reg, P1, scratch):
        builder.free(r)
    return builder.finish_circuit()


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('output', nargs='?', default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'invsqrt_constseed.kmb'))
    ap.add_argument('--hybrid', action='store_true',
                    help='build the hybrid (Newton#1 transient) variant instead of all-persistent')
    args = ap.parse_args()
    circuit = build_hybrid() if args.hybrid else build()
    circuit.to_file(args.output, format='kmb')
    st = circuit.operation_statistics()
    print(f'wrote {args.output}')
    print(f'  num_qubits={circuit.num_qubits}  static_CCX={st.num_toffoli_like}  '
          f'T={st.num_t_like}  rot(h4+)={st.num_z_pow(min_clifford_hierarchy_level=4)}  '
          f'ops={len(circuit)}  depth={circuit.reaction_depth()}')


if __name__ == '__main__':
    main()
