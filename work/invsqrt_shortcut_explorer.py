#!/usr/bin/env python3
"""
Invsqrt Domain-Shortcut & Rotation-Slack Explorer (Benchmark I)
1. Liest den offiziellen Verifier (verify_submission_invsqrt.py) & starter_kit/verifier/costs.py aus.
2. Prueft mwa_verify_invsqrt.log auf exakte Teil-Metriken.
3. Analysiert die Gewichtung der 22 Exponenten-Buckets (x = 1 .. 3,133,452).
4. Scannt sota_mrmeows/sources/ und work/invsqrt_caching/ nach dem Kickmix-Gate-Format.
"""
import glob
import re
from pathlib import Path
import numpy as np

REPO = Path("/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum")
VERIFIER_PATH = REPO / "data" / "verifiers" / "invsqrt" / "verify_submission_invsqrt.py"
COSTS_PATH = REPO / "starter_kit" / "verifier" / "costs.py"
LOG_PATH = REPO / "work" / "frontier_scan" / "mwa_verify_invsqrt.log"
KMB_PATH = REPO / "work" / "frontier_scan" / "mwa_unpacked" / "invsqrt.kmb"

N_MAX = 3_133_452
REF_COST_INVSQRT = 2_076_774.23
CUR_Q = 62
CUR_MEAN_TOFF = 1_289.29
CUR_MAX_TOFF = 1_487
CUR_T_COUNT = 20.5
CUR_COST = 98_533.87


def inspect_invsqrt_verifier():
    print("=" * 78)
    print("1. OFFIZIELLER INVSQRT-VERIFIER & COSTS.PY: WIE WIRD GEZAHLT?")
    print("=" * 78)
    for path in [VERIFIER_PATH, COSTS_PATH]:
        if path.exists():
            print(f"\n>>> DATEI: {path.relative_to(REPO)} <<<")
            print(path.read_text()[:4500])
        else:
            print(f"[!] Datei nicht gefunden: {path}")

    if LOG_PATH.exists():
        print(f"\n>>> AKTUELLES VERIFIER-LOG ({LOG_PATH.relative_to(REPO)}) <<<")
        print(LOG_PATH.read_text()[:3000])


def analyze_exponent_buckets():
    print("\n" + "=" * 78)
    print("2. GEWICHTUNG DER 22 BIT-BEREICHE (BUCKETS) VON x = 1 BIS 3.133.452")
    print("=" * 78)
    print(f"Gesamte Zahlen: {N_MAX:,} | Aktueller Mean Toffolis: {CUR_MEAN_TOFF:.2f} (Max: {CUR_MAX_TOFF})")
    print(f"Differenz Max - Mean = {CUR_MAX_TOFF - CUR_MEAN_TOFF:.2f} Toffolis werden bereits jetzt im Schnitt uebersprungen!\n")

    print(f"{'Bucket b':>8} | {'Bereich [2^b .. 2^(b+1)-1]':>27} | {'Anzahl x':>10} | {'Anteil Preis':>12} | {'Kumuliert ab b':>14}")
    print("-" * 78)

    counts = []
    for b in range(22):
        lo = 1 << b
        hi = min((1 << (b + 1)) - 1, N_MAX)
        cnt = max(0, hi - lo + 1)
        counts.append((b, lo, hi, cnt))

    cum_from_top = 0
    rows_out = []
    for b, lo, hi, cnt in reversed(counts):
        cum_from_top += cnt
        pct = cnt / N_MAX * 100.0
        cum_pct = cum_from_top / N_MAX * 100.0
        mark = " <-- x=161 (Limit 0.99932!)" if lo <= 161 <= hi else ""
        rows_out.append(
            f"{b:8d} | {f'{lo:,} .. {hi:,}':>27} | {cnt:10,d} | {pct:11.4f}% | {cum_pct:13.4f}%{mark}"
        )

    for r in reversed(rows_out):
        print(r)

    print("\n--- HEBEL-RECHNUNG FUER DIE ABKUERZUNG ---")
    for saved_toff in [100, 200, 300, 450]:
        share = (N_MAX - 65535) / N_MAX
        new_mean = CUR_MEAN_TOFF - saved_toff * share
        cur_c = CUR_COST / CUR_Q
        new_c = cur_c - saved_toff * share
        new_cost = CUR_Q * new_c
        new_ratio = REF_COST_INVSQRT / new_cost
        gm_gain_factor = (new_ratio / (REF_COST_INVSQRT / CUR_COST)) ** (1.0 / 3.0)
        new_gm = 24.45812 * gm_gain_factor
        print(
            f"  Sparen wir {saved_toff:3d} Toffolis fuer x >= 65.536 (97.9% der Zahlen): "
            f"Mean_Toff -> {new_mean:7.2f} | Ratio: {new_ratio:6.2f}x | Gesamt-Score: {new_gm:.5f} (+{new_gm - 24.45812:.3f})"
        )


def scan_existing_invsqrt_tools():
    print("\n" + "=" * 78)
    print("3. VORHANDENE INVSQRT-SKRIPTE & KICKMIX-SCHALTKREIS-TOOLS IM REPO")
    print("=" * 78)
    search_dirs = [
        REPO / "work" / "invsqrt_caching",
        REPO / "work" / "constseed_build",
        REPO / "sota_mrmeows",
        REPO / "sota_yoyobar",
        REPO / "starter_kit" / "starter" / "task3_circuits",
    ]
    for d in search_dirs:
        if not d.exists():
            continue
        py_files = sorted(d.rglob("*.py"))
        print(f"\nVerzeichnis {d.relative_to(REPO)}: {len(py_files)} Python-Dateien")
        for pf in py_files[:15]:
            lines = pf.read_text().splitlines()
            print(f"  - {pf.relative_to(REPO)} ({len(lines)} Zeilen)")
            for i, l in enumerate(lines[:25], 1):
                if any(w in l.lower() for w in ["kickmix", "kmb", "toffoli", "rot", "phase", "hmr", "circuit", "verify"]):
                    print(f"      L{i:3d}: {l.strip()[:100]}")

    caching_files = sorted((REPO / "work" / "invsqrt_caching").glob("*.py")) if (REPO / "work" / "invsqrt_caching").exists() else []
    for cf in caching_files[:2]:
        print(f"\n>>> CODE-AUSZUG: {cf.relative_to(REPO)} <<<")
        print(cf.read_text()[:3000])


if __name__ == "__main__":
    inspect_invsqrt_verifier()
    analyze_exponent_buckets()
    scan_existing_invsqrt_tools()
