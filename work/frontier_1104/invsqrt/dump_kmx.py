#!/usr/bin/env python3
"""Render a trusted-format circuit to kmx text. usage: dump_kmx.py in.kmb out.kmx"""
import sys
import kickmix as km
c = km.Circuit.from_file(sys.argv[1], format='kmb')
c.to_file(sys.argv[2], format='kmx')
print('qubits', c.num_qubits, 'ops', len(c))
s = c.operation_statistics()
print(s)
