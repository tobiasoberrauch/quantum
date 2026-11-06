"""Time a single JAX epoch of the Qaggle cost at a given (M,G) shape (CPU)."""
import os, sys, time
import numpy as np
import jax
import jax.numpy as jnp

REPO = "/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum"
sys.path.insert(0, os.path.join(REPO, "starter_kit", "starter_kit"))
sys.path.insert(0, os.path.join(REPO, "data", "verifiers"))

from dfthc import df_thc_sga
from dfthc.train_df_thc_sga import Initialize, Params
from dfthcsos.scoreinfra.reference import check_fcidump, load_fixed_shifts

FCI = os.path.join(REPO, "starter_kit", "FeMoCo76o113e.fcidump")
UPPER = -22140.27335


def main():
    M, G = int(sys.argv[1]), int(sys.argv[2])
    R, N = 9, 76
    t0 = time.time()
    ref = Initialize(FCI, UPPER)
    print(f"[{time.time()-t0:.0f}s] ref loaded, orbitals={ref['orbitals']}")
    # fixed shifts
    fs = load_fixed_shifts(os.path.join(REPO, "starter_kit", "FeMoCo76o113e.fixed_shifts.npz"))
    frozen = {k: jnp.asarray(v, dtype=df_thc_sga.dtype) for k, v in fs.items()}
    params = Params('Qaggle', R, M, G, N, seed=0)
    params = {**params, **frozen}
    active = {k: v for k, v in params.items() if k not in frozen}
    complete = lambda a: {**a, **frozen}
    cost_fn = lambda p: df_thc_sga.Compute_qaggle_df_thc_cost_function(
        complete(p), ref, 0.0001, 'Qaggle', epsilon_dfthc=0.02,
        lambda_floor=49.0, sos_gap_floor=3.9152)['cost']
    vgrad = jax.jit(jax.value_and_grad(cost_fn))
    # warmup + compile
    t1 = time.time()
    val, grad = vgrad(active)
    compile_t = time.time() - t1
    print(f"[compile {compile_t:.1f}s] cost={float(val):.5f}")
    # time 20 real epochs
    import optax
    opt = optax.adam(1e-3)
    st = opt.init(active)
    t2 = time.time()
    for _ in range(20):
        val, grad = vgrad(active)
        upd, st = opt.update(grad, st, active)
        active = optax.apply_updates(active, upd)
    dt = (time.time() - t2) / 20
    print(f"[{dt*1000:.1f} ms/epoch]  -> 2000 epochs ~ {dt*2000/60:.1f} min, 5000 ~ {dt*5000/60:.1f} min")
    o = df_thc_sga.Compute_qaggle_df_thc_cost_function(complete(active), ref, 0.0001, 'Qaggle',
                                                       epsilon_dfthc=0.02, lambda_floor=49.0, sos_gap_floor=3.9152)
    print(f"after 20ep: err2={1e3*o['epsilon_fro']:.2f}mHa lamEff={o['lambda_eff']:.3f} Egap={o['sos_gap']:.5f} Lambda={o['Lambda']:.2f}")


if __name__ == "__main__":
    main()
