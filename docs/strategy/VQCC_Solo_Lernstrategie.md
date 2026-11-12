# VQCC Solo-Lernstrategie

**Ziel:** Von den Besten lernen – nicht gegen sie gewinnen. Die Competition als strukturiertes Lernprogramm für Quantum Circuit Compilation nutzen.

---

## Was die Besten eigentlich können (und wie man es lernt)

Die Top-Teams haben keinen Geheimcode. Sie haben einen **Prozess**:

```
Scan → Verifizieren → Vergleichen → Dokumentieren → Iterieren
```

Das ist lernbar. In 9 Wochen kannst du diesen Prozess internalisieren.

---

## Die drei Tasks als Lernpfad

### Stufe 1: invsqrt (einfachste Task, dein stärkster Bereich)

**Was du schon hast:** pwq3 Seed-Modell (0.5577 vs 0.617 published). Das ist besser als alles public.

**Was die Besten wissen, das du noch nicht hast:**
- QROM-Design: Wie man Lookup-Tabellen in minimale Toffolis übersetzt
- Gauge-Optimisation: Pi-Gauge vs. andere Gauges – wann lohnt sich was?
- Uncompute vs. Reset: Der fundamentale Trade-off (R-Frage!)
- Carry-Ketten: Wie man Addition/Subtraktion in minimalen Gates baut

**Lernübung:**
1. Nimm yoyobar's 62-Qubit-Circuit (public, LB 22.99)
2. Zerlege ihn Block für Block: Welche Gates tun was?
3. Baue jeden Block selbst nach (in kickmix)
4. Optimiere EINEN Block – z.B. den QROM – und messe den Delta
5. Dokumentiere: Was funktioniert, was nicht, warum

**Erwartetes Ergebnis nach 2 Wochen:** Du verstehst invsqrt auf Gate-Ebene. Kannst eigene Tweaks machen. Weißt warum 62 Qubits der Floor ist (oder nicht).

---

### Stufe 2: DQI (mittlere Komplexität, größter Kostenblock)

**Was die Besten wissen:**
- Reed-Solomon-Decoding über GF(2¹²): Die Mathematik dahinter
- Product Caching (R41): Wie man wiederholte Produkte auf eine Wire schreibt
- Readout-Optimierung: CX statt Controlled Swap
- Failure Penalty: Warum ein einziger fehlgeschlagener Shot in 102,400 so teuer ist
- 891 vs. 892 Qubits: Der Qubit-Floor und warum weniger nicht immer besser ist

**Lernübung:**
1. Nimm busyaprime's Top-30 Re-Verified Notebook
2. Lies die DQI-Sektion: Wie der Verifier arbeitet, was k=0 vs. k=1 bedeutet
3. Baue den einfachsten möglichen DQI-Decoder (auch wenn er schlecht ist)
4. Führe Product Caching ein (R41) und messe den Delta
5. Experimentiere mit R-Reset: Was passiert wenn ich Uncompute durch R ersetze?

**Erwartetes Ergebnis nach 3 Wochen:** Du verstehst den Decoder auf Algorithmus-Ebene. Kannst die R-Reset-Frage selbst beantworten (experimentell). Weißt wo die Toffolis hingehen.

---

### Stufe 3: DF-THC-SOS / Chemistry (komplexeste Task, am wenigsten intuitiv)

**Was die Besten wissen:**
- Density-Fitted Tensor Hypercontraction: Die Factorization-Mathematik
- Word Tables: (R,B,C) = (8,143,44) – was die Zahlen bedeuten
- Angle Loaders: 15 Lookup-Circuits, wie man sie neu plant
- λ_eff: Was der effektive Spektralradius kostet und wie man ihn senkt
- Pi-Gauge: Warum die Gaugewahl die Loader-Kosten bestimmt
- Progressive Rounding: Wie man Präzision verliert ohne Accuracy zu brechen

**Lernübung:**
1. Lies manwithacat's "VQCC Chemistry Primer" Notebook (verlinkt im Hedge Wizardry)
2. Nimm sohier's Starter-Kit und arbeite den dfthcsos-Loop durch
3. Verstehe die (R,B,C)-Table: Was ist R? Was ist B? Was ist C? Warum 44?
4. Baue EINEN Loader selbst und optimiere ihn
5. Refit die Gewichte (wie heliosli es macht) und messe λ_eff-Delta

**Erwartetes Ergebnis nach 4 Wochen:** Du verstehst die Chemistry-Pipeline von der Hamiltonian bis zum Circuit. Kannst Loader-Tweaks machen. Verstehst warum C=44 besser ist als C=39.

---

## Der tägliche Workflow (was die Besten machen)

```
MORGEN (30 Min):
  - Kaggle Code-Tab prüfen: Neue Notebooks seit gestern?
  - Für jedes neue: Was ist der Claim? (Score, Task, Technik)
  - Ist der Claim plausibel? (Kostengröße, Qubit-Zahl)

MITTAG (1-2h, fokussiert):
  - EINE Sache vertiefen (Block zerlegen, Technik nachbauen, Experiment)
  - Immer mit Verifier: Funktioniert es? Was ist der exakte Cost-Delta?
  - Notizen machen: Was habe ich gelernt? Was ist noch offen?

ABEND (30 Min):
  - Negative Results dokumentieren (auch "das hat nicht funktioniert")
  - Public Notebook aktualisieren (wenn es Fortschritt gibt)
  - Discussion-Tab lesen: Neue Fragen? Neue Rulings?
```

**Wichtig:** Die Besten arbeiten nicht 8h am Stück an einem Circuit. Sie arbeiten in kurzen, fokussierten Sprints mit klarem Ziel pro Session.

---

## Dein AI-Agent als Lernpartner (nicht als Ersatz)

### Was der Agent macht (RezOps-Stil, aber lernfokussiert):

1. **Scanner:** Neue public Notebooks finden + zusammenfassen ("Was ist neu? Was ist der Claim?")
2. **Verifier:** Circuits lokal verifizieren + Kosten berechnen
3. **Explainer:** Wenn du einen Block nicht verstehst: Agent erklärt die Gates Schritt für Schritt
4. **Negative-Result-Tester:** Du sagst "Test ob X funktioniert" → Agent baut es, verifiziert, meldet Ergebnis
5. **Tagebuch:** Jeden Tag: Was wurde gelernt? Was ist der aktuelle Stand? Was ist die nächste Frage?

### Was der Agent NICHT macht:
- Nicht blind Code generieren und hoffen dass er funktioniert
- Nicht den Verifier umgehen
- Nicht Claims machen ohne lokale Verifikation

### Setup (1 Tag Arbeit):
```python
# vqcc_agent.py – Dein persönlicher Research-Op
# 1. Kaggle API pollen (neue Kernels)
# 2. Für neue: kernels_pull + Circuit extrahieren
# 3. kickmix Verifier laufen lassen
# 4. Ergebnis formatieren: "Neu: X's Circuit, Task=Y, Cost=Z, Delta zu Current=-W%"
# 5. Wenn Delta > 0.1%: Alert
# 6. Tägliches Digest-Notebook generieren
```

---

## Was du in 9 Wochen weißt (Lernziele)

| Woche | Wissen | Nachweis |
|-------|--------|----------|
| 1 | invsqrt auf Gate-Ebene | Eigener 62Q Circuit gebaut + verifiziert |
| 2 | QROM + Gauge Design | Eigener QROM-Block, 1-2 Toffolis gespart |
| 3 | DQI Decoder + Product Caching | R41 implementiert, Cost-Delta gemessen |
| 4 | R-Reset-Frage beantwortet | Experimentelles Ergebnis (geht / geht nicht) |
| 5 | Chemistry Factorization | (R,B,C)-Table verstanden, eigener Loader |
| 6 | λ_eff + Weight Refit | Refit durchgeführt, Delta gemessen |
| 7 | Vollständiger Portfolio-Loop | Alle 3 Tasks selbst verifiziert + kombiniert |
| 8 | Negative Results Collection | ≥15 dokumentierte Null-Ergebnisse |
| 9 | Write-up Qualität | Ein Notebook das manwithacat/alexchilton-Niveau erreicht |

**Endzustand:** Du kannst jede Technik in jedem public Notebook erklären, nachbauen, und bewerten. Du hast einen eigenen verifizierten Portfolio-Circuit. Und du weißt genau wo die nächsten Verbesserungen liegen – auch wenn du sie nicht mehr machst.

---

## Die eigentliche Lektion (aus hengck23's Post, 23 votes)

> "In the end, ask yourself: What did you learn? Do you have a competitive advantage (after this competition)?"

Die competitive advantage nach dieser Competition:
- **Quantum Circuit Compilation** als Disziplin verstanden
- **Verification-driven Development** internalisiert (Claim → Verifier → Evidence)
- **AI-Agent-gestützte Research Ops** aufgebaut (wiederverwendbar für jede andere Competition/Domäne)
- **Systematisches Negative-Result-Denken** (was NICHT geht ist genauso wertvoll wie was geht)
- **Combinatorische Optimierung** auf Gate-Ebene (QROM, Gauge, Uncompute, Caching)

Das ist transferierbar. Nicht nur für diese Competition.
