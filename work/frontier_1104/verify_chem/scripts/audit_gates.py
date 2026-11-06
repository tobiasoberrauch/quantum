#!/usr/bin/env python3
"""Gate histogram and static Toffoli counts per circuit. Usage: audit_gates.py <dir> [<dir> ...]"""
import collections
import glob
import os
import re
import sys

import kickmix as km


def main() -> None:
    for d in sys.argv[1:]:
        files = sorted(glob.glob(d + '/angle_k_*.km*'), key=lambda p: int(re.search(r'_(\d+)\.', p).group(1)))
        hist, cond = collections.Counter(), collections.Counter()
        total = 0
        tmax = []
        for p in files:
            c = km.Circuit.from_file(p, format='kmb')
            st = c.operation_statistics()
            total += int(st.num_toffoli_like)
            tmax.append((int(st.num_toffoli_like), int(c.num_qubits)))
            for line in str(c).splitlines():
                parts = line.split()
                if not parts:
                    continue
                hist[parts[0]] += 1
                if ' if ' in line:
                    cond[parts[0]] += 1
        print(d)
        print(' per-k (static T, qubits):', tmax)
        print(' static T sum', total, '2x =', 2 * total)
        print(' opcodes', dict(hist.most_common()))
        print(' conditioned', dict(cond.most_common()))


if __name__ == '__main__':
    main()
