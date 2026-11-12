import sys, random, itertools, importlib.util
from fractions import Fraction
from collections import Counter
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))  # neue Seite: das Paket kmx neben main.py
import types
import kmx, kmx.ops, kmx.verify.window
m = types.SimpleNamespace(META_OPS=kmx.ops.META_OPS, check_exact=kmx.check_exact, parse_lines=kmx.parse_lines,
                          _op_bits_written=kmx.verify.window.op_bits_written,
                          analyze_layout=kmx.analyze_layout, build_domains=kmx.build_domains, Options=kmx.Options,
                          parse_text=kmx.parse_text, Session=kmx.Session, Workbench=kmx.Workbench)  # alter privater Name -> öffentlich

NQ, NB = 3, 2
def ref_final(ops, q0, b0, top0):
    """distribution of final configs: Counter{(q,b,phase,stackdepth,top):prob}"""
    res = Counter()
    def run(i, q, b, stack, top, ph, p):
        while i < len(ops):
            o = ops[i]; n = o.name
            if n in m.META_OPS: i += 1; continue
            if n == "PUSH_CONDITION":
                stack = stack + (top,); top = top and b[o.cond]; i += 1; continue
            if n == "POP_CONDITION":
                if stack: top = stack[-1]; stack = stack[:-1]
                i += 1; continue
            act = top and (o.cond is None or b[o.cond])
            if not act: i += 1; continue
            qs = o.qs
            if n == "X": q = q[:qs[0]] + (1-q[qs[0]],) + q[qs[0]+1:]
            elif n == "CX":
                if q[qs[0]]: q = q[:qs[1]] + (1-q[qs[1]],) + q[qs[1]+1:]
            elif n == "CCX":
                if q[qs[0]] and q[qs[1]]: q = q[:qs[2]] + (1-q[qs[2]],) + q[qs[2]+1:]
            elif n == "SWAP":
                l = list(q); l[qs[0]], l[qs[1]] = l[qs[1]], l[qs[0]]; q = tuple(l)
            elif n == "CSWAP":
                if q[qs[0]]:
                    l = list(q); l[qs[1]], l[qs[2]] = l[qs[2]], l[qs[1]]; q = tuple(l)
            elif n == "Z":
                if q[qs[0]]: ph = (ph+1) % 2
            elif n == "CZ":
                if q[qs[0]] and q[qs[1]]: ph = (ph+1) % 2
            elif n == "CCZ":
                if all(q[x] for x in qs): ph = (ph+1) % 2
            elif n == "Z_POW":
                if q[qs[0]]: ph = (ph + Fraction(o.args[1])) % 2
            elif n == "NEG": ph = (ph+1) % 2
            elif n == "BIT_STORE0": b = b[:o.bit]+(0,)+b[o.bit+1:]
            elif n == "BIT_STORE1": b = b[:o.bit]+(1,)+b[o.bit+1:]
            elif n == "BIT_INVERT": b = b[:o.bit]+(1-b[o.bit],)+b[o.bit+1:]
            elif n == "HMR":
                for out in (0,1):
                    q2 = q[:qs[0]]+(0,)+q[qs[0]+1:]
                    b2 = b[:o.bit]+(out,)+b[o.bit+1:]
                    ph2 = (ph + (out & q[qs[0]])) % 2
                    run(i+1, q2, b2, stack, top, ph2, p/2)
                return
            elif n == "R":
                if q[qs[0]]:
                    for out in (0,1):
                        q2 = q[:qs[0]]+(0,)+q[qs[0]+1:]
                        run(i+1, q2, b, stack, top, (ph+out) % 2, p/2)
                    return
            else: raise Exception(n)
            i += 1
        res[(q, b, ph, len(stack), top)] += p
    run(0, q0, b0, (), top0, Fraction(0), Fraction(1))
    return res

def equiv(orig, cand, dead, depth):
    for q in itertools.product((0,1), repeat=NQ):
        for b in itertools.product((0,1), repeat=NB):
            for top in ((True,) if depth == 0 else (True, False)):
                ra, rb = ref_final(orig, q, b, top), ref_final(cand, q, b, top)
                def proj(r):
                    c = Counter()
                    for (qq, bb, ph, d, t), p in r.items():
                        bb = tuple(0 if i in dead else v for i, v in enumerate(bb))
                        c[(qq, bb, ph, d, t)] += p
                    return c
                if proj(ra) != proj(rb): return False
    return True

POOL = ["X q0","X q1","CX q0 q1","CX q1 q0","CX q0 q2","CCX q0 q1 q2","CCX q1 q2 q0","SWAP q0 q1","CSWAP q0 q1 q2",
        "Z q0","Z q1","CZ q0 q1","CCZ q0 q1 q2","Z_POW q0 0.5","Z_POW q0 -0.5","Z_POW q1 0.5","Z_POW q0 1.5","Z_POW q1 0.25","NEG",
        "HMR q0 b0","HMR q1 b0","HMR q0 b1","R q0","R q1","R q2",
        "BIT_STORE0 b0","BIT_STORE1 b0","BIT_INVERT b0","BIT_STORE0 b1","BIT_STORE1 b1","BIT_INVERT b1",
        "X q0 if b0","CX q0 q1 if b0","Z q0 if b0","CX q1 q2 if b1","Z_POW q0 0.5 if b0","BIT_STORE1 b1 if b0","BIT_INVERT b0 if b1",
        "CCX q0 q1 q2 if b0","HMR q2 b1 if b0","R q0 if b0","BIT_STORE0 b0 if b1"]
def rnd_window(r, maxlen):
    ops = []
    for _ in range(r.randrange(0, maxlen+1)):
        s = r.choice(POOL)
        if r.random() < 0.08:
            c = r.choice(["b0","b1"]); ops += [f"PUSH_CONDITION if {c}", s, "POP_CONDITION"]
        else: ops.append(s)
    return ops

def mutate(r, w):
    w = list(w)
    k = r.randrange(5)
    if k == 0 and w: del w[r.randrange(len(w))]
    elif k == 1: w.insert(r.randrange(len(w)+1), r.choice(POOL))
    elif k == 2 and len(w) > 1:
        i = r.randrange(len(w)-1); w[i], w[i+1] = w[i+1], w[i]
    elif k == 3 and w: w[r.randrange(len(w))] = r.choice(POOL)
    else:
        i = r.randrange(len(w)+1); s = r.choice(POOL); w[i:i] = [s, s]
    return w

def structure_ok(w):
    d = 0
    for l in w:
        d += l.startswith("PUSH") - l.startswith("POP")
        if d < 0: return False
    return d == 0

def main(seed, N):
    r = random.Random(seed); proved = refuted = na = 0; bad = []
    for it in range(N):
        a = rnd_window(r, 5)
        c = a
        for _ in range(r.randrange(1, 3)): c = mutate(r, c)
        if r.random() < .2: c = rnd_window(r, 4)
        if not (structure_ok(a) and structure_ok(c)): continue
        oa, oc = m.parse_lines(a), m.parse_lines(c)
        wr = m._op_bits_written(oa) | m._op_bits_written(oc)
        dead = {x for x in wr if r.random() < 0.3}
        depth = r.choice([0, 0, 1])
        st, msg = m.check_exact(oa, oc, depth, dead)
        if st == "proved":
            proved += 1
            if not equiv(oa, oc, dead, depth):
                bad.append((a, c, dead, depth)); print("UNSOUND", a, c, dead, depth, flush=True)
        elif st == "refuted":
            refuted += 1
        else: na += 1
    print(seed, "proved", proved, "refuted", refuted, "na", na, "unsound", len(bad))
if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
