"""Frozen-U weight refit: reduce G (drop least-important copies) and re-optimize
ONLY W (9,M,G) + H2_I (9,G) with U held at the current best's basis. Tests
empirically whether lambda_eff drops (as the Lambda decomposition predicts) while
error_2 is pulled back to <= 20 mHa. Uses JAX with clipped Adam (stable) and,
optionally, L-BFGS.

Usage: python refit_g.py <G> <epochs> [--lr L] [--clip C] [--solver adam|lbfgs] [--out F]
"""
import argparse, os, sys, time
import numpy as np
import jax, jax.numpy as jnp, optax

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("G", type=int); ap.add_argument("epochs", type=int)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--clip", type=float, default=1.0)
    ap.add_argument("--rho", type=float, default=1e-4)
    ap.add_argument("--eps", type=float, default=0.02)
    ap.add_argument("--gap-floor", type=float, default=3.9152)
    ap.add_argument("--lam-floor", type=float, default=49.0)
    ap.add_argument("--solver", choices=["adam", "lbfgs"], default="adam")
    ap.add_argument("--print-int", type=int, default=200)
    ap.add_argument("--out", type=str, default=None)
    a = ap.parse_args()

    t0 = time.time()
    ref = Initialize(FCI, UPPER)
    fs = load_fixed_shifts(FSHIFT)
    dt = df_thc_sga.dtype
    frozen = {k: jnp.asarray(v, dtype=dt) for k, v in fs.items()}
    base = load_factorization(BEST)
    U0 = np.asarray(base["U"], float); W0 = np.asarray(base["W"], float); H20 = np.asarray(base["H2_I"], float)
    M = U0.shape[1]; C0 = W0.shape[2]
    # drop least-important copies per group, keep top-G
    W = np.zeros((R, M, a.G)); H2 = np.zeros((R, a.G))
    for r in range(R):
        imp = np.abs(H20[r]) + np.sum(np.abs(W0[r]), axis=0)
        keep = np.argsort(-imp)[:a.G]
        W[r] = W0[r][:, keep]; H2[r] = H20[r][keep]
    # active params: W, H2_I only (U frozen)
    active0 = {"W": jnp.asarray(W, dtype=dt), "H2_I": jnp.asarray(H2, dtype=dt)}
    Uf = jnp.asarray(U0, dtype=dt)
    complete = lambda p: {"U": Uf, "W": p["W"], "H2_I": p["H2_I"], **frozen}
    kw = dict(epsilon_dfthc=a.eps, lambda_floor=a.lam_floor, sos_gap_floor=a.gap_floor)
    full = jax.jit(lambda p: df_thc_sga.Compute_qaggle_df_thc_cost_function(complete(p), ref, a.rho, "Qaggle", **kw))
    cost = lambda p: full(p)["cost"]
    vgrad = jax.jit(jax.value_and_grad(cost))

    o0 = full(active0)
    print(f"[{time.time()-t0:.0f}s] frozen-U seed ({R},{M},{a.G}): err2={1e3*float(o0['epsilon_fro']):.1f}m "
          f"lamEff={float(o0['lambda_eff']):.2f} Egap={float(o0['sos_gap']):.4f} Lambda={float(o0['Lambda']):.1f}", flush=True)

    if a.solver == "adam":
        opt = optax.chain(optax.clip_by_global_norm(a.clip), optax.adam(a.lr))
        st = opt.init(active0)
    else:
        opt = optax.lbfgs(learning_rate=1.0, maxiter=30, num_history=10)
        st = opt.init(active0)

    best = (float(cost(active0)), active0)
    tag = [0]
    for ep in range(1, a.epochs + 1):
        val, grad = vgrad(active0)
        upd, st = opt.update(grad, st, active0)
        active0 = optax.apply_updates(active0, upd)
        if float(val) < best[0]:
            best = (float(val), active0)
        if ep % a.print_int == 0 or ep == a.epochs:
            o = full(active0)
            tag[0] = ep
            print(f"ep={ep:>6d} [{time.time()-t0:>6.0f}s] err2={1e3*float(o['epsilon_fro']):8.3f}m "
                  f"lamEff={float(o['lambda_eff']):8.3f} Egap={float(o['sos_gap']):9.5f} Lambda={float(o['Lambda']):8.2f} "
                  f"cost={float(o['cost']):8.4f}", flush=True)
    ob = full(best[1])
    print(f"\nBEST: err2={1e3*float(ob['epsilon_fro']):.3f}m lamEff={float(ob['lambda_eff']):.4f} "
          f"Egap={float(ob['sos_gap']):.6f} Lambda={float(ob['Lambda']):.3f} "
          f"valid_err2={bool(float(ob['epsilon_fro'])<=a.eps)} valid_gap={bool(float(ob['sos_gap'])>a.gap_floor)}", flush=True)
    if a.out:
        npz = {k: np.asarray(v) for k, v in best[1].items()}
        npz["U"] = U0
        npz.update({k: np.asarray(v) for k, v in fs.items()})
        np.savez(a.out, **npz)
        print(f"saved {a.out}", flush=True)


if __name__ == "__main__":
    main()
