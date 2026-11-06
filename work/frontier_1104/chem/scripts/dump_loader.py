import sys, re, collections
import kickmix as km
c = km.Circuit.from_file(sys.argv[1], format='kmb')
s = str(c)
open(sys.argv[2], 'w').write(s)
lines = s.splitlines()
print(len(lines), c.num_qubits)
cnt = collections.Counter(l.split()[0] for l in lines if l.strip())
print(cnt)
print('\n'.join(lines[:40]))
