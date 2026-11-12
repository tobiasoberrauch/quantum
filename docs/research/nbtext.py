#!/usr/bin/env python3
"""Print notebook cells as readable text. Usage: nbtext.py <file.ipynb> [max_chars]"""
import json
import sys


def main():
    path = sys.argv[1]
    max_chars = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
    with open(path) as f:
        nb = json.load(f)
    out = []
    for i, cell in enumerate(nb.get("cells", [])):
        src = "".join(cell.get("source", []))
        kind = cell.get("cell_type", "?")
        out.append(f"--- [{i}] {kind} ---")
        out.append(src)
        for o in cell.get("outputs", []):
            if "text" in o:
                out.append(">>> " + "".join(o["text"])[:2000])
            elif "data" in o and "text/plain" in o["data"]:
                out.append(">>> " + "".join(o["data"]["text/plain"])[:2000])
    text = "\n".join(out)
    print(text[:max_chars])
    if len(text) > max_chars:
        print(f"\n[... truncated, total {len(text)} chars]")


if __name__ == "__main__":
    main()
