# Google Quantum AI – Verifiable Quantum Circuit Compilation
## Top-10 Leaderboard Deep-Dive & Erkenntnis-Report

**Stand:** 2026-11-09 | **Competition ID:** 161954 | **Merger-Deadline:** 2027-01-13

---

## 1. LEADERBOARD TOP 10

| # | Team | Score | Letzter Submit |
|---|------|-------|----------------|
| 1 | Entangled Team | 29.30100 | 2026-11-08 |
| 2 | Schrödinger's cat lived | 29.18459 | 2026-11-08 |
| 3 | taiseiu | 28.44097 | 2026-11-07 |
| 4 | Breaking1800 | 27.99617 | 2026-11-01 |
| 5 | Diana | 27.43151 | 2026-11-07 |
| 6 | CroDoc & Pavel | 27.39772 | 2026-11-07 |
| 7 | Yan Zhou | 27.36301 | 2026-11-08 |
| 8 | Thinking... | 27.23779 | 2026-11-07 |
| 9 | yicheng guang | 27.18925 | 2026-11-08 |
| 10 | Bingran You | 27.02564 | 2026-11-05 |

**Frontier:** ~25× besser als Googles Reference-Circuit (Score 1.00). Top-10 alle >27×.

---

## 2. WIE DIE COMPETITION FUNKTIONIERT

### Drei Tasks, ein Geometrisches Mittel

| Task | Was der Circuit tut | Kostenformel | Reference |
|------|---------------------|--------------|-----------|
| **invsqrt** | Phasiert 22-Bit Input x mit β/√x (Coulomb-Energie in Fusion-Simulationen) | Qubits × (Toffolis + T/4) | 260 Q, 7,988 |
| **DQI** | Dekodiert Reed–Solomon-Syndrom über GF(2¹²), korrigiert Quantenfehler | R(k) × Qubits² × Toffolis | ~891 Q |
| **DF-THC-SOS** | Block-Encoding der FeMoCo-Hamiltonian für Quantum-Chemistry | λ_eff × T × Q | 427 Q, C=44 |

**Score = (ref_cost_invsqrt / your_cost_invsqrt × ref_cost_dqi / your_cost_dqi × ref_cost_chem / your_cost_chem)^(1/3)**

### Verifiability-Prinzip
- Der Verifier seedet Test-Inputs aus SHA-256(Circuit-Datei + Salt)
- Kein verstecktes Test-Set → jeder kann lokal verifizieren
- kickmix (PyPI: `pip install kickmix`) = offizialer Circuit-Simulator
- Ein fehlgeschlagener DQI-Shot in 102,400 kostet ~1,840 Toffolis (Repetition-Penalty)

---

## 3. TOP-AUTOREN & IHR BEITRAG

| Autor | Votes | Kernels | Kernbeitrag |
|-------|-------|---------|-------------|
| **heliosli** | 203 | 2 | Public-Dataset-Release, "best-of-public" Portfolio-Assembler |
| **kirilltym** | 195 | 4 | Exact Gauge + 5-Word QROM, Pi-Gauge Weight Refinement, Conditional Uncompute Audit |
| **manwithacat** (James Barlow) | 180 | 27 | RezOps AI-Agent, Hedge Wizardry (kleine verifizierte Tweaks), Public Circuits Dataset |
| **alexchilton** | 124 | 2 | 24.94 LB Verified Three-Task Portfolio (detailliertester Write-up) |
| **ahmedberatozer** | 121 | 1 | DF-THC Group Compression, 24-Agent-Negative-Results |
| **somejoint** (Agniv Banerjee) | 117 | 1 | 24.65 Local GM, Chem Refit, 892-Qubit DQI |
| **yoyobar** | 105 | 1 | LB 22.99 invsqrt, 101→62 Qubits |
| **syed3000** (Syed Asad Ali) | 60 | 2 | (8,143,44) Word Table, eigener Loader-Compiler, Pi-Gauge |
| **maoxin123** | 48 | 5 | LB 25.1498 Combined invsqrt + refit chem |
| **busyaprime** (Akmal Xodarev) | 52 | 1 | Top-30 Re-Verified, DQI Product Caching (R41) |
| **dmitriigluzdov** | 92 | 1 | Quantum Circuit Compilation from Source, FeMoCo Factorization Dataset |
| **evgendvorkin** | 58 | 1 | Deep EDA with Analogies (Factory/City/Kitchen-Metaphern) |

---

## 4. METHODOLOGIE DER TOP-TEAMS

### Muster 1: "Best-of-Public Portfolio" (dominant)
Die Top-Teams schreiben **keine eigenen Circuits von Grund auf**. Stattdessen:
1. Scannen alle öffentlichen Notebooks/Datasets
2. Verifizieren jeden Circuit mit dem offiziellen Verifier (lokal, ungesalzen)
3. Wähle den günstigsten pro Task
4. Kombinieren zu einem Portfolio
5. Fügen kleine eigene Optimierungen hinzu (< 0.5% Gain pro Tweak)

**Beispiel alexchilton (24.94 LB):**
- invsqrt = maoxin123's Circuit (baut auf Hosen42, Ertuğrul Özer, Kirill Tymchishin, Atakan Aldemir, Syed Asad Ali)
- DQI = Ertuğrul Özer's V70 Readout Rewrite
- Chemistry = Syed Asad Ali's Table + manwithacat's Loaders + Atakan's Pi-Gauge

### Muster 2: AI-Agent-gestützte Research Ops
**manwithacat's "RezOps"** (Claude-basiert):
- Scannt neue öffentliche Notebooks automatisch
- Verifiziert deren Circuits lokal
- Maintained das Public Circuits Dataset
- Schreibt "RezOps Briefings" (12k–23k Zeichen pro Post)
- Mensch setzt Richtung, reviewt und approvet

### Muster 3: Negative Results als Beitrag
- ahmedberatozer: "24 agents ruled out" – dokumentiert was NICHT funktioniert
- manwithacat: `vqcc-chemistry-negative-results` Dataset
- alexchilton: "What we tried that did not work" Tabelle
- **Prinzip:** Negative Ergebnisse sparen der Community Zeit

### Muster 4: Incremental Verification
- Jeder Tweak wird vor Release lokal verifiziert
- SHA-256-Pinning aller Input-Dateien
- "Planted defects that went red" – Testen ob der Verifier Fehler auch findet
- Paired-seed Tests (zwei verschiedene Salts, gleiche Kosten erwartet)

---

## 5. TECHNISCHE TECHNIKEN (State of the Art)

### invsqrt (Inverse Square Root)
- **QROM** (Quantum Random Access Memory) für Lookup-Tabellen
- **Uncomputation** vs. **Reset (R)**: Offene Frage ob R erlaubt ist (Discussion #755302)
- **Gauge Optimization**: Pi-Gauge reduziert Loader-Kosten
- **5-Word QROM** (kirilltym): Kompaktere Wort-Tabelle
- **Carry Port** (Kirill Tymchishin): Bessere Trägheitsverteilung
- **CSWAP Deletion** (Atakan Aldemir): Weniger Controlled-Swaps
- Frontier: **62 Qubits**, ~95,345 cost (Ratio 21.78)

### DQI (Quantum Error Correction Decoder)
- **Reed-Solomon over GF(2¹²)**: Syndrome-Dekodierung
- **Product Caching** (busyaprime R41): Wiederholte Produkte auf eine Wire schreiben → 13.8 Toffolis/Shot gespart
- **Readout Rewrite** (ozertuu V70): 48 Controlled Swaps durch CX ersetzen
- **Exact Product Reuse** (leoprovorov): ~395.4k Toffolis/Shot
- **17-Product DQI** (Atakan Aldemir): Weniger Produkte, gleiche Qubits
- Frontier: **891–892 Qubits**, ~374.7B cost (Ratio ~65)

### DF-THC-SOS (Chemistry / FeMoCo)
- **DF-THC Factorization**: Density-Fitted Tensor Hypercontraction
- **(R,B,C) = (8,143,44) Word Table** (syed3000): Kompakter als (9,143,39)
- **Pi-Gauge** (Atakan Aldemir): Reduziert λ_eff
- **Loader Re-planning** (manwithacat HW-24): 11 Loaders neu geplant → -0.29%
- **Weight Refit** (heliosli): Kontinuierliche Gewichte optimiert
- **Compact Groups** (Lera/marculera): Basis-Pipeline
- **Progressive Rounding** (ahmedberatozer): Präzisionsmanagement
- Frontier: **427 Qubits**, C=44, λ_eff≈46.89, T≈14,966 (Ratio ~10.6)

### Finite-Feld-Multiplikation (Grundlagenforschung)
- μ₄(5) = μ₄^sym(5) = 11 (bewiesen, kein Rank-10 Algorithmus existiert)
- μ₄^sym(6) = 14 (bewiesen, kein symmetrischer Rank-13 Algorithmus)
- Lean 4 + Mathlib formale Beweise (Dyst-0)
- **Relevanz:** Setzt untere Schranken für Multiplikations-Kosten in GF(4)

---

## 6. DATENSETS (Top 15 nach Downloads)

| Dataset | Downloads | Inhalt |
|---------|-----------|--------|
| manwithacat/vqcc-apache-public-circuits | 75,316 | Alle public Circuits (Apache-2.0), frontier_steps.csv |
| dmitriigluzdov/vqcc-femoco-public-factorization | 43,369 | FeMoCo Angle Words, Factorization |
| sohier/verifiable-circuit-compilation-starter-kit | 22,817 | Offizielles Starter-Kit (Qualtran, kickmix) |
| ahmedberatozer/df-thc-group-compression-factorization | 11,714 | DF-THC Group Compression |
| manwithacat/vqcc-hedge-wizardry | 10,745 | Kleine verifizierte Tweaks (HW-01 bis HW-24) |
| ahmedberatozer/vqcc-v8-components | 8,733 | Bezout-Schur DQI + 8-bit Chem |
| michaelrustad/vqcc-dfthc-r10-merged-groups | 7,406 | DF-THC R10 merged-group |
| ahmedberatozer/vqcc-v9-components | 7,179 | Narrow fused DQI + R10 J5 |
| syed3000/vqcc-own-circuit-portfolio | 6,500 | Syeds eigenes Portfolio (8,143,44) |
| somejoint/qcc-ladder-parts | 4,264 | QCC Ladder Components |
| kozykappa/quantum-ai-dataset | 2,266 | Quantum Circuit Toolbox |
| manwithacat/vqcc-chemistry-negative-results | 2,082 | Dokumentierte Null-Ergebnisse |
| auqib92/qvcc-own-circuits | 1,813 | Eigene Circuits (invsqrt, dqi, dfthcsos) |

---

## 7. DISCUSSIONS – KEY INSIGHTS

### RezOps Briefings (manwithacat) – die wichtigsten "Living Documents"
- **#757068:** Plateau 25.148 – two one-Toffoli invsqrt edits, four-route DQI cache, refit chemistry weights
- **#756824:** Plateau 25.09 – measure-first rewrites cut invsqrt 1.8%, DQI loses 14 Toffolis
- **#756558:** Plateau 24.94 – chemistry −1.0% on Syed's re-planned loaders; silver/bronze 0.04% apart
- **#756210:** Chemistry falls 2.8% via Atakan's pi gauge + Syed's C=44 table; invsqrt under 97,810

### Open Problems (Rustam Bazarbayev, #757030)
- Shifters, Qubit Floors, Uncompute & Loader Bounds
- "Small, hard, well-defined combinatorics problems"
- Negative results gewünscht ("we proved this is impossible")

### Regeln & Lizenz
- **#756131:** jday96314's DQI Decoder – Apache-2.0 bestätigt vom Autor
- **#756745:** Prize eligibility für aus public Apache-2.0 assemblierte Submissions
- **#755996:** Prize Winner Requirements (keine Reise-Pflicht)
- **#755302:** R-Reset vs. Uncomputation – noch ungeklärt!

### Meta-Lektionen (hengck23, #754652, 23 votes)
> "This is a rare competition that many are using the same AI agent. Many are unfamiliar with the background knowledge. The maths/modeling is rather difficult. AI agent is in general better than the human participant."

> "You can copy others' circuits and fuse them with yours, then make some improvements using your CC or Codex. But in the end, ask yourself: What did you learn? Do you have a competitive advantage?"

### Lynn Langit (#755972) – Crowd-Built Entry Lessons
- Top 5% erreicht durch Verifizieren und Blenden von Public Work
- "One failed DQI shot in 102,400 costs as much as ~1,840 Toffolis"
- 8 Prinzipien + 10 geschlossene Hebel (visual summary)

---

## 8. TOOLCHAIN & INFRASTRUKTUR

| Tool | Zweck |
|------|-------|
| **kickmix** (`pip install kickmix`) | Offizieller Circuit-Simulator/Verifier (PyPI, Windows/Linux/macOS) |
| **Qualtran** | Google's Quantum Circuit Library (Starter-Kit) |
| **Kaggle Notebooks** | CPU-only, Internet für pip install |
| **Claude / AI Agents** | Research Ops (RezOps), Code-Generierung, Verifikation |
| **SHA-256 Pinning** | Datenintegrität aller Circuit-Dateien |
| **Apache-2.0** | Lizenz für alle public Submissions (Pflicht für Preisträger) |

**Wichtig:** KEIN GPU/TPU verwendet. 100% CPU. Das ist ein kombinatorisches Optimierungsproblem, kein ML-Problem.

---

## 9. DEINE POSITION (Tobias Oberrauch)

Aus Discussion #755075:
- **Solo Competitor** auf ~23.95 GM (Public Frontier)
- Best-of-public Portfolio mit fast same-day Adoption Loop
- invsqrt 20.65×, DQI ~64.8×, chem ~10.27×
- Eigene invsqrt-Forschung: improved seed model "pwq3" (0.5577 worst err/tol vs published 0.617)
- **Sucht Merger-Partner** vor dem 2027-01-13 Deadline
- crackercoder hat bereits geantwortet: Team bei 24.53 locally verified, offen für Merger

**Gap zu Top-10:** ~3.1 Punkte (23.95 vs 27.03). Top-10 nutzen alle drei Tasks auf >27× Niveau.

---

## 10. ERKENNTNISSE – WAS MAN VON DEN BESTEN LERNEN KANN

### Strategisch
1. **Öffentliche Arbeit ist der Rohstoff.** Die besten Teams sind die besten Kuratoren + Verifizierer, nicht die besten Erfinder.
2. **Same-day Adoption.** Neue public Circuits werden innerhalb von Stunden verifiziert und ins Portfolio integriert.
3. **Negative Results sind ein Feature.** Wer dokumentiert was NICHT geht, spart der Community Wochen.
4. **AI Agents als Research Ops.** manwithacat's RezOps scannt, verifiziert, kuratiert – der Mensch steuert nur Richtung.
5. **Merger ist erlaubt und sinnvoll.** Best-per-benchmark Kombination schlägt jede Solo-Leistung.

### Technisch
6. **Verifikation vor allem.** Kein Circuit wird ohne lokalen Verifier-Run verwendet. SHA-256-Pinning. Planted defects.
7. **Incremental Gains.** Die letzten Punkte kommen aus <0.5% Tweaks (ein Toffoli weniger, ein Loader neu geplant).
8. **Task-Unabhängigkeit.** Die drei Tasks werden komplett unabhängig optimiert – nur das geometrische Mittel verbindet sie.
9. **QROM & Gauge sind die Hebel.** In invsqrt: Wort-Tabelle + Gauge. In Chem: Loader-Planung + Pi-Gauge. In DQI: Product Caching.
10. **Die R-Reset-Frage ist der nächste große Hebel.** Wenn R erlaubt ist, fallen Uncompute-Kosten weg → massive Einsparungen in DQI.

### Meta
11. **Community > Einzelkämpfer.** Die Competition ist ein kollaboratives Forschungsprojekt mit Wettbewerbsoberfläche.
12. **Write-ups sind das eigentliche Produkt.** Die besten Notebooks sind nicht Code, sondern Erklärungen mit Beweisen.
13. **Transparenz schafft Vertrauen.** Jeder Claim wird mit Verifier-Output, SHA-Hash und Reproduktionsanleitung belegt.
14. **Die Frontier ist eine Treppe.** Jeder Schritt ist dokumentiert (frontier_steps.csv). Man sieht genau wer wann was verbessert hat.

---

## 11. DATEIEN & ZUGRIFF

| Datei | Inhalt |
|-------|--------|
| `raw_data.json` | Alle Rohdaten (Leaderboard, 387 Kernels, 42 Datasets, 20 Discussions mit Volltext) |
| `writeup_extracts.json` | Extrahierter Markdown-Text der Top-10 Write-Ups |
| `analysis.json` | Aggregierte Analyse (Authors, Resources, Sources, Themes) |
| `kernels/` | 25 heruntergeladene Notebooks (.ipynb) |
| `REPORT.md` | Dieser Report |

**Zugriff auf Kaggle:**
- Leaderboard: https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/leaderboard
- Code Tab: https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/code
- Discussions: https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion
