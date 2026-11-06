"""Task 2b: map the shipped circuit's toffoli-like ops by region + condition-depth,
to locate where the 1,289.29 mean-executed Toffolis live and find slack."""
import kickmix as km
from collections import Counter

c = km.Circuit.from_file('work/frontier_scan/mwa_unpacked/invsqrt.kmb')
lines = str(c).splitlines()

TOFF = {'CCX':1, 'CSWAP':1, 'CCZ':1}   # toffoli-like (CCZ=1 toffoli up to Cliffords)
depth = 0
region_static = Counter()
region_cond = Counter()      # ops inside >=1 PUSH_CONDITION (fractional applied)
total_static = 0
total_cond = 0
# track line -> condition depth
depth_by_line = []
for i, ln in enumerate(lines):
    s = ln.strip()
    if not s or s.startswith('#'):
        depth_by_line.append(depth); continue
    name = s.split()[0]
    if name == 'PUSH_CONDITION':
        depth += 1
        depth_by_line.append(depth); continue
    if name == 'POP_CONDITION':
        depth_by_line.append(depth); depth -= 1; continue
    depth_by_line.append(depth)
    if name in TOFF:
        total_static += 1
        if depth > 0: total_cond += 1

print(f'total static toffoli-like ops = {total_static}')
print(f'  of which inside >=1 PUSH_CONDITION (fractional applied) = {total_cond} ({total_cond/total_static:.1%})')
print(f'  unconditional (always applied) = {total_static-total_cond}')
print(f'implied mean-executed lower bound (uncond + fraction of cond) ~ {total_static-total_cond} .. {total_static}')
print(f'(shipped mean_executed_Toffolis = 1289.29)')

# histogram of toffoli ops over line ranges (buckets of 2000 lines)
import numpy as np
hist = Counter()
for i, ln in enumerate(lines):
    s = ln.strip()
    if not s or s.startswith('#'): continue
    if s.split()[0] in TOFF:
        hist[i//2000] += 1
print('\ntoffoli-like ops per 2000-line bucket (line_start : count : cond-depth-at-bucket):')
for bkt in sorted(hist):
    lo = bkt*2000
    # sample condition depth in this bucket
    ds = [d for d in depth_by_line[lo:lo+2000] if d>0]
    frac_cond = len(ds)/max(1,len([1 for _ in range(lo,min(lo+2000,len(lines))) ]))
    print(f'  {lo:6d}-{lo+2000:6d} : {hist[bkt]:5d}   (max depth {max(depth_by_line[lo:lo+2000]) if lo+2000<=len(depth_by_line) else 0})')
