#!/usr/bin/env python3
"""Print only markdown cells plus truncated outputs from a notebook. Usage: mdonly.py in.ipynb [max_output_chars]"""
import json, sys
nb = json.load(open(sys.argv[1]))
m = int(sys.argv[2]) if len(sys.argv) > 2 else 800
for i, c in enumerate(nb.get("cells", [])):
    if c.get("cell_type") == "markdown":
        print(f"\n#### MD {i}\n" + "".join(c.get("source", [])))
    else:
        for o in c.get("outputs", []) or []:
            t = o.get("text") or o.get("data", {}).get("text/plain") or ""
            t = "".join(t) if isinstance(t, list) else str(t)
            if t.strip():
                print(f"---- OUT {i}\n" + t[:m])
