"""DQI Benchmark II — per-INFO_TAG-block structural analysis of dqi.kmb.

Read-only. Uses width_liveness.KmbReader (zero-copy mmap).
Outputs: work/dqi_t_sprint/block_analysis.json + console summary.
"""
import importlib.util
import json
import sys
from collections import Counter, defaultdict

import numpy as np

ROOT = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum'
KMB = f'{ROOT}/work/frontier_scan/mwa_unpacked/dqi.kmb'

spec = importlib.util.spec_from_file_location('wl', f'{ROOT}/work/dqi_sources/width_liveness.py')
wl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wl)

TYPE3Q = {0x30: "CCZ", 0xB0: "CCZ_IF", 0x31: "CCX", 0xB1: "CCX_IF",
          0x32: "CSWAP", 0xB2: "CSWAP_IF"}
TYPE2Q = {0x20: "CZ", 0xA0: "CZ_IF", 0x21: "CX", 0xA1: "CX_IF",
          0x22: "SWAP", 0xA2: "SWAP_IF"}
TYPE1Q = {0x10: "Z", 0x90: "Z_IF", 0x11: "X", 0x91: "X_IF",
          0x12: "R", 0x92: "R_IF", 0x13: "Z_POW", 0x93: "Z_POW_IF",
          0x50: "HMR", 0xD0: "HMR_IF"}


def main():
    r = wl.KmbReader(KMB)
    t = r.types
    N = r.num_ops
    nops = N
    print(f'[blk] ops={nops:,} 3q={r.n3q:,} 2q={r.n2q:,} 1q={r.n1q:,} '
          f'1b={r.n1b:,} cond={r.ncond:,} tags={r.ntags}', file=sys.stderr)

    # ---- registers: syndrome ids ----
    syndrome = set()
    for name, qs in r.registers.items():
        if name.startswith('S') and name[1:].isdigit():
            syndrome.update(qs)
    nq = r.num_qubits
    working = [q for q in range(nq) if q not in syndrome]
    print(f'[blk] syndrome={len(syndrome)} working={len(working)} {working[:5]}..{working[-5:]}', file=sys.stderr)

    # ---- tag events ----
    tagpos = np.flatnonzero(t == 0x06)
    assert len(tagpos) == r.ntags
    events = []  # (pos, name, is_enter)
    for p, s in zip(tagpos.tolist(), r.tag_strings):
        if s.startswith('@enter:'):
            events.append((p, s[7:], True))
        elif s.startswith('@exit:'):
            events.append((p, s[6:], False))
        else:
            events.append((p, s, None))
    events.sort()

    # build nested block tree
    root = {'name': '<root>', 'lo': 0, 'hi': nops, 'children': []}
    stack = [root]
    for p, name, is_enter in events:
        if is_enter:
            node = {'name': name, 'lo': p, 'hi': None, 'parent': stack[-1], 'children': []}
            stack[-1]['children'].append(node)
            stack.append(node)
        elif is_enter is False:
            # pop until matching
            if len(stack) > 1 and stack[-1]['name'] == name:
                node = stack.pop()
            else:
                while len(stack) > 1 and stack[-1]['name'] != name:
                    stack.pop()
                node = stack.pop()
            node['hi'] = p
        # is_enter is None: standalone tag, ignore for tree
    def close(node, lo, hi):
        for c in node['children']:
            if c['hi'] is None:
                c['hi'] = hi
                close(c, lo, hi)
    close(root, 0, nops)

    # ---- op-type prefix sums for range queries ----
    def lut(keys):
        L = np.zeros(256, dtype=bool)
        L[list(keys)] = True
        return L

    l3 = lut(set(TYPE3Q))
    l2 = lut(set(TYPE2Q))
    l1 = lut(set(TYPE1Q))
    lhmr = lut((0x50, 0xD0))
    lr = lut((0x12, 0x92))
    pre3 = np.concatenate(([0], np.cumsum(l3[t].astype(np.int32))))
    pre2 = np.concatenate(([0], np.cumsum(l2[t].astype(np.int32))))
    pre1 = np.concatenate(([0], np.cumsum(l1[t].astype(np.int32))))
    prehmr = np.concatenate(([0], np.cumsum(lhmr[t].astype(np.int32))))
    prer = np.concatenate(([0], np.cumsum(lr[t].astype(np.int32))))

    pos3 = np.flatnonzero(l3[t]).astype(np.int32)
    pos1 = np.flatnonzero(l1[t]).astype(np.int32)
    hmr_pos = np.flatnonzero(lhmr[t]).astype(np.int32)
    r_pos = np.flatnonzero(lr[t]).astype(np.int32)

    def qclass(arr, idx):
        """count of ids in arr[idx] that are syndrome vs working"""
        v = arr[idx]
        if len(v) == 0:
            return 0, 0
        return int(np.isin(v, list(syndrome)).sum()), int(len(v) - np.isin(v, list(syndrome)).sum())

    # precompute syndrome membership as bool array for speed
    synmask = np.zeros(nq, dtype=bool)
    synmask[list(syndrome)] = True

    def block_stats(node):
        lo, hi = node['lo'], node['hi']
        span = hi - lo
        n3 = int(pre3[hi] - pre3[lo])
        n2 = int(pre2[hi] - pre2[lo])
        n1 = int(pre1[hi] - pre1[lo])
        nhmr = int(prehmr[hi] - prehmr[lo])
        nr = int(prer[hi] - prer[lo])
        st = {'name': node['name'], 'lo': lo, 'hi': hi, 'span': span,
              'frac_lo': round(lo / nops, 5), 'frac_hi': round(hi / nops, 5),
              'n3': n3, 'n2': n2, 'n1': n1, 'nhmr': nhmr, 'nr': nr}
        if n3:
            i0, i1 = np.searchsorted(pos3, lo, 'left'), np.searchsorted(pos3, hi, 'left')
            seg = pos3[i0:i1]
            tt = t[seg]
            tc = Counter(int(x) for x in tt)
            st['3q_types'] = {TYPE3Q[k]: v for k, v in sorted(tc.items())}
            # qubit class legs
            slegs = wlegs = 0
            for arr in (r.q3a, r.q3b, r.q3c):
                v = arr[i0:i1]
                slegs += int(synmask[v].sum())
                wlegs += int(len(v) - synmask[v].sum())
            st['3q_syndrome_legs'] = slegs
            st['3q_working_legs'] = wlegs
        if nhmr or nr:
            i0, i1 = np.searchsorted(hmr_pos, lo, 'left'), np.searchsorted(hmr_pos, hi, 'left')
            v = r.q1[np.searchsorted(pos1, hmr_pos[i0:i1])]
            st['hmr_syndrome'] = int(synmask[v].sum())
            st['hmr_working'] = int(len(v) - synmask[v].sum())
            i0, i1 = np.searchsorted(r_pos, lo, 'left'), np.searchsorted(r_pos, hi, 'left')
            v = r.q1[np.searchsorted(pos1, r_pos[i0:i1])]
            st['r_syndrome'] = int(synmask[v].sum())
            st['r_working'] = int(len(v) - synmask[v].sum())
        return st

    top = [c for c in root['children']]
    out = {}
    for node in top:
        out[node['name']] = block_stats(node)
        subs = defaultdict(lambda: [0, 0, 0])  # name -> [count, n3, span]
        for c in node['children']:
            s = subs[c['name']]
            s[0] += 1
            s[1] += int(pre3[c['hi']] - pre3[c['lo']])
            s[2] += c['hi'] - c['lo']
        if subs:
            out[node['name']]['subs'] = {k: dict(count=v[0], n3=v[1], span=v[2])
                                         for k, v in sorted(subs.items(), key=lambda kv: -kv[1][1])}

    total3 = sum(v['n3'] for v in out.values())
    print(f'\ntotal 3q in top blocks: {total3} (header n3q={r.n3q})')
    print(f'{"block":20} {"frac":>12} {"span":>12} {"3q":>8} {"%":>6} {"2q":>12} {"1q":>8} {"HMR":>6} {"R":>6}')
    for k, v in sorted(out.items(), key=lambda kv: -kv[1]['n3']):
        print(f'{k:20} {v["frac_lo"]:>6.3f}-{v["frac_hi"]:<6.3f} {v["span"]:>12,} '
              f'{v["n3"]:>8,} {100*v["n3"]/max(1,r.n3q):>6.2f} {v["n2"]:>12,} {v["n1"]:>8,} '
              f'{v.get("nhmr",0):>6,} {v.get("nr",0):>6,}')
        if 'subs' in v:
            for sk, sv in list(v['subs'].items())[:12]:
                print(f'   └ {sk:28} ×{sv["count"]:>5}  3q={sv["n3"]:>8,}  span={sv["span"]:>12,}')

    with open(f'{ROOT}/work/dqi_t_sprint/block_analysis.json', 'w') as f:
        json.dump(out, f, indent=1)
    r.close()


if __name__ == '__main__':
    main()
