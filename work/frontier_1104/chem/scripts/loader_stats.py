import glob, os, sys
import kickmix as km, numpy as np
sys.path.insert(0, 'scripts')
import emit
base = sys.argv[1]
words = np.load('base/submission.npz')['angle_words']
out = []
for k in range(15):
    p = f'{base}/angle_k_{k}.kmb'
    c = km.Circuit.from_file(p, format='kmb')
    out.append((k, int(c.operation_statistics().num_toffoli_like), int(c.num_qubits)))
print(out, 'sum', sum(x[1] for x in out))
