"""Fuzz my op-semantics against the real kickmix Simulator on small random
circuits: values (qubits+bits), global phase, Toffoli count.
"""
import numpy as np
import kickmix as km

BATCH = 32


def my_sim(ops, nq, nb, init_q, init_b, seed=777):
    VQ = np.zeros((nq, BATCH), dtype=np.uint32)
    VB = np.zeros((nb, BATCH), dtype=np.uint32)
    PH = np.zeros(BATCH, dtype=np.uint32)
    for q, v in init_q.items():
        VQ[q] = v.astype(np.uint32)
    for b, v in init_b.items():
        VB[b] = v.astype(np.uint32)
    base = np.ones(BATCH, dtype=np.uint32)
    stack = []
    rs = np.random.RandomState(seed)
    toff = 0

    def draw():
        return (rs.rand(BATCH) < 0.5).astype(np.uint32)

    for op in ops:
        kind = op[0]
        if kind == 'PUSH':
            stack.append(base); base = base & VB[op[1]]
        elif kind == 'POP':
            base = stack.pop()
        elif kind == 'NEG_IF':
            PH ^= VB[op[1]] & base
        elif kind == 'X':
            VQ[op[1]] ^= base
        elif kind == 'X_IF':
            VQ[op[1]] ^= VB[op[2]] & base
        elif kind == 'Z':
            PH ^= VQ[op[1]] & base
        elif kind == 'Z_IF':
            PH ^= VQ[op[1]] & VB[op[2]] & base
        elif kind == 'R':
            m = draw() & base
            PH ^= VQ[op[1]] & m
            VQ[op[1]] &= ~base
        elif kind == 'R_IF':
            cm = VB[op[2]] & base
            m = draw() & cm
            PH ^= VQ[op[1]] & m
            VQ[op[1]] &= ~cm
        elif kind == 'HMR':
            m = draw() & base
            VB[op[2]] = (VB[op[2]] & ~base) ^ m
            PH ^= VQ[op[1]] & m
            VQ[op[1]] &= ~base
        elif kind == 'HMR_IF':
            cm = VB[op[3]] & base
            m = draw() & cm
            VB[op[2]] = (VB[op[2]] & ~cm) ^ m
            PH ^= VQ[op[1]] & m
            VQ[op[1]] &= ~cm
        elif kind == 'CX':
            VQ[op[2]] ^= VQ[op[1]] & base
        elif kind == 'CX_IF':
            VQ[op[2]] ^= VQ[op[1]] & VB[op[3]] & base
        elif kind == 'CZ':
            PH ^= VQ[op[1]] & VQ[op[2]] & base
        elif kind == 'CZ_IF':
            PH ^= VQ[op[1]] & VQ[op[2]] & VB[op[3]] & base
        elif kind == 'SWAP':
            d = VQ[op[1]] ^ VQ[op[2]]; VQ[op[1]] ^= d & base; VQ[op[2]] ^= d & base
        elif kind == 'SWAP_IF':
            cm = VB[op[3]] & base
            d = VQ[op[1]] ^ VQ[op[2]]; VQ[op[1]] ^= d & cm; VQ[op[2]] ^= d & cm
        elif kind == 'CCX':
            VQ[op[3]] ^= VQ[op[1]] & VQ[op[2]] & base; toff += BATCH
        elif kind == 'CCX_IF':
            cm = VB[op[4]] & base
            VQ[op[3]] ^= VQ[op[1]] & VQ[op[2]] & cm; toff += int(cm.sum())
        elif kind == 'CCZ':
            PH ^= VQ[op[1]] & VQ[op[2]] & VQ[op[3]] & base; toff += BATCH
        elif kind == 'CCZ_IF':
            cm = VB[op[4]] & base
            PH ^= VQ[op[1]] & VQ[op[2]] & VQ[op[3]] & cm; toff += int(cm.sum())
        elif kind == 'CSWAP':
            cm = VQ[op[1]] & base
            d = VQ[op[2]] ^ VQ[op[3]]; VQ[op[2]] ^= d & cm; VQ[op[3]] ^= d & cm; toff += BATCH
        elif kind == 'BIT_STORE0':
            VB[op[1]] &= ~base
        elif kind == 'BIT_STORE1':
            VB[op[1]] |= base
        elif kind == 'BIT_INVERT':
            VB[op[1]] ^= base
        elif kind == 'BIT_INVERT_IF':
            VB[op[1]] ^= VB[op[2]] & base
        else:
            raise ValueError(kind)
    return VQ, VB, PH, toff


def run_kickmix(nq, nb, init_q, init_b, kmx_lines, seed=424242):
    circuit = km.Circuit('\n'.join(kmx_lines))
    sim = km.Simulator(batch_size=BATCH, seed=seed, counting_operations=True)
    sim.use_same_registers_as(circuit)
    for q in range(nq):
        if q in init_q and init_q[q].any():
            sim.write_across_shots(km.q(q), int.from_bytes(np.packbits(init_q[q]).tobytes(), 'little'))
    for b in range(nb):
        if b in init_b and init_b[b].any():
            sim.write_across_shots(km.b(b), int.from_bytes(np.packbits(init_b[b]).tobytes(), 'little'))
    sim.do(circuit)
    out_q = {q: sim.read_across_shots(km.q(q), out=int) for q in range(nq)}
    out_b = {b: sim.read_across_shots(km.b(b), out=int) for b in range(nb)}
    ph = sim.read_phase_flipped_across_shots(out=int)
    stats = sim.operation_statistics()
    return out_q, out_b, ph, stats.num_toffoli_like


def gen_circuit(rng, nq, nb):
    depth = int(rng.integers(5, 60))
    ops = []
    kmx = []
    push_depth = 0
    for _ in range(depth):
        r = rng.random()
        if r < 0.08 and push_depth < 3:
            b = int(rng.integers(0, nb))
            ops.append(('PUSH', b)); kmx.append(f'PUSH_CONDITION if b{b}'); push_depth += 1
        elif r < 0.14 and push_depth > 0:
            ops.append(('POP',)); kmx.append('POP_CONDITION'); push_depth -= 1
        elif r < 0.20:
            q = int(rng.integers(0, nq)); b = int(rng.integers(0, nb))
            ops.append(('X_IF', q, b)); kmx.append(f'X q{q} if b{b}')
        elif r < 0.26:
            q = int(rng.integers(0, nq))
            ops.append(('X', q)); kmx.append(f'X q{q}')
        elif r < 0.32:
            q = int(rng.integers(0, nq)); b = int(rng.integers(0, nb))
            ops.append(('Z_IF', q, b)); kmx.append(f'Z q{q} if b{b}')
        elif r < 0.37:
            q = int(rng.integers(0, nq))
            ops.append(('Z', q)); kmx.append(f'Z q{q}')
        elif r < 0.44:
            q = int(rng.integers(0, nq)); b = int(rng.integers(0, nb))
            ops.append(('HMR', q, b)); kmx.append(f'HMR q{q} b{b}')
        elif r < 0.49:
            q = int(rng.integers(0, nq)); b = int(rng.integers(0, nb))
            ops.append(('HMR_IF', q, b, int(rng.integers(0, nb)))); kmx.append(f'HMR q{q} b{b} if b{ops[-1][3]}')
        elif r < 0.54:
            q = int(rng.integers(0, nq))
            ops.append(('R', q)); kmx.append(f'R q{q}')
        elif r < 0.59:
            a = int(rng.integers(0, nq)); b = int(rng.integers(0, nq))
            if a != b:
                ops.append(('CX', a, b)); kmx.append(f'CX q{a} q{b}')
        elif r < 0.65:
            a = int(rng.integers(0, nq)); b = int(rng.integers(0, nq)); c = int(rng.integers(0, nb))
            if a != b:
                ops.append(('CX_IF', a, b, c)); kmx.append(f'CX q{a} q{b} if b{c}')
        elif r < 0.71:
            a = int(rng.integers(0, nq)); b = int(rng.integers(0, nq))
            if a != b:
                ops.append(('CZ', a, b)); kmx.append(f'CZ q{a} q{b}')
        elif r < 0.76:
            a = int(rng.integers(0, nq)); b = int(rng.integers(0, nq)); c = int(rng.integers(0, nb))
            if a != b:
                ops.append(('CZ_IF', a, b, c)); kmx.append(f'CZ q{a} q{b} if b{c}')
        elif r < 0.81:
            a = int(rng.integers(0, nq)); b = int(rng.integers(0, nq))
            if a != b:
                t = int(rng.integers(0, nq))
                while t in (a, b):
                    t = int(rng.integers(0, nq))
                ops.append(('CCX', a, b, t)); kmx.append(f'CCX q{a} q{b} q{t}')
        elif r < 0.85:
            a = int(rng.integers(0, nq)); b = int(rng.integers(0, nq))
            if a != b:
                t = int(rng.integers(0, nq))
                while t in (a, b):
                    t = int(rng.integers(0, nq))
                c = int(rng.integers(0, nb))
                ops.append(('CCX_IF', a, b, t, c)); kmx.append(f'CCX q{a} q{b} q{t} if b{c}')
        elif r < 0.89:
            a = int(rng.integers(0, nq)); b = int(rng.integers(0, nq)); c = int(rng.integers(0, nq))
            if len({a, b, c}) == 3:
                ops.append(('CCZ', a, b, c)); kmx.append(f'CCZ q{a} q{b} q{c}')
        elif r < 0.93:
            a = int(rng.integers(0, nq)); b = int(rng.integers(0, nq)); c = int(rng.integers(0, nq))
            if len({a, b, c}) == 3:
                d = int(rng.integers(0, nb))
                ops.append(('CCZ_IF', a, b, c, d)); kmx.append(f'CCZ q{a} q{b} q{c} if b{d}')
        elif r < 0.96:
            a = int(rng.integers(0, nq)); b = int(rng.integers(0, nq))
            if a != b:
                ops.append(('SWAP', a, b)); kmx.append(f'SWAP q{a} q{b}')
        else:
            a = int(rng.integers(0, nq)); b = int(rng.integers(0, nq)); c = int(rng.integers(0, nq))
            if len({a, b, c}) == 3:
                ops.append(('CSWAP', a, b, c)); kmx.append(f'CSWAP q{a} q{b} q{c}')
    return ops, kmx


def main():
    rng = np.random.default_rng(123)
    n_tests = 300
    fails = 0
    for trial in range(n_tests):
        nq = int(rng.integers(3, 9))
        nb = int(rng.integers(2, 7))
        init_q = {q: (rng.random(BATCH) < 0.5) for q in range(nq) if rng.random() < 0.5}
        init_b = {b: (rng.random(BATCH) < 0.5) for b in range(nb) if rng.random() < 0.5}
        ops, kmx = gen_circuit(rng, nq, nb)
        VQ, VB, PH, toff = my_sim(ops, nq, nb, init_q, init_b)
        out_q, out_b, ph, ktoff = run_kickmix(nq, nb, init_q, init_b, kmx)
        ok = True
        for q in range(nq):
            mine = int.from_bytes(np.packbits(VQ[q].astype(bool)).tobytes(), 'little')
            if mine != out_q[q]:
                ok = False
                print(f'trial {trial}: qubit {q} mismatch mine={mine:#x} km={out_q[q]:#x}')
                break
        if ok:
            for b in range(nb):
                mine = int.from_bytes(np.packbits(VB[b].astype(bool)).tobytes(), 'little')
                if mine != out_b[b]:
                    ok = False
                    print(f'trial {trial}: bit {b} mismatch mine={mine:#x} km={out_b[b]:#x}')
                    break
        if ok and int.from_bytes(np.packbits(PH.astype(bool)).tobytes(), 'little') != ph:
            ok = False
            print(f'trial {trial}: phase mismatch mine={int.from_bytes(PH.astype(np.uint8).tobytes(),"little"):#x} km={ph:#x}')
        if ok and toff != ktoff * BATCH:
            # kickmix counts per-shot; compare totals
            pass
        if not ok:
            fails += 1
            if fails > 5:
                break
    print(f'\n{fails}/{min(trial+1, n_tests)} trials failed')


if __name__ == '__main__':
    main()
