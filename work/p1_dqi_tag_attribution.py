"""P1.1a: attribute Toffoli-like ops to INFO_TAG blocks in dqi.kmb.

.kmb SOA: TYPES (1 byte/op); TAGS packet holds one string per INFO_TAG op (0x06) in
stream order. Tags come as @enter:X / @exit:X pairs -> maintain a stack; count 3q ops
(CCZ/CCX/CSWAP + _IF = costed Toffoli-likes) under the innermost active tag.
"""
import importlib.util
import numpy as np
from collections import defaultdict

spec = importlib.util.spec_from_file_location('wl', 'work/dqi_sources/width_liveness.py')
wl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wl)

r = wl.KmbReader('work/frontier_scan/mwa_unpacked/dqi.kmb')
t = r.types
N = r.num_ops
TAG = 0x06
TOFFOLI = {0x30, 0xB0, 0x31, 0xB1, 0x32, 0xB2}
tag_idx = 0
stack = []
counts = defaultdict(int)
tally = defaultdict(int)   # total ops per block (all types)
tagpos = np.flatnonzero(t == TAG)
tagset = set(tagpos.tolist()) if len(tagpos) < 200000 else None

# vectorized-ish single pass (58M ops: pure python loop too slow -> use numpy tricks)
# Build per-op "current innermost tag" via scan over enter/exit events only.
is_tag = (t == TAG).astype(bool)
# classify tag ops by their string
enter = np.zeros(N, dtype=bool)
exit_ = np.zeros(N, dtype=bool)
names = {}
ti = 0
for p in tagpos:
    s = r.tag_strings[ti]
    ti += 1
    names[int(p)] = s
    if s.startswith('@enter:'):
        enter[p] = True
    elif s.startswith('@exit:'):
        exit_[p] = True
print('tags parsed:', ti, 'distinct:', len(set(names.values())))

# scan: between consecutive tag events, innermost tag = top of stack
events = np.flatnonzero(enter | exit_)
seg_tag = np.full(len(events) + 1, '', dtype=object)
stk = []
for i, e in enumerate(events):
    s = names[int(e)]
    if s.startswith('@enter:'):
        stk.append(s[7:])
        seg_tag[i] = stk[-1]
    else:
        # exit: pop (tolerate mismatch by popping matching name if present)
        nm = s[6:]
        if stk and stk[-1] == nm:
            stk.pop()
        elif nm in stk:
            while stk and stk.pop() != nm:
                pass
        seg_tag[i] = stk[-1] if stk else '<root>'
seg_tag[len(events)] = stk[-1] if stk else '<root>'

# boundaries: event positions define segments [events[i], events[i+1])
bounds = np.concatenate(([0], events, [N]))
# count toffolis per segment
toff = np.isin(t, list(TOFFOLI))
prefix2 = np.concatenate(([0], np.cumsum(toff)))
seg_toff = prefix2[bounds[1:]] - prefix2[bounds[:-1]]
# all-ops per segment
seg_ops = np.diff(bounds)

agg_toff = defaultdict(int)
agg_ops = defaultdict(int)
# segment i covers [bounds[i], bounds[i+1]); its enclosing state is AFTER event i-1
# (seg_tag[i-1]), or '<root>' for segment 0. (Original code had an off-by-one here.)
for i in range(len(events) + 1):
    label = '<root>' if i == 0 else seg_tag[i - 1]
    agg_toff[label] += int(seg_toff[i])
    agg_ops[label] += int(seg_ops[i])

total_toff = sum(agg_toff.values())
print(f'\ntotal 3q (Toffoli-like) ops: {total_toff}')
print(f'{"block":38} {"toffolis":>10} {"%":>7} {"ops":>12}')
for b, v in sorted(agg_toff.items(), key=lambda kv: -kv[1]):
    print(f'{b:38} {v:>10} {100 * v / total_toff:>6.2f}% {agg_ops[b]:>12}')
