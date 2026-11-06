"""Bounded full-parameter (U,W,H2_I) L-BFGS-B refit at a reduced (M,G) shape.

Seeds by importance-truncating the current best, then runs scipy L-BFGS-B driven
by JAX autodiff gradients (stable line search, unlike raw Adam which diverged).
Timeboxed: documents the CPU convergence trajectory toward error_2<=20 and the
resulting lambda_eff, without requiring the notebook's GPU-scale 8x60k-iteration
full convergence.

Usage: python train_lbfgs.py <M> <G> <maxfun> [--out F] [--print-int N]
"""
import argparse, os, sys, time
import numpy as np
import jax, jax.numpy as jnp
from scipy.optimize import minimize as spmin

REPO = "/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum"
sys.path.insert(0, os.path.join(REPO, "starter_kit", "starter_kit"))
sys.path.insert(0, os.path.join(REPO, "data", "verifiers"))
from dfthc import df_thc_sga
from dfthc.train_df_thc_sga import Initialize
from dfthcsos.scoreinfra.reference import check_fcidump, load_fixed_shifts, load_factorization

FCI = os.path.join(REPO, "starter_kit", "FeMoCo76o113e.fcidump")
FSHIFT = os.path.join(REPO, "starter_kit", "FeMoCo76o113e.fixed_shifts.npz")
BEST = os.path.join(REPO, "work/frontier_scan/mwa2_unpacked/dfthcsos/submission.npz")
UPPER = -22140.27335
R, N = 9, 76


def importance_truncate(params, M, G):
    U = np.asarray(params["U"], float); W = np.asarray(params["W"], float); H2 = np.asarray(params["H2_I"], float)
    Uo, Wo, Ho = [], [], []
    for r in range(R):
        kb = np.argsort(-(np.abs(W[r]).sum(1)))[:M]
        kc = np.argsort(-(np.abs(H2[r]) + np.abs(W[r]).sum(0)))[:G]
        Uo.append(U[r, kb]); Wo.append(W[r, kb][:, kc]); Ho.append(H2[r, kc])
    return {"U": np.stack(Uo), "W": np.stack(Wo), "H2_I": np.stack(Ho)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("M", type=int); ap.add_argument("G", type=int); ap.add_argument("maxfun", type=int)
    ap.add_argument("--rho", type=float, default=1e-4); ap.add_argument("--eps", type=float, default=0.02)
    ap.add_argument("--gap-floor", type=float, default=3.9152); ap.add_argument("--lam-floor", type=float, default=49.0)
    ap.add_argument("--print-int", type=int, default=200); ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--start", type=str, default=BEST)
    a = ap.parse_args()

    t0 = time.time()
    ref = Initialize(FCI, UPPER)
    fs = load_fixed_shifts(FSHIFT)
    dt = df_thc_sga.dtype
    frozen = {k: jnp.asarray(v, dtype=dt) for k, v in fs.items()}
    tp = importance_truncate(load_factorization(a.start), a.M, a.G)
    shapes = {"U": tp["U"].shape, "W": tp["W"].shape, "H2_I": tp["H2_I"].shape}
    flat0 = np.concatenate([tp[k].ravel() for k in ("U", "W", "H2_I")])

    def unflat(x):
        out, i = {}, 0
        for k in ("U", "W", "H2_I"):
            n = int(np.prod(shapes[k])); out[k] = x[i:i+n].reshape(shapes[k]); i += n
        return out

    kw = dict(epsilon_dfthc=a.eps, lambda_floor=a.lam_floor, sos_gap_floor=a.gap_floor)
    def full_jax(p):
        return df_thc_sga.Compute_qaggle_df_thc_cost_function({**p, **frozen}, ref, a.rho, "Qaggle", **kw)
    fj = jax.jit(full_jax); cj = jax.jit(lambda p: full_jax(p)["cost"]); gj = jax.jit(jax.grad(lambda p: full_jax(p)["cost"]))
    def f(x):
        p = {k: jnp.asarray(v, dtype=dt) for k, v in unflat(x).items()}
        return float(cj(p))
    def g(x):
        p = {k: jnp.asarray(v, dtype=dt) for k, v in unflat(x).items()}
        gp = gj(p)
        return np.concatenate([np.asarray(gp[k]).ravel() for k in ("U", "W", "H2_I")])

    o0 = fj({k: jnp.asarray(tp[k], dtype=dt) for k in tp})
    print(f"[{time.time()-t0:.0f}s] seed ({R},{a.M},{a.G}): err2={1e3*float(o0['epsilon_fro']):.1f}m "
          f"lamEff={float(o0['lambda_eff']):.2f} Egap={float(o0['sos_gap']):.4f}", flush=True)

    state = {"n": 0, "best": (float(o0["cost"]), flat0.copy())}
    def cb(xk):
        state["n"] += 1
        c = float(cj({k: jnp.asarray(v, dtype=dt) for k, v in unflat(xk).items()}))
        if c < state["best"][0]:
            state["best"] = (c, xk.copy())
        if state["n"] % a.print_int == 0:
            o = fj({k: jnp.asarray(v, dtype=dt) for k, v in unflat(xk).items()})
            print(f"iter={state['n']:>5d} [{time.time()-t0:>6.0f}s] err2={1e3*float(o['epsilon_fro']):8.3f}m "
                  f"lamEff={float(o['lambda_eff']):8.3f} Egap={float(o['sos_gap']):9.5f} Lambda={float(o['Lambda']):8.2f}", flush=True)
        return False

    res = spmin(f, flat0, jac=g, method="L-BFGS-B", callback=cb,
                options={"maxfun": a.maxfun, "maxiter": a.maxfun, "gtol": 1e-6})
    xb = state["best"][1]
    ob = fj({k: jnp.asarray(v, dtype=dt) for k, v in unflat(xb).items()})
    print(f"\nL-BFGS status={res.message} fun={res.fun:.5f} nfev={res.nfev}", flush=True)
    print(f"BEST: err2={1e3*float(ob['epsilon_fro']):.3f}m lamEff={float(ob['lambda_eff']):.4f} "
          f"Egap={float(ob['sos_gap']):.6f} Lambda={float(ob['Lambda']):.3f} "
          f"valid_err2={bool(float(ob['epsilon_fro'])<=a.eps)} valid_gap={bool(float(ob['sos_gap'])>a.gap_floor)}", flush=True)
    if a.out:
        ub = unflat(xb)
        npz = {k: ub[k] for k in ("U", "W", "H2_I")}
        npz.update({k: np.asarray(v) for k, v in fs.items()})
        np.savez(a.out, **npz)
        print(f"saved {a.out}", flush=True)


if __name__ == "__main__":
    main()
