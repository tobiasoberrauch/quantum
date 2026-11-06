#!/usr/bin/env python3
"""List files (name,size) of Kaggle kernels' outputs and datasets without downloading."""
import json, sys, os
from concurrent.futures import ThreadPoolExecutor
import kaggle
from kagglesdk.kernels.types.kernels_api_service import ApiListKernelSessionOutputRequest
api = kaggle.api

def list_kernel(ref):
    owner, slug = ref.split('/')
    out, tok = [], None
    with api.build_kaggle_client() as c:
        while True:
            r = ApiListKernelSessionOutputRequest()
            r.user_name, r.kernel_slug = owner, slug
            r.page_size = 200
            if tok: r.page_token = tok
            resp = c.kernels.kernels_api_client.list_kernel_session_output(r)
            for it in resp.files or []:
                out.append({'name': it.file_name, 'size': getattr(it, 'total_bytes', None) or getattr(it, 'size', None)})
            tok = resp.next_page_token
            if not tok: break
    return out

def list_dataset(ref):
    out, tok = [], None
    while True:
        resp = api.dataset_list_files(ref, page_token=tok, page_size=200)
        for f in resp.files:
            s = getattr(f, 'total_bytes', None)
            if s is None: s = getattr(f, 'size', None)
            out.append({'name': f.name, 'size': s})
        tok = resp.next_page_token
        if not tok: break
    return out

def main(listfile, outpath):
    srcs = [l.split() for l in open(listfile) if l.strip() and not l.startswith('#')]
    def one(s):
        kind, ref = s
        try:
            files = list_kernel(ref) if kind == 'k' else list_dataset(ref)
            return {'kind': kind, 'ref': ref, 'files': files}
        except Exception as ex:
            return {'kind': kind, 'ref': ref, 'error': repr(ex)[:400]}
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(one, srcs))
    json.dump(res, open(outpath, 'w'), indent=1)
    for r in res:
        if 'error' in r:
            print(r['kind'], r['ref'], 'ERROR', r['error'][:150]); continue
        fs = r['files']
        tot = sum(int(f['size'] or 0) for f in fs)
        kmb = [f for f in fs if '.kmb' in f['name']]
        npz = [f for f in fs if f['name'].endswith('.npz')]
        zips = [f for f in fs if f['name'].endswith(('.zip', '.xz', '.tar', '.tgz', '.gz'))]
        print(f"{r['kind']} {r['ref']:70s} n={len(fs):5d} tot={tot/2**20:9.1f}MB kmb={len(kmb)} npz={len(npz)} arch={[z['name'] for z in zips][:4]}")

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
