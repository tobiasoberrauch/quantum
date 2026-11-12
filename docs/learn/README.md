# 🎓 VQCC Lernprogramm
## Google Quantum AI – Verifiable Quantum Circuit Compilation

**Von den Besten lernen.** 25 Notebooks + 20 Discussions → strukturiertes Lernmaterial in Markdown.

**Stand:** 2026-11-09 | **Competition:** [Kaggle](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/leaderboard) | **Frontier:** 29.3× (Reference = 1.0×)

---

## So benutzt du dieses Programm

1. **Lies in Reihenfolge** (00 → 04). Jeder Track baut auf dem vorherigen auf.
2. **Jede Datei hat ein Lernziel** oben. Wenn du es nach dem Lesen formulieren kannst → weiter.
3. **Zwei Wege pro Thema:**
   - **`.md` Datei lesen** → strukturiert, annotiert, mit Lern-Notizen
   - **`.ipynb` Notebook öffnen** (`notebooks/` Unterordner) → original, ausführbar, interaktiv
4. **Code ausführen:** Notebooks brauchen `pip install kickmix` + Competition-Daten von Kaggle. Die .md-Dateien haben den Code als Referenz.
5. **Lern-Notizen ausfüllen:** Am Ende jeder .md-Datei. Das ist dein eigener Nachweis dass du es verstanden hast.
6. **Nicht alles auf einmal.** Ein Track pro Woche ist realistisch.

### Dateistruktur pro Track
```
01_invsqrt/
├── 01_starter_25_137.md          ← Lesen (annotiert)
├── 02_yoyobar_62q_invsqrt.md     ← Lesen
├── ...
└── notebooks/
    ├── 25-137-starter-notebook.ipynb   ← Ausführen/Interagieren
    ├── lb-22-99-invsqrt-101-62-qubits.ipynb
    └── ...
```

---

## Die drei Tasks in einem Bild

```
                    ┌─────────────────────────────────────────────────┐
                    │         DEINE SUBMISSION (Portfolio)            │
                    │                                                 │
                    │   Score = (ratio_invsqrt × ratio_dqi ×         │
                    │            ratio_chem)^(1/3)                   │
                    └────────────────────┬────────────────────────────┘
                                         │
          ┌──────────────────────────────┼──────────────────────────┐
          ▼                              ▼                          ▼
   ┌─────────────┐              ┌─────────────┐           ┌─────────────┐
   │  INVSQRT    │              │     DQI     │           │  CHEMISTRY  │
   │             │              │             │           │  (DF-THC)   │
   │ β/√x Phase  │              │ RS-Decoder  │           │ FeMoCo H̄   │
   │ 22-bit →    │              │ GF(2¹²)    │           │ Block-      │
   │ phase gate  │              │ Syndrome →  │           │ Encoding    │
   │             │              │ Error fix   │           │             │
   │ Cost:       │              │ Cost:       │           │ Cost:       │
   │ Q×(T+T/4)  │              │ R(k)×Q²×T  │           │ λ_eff×T×Q  │
   │             │              │             │           │             │
   │ Ref: 260Q   │              │ Ref: ~891Q  │           │ Ref: 427Q   │
   │ Best: 62Q   │              │ Best: 891Q  │           │ Best: 427Q  │
   │ Ratio: 21.8 │              │ Ratio: 65.1 │           │ Ratio: 10.7 │
   └─────────────┘              └─────────────┘           └─────────────┘
   
   LEICHTER ←────────────────────────────────────────────→ SCHWIERIGER
   (dein Start)         (größter Kostenblock)       (am wenigst intuitiv)
```

**Warum diese Reihenfolge?**
- invsqrt: Am einfachsten zu verstehen, du hast schon pwq3 → schneller Erfolg
- DQI: Größter absoluter Kostenblock, Q²-Faktor macht Qubit-Zahl kritisch
- Chemistry: Am komplexeste (Factorization + Loaders + Weights), aber kleinster Ratio

---

## Track 0: Fundament (Woche 1, Tag 1-2)

> **Ziel:** Verstehen WAS die Competition ist, WIE der Verifier funktioniert, und WIE man einen Circuit baut + verifiziert.

| # | Datei | Was du lernst | Dauer |
|---|-------|---------------|-------|
| 01 | `00_foundation/01_starter_kit.md` | Offizieller Starter-Loop: Circuit bauen → verifizieren → submit | 30 Min |
| 02 | `00_foundation/02_deep_eda_analogies.md` | Die 3 Tasks als Factory/City/Kitchen verstanden | 45 Min |
| 03 | `00_foundation/03_metric_explained.md` | Exakte Kostenformeln + Verifier-Mechanik | 20 Min |
| 04 | `00_foundation/04_public_dataset_guide.md` | Wie man das Public Dataset nutzt + Credits | 15 Min |

**Nach Track 0 kannst du:** Einen einfachen Circuit in kickmix bauen, mit dem offiziellen Verifier testen, und verstehen was die Zahlen bedeuten.

---

## Track 1: invsqrt (Woche 1-2)

> **Ziel:** Den Inverse-Square-Root-Circuit auf Gate-Ebene verstehen. QROM, Gauge, Uncompute.

| # | Datei | Was du lernst | Technik | Level |
|---|-------|---------------|---------|-------|
| 01 | `01_invsqrt/01_starter_25_137.md` | Ausgangspunkt: Wie man von Reference zu 25× kommt | Portfolio | 🟢 |
| 02 | `01_invsqrt/02_yoyobar_62q_invsqrt.md` | Der 62-Qubit-Circuit: Struktur + Kosten | QROM + Carry | 🟢 |
| 03 | `01_invsqrt/03_kirilltym_exact_gauge_qrom.md` | Exact Gauge + 5-Word QROM Design | Gauge + QROM | 🟡 |
| 04 | `01_invsqrt/04_kirilltym_pi_gauge_refinement.md` | Pi-Gauge Weight Refinement | Gauge Optimization | 🟡 |
| 05 | `01_invsqrt/05_kirilltym_four_loaders_eight_toffolis.md` | Loader-Kompression: 4 Loader, 8 Toffolis | Loader Design | 🟡 |
| 06 | `01_invsqrt/06_kirilltym_uncompute_audit.md` | Uncomputation vs. Reset: Der fundamentale Trade-off | Uncompute/R | 🔴 |
| 07 | `01_invsqrt/07_lightningv08_bezout_schur.md` | Bezout-Schur Decomposition für QROM | Advanced QROM | 🔴 |

**Nach Track 1 kannst du:** Einen invsqrt-Circuit erklären, die QROM-Struktur nachbauen, und verstehen warum 62 Qubits der aktuelle Floor ist.

**Dein Vorteil:** Du hast pwq3 (0.5577). Vergleiche es mit den hier gezeigten Ansätzen – wo bist du besser, wo schlechter?

---

## Track 2: DQI (Woche 3-4)

> **Ziel:** Den Reed-Solomon-Decoder verstehen. Product Caching, Readout, Failure Penalty.

| # | Datei | Was du lernst | Technik | Level |
|---|-------|---------------|---------|-------|
| 01 | `02_dqi/01_busyaprime_top30_verified.md` | DIE Referenz: Alle Top-30 Notebooks verglichen + DQI-Rewrite-Stack | Verification + Caching | 🟡 |
| 02 | `02_dqi/02_manwithacat_hedge_wizardry_dqi.md` | Inkrementelle DQI-Verbesserungen (HW-Einträge) | Micro-optimization | 🟡 |
| 03 | `02_dqi/03_leoprovorov_unbearable_lightness.md` | Portfolio-Ansatz mit Exact Product Reuse | Product Reuse | 🔴 |
| 04 | `02_dqi/04_mrmeows_plateau_circuits.md` | Wie man die Plateau erreicht | Strategy | 🟢 |

**Nach Track 2 kannst du:** Die DQI-Kostenformel R(k)×Q²×T erklären, Product Caching nachvollziehen, und verstehen warum ein einziger fehlgeschlagener Shot so teuer ist.

**Kritisch:** Die Q²-Macht! 891² = 793,881 vs. 892² = 795,664. Ein Qubit mehr kostet 0.22% – bei DQI.

---

## Track 3: Chemistry / DF-THC (Woche 5-6)

> **Ziel:** Die FeMoCo-Hamiltonian-Block-Encoding-Pipeline verstehen. Factorization, Word Tables, Loaders, λ_eff.

| # | Datei | Was du lernst | Technik | Level |
|---|-------|---------------|---------|-------|
| 01 | `03_chemistry/01_dmitriigluzdov_from_source.md` | Von Null: Hamiltonian → Factorization → Circuit | DF-THC Basics | 🟡 |
| 02 | `03_chemistry/02_anazemcev_exact_compilation.md` | Exact Compilation: Präzision vs. Kosten | Compilation | 🟡 |
| 03 | `03_chemistry/03_ahmedberatozer_df_thc_compression.md` | Group Compression: (R,B,C) optimieren + 24 Negative Results | Compression | 🔴 |
| 04 | `03_chemistry/04_somejoint_chem_refit.md` | Weight Refitting: λ_eff minimieren | Optimization | 🔴 |
| 05 | `03_chemistry/05_phucthaiv02_retraining_study.md` | Systematisches Retraining: Was bringt was? | Analysis | 🔴 |

**Nach Track 3 kannst du:** Die (R,B,C)-Tabelle erklären, verstehen warum C=44 besser ist als C=39, einen Angle Loader nachbauen, und Weight Refits durchführen.

**Die härteste Task.** Nimm dir Zeit. Die Analogie hilft: Es ist wie ein Lookup-Table für kontinuierliche Werte – nur dass jeder Lookup ein Quantum Circuit ist.

---

## Track 4: Advanced Process (Woche 7-9)

> **Ziel:** DEN PROZESS der Top-Teams verstehen. Verification Culture, Portfolio Assembly, AI-Agent Workflow, Frontier Tracking.

| # | Datei | Was du lernst | Fokus |
|---|-------|---------------|-------|
| 01 | `04_advanced_process/01_alexchilton_verified_portfolio.md` | Der Gold-Standard Write-up: Every claim verified, every null documented | Verification Culture |
| 02 | `04_advanced_process/02_manwithacat_150k_friends.md` | Frontier Tracking: Wie man den Stand der Community kennt | Community/Ops |
| 03 | `04_advanced_process/03_syed3000_own_portfolio.md` | Eigene Circuits bauen (nicht nur blenden) | Original Research |
| 04 | `04_advanced_process/04_prvsiyan_verifier_guided.md` | Verifier-Guided Optimization: Der Verifier als Design-Tool | Methodology |
| 05 | `04_advanced_process/05_heliosli_public_assembly.md` | Die Assembly-Pipeline: Public → Verified → Portfolio | Process |
| 06 | `04_advanced_process/06_discussions_key_insights.md` | Alle Key-Discussions: RezOps Briefings, Open Problems, Rulings | Meta-Knowledge |

**Nach Track 4 kannst du:** Einen vollständigen Portfolio-Loop selbst durchführen (Scan → Verify → Compare → Assemble → Submit). Und du verstehst WO die nächsten Verbesserungen liegen.

---

## Quick-Reference: Die wichtigsten Zahlen

### Kostenformeln
```
invsqrt:  cost = Qubits × (Toffolis + T_gates/4)
DQI:      cost = R(k) × Qubits² × mean_Toffolis_per_shot
Chem:     cost = λ_eff × total_Toffolis × Qubits

Score = (ref_invsqrt/your_invsqrt × ref_dqi/your_dqi × ref_chem/your_chem)^(1/3)
```

### R(k) – DQI Failure Penalty
```
R(0) = 1.191260  (keine fehlgeschlagenen Shots)
R(1) = 1.196731  (+0.459%)
R(2) = 1.201388  (+0.389% zusätzlich)
→ Ein fehlgeschlagener Shot ≈ 1,840 Toffolis extra
```

### Current Frontier (2026-11-09)
```
invsqrt:  62 Qubits, cost ~95,345, ratio 21.78
DQI:      891 Qubits, cost ~374.7B, ratio ~65.1
Chem:     427 Qubits, C=44, λ_eff≈46.89, T≈14,966, ratio ~10.66
GM:       ~25.15 (public) / 29.30 (leaderboard #1, private)
```

### Key People & Their Contributions
```
syed3000 (Syed Asad Ali):  (8,143,44) Word Table, Loader Compiler, Pi-Gauge
manwithacat (James Barlow): RezOps Agent, Hedge Wizardry, Public Circuits Dataset
kirilltym (Kirill Tymchishin): Exact Gauge, 5-Word QROM, Uncompute Audit
ahmedberatozer:             DF-THC Group Compression, Negative Results
busyaprime (Akmal Xodarev): DQI Product Caching (R41), Top-30 Verification
heliosli:                    Public Dataset Release, Portfolio Assembly
alexchilton:                Verified Three-Task Portfolio (best write-up)
yoyobar:                    62-Qubit invsqrt
somejoint (Agniv Banerjee): 892-Qubit DQI, Chem Refit
maoxin123:                  LB 25.15 Combined
Atakan Aldemir:             Pi-Gauge, CSWAP Deletion, 17-Product DQI
Lera (marculera):           Compact Groups Pipeline (Chemistry foundation)
```

---

## Toolchain Setup (einmalig, 30 Min)

```bash
# 1. kickmix installieren (Circuit Simulator + Verifier)
pip install kickmix

# 2. Kaggle Competition Daten herunterladen
kaggle competitions download -c google-verifiable-quantum-circuit-compilation --verbose
unzip google-verifiable-quantum-circuit-compilation.zip -d vqcc_data/

# 3. Verifier testen
python -c "
from kickmix import verify
print('kickmix OK')
"

# 4. Optional: Qualtran (für Chemistry Starter-Kit)
pip install qualtran
```

**Dateistruktur nach Download:**
```
vqcc_data/
├── verifiers/          # Offizielle Verifier (NICHT modifizieren!)
│   ├── invsqrt/
│   ├── dqi/
│   └── dfthcsos/
├── starter_kit/        # dfthcsos Starter-Kit
└── kickmix/            # kickmix.so (Circuit Simulator)
```

---

## Dein Lern-Tagebuch (leer, zum Ausfüllen)

Jeden Tag 5 Minuten: Was habe ich heute gelernt? Was ist noch unklar?

```
Datum: ___________
Track: ___ (0/1/2/3/4)
Datei: ___________

Gelernt:
- 

Unklar:
- 

Nächste Frage:
- 

Cost-Delta gemessen (falls zutreffend):
Task: ___ | Vorher: ___ | Nachher: ___ | Delta: ___%
```

---

## Progress Tracking

| Track | Status | Datum fertig | Notes |
|-------|--------|-------------|-------|
| 0: Fundament | ⬜ | | |
| 1: invsqrt | ⬜ | | |
| 2: DQI | ⬜ | | |
| 3: Chemistry | ⬜ | | |
| 4: Advanced | ⬜ | | |

⬜ = nicht angefangen | 🟨 = in Arbeit | ✅ = fertig (Lern-Notizen ausgefüllt)
