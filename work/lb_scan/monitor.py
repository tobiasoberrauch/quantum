#!/usr/bin/env python3
"""One-shot LB/dataset/kernel snapshot for the QVC competition monitor.

Writes a JSON snapshot to work/lb_scan/monitor/snapshot-<ts>.json and prints a
compact change summary vs the previous snapshot (if any).
"""
import json, subprocess, sys, time, hashlib
from pathlib import Path

ROOT = Path("/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum")
KAGGLE = str(ROOT / ".venv/bin/kaggle")
COMP = "google-verifiable-quantum-circuit-compilation"
OUT = ROOT / "work/lb_scan/monitor"
OUT.mkdir(parents=True, exist_ok=True)

WATCH_DATASETS = [
    "heliosli/qcc-circuits-live",
    "yoyobar/qcc-local-sota-20261031",
    "somejoint/qcc-dqi-892-q26",
    "manwithacat/vqcc-apache-public-circuits",
    "busyaprime/33-qcc-v8-members",
    "dmitriigluzdov/vqcc-femoco-public-factorization",
]


def run(args):
    r = subprocess.run([KAGGLE] + args, capture_output=True, text=True, timeout=300)
    return r.stdout


def lb_top():
    out = run(["competitions", "leaderboard", "-c", COMP, "--show"])
    rows = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[0].isdigit():
            try:
                rows.append({"team": " ".join(parts[1:-2]), "date": parts[-2], "score": float(parts[-1])})
            except ValueError:
                pass
    return rows[:20]


def dataset_fingerprint(slug):
    out = run(["datasets", "files", slug, "--page-size", "200"])
    h = hashlib.sha256(out.encode()).hexdigest()[:12]
    # count files + latest creation date
    n = sum(1 for l in out.splitlines() if l.strip() and not l.startswith("name") and not l.startswith("---") and not l.startswith("Next Page"))
    dates = [l.split()[-1] for l in out.splitlines() if len(l.split()) >= 3 and l.split()[-1].startswith("2026")]
    return {"files_hash": h, "n_files_page1": n, "latest": max(dates) if dates else None}


def kernels_recent():
    out = run(["kernels", "list", "--competition", COMP, "--page-size", "50"])
    rows = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and "/" in parts[0]:
            rows.append({"ref": parts[0], "run": parts[-2], "votes": parts[-1]})
    return rows


def main():
    snap = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "lb_top": lb_top(),
        "datasets": {d: dataset_fingerprint(d) for d in WATCH_DATASETS},
        "kernels": kernels_recent(),
    }
    prev_files = sorted(OUT.glob("snapshot-*.json"))
    prev = json.loads(prev_files[-1].read_text()) if prev_files else None
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = OUT / f"snapshot-{ts}.json"
    path.write_text(json.dumps(snap, indent=1))
    # prune old snapshots (> 48h)
    cutoff = time.time() - 48 * 3600
    for p in OUT.glob("snapshot-*.json"):
        try:
            if time.mktime(time.strptime(p.stem.replace("snapshot-", ""), "%Y%m%d-%H%M%S")) < cutoff:
                p.unlink()
        except ValueError:
            pass
    if prev is None:
        print(f"[monitor] baseline snapshot written: {path.name}")
        return
    changes = []
    top_prev = {r["team"]: r["score"] for r in prev["lb_top"]}
    for r in snap["lb_top"]:
        old = top_prev.get(r["team"])
        if old is None:
            changes.append(f"LB new top-20 team: {r['team']} {r['score']}")
        elif r["score"] != old:
            changes.append(f"LB score change: {r['team']} {old} -> {r['score']}")
    best_prev = max((r["score"] for r in prev["lb_top"]), default=0)
    best_new = max((r["score"] for r in snap["lb_top"]), default=0)
    if best_new > best_prev:
        changes.append(f"LB TOP improved: {best_prev} -> {best_new}")
    for d in WATCH_DATASETS:
        if prev["datasets"].get(d, {}).get("files_hash") != snap["datasets"][d]["files_hash"]:
            changes.append(f"DATASET changed: {d} (latest file {snap['datasets'][d]['latest']})")
    prev_refs = {k["ref"] for k in prev["kernels"]}
    for k in snap["kernels"]:
        if k["ref"] not in prev_refs:
            changes.append(f"NEW KERNEL: {k['ref']} (run {k['run']})")
    print(f"[monitor] {snap['ts']} | top={best_new:.5f} | changes={len(changes)}")
    for c in changes:
        print("[monitor]   " + c)


if __name__ == "__main__":
    main()
