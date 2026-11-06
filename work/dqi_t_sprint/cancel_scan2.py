#!/usr/bin/env python3
"""Lever A2 (cheap bound): commuting-separated identical 3-qubit gates.

Two identical self-inverse 3q gates G,G' at p<p' cancel iff no op in (p,p')
touches any of G's 3 qubits. In a dense circuit (≈65k ops/qubit) that requires
a very SHORT gap, so we (1) histogram consecutive same-signature gaps and
(2) do a detailed cleanliness check only for gaps <= GAP_DETAIL.

Read-only. Usage: cancel_scan2.py [path.kmb]
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dqi_sources"))
from width_liveness import KmbReader  # noqa: E402

KMB = sys.argv[1] if len(sys.argv) > 1 else \
    "work/frontier_scan/mwa_unpacked/dqi.kmb"
GAP_DETAIL = 2000


def main():
    rd = KmbReader(KMB)
    t = rd.types
    nops = rd.num_ops

    t3 = np.isin(t, (0x30, 0x31, 0x32))
    pos3 = np.flatnonzero(t3).astype(np.int64)
    n3 = len(pos3)

    ty = t[pos3].astype(np.uint8)
    tcode = (ty - 0x30).astype(np.int64)
    a = rd.q3a.astype(np.int64)
    b = rd.q3b.astype(np.int64)
    c = rd.q3c.astype(np.int64)
    sig = (tcode << 30) | (a << 20) | (b << 10) | c
    qset = np.stack([a, b, c], axis=1)

    # order 3q ops by global position (pos3 already ascending); group by sig
    order = np.argsort(sig, kind="stable")
    s_sorted = sig[order]
    p_sorted = pos3[order]
    q_sorted = qset[order]

    # consecutive same-sig gaps
    same = s_sorted[1:] == s_sorted[:-1]
    gaps = (p_sorted[1:] - p_sorted[:-1])[same]
    # indices (in sorted space) of the left member of each same-sig consecutive pair
    left_idx = np.flatnonzero(same)

    hist = {th: int((gaps <= th).sum()) for th in (50, 100, 500, 1000, 2000, 10000, 100000)}

    # detailed check for gaps <= GAP_DETAIL
    det_mask = gaps <= GAP_DETAIL
    det_left = left_idx[det_mask]
    det_gap = gaps[det_mask]

    # Precompute per-global-op touched qubits ONLY for the small windows we need.
    # Build class position arrays for inverse mapping.
    def class_positions(keys):
        return np.flatnonzero(np.isin(t, keys)).astype(np.int64)
    p3 = class_positions((0x30, 0xB0, 0x31, 0xB1, 0x32, 0xB2))
    p2 = class_positions((0x20, 0xA0, 0x21, 0xA1, 0x22, 0xA2))
    p1 = class_positions((0x10, 0x90, 0x11, 0x91, 0x12, 0x92, 0x13, 0x93, 0x50, 0xD0))
    pbit = class_positions((0x40, 0xC0, 0x41, 0xC1, 0x42, 0xC2))

    def ops_touch_qubits(lo, hi):
        """Set of qubit ids touched by any op with global pos in (lo,hi)."""
        qs = set()
        for pos, arrs in ((p3, (rd.q3a, rd.q3b, rd.q3c)),
                          (p2, (rd.q2a, rd.q2b)),
                          (p1, (rd.q1,))):
            i = np.searchsorted(pos, lo, side="right")
            j = np.searchsorted(pos, hi, side="left")
            if j > i:
                for arr in arrs:
                    qs.update(arr[i:j].tolist())
        return qs

    cancellable = 0
    examples = []
    for li, g in zip(det_left.tolist(), det_gap.tolist()):
        p_lo = int(p_sorted[li])
        p_hi = int(p_sorted[li + 1])
        qs_gate = set(q_sorted[li].tolist())
        mid = ops_touch_qubits(p_lo, p_hi)
        if mid.isdisjoint(qs_gate):
            cancellable += 1
            if len(examples) < 10:
                examples.append(dict(sig=int(s_sorted[li]), p_lo=p_lo,
                                     p_hi=p_hi, gap=int(g), qset=sorted(qs_gate)))

    out = dict(
        path=os.path.abspath(rd.path), n3q=n3,
        total_consecutive_same_sig_pairs=int(same.sum()),
        gap_hist_le=hist,
        detail_checked=int(len(det_left)),
        commuting_separated_cancellable_pairs=cancellable,
        frac_of_T=round(cancellable / n3, 5),
        examples=examples,
    )
    print(json.dumps(out, indent=1))
    rd.close()


if __name__ == "__main__":
    main()
