#!/usr/bin/env python3
"""Package work/qvc008/submission/ into qvc-008.zip with exactly the 18
manifest members in manifest order (ZIP_DEFLATED, mirroring heliosli's
notebook and our prior submission zips), then re-verify every member's
SHA-256 from inside the zip against the manifest."""
import hashlib
import json
import os
import sys
import zipfile

BASE = os.path.dirname(os.path.abspath(__file__))
SUB = os.path.join(BASE, 'submission')
ZIP_PATH = os.path.join(BASE, 'qvc-008.zip')


def fail(msg: str) -> None:
    print(f'FATAL: {msg}', file=sys.stderr)
    sys.exit(1)


def sha256_bytes(data: bytes) -> str:
    if data is None:
        raise ValueError('sha256_bytes: data is None')
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    meta_path = os.path.join(BASE, 'extracted.json')
    if not os.path.isfile(meta_path):
        fail('extracted.json missing - run extract.py first')
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
    except (OSError, json.JSONDecodeError) as ex:
        fail(f'cannot read extracted.json: {ex}')
    files = meta.get('files') if isinstance(meta, dict) else None
    if not isinstance(files, list) or len(files) != 18:
        fail('extracted.json must list exactly 18 files')

    if os.path.exists(ZIP_PATH):
        os.remove(ZIP_PATH)
    with zipfile.ZipFile(ZIP_PATH, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for item in files:
            fname = item.get('file')
            if not isinstance(fname, str) or fname.strip() == '':
                fail(f'bad manifest file entry: {item!r}')
            src = os.path.join(SUB, fname)
            if not os.path.isfile(src):
                fail(f'missing local file for zip: {src}')
            z.write(src, fname)

    # Re-verify from inside the zip.
    with zipfile.ZipFile(ZIP_PATH, 'r') as z:
        names = [n for n in z.namelist() if not n.endswith('/')]
        if len(names) != 18:
            fail(f'zip has {len(names)} non-directory members, want 18')
        for item in files:
            fname = item['file']
            if fname not in names:
                fail(f'zip missing member {fname}')
            got = sha256_bytes(z.read(fname))
            want = item['sha256'].lower()
            if got != want:
                fail(f'ZIP SHA MISMATCH {fname}: got {got} want {want}')
            print(f'zip sha256 OK  {fname:35s} {got[:16]}...')
    size = os.path.getsize(ZIP_PATH)
    print(f'wrote {ZIP_PATH} ({size} bytes, {size / 2**20:.1f} MiB), 18 members verified')


if __name__ == '__main__':
    main()
