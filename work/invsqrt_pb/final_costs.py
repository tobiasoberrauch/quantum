"""Final P-B cost computation + scanner sanity check + blocker arithmetic.

1. Sanity-check the conditional-toffoli scanner on the CURRENT SOTA circuit
   (work/frontier_scan/mwa_unpacked/invsqrt.kmb), which is known to have ~254
   conditional toffolis (from P-A task2_toffoli_map). If the scanner finds ~254,
   the cond==0 result on the P-B variants is trustworthy.
2. Recompute the official cost model (C, score, ratio, dGM) for each P-B variant
   using the authoritative min_margin from the official full-domain verify JSONs.
3. Blocker arithmetic: how much must Q and/or C improve to flip to GO.
"""
import os, json, math
import numpy as np
import kickmix as km

HERE = os.path.dirname(os.path.abspath(__file__))
CONST = os.path.abspath(os.path.join(HERE, '..', 'constseed_build'))
REF_COST = 2076774.233715282
CUR_Q, CUR_C, CUR_RATIO = 62, 1589.26, 21.0768
TOFF = {'CCX', 'CSWAP', 'CCZ'}

def cond_scan(circ):
    lines = str(circ).splitlines(); depth = 0; cond = 0; tot = 0
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith('#'): continue
        name = s.split()[0]
        if name == 'PUSH_CONDITION': depth += 1; continue
        if name == 'POP_CONDITION': depth -= 1; continue
        if name in TOFF:
            tot += 1
            if depth > 0: cond += 1
    return tot, cond

# ---- 1. scanner sanity on current SOTA ----
sota = km.Circuit.from_file('work/frontier_scan/mwa_unpacked/invsqrt.kmb')
st_tot, st_cond = cond_scan(sota)
print(f'[sanity] current SOTA invsqrt.kmb: static toffoli-like={st_tot}, conditional={st_cond} '
      f'(expect ~1487 / ~254 from P-A map)')

# ---- 2. official cost model per variant ----
def official_cost(Q, toffoli_count, t_base, n_rot, eps):
    t_count = t_base + (n_rot * (0.56*math.log2(1/eps) + 5.3) if n_rot else 0)
    C = toffoli_count + t_count / 4
    score = Q * C
    return C, score, REF_COST / score

VARIANTS = [
    # label, kmb, verify_json
    ('PRIMARY lookup all-persistent', 'invsqrt_constseed_lookup.kmb', 'verify_full_lookup.json'),
    ('lookup hybrid N1-transient',    'invsqrt_constseed_lookup_hybrid.kmb', None),
    ('raw Horner all-persistent',     'invsqrt_constseed.kmb', 'verify_full.json'),
    ('raw Horner transient',          'invsqrt_constseed_current.kmb', None),
]
out = []
print(f'\n{"variant":32s} {"Q":>4s} {"meanT":>7s} {"T":>3s} {"rot":>4s} {"eps":>11s} {"C":>9s} {"score":>12s} {"ratio":>8s} {"dGM":>8s}')
for label, fn, vj in VARIANTS:
    path = os.path.join(CONST, fn)
    c = km.Circuit.from_file(path)
    st = c.operation_statistics()
    Q = c.num_qubits
    static_ccx = int(st.num_toffoli_like); t = int(st.num_t_like); rot = int(st.num_z_pow(min_clifford_hierarchy_level=4))
    _, cond = cond_scan(c)
    mean_toff = float(static_ccx) if cond == 0 else float('nan')   # cond==0 => applied==static
    if vj and os.path.exists(os.path.join(CONST, vj)):
        d = json.load(open(os.path.join(CONST, vj)))
        eps = d['rotation_eps']; mean_toff = d['toffoli_count']    # authoritative full-domain applied
        C, score, ratio = official_cost(Q, mean_toff, d['t_count'], d['rotation_count'], eps)
        src = 'official-full'
    else:
        # no full-domain json -> use primary's eps as proxy (same n_rot=34, similar margin)
        eps = 1.743789533918183e-12
        C, score, ratio = official_cost(Q, mean_toff, t, rot, eps)
        src = 'static+proxy-eps'
    dgm = (ratio / CUR_RATIO) ** (1/3) - 1
    out.append(dict(variant=label, file=fn, Q=Q, mean_toffolis=round(mean_toff,2), T=t, n_rot=rot,
                    eps=eps, C=round(C,2), score=round(score,1), ratio=round(ratio,4),
                    dGM_pct=round(dgm*100,2), source=src, cond_toffoli=cond))
    print(f'{label:32s} {Q:>4d} {mean_toff:>7.0f} {t:>3d} {rot:>4d} {eps:>11.2e} {C:>9.2f} {score:>12.0f} {ratio:>8.4f} {dgm*100:>+7.1f}%')

os.makedirs(os.path.join(HERE, 'data'), exist_ok=True)
json.dump(out, open(os.path.join(HERE, 'data', 'pb_costs.json'), 'w'), indent=1)

# ---- 3. blocker arithmetic ----
print('\n=== BLOCKER ARITHMETIC (to flip P-B to GO) ===')
prim = out[0]
need_cost_match = REF_COST / CUR_RATIO          # cost that gives ratio == current 21.0768x
print(f'current SOTA cost (ratio 21.0768x) = {need_cost_match:.0f}')
for Q in (prim['Q'], 62):
    C_need = need_cost_match / Q
    print(f'  to MATCH current at Q={Q}: need C <= {C_need:.1f}  (P-B actual C={prim["C"]:.0f})')
# mean-toffoli requirement at Q=62
mt_need = (need_cost_match / 62) - (prim['n_rot']*(0.56*math.log2(1/prim['eps'])+5.3))/4 - prim['T']/4
print(f'  at Q=62 the mean-executed Toffolis alone must be <= ~{mt_need:.0f} (P-B actual = {prim["mean_toffolis"]:.0f})')
print(f'  Q reduction needed: {prim["Q"]} -> 62  ({(1-62/prim["Q"])*100:.0f}% lower)')
print(f'  C reduction needed: {prim["C"]:.0f} -> {need_cost_match/prim["Q"]:.0f} at Q={prim["Q"]}  ({(1-(need_cost_match/prim["Q"])/prim["C"])*100:.0f}% lower)')
