# VQCC Own-Circuit Portfolio – eigene Circuits auf einer öffentlichen Linie

> **Lernziel:** Wie man *eigene* Circuits baut, indem man eine öffentliche Linie nimmt und sie mit einer Kette kleiner, *bewiesener* Re-Writes verbessert – jedes einzelne exakt auf allen Inputs und allen Messergebnissen geprüft. Das ist das Gegenstück zu "nur kuratieren": hier entsteht echte Wertschöpfung, aber immer verifikationserst und mit dokumentierten Null-Ergebnissen.
> **Dauer:** ~15 Minuten
> **Quelle:** Syed Asad Ali (syed3000) | 46 votes
> **Fokus:** Portfolio assembly / Verification culture / Negative results / Credit chain

---

> **Hinweis:** Der Originaltext des Notebooks steht unten **auf Englisch, unverändert** ("as-is"). Deutsche Anmerkungen sind als 📌-Callouts dazwischen gesetzt.

Public portfolio (Apache-2.0). Fusion: the invsqrt lineage mrmeows → busyaprime → yoyobar, plus our deferred fan-in lookup, our own edit rounds an exact window resynthesis, a measurement clean-up and further proven rewrites (96,267.97). DQI: our decoder (C1 lineage) with ports of SomeJoint's narrow return and flag carry (Ali Haydar Özdağ's idea), plus our measurement-based clean-up and product caching (now also of products that are equal as Boolean functions), plus a one-qubit trade (Q 892). Chemistry: marculera's DF-THC pipeline and Özer's progressive rounding, plus our loader compiler, lattice-aware rounding and our own 8-group table (8 × 143 × 44), plus a weight refit (299,666,607; refitting the weights up to the error gate was first shown publicly by Heliosli). Verified with manwithacat's kickmix-engine. Thanks to everyone whose public work this builds on.

## Methods by task (all numbers measured with the kickmix-engine verifier)

**Local geometric mean 25.0657** (at 0 DQI failures on the draw) of reference/cost ratios (Kaggle's public score is shown on this notebook): invsqrt **21.57×**, DQI **~65.2×**, chemistry **11.20×**.

### 1. Fusion (inverse square root): 96,267.97 = 62 qubits × 1,552.71 Toffoli-eq

Base: the public invsqrt lineage (mrmeows → busyaprime → yoyobar): an 8-bit semi-log table, degree-2 Horner evaluation, and a two-pass phase with 41 rotations. Our changes:

- **Deferred fan-in lookup:** coefficient decoding with algebraic 3-product decodes (169 ANDs).
- **Measurement-based uncomputation** of adder carries: the pre-/post-low add and subtract, Q-row carries and the R_hi un-ripple are erased by X-measurement plus a conditional CZ instead of reverse ripples.
- **Carry-save merges** in the reverse decoders and R-rows, **ancilla-free top-of-ripple steps** (T gates count ¼ here), and pruning of the S1 helpers.
- **Exact window resynthesis:** an automated search over every small window of the compiled circuit (up to 12 wires, exact truth tables including phases) re-synthesises quadratic windows with the fewest products. It found 7 windows where 3 Toffolis become 2 (static Toffolis 1,492 → 1,485); each is proven exhaustively and with an independent simulator.
- **Measurement clean-up:** two X-basis measurements act on a qubit that is provably |0>, so their outcome bits carry no phase; every conditioned fix-up that reads them (two 3-T gadgets each) is removed, taking the mean T count from 20.5 to 14.5.
- **Decode re-synthesis:** one 5-product coefficient decode after the hi pass is re-synthesised with 4 products, proven on all 256 lookup addresses.
- **Two proven rewrites:** a phase gadget that fires on half the shots has a quadratic phase, so it is now applied with cheap two-qubit gates (−0.5 Toffoli-eq); and a 19-wire fix-up chain that acts on only 3 of the 3,133,452 inputs is replaced by a smaller equivalent block (−0.25). Both are proven exact on all inputs and all measurement outcomes.
- **More proven rewrites:** four products feeding one target form a rank-2 quadratic and become 2 Toffolis; two Toffoli pairs reuse a product computed a few gates later; the end-of-circuit clean-up of the shift register becomes a thermometer code erased top-down by measurement (one CCZ per step); and all 9 conditioned T-gate blocks are rebuilt in their measured branch with a freed wire, a CZ and one deferred CCZ (each −0.125 Toffoli-eq). Every rewrite is proven exact on all 3,133,452 inputs and all measurement outcomes, and the circuit passes the verifier on four salts.
- **Three more proven rewrites:** after the hi pass, a product already held on a measured wire is reused, so the control of one controlled swap is formed with two CNOTs instead of a Toffoli (−1 Toffoli on every shot); duplicate CZ pairs cancel; and dead gates in the conditioned copies and adjacent self-inverse pairs are removed. Every change is proven exact on all 3,133,452 inputs and all measurement outcomes, the whole circuit is rebuilt from our earlier version by one script, and it passes the verifier on four salts (97,747.22).
- **Shorter clean-up and shift networks:** the k = 9 and k = 10 clean-up cascades and the lo-pass flush are removed by holding the class bits in idle qubits; the normalise and unnormalise shift networks shrink from 52 to 47 and 52 to 48 controlled swaps; one post-hi cascade is removed by reusing a controlled swap that runs anyway; plus three further local rewrites. Mean Toffolis 1,281.48 → 1,268.75 (static 1,475 → 1,418). Every change is proven exact on all 3,133,452 inputs and all measurement outcomes, and the circuit passes the verifier on four salts (96,957.87).
- **Decode re-syntheses (new):** a 6-product decode of two coefficient wires and a backward re-encode of k (-2); the lo-side k decode from 8 to 7 products (-1); a ternary {0,4,8} delay line in the lo pass (-4); a cheaper unlookup end-game (-1.13); a joint backward decode re-plan (-1); and the lookup body re-solved with our new MinRank (low-rank alternating-form) solver, 137 to 135 products (-2). Mean Toffolis 1,268.75 → 1,257.62. Every change is proven exact on all 3,133,452 inputs and all measurement outcomes, and the circuit passes the verifier on four salts (96,267.97).

> **📌 Prozess-Hinweis (DE):** Lies die letzte Zahl in jeder Klammer: 97,747.22 → 96,957.87 → 96,267.97. Das ist eine *Reihenfolge bewiesener Mikro-Optimierungen*, jede mit ihrer eigenen Verifikation bei vier Salts. Kein einzelner Schritt ist groß – zusammen sind es ~1.8 %. Und jeder Schritt ist *bewiesen* (exakt auf allen 3,133,452 Inputs), nicht nur getestet. Das ist der Unterschied zwischen "es läuft" und "es ist korrekt".

### 2. DQI (Reed–Solomon decoding, GF(2¹²), 70 syndromes): 892 qubits, ~395.51k mean Toffolis

Base: our C1 decoder lineage (built with GPT-6 Astra on SomeJoint's kit): a retained-head chain, a block-Wronskian telescoped prefix jump, and SomeJoint's **narrow return** (single-pass reverse node). Our changes:

- **Flag carry** (ported from SomeJoint's 892-qubit line; idea by Ali Haydar Özdağ): pole flags are X-measured on the way forward, rebuilt on the way back (flag AND zero-test) and repaid with a CZ. Width 902 → 891.
- **Measurement-based erasure** of recompute steps and flag uncomputes, plus **conditionally clean AND ladders** (Khattar & Gidney, 2024).
- **Exact product caching:** repeated products are kept on wires proven idle and reused as CNOTs.
- **A one-qubit trade:** a 892nd qubit lets the converter and the reverse stages use wider exact variants (about 1,070 Toffolis saved for a qubit worth about 890 at this size). The last node's pole flag is now X-measured on the way forward like the others and recomputed at the start of the reverse (24 Toffolis), which frees a qubit through convert, unconvert and unsynthesis. Each scan position's test now runs only when its classical mask is nonzero (exact: the block is the identity otherwise). Extraction node 3 now runs as a retained chain without a pole flag (its pole fires only on shots of error weight 5 or less, a class already given up and priced). Mean Toffolis 396,921 → 395,394. A few rare chance events (for example an accidental zero in a 24-bit test) can still fail a shot; their rate is measured over 24 paired draws and priced.
- **Measurement peephole and functional caching:** a Toffoli whose target is X-measured before any other use is replaced by the measurement plus a conditional CZ (14 sites). Product caching now also groups products that are equal as Boolean functions (found by fingerprints of the affine-canonical product over random and DQI inputs with random, all-one and all-zero measurement outcomes), including products of negated operands with exact CNOT/CZ fix-ups; every chain is checked member by member on held-out inputs and the whole circuit is compared with the previous one on more than 300,000 shots (48 Toffolis saved).
- **Weight-17 shots exact (new):** the chain node-9 pole flag and the fold-18 zero flag are kept, so shots of error weight 17 no longer fail (+175 Toffolis): over 72 paired draws the failing shots fall from 27 to 21. The peephole and caching passes are re-applied on this base and checked exact against it on 48 held-out input sets.

### 3. Chemistry (DF-THC, FeMoCo): 299,666,607 = λ_eff 46.892646 × 14,966 Toffolis × 427 qubits

Base: marculera's DF-THC pipeline (compact groups) and Özer's progressive rounding idea. Our changes:

- **An 8 × 143 × 44 table** (8 groups, 1,220 addresses, one column fewer than v7) from our own continuous fit: float64 L-BFGS on an A100 (CUDA-graph captured) with a sign-mixing penalty, started from our 8 × 48 basin with columns merged down.
- **Lattice-aware rounding:** Babai-style nearest-plane rounding with lazy code commitment and a sign-mixing penalty, a conditional-curvature freezing order and three times the refit iterations per stage, then a refit that holds both error gates (error_1 and error_2) at 20 mHa with exact zero weights and column-gauge rotations (λ_eff 46.8937).
- **Our loader compiler:** engineered-overlap product selection with exact linear-matroid-parity choice, a cap-4 zero-recomputation schedule and coded bit 0 (bit 7 now carries the helpers instead of being borrowed). **4,152 Toffolis per pass**: a commuting reorder of the Givens tree plus the exact π-gauge of each address (bit 7) carries five low-address helper products from one batch to the next, so the coded batches cost 270–274 and the uncoded 291–297, from a hub-free grouping of the low address monomials with exact matroid-parity pair selection, don't-care absorption on unused addresses, a fifth low-cache slot freed inside the 128-qubit cap, and flexible compute/erase factorisations; the planner variants were found by an evolutionary search scored by the exact verifier.
- **Five-block coded plans:** the coded loaders are now planned with five blocks of three low address coordinates instead of four larger blocks. Because the carried helpers keep every low monomial live in one window, every pair of blocks is a valid product pair, so the pairing is perfect and each coded loader drops from 202 to 195 products (a slightly larger pairing budget plus a local search guided by the pairing deficit). Every new loader passes the algebra, truth-table and true-preload checks on all 1,220 addresses (forward, again and reverse), the official word recovery, the engine and the official verifier. No padding rows.
- **Weight refit at fixed words:** only the weights are refit to spend the remaining error budget (a longer run of our refit with tighter gate margins now reaches λ_eff 46.892646). Refitting the weights up to the gate was first shown publicly by Heliosli (v60).

### What did NOT work (measured, so you can skip it)

- **7-bit angles:** rounding noise grows ~1.72× per bit removed, and our rounding is already near the lattice optimum (an exact closest-vector search gains only 0.875× in squared noise at 8 bits).
- **Other loader address splits:** the best verified results were 6/5 = 418, 5/6 = 445 and 3/4/4 = 731 ANDs, all above the 4/7 incumbent (now 292).
- **The DQI key-equation / in-place Hankel route:** ~14× over budget.
- **DQI and invsqrt clean-slate architectures:** no design beat the incumbents on paper.

Built with AI agents (Claude Code, Claude Science, GPT-6 Astra, Gemini Argon) and verified with manwithacat's Rust kickmix-engine. Apache-2.0. Feedback and improvements are welcome. If you build on this, please keep the credit chain.

> **📌 Prozess-Hinweis (DE):** "What did NOT work" listet 4 gemessene Sackgassen (7-Bit-Winkel, andere Adressen-Splits, Key-Equation-Route, Clean-Slate-Architekturen). Und der letzte Satz – "If you build on this, please keep the credit chain" – ist die explizite Weitergabe der Kredit-Kette-Pflicht.

### Der Submission-Builder (das einzige Code-Zell)

```python
import os, zipfile, hashlib
base = None
for root, _, files in os.walk('/kaggle/input'):
    if 'dqi.kmb' in files and 'invsqrt.kmb' in files and 'dfthcsos__submission.npz' in files:
        base = root; break
assert base, 'dataset files not found'
out = '/kaggle/working/submission.zip'
with zipfile.ZipFile(out, 'w', zipfile.ZIP_STORED) as z:
    for f in sorted(os.listdir(base)):
        if f.endswith(('.kmb', '.npz')):
            z.write(os.path.join(base, f), f.replace('__', '/'))   # dfthcsos__submission.npz → dfthcsos/submission.npz
with zipfile.ZipFile(out) as z:
    names = z.namelist()
    for n in names:
        print(hashlib.sha256(z.read(n)).hexdigest(), n)            # jede Datei per SHA-256 nachweisbar
assert len(names) == 18 and 'dfthcsos/submission.npz' in names
print('OK', len(names), 'files')
```

> **📌 Prozess-Hinweis (DE):** Der Builder ist bewusst minimal: er nimmt die Dateien aus dem eigenen Dataset (die schon alle verifiziert sind), packt sie in ein ZIP mit fixem Layout und druckt den SHA-256 jeder Datei. Die eigentliche Arbeit – die Re-Writes, der Loader-Compiler, das Rounding – liegt *außerhalb* des Notebooks, in den Agenten-Läufen, die diese Dateien erzeugt haben. Das Notebook ist der *Nachweis*, nicht der Bau.

---

## 🧠 Prozess-Lektion

**Wie Syed Asad Ali arbeitet – eigene Circuits durch bewiesene Mikro-Optimierung:**

1. **Eine öffentliche Linie als Basis, dann echte Wertschöpfung.** Syed nimmt die invsqrt-Linie (mrmeows → busyaprime → yoyobar) und den C1-Decoder (auf SomeJoint's Kit), und baut darauf *eigene* Komponenten: ein Loader-Compiler, eine 8×143×44-Tabelle, lattice-aware Rounding, ein MinRank-Solver. Das ist der Unterschied zu reinem Kuratieren – hier entstehen neue Artefakte.

2. **Jeder Rewrite ist *bewiesen*, nicht nur getestet.** Die Formel "exakt auf allen 3,133,452 Inputs und allen Messergebnissen bewiesen" wiederholt sich in fast jedem Bullet. Das ist ein *Korrektheitsstandard*: ein Rewrite wird nur übernommen, wenn seine Äquivalenz erschöpfend (oder mit unabhängigen Simulatoren) belegt ist. *Lektion:* Bei reversiblen Circuits ist "läuft auf dem Default-Salt" nicht genug – es muss auf allen Inputs und allen Mess-Branches exakt sein.

3. **Mikro-Gewinne summieren sich, aber jeder wird einzeln verifiziert.** Die invsqrt-Kosten fallen in dokumentierten Stufen: 97,747.22 → 96,957.87 → 96,267.97. Jede Stufe ist ein eigener, vier-Salt-verifizierter Schritt. *Lektion:* Führe ein Kosten-Tagebuch pro Stufe; das macht Fortschritt sichtbar und regressionsfrei.

4. **Negative Results werden gleich mitgeliefert.** "Was NICHT funktionierte" listet 4 gemessene Sackgassen (7-Bit-Winkel, andere Adressen-Splits, Key-Equation-Route, Clean-Slate-Architekturen). *Lektion:* Wer eigene Circuits baut, dokumentiert auch, was er verworfen hat – sonst wiederholt die Community die Arbeit.

5. **AI-Agenten als Bauarbeiter, Verifier als Richter.** "Mit AI-Agenten gebaut (Claude Code, Claude Science, GPT-6 Astra, Gemini Argon) und mit manwithacats Rust kickmix-engine verifiziert." Die Agenten erzeugen Kandidaten; der offizielle Verifier entscheidet. *Lektion:* Trenne Erzeugung (Agent) von Bewertung (Verifier) strikt.

6. **Die Kredit-Kette wird explizit weitergegeben.** "Wenn du darauf aufbaust, bitte die Kredit-Kette beibehalten." Jede fremde Komponente (SomeJoint's Kit, Ali Haydar Özdağ's Flag-Carry-Idee, Khattar & Gidney's AND-Leitern, Heliosli's Refit-bis-zum-Gate) wird namentlich genannt. *Lektion:* Credit ist Teil des Werks, nicht Fußnote.

**Meta-Erkenntnis:** Syeds Notebook zeigt, dass "eigene Circuits" in dieser Competition *nicht* von Grund auf bedeutet. Es bedeutet: eine bewährte Linie nehmen, dann eine Kette kleiner, bewiesener, verifizierter Verbesserungen darauf legen – und dabei jede Null-Ergebnis-Kette und jede Kredit-Kette mitliefern.

## 📝 Lern-Notizen

- [ ] Öffentliche Linie als Basis identifizieren (invsqrt: mrmeows→busyaprime→yoyobar; DQI: C1 auf SomeJoint's Kit)
- [ ] Eigene Komponenten bauen: Loader-Compiler, Wort-Tabelle, Rounding, Solver
- [ ] Korrektheitsstandard: "exakt auf allen Inputs und allen Messergebnissen bewiesen" – erschöpfend oder mit unabhäng. Simulator
- [ ] Kosten-Tagebuch pro Stufe führen (jeder Rewrite = eigener verifizierter Schritt, 4 Salts)
- [ ] Messbasierte Uncomputation verstehen: X-Messung + konditioniertes CZ statt umgekehrter Ripple
- [ ] Exaktes Produkt-Caching: Produkte auf idle Wires halten, als CNOTs wiederverwenden; auch Boolesch-gleiche Produkte gruppieren
- [ ] Ein-Qubit-Trade rechnen: ~1,070 Toffolis gespart vs. ~890 Qubit-Kosten bei dieser Größe
- [ ] Lattice-aware Rounding: Babai-artig + Sign-Mixing-Strafe + beide Fehler-Gates bei 20 mHa halten
- [ ] "Was NICHT funktionierte"-Sektion schreiben (gemessen, mit Zahlen)
- [ ] AI-Agent (Erzeugung) vs. Verifier (Bewertung) strikt trennen; Kredit-Kette weitergeben
