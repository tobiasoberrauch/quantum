#!/usr/bin/env python3
"""Extract the 18 portfolio files from the heliosli/qcc-circuits-live dataset
into work/qvc008/submission/, decompressing per manifest `stored_as`, and
SHA-256-verify every file. Stops on any mismatch."""
import hashlib
import json
import lzma
import os
import shutil
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, 'src')
SUB = os.path.join(BASE, 'submission')


def fail(msg: str) -> None:
    print(f'FATAL: {msg}', file=sys.stderr)
    sys.exit(1)


def sha256(path: str | None) -> str:
    if not path or not isinstance(path, str) or path.strip() == '':
        raise ValueError('sha256: path must be a non-empty string')
    if not os.path.isfile(path):
        raise ValueError(f'sha256: not a file: {path!r}')
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 22), b''):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    manifest_path = os.path.join(SRC, 'QCC_RELEASE_MANIFEST.json')
    if not os.path.isfile(manifest_path):
        fail(f'manifest missing: {manifest_path}')
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
    except (OSError, json.JSONDecodeError) as ex:
        fail(f'cannot read manifest: {ex}')
    if not isinstance(manifest, dict):
        fail('manifest is not a JSON object')

    portfolio = manifest.get('portfolio')
    if not isinstance(portfolio, str) or portfolio.strip() == '':
        fail('manifest has no portfolio string')
    if portfolio != 'v65w_sx_sy7':
        fail(f'unexpected portfolio {portfolio!r} (want v65w_sx_sy7)')

    salt = manifest.get('salt')
    if not isinstance(salt, str):
        salt = ''

    files = manifest.get('files')
    if not isinstance(files, list) or len(files) == 0:
        fail('manifest has no files list')
    if len(files) != 18:
        fail(f'expected 18 files in manifest, got {len(files)}')

    ref_costs = manifest.get('reference_costs')
    if not isinstance(ref_costs, dict):
        fail('manifest has no reference_costs dict')

    # Fresh output dir.
    if os.path.exists(SUB):
        shutil.rmtree(SUB)
    os.makedirs(SUB, exist_ok=True)

    for i, item in enumerate(files):
        if not isinstance(item, dict):
            fail(f'files[{i}] is not an object')
        fname = item.get('file')
        stored = item.get('stored_as')
        want_sha = item.get('sha256')
        if not isinstance(fname, str) or fname.strip() == '' or os.path.isabs(fname) \
                or '..' in fname.replace('\\', '/').split('/'):
            fail(f'files[{i}].file unsafe or empty: {fname!r}')
        if not isinstance(stored, str) or stored.strip() == '' or os.path.isabs(stored) \
                or '..' in stored.replace('\\', '/').split('/'):
            fail(f'files[{i}].stored_as unsafe or empty: {stored!r}')
        if not isinstance(want_sha, str) or len(want_sha) != 64:
            fail(f'files[{i}].sha256 invalid: {want_sha!r}')
        src_path = os.path.join(SRC, stored)
        if not os.path.isfile(src_path):
            fail(f'source file missing in dataset: {src_path}')
        dst_path = os.path.join(SUB, fname)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        if stored.endswith('.xz'):
            with lzma.open(src_path, 'rb') as fi, open(dst_path, 'wb') as fo:
                shutil.copyfileobj(fi, fo, 1 << 22)
        else:
            shutil.copyfile(src_path, dst_path)
        got = sha256(dst_path)
        if got != want_sha.lower():
            fail(f'SHA MISMATCH {fname}: got {got} want {want_sha}')
        print(f'sha256 OK  {fname:35s} {got}')

    out = {
        'portfolio': portfolio,
        'salt': salt,
        'reference_costs': ref_costs,
        'files': [
            {'file': it['file'], 'stored_as': it['stored_as'], 'sha256': it['sha256']}
            for it in files
        ],
    }
    with open(os.path.join(BASE, 'extracted.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2)
    print(f'{len(files)} files extracted and SHA-256 verified -> {SUB}')


if __name__ == '__main__':
    main()
