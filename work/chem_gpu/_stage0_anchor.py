"""Stage-0 anchor check: does cost-model + dfthc_math reproduce 10.6976x on the
current best (9,143,39)? Also print T/Q/ratio for every target shape so the plan's
ratio estimates are grounded in the real cost model (not hand-waved)."""
import os, sys
import numpy as np
REPO = "/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum"
for p in (os.path.join(REPO, "data", "verifiers"), os.path.join(REPO, "work", "chem_lower_rank")):
    sys.path.insert(0, p)
from dfthcsos.scoreinfra.reference import (check_fcidump, load_factorization,
                                           load_fixed_shifts, load_reference)
from metrics_np import native_inputs, evaluate, costs, ratio, score_from, REFERENCE_COST

B = os.path.join(REPO, "work/frontier_scan/mwa2_unpacked/dfthcsos/submission.npz")
params = load_factorization(B); params.update(load_fixed_shifts())
ref = load_reference(check_fcidump()); N = int(ref["orbitals"])
R = params["W"].shape[0]

# --- Stage 0 anchor: current best ---
nat = native_inputs(params, ref)
mv = evaluate(nat, params["U"])
Bn, Cn = params["W"].shape[1], params["W"].shape[2]
c = costs(R, Bn, Cn, N, brot=8)
sc = score_from(mv["lambda_eff"], c["toffolis"], c["qubits"])
print("=== STAGE 0 ANCHOR (current best) ===")
print(f"shape R,B,C,N = {R},{Bn},{Cn},{N}")
print(f"error_2 = {1e3*mv['error_2']:.5f} mHa   (target 19.99965)")
print(f"E_gap   = {mv['E_gap']:.7f}          (target 3.9148992)")
print(f"lambda_eff = {mv['lambda_eff']:.4f}  (target 47.0256)")
print(f"Toffolis = {c['toffolis']}  (target 15585)")
print(f"Qubits   = {c['qubits']}  (target 428)")
print(f"score = {sc:.4g}   ratio = {ratio(sc):.4f}x   (target 10.6976x)")
ok = (abs(1e3*mv['error_2']-19.99965)<0.01 and abs(mv['lambda_eff']-47.0256)<0.01
      and c['toffolis']==15585 and c['qubits']==428 and abs(ratio(sc)-10.6976)<0.001)
print("STAGE0_REPRODUCE =", ok)

# --- Target shapes: cost model only (T,Q) + optimistic lambda_eff scaling ---
print("\n=== TARGET SHAPES (cost model T/Q; ratio @ lambda_eff=47.0256 fixed) ===")
lam_fixed = mv["lambda_eff"]
for M, G in [(130,35),(130,36),(134,36),(132,35),(132,36),(129,35),(129,36),(134,35)]:
    cc = costs(R, M, G, N, brot=8)
    ssc = score_from(lam_fixed, cc["toffolis"], cc["qubits"])
    dgm = ratio(ssc) - 10.6976
    print(f"M={M:>3} G={G:>2} | T={cc['toffolis']:>6} Q={cc['qubits']:>3} | "
          f"ratio@fixedLam={ratio(ssc):>6.3f}x  dGM={dgm:+.3f}")
