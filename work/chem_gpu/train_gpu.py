"""Staged, gated DF-THC lower-rank GPU trainer (JAX + Optax/L-BFGS).

Implements ALGO_PLAN.md exactly:
  STAGE 0  baseline anchor  -> reproduce 10.6976x on the stored qvc-007 circuits
  STAGE 1  PRIMARY (130,35) -> Cholesky seed -> L-BFGS -> compile+verify
  STAGE 2  FALLBACK ladder  -> (only if Stage 1 invalid) a) multi-start
                               b) truncation warm-start  c) hybrid Adam->L-BFGS
  STAGE 3  remaining shapes -> (only if >=1 valid) sweep with the winning recipe
  DECISION GO / DEAD        -> written to results/DECISION.json

Runs on CPU (smoke / selftest) or CUDA (real run). JAX picks the device; force CPU
with JAX_PLATFORMS=cpu. Guards nullable/empty inputs throughout.

Objective (float32, STE-aware): the two-body fit is evaluated on the DECODED
b-bit-rounded Givens vectors (straight-through estimator), so training optimizes the
quantized solution directly. Terms:
    error_2(quantized) + alpha*max(0, 3.9152 - E_gap) + gamma*||w||_1 + beta*GF2(words)
Validity gate: a point is VALID iff continuous error_2 <= 20 mHa (and gap_in_domain).
Authoritative ratio comes from compiling the factorization and running the official
verifier (data/verifiers/dfthcsos/verify.py).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Paths / constants
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
# Repo root is two levels up from work/chem_gpu; override with QUANTUM_REPO if needed.
REPO = os.environ.get("QUANTUM_REPO") or os.path.abspath(os.path.join(HERE, "..", ".."))
SK = os.path.join(REPO, "starter_kit", "starter_kit")
VERIFIERS = os.path.join(REPO, "data", "verifiers")
for _p in (SK, VERIFIERS, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SYSTEM = "FeMoCo76o113e"
BASELINE_NPZ = os.path.join(REPO, "work/frontier_scan/mwa2_unpacked/dfthcsos/submission.npz")
STORED_CIRCUITS_DIR = os.path.join(REPO, "work/frontier_scan/mwa2_unpacked/dfthcsos")
OFFICIAL_VERIFY = os.path.join(VERIFIERS, "dfthcsos", "verify.py")
SEED_DIR = os.path.join(HERE, "seed")
RESULTS_DIR = os.path.join(HERE, "results")
CIRCUIT_DIR = os.path.join(HERE, "_circuits")

REFERENCE_COST = 3355599588.3155365
BASELINE_RATIO = 10.6976
ERR2_GATE_MA = 20.0          # validity gate: error_2 <= 20 mHa
EGAP_BARRIER = 3.9152        # accuracy barrier threshold (Ha)
LAM_EFF_MIN = 47.0           # GO requires lambda_eff >= 47
BROT = 8                     # angle word bit width
BATCH_SIZE = 5               # words per QROM batch (J)
KEEP_BITS = 10               # chi of the heuristic cost model

STAGE1_SHAPE = (130, 35)     # PRIMARY bet
STAGE3_SHAPES = [(130, 36), (134, 36), (132, 35), (132, 36)]


# ---------------------------------------------------------------------------
# Defensive input guards (nullable / empty / whitespace)
# ---------------------------------------------------------------------------
def require_str(name: str, value: Any) -> str:
    if value is None or not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string, got {value!r}")
    return value.strip()


def require_int(name: str, value: Any, lo: int, hi: int) -> int:
    if value is None:
        raise ValueError(f"{name} is required (got None)")
    try:
        iv = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be an integer, got {value!r}")
    if not (lo <= iv <= hi):
        raise ValueError(f"{name} must be in [{lo},{hi}], got {iv}")
    return iv


def require_path(name: str, value: Any) -> str:
    p = require_str(name, value)
    if not os.path.exists(p):
        raise FileNotFoundError(f"{name} does not exist: {p}")
    return p


def parse_shapes(tok: str) -> list[tuple[int, int]]:
    out = []
    for part in require_str("shapes", tok).split():
        if "," not in part:
            raise ValueError(f"bad shape token {part!r}; expected 'M,G'")
        m, g = part.split(",")
        out.append((require_int("M", m, 1, 200), require_int("G", g, 1, 60)))
    return out


# ---------------------------------------------------------------------------
# Frozen constants (loaded once)
# ---------------------------------------------------------------------------
@dataclass
class Consts:
    N: int
    R: int
    oei: Any
    tei: Any
    ecore: float
    electrons: int
    energy_upper: float
    S: Any                 # (N,N) fixed symmetry shift (frozen)
    beta_1: float          # frozen particle-number shift
    h1_thc: Any            # (N,N)
    hsym_lower: Any
    h1_i: Any
    edges: Any             # (N-1,2) log-depth Givens tree
    A_shift: Any           # (N,N,N,N) error_2 S-shift term 1
    B_shift: Any           # (N,N,N,N) error_2 S-shift term 2
    eye: Any               # (N,N)


def load_consts() -> Consts:
    import numpy as np
    from dfthcsos.scoreinfra.reference import (check_fcidump, load_reference,
                                               load_factorization, UPPER_ENERGY)
    from dfthcsos.scoreinfra.dfthc_math import symmetric_from_lower
    from starter.task2_angles.trees import log_depth_tree_edges

    ref = load_reference(check_fcidump())
    N = int(ref["orbitals"])
    base = load_factorization(require_path("baseline_npz", BASELINE_NPZ))
    S = np.asarray(symmetric_from_lower(base["Hsym_lower"], N), dtype=np.float64)
    beta_1 = float(base["H1_I"]) - 0.5 * float(np.trace(S))
    oei = np.asarray(ref["oei"], dtype=np.float64)
    tei = np.asarray(ref["tei"], dtype=np.float64)
    h1_thc = oei - 0.5 * np.einsum("prrq->pq", tei)
    E = np.eye(N, dtype=np.float64)
    A_shift = 0.5 * S[:, :, None, None] * E[None, None, :, :]
    B_shift = 0.5 * S[None, None, :, :] * E[:, :, None, None]
    edges = log_depth_tree_edges(N)
    return Consts(
        N=N, R=int(base["W"].shape[0]), oei=oei, tei=tei, ecore=float(ref["ecore"]),
        electrons=int(ref["electrons"]), energy_upper=float(UPPER_ENERGY), S=S,
        beta_1=beta_1, h1_thc=h1_thc, hsym_lower=base["Hsym_lower"], h1_i=base["H1_I"],
        edges=edges, A_shift=A_shift, B_shift=B_shift, eye=E,
    )


# ---------------------------------------------------------------------------
# JAX kernels
# ---------------------------------------------------------------------------
def _jax():
    import jax
    import jax.numpy as jnp
    return jax, jnp


def sym_lower(X, jnp):
    """Symmetrize (...,N,N) from its lower triangle (matches dfthc_math)."""
    return jnp.tril(X) + jnp.swapaxes(jnp.tril(X, k=-1), -1, -2)


def tree_angles_jax(vectors, edges, jax, jnp):
    """theta/pi in [0,2) such that the Givens tree maps e_0 to each row (inverse map)."""
    V, N = vectors.shape
    u = vectors / (jnp.linalg.norm(vectors, axis=1, keepdims=True) + 1e-30)
    rev = edges[::-1]

    def step(u_c, e):
        p, c = e[0], e[1]
        up, uc = u_c[:, p], u_c[:, c]
        th = jnp.arctan2(uc, up) / jnp.pi
        a = jnp.hypot(up, uc)
        return u_c.at[:, p].set(a).at[:, c].set(0.0), th

    _, thetas_rev = jax.lax.scan(step, u, rev)      # thetas_rev: (N-1, V)
    return jnp.mod(thetas_rev[::-1].T, 2.0)         # (V, N-1)


def reconstruct_u_vectors_jax(theta_over_pi, edges, jax, jnp):
    """Forward Givens-tree rotations applied to e_0 for every row."""
    V, Na = theta_over_pi.shape
    N = Na + 1
    ej = jnp.asarray(edges)                      # (Na,2) JAX array -> dynamic gather OK

    def step(vecs, i):
        p, c = ej[i][0], ej[i][1]
        th = jnp.pi * theta_over_pi[:, i]
        ct, st = jnp.cos(th), jnp.sin(th)
        vp, vc = vecs[:, p], vecs[:, c]
        new = vecs.at[:, p].set(ct * vp - st * vc).at[:, c].set(st * vp + ct * vc)
        return new, None

    vecs = jnp.zeros((V, N)).at[:, 0].set(1.0)
    return jax.lax.scan(step, vecs, jnp.arange(Na))[0]


def ste_snap(x, brot, jnp):
    """Straight-through b-bit snap: forward = rounded grid value, backward = identity."""
    scale = 2 ** (brot - 1)
    rounded = jnp.floor(x * scale + 0.5) % (2 ** brot)
    snapped = rounded / scale
    import jax
    return x + jax.lax.stop_gradient(snapped - x)


def gf2_soft_entropy(words, brot, jnp):
    """Differentiable compile-friendliness proxy: summed soft Shannon entropy of the
    per-column word histograms. Lower = more concentrated = fewer distinct words =
    cheaper QROM. (words: (V, C) continuous on the b-bit grid.)"""
    V, C = words.shape
    nbins = 2 ** brot
    grid = jnp.arange(nbins) / (2 ** (brot - 1))            # bin centers in [0,2)
    sigma = 0.5 / (2 ** (brot - 1))
    d2 = ((words[:, :, None] - grid[None, None, :]) ** 2) / (sigma * sigma)
    p = jnp.exp(-d2).sum(0) / max(V, 1)                      # (C, nbins)
    p = p + 1e-9
    return -(p * jnp.log(p)).sum()


# ---------------------------------------------------------------------------
# JAX metrics + objective
# ---------------------------------------------------------------------------
def make_jax_continuous_metrics(c: Consts):
    """Continuous (unquantized) error_2 / E_gap / Lambda / lambda_eff in JAX f32."""
    jax, jnp = _jax()
    N, R = c.N, c.R
    oei = jnp.asarray(c.oei); tei = jnp.asarray(c.tei)
    S = jnp.asarray(c.S); E = jnp.asarray(c.eye)
    h1_thc = jnp.asarray(c.h1_thc)
    A_shift = jnp.asarray(c.A_shift); B_shift = jnp.asarray(c.B_shift)
    ecore = jnp.asarray(c.ecore); eta = jnp.asarray(c.electrons)
    eu = jnp.asarray(c.energy_upper); b1 = jnp.asarray(c.beta_1)

    def metrics(U, w, H2I):
        Wrc = H2I - w.sum(axis=1)                              # (R,G)
        Un = U / (jnp.linalg.norm(U, axis=2, keepdims=True) + 1e-30)
        X = jnp.einsum("rbp,rbq,rbg->rgpq", Un, Un, w)
        X = sym_lower(X, jnp)
        h1p = h1_thc - 0.5 * eta * S + b1 * E - jnp.einsum("rc,rcpq->pq", Wrc, X)
        evals = jnp.linalg.eigvalsh(h1p)
        h2d = jnp.einsum("rcpq,rcst->pqst", X, X) - tei - A_shift - B_shift
        error_2 = jnp.sqrt(jnp.sum(h2d * h2d))
        lam_h1 = jnp.sum(jnp.abs(evals))
        lam_h2 = 0.25 * jnp.sum((jnp.abs(w).sum(axis=1) + jnp.abs(H2I)) ** 2)
        Lambda = lam_h1 + lam_h2
        E_SOS = ecore - eta * b1 - (lam_h1 - jnp.sum(evals)) - 0.5 * jnp.sum(Wrc ** 2)
        E_gap = eu - E_SOS
        in_dom = (E_gap > 0) & (E_gap < 2 * Lambda)
        lam_eff = jnp.where(in_dom, jnp.sqrt(jnp.maximum(E_gap * (2 * Lambda - E_gap), 0.0)), jnp.nan)
        return {"error_2": error_2, "E_gap": E_gap, "Lambda": Lambda,
                "lambda_eff": lam_eff, "in_domain": in_dom, "X": X}
    return metrics


def make_jax_objective(c: Consts, alpha: float, gamma: float, beta: float,
                       brot: int = BROT, quantized: bool = True):
    """Composite objective over params dict {'U','w','H2I'} (f32)."""
    jax, jnp = _jax()
    N, R = c.N, c.R
    cont = make_jax_continuous_metrics(c)
    edges = c.edges
    tei = jnp.asarray(c.tei); A_shift = jnp.asarray(c.A_shift); B_shift = jnp.asarray(c.B_shift)
    S = jnp.asarray(c.S); E = jnp.asarray(c.eye); h1_thc = jnp.asarray(c.h1_thc)
    eta = jnp.asarray(c.electrons); b1 = jnp.asarray(c.beta_1); eu = jnp.asarray(c.energy_upper)
    ecore = jnp.asarray(c.ecore)

    @jax.jit
    def objective(params):
        U, w, H2I = params["U"], params["w"], params["H2I"]
        M = U.shape[1]
        Wrc = H2I - w.sum(axis=1)
        if quantized:
            # STE-snap the two-body Givens angles, decode, rebuild X from decoded vectors
            V2 = U.reshape(-1, N)
            th2 = tree_angles_jax(V2, edges, jax, jnp)
            w2 = ste_snap(th2, brot, jnp)
            u2 = reconstruct_u_vectors_jax(w2, edges, jax, jnp).reshape(R, M, N)
            X = jnp.einsum("rbp,rbq,rbg->rgpq", u2, u2, w)
            X = sym_lower(X, jnp)
            gf2 = beta * gf2_soft_entropy(w2, brot, jnp)
        else:
            Un = U / (jnp.linalg.norm(U, axis=2, keepdims=True) + 1e-30)
            X = jnp.einsum("rbp,rbq,rbg->rgpq", Un, Un, w)
            X = sym_lower(X, jnp)
            gf2 = jnp.asarray(0.0)
        h1p = h1_thc - 0.5 * eta * S + b1 * E - jnp.einsum("rc,rcpq->pq", Wrc, X)
        evals = jnp.linalg.eigvalsh(h1p)
        h2d = jnp.einsum("rcpq,rcst->pqst", X, X) - tei - A_shift - B_shift
        error_2 = jnp.sqrt(jnp.sum(h2d * h2d))
        lam_h1 = jnp.sum(jnp.abs(evals))
        lam_h2 = 0.25 * jnp.sum((jnp.abs(w).sum(axis=1) + jnp.abs(H2I)) ** 2)
        Lambda = lam_h1 + lam_h2
        E_SOS = ecore - eta * b1 - (lam_h1 - jnp.sum(evals)) - 0.5 * jnp.sum(Wrc ** 2)
        E_gap = eu - E_SOS
        barrier = alpha * jnp.maximum(0.0, EGAP_BARRIER - E_gap)
        sparsity = gamma * jnp.sum(jnp.abs(w))
        total = error_2 + barrier + sparsity + gf2
        return total
    return objective


# ---------------------------------------------------------------------------
# Optimizers
# ---------------------------------------------------------------------------
def run_lbfgs(objective, init_params, max_rounds: int, maxiter: int,
              ftol: float = 1e-12, gtol: float = 1e-8, maxls: int = 40):
    """Multi-restart L-BFGS-B (~max_rounds rounds x up to maxiter iterations each)."""
    import jax.scipy.optimize as jsopt
    fun = lambda p: float(objective(p))
    best, best_val = init_params, fun(init_params)
    cur = init_params
    history = [{"round": -1, "fun": best_val, "note": "init"}]
    for rnd in range(require_int("max_rounds", max_rounds, 1, 50)):
        res = jsopt.minimize(fun, cur, method="L-BFGS-B",
                             options={"maxiter": maxiter, "ftol": ftol,
                                      "gtol": gtol, "maxls": maxls})
        cur = res.x
        val = float(res.fun)
        history.append({"round": rnd, "fun": val, "nfev": int(res.nfev),
                        "status": int(res.status)})
        if val < best_val:
            best, best_val = cur, val
        if res.status in (0, 1, 2, 3):
            break
    return best, best_val, history


def run_adam(objective, init_params, steps: int, lr: float):
    """Small-LR Adam preconditioner (Stage 2c)."""
    import jax, jax.numpy as jnp
    import optax
    opt = optax.adam(lr)
    state = opt.init(init_params)
    p = init_params
    for _ in range(require_int("steps", steps, 1, 100000)):
        val, grads = jax.value_and_grad(objective)(p)
        updates, state = opt.update(grads, state, p)
        p = optax.apply_updates(p, updates)
    return p


# ---------------------------------------------------------------------------
# Authoritative (numpy f64) metrics + compile/verify
# ---------------------------------------------------------------------------
def authoritative_metrics(params: dict, c: Consts) -> dict:
    """Exact dfthc_math metrics (f64) for a verifier-format params dict."""
    import numpy as np
    from dfthcsos.scoreinfra.dfthc_math import (reconstruct_x, build_h1_prime,
                                                evaluate_dfthc_vectors)
    w = np.asarray(params["W"], dtype=np.float64)
    H2I = np.asarray(params["H2_I"], dtype=np.float64)
    W = H2I - w.sum(axis=1)
    N = int(np.shape(params["U"])[-1])
    S = np.asarray(c.S, dtype=np.float64)
    beta_1 = c.beta_1
    U = np.asarray(params["U"], dtype=np.float64)
    X = reconstruct_x(U, w)
    X = np.tril(X) + np.swapaxes(np.tril(X, k=-1), -1, -2)
    h1_thc = np.asarray(c.h1_thc, dtype=np.float64)
    h1p = build_h1_prime(h1_thc, S, beta_1, c.electrons, W, X)
    _, evec = np.linalg.eigh(h1p)
    u_all = np.vstack([evec.T, U.reshape(-1, N)])
    ref = {"oei": c.oei, "tei": c.tei, "ecore": c.ecore, "electrons": c.electrons,
           "orbitals": c.N}
    return evaluate_dfthc_vectors(u_all, w, W, S, beta_1, ref, energy_upper=c.energy_upper)


def save_factorization_npz(params: dict, path: str) -> str:
    import numpy as np
    require_path("out_dir", os.path.dirname(path))
    np.savez(path, U=params["U"], W=params["W"], H2_I=params["H2_I"],
             H1_I=params["H1_I"], Hsym_lower=params["Hsym_lower"])
    return path


def compile_and_verify(params: dict, tag: str) -> dict:
    """Encode -> build circuits -> official verify -> score/ratio. Authoritative."""
    import numpy as np
    from starter.task3_circuits.build_circuits import build_submission
    outdir = os.path.join(CIRCUIT_DIR, require_str("tag", tag))
    os.makedirs(outdir, exist_ok=True)
    fac_npz = os.path.join(outdir, "factorization.npz")
    save_factorization_npz(params, fac_npz)
    build_submission(SYSTEM, fac_npz, tree="log_depth", brot=BROT, batch_size=BATCH_SIZE,
                     rounding="nearest", output_directory=outdir, overwrite=True,
                     keep_bits=KEEP_BITS)
    proc = subprocess.run([sys.executable, OFFICIAL_VERIFY, outdir],
                          capture_output=True, text=True)
    out = proc.stdout
    start = out.rfind("{")
    if start < 0:
        raise RuntimeError(f"official verifier produced no JSON; stderr:\n{proc.stderr[-2000:]}")
    off = json.loads(out[start:])
    score = off.get("score")
    off["ratio"] = (REFERENCE_COST / score) if score else None
    off["_outdir"] = outdir
    return off


# ---------------------------------------------------------------------------
# Seed handling (load prebuilt, else build on the fly via seed_build)
# ---------------------------------------------------------------------------
def get_seed(kind: str, M: int, G: int, c: Consts, kmeans_seed: int = 0,
             rotate: bool = False) -> dict:
    """Return a verifier-format params dict for a seed of shape (M,G).
    kind in {'chol','trunc'}. Builds+caches under seed/ if missing."""
    import numpy as np
    require_str("kind", kind)
    M = require_int("M", M, 1, 200); G = require_int("G", G, 1, 60)
    fname = f"{kind}_seed_{M}_{G}.npz"
    fpath = os.path.join(SEED_DIR, fname)
    if kind == "chol" and kmeans_seed != 0:
        fpath = os.path.join(SEED_DIR, f"chol_seed_{M}_{G}_ks{kmeans_seed}.npz")
    if os.path.exists(fpath):
        z = np.load(fpath, allow_pickle=False)
        return {k: z[k] for k in ("U", "W", "H2_I", "H1_I", "Hsym_lower")}
    # build on the fly
    import seed_build as sb
    ii, jj, mult = sb.packed_pairs(c.N)
    Tfull = sb.build_target_full({"orbitals": c.N, "tei": c.tei}, c.S)
    T = Tfull[ii[:, None], jj[:, None], ii[None, :], jj[None, :]]
    if kind == "chol":
        tp = sb.build_compact_seed(T, ii, jj, mult, M, G, c.N, seed=kmeans_seed)
    elif kind == "trunc":
        base = np.load(BASELINE_NPZ, allow_pickle=False)
        tp = sb.truncate_seed(base["U"], base["W"], base["H2_I"], M, G)
    else:
        raise ValueError(f"unknown seed kind {kind!r}")
    if rotate:
        rng = np.random.default_rng(kmeans_seed + 1)
        U = tp["U"].copy()
        for r in range(c.R):
            Q, _ = np.linalg.qr(rng.standard_normal((M, M)))
            U[r] = U[r] @ Q.T
        tp["U"] = U
    tp["H1_I"] = c.h1_i; tp["Hsym_lower"] = c.hsym_lower
    os.makedirs(SEED_DIR, exist_ok=True)
    np.savez(fpath, U=tp["U"], W=tp["W"], H2_I=tp["H2_I"],
             H1_I=tp["H1_I"], Hsym_lower=tp["Hsym_lower"])
    return {k: tp[k] for k in ("U", "W", "H2_I", "H1_I", "Hsym_lower")}


def to_jax_params(params: dict, jnp):
    return {"U": jnp.asarray(params["U"]), "w": jnp.asarray(params["W"]),
            "H2I": jnp.asarray(params["H2_I"])}


def from_jax_params(jp: dict, c: Consts, np) -> dict:
    return {"U": np.asarray(jp["U"]), "W": np.asarray(jp["w"]),
            "H2_I": np.asarray(jp["H2I"]), "H1_I": c.h1_i, "Hsym_lower": c.hsym_lower}


# ---------------------------------------------------------------------------
# Result record + stage runner
# ---------------------------------------------------------------------------
@dataclass
class StageResult:
    stage: str
    shape: tuple
    seed_kind: str
    valid: bool
    error_2_ma: float
    error_1_ma: Optional[float]
    E_gap: float
    Lambda: float
    lambda_eff: float
    toffoli: Optional[int]
    qubits: Optional[int]
    score: Optional[float]
    ratio: Optional[float]
    dGM: Optional[float]
    recipe: str
    history: list = field(default_factory=list)

    def to_json(self) -> dict:
        d = asdict(self)
        d["shape"] = list(self.shape)
        return d


def train_shape(c: Consts, M: int, G: int, seed_kind: str, cfg: argparse.Namespace,
                kmeans_seed: int = 0, rotate: bool = False, adam_pre: int = 0) -> StageResult:
    """Train one (M,G) from one seed with the configured recipe; compile+verify."""
    import numpy as np
    _, jnp = _jax()
    tag = require_str("tag", f"s{cfg.stage}_{M}_{G}_{seed_kind}_k{kmeans_seed}")
    params0 = get_seed(seed_kind, M, G, c, kmeans_seed=kmeans_seed, rotate=rotate)
    jp0 = to_jax_params(params0, jnp)
    obj = make_jax_objective(c, cfg.alpha, cfg.gamma, cfg.beta, brot=cfg.brot,
                             quantized=not cfg.no_quantize)
    if adam_pre > 0:
        jp0 = run_adam(obj, jp0, steps=adam_pre, lr=cfg.adam_lr)
    best_jp, best_val, hist = run_lbfgs(obj, jp0, cfg.max_rounds, cfg.maxiter)
    params = from_jax_params(best_jp, c, np)
    am = authoritative_metrics(params, c)
    err2_ma = 1e3 * float(am["error_2"])
    valid = bool(err2_ma <= ERR2_GATE_MA and am["gap_in_domain"])
    res = StageResult(stage=f"stage{cfg.stage}", shape=(M, G), seed_kind=seed_kind,
                      valid=valid, error_2_ma=err2_ma, error_1_ma=None,
                      E_gap=float(am["E_gap"]), Lambda=float(am["Lambda"]),
                      lambda_eff=float(am["lambda_eff"]), toffoli=None, qubits=None,
                      score=None, ratio=None, dGM=None,
                      recipe=f"{seed_kind}+{'adam%d->' % adam_pre if adam_pre else ''}lbfgs",
                      history=hist)
    # compile + official verify (authoritative T/Q/ratio/error_1)
    try:
        off = compile_and_verify(params, tag)
        m, r = off.get("metrics", {}), off.get("resources", {})
        res.error_1_ma = 1e3 * float(m.get("error_1", 0.0))
        res.toffoli = int(r.get("toffoli", 0)); res.qubits = int(r.get("qubits", 0))
        res.score = off.get("score"); res.ratio = off.get("ratio")
        res.dGM = (res.ratio - BASELINE_RATIO) if res.ratio else None
        res.valid = res.valid and (res.ratio is not None and res.ratio > BASELINE_RATIO) \
            and (res.error_1_ma is not None and res.error_1_ma <= ERR2_GATE_MA)
    except Exception as exc:  # noqa: BLE001 - record and continue
        res.history.append({"compile_error": str(exc)[:500]})
    return res


def write_result(res: StageResult) -> str:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, f"{res.stage}_{res.shape[0]}_{res.shape[1]}_{res.seed_kind}.json")
    with open(path, "w") as fh:
        json.dump(res.to_json(), fh, indent=2)
    return path


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------
def stage0_anchor(cfg: argparse.Namespace) -> dict:
    """Reproduce 10.6976x on the stored qvc-007 circuits via the official verifier."""
    require_path("stored_circuits", STORED_CIRCUITS_DIR)
    proc = subprocess.run([sys.executable, OFFICIAL_VERIFY, STORED_CIRCUITS_DIR],
                          capture_output=True, text=True)
    out = proc.stdout; start = out.rfind("{")
    if start < 0:
        raise RuntimeError(f"Stage 0 verifier failed; stderr:\n{proc.stderr[-2000:]}")
    off = json.loads(out[start:])
    score = off.get("score")
    ratio = (REFERENCE_COST / score) if score else None
    reproduced = bool(off.get("status") == "PASS" and ratio is not None
                      and abs(ratio - BASELINE_RATIO) < 0.01)
    rec = {"stage": "stage0", "status": off.get("status"), "score": score,
           "ratio": ratio, "reproduced": reproduced,
           "metrics": off.get("metrics"), "resources": off.get("resources")}
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "stage0_anchor.json"), "w") as fh:
        json.dump(rec, fh, indent=2)
    return rec


def stage1_primary(c: Consts, cfg: argparse.Namespace) -> StageResult:
    M, G = STAGE1_SHAPE
    cfg.stage = 1
    res = train_shape(c, M, G, "chol", cfg)
    write_result(res)
    return res


def stage2_ladder(c: Consts, cfg: argparse.Namespace) -> list[StageResult]:
    """Fallback ladder for the PRIMARY shape; stop at first valid."""
    M, G = STAGE1_SHAPE
    results = []
    # (a) multi-start
    cfg.stage = 2
    for ks in range(cfg.n_starts):
        r = train_shape(c, M, G, "chol", cfg, kmeans_seed=ks + 1, rotate=(ks % 2 == 1))
        write_result(r); results.append(r)
        if r.valid:
            return results
    # (b) truncation warm-start
    r = train_shape(c, M, G, "trunc", cfg)
    write_result(r); results.append(r)
    if r.valid:
        return results
    # (c) hybrid Adam -> L-BFGS
    r = train_shape(c, M, G, "chol", cfg, adam_pre=cfg.adam_pre)
    write_result(r); results.append(r)
    return results


def stage3_sweep(c: Consts, cfg: argparse.Namespace, winner: StageResult) -> list[StageResult]:
    cfg.stage = 3
    results = []
    for M, G in STAGE3_SHAPES:
        r = train_shape(c, M, G, winner.seed_kind, cfg, kmeans_seed=winner._ks if hasattr(winner, "_ks") else 0)
        write_result(r); results.append(r)
    return results


def decide(results: list[StageResult], stage0: dict) -> dict:
    valid = [r for r in results if r.valid and (r.ratio or 0) > BASELINE_RATIO]
    os.makedirs(RESULTS_DIR, exist_ok=True)
    if not stage0.get("reproduced"):
        decision = {"decision": "BLOCKED", "reason": "Stage 0 did not reproduce 10.6976x"}
    elif valid:
        best = max(valid, key=lambda r: r.ratio)
        decision = {"decision": "GO", "best_shape": list(best.shape), "best_ratio": best.ratio,
                    "dGM": best.dGM, "recipe": best.recipe, "seed_kind": best.seed_kind,
                    "error_2_ma": best.error_2_ma, "error_1_ma": best.error_1_ma,
                    "lambda_eff": best.lambda_eff, "E_gap": best.E_gap, "Lambda": best.Lambda,
                    "toffoli": best.toffoli, "qubits": best.qubits,
                    "valid_count": len(valid)}
    else:
        decision = {"decision": "DEAD",
                    "reason": "no valid point (error_2<=20mHa & ratio>10.6976x) at target shapes",
                    "best_err2_per_stage": {
                        f"{r.stage}_{r.shape[0]}_{r.shape[1]}_{r.seed_kind}": r.error_2_ma
                        for r in results}}
    with open(os.path.join(RESULTS_DIR, "DECISION.json"), "w") as fh:
        json.dump(decision, fh, indent=2)
    return decision


# ---------------------------------------------------------------------------
# Self-test: JAX continuous metrics must match numpy dfthc_math on the current best
# ---------------------------------------------------------------------------
def selftest(c: Consts) -> bool:
    import numpy as np
    _, jnp = _jax()
    base = np.load(BASELINE_NPZ, allow_pickle=False)
    params = {k: base[k] for k in ("U", "W", "H2_I", "H1_I", "Hsym_lower")}
    am = authoritative_metrics(params, c)
    cont = make_jax_continuous_metrics(c)
    jp = to_jax_params(params, jnp)
    jm = cont(jp["U"], jp["w"], jp["H2I"])
    ok = True
    for key, tol in (("error_2", 5e-3), ("E_gap", 1e-4), ("Lambda", 1e-2), ("lambda_eff", 1e-2)):
        a = float(am[key]); b = float(jm[key])
        good = abs(a - b) <= tol * max(1.0, abs(a))
        ok = ok and good
        print(f"  {key:>10}: numpy={a:.6g}  jax={b:.6g}  {'OK' if good else 'MISMATCH'}")
    print("SELFTEST =", "PASS" if ok else "FAIL")
    return ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Staged DF-THC lower-rank GPU trainer")
    ap.add_argument("--stage", default="all", choices=["0", "1", "2", "3", "all", "smoke", "selftest"])
    ap.add_argument("--shapes", default="", help="override Stage-3 shapes, space-separated M,G")
    ap.add_argument("--alpha", type=float, default=1.0, help="E_gap barrier weight")
    ap.add_argument("--gamma", type=float, default=1e-4, help="sparsity ||w||_1 weight")
    ap.add_argument("--beta", type=float, default=1e-4, help="GF(2) entropy weight")
    ap.add_argument("--brot", type=int, default=BROT)
    ap.add_argument("--max-rounds", type=int, default=8, help="L-BFGS restart rounds")
    ap.add_argument("--maxiter", type=int, default=60000, help="L-BFGS iters per round")
    ap.add_argument("--n-starts", type=int, default=4, help="Stage-2a multi-start count")
    ap.add_argument("--adam-pre", type=int, default=200, help="Stage-2c Adam preconditioner steps")
    ap.add_argument("--adam-lr", type=float, default=1e-4)
    ap.add_argument("--no-quantize", action="store_true", help="use continuous objective (debug)")
    ap.add_argument("--x64", dest="x64", action="store_true", default=True,
                    help="JAX float64 (default on; required for accurate E_gap barrier)")
    ap.add_argument("--no-x64", dest="x64", action="store_false",
                    help="disable JAX float64 (faster on GPU but E_gap barrier becomes noisy)")
    ap.add_argument("--smoke-m", type=int, default=24, help="smoke-test M")
    ap.add_argument("--smoke-g", type=int, default=6, help="smoke-test G")
    return ap


def main(argv: Optional[list[str]] = None) -> int:
    global STAGE3_SHAPES
    cfg = build_parser().parse_args(argv)
    cfg.stage_num = 0
    require_str("stage", cfg.stage)
    import jax
    jax.config.update("jax_enable_x64", bool(cfg.x64))
    if cfg.shapes.strip():
        STAGE3_SHAPES = parse_shapes(cfg.shapes)

    print(f"[train_gpu] device(s): {os.environ.get('JAX_PLATFORMS', 'auto')}  "
          f"repo={REPO}", flush=True)
    c = load_consts()
    print(f"[train_gpu] N={c.N} R={c.R} energy_upper={c.energy_upper:.7f} "
          f"beta_1={c.beta_1:.6f}", flush=True)

    if cfg.stage == "selftest":
        return 0 if selftest(c) else 1

    if cfg.stage == "smoke":
        return run_smoke(c, cfg)

    # ---- gated pipeline ----
    stage0 = stage0_anchor(cfg)
    print(f"[stage0] reproduced={stage0['reproduced']} ratio={stage0['ratio']}", flush=True)
    if not stage0["reproduced"]:
        dec = decide([], stage0)
        print(f"[DECISION] BLOCKED: {dec['reason']}")
        return 2

    all_results: list[StageResult] = []
    if cfg.stage in ("all", "1"):
        s1 = stage1_primary(c, cfg)
        all_results.append(s1)
        print(f"[stage1] (130,35) valid={s1.valid} err2={s1.error_2_ma:.2f}m "
              f"ratio={s1.ratio}", flush=True)
        if cfg.stage == "1":
            dec = decide(all_results, stage0)
            print(f"[DECISION] {dec['decision']}"); return 0

    if cfg.stage in ("all", "2"):
        ladder = stage2_ladder(c, cfg)
        all_results.extend(ladder)
        for r in ladder:
            print(f"[stage2] {r.recipe} valid={r.valid} err2={r.error_2_ma:.2f}m ratio={r.ratio}",
                  flush=True)

    if cfg.stage in ("all", "3"):
        valid = [r for r in all_results if r.valid]
        if valid:
            winner = max(valid, key=lambda r: (r.ratio or 0))
            s3 = stage3_sweep(c, cfg, winner)
            all_results.extend(s3)
            for r in s3:
                print(f"[stage3] ({r.shape[0]},{r.shape[1]}) valid={r.valid} "
                      f"err2={r.error_2_ma:.2f}m ratio={r.ratio}", flush=True)
        else:
            print("[stage3] skipped (no valid point from stages 1-2)", flush=True)

    dec = decide(all_results, stage0)
    print(f"\n[DECISION] {dec['decision']}")
    print(json.dumps({k: v for k, v in dec.items() if k != 'best_err2_per_stage'}, indent=2))
    return 0


def run_smoke(c: Consts, cfg: argparse.Namespace) -> int:
    """End-to-end connectivity on a tiny config (CPU-safe): seed -> few L-BFGS steps
    -> compile -> official verify -> score. Proves every stage connects."""
    import numpy as np
    _, jnp = _jax()
    M, G = require_int("smoke_m", cfg.smoke_m, 4, 200), require_int("smoke_g", cfg.smoke_g, 2, 60)
    print(f"[smoke] shape=({M},{G}) tiny config, proving end-to-end connectivity", flush=True)
    # 1) seed (truncate current best to tiny shape - fast, right basin)
    params0 = get_seed("trunc", M, G, c)
    jp0 = to_jax_params(params0, jnp)
    obj = make_jax_objective(c, cfg.alpha, cfg.gamma, cfg.beta, brot=cfg.brot,
                             quantized=not cfg.no_quantize)
    # 2) a handful of L-BFGS iterations
    best_jp, best_val, hist = run_lbfgs(obj, jp0, max_rounds=1, maxiter=10)
    params = from_jax_params(best_jp, c, np)
    am = authoritative_metrics(params, c)
    print(f"[smoke] after 10 L-BFGS iters: obj={best_val:.5f} "
          f"err2={1e3*am['error_2']:.2f}m Egap={am['E_gap']:.4f} lamEff={am['lambda_eff']:.3f}",
          flush=True)
    # 3) compile + official verify + score
    off = compile_and_verify(params, "smoke")
    m, r = off.get("metrics", {}), off.get("resources", {})
    ratio = off.get("ratio")
    print(f"[smoke] compile+verify: status={off.get('status')} "
          f"err1={1e3*m.get('error_1',0):.2f}m err2={1e3*m.get('error_2',0):.2f}m "
          f"T={r.get('toffoli')} Q={r.get('qubits')} score={off.get('score'):.4g} ratio={ratio}",
          flush=True)
    ok = off.get("status") in ("PASS", "FAIL") and off.get("score") is not None \
        and np.isfinite(am["error_2"])
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "smoke.json"), "w") as fh:
        json.dump({"ok": bool(ok), "shape": [M, G], "official": off}, fh, indent=2)
    print(f"[smoke] CONNECTED = {bool(ok)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
