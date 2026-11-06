#!/usr/bin/env python3
"""Run the official verifiers on the extracted portfolio files.

Usage: verify_all.py [invsqrt|dqi|dfthcsos|all]
Results are merged into work/qvc008/verify_results.json; GM is computed when
all three are present and PASS. Mirrors heliosli's notebook exactly:
Python API calls with salt from the manifest, default shot counts.
"""
import json
import math
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
SUB = os.path.join(BASE, 'submission')
REPO = os.path.abspath(os.path.join(BASE, '..', '..'))
RESULTS_PATH = os.path.join(BASE, 'verify_results.json')


def fail(msg: str) -> None:
    print(f'FATAL: {msg}', file=sys.stderr)
    sys.exit(1)


def load_meta() -> dict:
    p = os.path.join(BASE, 'extracted.json')
    if not os.path.isfile(p):
        fail('extracted.json missing - run extract.py first')
    try:
        with open(p, 'r', encoding='utf-8') as f:
            meta = json.load(f)
    except (OSError, json.JSONDecodeError) as ex:
        fail(f'cannot read extracted.json: {ex}')
    if not isinstance(meta, dict) or not isinstance(meta.get('reference_costs'), dict):
        fail('extracted.json malformed')
    return meta


def load_results() -> dict:
    if os.path.isfile(RESULTS_PATH):
        try:
            with open(RESULTS_PATH, 'r', encoding='utf-8') as f:
                r = json.load(f)
            if isinstance(r, dict):
                return r
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def save_results(results: dict) -> None:
    with open(RESULTS_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)


def check_file(name: str) -> str:
    p = os.path.join(SUB, name)
    if not os.path.isfile(p):
        fail(f'missing extracted file: {p}')
    return p


def run_invsqrt(salt: str) -> dict:
    import kickmix as km
    sys.path.insert(0, os.path.join(REPO, 'data', 'verifiers'))
    from invsqrt import verify_submission_invsqrt as vinv
    path = check_file('invsqrt.kmb')
    t0 = time.time()
    circ = km.Circuit.from_file(path, format='kmb')
    res = vinv.verify(circ, vinv.ProblemSpecInvSqrt.for_n_p(10), salt=salt)
    dt = time.time() - t0
    out = {'status': res.get('status'), 'score': res.get('score'),
           'num_qubits': res.get('num_qubits'),
           'toffoli_equivalent': res.get('toffoli_equivalent'),
           'seconds': round(dt, 1)}
    print(f'invsqrt: {json.dumps(out)}')
    return out


def run_dqi(salt: str) -> dict:
    import kickmix as km
    sys.path.insert(0, os.path.join(REPO, 'data', 'verifiers'))
    from dqi import verify_submission_dqi as vdqi
    path = check_file('dqi.kmb')
    t0 = time.time()
    circ = km.Circuit.from_file(path, format='kmb')
    res = vdqi.verify(circ, vdqi.ProblemSpecDQI.benchmark_instance(), salt=salt)
    dt = time.time() - t0
    out = {'status': res.get('status'), 'score': res.get('score'),
           'num_qubits': res.get('num_qubits'),
           'toffoli_count': res.get('toffoli_count'),
           'value_errors': res.get('value_errors', 0),
           'phase_errors': res.get('phase_errors', 0),
           'repetition_factor': res.get('repetition_factor'),
           'seconds': round(dt, 1)}
    print(f'dqi: {json.dumps(out)}')
    return out


def run_dfthcsos(salt: str) -> dict:
    sys.path.insert(0, os.path.join(REPO, 'data', 'verifiers'))
    from dfthcsos import verify as vdft
    d = os.path.join(SUB, 'dfthcsos')
    if not os.path.isfile(os.path.join(d, 'submission.npz')):
        fail('dfthcsos/submission.npz missing - run extract.py first')
    t0 = time.time()
    res = vdft.verify(d, salt=salt)
    dt = time.time() - t0
    out = {'status': res.get('status'), 'score': res.get('score'),
           'lambda_eff': res.get('lambda_eff'),
           'toffoli_count': res.get('toffoli_count'),
           'num_qubits': res.get('num_qubits'),
           'error_2': res.get('error_2'),
           'verified_shots': res.get('verified_shots'),
           'seconds': round(dt, 1)}
    print(f'dfthcsos: {json.dumps(out)}')
    return out


def compute_gm(meta: dict, results: dict) -> float | None:
    ref = meta['reference_costs']
    ratios = []
    for task in ('invsqrt', 'dqi', 'dfthcsos'):
        r = results.get(task)
        if not isinstance(r, dict) or r.get('status') != 'PASS' or r.get('score') in (None, 0):
            return None
        ratios.append(float(ref[task]) / float(r['score']))
    gm = math.prod(ratios) ** (1 / 3)
    for task, ratio in zip(('invsqrt', 'dqi', 'dfthcsos'), ratios):
        results[task]['ratio'] = ratio
    results['ratios'] = dict(zip(('invsqrt', 'dqi', 'dfthcsos'), ratios))
    results['gm'] = gm
    return gm


def main() -> None:
    argv = [a for a in sys.argv[1:] if a and str(a).strip()]
    task = argv[0] if argv else 'all'
    if task not in ('invsqrt', 'dqi', 'dfthcsos', 'all'):
        fail(f'unknown task {task!r}')
    meta = load_meta()
    salt = meta.get('salt') or ''
    results = load_results()
    runners = {'invsqrt': run_invsqrt, 'dqi': run_dqi, 'dfthcsos': run_dfthcsos}
    todo = list(runners) if task == 'all' else [task]
    for t in todo:
        results[t] = runners[t](salt)
        save_results(results)
    gm = compute_gm(meta, results)
    save_results(results)
    if gm is not None:
        print(f'LOCAL GM = {gm:.5f}')
    else:
        print('GM not computable yet (missing/failed component)')


if __name__ == '__main__':
    main()
