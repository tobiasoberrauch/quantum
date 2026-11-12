"""Fuzz-Differenztest: Zufallsschaltkreise durch die Abschnitt-5-Pässe von Referenz (v5/main.py) und Paket kmx."""
import importlib.util, random, sys
from collections import Counter

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m; spec.loader.exec_module(m); return m

ref = load("/tmp/kmx_merge/v5/main.py", "ref_main")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))  # neue Seite: das Paket kmx neben main.py
import kmx as new  # noqa: E402  (alle benutzten Namen exportiert kmx)
W, S = 5, 7

def gen(seed, n_ops):
    r = random.Random(seed)
    lines = [f"APPEND_TO_REGISTER q{i} r0" for i in range(W)]
    qs = list(range(W + S)); scratch = list(range(W, W + S)); bits = []; depth = 0
    def cond():
        return f" if b{r.choice(bits)}" if bits and r.random() < 0.12 else ""
    for _ in range(n_ops):
        x = r.random()
        if x < 0.40:
            a, b = r.sample(qs, 2); t = r.choice([q for q in scratch if q not in (a, b)] )
            if r.random() < 0.5 and lines[-1].startswith("CCX"):      # Gruppen: gleiches Ziel wie zuvor
                t = int(lines[-1].split()[3][1:])
                if t in (a, b): continue
            lines.append(f"CCX q{a} q{b} q{t}{cond()}")
        elif x < 0.58:
            a = r.choice(qs); t = r.choice([q for q in scratch if q != a]); lines.append(f"CX q{a} q{t}{cond()}")
        elif x < 0.62: lines.append(f"X q{r.choice(scratch)}{cond()}")
        elif x < 0.67: a, b, c = r.sample(qs, 3); lines.append(f"CCZ q{a} q{b} q{c}{cond()}")
        elif x < 0.71: a, b = r.sample(qs, 2); lines.append(f"CZ q{a} q{b}{cond()}")
        elif x < 0.75: a = r.choice(qs); b, c = r.sample([q for q in scratch if q != a], 2); lines.append(f"CSWAP q{a} q{b} q{c}{cond()}")
        elif x < 0.78: b, c = r.sample(scratch, 2); lines.append(f"SWAP q{b} q{c}{cond()}")
        elif x < 0.84: lines.append(f"Z_POW q{r.choice(qs)} {r.choice(['0.25', '0.125', '-0.75', '0.0009765625', '0.5'])}{cond()}")
        elif x < 0.87: lines.append(f"Z q{r.choice(qs)}{cond()}")
        elif x < 0.92:
            b = r.randrange(6); bits.append(b); lines.append(f"HMR q{r.choice(scratch)} b{b}")
        elif x < 0.95: lines.append(f"R q{r.choice(scratch)}")
        elif x < 0.975 and bits: lines.append(f"PUSH_CONDITION if b{r.choice(bits)}"); depth += 1
        elif depth: lines.append("POP_CONDITION"); depth -= 1
    lines += ["POP_CONDITION"] * depth
    return "\n".join(lines) + "\n"

def run(m, text, seed):
    r = random.Random(seed)
    ops = m.parse_text(text)
    layout = m.analyze_layout(ops, value_range=f"0:{(1 << W) - 1}")
    dom = m.exhaustive_domain(layout) if seed % 2 else m.sample_domain(layout, 24, 2)
    smp = m.sample_domain(layout, r.choice([4, 8, 16, 32]), 1)
    kw = dict(max_terms=r.choice([2, 3, 8]), max_group=r.choice([2, 3, 6]), drop_idle_hmr=r.random() < 0.7)
    trace, keys = [], Counter()
    for rnd in range(2):
        a, n1 = m.pass_fold(ops); a, n2, n3 = m.pass_cancel(a, r.choice([2, 200])); trace.append((n1, n2, n3)); ops = a
        a, st = m.pass_sim_reduce(ops, layout, dom, smp, True, 600.0, **kw)
        trace.append((list(st.items()), [type(v).__name__ for v in st.values()], [o.fmt() for o in a], a is ops)); keys.update(st.keys()); ops = a
        a, st = m.pass_sim_reduce(ops, layout, dom, smp, False); trace.append((list(st.items()), [o.fmt() for o in a])); ops = a
        a, st = m.pass_mbu(ops, layout, dom); trace.append((list(st.items()), [type(v).__name__ for v in st.values()], [o.fmt() for o in a])); keys.update("mbu_" + k for k in st); ops = a
        tt = m.trace_touches(ops, layout, dom); lt = m.lifetimes_of(ops, tt); trace.append((list(tt.items()), lt[0], sorted(lt[1])))
        keys["drop"] += bool(lt[1])
        a, st = m.pass_repack(ops, layout, dom); trace.append((list(st.items()), [o.fmt() for o in a])); keys["repacked"] += st["q_after"] < st["q_before"]; ops = a
    return trace, keys

bad, cover = 0, Counter()
n = int(sys.argv[1])
for seed in range(n):
    text = gen(seed, random.Random(seed).choice([30, 80, 200, 500]))
    try:
        a, ka = run(ref, text, seed)
    except Exception as e:      # Referenz selbst scheitert: gleiches Verhalten verlangt
        ea = repr(e)
        try: run(new, text, seed); eb = None
        except Exception as e2: eb = repr(e2)
        cover["ref_exception"] += 1
        if ea != eb: bad += 1; print("EXC DIFF", seed, ea, eb)
        continue
    b, _ = run(new, text, seed)
    cover.update(ka)
    if a != b:
        bad += 1; print("DIFF seed", seed)
print("coverage", dict(cover)); print("FUZZ SAME" if not bad else f"FUZZ MISMATCH {bad}")
