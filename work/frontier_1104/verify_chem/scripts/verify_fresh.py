#!/usr/bin/env python3
"""Fresh-process call of the unmodified official dfthcsos verifier.

Usage: python -I -B -X pycache_prefix=<empty> verify_fresh.py <member_dir> <salt> [shots] [out.json]
"""
import json
import sys
import time

VERIFIERS = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/data/verifiers'
REF_COST = 3355599588.3155375


def main() -> None:
    member, salt = sys.argv[1], sys.argv[2]
    shots = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else None
    sys.path.insert(0, VERIFIERS)
    from dfthcsos import verify as official
    t0 = time.time()
    kwargs = {} if shots is None else {'shots_per_address': shots}
    try:
        r = official.verify(member, salt=salt, **kwargs)
    except Exception as ex:  # a rejection is a result, report it
        out = {'member': member, 'salt': salt, 'shots': shots, 'status': 'FAIL', 'error': f'{type(ex).__name__}: {ex}'}
    else:
        m, rs = r['metrics'], r['resources']
        out = {
            'member': member, 'salt': salt, 'shots': shots, 'status': r['status'], 'score': r['score'],
            'ratio': REF_COST / r['score'], 'lambda_eff': m['lambda_eff'], 'Lambda': m['Lambda'],
            'E_gap': m['E_gap'], 'E_SOS': m['E_SOS'], 'error_1': m['error_1'], 'error_2': m['error_2'],
            'T': r['toffoli_count'], 'Q': r['num_qubits'], 'brot': r['brot'], 'J': r['batch_size'],
            'K': r['num_circuits'], 'angT': rs['angles_toffoli'], 'heurT': rs['heuristic_toffoli'],
            'angQ': rs['angles_qubits'], 'verified_shots': r['verified_shots'], 'sha': r['submission_sha256'],
            'indep_score': m['lambda_eff'] * r['toffoli_count'] * r['num_qubits'],
            'secs': round(time.time() - t0, 1), 'verifier_file': official.__file__,
        }
    text = json.dumps(out, indent=1)
    print(text)
    if len(sys.argv) > 4:
        with open(sys.argv[4], 'w', encoding='utf-8') as f:
            f.write(text)


if __name__ == '__main__':
    main()
