#!/usr/bin/env python3
"""Dump a notebook's cells as plain text without executing anything. Usage: nb2txt.py in.ipynb out.txt"""
import json, sys
nb = json.load(open(sys.argv[1]))
with open(sys.argv[2], "w") as f:
    for i, c in enumerate(nb.get("cells", [])):
        f.write(f"\n#### CELL {i} [{c.get('cell_type')}]\n")
        f.write("".join(c.get("source", [])) + "\n")
        for o in c.get("outputs", []) or []:
            t = o.get("text") or o.get("data", {}).get("text/plain") or ""
            t = "".join(t) if isinstance(t, list) else str(t)
            if t.strip():
                f.write("---- OUTPUT\n" + t[:6000] + "\n")
