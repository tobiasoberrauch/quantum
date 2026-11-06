"""Exact symbolic repeat-finder (v3) using int-bitmask monomials.

Each variable -> one bit. A monomial -> an int bitmask. An ANF -> frozenset of ints.
  XOR = symmetric difference; AND = pairwise OR with mod-2 parity reduction.
No cap: values are tracked exactly (so XOR cancellations are visible). Products that
would exceed a hard guard are marked complex (counted), but the guard is set very high
so this almost never triggers.

Two CCX gates compute the same product iff their control-ANF pairs match (up to order).
Group by (unordered control-pair, effective condition). Size-k group => k-1 static
Toffolis cacheable (one copy CCX + k CNOTs + free del_and clear), provided operands are
stable across the span and a free wire exists.

READ-ONLY.
"""
from __future__ import annotations
import sys, json, time
from collections import defaultdict

ZERO = frozenset()
ONE = frozenset({0})          # constant 1 = empty monomial = bitmask 0
GUARD = 300_000_000           # |A|*|B| above this -> complex (rare)

def xor(a, b):
    if a is None or b is None: return None
    return a ^ b

def andf(a, b):
    if a is None or b is None: return None
    if len(a) * len(b) > GUARD: return None
    out = defaultdict(int)
    for m1 in a:
        for m2 in b: out[m1 | m2] += 1
    return frozenset(m for m, c in out.items() if c % 2)

def parse_ops(path):
    ops = []
    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if not line: continue
            toks = line.split(); op = toks[0]; args = toks[1:]; cb = None
            if 'if' in args:
                i = args.index('if'); cb = args[i+1]; args = args[:i]
            ops.append((op, args, cb))
    return ops

def main(kmx_path, out_path):
    t0 = time.time()
    ops = parse_ops(kmx_path)
    val = {}
    def get(w): return val.get(w, ZERO)
    def setw(w, a): val[w] = a
    nv = 0
    for i in range(22):
        w = f'q{i}'; nv += 1; setw(w, frozenset({1 << (nv-1)}))
    stack = []
    def eff(cb):
        a = ONE
        for s in stack:
            a = andf(a, s)
            if a is None: return None
        if cb is not None: a = andf(a, get(cb))
        return a

    recs = []
    mod_log = defaultdict(list)
    n_complex = 0
    max_size = 0
    for idx, (op, args, cb) in enumerate(ops):
        if op == 'PUSH_CONDITION':
            c = cb if cb is not None else (args[0] if args else None)
            stack.append(get(c) if c is not None else ONE); continue
        if op == 'POP_CONDITION': stack.pop(); continue
        if op in ('APPEND_TO_REGISTER', 'REGISTER'): continue
        cond = eff(cb)
        if op == 'X':
            t = args[0]; setw(t, xor(get(t), ONE)); mod_log[t].append(idx)
        elif op in ('Z', 'NEG', 'Z_POW'): pass
        elif op == 'CX':
            c, t = args; setw(t, xor(get(t), get(c))); mod_log[t].append(idx)
        elif op == 'CZ': pass
        elif op == 'CCX':
            c1, c2, t = args
            a1, a2 = get(c1), get(c2)
            prod = andf(a1, a2)
            nt = xor(get(t), prod); setw(t, nt); mod_log[t].append(idx)
            if a1 is None or a2 is None or cond is None: n_complex += 1
            if nt is not None and len(nt) > max_size: max_size = len(nt)
            recs.append(dict(idx=idx, type='CCX', c1=c1, c2=c2, tgt=t,
                             k1=a1, k2=a2, ck=cond))
        elif op == 'CCZ':
            c1, c2, c3 = args
            a1, a2, a3 = get(c1), get(c2), get(c3)
            if a1 is None or a2 is None or a3 is None or cond is None: n_complex += 1
            recs.append(dict(idx=idx, type='CCZ', c1=c1, c2=c2, tgt=c3,
                             k1=a1, k2=a2, k3=a3, ck=cond))
        elif op == 'SWAP':
            a, b = args; va, vb = get(a), get(b); setw(a, vb); setw(b, va)
            mod_log[a].append(idx); mod_log[b].append(idx)
        elif op == 'CSWAP':
            c, a, b = args
            d = xor(get(a), get(b)); p = andf(get(c), d)
            na = xor(get(a), p); nb = xor(get(b), p)
            setw(a, na); setw(b, nb); mod_log[a].append(idx); mod_log[b].append(idx)
            if get(c) is None or cond is None: n_complex += 1
            recs.append(dict(idx=idx, type='CSWAP', c1=c, c2=a, tgt=b,
                             kc=get(c), ka=na, kb=nb, ck=cond))
        elif op == 'HMR':
            q, b = args; nv += 1; setw(b, frozenset({1 << (nv-1)})); setw(q, ZERO)
            mod_log[q].append(idx); mod_log[b].append(idx)
        elif op == 'R':
            q = args[0]; setw(q, ZERO); mod_log[q].append(idx)
        elif op == 'BIT_STORE0':
            b = args[0]; setw(b, ZERO); mod_log[b].append(idx)
        elif op == 'BIT_STORE1':
            b = args[0]; setw(b, ONE); mod_log[b].append(idx)
        elif op == 'BIT_INVERT':
            b = args[0]; setw(b, xor(get(b), ONE)); mod_log[b].append(idx)

    # canonical key for an ANF (hashable)
    def key(anf):
        return None if anf is None else tuple(sorted(anf))

    g_ccx = defaultdict(list); g_ccz = defaultdict(list); g_cswap = defaultdict(list)
    # cross-check: repeated (c1,c2) WIRE-NAME pairs vs their actual control-ANF pairs
    namepair_occ = defaultdict(list)   # (c1name,c2name) -> list of (idx, anfpairkey or None)
    for r in recs:
        if r['type'] == 'CCX':
            k1, k2, kc = key(r['k1']), key(r['k2']), key(r['ck'])
            ak = (tuple(sorted([k1, k2])), kc) if None not in (k1, k2, kc) else None
            namepair_occ[(r['c1'], r['c2'])].append((r['idx'], ak))
            if ak is None: continue
            g_ccx[ak].append(r)
        elif r['type'] == 'CCZ':
            k1, k2, k3, kc = key(r['k1']), key(r['k2']), key(r['k3']), key(r['ck'])
            if None in (k1, k2, k3, kc): continue
            g_ccz[(tuple(sorted([k1, k2])), k3, kc)].append(r)
        elif r['type'] == 'CSWAP':
            kc, ck = key(r['kc']), key(r['ck'])
            if kc is None or ck is None: continue
            g_cswap[(kc, ck)].append(r)

    # analyze name-pair repeats
    np_total_rep = 0          # name-pairs occurring >=2 times
    np_with_exact = 0         # ...of which we have exact ANFs for >=2 occurrences
    np_true_repeat = 0        # ...of which the exact ANF pairs actually match (>=2 same anfpair)
    np_examples = []
    for (n1, n2), occ in namepair_occ.items():
        if len(occ) < 2: continue
        np_total_rep += 1
        exact = [ak for _, ak in occ if ak is not None]
        if len(exact) >= 2:
            np_with_exact += 1
            from collections import Counter as _C
            c = _C(exact)
            best = max(c.values())
            if best >= 2:
                np_true_repeat += 1
                np_examples.append((n1, n2, len(occ), best))

    def stable(rs, wires):
        lo = min(r['idx'] for r in rs); hi = max(r['idx'] for r in rs)
        use = set(r['idx'] for r in rs)
        for w in wires:
            for m in mod_log[w]:
                if lo < m < hi and m not in use: return False
        return True

    def summarize(groups, wirefn):
        chains = []
        for k, rs in groups.items():
            if len(rs) >= 2:
                st = stable(rs, wirefn(rs[0]))
                chains.append(dict(size=len(rs), save=len(rs)-1, stable=st,
                                   idxs=[r['idx'] for r in rs], wires=wirefn(rs[0])))
        chains.sort(key=lambda c: -c['size'])
        return chains

    ccx_chains = summarize(g_ccx, lambda r: [r['c1'], r['c2']])
    ccz_chains = summarize(g_ccz, lambda r: [r['c1'], r['c2']])
    cswap_chains = summarize(g_cswap, lambda r: [r['c1']])

    def sav(chains, stable_only=False):
        return sum(c['save'] for c in chains if (c['stable'] or not stable_only))

    result = dict(
        elapsed_s=round(time.time()-t0, 2), num_ops=len(ops),
        toffoli_like_gates=len(recs),
        ccx=sum(1 for r in recs if r['type']=='CCX'),
        ccz=sum(1 for r in recs if r['type']=='CCZ'),
        cswap=sum(1 for r in recs if r['type']=='CSWAP'),
        n_complex=n_complex, max_anf_size=max_size, num_vars=nv,
        ccx_groups=len(g_ccx), ccz_groups=len(g_ccz), cswap_groups=len(g_cswap),
        namepair_repeats=np_total_rep, namepair_with_exact=np_with_exact,
        namepair_true_product_repeats=np_true_repeat, namepair_true_examples=np_examples[:20],
        ccx_chains=len(ccx_chains), ccz_chains=len(ccz_chains), cswap_chains=len(cswap_chains),
        est_save_ccx_all=sav(ccx_chains), est_save_ccx_stable=sav(ccx_chains, True),
        est_save_ccz_all=sav(ccz_chains), est_save_ccz_stable=sav(ccz_chains, True),
        est_save_cswap_all=sav(cswap_chains), est_save_cswap_stable=sav(cswap_chains, True),
        est_save_total_all=sav(ccx_chains)+sav(ccz_chains)+sav(cswap_chains),
        est_save_total_stable=sav(ccx_chains,True)+sav(ccz_chains,True)+sav(cswap_chains,True),
        ccx_chain_sizes=[c['size'] for c in ccx_chains],
        ccz_chain_sizes=[c['size'] for c in ccz_chains],
        cswap_chain_sizes=[c['size'] for c in cswap_chains],
        ccx_top=ccx_chains[:40], ccz_top=ccz_chains[:20], cswap_top=cswap_chains[:20],
    )
    with open(out_path, 'w') as f: json.dump(result, f, indent=2)
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ('ccx_top','ccz_top','cswap_top')}, indent=2))
    print('\nCCX top chains:')
    for c in ccx_chains[:25]:
        print(f"  size={c['size']} save={c['save']} stable={c['stable']} wires={c['wires']} idxs={c['idxs'][:12]}")
    print('\nCCZ top chains:')
    for c in ccz_chains[:15]:
        print(f"  size={c['size']} save={c['save']} stable={c['stable']} wires={c['wires']} idxs={c['idxs'][:12]}")
    print('\nCSWAP top chains:')
    for c in cswap_chains[:15]:
        print(f"  size={c['size']} save={c['save']} stable={c['stable']} wires={c['wires']} idxs={c['idxs'][:12]}")

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
