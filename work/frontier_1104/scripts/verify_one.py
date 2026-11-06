#!/usr/bin/env python3
"""Run one official verifier on one candidate described in candidates.json.

usage: verify_one.py <invsqrt|dqi|chem> <key> <candidates.json> <results_dir> <scratch_dir>
Materialises from the locator (zip/xz/plain) to scratch, verifies with the
unmodified verifier in data/verifiers using salt 'notebook-verification' and
default shots, removes large scratch, writes result JSON. One run per key.
"""
import hashlib, json, lzma, os, shutil, sys, time, zipfile

ROOT = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum'
SALT = 'notebook-verification'
REF = {'invsqrt': 2076774.233715282, 'dqi': 24439463583672.93, 'chem': 3355599588.3155375}


def open_loc(loc):
    if loc['inner'] is not None:
        raw = zipfile.ZipFile(loc['path']).open(loc['inner'])
    else:
        raw = open(loc['path'], 'rb')
    return lzma.open(raw) if loc['xz'] else raw


def write_loc(loc, dst, want):
    h = hashlib.sha256()
    with open_loc(loc) as fi, open(dst, 'wb') as fo:
        while True:
            b = fi.read(1 << 22)
            if not b:
                break
            h.update(b); fo.write(b)
    if h.hexdigest() != want:
        raise RuntimeError(f'sha mismatch {dst}: {h.hexdigest()} != {want}')


def main():
    comp, key, cand_json, results, scratch = sys.argv[1:6]
    out = os.path.join(results, f'{comp}_{key}.json')
    if os.path.exists(out):
        print('cached', out); return
    cand = json.load(open(cand_json))[comp][key]
    sys.path.insert(0, os.path.join(ROOT, 'data', 'verifiers'))
    t0 = time.time()
    d = os.path.join(scratch, f'{comp}_{key[:16]}')
    os.makedirs(d, exist_ok=True)
    rec = {'component': comp, 'key': key, 'sources': cand['sources']}
    try:
        if comp in ('invsqrt', 'dqi'):
            import kickmix as km
            fmt = cand.get('ext', 'kmb')
            p = os.path.join(d, f'{comp}.{fmt}')
            write_loc(cand['locs'][0], p, key)
            circ = km.Circuit.from_file(p, format=fmt)
            if comp == 'invsqrt':
                from invsqrt import verify_submission_invsqrt as v
                res = v.verify(circ, v.ProblemSpecInvSqrt.for_n_p(10), salt=SALT, max_workers=int(os.environ.get('VQ_WORKERS', '3')))
            else:
                from dqi import verify_submission_dqi as v
                res = v.verify(circ, v.ProblemSpecDQI.benchmark_instance(), salt=SALT, max_workers=int(os.environ.get('VQ_WORKERS', '3')))
        else:
            from dfthcsos import verify as v
            for name, loc in cand['locs'].items():
                write_loc(loc, os.path.join(d, name), cand['members'][name])
            res = v.verify(d, salt=SALT)
        keep = {k: x for k, x in res.items() if isinstance(x, (int, float, str, bool, type(None)))}
        rec.update(keep)
        rec['seconds'] = round(time.time() - t0, 1)
        if res.get('status') == 'PASS' and res.get('score'):
            rec['ratio'] = REF[comp] / float(res['score'])
    except Exception as ex:
        rec.update({'status': 'EXC', 'error': repr(ex)[:800], 'seconds': round(time.time() - t0, 1)})
    finally:
        shutil.rmtree(d, ignore_errors=True)
    json.dump(rec, open(out, 'w'), indent=1)
    print(json.dumps({k: rec.get(k) for k in ('component', 'key', 'status', 'score', 'ratio', 'num_qubits', 'toffoli_count', 'toffoli_equivalent', 'lambda_eff', 'seconds', 'error')}))


if __name__ == '__main__':
    main()
