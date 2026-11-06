#!/usr/bin/env python3
"""Index circuits across download dirs without extracting to disk.

Run with `python -I`. Treats everything as data: zip members read via zipfile,
xz streamed via lzma, nothing executed. Output: candidates.json with
{invsqrt: {sha: {...sources}}, dqi: {...}, chem: {key: {members: {name: sha}, sources}}}.
"""
import hashlib, io, json, lzma, os, re, sys, zipfile

CHUNK = 1 << 22
ANGLE = re.compile(r'^(?:.*?)(angle_k_\d+\.(?:kmb|kmx))$')


def sha_stream(fh) -> tuple[str, int]:
    h = hashlib.sha256(); n = 0
    while True:
        b = fh.read(CHUNK)
        if not b:
            return h.hexdigest(), n
        h.update(b); n += len(b)


class Member:
    """Locator of one logical file: (container path, member-in-zip or None, xz flag)."""
    def __init__(self, path, inner=None, xz=False, zipname=None):
        self.path, self.inner, self.xz, self.zipname = path, inner, xz, zipname

    def open(self, zc):
        if self.inner is not None:
            raw = zc[self.path].open(self.inner)
        else:
            raw = open(self.path, 'rb')
        return lzma.open(raw) if self.xz else raw

    def loc(self):
        return {'path': self.path, 'inner': self.inner, 'xz': self.xz}


def classify(name: str):
    """Return (component, canonical member) for an arbitrary file name."""
    n = name.replace('\\', '/')
    xz = n.endswith('.xz')
    if xz:
        n = n[:-3]
    base = n.rsplit('/', 1)[-1]
    # flattened names, e.g. dfthcsos__angle_k_0.kmb
    m = re.search(r'(angle_k_\d+\.km[bx])$', base)
    if m:
        return 'chem', m.group(1), xz
    if base.endswith('submission.npz'):
        return 'chem', 'submission.npz', xz
    if re.search(r'(^|/)circuits/invsqrt/[^/]+\.km[bx]$', n):
        return 'invsqrt', 'invsqrt.' + base.rsplit('.', 1)[1], xz
    if re.search(r'(^|/)circuits/dqi/[^/]+\.km[bx]$', n):
        return 'dqi', 'dqi.' + base.rsplit('.', 1)[1], xz
    if base in ('invsqrt.kmb', 'invsqrt.kmx'):
        return 'invsqrt', base, xz
    if base in ('dqi.kmb', 'dqi.kmx'):
        return 'dqi', base, xz
    return None, None, xz


def group_dir(name: str) -> str:
    n = name.replace('\\', '/')
    return n.rsplit('/', 1)[0] if '/' in n else ''


def scan_source(src_dir: str, zc: dict) -> list:
    out = []
    for root, _, files in os.walk(src_dir):
        for f in files:
            p = os.path.join(root, f)
            rel = os.path.relpath(p, src_dir)
            is_zip = False
            if f.endswith(('.zip', '.zip.bin')):
                is_zip = True
            if is_zip and zipfile.is_zipfile(p):
                z = zipfile.ZipFile(p)
                zc[p] = z
                for info in z.infolist():
                    if info.is_dir():
                        continue
                    comp, canon, xz = classify(info.filename)
                    if comp:
                        out.append((comp, canon, f'{rel}!{group_dir(info.filename)}', Member(p, info.filename, xz), info.file_size))
            else:
                comp, canon, xz = classify(f)
                if comp:
                    out.append((comp, canon, group_dir(rel), Member(p, None, xz), os.path.getsize(p)))
    return out


def main(dl_root: str, out_json: str, cache_json: str, srcs: list) -> None:
    cache = json.load(open(cache_json)) if os.path.exists(cache_json) else {}
    res = {'invsqrt': {}, 'dqi': {}, 'chem': {}}
    zc = {}
    names = srcs or sorted(d for d in os.listdir(dl_root) if d.startswith(('k__', 'd__', 'f__', 'k2__', 'k5__', 'd5__')))
    for name in names:
        src = os.path.join(dl_root, name)
        items = scan_source(src, zc)
        groups = {}
        for comp, canon, grp, mem, size in items:
            key = f'{mem.path}|{mem.inner}'
            st = os.stat(mem.path)
            ckey = f'{key}|{st.st_size}|{int(st.st_mtime)}'
            if ckey not in cache:
                with mem.open(zc) as fh:
                    sha, n = sha_stream(fh)
                cache[ckey] = {'sha': sha, 'size': n}
                json.dump(cache, open(cache_json, 'w'))
            sha, n = cache[ckey]['sha'], cache[ckey]['size']
            if comp in ('invsqrt', 'dqi'):
                e = res[comp].setdefault(sha, {'size': n, 'ext': canon.rsplit('.', 1)[1], 'locs': [], 'sources': []})
                e['locs'].append(mem.loc())
                if name not in e['sources']:
                    e['sources'].append(name)
            else:
                groups.setdefault(grp, {})[canon] = (sha, n, mem)
        for grp, members in groups.items():
            angle = sorted(k for k in members if k.startswith('angle_k_'))
            if 'submission.npz' not in members or not angle:
                print(f'INCOMPLETE chem {name}:{grp} members={len(members)}')
                continue
            idx = sorted(int(re.search(r'(\d+)\.', k).group(1)) for k in angle)
            if idx != list(range(len(idx))):
                print(f'NONCONTIGUOUS chem {name}:{grp} {idx}')
                continue
            blob = json.dumps(sorted((k, v[0]) for k, v in members.items())).encode()
            ck = hashlib.sha256(blob).hexdigest()
            e = res['chem'].setdefault(ck, {'n_angle': len(angle), 'members': {k: v[0] for k, v in members.items()},
                                            'locs': {k: v[2].loc() for k, v in members.items()}, 'sources': []})
            if name not in e['sources']:
                e['sources'].append(name)
    json.dump(res, open(out_json, 'w'), indent=1)
    for c in res:
        print(c, len(res[c]))
        for k, v in res[c].items():
            print(' ', k[:12], v.get('size', v.get('n_angle')), v['sources'][:4], ('+%d' % (len(v['sources'])-4)) if len(v['sources']) > 4 else '')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:])
