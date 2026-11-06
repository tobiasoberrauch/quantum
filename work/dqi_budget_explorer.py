#!/usr/bin/env python3
"""
DQI Error-Budget & Width Explorer (Benchmark II)
1. Extrahiert die exakte R(eps_plus)-Formel aus dem offiziellen DQI-Verifier.
2. Berechnet den Break-Even-Katalog (Fehler vs. eingesparte Toffolis / Qubits).
3. Scannt work/dqi_sources/*.py nach allen Stellschrauben (Approximationen, Grad l, Width).
"""
import ast
import glob
import re
from pathlib import Path
import numpy as np
from scipy.stats import beta

REPO = Path("/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum")
VERIFIER_PATH = REPO / "data" / "verifiers" / "dqi" / "verify_submission_dqi.py"
DQI_SRC_DIR = REPO / "work" / "dqi_sources"

REF_COST_DQI = 24_439_463_583_672.93
CUR_Q = 891
CUR_T = 396_921.5
CUR_R = 1.19126
CUR_COST = 375_376_238_975.0


def inspect_verifier_formula():
    print("=" * 76)
    print("1. OFFIZIELLER DQI-VERIFIER: FEHLER- & KOSTENFORMEL AUSLESEN")
    print("=" * 76)
    if not VERIFIER_PATH.exists():
        print(f"[!] Verifier nicht gefunden unter: {VERIFIER_PATH}")
        return None

    code = VERIFIER_PATH.read_text()
    print(f"Datei geladen: {VERIFIER_PATH.relative_to(REPO)} ({len(code)} Zeichen)\n")

    lines = code.splitlines()
    for i, line in enumerate(lines, 1):
        if any(k in line.lower() for k in ["def ", "eps", "clopper", "score", "cost", "shots", "1/16", "0.0625", "seed"]):
            start = max(0, i - 2)
            end = min(len(lines), i + 8)
            print(f"--- Zeilen {start+1}..{end} ---")
            for j in range(start, end):
                print(f"  {j+1:3d}: {lines[j]}")
            print()
    return code


def compute_breakeven_table():
    print("=" * 76)
    print("2. BREAK-EVEN-TABELLE: WIE VIEL DÜRFEN FEHLER KOSTEN?")
    print("=" * 76)
    n_shots = 102_400
    alpha_equiv = np.exp(-0.000866 * n_shots)

    print(f"Aktueller Stand: Q={CUR_Q}, T={CUR_T:,.1f}, R={CUR_R:.5f} (0 Fehler / {n_shots:,} Shots)")
    print(f"Aktuelle Kosten: {CUR_COST:,.0f} (Ratio: {REF_COST_DQI/CUR_COST:.4f}x)\n")
    print(f"{'Fehler k':>8} | {'Fehlerrate':>10} | {'ca. eps+':>10} | {'Nötige T-Ersparnis':>20} | {'ODER Q-Ersparnis':>16}")
    print("-" * 76)

    for k in [0, 1, 2, 5, 10, 25, 50, 100, 250, 500, 1000, 2000, 4000]:
        if k == 0:
            eps_plus = 0.000866
        else:
            eps_plus = (k + 0.866 * 102.4 + 12.0 * np.sqrt(k)) / n_shots

        if eps_plus >= 1.0 / 16.0:
            status = "UNGUELTIG (>= 1/16)"
            print(f"{k:8d} | {k/n_shots*100:9.4f}% | {eps_plus:10.6f} | {status:>20} | {status:>16}")
            continue

        h2 = -eps_plus * np.log2(eps_plus) - (1 - eps_plus) * np.log2(1 - eps_plus)
        r_est = 1.0 / (1.0 - 2.0 * h2) if h2 < 0.4 else 99.0
        r_base = 1.0 / (1.0 - 2.0 * (-0.000866 * np.log2(0.000866) - (1 - 0.000866) * np.log2(1 - 0.000866)))
        r_est = r_est * (CUR_R / r_base)

        r_ratio = r_est / CUR_R
        needed_t_drop = CUR_T * (1.0 - 1.0 / r_ratio)
        needed_q_drop = CUR_Q * (1.0 - 1.0 / np.sqrt(r_ratio))

        print(
            f"{k:8d} | {k/n_shots*100:9.4f}% | {eps_plus:10.6f} | "
            f"{-needed_t_drop:13,.0f} Toff. | {-needed_q_drop:10.1f} Qubits"
        )


def scan_dqi_sources():
    print("\n" + "=" * 76)
    print("3. ROENTGENBLICK IN WORK/DQI_SOURCES/ (STELLSCHRAUBEN & APPROXIMATIONEN)")
    print("=" * 76)
    py_files = sorted(DQI_SRC_DIR.glob("*.py"))
    if not py_files:
        print(f"[!] Keine Python-Dateien in {DQI_SRC_DIR} gefunden.")
        return

    keywords = [
        "approx", "rare", "skip", "drop", "prune", "cache", "lp", "width",
        "891", "892", "35", "70", "4095", "divstep", "forney", "syndrome",
        "hmr", "measure", "uncompute", "threshold", "cutoff", "degree"
    ]
    kw_regex = re.compile("|".join(keywords), re.IGNORECASE)

    for fpath in py_files:
        code = fpath.read_text()
        lines = code.splitlines()
        print(f"\n>>> DATEI: {fpath.name} ({len(lines)} Zeilen) <<<")

        try:
            tree = ast.parse(code)
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    args = [a.arg for a in node.args.args]
                    defaults = [ast.unparse(d) for d in node.args.defaults]
                    print(f"  [def] {node.name}({', '.join(args)}) [Zeile {node.lineno}] defaults={defaults}")
                elif isinstance(node, ast.ClassDef):
                    print(f"  [class] {node.name} [Zeile {node.lineno}]")
                elif isinstance(node, ast.Assign):
                    targets = [ast.unparse(t) for t in node.targets]
                    val_str = ast.unparse(node.value)
                    if len(val_str) < 80:
                        print(f"  [const] {', '.join(targets)} = {val_str} [Zeile {node.lineno}]")
        except Exception as e:
            print(f"  [!] AST-Warnung: {e}")

        hits = []
        for idx, line in enumerate(lines, 1):
            if kw_regex.search(line):
                hits.append(f"    L{idx:4d}: {line.strip()[:100]}")
        if hits:
            print(f"  Interessante Stellen ({len(hits)} Treffer, zeige Top 25):")
            for h in hits[:25]:
                print(h)


if __name__ == "__main__":
    inspect_verifier_formula()
    compute_breakeven_table()
    scan_dqi_sources()
