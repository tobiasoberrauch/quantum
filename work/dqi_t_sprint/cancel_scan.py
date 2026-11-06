#!/usr/bin/env python3
"""Scan the DQI .kmb for safe local Toffoli cancellations / caching ceilings.

Lever A: strictly-adjacent identical 3-qubit gates (CCX/CCZ/CSWAP are all
         self-inverse) -> g g = I, delete both. Trivially safe.
Lever B: repeated-signature ceiling = sum over distinct sigs of (count-1).
         Upper bound on product-caching savings (needs free wires to realize).
Per-block (INFO_TAG region) breakdown of A and B.

Read-only. Usage: cancel_scan.py [path.kmb]
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dqi_sources"))
from width_liveness import KmbReader, OP_INFO_TAG  # noqa: E402

KMB = sys.argv[1] if len(sys.argv) > 1 else \
    "work/frontier_scan/mwa_unpacked/dqi.kmb"
BLOCKS = os.path.join(os.path.dirname(__file__), "block_analysis.json")


def main():
    rd = KmbReader(KMB)
    t = rd.types
    nops = rd.num_ops

    # global positions of every 3q op
    t3 = np.isin(t, (0x30, 0x31, 0x32))
    pos3 = np.flatnonzero(t3).astype(np.int64)
    n3 = len(pos3)
    assert n3 == rd.n3q, (n3, rd.n3q)

    # signature = type(2 bits) | a<<2 | ... ; pack into int64
    ty = t[pos3].astype(np.uint8)              # 0x30/0x31/0x32
    tcode = (ty - 0x30).astype(np.int64)       # 0=CCZ 1=CCX 2=CSWAP
    a = rd.q3a.astype(np.int64)
    b = rd.q3b.astype(np.int64)
    c = rd.q3c.astype(np.int64)
    sig = (tcode << 30) | (a << 20) | (b << 10) | c

    # ---- Lever A: strictly adjacent identical pairs ----
    gap = pos3[1:] - pos3[:-1]
    adj = (gap == 1) & (sig[1:] == sig[:-1])
    n_adj = int(adj.sum())
    adj_pos = pos3[:-1][adj]

    # ---- Lever B: repeated-signature ceiling ----
    uniq, inv, cnt = np.unique(sig, return_inverse=True, return_counts=True)
    repeats = int((cnt - 1).sum())             # sum(count-1) over all sigs
    multi = int((cnt > 1).sum())               # distinct sigs appearing >=2
    maxc = int(cnt.max())

    # ---- block map ----
    blocks = {}
    if os.path.exists(BLOCKS):
        with open(BLOCKS) as fh:
            blocks = {k: v for k, v in json.load(fh).items()}

    def block_of(p):
        for name, bl in blocks.items():
            if bl["lo"] <= p <= bl["hi"]:
                return name
        return "<none>"

    # per-block Lever A
    adj_blk = {}
    for p in adj_pos.tolist():
        k = block_of(int(p))
        adj_blk[k] = adj_blk.get(k, 0) + 1

    # per-block Lever B: assign each 3q op to a block, count sig repeats within block
    blk_of_op = np.array([block_of(int(p)) for p in pos3.tolist()], dtype=object)
    blk_b = {}
    for s, bl in zip(sig.tolist(), blk_of_op):
        blk_b[(bl, s)] = blk_b.get((bl, s), 0) + 1
    blk_repeat = {}
    for (bl, s), ct in blk_b.items():
        blk_repeat[bl] = blk_repeat.get(bl, 0) + (ct - 1)

    out = dict(
        path=os.path.abspath(rd.path),
        num_ops=nops, n3q=n3,
        leverA_adj_identical_pairs=n_adj,
        leverA_by_block=adj_blk,
        leverB_repeat_ceiling=repeats,
        leverB_distinct_sigs=len(uniq),
        leverB_multi_sigs=multi,
        leverB_max_count=maxc,
        leverB_by_block=blk_repeat,
    )
    print(json.dumps(out, indent=1))
    rd.close()


if __name__ == "__main__":
    main()
