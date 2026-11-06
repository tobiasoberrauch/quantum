"""Baut learn/01_kickmix_grundlagen.ipynb. Ausführen: .venv/bin/python learn/_build_01.py"""
import nbformat as nbf
from pathlib import Path

cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))

md(r"""
# 01 · kickmix-Grundlagen zum Anfassen

Dieses Notebook baut **alle Bausteine** nach, aus denen die drei Wettbewerbs-Schaltkreise bestehen — klein genug, um jedes Gatter zu sehen:

| Abschnitt | Baustein | Wo er im Wettbewerb steckt |
|---|---|---|
| 1 | Toffoli = reversibles AND | überall (das teure Gatter) |
| 2 | Uncomputation: rückwärts vs. **HMR + CZ** | invsqrt-Uncompute, DQI `un*`-Blöcke, Chemie `del_and` |
| 3 | Reversibler Addierer | Newton-Schritt (invsqrt), Arithmetik |
| 4 | QROM-Lookup-Tabelle | invsqrt-Seed, Chemie-Angle-Loader |
| 5 | **Phase Kickback** mit `Z_POW` | invsqrt-Ausgabe, Givens-Winkel |
| 6 | Kosten zählen & Pebbling | die Score-Formeln |

**Konvention, die man sich merken muss:** `read_shot_phase` liefert die Phase in **Halbdrehungen** (1 = π = Vorzeichen −1). `Z_POW t` bedeutet Phase `e^{iπ t}` auf `|1⟩`.
""")

code(r"""
import kickmix as km
import numpy as np
from fractions import Fraction

def run(circuit, inputs: dict, shots: int, seed=0):
    # Simuliert `shots` Läufe; inputs = {registername: liste von Werten pro Shot}
    sim = km.Simulator(batch_size=shots, seed=seed, debug_print=False)
    sim.use_same_registers_as(circuit)
    for name, vals in inputs.items():
        for s, v in enumerate(vals):
            sim.write_within_shot(name, s, int(v))
    sim.do(circuit)
    return sim

def kosten(circuit):
    st = circuit.operation_statistics()
    return {"Qubits": circuit.num_qubits, "Toffolis": st.num_toffoli_like,
            "Z_POW": st.num_z_pow(), **{k: v for k, v in st.items() if k != "INFO_TAG"}}
""")

md(r"""
## 1 · Der Toffoli: ein umkehrbares AND

`CCX(a, b, t)` macht `t ⊕= a·b`. Mit `t = 0` steht danach `a AND b` in `t` — und anders als ein normales AND **verliert es keine Information** (a und b bleiben erhalten). Wir testen alle 8 Eingaben gleichzeitig: ein *Shot* pro Eingabe.
""")

code(r"""
b = km.CircuitBuilder()
r = b.create_quantum_register(3, "r")      # r[0]=a, r[1]=b, r[2]=t  (little-endian)
b.ccx(r[0], r[1], r[2])
toffoli = b.finish_circuit()
print(toffoli)

sim = run(toffoli, {"r": range(8)}, shots=8)
print(" a b t  →  a b t")
for s in range(8):
    vor = [(s >> i) & 1 for i in range(3)]
    nach = [int(v) for v in sim.read_within_shot("r", s)]
    print(" ", *vor, " → ", *nach)
""")

md(r"""
**Beobachtung:** Nur wenn `a = b = 1`, kippt `t`. Zweimal angewendet ist der Toffoli die Identität — das ist *Umkehrbarkeit*.

> In fehlerkorrigierter Hardware kostet jeder Toffoli einen „Magic State“ aus einer Fabrik — **das ist die Währung des Wettbewerbs**. X, CNOT, CZ sind dagegen fast gratis.
""")

md(r"""
## 2 · Das Müll-Problem und der HMR-Trick

Ein Hilfsqubit `t = a AND b` muss am Ende wieder `|0⟩` sein, sonst bleibt es mit `a, b` verschränkt und zerstört die Interferenz des Gesamtalgorithmus. Drei Varianten:

1. **rückwärts** — noch ein Toffoli: `t ⊕= a·b` → 0. Kosten: 2 Toffolis.
2. **HMR + CZ** (`del_and`) — `t` in der X-Basis messen und zurücksetzen. Das Messergebnis `m` ist zufällig; bei `m = 1` entsteht ein Phasenfehler `(−1)^{a·b}`, den ein **klassisch gesteuertes CZ(a, b)** repariert. Kosten: **1 Toffoli**.
3. **nackt** — nur HMR, ohne Korrektur. Billig, aber **falsch**.

Wir testen jede Variante auf 256 Shots (alle 4 Eingaben × zufällige Messergebnisse) und zählen Shots mit falscher Phase.
""")

code(r"""
def and_mit_uncompute(variante):
    b = km.CircuitBuilder()
    a = b.create_quantum_register(1, "a")
    c = b.create_quantum_register(1, "b")
    t = b.alloc_qubits(1)[0]
    b.init_and(a[0], c[0], t)                 # t := a AND b   (1 Toffoli)
    if variante == "rückwärts":
        b.ccx(a[0], c[0], t)                  # noch ein Toffoli
    elif variante == "HMR + CZ":
        b.del_and(a[0], c[0], t)              # HMR, dann CZ(a,b) falls Messung = 1
    elif variante == "nackt":
        b.hmr(t, b.alloc_bits(1)[0])          # Messen ohne Korrektur
    return b.finish_circuit()

shots = 256
eingabe_a = [s & 1 for s in range(shots)]
eingabe_b = [(s >> 1) & 1 for s in range(shots)]
for v in ["rückwärts", "HMR + CZ", "nackt"]:
    c = and_mit_uncompute(v)
    sim = run(c, {"a": eingabe_a, "b": eingabe_b}, shots, seed=1)
    falsch = sum(sim.read_shot_phase(s) != 0 for s in range(shots))
    print(f"{v:10s}  Toffolis={c.operation_statistics().num_toffoli_like}  Shots mit Phasenfehler: {falsch}/{shots}")

print("\nSo sieht die HMR+CZ-Variante aus:")
print(and_mit_uncompute("HMR + CZ"))
""")

md(r"""
**Ergebnis:** HMR + CZ ist genauso korrekt wie Rückwärtsrechnen, **spart aber die Hälfte der Toffolis**. Die nackte Variante liegt in ~1/8 der Shots daneben (a·b = 1 in 1/4 der Fälle × Messung = 1 in 1/2) — genau solche Fehler findet der Fuzz-Verifier des Wettbewerbs.

> **Im Wettbewerb:** Bei DQI kosten die `un*`-Blöcke (unextract, unconvert …) 1,6–1,8× ihre Vorwärts-Blöcke — dort wird teils noch *rückwärts gerechnet*, weil HMR nur geht, wenn sich der Phasenfehler billig reparieren lässt.
""")

md(r"""
## 3 · Ein reversibler Addierer

`target += offset` für 4-Bit-Zahlen, modulo 16. kickmix verwendet einen Addierer, der für `n` Bits nur **n − 1 Toffolis** braucht (Überträge per AND berechnen, per HMR wieder löschen). Wir prüfen **alle 256** Eingabepaare.
""")

code(r"""
b = km.CircuitBuilder()
A = b.create_quantum_register(4, "a")
T = b.create_quantum_register(4, "t")
b.iadd(A, target=T)
adder = b.finish_circuit()
print(kosten(adder))

paare = [(x, y) for x in range(16) for y in range(16)]
sim = run(adder, {"a": [p[0] for p in paare], "t": [p[1] for p in paare]}, shots=256, seed=3)
ok = all(
    sim.read_within_shot("t", s, out=int) == (x + y) % 16
    and sim.read_within_shot("a", s, out=int) == x
    and sim.read_shot_phase(s) == 0
    for s, (x, y) in enumerate(paare)
)
print("alle 256 Summen korrekt, a erhalten, Phase sauber:", ok)
print(adder.text_diagram())
""")

md(r"""
Im Diagramm sieht man oben die **Überträge** (CCX auf frische `|0>`-Qubits q8, q9) und unten ihr Löschen per `HMR` + bedingtem `Z**b` — exakt der Trick aus Abschnitt 2.

> **Im Wettbewerb:** Der Newton-Schritt von invsqrt (`y₁ = ½·y₀·(3 − x·y₀²)`) besteht aus Multiplikationen = vielen Additionen. Jedes eingesparte Bit Breite spart Toffolis *und* Qubits.
""")

md(r"""
## 4 · QROM: eine Lookup-Tabelle im Quantencomputer

`init_lookup` lädt `table[address]` in ein Zielregister — für *alle Adressen in Überlagerung gleichzeitig*. Kosten wachsen mit der **Tabellengröße**, nicht mit der Datenbreite:
""")

code(r"""
def lookup_kosten(adressbits: int, loeschen: bool) -> int:
    b = km.CircuitBuilder()
    x = b.create_quantum_register(adressbits, "x")
    y = b.alloc_qubits(8)
    tabelle = [(37 * i + 11) % 256 for i in range(2 ** adressbits)]
    b.init_lookup(table=tabelle, address=x, target=y)
    if loeschen:
        b.del_lookup(table=tabelle, address=x, target=y)
    return b.finish_circuit().operation_statistics().num_toffoli_like

for adressbits in [2, 4, 6, 8]:   # ponytail: del_lookup wirft bei >8 Adressbits mit 8 Zielbits (kickmix-Eigenheit)
    laden = lookup_kosten(adressbits, False)
    weg = lookup_kosten(adressbits, True) - laden
    print(f"{2**adressbits:5d} Einträge: laden {laden:5d} Toffolis, löschen nur +{weg:4d}  (√N ≈ {2**(adressbits/2):.0f})")
""")

md(r"""
**Faustregel:** Laden kostet ≈ N − 2 Toffolis (N = Anzahl Einträge), **Löschen nur ≈ √N** — die Ziel-Bits werden per HMR gemessen, und nur die Phasenkorrektur braucht noch eine kleine Lookup-Rechnung. Darum ist bei invsqrt der *Seed* eine kleine Tabelle (≈ 2⁷–2⁹ Einträge), und darum kostet bei der Chemie jede zusätzliche Winkel-Tabelle direkt Toffolis — und jedes Bit Datenbreite Qubits (Grenze: 128 pro Angle-Loader).
""")

md(r"""
## 5 · Phase Kickback: Ergebnisse als Phase ausgeben

Ziel (wie bei invsqrt): `|x⟩ → e^{2πi · f(x)/8} |x⟩` für eine 3-Bit-Funktion `f`.

Rezept:
1. `y = f(x)` per Lookup berechnen,
2. auf Bit `k` von `y` ein `Z_POW` mit Gewicht `2^k / 8` **Drehungen** = `2^{k+1}/8` **Halbdrehungen**,
3. `y` wieder löschen → nur die Phase bleibt übrig.
""")

code(r"""
f = [(5 * a + 3) % 8 for a in range(8)]     # irgendeine Funktion 3 Bit → 3 Bit

b = km.CircuitBuilder()
x = b.create_quantum_register(3, "x")
y = b.alloc_qubits(3)
b.init_lookup(table=f, address=x, target=y)
for k in range(3):
    b.z_pow(y[k], Fraction(2 * 2**k, 8))    # Halbdrehungen!
b.del_lookup(table=f, address=x, target=y)
kick = b.finish_circuit()

sim = run(kick, {"x": range(8)}, shots=8, seed=4)
print(" x  f(x)  Soll-Phase (Halbdreh.)  Ist-Phase   y wieder 0?")
for s in range(8):
    soll = Fraction(2 * f[s], 8) % 2
    ist = sim.read_shot_phase(s)
    print(f" {s}   {f[s]}        {str(soll):6s}            {str(ist):6s}     {sim.read_within_shot(y, s, out=int) == 0}")

st = kick.operation_statistics()
print("\nZ_POW nach Clifford-Hierarchie-Stufe:", st.z_pow_clifford_hierarchy_counts)
""")

md(r"""
**Die Hierarchie-Stufen sind der Kern des invsqrt-Hebels:**

| Stufe | Winkel (Halbdrehungen) | Gatter | Kosten |
|---|---|---|---|
| 1 | 1 | Z | gratis (Clifford) |
| 2 | 1/2 | S | gratis (Clifford) |
| 3 | 1/4 | T | 1 T = ¼ Toffoli |
| ≥ 4 | 1/8, 1/16, … | „feine“ Rotation | ≈ 0,56·log₂(1/ε) + 5,3 T-Gatter — **teuer**, und umso teurer, je genauer |

Ein 40-Bit-Ergebnis wie bei invsqrt braucht also für die feinen Bits viele teure Rotationen (`n_rot`). Je mehr Rotationen, desto kleiner das Fehlerbudget pro Rotation und desto teurer jede einzelne — darum versucht Subagent D, die Phase *ohne* feine Rotationen auszugeben.
""")

md(r"""
## 6 · Kosten zählen wie der Wettbewerb — und Pebbling

Die Score-Formeln multiplizieren **Qubits × Toffolis**. Wer Hilfsqubits nach Gebrauch freigibt (`free`), kann sie wiederverwenden — das heißt *Pebbling* und senkt `Q` ohne mehr Toffolis. Vergleich: vier AND-Berechnungen nacheinander, einmal mit frischen Qubits, einmal mit Wiederverwendung.
""")

code(r"""
def vier_ands(wiederverwenden: bool):
    b = km.CircuitBuilder()
    x = b.create_quantum_register(8, "x")
    for i in range(4):
        t = b.alloc_qubits(1)[0]
        b.init_and(x[2 * i], x[2 * i + 1], t)
        b.z_pow(t, 1)                          # Phase (-1)^(x_2i · x_2i+1) "benutzen"
        b.del_and(x[2 * i], x[2 * i + 1], t)
        if wiederverwenden:
            b.free(t)
    return b.finish_circuit()

for wv in [False, True]:
    c = vier_ands(wv)
    Q, T = c.num_qubits, c.operation_statistics().num_toffoli_like
    print(f"wiederverwenden={wv!s:5s}: Q={Q:2d}  T={T}  Q×T={Q*T}")
""")

md(r"""
Gleiche Toffolis, weniger Qubits → besserer Score. Der 62-Qubit-invsqrt-Spitzenschaltkreis (vs. 260 in der Referenz) lebt genau davon: Zwischenergebnisse so früh wie möglich löschen und Qubits sofort wiederverwenden. Bei DQI ist das ausgereizt (892 = beweisbare Untergrenze, siehe unsere Liveness-Analyse).

### Die drei Score-Formeln in einem Satz
- **invsqrt:** `Q × (Toffolis + T/4 + Rotationskosten)`
- **DQI:** `R(ε₊) × Q² × T` — Breite zählt doppelt, Fehlerrate über `R`
- **Chemie:** `λ_eff × T × Q` — zusätzlich die Normierung aus der klassischen Faktorisierung
""")

md(r"""
## Übungen

1. **Abschnitt 2:** Ersetze `del_and` durch HMR + CZ *von Hand* (`b.hmr`, dann `b.push_condition(m)`, `b.cz(...)`, `b.pop_condition()`). Prüfe 0 Phasenfehler.
2. **Abschnitt 3:** Baue einen *gesteuerten* Addierer (`iadd(..., control=q)`) und vergleiche die Toffoli-Zahl. Warum steigt sie?
3. **Abschnitt 3:** Probiere `iadd(5, target=T, btol=1)` (klassische Konstante, absichtlich ungenau). Wie viele der 16 Eingaben sind falsch? → So funktionieren „smarte Approximationen“ (DQI-ε₊-Budget!).
4. **Abschnitt 5:** Mache `f` 6-bittig und zähle, wie viele Rotationen Stufe ≥ 4 haben. Was passiert, wenn du die 2 feinsten Bits einfach weglässt — wie groß wird der maximale Phasenfehler?
5. **Abschnitt 6:** Setze `b.set_max_qubits(9)` vor die Schleife — welche Variante bricht ab?
""")

nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"name": "quantum", "display_name": "Python (quantum .venv)"}})
out = Path(__file__).with_name("01_kickmix_grundlagen.ipynb")
nbf.write(nb, out)
print(out)
