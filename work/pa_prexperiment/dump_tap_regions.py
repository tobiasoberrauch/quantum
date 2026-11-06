"""Dump circuit text around the two tap clusters to understand the physical mechanism."""
import sys
from collections import Counter
import kickmix as km

CIRCUIT = 'work/frontier_scan/mwa_unpacked/invsqrt.kmb'
c = km.Circuit.from_file(CIRCUIT)
text = str(c)
lines = text.splitlines()
print('total text lines:', len(lines), file=sys.stderr)

def show(a, b, label):
    print(f'\n===== {label}  lines {a}..{b} =====')
    for i in range(a, min(b, len(lines))):
        s = lines[i]
        if s.strip():
            print(f'{i:6d}: {s}')

# first tap cluster (j=0..14) around line 15312
show(15290, 15345, 'cluster1 start (j=0,1,2)')
# second tap cluster (j=15..) around line 25680
show(25660, 25700, 'cluster2 start (j=15,16,17)')

# gate counts
names = Counter()
for ln in lines:
    s = ln.strip()
    if not s or s.startswith('#'):
        continue
    names[s.split()[0]] += 1
print('\nGate counts:', dict(names.most_common()), file=sys.stderr)

# registers
print('\nRegisters:', file=sys.stderr)
for name, reg in c.register_data.items():
    print(f'  {name}: {len(reg)} qubits -> {[str(q) for q in reg[:8]]}...', file=sys.stderr)
print('num_qubits:', c.num_qubits, file=sys.stderr)
