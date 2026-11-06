import collections, sys
def triples_of(fn):
    terms = [(int(p), int(a, 16), int(b, 16), int(s, 16)) for p, a, b, s in (l.split() for l in open(fn))]
    bs = sorted({t[2] for t in terms})
    S = set(bs)
    tri = set()
    for x in bs:
        for y in bs:
            if x < y and (x ^ y) in S:
                tri.add(tuple(sorted((x, y, x ^ y))))
    # greedily merge lines into Fano planes (7 elements)
    planes = []
    used = set()
    for x in bs:
        for y in bs:
            for z in bs:
                if x < y < z:
                    cl = {x, y, z, x ^ y, x ^ z, y ^ z, x ^ y ^ z}
                    if len(cl) == 7 and cl <= S and not (cl & used):
                        planes.append(sorted(cl))
                        used |= cl
    cnt = collections.Counter(t[2] for t in terms)
    return bs, planes, [sum(cnt[b] for b in pl) for pl in planes], len(S - used)
if __name__ == '__main__':
    for fn in sys.argv[1:]:
        bs, planes, tot, rest = triples_of(fn)
        print(fn, 'unique', len(bs), 'planes', len(planes), 'terms per plane', tot, 'leftover', rest)
        for pl in planes:
            print('  ', [format(x, '015b') for x in pl[:3]])
