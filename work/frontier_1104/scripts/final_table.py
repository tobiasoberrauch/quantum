#!/usr/bin/env python3
import csv, glob, json, re, sys
F = sys.argv[1]; B = sys.argv[2]
man = {r['sha256']: r for r in csv.DictReader(open(B + '/downloads/_meta_hub5/manifest.csv'))}
dl = {}
for lg in ('dl1.log', 'dl3.log', 'dl5.log', 'dl5b.log'):
    for line in open(f'{F}/logs/{lg}'):
        m = re.match(r'(?:dataset )?(\S+/\S+) rc=\d+ .*License\(s\): (\S+)', line)
        if m:
            dl[('d5__' if lg.startswith('dl5') else 'd__') + m.group(1).replace('/', '__')] = m.group(2)
dl['d__qwertykeypadapple__qcc-kernel-search-portfolio'] = 'other, ships Apache-2.0 LICENSE'
dl['d__manwithacat__vqcc-hedge-wizardry'] = dl['d5__manwithacat__vqcc-hedge-wizardry'] = 'apache-2.0'
dl['d__isabe11am00re__qcc-v67s33w-circuits'] = 'apache-2.0'
def url(s):
    if s.startswith('MIX'): return ''
    kind, a, b = s.split('__', 2)
    return f"https://www.kaggle.com/{'code' if kind.startswith('k') else 'datasets'}/{a}/{b}"
cand = json.load(open(F + '/candidates.json')); mix = json.load(open(F + '/candidates_mix.json'))
rows = []
for p in glob.glob(F + '/results/*.json'):
    r = json.load(open(p)); c = r['component']; k = r['key']
    v = cand[c].get(k) or mix['chem'].get(k)
    src = v['sources'] if v else r['sources']
    s0 = next((x for x in src if not x.startswith('MIX')), src[0])
    lic = next((dl[x] for x in src if x in dl), None) or man.get(k, {}).get('licence') or 'not recorded (not adopted)'
    if v:
        loc = v['locs'][0] if c != 'chem' else v['locs']['submission.npz']
        path = loc['path'].split('/downloads/')[-1] + (('!' + loc['inner']) if loc['inner'] else '')
    else:
        path = '(raw copy deleted after verification) ' + s0
    det = {'invsqrt': f"Q={r.get('num_qubits')} Teq={round(r.get('toffoli_equivalent') or 0, 3)}",
           'dqi': f"Q={r.get('num_qubits')} T={round(r.get('toffoli_count') or 0, 2)} maxT={r.get('max_toffoli_count')} R={round(r.get('repetition_factor') or 0, 5)} ve={r.get('value_errors')} pe={r.get('phase_errors')}",
           'chem': f"Q={r.get('num_qubits')} T={r.get('toffoli_count')} lambda={round(r.get('lambda_eff') or 0, 6)}"}[c]
    if src[0].startswith('MIX'): det += ' ' + src[0]
    rows.append({'component': 'dfthcsos' if c == 'chem' else c, 'sha256': k, 'path': path, 'source_url': url(s0), 'author': s0.split('__')[1] if not s0.startswith('MIX') else 'mix', 'licence': lic, 'status': r.get('status'), 'ratio': r.get('ratio') or 0.0, 'detail': det})
rows.sort(key=lambda x: (x['component'], -x['ratio']))
json.dump(rows, open(F + '/candidates_ranked.json', 'w'), indent=1)
print(len(rows), sum(1 for r in rows if r['status'] == 'PASS'))
for r in rows:
    print(json.dumps(r, ensure_ascii=False, separators=(',', ':')))
