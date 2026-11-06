#!/usr/bin/env python3
"""Follow-up detail for report_G: last-consume distribution, probe-row check,
final/initial block op census, INFO_TAG context at last-consume positions."""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "dqi_sources"))
from width_liveness import KmbReader, op_positions, TYPE3Q, TYPE2Q, TYPE1Q, RESET_TYPES  # noqa: E402

KMB = os.path.join(HERE, "..", "frontier_scan", "mwa_unpacked", "dqi.kmb")
CCX_T = frozenset((0x31, 0xB1)); CCZ_T = frozenset((0x30, 0xB0)); CSW_T = frozenset((0x32, 0xB2))
CX_T = frozenset((0x21, 0xA1)); CZ_T = frozenset((0x20, 0xA0)); SWP_T = frozenset((0x22, 0xA2))
X_T = frozenset((0x11, 0x91)); Z_T = frozenset((0x10, 0x90, 0x13, 0x93))


def main():
    t0 = time.time()
    rd = KmbReader(KMB)
    nq, nops = rd.num_qubits, rd.num_ops
    syn_mask = np.zeros(nq, dtype=bool)
    for name, qs in rd.registers.items():
        if name.startswith("S") and len(name) > 1 and name[1:].isdigit():
            syn_mask[qs] = True
    syn_ids = np.flatnonzero(syn_mask)

    pos3 = op_positions(rd.types, set(TYPE3Q)).astype(np.int64)
    pos2 = op_positions(rd.types, set(TYPE2Q)).astype(np.int64)
    pos1 = op_positions(rd.types, set(TYPE1Q)).astype(np.int64)

    # role != reset  =>  value-consuming
    r3 = np.zeros(len(pos3), bool)   # no resets in 3q class
    r2 = np.zeros(len(pos2), bool)
    r1 = np.isin(rd.types[pos1], list(RESET_TYPES))

    vq_parts, vc_parts = [], []
    for arr, pos, rst in ((rd.q3a, pos3, r3), (rd.q3b, pos3, r3), (rd.q3c, pos3, r3),
                          (rd.q2a, pos2, r2), (rd.q2b, pos2, r2), (rd.q1, pos1, r1)):
        m = syn_mask[arr] & ~rst
        if m.any():
            vq_parts.append(arr[m]); vc_parts.append(pos[m])
    vq = np.concatenate(vq_parts); vc = np.concatenate(vc_parts)
    # per-qubit last value-consuming touch
    last_vc = np.full(nq, -1, np.int64)
    o = np.lexsort((vc, vq))
    vq_s, vc_s = vq[o], vc[o]
    change = np.concatenate(([True], vq_s[1:] != vq_s[:-1]))
    starts = np.flatnonzero(change)
    last_per_q = vc_s[np.r_[starts[1:] - 1, len(vc_s) - 1]]
    uniq_q = vq_s[starts]
    last_vc[uniq_q] = last_per_q

    lv = last_vc[syn_ids]
    print(f"[s3f] syndrome last value-consume touch: n={len(lv)}")
    for pctl in (0, 1, 5, 25, 50, 75, 95, 99, 100):
        v = int(np.percentile(lv, pctl))
        print(f"   p{pctl:3d}: op {v:>12,}  frac {v/nops:.5f}")
    print(f"   min={lv.min():,} ({lv.min()/nops:.5f})  max={lv.max():,} ({lv.max()/nops:.5f})")
    # how many finish before various fracs
    for f in (0.5, 0.7, 0.8, 0.9, 0.95, 0.99, 0.994):
        c = int((lv < f * nops).sum())
        print(f"   last_vc < {f:.3f}: {c}/{len(lv)}")

    # ---- op census in final block (frac >= 0.994) and initial (frac < 0.045) ----
    def census(lo_frac, hi_frac, label):
        lo, hi = int(lo_frac * nops), int(hi_frac * nops)
        m3 = (pos3 >= lo) & (pos3 < hi); m2 = (pos2 >= lo) & (pos2 < hi); m1 = (pos1 >= lo) & (pos1 < hi)
        ty3 = rd.types[pos3[m3]]; ty2 = rd.types[pos2[m2]]; ty1 = rd.types[pos1[m1]]
        out = dict(
            CCX=int(np.isin(ty3, list(CCX_T)).sum()), CCZ=int(np.isin(ty3, list(CCZ_T)).sum()),
            CSWAP=int(np.isin(ty3, list(CSW_T)).sum()),
            CX=int(np.isin(ty2, list(CX_T)).sum()), CZ=int(np.isin(ty2, list(CZ_T)).sum()),
            SWAP=int(np.isin(ty2, list(SWP_T)).sum()),
            X=int(np.isin(ty1, list(X_T)).sum()), RHMR=int(np.isin(ty1, list(RESET_TYPES)).sum()),
            Z=int(np.isin(ty1, list(Z_T)).sum()),
        )
        print(f"[s3f] {label} (frac {lo_frac}-{hi_frac}, ops {hi-lo:,}): {out}")
        return out

    fin = census(0.994, 1.0, "FINAL block")
    ini = census(0.0, 0.045, "INITIAL block")

    # syndrome involvement in final block 2q gates
    fin_lo, fin_hi = int(0.994 * nops), nops
    m2 = (pos2 >= fin_lo) & (pos2 < fin_hi)
    p2f, t2f = pos2[m2], rd.types[pos2[m2]]
    a, b = rd.q2a[m2], rd.q2b[m2]
    cxm = np.isin(t2f, list(CX_T)); czm = np.isin(t2f, list(CZ_T)); swpm = np.isin(t2f, list(SWP_T))
    def cnt(m):
        return int((syn_mask[a[m]] | syn_mask[b[m]]).sum())
    print(f"[s3f] FINAL 2q gates: CX={int(cxm.sum()):,} (syn-involved {cnt(cxm):,}) "
          f"CZ={int(czm.sum()):,} (syn {cnt(czm):,}) SWAP={int(swpm.sum()):,} (syn {cnt(swpm):,})")
    # direction: syndrome as control (leg a) vs target (leg b) for CX in final block
    if cxm.any():
        ac = int(syn_mask[a[cxm]].sum()); bc = int(syn_mask[b[cxm]].sum())
        print(f"[s3f] FINAL CX: syndrome-as-control(leg_a)={ac:,} syndrome-as-target(leg_b)={bc:,}")

    # same for initial block
    ini_lo, ini_hi = 0, int(0.045 * nops)
    m2i = (pos2 >= ini_lo) & (pos2 < ini_hi)
    t2i = rd.types[pos2[m2i]]
    ai, bi = rd.q2a[m2i], rd.q2b[m2i]
    cxi = np.isin(t2i, list(CX_T)); czi = np.isin(t2i, list(CZ_T))
    if cxi.any():
        ac = int(syn_mask[ai[cxi]].sum()); bc = int(syn_mask[bi[cxi]].sum())
        print(f"[s3f] INITIAL CX: {int(cxi.sum()):,} gates; syndrome-as-control={ac:,} as-target={bc:,}")
    print(f"[s3f] INITIAL CZ: {int(czi.sum()):,}")

    # ---- INFO_TAG context: tags present in final block and their positions ----
    tag_pos = op_positions(rd.types, (0x06,))
    if len(tag_pos) and rd.tag_strings:
        tf = tag_pos / nops
        fin_tags = {}
        for p, i in zip(tag_pos, range(len(tag_pos))):
            if p >= fin_lo:
                s = rd.tag_strings[i]
                fin_tags[s] = fin_tags.get(s, 0) + 1
        top = sorted(fin_tags.items(), key=lambda kv: -kv[1])[:15]
        print(f"[s3f] FINAL block INFO_TAGS (top15): {top}")
        # last tag before end of stream
        print(f"[s3f] last 5 tags overall: {[rd.tag_strings[i] for i in range(len(tag_pos)-5, len(tag_pos))]} "
              f"at fracs {[round(p/nops, 4) for p in tag_pos[-5:]]}")

    # ---- probe rows from main JSON: confirm M3 all zero ----
    with open(os.path.join(HERE, "free_window.json")) as fh:
        j = json.load(fh)
    rows = j["probe_rows"]
    m3s = [r["M3_no_future_val"] for r in rows]
    m4s = [r["M4_no_future_phase"] for r in rows]
    m1s = [r["M1_naive_idle"] for r in rows]
    m2s = [r["M2_holds_zero"] for r in rows]
    print(f"\n[s3f] probe rows: n={len(rows)}")
    print(f"   M1 naive_idle: min={min(m1s)} max={max(m1s)} mean={np.mean(m1s):.1f}")
    print(f"   M2 holds_zero: min={min(m2s)} max={max(m2s)} mean={np.mean(m2s):.1f}")
    print(f"   M3 no_future_val: min={min(m3s)} max={max(m3s)}  (all zero: {all(x == 0 for x in m3s)})")
    print(f"   M4 no_future_phase: min={min(m4s)} max={max(m4s)} mean={np.mean(m4s):.1f}")
    # M4 profile: where does it rise?
    rising = [(r["frac"], r["M4_no_future_phase"]) for r in rows if r["M4_no_future_phase"] > 0]
    if rising:
        print(f"   M4>0 first at frac={rising[0][0]}, last at frac={rising[-1][0]} (n={len(rising)})")

    # ---- workspace liveness: are all 51 ws qubits live across the whole plateau? ----
    ws_ids = np.flatnonzero(~syn_mask)
    # reuse first/last from quick recompute
    tq_parts, tp_parts = [], []
    for arr, pos in ((rd.q3a, pos3), (rd.q3b, pos3), (rd.q3c, pos3),
                     (rd.q2a, pos2), (rd.q2b, pos2), (rd.q1, pos1)):
        if len(arr):
            tq_parts.append(arr); tp_parts.append(np.broadcast_to(pos, (len(arr),)))
    tq = np.concatenate(tq_parts).astype(np.int32)
    tp = np.concatenate(tp_parts).astype(np.int32)
    o = np.lexsort((tp, tq))
    tq_s, tp_s = tq[o], tp[o]
    qs = np.searchsorted(tq_s, np.arange(nq), side="left")
    qe = np.searchsorted(tq_s, np.arange(nq), side="right")
    first = np.full(nq, -1, np.int64); last = np.full(nq, -1, np.int64)
    u = qe > qs
    first[u] = tp_s[qs[u]]; last[u] = tp_s[qe[u] - 1]
    wsf, wsl = first[ws_ids], last[ws_ids]
    plateau_lo, plateau_hi = 3031171, 57984209
    ws_live_at_plat_lo = int(((wsf <= plateau_lo) & (wsl >= plateau_lo)).sum())
    ws_live_at_plat_hi = int(((wsf <= plateau_hi) & (wsl >= plateau_hi)).sum())
    ws_start_after_plat_lo = int((wsf > plateau_lo).sum())
    print(f"\n[s3f] workspace: live at plateau start={ws_live_at_plat_lo}/51, "
          f"live at plateau end={ws_live_at_plat_hi}/51, first-touch after plateau start={ws_start_after_plat_lo}")
    late = [(int(qi), int(wsf[i]), int(wsl[i])) for i, qi in enumerate(ws_ids) if wsf[i] > plateau_lo]
    print(f"[s3f] late-starting ws qubits (first>plateau_lo): {late[:10]}")
    early_end = [(int(qi), int(wsf[i]), int(wsl[i])) for i, qi in enumerate(ws_ids) if wsl[i] < plateau_hi]
    print(f"[s3f] early-ending ws qubits (last<plateau_hi): {early_end[:10]}")

    # post-plateau live counts (uninitial / restore_masks region)
    synf, synl = first[syn_ids], last[syn_ids]
    for f in (0.994, 0.995, 0.996, 0.997, 0.998, 0.9984, 0.999, 1.0):
        tt = int(f * nops)
        lw = int(((wsf <= tt) & (wsl >= tt)).sum())
        ls_ = int(((synf <= tt) & (synl >= tt)).sum())
        print(f"[s3f] frac {f:.4f}: live ws={lw}/51 syn={ls_}/840 total={lw + ls_}")

    print(f"\nelapsed {time.time()-t0:.1f}s")
    rd.close()


if __name__ == "__main__":
    main()
