#!/usr/bin/env python3
"""Strategy 3 measurement: syndrome-qubit free-to-overwrite window at the width peak.

Circuit: work/frontier_scan/mwa_unpacked/dqi.kmb (sha fc3ba816...)
Q=891 = 840 syndrome (S0..S69 x 12, ids 0..839) + 51 workspace (ids 840..890).

For every qubit we build the full sorted touch list (op position + role):
  role 0 = read        (value consumed for data or phase; qubit value persists or kicks phase)
  role 1 = write       (old value destroyed / moved: CX-target, CCX-target, X, SWAP legs)
  role 2 = reset       (R / HMR: old value discarded, qubit set to |0>)
Role mapping from kickmix Circuit::iter_ops (src/kickmix/circuit/circuit.h):
  3q: q3a=control2, q3b=control1, q3c=target
      CCX:  a=r b=r c=w     CCZ: a=r b=r c=r (phase-only)     CSWAP: a=r b=w c=w
  2q: q2a=control1, q2b=target
      CX:   a=r b=w          CZ: a=r b=r (phase-only)          SWAP: a=w b=w
  1q: q1=target
      X: w    Z/Z_POW: r (phase)    R/HMR: reset
Phase-producing (complex) ops: CZ, CCZ, Z, Z_POW (+_IF). Real-valued (phase-safe):
CX, CCX, CSWAP, SWAP, X, R, HMR.

Metrics at a probe time t* (all over the naive-live peak plateau):
  M1 naive_idle_syn      : last_touch < t* < next_touch            (task's literal def)
  M2 holds_zero_syn      : last touch at pos<=t* is a reset        (qubit is |0>, trivially aliasable)
  M3 no_future_val_syn   : last value-consuming (role!=reset) touch at pos<=t*   [phase-blind]
  M4 no_future_phase_syn : last phase-producing touch at pos<=t*   [phase-safe aliasing bound]
  live_ws / live_syn     : naive liveness counts at t*
Max dQ candidate = min(live_ws, M_k).

Also: per-block touch histogram for syndrome qubits (by op class), Toffoli-touch census on
syndrome vs workspace, and the longest per-syndrome-qubit idle gaps with block locations.

Read-only. Writes JSON + console summary.
"""
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

# Block boundaries as fractions of the op stream (Report A §2, INFO_TAG-derived [FAKT]).
BLOCKS = [
    ("initial",     0.000, 0.045),
    ("extract",     0.045, 0.113),
    ("synthesis",   0.113, 0.206),
    ("convert",     0.206, 0.304),
    ("scan",        0.304, 0.706),
    ("unconvert",   0.706, 0.796),
    ("unsynthesis", 0.796, 0.894),
    ("unextract",   0.894, 0.994),
    ("final",       0.994, 1.000),
]
BLOCK_NAMES = [b[0] for b in BLOCKS]
BLOCK_LO = np.array([b[1] for b in BLOCKS])
BLOCK_HI = np.array([b[2] for b in BLOCKS])

# Op-type sets (bytes).
CCX_T = frozenset((0x31, 0xB1))
CCZ_T = frozenset((0x30, 0xB0))
CSW_T = frozenset((0x32, 0xB2))
CX_T = frozenset((0x21, 0xA1))
CZ_T = frozenset((0x20, 0xA0))
SWP_T = frozenset((0x22, 0xA2))
X_T = frozenset((0x11, 0x91))
Z_T = frozenset((0x10, 0x90, 0x13, 0x93))  # Z, Z_IF, Z_POW, Z_POW_IF
PHASE_T = CZ_T | CCZ_T | Z_T               # complex-valued (phase-producing)
TOFF_T = CCX_T | CCZ_T | CSW_T             # Toffoli-like (scored T)


def block_of(pos_frac: np.ndarray) -> np.ndarray:
    """Block index for op-position fractions (vectorized)."""
    idx = np.searchsorted(BLOCK_HI, pos_frac, side="left")
    return np.clip(idx, 0, len(BLOCKS) - 1)


def main() -> None:
    t0 = time.time()
    rd = KmbReader(KMB)
    nq, nops = rd.num_qubits, rd.num_ops
    print(f"[s3] {rd.path}\n[s3] num_qubits={nq} num_ops={nops:,} "
          f"(3q={rd.n3q:,} 2q={rd.n2q:,} 1q={rd.n1q:,})", file=sys.stderr)

    # ---- syndrome id set ----
    syn_ids = set()
    n_sregs = 0
    for name, qs in rd.registers.items():
        if name.startswith("S") and len(name) > 1 and name[1:].isdigit():
            syn_ids.update(qs)
            n_sregs += 1
    syn_ids = sorted(syn_ids)
    n_syn = len(syn_ids)
    syn_mask = np.zeros(nq, dtype=bool)
    syn_mask[syn_ids] = True
    print(f"[s3] syndrome registers={n_sregs} qubits={n_syn} "
          f"ids[{min(syn_ids)}..{max(syn_ids)}]; workspace={nq - n_syn}", file=sys.stderr)

    # ---- op positions per target class ----
    pos3 = op_positions(rd.types, set(TYPE3Q)).astype(np.int64)
    pos2 = op_positions(rd.types, set(TYPE2Q)).astype(np.int64)
    pos1 = op_positions(rd.types, set(TYPE1Q)).astype(np.int64)

    # ---- build (qubit, pos, role, is_phase, is_toffoli) touch records ----
    tq, tp, tr, tph, tt3 = [], [], [], [], []

    def add(arr, pos, role_arr, phase_arr, toff_arr):
        n = len(arr)
        if n == 0:
            return
        tq.append(arr.astype(np.int32, copy=False))
        tp.append(np.broadcast_to(pos, (n,)).astype(np.int32, copy=False).copy())
        tr.append(role_arr.astype(np.int8, copy=False))
        tph.append(phase_arr.astype(np.bool_, copy=False))
        tt3.append(toff_arr.astype(np.bool_, copy=False))

    if len(pos3):
        t3 = rd.types[pos3]
        ccx = np.isin(t3, list(CCX_T)); ccz = np.isin(t3, list(CCZ_T)); csw = np.isin(t3, list(CSW_T))
        add(rd.q3a, pos3, np.where(ccz, 0, 0), ccz, ccx | ccz | csw)          # control2: always read
        add(rd.q3b, pos3, np.where(csw, 1, 0), ccz, ccx | ccz | csw)           # control1: read (swap-leg: write)
        add(rd.q3c, pos3, np.ones(len(pos3), np.int8), ccz, ccx | ccz | csw)   # target: write
    if len(pos2):
        t2 = rd.types[pos2]
        cx = np.isin(t2, list(CX_T)); cz = np.isin(t2, list(CZ_T)); swp = np.isin(t2, list(SWP_T))
        add(rd.q2a, pos2, np.where(swp, 1, 0), cz, np.zeros(len(pos2), bool))   # control: read (swap: write)
        add(rd.q2b, pos2, np.ones(len(pos2), np.int8), cz, np.zeros(len(pos2), bool))  # target: write
    if len(pos1):
        t1 = rd.types[pos1]
        rst = np.isin(t1, list(RESET_TYPES)); xx = np.isin(t1, list(X_T)); zz = np.isin(t1, list(Z_T))
        role = np.where(rst, 2, np.where(xx, 1, 0)).astype(np.int8)
        add(rd.q1, pos1, role, zz, np.zeros(len(pos1), bool))

    tq = np.concatenate(tq); tp = np.concatenate(tp)
    tr = np.concatenate(tr); tph = np.concatenate(tph); tt3 = np.concatenate(tt3)
    n_touch = len(tq)
    print(f"[s3] total qubit touches={n_touch:,} (mem ~{n_touch*15/1e6:.0f} MB)", file=sys.stderr)

    # ---- sort by (qubit, pos) ----
    order = np.lexsort((tp, tq)).astype(np.int32)
    tq_s = tq[order].astype(np.int32, copy=False)
    tp_s = tp[order].astype(np.int32, copy=False)
    tr_s = tr[order]
    tph_s = tph[order]
    tt3_s = tt3[order]
    del tq, tp, tr, tph, tt3, order

    q_starts = np.searchsorted(tq_s, np.arange(nq), side="left").astype(np.int64)
    q_ends = np.searchsorted(tq_s, np.arange(nq), side="right").astype(np.int64)
    used = q_ends > q_starts
    first = np.full(nq, -1, np.int64)
    last = np.full(nq, -1, np.int64)
    first[used] = tp_s[q_starts[used]].astype(np.int64)
    last[used] = tp_s[q_ends[used] - 1].astype(np.int64)

    # ---- naive liveness sweep -> peak plateau ----
    ev = {}
    for q in range(nq):
        if first[q] >= 0:
            ev[first[q]] = ev.get(first[q], 0) + 1
            ev[last[q] + 1] = ev.get(last[q] + 1, 0) - 1
    pts = sorted(ev)
    cur = peak = 0
    peak_runs = []
    counts = []
    for i, p in enumerate(pts):
        cur += ev[p]
        end = pts[i + 1] - 1 if i + 1 < len(pts) else p
        counts.append((p, end, cur))
        if cur > peak:
            peak = cur
            peak_runs = [[p, end]]
        elif cur == peak:
            peak_runs.append([p, end])
    merged = []
    for a, b in peak_runs:
        if merged and merged[-1][1] + 1 >= a:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    print(f"\n[s3] NAIVE PEAK concurrent-live = {peak} (declared Q={nq})", file=sys.stderr)
    for a, b in merged:
        print(f"[s3]   plateau ops [{int(a):,} .. {int(b):,}] frac "
              f"[{a/nops:.4f} .. {b/nops:.4f}] span={int(b-a+1):,} ({(b-a+1)/nops*100:.1f}% of stream)",
              file=sys.stderr)

    # fraction of stream at peak
    peak_frac = sum(b - a + 1 for a, b in merged) / nops
    print(f"[s3] peak covers {peak_frac*100:.2f}% of stream", file=sys.stderr)

    # ---- per-qubit precomputed stats ----
    # For each qubit: sorted pos list, role list, phase list; scalars:
    #   last_val  = max pos with role != 2  (last value-consuming touch)
    #   last_ph   = max pos with phase-producing touch
    #   last_toff = max pos with Toffoli-like touch
    last_val = np.full(nq, -1, np.int64)
    last_ph = np.full(nq, -1, np.int64)
    last_toff = np.full(nq, -1, np.int64)
    qpos_list = []
    qrole_list = []
    for q in range(nq):
        s, e = int(q_starts[q]), int(q_ends[q])
        if e <= s:
            qpos_list.append(None)
            qrole_list.append(None)
            continue
        pq = tp_s[s:e].astype(np.int64, copy=False)
        rq = tr_s[s:e]
        phq = tph_s[s:e]
        tvq = tt3_s[s:e]
        nv = rq != 2
        last_val[q] = pq[nv].max() if nv.any() else -1
        last_ph[q] = pq[phq].max() if phq.any() else -1
        last_toff[q] = pq[tvq].max() if tvq.any() else -1
        qpos_list.append(pq)
        qrole_list.append(rq)

    ws_idx = np.flatnonzero(~syn_mask)
    syn_idx = np.array(syn_ids, dtype=np.int64)
    ws_first = first[ws_idx]; ws_last = last[ws_idx]
    syn_first = first[syn_idx]; syn_last = last[syn_idx]

    # ---- probe times: dense across the peak plateau ----
    total_span = sum(b - a + 1 for a, b in merged)
    n_probe = 400
    probes = []
    for a, b in merged:
        k = max(2, round(n_probe * (b - a + 1) / total_span))
        probes.extend(np.linspace(a, b, k).astype(np.int64).tolist())
    probes = sorted(set(probes))
    print(f"[s3] probing {len(probes)} times across peak plateau", file=sys.stderr)

    rows = []
    for t_star in probes:
        live_ws = int(((ws_first <= t_star) & (ws_last >= t_star)).sum())
        live_syn = int(((syn_first <= t_star) & (syn_last >= t_star)).sum())
        m3 = int((last_val[syn_idx] <= t_star).sum())
        m4 = int((last_ph[syn_idx] <= t_star).sum())
        m1 = 0
        m2 = 0
        for q in syn_ids:
            pq = qpos_list[q]
            if pq is None or len(pq) == 0:
                continue
            idx = int(np.searchsorted(pq, t_star, side="left"))
            if 0 < idx < len(pq) and pq[idx - 1] < t_star < pq[idx]:
                m1 += 1
            if idx > 0:
                j = idx - 1
                while j >= 0 and pq[j] >= t_star:
                    j -= 1
                if j >= 0 and qrole_list[q][j] == 2:
                    m2 += 1
        rows.append(dict(t=int(t_star), frac=round(t_star / nops, 5),
                         live_ws=live_ws, live_syn=live_syn,
                         M1_naive_idle=m1, M2_holds_zero=m2,
                         M3_no_future_val=m3, M4_no_future_phase=m4,
                         total_live=live_ws + live_syn))

    rows_arr = np.array([(r["M1_naive_idle"], r["M2_holds_zero"], r["M3_no_future_val"],
                          r["M4_no_future_phase"], r["live_ws"], r["live_syn"]) for r in rows])
    best = {k: int(rows_arr[:, i].max()) for i, k in enumerate(
        ("M1_naive_idle", "M2_holds_zero", "M3_no_future_val", "M4_no_future_phase"))}
    best_at = {k: int(rows_arr[:, i].argmax()) for i, k in enumerate(
        ("M1_naive_idle", "M2_holds_zero", "M3_no_future_val", "M4_no_future_phase"))}

    # ---- per-block syndrome touch histogram (by class) ----
    def syn_hist(pos, arrs):
        """Per-block touch counts of syndrome qubits for the given target arrays."""
        out = np.zeros(len(BLOCKS), dtype=np.int64)
        for arr in arrs:
            if arr is None or len(arr) == 0:
                continue
            m = syn_mask[arr]
            if not m.any():
                continue
            bf = block_of((pos[m].astype(np.float64)) / nops)
            out += np.bincount(bf, minlength=len(BLOCKS))
        return out

    h3a = syn_hist(pos3, [rd.q3a]); h3b = syn_hist(pos3, [rd.q3b]); h3c = syn_hist(pos3, [rd.q3c])
    h2a = syn_hist(pos2, [rd.q2a]); h2b = syn_hist(pos2, [rd.q2b]); h1 = syn_hist(pos1, [rd.q1])
    tbl = {}
    tbl["3q_leg_a"] = h3a.tolist(); tbl["3q_leg_b"] = h3b.tolist(); tbl["3q_leg_c"] = h3c.tolist()
    tbl["2q_leg_a"] = h2a.tolist(); tbl["2q_leg_b"] = h2b.tolist(); tbl["1q"] = h1.tolist()
    tbl["total"] = (h3a + h3b + h3c + h2a + h2b + h1).tolist()

    # Toffoli-like touches on syndrome vs workspace
    def toff_hist(pos, arrs):
        out_syn = np.zeros(len(BLOCKS), dtype=np.int64)
        out_ws = np.zeros(len(BLOCKS), dtype=np.int64)
        for arr in arrs:
            if arr is None or len(arr) == 0:
                continue
            ms = syn_mask[arr]; mw = ~ms
            if ms.any():
                out_syn += np.bincount(block_of(pos[ms].astype(np.float64) / nops), minlength=len(BLOCKS))
            if mw.any():
                out_ws += np.bincount(block_of(pos[mw].astype(np.float64) / nops), minlength=len(BLOCKS))
        return out_syn.tolist(), out_ws.tolist()

    toff_syn, toff_ws = toff_hist(pos3, [rd.q3a, rd.q3b, rd.q3c])
    tot_toff_syn = sum(toff_syn); tot_toff_ws = sum(toff_ws)

    # phase-op touches on syndrome vs workspace (CZ/CCZ/Z legs)
    def phase_hist(pos, arrs):
        out_syn = np.zeros(len(BLOCKS), dtype=np.int64)
        out_ws = np.zeros(len(BLOCKS), dtype=np.int64)
        for arr in arrs:
            if arr is None or len(arr) == 0:
                continue
            ms = syn_mask[arr]; mw = ~ms
            if ms.any():
                out_syn += np.bincount(block_of(pos[ms].astype(np.float64) / nops), minlength=len(BLOCKS))
            if mw.any():
                out_ws += np.bincount(block_of(pos[mw].astype(np.float64) / nops), minlength=len(BLOCKS))
        return out_syn.tolist(), out_ws.tolist()

    # phase ops: 3q CCZ legs (all three), 2q CZ legs (both), 1q Z
    ph3 = pos3[np.isin(rd.types[pos3], list(CCZ_T))]
    ph2 = pos2[np.isin(rd.types[pos2], list(CZ_T))]
    ph1 = pos1[np.isin(rd.types[pos1], list(Z_T))]
    ph3a = rd.q3a[np.isin(rd.types[pos3], list(CCZ_T))]
    ph3b = rd.q3b[np.isin(rd.types[pos3], list(CCZ_T))]
    ph3c = rd.q3c[np.isin(rd.types[pos3], list(CCZ_T))]
    ph2a = rd.q2a[np.isin(rd.types[pos2], list(CZ_T))]
    ph2b = rd.q2b[np.isin(rd.types[pos2], list(CZ_T))]
    ph1q = rd.q1[np.isin(rd.types[pos1], list(Z_T))]
    psyn, pws = phase_hist(ph3, [ph3a, ph3b, ph3c])
    psyn2, pws2 = phase_hist(ph2, [ph2a, ph2b])
    psyn3, pws3 = phase_hist(ph1, [ph1q])
    phase_syn = [a + b + c for a, b, c in zip(psyn, psyn2, psyn3)]
    phase_ws = [a + b + c for a, b, c in zip(pws, pws2, pws3)]

    # ---- longest idle gaps per syndrome qubit (top 15) ----
    gaps = []
    for q in syn_ids:
        pq = qpos_list[q]
        if pq is None or len(pq) < 2:
            continue
        g = np.diff(pq)
        i = int(g.argmax())
        gaps.append((int(g[i]), int(pq[i]), int(pq[i + 1]), q))
    gaps.sort(reverse=True)
    top_gaps = [dict(gap_ops=g, gap_frac=round(g / nops, 5), at_ops=[a, b],
                     at_frac=[round(a / nops, 4), round(b / nops, 4)],
                     block_lo=BLOCK_NAMES[int(block_of(a / nops))],
                     block_hi=BLOCK_NAMES[int(block_of(b / nops))], qubit=q)
                for g, a, b, q in gaps[:15]]

    # how many syndrome qubits have an idle gap covering each probe time (== M1, sanity)
    # distribution of last_val / last_ph over syndrome qubits (block of last consume)
    lv_blocks = block_of(np.clip(last_val[syn_idx], 0, nops - 1).astype(np.float64) / nops)
    lp_blocks = block_of(np.clip(last_ph[syn_idx], 0, nops - 1).astype(np.float64) / nops)
    lv_hist = np.bincount(lv_blocks, minlength=len(BLOCKS)).tolist()
    lp_hist = np.bincount(lp_blocks, minlength=len(BLOCKS)).tolist()

    result = dict(
        path=os.path.abspath(rd.path),
        header=dict(num_qubits=nq, num_ops=nops, n3q=int(rd.n3q), n2q=int(rd.n2q), n1q=int(rd.n1q)),
        syndrome=dict(count=n_syn, ids_min=min(syn_ids), ids_max=max(syn_ids),
                      workspace_count=nq - n_syn),
        peak=dict(naive_peak=peak, plateau=[[int(a), int(b)] for a, b in merged],
                  plateau_frac=round(peak_frac, 4)),
        probes=len(probes),
        probe_rows=rows,
        best_at_peak=best,
        best_at_probe_index=best_at,
        syndrome_touches_per_block=dict(blocks=BLOCK_NAMES, **tbl),
        toffoli_like_touches=dict(blocks=BLOCK_NAMES, syndrome=tot_toff_syn,
                                  workspace=tot_toff_ws,
                                  syndrome_per_block=toff_syn, workspace_per_block=toff_ws),
        phase_op_touches=dict(blocks=BLOCK_NAMES, syndrome=sum(phase_syn),
                              workspace=sum(phase_ws),
                              syndrome_per_block=phase_syn, workspace_per_block=phase_ws),
        last_value_consume_block_hist=dict(blocks=BLOCK_NAMES, counts=lv_hist),
        last_phase_consume_block_hist=dict(blocks=BLOCK_NAMES, counts=lp_hist),
        top_syndrome_idle_gaps=top_gaps,
        elapsed_s=round(time.time() - t0, 1),
    )

    out_json = os.path.join(HERE, "free_window.json")
    with open(out_json, "w") as fh:
        json.dump(result, fh, indent=1)
    print(f"[s3] wrote {out_json}", file=sys.stderr)

    # ---- console summary ----
    print(json.dumps(result["peak"], indent=1))
    print(f"\nBest metric values across {len(probes)} peak probes:")
    for k in ("M1_naive_idle", "M2_holds_zero", "M3_no_future_val", "M4_no_future_phase"):
        i = best_at[k]
        r = rows[i]
        print(f"  {k:20s} max={best[k]:4d}  at t={r['t']:,} ({r['frac']})  "
              f"live_ws={r['live_ws']} live_syn={r['live_syn']} total={r['total_live']}")
    print("\nSyndrome touches per block (leg sums):")
    print(f"  {'block':12s} {'3q_a':>8s} {'3q_b':>8s} {'3q_c':>8s} {'2q_a':>8s} {'2q_b':>8s} {'1q':>8s} {'TOTAL':>9s}")
    for i, bn in enumerate(BLOCK_NAMES):
        print(f"  {bn:12s} {tbl['3q_leg_a'][i]:8d} {tbl['3q_leg_b'][i]:8d} {tbl['3q_leg_c'][i]:8d} "
              f"{tbl['2q_leg_a'][i]:8d} {tbl['2q_leg_b'][i]:8d} {tbl['1q'][i]:8d} {tbl['total'][i]:9d}")
    print(f"\nToffoli-like touches: syndrome={tot_toff_syn:,} workspace={tot_toff_ws:,}")
    print(f"Phase-op touches:     syndrome={sum(phase_syn):,} workspace={sum(phase_ws):,}")
    print("\nLast value-consume per syndrome qubit (block histogram):")
    for i, bn in enumerate(BLOCK_NAMES):
        print(f"  {bn:12s} {lv_hist[i]:5d}")
    print("\nTop-10 longest syndrome idle gaps:")
    for g in top_gaps[:10]:
        print(f"  q{g['qubit']:4d} gap={g['gap_ops']:>9,} ops ({g['gap_frac']*100:5.1f}%) "
              f"frac[{g['at_frac'][0]}..{g['at_frac'][1]}] blocks {g['block_lo']}->{g['block_hi']}")
    print(f"\nelapsed {result['elapsed_s']}s")
    rd.close()


if __name__ == "__main__":
    main()
