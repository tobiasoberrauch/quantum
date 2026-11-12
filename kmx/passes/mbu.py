"""Measurement-Based Uncomputation für reversible Uncompute-Ketten."""

from __future__ import annotations

import heapq
from collections.abc import Sequence
from typing import TypedDict

from kmx.domains import Domain
from kmx.layout import Layout
from kmx.ops import Op, bit_token, qubit_token
from kmx.passes.repack import ROLE_X_TARGET, ScratchTouches, trace_touches
from kmx.simulator import push_depths

# (Scratch-Qubit, Indizes der Kette)
UncomputeChain = tuple[int, list[int]]


class MbuStats(TypedDict, total=False):
    """Statistik von pass_mbu; ohne Kette leer."""

    chains: int
    toffoli_saved: int


def _mbu_uncompute_chains(
    ops: Sequence[Op], depths: Sequence[int], touches: ScratchTouches
) -> list[UncomputeChain]:
    """(Qubit, Indizes) aller lückenlosen Folgen unbedingter X/CX/CCX auf ein
    Scratch-Qubit, nach denen es auf der ganzen Domäne |0> ist und die mindestens ein
    CCX enthalten (sonst spart MBU nichts).
    """
    chains: list[UncomputeChain] = []
    for q, qubit_touches in touches.items():
        run: list[int] = []
        for i, role, zero in qubit_touches:
            if role != ROLE_X_TARGET or depths[i] != 0:
                run = []
                continue
            run.append(i)
            if zero:
                if any(ops[j].name == "CCX" for j in run):
                    chains.append((q, run))
                run = []
    return chains


def _mbu_phase_fix(op: Op, bit: int) -> list[Op]:
    """Phasenkorrektur, die ein X/CX/CCX einer Uncompute-Kette ersetzt, wirksam nur bei
    Messergebnis `bit` = 1. War das Gatter selbst schon `if bN`-bedingt, bleibt diese
    Bedingung am Gatter und `bit` kommt per PUSH dazu.
    """
    if op.name == "CCX":
        name, args = "CZ", (qubit_token(op.qs[0]), qubit_token(op.qs[1]))
    elif op.name == "CX":
        name, args = "Z", (qubit_token(op.qs[0]),)
    else:
        name, args = "NEG", ()
    if op.cond is None:
        return [Op(name, args, bit)]
    return [Op("PUSH_CONDITION", (), bit), Op(name, args, op.cond), Op("POP_CONDITION")]


def pass_mbu(
    ops: Sequence[Op], layout: Layout, dom: Domain
) -> tuple[list[Op], MbuStats]:
    """Measurement-Based Uncomputation. Endet eine Folge von X/CX/CCX auf ein
    Scratch-Qubit t damit, dass t auf der ganzen Domäne |0> ist (und wird t
    dazwischen nicht gelesen), dann hielt t vorher genau die XOR-Summe dieser Terme.
    Ersatz: HMR t b am Anfang, und jedes Gatter wird zur klassisch bedingten
    Phasenkorrektur (CCX a b t -> CZ a b if b; CX a t -> Z a if b; X t -> NEG if b).
    Jedes CCX der Kette spart ein Toffoli.
    """
    depths = push_depths(ops)
    chains = _mbu_uncompute_chains(ops, depths, trace_touches(ops, layout, dom))
    if not chains:
        return list(ops), {}
    used_bits = {o.bit for o in ops if o.bit is not None} | {
        o.cond for o in ops if o.cond is not None
    }
    next_bit = max(used_bits, default=-1) + 1
    # Heap (frei ab Index, Bit): Messbits abgeschlossener Ketten
    pool: list[tuple[int, int]] = []
    repl: dict[int, list[Op]] = {}
    saved = 0
    for q, run in sorted(chains, key=lambda chain: chain[1][0]):
        if pool and pool[0][0] < run[0]:
            _, bit = heapq.heappop(pool)
        else:
            bit, next_bit = next_bit, next_bit + 1
        heapq.heappush(pool, (run[-1], bit))
        for k, i in enumerate(run):
            op = ops[i]
            saved += op.name == "CCX"
            measure = [Op("HMR", (qubit_token(q), bit_token(bit)))] if k == 0 else []
            repl[i] = measure + _mbu_phase_fix(op, bit)
    out: list[Op] = []
    for i, op in enumerate(ops):
        if i in repl:
            out.extend(repl[i])
        else:
            out.append(op)
    return out, {"chains": len(chains), "toffoli_saved": saved}
