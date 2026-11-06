"""Baseline end-to-end validation: factorization -> encode -> build circuits ->
official verify -> score. Must reproduce 10.6976x on the current best before any
lower-rank output is trusted. Writes only under work/chem_gpu/.
"""
import os, sys, json, subprocess

REPO = "/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum"
SK = os.path.join(REPO, "starter_kit", "starter_kit")
for p in (SK, os.path.join(REPO, "data", "verifiers")):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np

BASELINE = os.path.join(REPO, "work/frontier_scan/mwa2_unpacked/dfthcsos/submission.npz")
OUT = os.path.join(REPO, "work", "chem_gpu", "_baseline_check")


def main():
    from starter.task2_angles.encode import encode_inputs, TREES
    from starter.task2_angles.trees import log_depth_tree_edges
    from starter.task3_circuits.build_circuits import build_submission
    from verifier.score import load_inputs
    from verifier.reference import load_factorization

    system = "FeMoCo76o113e"
    params = load_factorization(BASELINE)
    inputs = load_inputs(system, params)
    N = inputs.num_orbitals
    edges = log_depth_tree_edges(N)
    words_fresh = encode_inputs(inputs, edges, brot=8, rounding="nearest")

    stored = np.load(BASELINE, allow_pickle=False)
    if "angle_words" in stored.files:
        ws = np.asarray(stored["angle_words"], np.int64)
        same = ws.shape == words_fresh.shape and int(np.sum(ws != words_fresh))
        print(f"fresh vs stored angle_words: shape {words_fresh.shape} vs {ws.shape}, differing entries = {same}")
    else:
        print("stored has no angle_words")

    os.makedirs(OUT, exist_ok=True)
    print(f"\nbuild_submission -> {OUT} ...", flush=True)
    summary = build_submission(
        system, BASELINE, tree="log_depth", brot=8, batch_size=5,
        rounding="nearest", output_directory=OUT, overwrite=True, keep_bits=10,
    )
    m, r = summary["metrics"], summary["resources"]
    REF = 3355599588.3155365
    print(f"\nDEV verifier: score={summary['score']:.4g} ratio={REF/summary['score']:.4f}x")
    print(f"  error_1={1e3*m['error_1']:.4f}m error_2={1e3*m['error_2']:.4f}m "
          f"E_gap={m['E_gap']:.7f} lambda_eff={m['lambda_eff']:.4f} T={r['toffoli']} Q={r['qubits']}")

    print("\nOFFICIAL verifier (data/verifiers/dfthcsos/verify.py) ...", flush=True)
    py = os.path.join(REPO, ".venv", "bin", "python")
    proc = subprocess.run([py, os.path.join(REPO, "data/verifiers/dfthcsos/verify.py"), OUT],
                          capture_output=True, text=True)
    try:
        off = json.loads(proc.stdout[proc.stdout.rindex("{"):])
    except Exception:
        print("official stdout tail:\n", proc.stdout[-2000:], "\nstderr tail:\n", proc.stderr[-2000:])
        raise
    om, orr = off.get("metrics", {}), off.get("resources", {})
    print(f"status={off.get('status')} score={off.get('score'):.4g} ratio={REF/off.get('score',1):.4f}x")
    print(f"  error_1={1e3*om.get('error_1',0):.4f}m error_2={1e3*om.get('error_2',0):.4f}m "
          f"E_gap={om.get('E_gap',0):.7f} lambda_eff={om.get('lambda_eff',0):.4f} "
          f"T={orr.get('toffoli')} Q={orr.get('qubits')}")


if __name__ == "__main__":
    main()
