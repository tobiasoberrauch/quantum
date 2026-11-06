#!/usr/bin/env python3
"""Enumerate every import in the 25 public DQI delta files, classify it
(stdlib / local-delta / missing-private), and collect call-site evidence for
the missing modules so we can infer their required API surface.

Read-only over work/dqi_sources/. Writes one JSON under work/dqi_builder_recon/.
All parameters are guarded against None / '' / whitespace before use.
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys

STDLIB = {
    "functools", "pathlib", "sys", "contextlib", "json", "types", "inspect",
    "dataclasses", "itertools", "collections", "math", "operator", "typing",
    "abc", "enum", "copy", "io", "os", "re", "struct", "hashlib", "argparse",
    "time", "mmap", "numpy", "np", "scipy", "kickmix", "km", "__future__",
    "random",
}


def _guard_dir(d):
    if d is None or not isinstance(d, str):
        raise SystemExit("ERROR: sources dir must be a string")
    d = d.strip()
    if not d:
        raise SystemExit("ERROR: sources dir is empty")
    if not os.path.isdir(d):
        raise SystemExit(f"ERROR: no such directory: {d}")
    return d


def _module_of(node, fname):
    """Top-level dotted module an import refers to."""
    return node.module or ""


def analyze(sources_dir, out_path):
    sources_dir = _guard_dir(sources_dir)
    if out_path is None or not isinstance(out_path, str) or not out_path.strip():
        raise SystemExit("ERROR: out_path must be a non-empty string")
    out_path = out_path.strip()

    files = sorted(f for f in os.listdir(sources_dir)
                   if f.endswith(".py") and not f.startswith("_"))
    # Compare import names against module STEMS (no .py), so local cross-imports
    # (e.g. `from division import ...` -> division.py) are not false-flagged.
    delta_names = {os.path.splitext(f)[0] for f in files}

    imports = {}          # file -> list of (kind, module, names)
    missing_modules = {}  # module -> {files: [...], from_imports: [...]}
    call_sites = {}       # module -> set of attribute paths used (e.g. ar.K, gf.pow)

    for fname in files:
        path = os.path.join(sources_dir, fname)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                src = fh.read()
        except OSError as e:
            print(f"WARN: cannot read {path}: {e}", file=sys.stderr)
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            print(f"WARN: cannot parse {fname}: {e}", file=sys.stderr)
            continue

        rec = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    top = a.name.split(".")[0]
                    rec.append(("import", a.name, [a.asname or a.name]))
                    if top not in STDLIB and top not in delta_names:
                        missing_modules.setdefault(a.name, {"files": [], "from_imports": []})
                        missing_modules[a.name]["files"].append(fname)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                top = mod.split(".")[0]
                names = [a.asname or a.name for a in node.names]
                rec.append(("from", mod, names))
                if top not in STDLIB and top not in delta_names:
                    mm = missing_modules.setdefault(mod, {"files": [], "from_imports": []})
                    mm["files"].append(fname)
                    mm["from_imports"].extend(names)
        imports[fname] = rec

        # call-site evidence: attribute access on imported names of missing modules
        # Build local alias map for this file.
        alias = {}
        for kind, mod, names in rec:
            top = (mod or "").split(".")[0]
            if top in STDLIB or top in delta_names:
                continue
            if kind == "import":
                for nm in names:
                    alias[nm.split(".")[0]] = mod
            else:  # from X import a,b
                for nm in names:
                    if nm == "*":
                        continue
                    alias[nm] = mod
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                base = node
                chain = []
                while isinstance(base, ast.Attribute):
                    chain.append(base.attr)
                    base = base.value
                if isinstance(base, ast.Name) and base.id in alias:
                    chain.reverse()
                    attr_path = ".".join(chain)
                    call_sites.setdefault(alias[base.id], set()).add(attr_path)

    result = {
        "sources_dir": os.path.abspath(sources_dir),
        "delta_file_count": len(files),
        "delta_files": files,
        "imports_by_file": imports,
        "missing_modules": {
            m: {
                "files": sorted(set(v["files"])),
                "from_imports": sorted(set(v["from_imports"])),
                "call_sites": sorted(call_sites.get(m, set())),
            } for m, v in sorted(missing_modules.items())
        },
        "total_missing_modules": len(missing_modules),
    }

    d = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(d, exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(result, fh, indent=1)
    print(f"wrote {out_path}")
    print(f"delta files: {len(files)}")
    print(f"missing modules: {len(missing_modules)}")
    return result


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "work/dqi_sources"
    out = sys.argv[2] if len(sys.argv) > 2 else "work/dqi_builder_recon/import_analysis.json"
    analyze(src, out)
