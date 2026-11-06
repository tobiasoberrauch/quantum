#!/usr/bin/env python3
"""Qubit-width liveness analysis for kickmix .kmb circuits (DQI Benchmark II).

Question answered: can the declared qubit width (header num_qubits, which is the Q
in the DQI cost R * Q^2 * T) be reduced by re-timing / reusing ancilla lifetimes?

Method (all at the compiled-.kmb level; no builder core required):
  1. Parse the .kmb binary (SOA layout) via mmap + numpy views (zero-copy; the file
     is never loaded fully into RAM beyond page cache).
  2. Per-qubit first-use / last-use op position (worst case: every conditional op
     treated as executing).
  3. Naive live-count sweep: a qubit is live on [first, last]. Peak concurrent
     liveness = minimum number of distinct qubit ids any renumbering can reach
     (interval graphs are perfect; greedy coloring uses exactly the peak).
  4. Refined sweep: lifetimes are split at R / HMR ops (both reset the qubit to
     |0>, ending its state-holding lifetime). Gives the true renumbering lower
     bound.
  5. 20-phase live-count histogram, peak plateau location, INFO_TAG block map.
  6. Working-ancilla (non-syndrome) idle analysis at the peak instant: interval
     length, use density, longest idle gap, Toffoli-like touch count (recompute
     cost proxy).

Usage:
    python3 width_liveness.py <path.kmb> [--json OUT.json] [--phases 20]

Read-only. Exits non-zero with ERROR: ... on malformed input.
"""
from __future__ import annotations

import argparse
import json
import mmap
import os
import struct
import sys
import time

import numpy as np

MAGIC = bytes.fromhex("d750c7d5c329d326e3cc9f6834f2b8bf")
HEADER_SIZE = 104
MAX_IDS = 500_000_000

# --- op type bytes (kickmix_binary_format.md) -------------------------------
OP_HAS_1Q, OP_HAS_2Q, OP_HAS_3Q, OP_HAS_1B, OP_HAS_COND = 0x10, 0x20, 0x30, 0x40, 0x80

TYPE3Q = {0x30: "CCZ", 0xB0: "CCZ_IF", 0x31: "CCX", 0xB1: "CCX_IF",
          0x32: "CSWAP", 0xB2: "CSWAP_IF"}
TYPE2Q = {0x20: "CZ", 0xA0: "CZ_IF", 0x21: "CX", 0xA1: "CX_IF",
          0x22: "SWAP", 0xA2: "SWAP_IF"}
TYPE1Q = {0x10: "Z", 0x90: "Z_IF", 0x11: "X", 0x91: "X_IF",
          0x12: "R", 0x92: "R_IF", 0x13: "Z_POW", 0x93: "Z_POW_IF",
          0x50: "HMR", 0xD0: "HMR_IF"}
TYPE1B = {0x40: "BIT_STORE0", 0xC0: "BIT_STORE0_IF",
          0x41: "BIT_STORE1", 0xC1: "BIT_STORE1_IF",
          0x42: "BIT_INVERT", 0xC2: "BIT_INVERT_IF"}
RESET_TYPES = frozenset((0x12, 0x92, 0x50, 0xD0))   # R, R_IF, HMR, HMR_IF
TOFFOLI_TYPES = frozenset(set(TYPE3Q))              # CCX/CCZ/CSWAP (+_IF)
OP_INFO_TAG = 0x06
# value-modifying ops (change the tracked Z-basis function); phase-only ops on a
# |0> qubit are provably inert (Z|0>=|0>, CZ/CCZ with a |0> leg are identity),
# so value-only liveness is the true renumbering bound.
VALUE_TYPES = frozenset((0x11, 0x91,          # X, X_IF
                         0x21, 0xA1,          # CX, CX_IF
                         0x22, 0xA2,          # SWAP, SWAP_IF
                         0x31, 0xB1,          # CCX, CCX_IF
                         0x32, 0xB2,          # CSWAP, CSWAP_IF
                         0x12, 0x92,          # R, R_IF
                         0x50, 0xD0))         # HMR, HMR_IF


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(2)


def _validate_path(path) -> str:
    """Guard the path argument before any use (None / '' / whitespace / missing)."""
    if path is None or not isinstance(path, str):
        die("kmb path must be a string")
    p = path.strip()
    if not p:
        die("kmb path is empty")
    if not os.path.exists(p):
        die(f"no such file: {p}")
    if not os.path.isfile(p):
        die(f"not a regular file: {p}")
    size = os.path.getsize(p)
    if size < HEADER_SIZE:
        die(f"file too small for kmb header ({size} bytes)")
    return p


class KmbReader:
    """Zero-copy reader for .kmb v2 files (mmap + numpy views)."""

    def __init__(self, path: str):
        self.path = _validate_path(path)
        try:
            self._fh = open(self.path, "rb")
            self.mm = mmap.mmap(self._fh.fileno(), 0, access=mmap.ACCESS_READ)
        except OSError as e:
            die(f"cannot open {self.path}: {e}")
        self.size = len(self.mm)
        self._parse_header()
        self._walk_packets()

    # -- header ---------------------------------------------------------------
    def _parse_header(self) -> None:
        try:
            magic, version, nq, nb, nr = struct.unpack_from("<16sIIII", self.mm, 0)
            (self.num_ops, self.n3q, self.n2q, self.n1q, self.n1b,
             self.ncond, self.nangle, self.ntags, self.ntagchars
             ) = struct.unpack_from("<9Q", self.mm, 32)
        except struct.error as e:
            die(f"truncated/corrupt header: {e}")
        if magic != MAGIC:
            die("bad magic bytes (not a kmb file)")
        if version != 2:
            die(f"unsupported kmb version {version} (expected 2)")
        if nq > MAX_IDS or nb > MAX_IDS:
            die(f"implausible id counts (nq={nq}, nb={nb})")
        self.num_qubits = nq
        self.num_bits = nb
        self.num_registers = nr
        # internal consistency: every op has exactly one target class, except HMR
        # which carries one qubit AND one bit target (counted in n1q and n1b).
        # Hence  -num_ops <= (n3q+n2q+n1q+n1b) - num_ops <= n1b.
        excess = self.n3q + self.n2q + self.n1q + self.n1b - self.num_ops
        if excess < -self.num_ops or excess > self.n1b:
            die(f"target-op counts inconsistent with num_ops (excess={excess})")

    # -- packets --------------------------------------------------------------
    def _walk_packets(self) -> None:
        off = HEADER_SIZE
        plan = (["REGISTER"] * self.num_registers
                + ["TYPES", "Q3A", "Q3B", "Q3C", "Q2A", "Q2B", "Q1",
                   "B1", "BCOND", "ANGLE", "TAGS"])
        expected_type = {"REGISTER": 0, "TYPES": 1, "Q3A": 2, "Q3B": 3, "Q3C": 4,
                         "Q2A": 5, "Q2B": 6, "Q1": 7, "B1": 8, "BCOND": 9,
                         "ANGLE": 10, "TAGS": 11}
        self.registers = {}          # name -> list[int] (qubit ids only, high bit cleared)
        self.types = None
        self.q3a = self.q3b = self.q3c = None
        self.q2a = self.q2b = self.q1 = None
        self.b1 = self.bcond = None
        self.tag_strings = []
        for kind in plan:
            if off + 16 > self.size:
                die(f"truncated packet header while expecting {kind}")
            try:
                ptype, plen = struct.unpack_from("<QQ", self.mm, off)
            except struct.error as e:
                die(f"truncated packet header ({kind}): {e}")
            off += 16
            if off + plen > self.size:
                die(f"truncated payload for {kind} (need {plen}, have {self.size - off})")
            if ptype != expected_type[kind]:
                die(f"packet order violation: expected {kind} (type {expected_type[kind]}), got type {ptype}")
            payload = self.mm[off:off + plen]
            off += plen
            if kind == "REGISTER":
                if plen < 8:
                    die("register payload too short")
                nlen, rlen = struct.unpack_from("<II", payload, 0)
                if 8 + nlen + 4 * rlen != plen:
                    die("register payload length inconsistent")
                name = payload[8:8 + nlen].decode("utf-8", "replace")
                ids = struct.unpack_from(f"<{rlen}I", payload, 8 + nlen) if rlen else ()
                qs = [i & 0x7FFFFFFF for i in ids if i & 0x80000000]
                self.registers[name] = qs
            elif kind == "TYPES":
                if plen != self.num_ops:
                    die(f"types payload {plen} != num_ops {self.num_ops}")
                self.types = np.frombuffer(payload, dtype=np.uint8)
            elif kind in ("Q3A", "Q3B", "Q3C"):
                if plen != 4 * self.n3q:
                    die(f"{kind} payload {plen} != 4*n3q {4 * self.n3q}")
                arr = np.frombuffer(payload, dtype=np.uint32)
                setattr(self, {"Q3A": "q3a", "Q3B": "q3b", "Q3C": "q3c"}[kind], arr)
            elif kind in ("Q2A", "Q2B", "Q1"):
                want = {"Q2A": self.n2q, "Q2B": self.n2q, "Q1": self.n1q}[kind]
                if plen != 4 * want:
                    die(f"{kind} payload {plen} != 4*{want}")
                arr = np.frombuffer(payload, dtype=np.uint32)
                setattr(self, {"Q2A": "q2a", "Q2B": "q2b", "Q1": "q1"}[kind], arr)
            elif kind in ("B1", "BCOND"):
                want = {"B1": self.n1b, "BCOND": self.ncond}[kind]
                if plen != 4 * want:
                    die(f"{kind} payload {plen} != 4*{want}")
                setattr(self, {"B1": "b1", "BCOND": "bcond"}[kind],
                        np.frombuffer(payload, dtype=np.uint32))
            elif kind == "ANGLE":
                if plen != 16 * self.nangle:
                    die(f"angle payload {plen} != 16*nangle {16 * self.nangle}")
            elif kind == "TAGS":
                if plen < 8:
                    die("info-tag payload too short")
                ntags = struct.unpack_from("<Q", payload, 0)[0]
                if ntags != self.ntags:
                    die(f"info-tag count {ntags} != header {self.ntags}")
                if ntagchars := self.ntagchars:
                    if plen != 8 * (ntags + 1) + ntagchars:
                        die("info-tag payload length inconsistent")
                body = payload[8:]
                ends = np.frombuffer(body[:8 * ntags], dtype=np.uint64) if ntags else np.array([], dtype=np.uint64)
                chars = body[8 * ntags:]
                if ntags:
                    if not np.all(ends[:-1] <= ends[1:]) or ends[-1] != ntagchars:
                        die("info-tag end offsets invalid")
                    starts = np.concatenate(([0], ends[:-1]))
                    self.tag_strings = [chars[int(s):int(e)].decode("utf-8", "replace")
                                        for s, e in zip(starts, ends)]
        if off != self.size:
            die(f"{self.size - off} trailing bytes after last packet")

    def close(self) -> None:
        try:
            self.mm.close()
            self._fh.close()
        except Exception:
            pass


# --- analysis ----------------------------------------------------------------

def sha256_of(path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def _lut32(keys) -> np.ndarray:
    lut = np.zeros(256, dtype=bool)
    lut[list(keys)] = True
    return lut


def op_positions(types: np.ndarray, keys) -> np.ndarray:
    """Global op indices whose type byte is in `keys` (ascending int32)."""
    return np.flatnonzero(_lut32(keys)[types]).astype(np.int32)


def first_last_for_array(vals: np.ndarray, pos: np.ndarray, nq: int):
    """Per-qubit (min pos, max pos) for one SOA target array. Returns (first, last)
    int64 arrays of length nq with -1 / +inf sentinels for unused qubits."""
    first = np.full(nq, np.iinfo(np.int64).max, dtype=np.int64)
    last = np.full(nq, -1, dtype=np.int64)
    n = len(vals)
    if n == 0:
        return first, last
    order = np.argsort(vals)                      # unstable: fine for min/max
    sv = vals[order]
    sp = pos[order].astype(np.int64)
    change = np.concatenate(([True], sv[1:] != sv[:-1]))
    starts = np.flatnonzero(change)
    uniq = sv[starts]
    f = np.minimum.reduceat(sp, starts)
    l = np.maximum.reduceat(sp, starts)
    np.minimum.at(first, uniq, f)
    np.maximum.at(last, uniq, l)
    return first, last


def sweep_peak(segments):
    """segments: iterable of (start, end) inclusive op positions.
    Returns (peak, peak_runs, counts) where peak_runs is a list of (lo, hi) op ranges
    attaining the peak, and counts is a list of (lo, hi, c) constant-count runs."""
    ev = {}
    for s, e in segments:
        if e < s:
            continue
        ev[s] = ev.get(s, 0) + 1
        ev[e + 1] = ev.get(e + 1, 0) - 1
    pts = sorted(ev)
    if not pts:
        return 0, [], []
    cur = 0
    peak = 0
    peak_runs = []
    counts = []
    for i, p in enumerate(pts):
        cur += ev[p]
        end = pts[i + 1] - 1 if i + 1 < len(pts) else p
        counts.append((p, end, cur))
        if cur > peak:
            peak = cur
            peak_runs = [(p, end)]
        elif cur == peak:
            peak_runs.append((p, end))
    merged = []
    for a, b in peak_runs:
        if merged and merged[-1][1] + 1 >= a:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    return peak, merged, counts


def live_count_at(counts, p):
    """counts: list of (lo, hi, c) constant-count runs covering the axis."""
    for lo, hi, c in counts:
        if lo <= p <= hi:
            return c
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("kmb", help="path to .kmb circuit file")
    ap.add_argument("--json", dest="json_out", default=None, help="write full results to this JSON path")
    ap.add_argument("--phases", type=int, default=20, help="histogram buckets (default 20)")
    args = ap.parse_args(argv)

    if args.phases is None or args.phases <= 0:
        die("--phases must be a positive integer")
    if args.json_out is not None and not isinstance(args.json_out, str) or \
       (isinstance(args.json_out, str) and not args.json_out.strip()):
        die("--json path must be a non-empty string when given")

    t0 = time.time()
    rd = KmbReader(args.kmb.strip())
    nq, nb, nops = rd.num_qubits, rd.num_bits, rd.num_ops
    print(f"[width] {rd.path}\n[width] header: num_qubits={nq} num_bits={nb} num_ops={nops:,} "
          f"(3q={rd.n3q:,} 2q={rd.n2q:,} 1q={rd.n1q:,} 1b={rd.n1b:,} cond={rd.ncond:,} tags={rd.ntags})",
          file=sys.stderr)

    # ---- validate id ranges & disjoint targets (bulk) ----
    max_qid = 0
    for name, arr in (("q3a", rd.q3a), ("q3b", rd.q3b), ("q3c", rd.q3c),
                      ("q2a", rd.q2a), ("q2b", rd.q2b), ("q1", rd.q1)):
        if arr is not None and len(arr):
            m = int(arr.max())
            if m >= nq:
                die(f"{name}: qubit id {m} out of range (num_qubits={nq})")
            max_qid = max(max_qid, m)
    if rd.b1 is not None and len(rd.b1) and int(rd.b1.max()) >= nb:
        die("b1: bit id out of range")
    if rd.bcond is not None and len(rd.bcond) and int(rd.bcond.max()) >= nb:
        die("bcond: bit id out of range")
    if len(rd.q2a):
        if (rd.q2a == rd.q2b).any():
            die("2-qubit gate with identical targets found")
    if len(rd.q3a):
        if ((rd.q3a == rd.q3b) | (rd.q3a == rd.q3c) | (rd.q3b == rd.q3c)).any():
            die("3-qubit gate with repeated target found")

    # ---- op position tables per target class ----
    pos3 = op_positions(rd.types, set(TYPE3Q))
    pos2 = op_positions(rd.types, set(TYPE2Q))
    pos1 = op_positions(rd.types, set(TYPE1Q))
    if len(pos3) != rd.n3q or len(pos2) != rd.n2q or len(pos1) != rd.n1q:
        die("op-type masks disagree with header target counts")

    # ---- per-qubit first/last (naive, worst case) ----
    first = np.full(nq, np.iinfo(np.int64).max, dtype=np.int64)
    last = np.full(nq, -1, dtype=np.int64)
    for arr, pos in ((rd.q3a, pos3), (rd.q3b, pos3), (rd.q3c, pos3),
                     (rd.q2a, pos2), (rd.q2b, pos2), (rd.q1, pos1)):
        if arr is None or len(arr) == 0:
            continue
        f, l = first_last_for_array(arr, pos, nq)
        m = f != np.iinfo(np.int64).max
        first[m] = np.minimum(first[m], f[m])
        m2 = l >= 0
        last[m2] = np.maximum(last[m2], l[m2])

    unused = np.where(first == np.iinfo(np.int64).max)[0].tolist()
    seg_naive = [(int(first[q]), int(last[q])) for q in range(nq) if first[q] != np.iinfo(np.int64).max]

    peak_naive, runs_naive, counts_naive = sweep_peak(seg_naive)
    print(f"[width] naive peak concurrent live qubits = {peak_naive} "
          f"(declared num_qubits = {nq}; unused ids = {unused if unused else 'none'})",
          file=sys.stderr)

    # ---- refined: split lifetimes at R/HMR ----
    reset_pos = op_positions(rd.types, RESET_TYPES)
    # qubit of each 1-q op:
    local1 = np.searchsorted(pos1, reset_pos)      # index into pos1 (reset ops are 1-q ops)
    reset_q = rd.q1[local1] if len(reset_pos) else np.array([], dtype=np.int32)
    n_qubits_ever_reset = int(len(np.unique(reset_q))) if len(reset_q) else 0
    print(f"[width] R/HMR ops = {len(reset_pos):,}; qubits ever reset = {n_qubits_ever_reset}",
          file=sys.stderr)

    # touches per reset qubit (all six target arrays); kind: 'reset' | 'val' | 'phase'
    touch_sources = ((rd.q3a, pos3), (rd.q3b, pos3), (rd.q3c, pos3),
                     (rd.q2a, pos2), (rd.q2b, pos2), (rd.q1, pos1))
    value_lut = _lut32(VALUE_TYPES)
    reset_lut = _lut32(RESET_TYPES)

    def touches_of(q: int):
        """Sorted list of (pos, kind) for every gate touching qubit q."""
        ts = []
        for arr, pos in touch_sources:
            if arr is None or len(arr) == 0:
                continue
            idx = np.flatnonzero(arr == q)
            if idx.size:
                p = pos[idx]
                t = rd.types[p]
                kind = np.where(reset_lut[t], "reset",
                                np.where(value_lut[t], "val", "phase"))
                ts.extend(zip(p.tolist(), kind.tolist()))
        ts.sort()
        return ts

    seg_refined = []
    seg_value = []
    touches_by_q = {}
    for q in range(nq):
        ts = touches_of(q)
        if not ts:
            continue                      # unused id (shouldn't happen; checked below)
        touches_by_q[q] = ts
        # conservative: every touch counts, split at R/HMR
        cur_start = None
        for p, k in ts:
            if cur_start is None:
                cur_start = p
            if k == "reset":
                seg_refined.append((cur_start, p))
                cur_start = None
        if cur_start is not None:
            seg_refined.append((cur_start, ts[-1][0]))
        # value-only: |0> stretches are inert, split at R/HMR
        cur_start = None
        last_val = None
        for p, k in ts:
            if k == "reset":
                if cur_start is not None:
                    seg_value.append((cur_start, p))
                    cur_start = None
            elif k == "val":
                if cur_start is None:
                    cur_start = p
                last_val = p
        if cur_start is not None and last_val is not None:
            seg_value.append((cur_start, last_val))

    peak_refined, runs_refined, counts_refined = sweep_peak(seg_refined)
    peak_value, runs_value, counts_value = sweep_peak(seg_value)
    print(f"[width] refined peak (lifetimes split at R/HMR) = {peak_refined}", file=sys.stderr)
    print(f"[width] VALUE-only peak (phase-inert |0> sharing allowed) = {peak_value}", file=sys.stderr)

    # ---- phase histogram ----
    ph = []
    for i in range(args.phases):
        lo = nops * i // args.phases
        hi = nops * (i + 1) // args.phases
        mid = (lo + hi - 1) // 2
        ph.append(dict(phase=i, op_lo=int(lo), op_hi=int(hi - 1),
                       frac_lo=round(lo / nops, 4), frac_hi=round((hi - 1) / nops, 4),
                       live_naive=int(live_count_at(counts_naive, mid)),
                       live_refined=int(live_count_at(counts_refined, mid)),
                       live_value=int(live_count_at(counts_value, mid))))

    # ---- peak plateau context ----
    def plateau_ctx(runs, counts):
        out = []
        for (a, b) in runs:
            out.append(dict(op_lo=int(a), op_hi=int(b),
                            frac_lo=round(a / nops, 5), frac_hi=round(b / nops, 5),
                            span=int(b - a + 1)))
        return out

    # ---- syndrome vs working classification ----
    reg_qids = {}
    for name, qs in rd.registers.items():
        for q in qs:
            reg_qids.setdefault(q, []).append(name)
    syndrome_ids = sorted(set(q for q, names in reg_qids.items()
                               if any(n.startswith("S") and n[1:].isdigit() for n in names)))
    working_ids = [q for q in range(nq) if q not in set(syndrome_ids)]
    # empirical cross-check: always-live qubits
    span_all = [(q, int(first[q]), int(last[q])) for q in range(nq)
                if first[q] != np.iinfo(np.int64).max]
    always_live = [q for q, f, l in span_all if f <= nops // args.phases and l >= nops - nops // args.phases]

    # ---- working-ancilla detail at the naive peak ----
    peak_mid = runs_naive[len(runs_naive) // 2]
    pm = (peak_mid[0] + peak_mid[1]) // 2 if peak_mid else 0
    toffoli_lut = _lut32(TOFFOLI_TYPES)
    work_detail = []
    for q in working_ids:
        if first[q] == np.iinfo(np.int64).max:
            continue
        f, l = int(first[q]), int(last[q])
        ts_pairs = touches_by_q.get(q)
        if ts_pairs is None:
            ts_pairs = touches_of(q)
            touches_by_q[q] = ts_pairs
        ts = [p for p, _ in ts_pairs]
        kinds = [k for _, k in ts_pairs]
        n_val = kinds.count("val")
        n_reset = kinds.count("reset")
        n_phase = kinds.count("phase")
        val_pos = [p for p, k in ts_pairs if k in ("val", "reset")]
        first_val = val_pos[0] if val_pos else None
        last_val = val_pos[-1] if val_pos else None
        gaps = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)] if len(ts) > 1 else []
        lg = max(gaps) if gaps else 0
        lg_i = gaps.index(lg) if gaps else -1
        # Toffoli-like touches: positions where this qubit is in a 3-q op
        tpos = []
        for arr, pos in ((rd.q3a, pos3), (rd.q3b, pos3), (rd.q3c, pos3)):
            if arr is None or len(arr) == 0:
                continue
            idx = np.flatnonzero(arr == q)
            if idx.size:
                tpos.extend(pos[idx].tolist())
        work_detail.append(dict(
            qubit=q, first=f, last=l, span=l - f + 1,
            frac_lo=round(f / nops, 5), frac_hi=round(l / nops, 5),
            first_value_touch=int(first_val) if first_val is not None else None,
            last_value_touch=int(last_val) if last_val is not None else None,
            touches=len(ts), value_touches=n_val, reset_touches=n_reset,
            phase_only_touches=n_phase,
            density=round(len(ts) / max(1, l - f + 1), 6),
            longest_gap_ops=int(lg),
            longest_gap_frac=round(lg / nops, 5),
            longest_gap_at=(int(ts[lg_i]), int(ts[lg_i + 1])) if lg_i >= 0 else None,
            peak_in_longest_gap=bool(lg_i >= 0 and ts[lg_i] <= pm <= ts[lg_i + 1]),
            toffoli_touches=len(tpos),
            live_at_peak=bool(f <= pm <= l),
        ))
    work_detail.sort(key=lambda d: (-d["longest_gap_ops"], d["qubit"]))

    # ---- INFO_TAG block map ----
    tag_pos = op_positions(rd.types, (OP_INFO_TAG,))
    tag_blocks = []
    if len(tag_pos) and rd.tag_strings:
        # consecutive runs of identical tag strings
        strs = [rd.tag_strings[i] for i in range(len(tag_pos))]
        i = 0
        while i < len(strs):
            j = i
            while j < len(strs) and strs[j] == strs[i]:
                j += 1
            tag_blocks.append(dict(tag=strs[i], count=j - i,
                                   op_lo=int(tag_pos[i]), op_hi=int(tag_pos[j - 1]),
                                   frac_lo=round(int(tag_pos[i]) / nops, 5),
                                   frac_hi=round(int(tag_pos[j - 1]) / nops, 5)))
            i = j
    # which tag region contains the peak midpoint
    peak_tag = None
    for tb in reversed(tag_blocks):
        if tb["op_lo"] <= pm:
            peak_tag = tb["tag"]
            break

    result = dict(
        path=os.path.abspath(rd.path),
        sha256=sha256_of(rd.path),
        header=dict(num_qubits=nq, num_bits=nb, num_registers=rd.num_registers,
                    num_ops=nops, n3q=rd.n3q, n2q=rd.n2q, n1q=rd.n1q,
                    n1b=rd.n1b, ncond=rd.ncond, ntags=rd.ntags),
        max_qubit_id_used=int(max_qid),
        unused_qubit_ids=unused,
        r_hmr_ops=int(len(reset_pos)),
        qubits_ever_reset=n_qubits_ever_reset,
        peak_naive=peak_naive,
        peak_refined=peak_refined,
        peak_value=peak_value,
        peak_plateau_naive=plateau_ctx(runs_naive, counts_naive),
        peak_plateau_refined=plateau_ctx(runs_refined, counts_refined),
        peak_plateau_value=plateau_ctx(runs_value, counts_value),
        peak_midpoint_op=int(pm),
        peak_midpoint_frac=round(pm / nops, 5),
        peak_info_tag=peak_tag,
        phases=ph,
        classification=dict(
            syndrome_register_count=len([n for n in rd.registers if n.startswith("S") and n[1:].isdigit()]),
            syndrome_ids_min=min(syndrome_ids) if syndrome_ids else None,
            syndrome_ids_max=max(syndrome_ids) if syndrome_ids else None,
            syndrome_ids_count=len(syndrome_ids),
            working_ids=working_ids,
            working_ids_count=len(working_ids),
            always_live_count=len(always_live),
            always_live_are_syndrome=bool(set(always_live) <= set(syndrome_ids)),
        ),
        working_detail=work_detail,
        info_tag_blocks=tag_blocks[:200],
        info_tag_distinct=len({tb["tag"] for tb in tag_blocks}),
        elapsed_s=round(time.time() - t0, 1),
    )

    if args.json_out:
        out = args.json_out.strip()
        d = os.path.dirname(os.path.abspath(out))
        os.makedirs(d, exist_ok=True)
        with open(out, "w") as fh:
            json.dump(result, fh, indent=1)
        print(f"[width] wrote {out}", file=sys.stderr)

    # ---- console summary ----
    print(json.dumps({k: result[k] for k in
                      ("header", "max_qubit_id_used", "unused_qubit_ids",
                       "peak_naive", "peak_refined", "peak_value",
                       "peak_plateau_naive",
                       "peak_midpoint_frac", "peak_info_tag")},
                     indent=1))
    print("\nPhase histogram (live qubits at phase midpoint):")
    print(f"{'ph':>3} {'frac':>12} {'naive':>6} {'refined':>8} {'value':>6}")
    for p in ph:
        bar = "#" * (p["live_naive"] // 20)
        print(f"{p['phase']:>3} {p['frac_lo']:>6.3f}-{p['frac_hi']:<6.3f} {p['live_naive']:>6} {p['live_refined']:>8} {p['live_value']:>6} {bar}")
    c = result["classification"]
    print(f"\nClassification: {c['syndrome_ids_count']} syndrome ids "
          f"[{c['syndrome_ids_min']}..{c['syndrome_ids_max']}], "
          f"{c['working_ids_count']} working ids {c['working_ids']}, "
          f"always-live={c['always_live_count']} (all syndrome: {c['always_live_are_syndrome']})")
    print(f"\nWorking ancillas (sorted by longest idle gap):")
    print(f"{'q':>4} {'first':>9} {'last':>9} {'span':>9} {'frac':>13} {'touch':>6} {'valT':>7} {'rst':>5} {'gap':>9} {'gap@peak':>8} {'toff':>5}")
    for w in work_detail[:60]:
        print(f"{w['qubit']:>4} {w['first']:>9,} {w['last']:>9,} {w['span']:>9,} "
              f"{w['frac_lo']:>6.3f}-{w['frac_hi']:<6.3f} {w['touches']:>6,} {w['value_touches']:>7,} "
              f"{w['reset_touches']:>5,} {w['longest_gap_ops']:>9,} {str(w['peak_in_longest_gap']):>8} {w['toffoli_touches']:>5,}")
    print(f"\nINFO_TAG blocks: {result['info_tag_distinct']} distinct, peak inside: {peak_tag!r}")
    print(f"elapsed {result['elapsed_s']}s")
    rd.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
