"""One scalar return for the retained homogeneous extraction nodes.

The forward is unchanged. A terminal ratio is copied before the reverse
chain and is normalized alongside N and sqrt(L). Its complete phase debts
are closed before the old N is measured. A direct denominator is recovered
from its chart, and one scalar reverse restores N and closes that mask.
"""
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(ROOT), str(ROOT/'exp/frontier/a05')]
import decode_q8q9 as base
import scalar_projection_multi as walk
import exact_subs as xs
import frozen_chart as frozen
from replay_erase import scalar_erase_second24


def normalize_three(b, N, D, L, R):
    ref.external_square24(b, L, True)
    r, g = D[:12], D[12:]
    F = ref.guarded.fresh_zero_flag(b, g)
    b.cswap(F, r, g)
    oldg = inverse_stream_noscratch(b, g)
    olda = scale_defer(b, r, g)
    for x in (N, L, R):
        correct_subfield(b, x, F)
        ar.mul_xor0(b, r, x[12:], x[:12])
    hm1 = [scale_defer(b, x[12:], g) for x in (N, L, R)]
    im = inverse_stream_noscratch(b, g)
    b.cz(g, oldg)
    b.free(oldg)
    ar.phase_product(b, r, g, olda)
    b.free(olda)
    for x, m in zip((N, L, R), hm1):
        ar.phase_product(b, x[12:], g, m)
        b.free(m)
    h = b.alloc_qubits(1)[0]
    chart_norm(b, r, F, h)
    gm = scale_defer(b, g, r)
    chart_norm(b, r, F, h, True)
    b.free(h)
    hm = inverse_stream_noscratch(b, g)
    hm2 = [scale_defer(b, x[:12], g) for x in (N, L, R)]
    b.x(r[0])
    b.cx(F, r[0])
    for x in (N, L, R):
        ar.mul_xor0(b, r, x[:12], x[12:])
        b.swap(x[:12], x[12:])
    b.cx(F, r[0])
    b.x(r[0])
    ref.external_square24(b, L)
    return dict(g=gm, i=im, h=hm, half=hm2), F


def pay_before_retire(b, D, F, forward, reverse, N, L, R):
    r, g = D[:12], D[12:]
    b.cz(F, forward['f'][0])
    b.free(forward['f'])
    b.x(r[0])
    b.cx(F, r[0])
    masks = dict(g=forward['g'],
                 i=add_masks(b, forward['i'], reverse['h']),
                 h=add_masks(b, forward['h'], reverse['i']),
                 t=add_masks(b, forward['t'], reverse['g']),
                 r=forward['r'])
    ref.external_square24(b, L, True)
    linear_inverse_character(b, g, masks['i'],
                             [(N[12:], reverse['half'][0]),
                              (L[12:], reverse['half'][1]),
                              (R[12:], reverse['half'][2])])
    ref.external_square24(b, L)
    b.free(masks.pop('i'))
    for m in reverse['half']:
        b.free(m)
    b.cz(g, masks['g'])
    b.free(masks.pop('g'))
    b.cz(r, masks['r'])
    b.free(masks.pop('r'))
    return masks


def restore_direct(b, D, F, masks):
    r, g = D[:12], D[12:]
    merged_chart(b, r, F)
    keep = b.alloc_qubits(12)
    b.cx(g, keep)
    gm = scale_defer(b, g, r)
    b.cz(g, masks['h'])
    b.free(masks['h'])
    phase_inverse36_pivot(b, g, masks['t'])
    b.free(masks['t'])
    m = b.alloc_bits(12)
    b.hmr(g, m)
    b.swap(g, keep)
    b.free(keep)
    ar.phase_product(b, g, r, m)
    b.free(m)
    b.cz(g, gm)
    b.free(gm)
    merged_chart(b, r, F, True)
    am = scale_defer(b, r, g)
    zero = b.alloc_bits(12)
    b.bit_store(zero, False)
    linear_inverse_character(b, g, zero, [(r, am)])
    b.free(zero)
    b.free(am)
    b.cswap(F, r, g)
    fm = b.alloc_bits(1)
    b.hmr(F, fm[0])
    b.free(F)
    b.x(g)
    frozen.phase_and(b, g, fm[0])
    b.x(g)
    b.free(fm)


def external_node_chain(b, words, gi, reverse=False, token=None, normalizer=None):
    if not reverse or gi not in SELECT:
        return forward_original(b, words, gi, reverse, token, normalizer)
    gn = ref.groups[gi]
    N = combine(words[gn['word']:gn['word']+2])
    L = combine(words[gn['word']+2:gn['word']+4])
    heads = [words[2*i:2*i+2] for i in range(2*gi)]
    params = []
    c = 0
    for i in range(2*gi):
        q = ref.ks[i] ^ gn['kap']
        params.append((q, c))
        c ^= inv(q)
    assert c == 0
    pole = token['pole']
    R = b.alloc_qubits(24)
    b.cx(N, R)
    D = b.alloc_qubits(24)
    b.x(D[0])
    b.cx(pole, N[0])
    b.cx(pole, D[0])
    for head, (q, c) in reversed(list(zip(heads, params))[1:]):
        ref.external_chain_step(b, head, N, D, L, q, gn['c'], c, True)
    q0 = params[0][0]
    scalepair(b, N, inv(q0))
    b.swap(N, D)
    scalepair(b, L, inv(q0))
    with b.mark('companion_normalize'):
        norm, F = normalize_three(b, N, D, L, R)
        masks = pay_before_retire(b, D, F, token['norm'], norm, N, L, R)
    a, h = heads[0]
    cx(b, h, a, gn['c'])
    b.cx(combine(heads[0]), N)
    cx(b, h, a, gn['c'])
    b.cx(h, L[:12])
    original = b.alloc_bits(24)
    b.hmr(N, original)
    b.swap(N, R)
    b.free(R)
    with b.mark('companion_direct'):
        restore_direct(b, D, F, masks)
    b.cswap(pole, N, D)
    fm = b.alloc_bits(1)
    b.hmr(pole, fm[0])
    b.free(pole)
    b.push_condition(fm[0])
    clean_zero_phase24(b, D)
    b.pop_condition()
    b.free(fm)
    with b.mark('companion_return'):
        for i in reversed(range(len(heads))):
            if i == 1:
                scalar_erase_second24(b, heads[i], N, D, params[i][0], gn['c'], q0)
            else:
                ref.external_scalar_step(b, heads[i], N, D, params[i][0], gn['c'], True, first=i == 0)
    b.x(D[0])
    b.free(D)
    b.cz(N, original)
    b.free(original)


def install(entry, select=range(9, 17)):
    replacements = {}
    original = entry.__globals__['extraction']
    for fn in walk.functions(original):
        if fn.__name__ != 'external_node_chain' or 'normalize_early' not in fn.__code__.co_names:
            continue
        scope = dict(fn.__globals__)
        norm_scope = dict(scope['normalize_early'].__globals__)
        direct_scope = dict(scope['direct_chart'].__globals__, frozen=frozen)
        scope.update(forward_original=fn, SELECT=frozenset(select),
                     normalize_three=xs.clone(normalize_three, norm_scope),
                     pay_before_retire=xs.clone(pay_before_retire, direct_scope),
                     restore_direct=xs.clone(restore_direct, direct_scope),
                     scalar_erase_second24=scalar_erase_second24)
        replacements[id(fn)] = xs.clone(external_node_chain, scope)
    assert replacements
    return xs.clone(entry, dict(entry.__globals__, extraction=xs.private_rebind(original, replacements)))


decode = install(base.decode)
