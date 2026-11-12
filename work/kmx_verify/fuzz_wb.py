import sys, random, itertools
exec(open(str(__import__("pathlib").Path(__file__).resolve().parent / "fuzz_exact.py")).read().replace('if __name__ == "__main__":','if False:').replace("NQ, NB = 3, 2","NQ, NB = 5, 3"))
HEAD = "".join(f"APPEND_TO_REGISTER q{i} r0\n" for i in range(3)) + 'REGISTER r0 "x"\nAPPEND_TO_REGISTER b0 r1\nREGISTER r1 "o"\n'
POOL2 = POOL + ["CX q2 q3","CCX q0 q3 q4","CCX q3 q4 q1","CX q3 q4","HMR q3 b2","HMR q4 b0","R q3","R q4","X q3","CZ q3 q4",
                "BIT_STORE0 b2","BIT_INVERT b2","CX q4 q3 if b2","Z q3 if b2","CCZ q1 q3 q4","SWAP q3 q4","CSWAP q4 q0 q3"]
POOL[:] = POOL2
def final_obs(ops):
    out = Counter()
    for x in range(8):
        q = tuple((x>>i)&1 for i in range(3)) + (0,0)
        r = ref_final(ops, q, (0,0,0), True)
        for (qq, bb, ph, d, t), p in r.items():
            out[(x, qq, bb[0], ph, d, t)] += p
    return out
def build(r, n):
    body = []
    while len(body) < n:
        s = r.choice(POOL)
        if r.random() < .1: body += [f"PUSH_CONDITION if {r.choice(['b0','b1','b2'])}", s, "POP_CONDITION"]
        else: body.append(s)
    return body
def main(seed, N, exact_only):
    r = random.Random(seed); acc = bad = 0; paths = Counter()
    for it in range(N):
        body = build(r, r.randrange(4, 12))
        ops = m.parse_text(HEAD + "\n".join(body) + "\n")
        layout = m.analyze_layout(ops, "x", "0:7")
        dom, sample_dom = m.build_domains(layout, 1<<20, 64, 64)
        s = m.Session(list(ops), layout, dom, sample_dom, m.Options(final_rounds=4), log=lambda *_: None)
        s.run_baseline()
        wb = m.Workbench(s, exact_only=exact_only)
        body_start = len(ops) - len(body)
        a = r.randrange(len(body)); b = min(len(body)-1, a + r.randrange(0, 4))
        win = [o.fmt() for o in ops[body_start+a: body_start+b+1]]
        if not structure_ok(win): continue
        cand = win
        for _ in range(r.randrange(1,3)): cand = mutate(r, cand)
        if not structure_ok(cand): continue
        before = list(s.ops)
        res = wb.propose_rewrite(body_start+a, body_start+b, cand, "", neutral_ok=True)
        if res.get("accepted"):
            acc += 1; paths[res["message"][:12]] += 1
            if final_obs(before) != final_obs(s.ops):
                bad += 1
                print("UNSOUND", exact_only, [o.fmt() for o in before][len(ops)-len(body):], (a,b), cand, res["message"], flush=True)
    print(seed, "accepted", acc, "unsound", bad, dict(paths))
main(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]=="1")
