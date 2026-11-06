#!/usr/bin/env python3
"""Candidates that pair the cheapest public loaders (v23) with a public npz having identical words/U."""
import json, hashlib, sys
F = sys.argv[1]
c = json.load(open(F + '/candidates.json'))['chem']
pick = lambda p: next(k for k in c if k.startswith(p))
base = c[pick('34d19b96538d')]
out = {'chem': {}}
for tag, donor in (('somejoint_e2ba3d', 'b9c9b0776e5f'), ('kalidenaiarys_b46369', '25c66718b05a'), ('isabe_ce0631', 'b038420ded4c'), ('isabe_17f5a4', '89963c2a1b61')):
    d = c[pick(donor)]
    members = dict(base['members']); locs = dict(base['locs'])
    members['submission.npz'] = d['members']['submission.npz']; locs['submission.npz'] = d['locs']['submission.npz']
    ck = hashlib.sha256(json.dumps(sorted(members.items())).encode()).hexdigest()
    out['chem'][ck] = {'n_angle': base['n_angle'], 'members': members, 'locs': locs, 'sources': [f'MIX loaders=ahmedberatozer/vqcc-v23-portfolio npz={tag}'] + d['sources'][:1]}
json.dump(out, open(F + '/candidates_mix.json', 'w'), indent=1)
print(list(out['chem']))
