"""Validate my_sim vs kickmix on DETERMINISTIC circuits (no HMR/R) — isolates
gate semantics + phase logic from RNG-stream differences."""
import numpy as np
import kickmix as km
import sys
sys.path.insert(0, '/Users/tobiasoberrauch/Repositories/tobiasoberrauch/quantum/work/dqi_t_sprint')
from fuzz_ops import my_sim, gen_circuit

BATCH = 32


def km_run(kmx, nq, nb, init_q=None, init_b=None, seed=1):
    circuit = km.Circuit(kmx)
    sim = km.Simulator(batch_size=BATCH, seed=seed)
    sim.use_same_registers_as(circuit)
    for q, v in (init_q or {}).items():
        sim.write_across_shots(km.q(q), int.from_bytes(np.packbits(v).tobytes(), 'little'))
    for b, v in (init_b or {}).items():
        sim.write_across_shots(km.b(b), int.from_bytes(np.packbits(v).tobytes(), 'little'))
    sim.do(circuit)
    oq = {q: sim.read_across_shots(km.q(q), out=int) for q in range(nq)}
    ob = {b: sim.read_across_shots(km.b(b), out=int) for b in range(nb)}
    ph = sim.read_phase_flipped_across_shots(out=int)
    return oq, ob, ph


def main():
    rng = np.random.default_rng(555)
    fails = 0
    n = 200
    for trial in range(n):
        nq = int(rng.integers(3, 9))
        nb = int(rng.integers(2, 7))
        init_q = {q: (rng.random(BATCH) < 0.5) for q in range(nq) if rng.random() < 0.5}
        init_b = {b: (rng.random(BATCH) < 0.5) for b in range(nb) if rng.random() < 0.5}
        ops, kmx = gen_circuit(rng, nq, nb)
        # strip HMR/R ops (make deterministic)
        ops_d = [op for op in ops if op[0] not in ('HMR', 'HMR_IF', 'R', 'R_IF')]
        # rebuild kmx to match ops_d: regenerate is hard; instead filter kmx lines
        kmx_d = [ln for ln in kmx if not ln.startswith(('HMR', 'R '))]
        # careful: 'R ' prefix could match nothing else; HMR lines start with HMR
        VQ, VB, PH, toff = my_sim(ops_d, nq, nb, init_q, init_b)
        oq, ob, ph = km_run('\n'.join(kmx_d), nq, nb, init_q, init_b)
        ok = True
        for q in range(nq):
            mine = int.from_bytes(np.packbits(VQ[q].astype(bool)).tobytes(), 'little')
            if mine != oq[q]:
                ok = False; print(f't{trial} q{q}: mine={mine:#x} km={oq[q]:#x}'); break
        if ok:
            for b in range(nb):
                mine = int.from_bytes(np.packbits(VB[b].astype(bool)).tobytes(), 'little')
                if mine != ob[b]:
                    ok = False; print(f't{trial} b{b}: mine={mine:#x} km={ob[b]:#x}'); break
        if ok:
            mine = int.from_bytes(np.packbits(PH.astype(bool)).tobytes(), 'little')
            if mine != ph:
                ok = False; print(f't{trial} phase: mine={mine:#x} km={ph:#x}')
        if not ok:
            fails += 1
            if fails > 5:
                break
    print(f'\n{fails}/{min(trial+1, n)} deterministic trials failed')


if __name__ == '__main__':
    main()
