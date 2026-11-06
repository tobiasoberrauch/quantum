#!/usr/bin/env python3
"""Apply line-addressed edits to kmx text.

Edits are {"delete": [lines], "after": {line: [text]}, "before": {line: [text]}, "replace": {line: text}},
all 0-based line numbers of the input file.
"""
from __future__ import annotations

import json
import sys


def apply(lines: list[str], edits: dict) -> list[str]:
    dele = set(edits.get('delete', []))
    after = {int(k): v for k, v in edits.get('after', {}).items()}
    before = {int(k): v for k, v in edits.get('before', {}).items()}
    repl = {int(k): v for k, v in edits.get('replace', {}).items()}
    out: list[str] = []
    for i, ln in enumerate(lines):
        out.extend(before.get(i, []))
        if i in repl:
            out.append(repl[i])
        elif i not in dele:
            out.append(ln)
        out.extend(after.get(i, []))
    return out


def edits_from_deletion(rec: dict) -> dict:
    """Converts a deltest.py 'ok' record into line edits."""
    e: dict = {'delete': [rec['line']], 'after': {}}
    for p in rec.get('patches', []):
        e['after'].setdefault(p['after'], []).extend(p['lines'])
        for store_line, text in p.get('toggles', []):
            e['after'].setdefault(store_line, []).append(text)
    return e


def merge(a: dict, b: dict) -> dict:
    out = {'delete': list(a.get('delete', [])) + list(b.get('delete', [])),
           'after': {int(k): list(v) for k, v in a.get('after', {}).items()},
           'before': {int(k): list(v) for k, v in a.get('before', {}).items()},
           'replace': {int(k): v for k, v in a.get('replace', {}).items()}}
    for k, v in b.get('after', {}).items():
        out['after'].setdefault(int(k), []).extend(v)
    for k, v in b.get('before', {}).items():
        out['before'].setdefault(int(k), []).extend(v)
    out['replace'].update({int(k): v for k, v in b.get('replace', {}).items()})
    return out


def main() -> None:
    src, edits_json, dst = sys.argv[1:4]
    with open(src, encoding='utf-8') as f:
        lines = f.read().splitlines()
    with open(edits_json, encoding='utf-8') as f:
        e = json.load(f)
    with open(dst, 'w', encoding='utf-8') as f:
        f.write('\n'.join(apply(lines, e)) + '\n')


if __name__ == '__main__':
    main()
