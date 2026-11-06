#!/usr/bin/env python3
"""List every distinct INFO_TAG label in the target .kmb with occurrence count,
op-range, and 3q (Toffoli-like) count, so we can map the named blocks to builder
functions. Reuses KmbReader from work/dqi_sources/width_liveness.py.

Read-only. Writes one JSON under work/dqi_builder_recon/. Guards params.
"""
from __future__ import annotations
import json
import os
import sys
from collections import OrderedDict


def _guard(path):
    if path is None or not isinstance(path, str) or not path.strip():
        raise SystemExit("ERROR: kmb path must be a non-empty string")
    p = path.strip()
    if not os.path.isfile(p):
        raise SystemExit(f"ERROR: no such file: {p}")
    return p


def main(kmb_path, out_path):
    kmb_path = _guard(kmb_path)
    if out_path is None or not isinstance(out_path, str) or not out_path.strip():
        raise SystemExit("ERROR: out_path must be a non-empty string")
    out_path = out_path.strip()

    sys.path.insert(0, os.path.abspath("work/dqi_sources"))
    from width_liveness import KmbReader, OP_INFO_TAG, TOFFOLI_TYPES  # noqa: E402
    import numpy as np  # noqa: E402

    rd = KmbReader(kmb_path)
    types = rd.types
    nops = rd.num_ops

    lut_tag = np.zeros(256, dtype=bool); lut_tag[OP_INFO_TAG] = True
    tag_pos = np.flatnonzero(lut_tag[types]).astype(np.int64)
    lut3 = np.zeros(256, dtype=bool); lut3[list(TOFFOLI_TYPES)] = True
    pos3 = np.flatnonzero(lut3[types]).astype(np.int64)

    agg = OrderedDict()
    for idx, s in enumerate(rd.tag_strings[:len(tag_pos)]):
        # @enter: is 7 chars, @exit: is 6 chars; strip the correct prefix.
        if s.startswith("@enter:"):
            label = s[7:]
        elif s.startswith("@exit:"):
            label = s[6:]
        else:
            label = s
        e = agg.setdefault(label, dict(occurrences=0, op_lo=int(tag_pos[idx]),
                                       op_hi=int(tag_pos[idx]), raw=set()))
        e["occurrences"] += 1
        p = int(tag_pos[idx])
        e["op_lo"] = min(e["op_lo"], p); e["op_hi"] = max(e["op_hi"], p)
        e["raw"].add(s)

    blocks = []
    for label, e in agg.items():
        n3 = int(np.searchsorted(pos3, e["op_hi"], side="right") -
                 np.searchsorted(pos3, e["op_lo"], side="left"))
        blocks.append(dict(tag=label, occurrences=e["occurrences"],
                           op_lo=e["op_lo"], op_hi=e["op_hi"],
                           frac_lo=round(e["op_lo"] / nops, 5),
                           frac_hi=round(e["op_hi"] / nops, 5), n3=n3,
                           raw_tags=sorted(e["raw"])))
    blocks.sort(key=lambda b: b["op_lo"])

    result = dict(path=os.path.abspath(kmb_path), num_ops=nops,
                  num_info_tags=int(len(tag_pos)), num_distinct=len(blocks),
                  total_tagged_n3=sum(b["n3"] for b in blocks), blocks=blocks)
    d = os.path.dirname(os.path.abspath(out_path)); os.makedirs(d, exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(result, fh, indent=1)
    rd.close()

    print(f"distinct INFO_TAG labels: {len(blocks)}; tagged 3q total: {result['total_tagged_n3']:,}")
    print(f"{'label':40s} {'occ':>6s} {'frac':>14s} {'n3(span)':>11s}")
    for b in blocks:
        print(f"{b['tag']:40s} {b['occurrences']:6d} {b['frac_lo']:7.4f}-{b['frac_hi']:<7.4f} {b['n3']:11,}")
    return result


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "work/frontier_scan/mwa_unpacked/dqi.kmb",
         sys.argv[2] if len(sys.argv) > 2 else "work/dqi_builder_recon/info_tags.json")
