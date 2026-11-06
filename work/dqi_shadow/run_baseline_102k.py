#!/usr/bin/env python3
"""Run the official DQI verifier at 102,400 shots on the reference circuit.

Works around the memory issue where _circuit_sha256 re-serializes the 845 MB
circuit into a BytesIO buffer by patching it to hash the .kmb file directly.
The file was written by kickmix's to_file(), so its bytes ARE the canonical
serialization.

Usage: .venv/bin/python work/dqi_shadow/run_baseline_102k.py
Writes: work/dqi_shadow/baseline_102k.json
"""
from __future__ import annotations
import hashlib
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'data', 'verifiers', 'dqi'))

KMB_PATH = os.path.join(REPO, 'work', 'dqi_builder_recon', 'reference.kmb')
OUT_PATH = os.path.join(REPO, 'work', 'dqi_shadow', 'baseline_102k.json')


def main() -> None:
    if not os.path.isfile(KMB_PATH):
        raise SystemExit(f"ERROR: {KMB_PATH} not found")

    # Compute SHA-256 of the .kmb file (canonical serialization).
    h = hashlib.sha256()
    with open(KMB_PATH, 'rb') as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    file_hash = h.hexdigest()
    print(f"[baseline] kmb sha256 = {file_hash}", file=sys.stderr)

    # Import verifier and patch _circuit_sha256 to avoid re-serialization.
    import verify_submission_dqi as vsd

    def _patched_circuit_sha256(circuit):
        return file_hash

    vsd._circuit_sha256 = _patched_circuit_sha256

    import kickmix as km
    print("[baseline] loading circuit ...", file=sys.stderr)
    circuit = km.Circuit.from_file(KMB_PATH, format='kmb')
    print(f"[baseline] loaded: Q={circuit.num_qubits}, ops={len(circuit)}, "
          f"static_T={circuit.operation_statistics().num_toffoli_like}", file=sys.stderr)

    spec = vsd.ProblemSpecDQI.benchmark_instance(num_shots=102_400)
    print(f"[baseline] verifying at {spec.num_shots} shots ...", file=sys.stderr)

    result = vsd.verify(circuit, spec, max_workers=4)
    result['circuit_sha256_from_file'] = file_hash

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, 'w') as f:
        json.dump(result, f, indent=2)
    print(json.dumps({k: result[k] for k in
                      ('status', 'score', 'repetition_factor', 'toffoli_count',
                       'max_toffoli_count', 'num_qubits', 'value_errors',
                       'phase_errors', 'verified_shots')}, indent=2))
    print(f"[baseline] wrote {OUT_PATH}", file=sys.stderr)


if __name__ == '__main__':
    main()
