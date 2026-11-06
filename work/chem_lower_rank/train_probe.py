"""Timeboxed lower-rank DF-THC probe trainer (CPU/JAX).

Seeds a (9,M,G) table by importance-truncating a starting factorization (default:
the current best), then minimizes the Qaggle cost
    relu(error_2 - eps) + gap_domain_violation + relu(lam_floor-Lambda)
                      + relu(gap_floor - E_gap) + rho * lambda_eff
(the advisory's lambda_eff barrier penalty), recording the trajectory.

Usage:
  python train_probe.py <M> <G> <epochs> [--lr L] [--rho R] [--gap-floor F]
                        [--start FILE.npz] [--out FILE.npz] [--print-int N]
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np
import jax
import jax.numpy as jnp
import optax

REPO = "/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum"
sys.path.insert(0, os.path.join(REPO, "starter_kit", "starter_kit"))
sys.path.insert(0, os.path.join(REPO, "data", "verifiers"))

from dfthc import df_thc_sga
from dfthc.train_df_thc_sga import Initialize, Params
from dfthcsos.scoreinfra.reference import check_fcidump, load_fixed_shifts, load_factorization

FCI = os.path.join(REPO, "starter_kit", "FeMoCo76o113e.fcidump")
FSHIFT = os.path.join(REPO, "starter_kit", "FeMoCo76o113e.fixed_shifts.npz")
UPPER = -22140.27335
R, N = 9, 76


def importance_truncate(params, M, G):
    """Keep top-M basis vectors and top-G copies per group by |W| importance."""
    U = np.asarray(params["U"], float); W = np.asarray(params["W"], float)
    H2 = np.asarray(params["H2_I"], float)
    Uo, Wo, Ho = [], [], []
    for r in range(R):
        b_imp = np.sum(np.abs(W[r]), axis=1)
        keep_b = np.argsort(-b_imp)[:M]
        c_imp = np.abs(H2[r]) + np.sum(np.abs(W[r]), axis=0)
        keep_c = np.argsort(-c_imp)[:G]
        Uo.append(U[r, keep_b]); Wo.append(W[r, keep_b][:, keep_c]); Ho.append(H2[r, keep_c])
    return {"U": np.stack(Uo), "W": np.stack(Wo), "H2_I": np.stack(Ho)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("M", type=int); ap.add_argument("G", type=int); ap.add_argument("epochs", type=int)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--rho", type=float, default=1e-4)
    ap.add_argument("--eps", type=float, default=0.02)
    ap.add_argument("--gap-floor", type=float, default=3.9152)
    ap.add_argument("--lam-floor", type=float, default=49.0)
    ap.add_argument("--start", type=str, default=os.path.join(REPO, "work/frontier_scan/mwa2_unpacked/dfthcsos/submission.npz"))
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--print-int", type=int, default=200)
    a = ap.parse_args()

    t0 = time.time()
    ref = Initialize(FCI, UPPER)
    fs = load_fixed_shifts(FSHIFT)
    frozen = {k: jnp.asarray(v, dtype=df_thc_sga.dtype) for k, v in fs.items()}
    start = load_factorization(a.start)
    tp = importance_truncate(start, a.M, a.G)
    dt = df_thc_sga.dtype
    params = {
        "U": jnp.asarray(tp["U"], dtype=dt), "W": jnp.asarray(tp["W"], dtype=dt),
        "H2_I": jnp.asarray(tp["H2_I"], dtype=dt),
    }
    complete = lambda p: {**p, **frozen}
    kwargs = dict(epsilon_dfthc=a.eps, lambda_floor=a.lam_floor, sos_gap_floor=a.gap_floor)
    cost_fn = lambda p: df_thc_sga.Compute_qaggle_df_thc_cost_function(complete(p), ref, a.rho, "Qaggle", **kwargs)["cost"]
    full_fn = jax.jit(lambda p: df_thc_sga.Compute_qaggle_df_thc_cost_function(complete(p), ref, a.rho, "Qaggle", **kwargs))
    vgrad = jax.jit(jax.value_and_grad(cost_fn))

    def report(tag, p):
        o = full_fn(p)
        print(f"{tag} ep={tag_ep[0]:>6d} [{time.time()-t0:>6.0f}s] err2={1e3*o['epsilon_fro']:8.3f}m "
              f"lamEff={float(o['lambda_eff']):8.3f} Egap={float(o['sos_gap']):9.5f} Lambda={float(o['Lambda']):8.2f} "
              f"cost={float(o['cost']):8.4f}", flush=True)

    tag_ep = [0]
    o0 = full_fn(params)
    print(f"[{time.time()-t0:.0f}s] seed ({R},{a.M},{a.G}) from {os.path.basename(a.start)}: "
          f"err2={1e3*float(o0['epsilon_fro']):.1f}m lamEff={float(o0['lambda_eff']):.2f} Egap={float(o0['sos_gap']):.4f}", flush=True)

    opt = optax.adam(a.lr)
    st = opt.init(params)
    best = (float(o0["cost"]), params)
    for ep in range(1, a.epochs + 1):
        val, grad = vgrad(params)
        upd, st = opt.update(grad, st, params)
        params = optax.apply_updates(params, upd)
        if float(val) < best[0]:
            best = (float(val), params)
        if ep % a.print_int == 0 or ep == a.epochs:
            tag_ep[0] = ep
            report("B" if params is best[1] else " ", params)
    # final report of best
    tag_ep[0] = a.epochs
    ob = full_fn(best[1])
    print(f"\nBEST: err2={1e3*float(ob['epsilon_fro']):.3f}m lamEff={float(ob['lambda_eff']):.4f} "
          f"Egap={float(ob['sos_gap']):.6f} Lambda={float(ob['Lambda']):.3f} "
          f"valid_err2={bool(float(ob['epsilon_fro'])<=a.eps)} valid_gap={bool(float(ob['sos_gap'])>a.gap_floor)}", flush=True)
    if a.out:
        npz = {k: np.asarray(v) for k, v in best[1].items()}
        npz.update({k: np.asarray(v) for k, v in frozen.items()})
        np.savez(a.out, **npz)
        print(f"saved {a.out}", flush=True)


if __name__ == "__main__":
    main()
