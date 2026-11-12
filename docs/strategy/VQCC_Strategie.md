# VQCC Strategie – Von den Besten Lernen

**Basis:** Top-10 Datenanalyse (2026-11-09) | **Deadline Merger:** 2027-01-13 (~9 Wochen)

---

## Ausgangslage

| | Tobias (solo) | Public Frontier | Top-10 Floor | #1 |
|---|---|---|---|---|
| **GM Score** | 23.95 | ~25.15 | 27.03 | 29.30 |
| **invsqrt** | 20.65× | 21.78× | ? | ? |
| **DQI** | ~64.8× | ~65.1× | ? | ? |
| **Chem** | ~10.27× | ~10.66× | ? | ? |

**Kern-Insight:** Der Gap zwischen Public Frontier (25.15) und Top-10 (27.0+) ist ~2 Punkte. Das heißt: Die Top-Teams haben **signifikante private Arbeit**, die nicht öffentlich ist. Wer nur public blendet, kommt auf ~25. Wer Top-10 will, braucht entweder private Optimierung ODER einen Partner mit privater Stärke.

---

## Was die Besten anders machen (und wie du es adaptierst)

### 1. Same-Day Adoption Loop → **Dein: AI-Agent-gestützter Scanner**

**manwithacat/RezOps macht:**
- Scannt NEUE public Notebooks automatisch
- Verifiziert deren Circuits lokal (unveränderter Verifier, Default Salt)
- Aktualisiert das Public Circuits Dataset
- Schreibt Briefing mit exakten Kosten-Deltas

**Du kannst besser:**
Du hast bereits die Infrastruktur (audius, litellm, Qwen). Baue einen **VQCC-Watcher-Agenten**:

```
Pipeline:
  1. Alle 4h: Kaggle API → neue/aktualisierte Kernels für diese Competition
  2. Für jeden neuen Kernel: kernels_pull → Circuit-Dateien extrahieren
  3. Lokaler Verifier-Run (kickmix, CPU, ~5-10 Min pro Task)
  4. Wenn Cost < Current-Best: Alert + auto-update Portfolio
  5. Täglicher Digest: "Was ist heute besser geworden?"
```

**Effekt:** Du adoptierst jede öffentliche Verbesserung innerhalb von Stunden statt Tagen. Das ist der gleiche Hebel wie RezOps, aber automatisierter.

**Aufwand:** ~1 Tag Build. **ROI:** +0.5–1.0 GM über 9 Wochen durch nie etwas zu verpassen.

---

### 2. Negative Results als Moat → **Dein: Systematisches Null-Testing**

**ahmedberatozer macht:** "24 agents ruled out" – 24 parallele AI-Agenten testen Ideen, die dann als dokumentierte Null-Ergebnisse veröffentlicht werden.

**alexchilton macht:** Tabelle "What we tried that did not work" mit gemessenen Werten.

**Du kannst:**
Deine pwq3-Forschung (invsqrt Seed-Modell) ist bereits ein Beispiel. Erweitere das:

```
Für jede Task:
  - Liste der bekannten Techniken (aus Write-Ups extrahiert)
  - Für jede Technik: "Haben wir das schon tried? Was war das Ergebnis?"
  - Ungetestete Kombinationen → AI-Agent testet sie
  - Ergebnis (positiv ODER negativ) → dokumentiert im Portfolio-Notebook
```

**Effekt:** 
- Positiv: Neue Optimierung gefunden
- Negativ: Du weißt was NICHT funktioniert → schnellerer Fokus auf das was geht
- Community: Dein Notebook wird referenziert → Reputation → Merger-Attraktivität

**Aufwand:** Laufend, ~2h/Woche Oversight. **ROI:** Vermeidung von Zeitfressern + gelegentliche Funde.

---

### 3. Best-of-Public + Small Tweaks → **Dein: Hedge-Wizardry-Äquivalent**

**manwithacat/HW macht:** Kleine verifizierte Tweaks (< 0.5% Gain), sofort released. HW-01 bis HW-24 in ~2 Wochen.

**Konkret:**
- Ein Loader neu geplant: -0.29%
- Vier Toffolis weniger in DQI: -0.001%
- Weight Refit: -0.05%

**Du kannst:**
Nimm dein aktuelles Portfolio und identifiziere die **10 größten einzelnen Kostenblöcke** pro Task. Für jeden Block: "Gibt es eine bekannte Alternative, die 1-5 Gates spart?"

```
invsqrt (62Q, ~95k cost):
  - Größter Block: QROM Lookup (wie viele Toffolis?)
  - Zweiter: Carry-Kette
  - Dritter: Phase-Akkumulation
  → Für jeden: AI-Agent sucht in public Notebooks nach alternativen Implementierungen

DQI (891Q, ~374B cost):
  - Größter Block: Syndrome-Decoding Hauptloop
  - Zweiter: Readout
  - Dritter: Product-Reuse
  → R41 Caching (busyaprime) schon drin? Wenn nicht: +13.8 Toffolis/Shot

Chem (427Q, C=44, λ_eff≈46.89):
  - Größter Block: 15 Angle Loaders
  - Zweiter: Word-Table Lookup
  - Dritter: Tree-Traversal
  → Pi-Gauge (Atakan) schon drin? HW-24 Loader Re-plan?
```

**Effekt:** +0.3–0.8 GM durch systematische Mikro-Optimierung. **Aufwand:** ~1 Woche fokussierte Arbeit mit AI-Agent.

---

### 4. Merger als Game-Changer → **Dein: Best-per-Benchmark Kombination**

**Die Mathematik:**
- Du: invsqrt 20.65, DQI 64.8, Chem 10.27 → GM = 23.95
- crackercoder: 24.53 GM (alle drei Tasks local verified)
- Wenn crackercoder z.B. invsqrt 21.5 hat und du DQI 65.0:
  - Combined: invsqrt 21.5 (cracker), DQI 65.0 (du), Chem 10.5 (bester) → GM ≈ 24.8

**Aber das reicht nicht für Top-10.** Top-10 braucht >27. Das heißt:
- Entweder: Partner mit **privater** Stärke >27 in mindestens einer Task
- Oder: Eigene private Optimierung, die den Gap schließt

**Strategie:**
1. **Kurzfristig (Woche 1-2):** crackercoder-Gespräch finalisieren. Was genau hat er privat? Welche Task ist seine Stärke?
2. **Mittelfristig (Woche 3-6):** Eigene private Optimierung auf der schwächsten Task (bei dir: invsqrt, Gap 20.65→21.78 = +5.5%)
3. **Langfristig (Woche 7-9):** Wenn Merger nicht zu Top-10 reicht → zweite Merger-Runde mit stärkerem Partner

**Dein Unique Selling Point für Merger:**
- pwq3 invsqrt Seed-Modell (0.5577 vs 0.617 published) – das ist **besser als alles public**
- AI-Agent-Infrastruktur (automatischer Scanner, Verifier, Portfolio-Manager)
- Same-day Adoption Loop (bereits aktiv)
- Dokumentierte Negative Results

**Das macht dich zum idealen "Operations Partner"** – du bringst die Infrastruktur, der andere bringt die private Circuit-Forschung.

---

### 5. Die R-Reset-Frage → **Dein: Early-Mover-Vorteil**

**Discussion #755302:** Ist R (Reset ohne Uncompute) erlaubt?

**Warum das wichtig ist:**
- In DQI ist die Uncompute-Hälfte des Circuits ein großer Kostenblock
- Syed Asad Ali (Comment): "the verifier already catches input-dependent R resets"
- Hassan Mohamed: "the answer changes the cost scale a lot"
- **Wenn R erlaubt ist:** DQI-Kosten könnten um 20-40% fallen → Ratio von 65 auf 80+

**Deine Strategie:**
1. **Jetzt:** Experimentiere lokal – baue eine DQI-Variante mit R-Reset statt Uncompute
2. **Verifiziere:** Läuft der offizielle Verifier durch? (Syed sagt ja für input-independent, nein für input-dependent)
3. **Dokumentiere:** Wenn es klappt → sofort public Notebook mit exaktem Cost-Delta
4. **Timing:** Vor dem 20. November Milestone (wird in der Discussion erwähnt)

**Risk:** Wenn die Hosts R später verbieten, ist die Arbeit umsonst. Aber: Die Frage ist OFFEN, und wer als erster eine working R-Reset-Variante hat, hat einen massiven Vorsprung.

**Aufwand:** 2-3 Tage Fokussierung. **ROI:** Potenziell +2-5 GM (DQI von 65→80+).

---

## Konkreter 9-Wochen-Plan

### Phase 1: Fundament (Woche 1-2)
- [ ] VQCC-Watcher-Agent bauen (auto-scan + verify + alert)
- [ ] crackercoder-Merger-Gespräch finalisieren (was hat er privat?)
- [ ] Aktuelles Portfolio auditieren: Top-10 Kostenblöcke pro Task identifizieren
- [ ] R-Reset-Experiment starten (lokal, kickmix)

### Phase 2: Optimierung (Woche 3-5)
- [ ] Mikro-Tweaks auf größten Kostenblöcken (Hedge-Wizardry-Stil)
- [ ] pwq3 invsqrt weiterentwickeln (0.5577 → <0.50 Ziel)
- [ ] Wenn R-Reset funktioniert: DQI-Circuit neu bauen
- [ ] Negative Results dokumentieren (mindestens 5 pro Task)
- [ ] Public Notebook veröffentlichen (Reputation + Merger-Attraktivität)

### Phase 3: Kombination (Woche 6-8)
- [ ] Merger finalisieren (best-per-benchmark)
- [ ] Gemeinsames Portfolio: beste Circuits aus beiden + eigene Tweaks
- [ ] Vollständige Verifikation (alle drei Tasks, beide Salts, planted defects)
- [ ] Submission + Monitoring

### Phase 4: Final Push (Woche 9, bis Deadline)
- [ ] Letzte Mikro-Optimierungen
- [ ] Edge Cases prüfen (DQI failed shots, Chem accuracy boundary)
- [ ] Finale Submission
- [ ] Write-up vorbereiten (Prize Winner Requirement)

---

## Erwartungsergebnis

| Szenario | GM Score | Voraussetzung |
|----------|----------|---------------|
| **Solo, nur Public Blending** | ~25.0 | Watcher-Agent + Tweaks |
| **Solo + pwq3 + R-Reset** | ~26.0-27.0 | R-Reset funktioniert + invsqrt-Fortschritt |
| **Merger mit crackercoder (24.53)** | ~25.5 | Best-per-benchmark, keine private Stärke |
| **Merger mit starkem Partner (>27 privat)** | **27.5-29.0** | Partner findet sich, Kompatibilität |
| **Merger + R-Reset + pwq3** | **28.0-29.5** | Alles trifft zu |

**Realistischstes Ziel Top-10:** Merger mit Partner der private DQI oder Chem Arbeit hat (>27 in einer Task) + deine invsqrt pwq3 + Watcher-Agent für same-day adoption.

---

## Was du NICHT tun solltest

1. **Kein eigenes Circuit von Grund auf** – die Top-Teams tun das auch nicht. Kuratieren > Erfinden.
2. **Kein GPU/ML-Ansatz** – das Problem ist kombinatorisch, nicht statistisch.
3. **Kein Ignorieren der Community** – die besten Ideen kommen aus public Notebooks. Wer solo in seiner Höhle sitzt, verpasst die Frontier.
4. **Kein Blindes Vertrauen in AI-Generierten Code** – jeder Circuit MUSS durch den offiziellen Verifier. "Sampled PASS is not an exact-correctness proof" (kirilltym).
5. **Kein Verpassen des Merger-Fensters** – 2027-01-13 ist hart. Danach kein Team-Wechsel mehr.

---

## Dein Unfair Advantage

Die Top-Teams haben alle eines gemeinsam: **Sie sind Vollzeit dabei.** Du nicht. Aber du hast etwas, das die meisten nicht haben:

1. **AI-Agent-Infrastruktur** (audius, litellm, Qwen) → RezOps-Äquivalent in 1 Tag gebaut
2. **pwq3** → Besser als alles public in invsqrt (0.5577 vs 0.617)
3. **Systematisches Denken** → Negative Results, Cost-Block-Analyse, Verification-Protokolle
4. **Zeit** → 9 Wochen bis Deadline, die meisten Top-Teams sind seit Oktober dabei und haben die easy Gains schon genommen. Die verbleibenden Gains sind systematisch erarbeitbar.

**Deine Rolle im Ökosystem:** Nicht der beste Circuit-Designer. Sondern der beste **Operations-Partner** – derjenige, der die Infrastruktur stellt, die Verifikation sicherstellt, und die public Arbeit am schnellsten adoptiert. Dafür brauchst du einen Partner mit starker privater Circuit-Forschung.
