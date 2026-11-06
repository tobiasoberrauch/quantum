#!/usr/bin/env python3
"""All-branch check: state evolution is independent of HMR coins (only CZ is conditioned), so per-HMR phase
correctness can be checked exactly on every in-range address, covering all 2^HMR measurement branches. Also tests
the XOR contract on random z inputs (the verifier only feeds z = previous batch).
Usage: exact_branch.py <member_dir> <random z trials> <seed>
"""
import sys

import numpy as np

sys.path.insert(0, '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/work/frontier_1104/verify_chem/scripts')
from indep_sim import parse  # noqa: E402

A, NQ = 76 + 8 * 143, 128


def main() -> None:
    member, trials, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    rng = np.random.default_rng(seed)
    parsed = [parse(f'{member}/angle_k_{k}.kmb') for k in range(15)]
    names = parsed[0][1]
    sel, regs = names['selection'], [names[f'word_{j}'] for j in range(5)]
    pub = set(sel) | {q for r in regs for q in r}
    work = [q for q in range(NQ) if q not in pub]
    addr = np.arange(A)
    words = np.load(member + '/submission.npz', allow_pickle=False)['angle_words']
    padded = np.zeros((A, 75), dtype=np.int64)
    padded[:, :75] = words
    batch = [padded[:, 5 * k:5 * k + 5] for k in range(15)]
    n_hmr = n_r = 0

    def exec_exact(ops, z):
        nonlocal n_hmr, n_r
        st = np.zeros((NQ, A), dtype=bool)
        for i, q in enumerate(sel):
            st[q] = (addr >> i) & 1
        for j, r in enumerate(regs):
            for i, q in enumerate(r):
                st[q] = (z[:, j] >> i) & 1
        open_hmr = {}
        for o in ops:
            n = o[0]
            if n == 'CX':
                st[o[2]] ^= st[o[1]]
            elif n == 'CCX':
                st[o[3]] ^= st[o[1]] & st[o[2]]
            elif n == 'X':
                st[o[1]] ^= True
            elif n == 'R':
                n_r += 1
                assert not st[o[1]].any(), 'R on nonzero qubit: uncorrectable dephasing'
            elif n == 'HMR':
                n_hmr += 1
                if o[2] in open_hmr:
                    q, acc = open_hmr[o[2]]
                    assert np.array_equal(q, acc), 'HMR phase not cancelled on some address'
                open_hmr[o[2]] = (st[o[1]].copy(), np.zeros(A, dtype=bool))
                st[o[1]] = False
            elif n == 'CZIF':
                q, acc = open_hmr[o[3]]
                acc ^= st[o[1]] & st[o[2]]
        for q, acc in open_hmr.values():
            assert np.array_equal(q, acc), 'HMR phase not cancelled on some address'
        assert not st[work].any(), 'workspace dirty'
        for i, q in enumerate(sel):
            assert np.array_equal(st[q], ((addr >> i) & 1).astype(bool)), 'selection changed'
        out = np.stack([sum(st[q].astype(np.int64) << i for i, q in enumerate(r)) for r in regs], axis=1)
        return out

    for k, (ops, _) in enumerate(parsed):
        prev = batch[k - 1] if k else np.zeros((A, 5), dtype=np.int64)
        out = exec_exact(ops, prev)
        assert np.array_equal(out, batch[k]), f'k{k} forward loads wrong words'
        back = exec_exact(ops, batch[k])
        assert np.array_equal(back, prev), f'k{k} reverse wrong'
        delta = batch[k] ^ prev
        for t in range(trials):
            z = rng.integers(0, 256, (A, 5), dtype=np.int64)
            assert np.array_equal(exec_exact(ops, z), z ^ delta), f'k{k} XOR contract fails on random z'
    print(f'EXACT OK {member}: all {A} addresses, 15 circuits fwd+rev, phase cancels per HMR on all branches; '
          f'{trials} random-z trials per circuit hold XOR contract. HMR visits={n_hmr} R visits={n_r}')


if __name__ == '__main__':
    main()
