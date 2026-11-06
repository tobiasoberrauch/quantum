#!/usr/bin/env python3
"""Re-extract build/submission.zip into a temp dir and verify from those bytes (official verifiers, default shots)."""
import hashlib, json, math, multiprocessing as mp, os, shutil, sys, tempfile, time, zipfile
ROOT = '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum'
F = ROOT + '/work/frontier_1104/frontier'
SALT = 'notebook-verification'
REF = {'invsqrt': 2076774.233715282, 'dqi': 24439463583672.93, 'dfthcsos': 3355599588.3155375}
def run(args):
    task, d, workers = args
    sys.path.insert(0, ROOT + '/data/verifiers')
    t0 = time.time()
    if task == 'dfthcsos':
        from dfthcsos import verify as v
        r = v.verify(os.path.join(d, 'dfthcsos'), salt=SALT)
    else:
        import kickmix as km
        c = km.Circuit.from_file(os.path.join(d, task + '.kmb'), format='kmb')
        if task == 'invsqrt':
            from invsqrt import verify_submission_invsqrt as v
            r = v.verify(c, v.ProblemSpecInvSqrt.for_n_p(10), salt=SALT, max_workers=workers)
        else:
            from dqi import verify_submission_dqi as v
            r = v.verify(c, v.ProblemSpecDQI.benchmark_instance(), salt=SALT, max_workers=workers)
    keep = {k: x for k, x in r.items() if isinstance(x, (int, float, str, bool, type(None)))}
    keep['seconds'] = round(time.time() - t0, 1); keep['task'] = task
    return keep
if __name__ == '__main__':
    tmp = tempfile.mkdtemp(prefix='zipverify_', dir=F + '/scratch')
    try:
        man = json.load(open(F + '/build/build_manifest.json'))['members']
        with zipfile.ZipFile(F + '/build/submission.zip') as z:
            for n in z.namelist():
                if n.endswith('/'): continue
                assert n in man and '..' not in n and not os.path.isabs(n), n
                p = os.path.join(tmp, n); os.makedirs(os.path.dirname(p), exist_ok=True)
                h = hashlib.sha256()
                with z.open(n) as fi, open(p, 'wb') as fo:
                    for b in iter(lambda: fi.read(1 << 22), b''):
                        h.update(b); fo.write(b)
                assert h.hexdigest() == man[n]['sha256'], n
        print('re-extracted 18 members, SHA-256 OK', flush=True)
        w = int(sys.argv[1]) if len(sys.argv) > 1 else 3
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(3, mp_context=mp.get_context('fork')) as pool:
            res = list(pool.map(run, [('dfthcsos', tmp, 1), ('invsqrt', tmp, w), ('dqi', tmp, w)]))
        out = {r['task']: r for r in res}
        ratios = {}
        for t, r in out.items():
            ratios[t] = REF[t] / float(r['score']) if r.get('status') == 'PASS' else None
            r['ratio'] = ratios[t]
            print(t, r['status'], r['score'], ratios[t], r.get('num_qubits'), r.get('toffoli_count'), r.get('seconds'), flush=True)
        gm = math.prod(ratios.values()) ** (1 / 3)
        out['gm'] = gm
        json.dump(out, open(F + '/build/zip_verify.json', 'w'), indent=1)
        print('GM', gm)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
