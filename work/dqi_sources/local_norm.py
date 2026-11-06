"""Keep selected pivot-norm coordinates only across the final undo action.

The saved coordinates are copied from a norm that the ordinary producer
already computed.  The final inverse character reconstructs only its missing
coordinates, then erases the complete norm with its exact quadratic phase.
"""
from pathlib import Path
from contextlib import contextmanager
import inspect
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'research/agents/a01'))
import ported_exact_cycle as baseline
import exact_subs as xs
import norm_cache as nc
from exp.noscratch.schedules import norm_xor_noscratch
from exp.noscratch.kernels import mul_xor_noscratch

p = baseline.p
ar = p.ar
TRACE = []


def inverse_zero_kept(b, x, count):
    to, frm, kval = ar.tower(12)
    ar.linear_inplace(b, x, to)
    norm = b.alloc_qubits(6)
    norm_xor_noscratch(b, x, norm, kval)
    projection, _ = nc.layout(count)
    saved = b.alloc_qubits(count)
    ar.linear_xor(b, norm, saved, [v & ((1 << count)-1) for v in projection])
    invnorm, zero = xs.inverse6_joint18_12extra(b, norm)
    ar._erase_norm(b, x, norm, kval)
    b.free(norm)
    out = b.alloc_qubits(12)
    b.cx(x[6:], x[:6])
    mul_xor_noscratch(b, x[:6], invnorm, out[:6])
    mul_xor_noscratch(b, x[6:], invnorm, out[6:])
    b.cx(x[6:], x[:6])
    ar._erase_norm(b, out, invnorm, kval)
    b.free(invnorm)
    ar.linear_inplace(b, x, frm)
    ar.linear_inplace(b, out, frm)
    return out, zero, saved


def make_cached_phase():
    source = inspect.getsource(xs.phase_inverse12_virtual_nonzero)
    source = source.replace('def phase_inverse12_virtual_nonzero(b, x, mask, zero_mask=None):',
                            'def phase_inverse_cached(b, x, mask, saved, zero_mask=None):')
    needle = '    D = b.alloc_qubits(6)\n    norm_xor_noscratch(b, x, D, K)'
    assert source.count(needle) == 1
    source = source.replace(needle, '    D = rebuild_norm(b, x, saved, K)')
    scope = dict(xs.phase_inverse12_virtual_nonzero.__globals__, rebuild_norm=nc.rebuild)
    exec(compile(source, __file__, 'exec'), scope)
    return scope['phase_inverse_cached']


phase_inverse_cached = make_cached_phase()


def erase_kept(b, x, inv, zero, saved):
    mask = b.alloc_bits(12)
    zm = b.alloc_bits(1)
    b.hmr(inv, mask)
    b.hmr(zero, zm[0])
    b.free(inv)
    b.free(zero)
    phase_inverse_cached(b, x, mask, saved, zm[0])
    b.free(mask)
    b.free(zm)


def make_decoder(count=1, levels=range(6, 17), quotient_count=0, plain_count=0,
                 plain_levels=range(2, 6), factorized=False, converter=None,
                 reference_decode=None):
    cv = baseline.convert_safe if converter is None else converter
    cells = dict(zip(cv.__code__.co_freevars, cv.__closure__))
    short = cells['core'].cell_contents.__globals__
    scope = short['old'].direct_post.__globals__
    dispatcher = scope['direct_pre']
    d_cells = dict(zip(dispatcher.__code__.co_freevars, dispatcher.__closure__))
    original = d_cells['handed'].cell_contents
    scope = original.__globals__
    levels = frozenset(levels)

    def handed(b, f, g, payloads, flag, incoming, defer, z0):
        if len(f)-1 not in levels:
            return original(b, f, g, payloads, flag, incoming, defer, z0)
        assert not defer
        b.cx(z0, g[-2][0])
        masks = scope['high_full_restore'](b, f, g, flag)
        b.cx(z0, g[-2][0])
        scope['pivot'](b, g, flag)
        a = g[-1]
        ai, zero, saved = inverse_zero_kept(b, a, count)
        b.cx(zero, z0)
        b.free(z0)
        scope['consume'](b, ai, zero, incoming)
        b.cx(zero, a[0])
        b.cx(zero, ai[0])
        scope['high_close_heads'](b, f, g, ai, flag, masks)
        for v in payloads:
            scope['dk'].shifted_product(b, g[:-1], v[-1], v[:-1], flag)
        for v in payloads:
            scope['scale'](b, v[-1], a, ai, False)
        b.cx(zero, ai[0])
        b.cx(zero, a[0])
        erase_kept(b, a, ai, zero, saved)
        scope['pivot'](b, g, flag)

    # install_undo_zeros captures this function directly in its dispatcher.
    d_cells['handed'].cell_contents = handed
    scope['handed_aligned_pre'] = handed

    if quotient_count:
        old_q_inverse = scope['q_inverse']

        @contextmanager
        def q_inverse(b, a, m, reverse, phase):
            if not reverse or m == 16:
                with old_q_inverse(b, a, m, reverse, phase) as ai:
                    yield ai
                return
            ai, zero, saved = inverse_zero_kept(b, a, quotient_count)
            scope['consume'](b, ai, zero, phase['q'].pop(m))
            b.cx(zero, a[0]); b.cx(zero, ai[0])
            yield ai
            b.cx(zero, ai[0]); b.cx(zero, a[0])
            erase_kept(b, a, ai, zero, saved)

        scope['q_inverse'] = q_inverse

    if plain_count:
        plain_levels = frozenset(plain_levels)
        plain_dispatcher = scope['pre']
        plain_cells = dict(zip(plain_dispatcher.__code__.co_freevars,
                               plain_dispatcher.__closure__))
        plain_original = plain_cells['plain_handed'].cell_contents

        def plain(b, f, g, payloads, incoming, defer, z0):
            if len(f)-1 not in plain_levels:
                return plain_original(b, f, g, payloads, incoming, defer, z0)
            assert not defer
            a = g[-1]
            b.cx(z0, a[0]); masks = scope['full_restore'](b, f, g); b.cx(z0, a[0])
            ai, zero, saved = inverse_zero_kept(b, a, plain_count)
            b.cx(zero, z0); b.free(z0)
            scope['consume'](b, ai, zero, incoming)
            b.cx(zero, a[0]); b.cx(zero, ai[0])
            scope['close_heads'](b, f, g, ai, masks)
            for v in payloads:
                for i in range(len(g)-1): ar.mul_xor0(b, g[i], v[-1], v[i])
            for v in payloads: scope['scale'](b, v[-1], a, ai, False)
            b.cx(zero, ai[0]); b.cx(zero, a[0])
            erase_kept(b, a, ai, zero, saved)

        plain_cells['plain_handed'].cell_contents = plain
        scope['handed_plain_pre'] = plain
    reference = baseline.decode if reference_decode is None else reference_decode
    decode = p.clone(reference, dict(reference.__globals__, convert_safe=cv))
    if not factorized:
        return decode
    from rebind_graph import private_rebind
    return private_rebind(p.install_factorized_boundary(decode),
                          p.base.replacements, p.ROOT)
