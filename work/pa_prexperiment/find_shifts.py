"""Locate the normalization shift (x_norm = x << 2s) and any other shift-like regions
in the shipped circuit, to understand the available variable-shift infrastructure and
its APPLIED-toffoli footprint."""
import sys
import kickmix as km

CIRCUIT = 'work/frontier_scan/mwa_unpacked/invsqrt.kmb'
c = km.Circuit.from_file(CIRCUIT)
lines = str(c).splitlines()

# Identify runs of adjacent-pair CX/SWAP/CSWAP on consecutive qubit indices (shift cascades).
def qidx(q):
    try: return int(q[1:])
    except: return None

# scan for the earliest dense region of CX between consecutive qubits (a shift)
import re
cx_adj = []
for i, ln in enumerate(lines):
    s = ln.strip()
    if not s or s.startswith('#'): continue
    parts = s.split()
    if parts[0] in ('CX','SWAP') and len(parts) >= 3:
        a, b = qidx(parts[1]), qidx(parts[2])
        if a is not None and b is not None and abs(a-b) == 1:
            cx_adj.append((i, parts[0], min(a,b)))

# cluster consecutive line indices
clusters = []
if cx_adj:
    start = cx_adj[0][0]; prev = start; length = 1
    for (i,_,_) in cx_adj[1:]:
        if i - prev <= 3:
            prev = i; length += 1
        else:
            clusters.append((start, prev, length)); start = i; prev = i; length = 1
    clusters.append((start, prev, length))
print('adjacent-CX/SWAP clusters (start_line, end_line, count): top 25 by count')
for cl in sorted(clusters, key=lambda x:-x[2])[:25]:
    print(f'  lines {cl[0]:6d}-{cl[1]:6d}  n={cl[2]}')

# Show the region of the largest early cluster (likely the normalization shift)
if clusters:
    big = max(clusters, key=lambda x: x[2])
    a, b, _ = big
    print(f'\n--- largest cluster lines {a}..{b} ---')
    for i in range(max(0,a-4), min(len(lines), b+5)):
        s = lines[i].strip()
        if s: print(f'{i:6d}: {s}')
