#!/usr/bin/env python3
"""Independent classical-trajectory simulator and independent metric code (no kickmix.Simulator, no dfthc_math).

Reads gate text via kickmix only for parsing. Implements the semantics documented in scoreinfra/circuits.py:
HMR/R draw a fresh coin per shot, phase flips when coin=1 and qubit=1, qubit is then |0>.
Usage: indep_sim.py <member_dir> <shots> <numpy seed> <out.json>
"""
import json
import sys
import time

import kickmix as km
import numpy as np
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/data/verifiers')
from dfthcsos.scoreinfra.reference import check_fcidump, load_fixed_shifts, load_reference, UPPER_ENERGY  # noqa: E402

N, ETA = 76, 113


def parse(path: str) -> tuple[list, dict]:
    ops, regs, names = [], {}, {}
    pending: dict[int, list[int]] = {}
    for line in str(km.Circuit.from_file(path, format='kmb')).splitlines():
        p = line.split()
        if p[0] == 'APPEND_TO_REGISTER':
            pending.setdefault(int(p[2][1:]), []).append(int(p[1][1:]))
        elif p[0] == 'REGISTER':
            names[p[2].strip('"')] = pending[int(p[1][1:])]
        elif p[0] in ('CX', 'X', 'R'):
            ops.append((p[0], *[int(x[1:]) for x in p[1:]]))
        elif p[0] == 'CCX':
            ops.append(('CCX', *[int(x[1:]) for x in p[1:]]))
        elif p[0] == 'HMR':
            ops.append(('HMR', int(p[1][1:]), int(p[2][1:])))
        elif p[0] == 'CZ' and p[3] == 'if':
            ops.append(('CZIF', int(p[1][1:]), int(p[2][1:]), int(p[4][1:])))
        else:
            raise SystemExit('unknown op ' + line)
    return ops, names


def run(ops: list, st: np.ndarray, phase: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    bits: dict[int, np.ndarray] = {}
    ccx = 0
    for o in ops:
        n = o[0]
        if n == 'CX':
            st[o[2]] ^= st[o[1]]
        elif n == 'CCX':
            st[o[3]] ^= st[o[1]] & st[o[2]]
            ccx += 1
        elif n == 'X':
            st[o[1]] ^= True
        elif n == 'R':
            coin = rng.integers(0, 2, st.shape[1], dtype=bool)
            phase ^= coin & st[o[1]]
            st[o[1]] = False
        elif n == 'HMR':
            coin = rng.integers(0, 2, st.shape[1], dtype=bool)
            phase ^= coin & st[o[1]]
            st[o[1]] = False
            bits[o[2]] = coin
        elif n == 'CZIF':
            phase ^= st[o[1]] & st[o[2]] & bits[o[3]]
    return ccx


def recover(member: str, shots: int, seed: int) -> tuple[np.ndarray, int, int]:
    parsed = [parse(f'{member}/angle_k_{k}.kmb') for k in range(15)]
    names = parsed[0][1]
    sel = names['selection']
    words = [names[f'word_{j}'] for j in range(sum(x.startswith('word_') for x in names))]
    brot = len(words[0])
    A = 76 + 8 * 143
    pub = set(sel) | {q for w in words for q in w}
    nq = 128
    addr = np.tile(np.arange(A), shots)
    rng = np.random.default_rng(seed)

    def fresh(batch):
        st = np.zeros((nq, addr.size), dtype=bool)
        for i, q in enumerate(sel):
            st[q] = (addr >> i) & 1
        if batch is not None:
            full = np.tile(batch, (shots, 1))
            for j, reg in enumerate(words):
                for i, q in enumerate(reg):
                    st[q] = (full[:, j] >> i) & 1
        return st

    def read(st):
        t = np.stack([sum((st[q].astype(np.int64) << i) for i, q in enumerate(reg)) for reg in words], axis=1)
        t = t.reshape(shots, A, len(words))
        assert (t == t[0]).all(), 'shots disagree'
        return t[0]

    def check(st, phase, label):
        assert not phase.any(), label + ' phase'
        work = [q for q in range(nq) if q not in pub]
        assert not st[work].any(), label + ' workspace'
        for i, q in enumerate(sel):
            assert (st[q] == ((addr >> i) & 1).astype(bool)).all(), label + ' selection'

    batches, ccx, batch = [], 0, None
    for k, (ops, _) in enumerate(parsed):
        st, phase = fresh(batch), np.zeros(addr.size, dtype=bool)
        ccx += run(ops, st, phase, rng)
        check(st, phase, f'fwd{k}')
        batch = read(st)
        batches.append(batch)
    for k in reversed(range(15)):
        st, phase = fresh(batches[k]), np.zeros(addr.size, dtype=bool)
        ccx += run(parsed[k][0], st, phase, rng)
        check(st, phase, f'rev{k}')
        back = read(st)
        assert (back == (batches[k - 1] if k else np.zeros_like(back))).all(), f'rev{k} restore'
    w = np.concatenate(batches, axis=1)
    assert not w[:, 75:].any(), 'padding'
    return w[:, :75], brot, ccx


def metrics(words: np.ndarray, brot: int, w: np.ndarray, wB: np.ndarray, edges: np.ndarray) -> dict:
    ref = load_reference(check_fcidump())
    shifts = load_fixed_shifts()
    Sf = np.zeros((N, N), dtype=np.float32)
    Sf[np.tril_indices(N)] = np.asarray(shifts['Hsym_lower']).astype(np.float32)
    S = (Sf + Sf.T - np.diag(np.diag(Sf))).astype(np.float64)
    beta = float(shifts['H1_I']) - 0.5 * float(np.trace(S))
    W = wB - w.sum(axis=1)
    th = np.pi * words / (1 << (brot - 1))
    v = np.zeros((words.shape[0], N))
    v[:, 0] = 1
    for t, (p, c) in enumerate(edges):
        a, b = v[:, p].copy(), v[:, c].copy()
        v[:, p] = np.cos(th[:, t]) * a - np.sin(th[:, t]) * b
        v[:, c] = np.sin(th[:, t]) * a + np.cos(th[:, t]) * b
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    R, B, C = w.shape
    u = v[N:].reshape(R, B, N)
    X = np.zeros((R, C, N, N))
    for r in range(R):
        P = u[r][:, :, None] * u[r][:, None, :]  # B,N,N
        X[r] = np.tensordot(w[r].T, P, axes=(1, 0))
    L = np.tril(X)
    X = L + np.swapaxes(np.tril(X, -1), 2, 3)
    tei = np.asarray(ref['tei'], dtype=np.float64)
    oei = np.asarray(ref['oei'], dtype=np.float64)
    h1 = oei - 0.5 * np.einsum('prrq->pq', tei)
    Wx = (W[:, :, None, None] * X).sum(axis=(0, 1))
    hp = h1 - 0.5 * ETA * S + beta * np.eye(N) - Wx
    ev, vec = np.linalg.eigh(hp)
    # own assignment-based residual
    ov = np.abs(v[:N] @ vec)
    ri, ci = linear_sum_assignment(ov, maximize=True)
    lam = np.empty(N)
    lam[ri] = ev[ci]
    e1 = np.linalg.norm((v[:N].T * lam) @ v[:N] - hp)
    # two-body residual, packed through the Gram matrix of flattened X
    F = X.reshape(R * C, N * N)
    G = F.T @ F
    D = G - tei.reshape(N * N, N * N)
    idx = np.arange(N) * (N + 1)
    D[:, idx] -= 0.5 * S.reshape(N * N, 1)
    D[idx, :] -= 0.5 * S.reshape(1, N * N)
    e2 = np.linalg.norm(D)
    lam1 = np.abs(ev).sum()
    lam2 = 0.25 * ((np.abs(w).sum(axis=1) + np.abs(wB)) ** 2).sum()
    Lam = lam1 + lam2
    Esos = ref['ecore'] - ETA * beta - (lam1 - ev.sum()) - 0.5 * (W ** 2).sum()
    Eg = UPPER_ENERGY - Esos
    return dict(e1=float(e1), e2=float(e2), Lambda=float(Lam), E_gap=float(Eg), lambda_eff=float(np.sqrt(Eg * (2 * Lam - Eg))))


def main() -> None:
    member, shots, seed, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    t0 = time.time()
    words, brot, ccx = recover(member, shots, seed)
    d = np.load(member + '/submission.npz', allow_pickle=False)
    res = dict(member=member, shots=shots, seed=seed, brot=brot, ccx_two_pass=ccx,
               words_match_npz=bool(np.array_equal(words, d['angle_words'])))
    res.update(metrics(words, brot, d['W'].astype(np.float64), d['H2_I'].astype(np.float64), d['tree_edges']))
    res['secs'] = round(time.time() - t0, 1)
    text = json.dumps(res, indent=1)
    print(text)
    open(out, 'w', encoding='utf-8').write(text)


if __name__ == '__main__':
    main()
