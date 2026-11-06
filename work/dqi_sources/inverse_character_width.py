"""Exact, compact inverse-character phase schedules for private converters.

The ordinary branch has two stored products and two cubic phases.  The
zero-mixed and zero-only branches have three stored products and one cubic
phase.  This file never builds or changes a decoder on import.
"""
from pathlib import Path
from types import CodeType, FunctionType, ModuleType, SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'exp/r-main/narrow240'),
                str(ROOT/'research/agents/a01')]
import exact_subs as xs
from rebind_graph import private_rebind

USED = False
ORDINARY_FORMS = ((12,52), (154,94))
ORDINARY_TERMS = ((2,), (4,), (5,), (7,), (0,6), (1,6), (1,7),
                  (2,3), (2,5), (2,7), (3,7))
ORDINARY_COLUMNS = (10,19,34,65,5,129,1,2)
ORDINARY_INVERSE = (64,128,80,129,194,132,72,96)
MIXED_FORMS = ((23,78), (60,234), (15,182))
MIXED_TERMS = ((), (1,), (2,3), (2,4), (2,5), (3,4), (3,8),
              (4,), (4,5), (4,8), (5,8), (7,), (8,))
MIXED_COLUMNS = (10,19,37,66,135,257,1,2,4)
MIXED_INVERSE = (64,128,256,129,194,324,136,464,96)


def quadratic_phase(b, source, terms):
    for term in terms:
        if not term:
            b.z(True)
        elif len(term) == 1:
            b.z(source[term[0]])
        else:
            b.cz(source[term[0]], source[term[1]])


def cubic_phase(b, source, columns, inverse):
    """Phase l0*l1*(1+l2), restoring every source coordinate."""
    xs.linear_inplace(b, source, columns)
    b.cz(source[0], source[1])
    b.ccz(source[0], source[1], source[2])
    xs.linear_inplace(b, source, inverse)


def character(b, x, forms, terms, columns, inverse, extra=False):
    work = b.alloc_qubits(len(forms))
    source = list(x)+list(work)
    for i, pair in enumerate(forms):
        with xs.expose_pair(b, source[:6+i], *pair) as (left,right):
            b.init_and(left,right,work[i])
    quadratic_phase(b, source, terms)
    cubic_phase(b, source, columns, inverse)
    if extra:
        b.ccz(x[0], x[2], x[3])
    for i in reversed(range(len(forms))):
        with xs.expose_pair(b, source[:6+i], *forms[i]) as (left,right):
            b.del_and(left,right,work[i])
    b.free(work)


def ordinary(b, x):
    character(b,x,ORDINARY_FORMS,ORDINARY_TERMS,
              ORDINARY_COLUMNS,ORDINARY_INVERSE,True)


def mixed(b, x):
    character(b,x,MIXED_FORMS,MIXED_TERMS,MIXED_COLUMNS,MIXED_INVERSE)


def zero_phase(b, x):
    b.x(x)
    work = b.alloc_qubits(3)
    b.init_and(x[0], x[1], work[0])
    for i in range(1,3):
        b.init_and(work[i-1], x[i+1], work[i])
    b.ccz(work[2], x[4], x[5])
    for i in reversed(range(1,3)):
        b.del_and(work[i-1], x[i+1], work[i])
    b.del_and(x[0], x[1], work[0])
    b.free(work)
    b.x(x)


def phase_inverse6(b, x, mask, zero_mask=None):
    global USED
    USED = True
    assert len(x) == len(mask) == 6
    for m in range(1,64):
        eq = xs.classical_equal(b, mask, m)
        b.push_condition(eq)
        xs.linear_inplace(b, x, xs.SCALES[m])
        if zero_mask is None:
            ordinary(b, x)
        else:
            b.push_condition(zero_mask)
            mixed(b, x)
            b.pop_condition()
            b.x(zero_mask)
            b.push_condition(zero_mask)
            ordinary(b, x)
            b.pop_condition()
            b.x(zero_mask)
        xs.linear_inplace(b, x, xs.UNSCALES[m])
        b.pop_condition()
        b.free(eq)
    if zero_mask is not None:
        eq = xs.classical_equal(b, mask, 0)
        b.push_condition(eq)
        b.push_condition(zero_mask)
        zero_phase(b, x)
        b.pop_condition()
        b.pop_condition()
        b.free(eq)


def target_ids(entry):
    """Find original helper copies only in this converter's private graph."""
    seen, targets = set(), set()

    def owned(path):
        try:
            return Path(path).resolve().is_relative_to(ROOT)
        except (TypeError,ValueError):
            return False

    def names(code):
        result = set(code.co_names)
        for item in code.co_consts:
            if isinstance(item,CodeType):
                result.update(names(item))
        return result

    def visit(value):
        key = id(value)
        if key in seen:
            return
        seen.add(key)
        if isinstance(value,FunctionType) and owned(value.__code__.co_filename):
            if value.__name__ == 'phase_inverse6_quad4' and Path(value.__code__.co_filename).name == 'exact_subs.py':
                targets.add(key)
            for name in names(value.__code__):
                if name in value.__globals__:
                    visit(value.__globals__[name])
            for cell in value.__closure__ or ():
                try:
                    visit(cell.cell_contents)
                except ValueError:
                    pass
        elif isinstance(value,SimpleNamespace) or (
                isinstance(value,ModuleType) and owned(getattr(value,'__file__',None))):
            for name,item in vars(value).items():
                if name != '__builtins__':
                    visit(item)
        elif isinstance(value,dict):
            for item in value.values():
                visit(item)
        elif isinstance(value,(tuple,list)):
            for item in value:
                visit(item)
        elif isinstance(value,FunctionType) and getattr(value,'__wrapped__',None) is not None:
            visit(value.__wrapped__)
    visit(entry)
    return targets


def install_converter(cv):
    ids = target_ids(cv)
    assert ids, 'The intended inverse-character API was not found'
    return private_rebind(cv, {key:phase_inverse6 for key in ids}, ROOT)


def install_decoder(decoder):
    cells = dict(zip(decoder.__code__.co_freevars,decoder.__closure__))
    scope = cells['g'].cell_contents
    scope['convert_safe'] = install_converter(scope['convert_safe'])
    return decoder
