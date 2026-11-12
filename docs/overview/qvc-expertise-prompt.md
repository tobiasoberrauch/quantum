# QVC · Verifizierbare Quantenschaltkreis-Kompilierung (Reversible Circuits)

**Bereich:** Quanten-Informatik / Reversible Computing / Toffoli-Synthese / Schaltkreis-Optimierung
**Zweck:** Erfahrungswissen, Werkzeuge, Vorgehensweise und Denkweise für diese Aufgabe strukturiert offenlegen und als wiederverwendbare Expertise-Kapsel festhalten.
**Nutzung:** Alles im Block unten kopieren, Platzhalter in `< >` anpassen, an die KI schicken. (Optional: als Prompt #51 in das `david/pocs/expertise_prompts`-Set aufnehmen, damit es über ChatGPT/Claude/DeepSeek/Gemini gelaufen wird.)

````text
Du bist ein erfahrener Praktiker im Fachgebiet der folgenden Aufgabe (Forscher/Optimierer für
verifizierbare reversible Quantenschaltkreise — Toffoli-Synthese, Mess-basiertes Uncomputing,
Arithmetik- und Decoder-Circuits, Quantenchemie-State-Prep) und zugleich Wissensingenieur.
Dein Ziel: das Erfahrungswissen, das ein Experte für diese Aufgabe im Kopf hat, explizit,
prüfbar und wiederverwendbar zu machen — nicht die Aufgabe selbst zu lösen.

## Aufgabe
Optimierung verifizierbarer reversibler Quantenschaltkreise gegen eine Kostenmetrik
(Q_peak × Toffoli-äquivalente Ops) unter strikten Korrektheits-Toleranzen. Konkret drei Benchmarks:
(I) Phasing eines Qubits mit 1/√x über einem großen Integer-Domain, (II) Reed–Solomon-MBUC-
Syndrom-Decoder (iterative belief propagation, ε₊-Fehlerbudget < 1/16 erlaubt), (III) DF-THC-
Chemie-Ground-State-Energie (Givens-Rotation-State-Prep + Winkel-Circuits + gelernte Gewichte).
Lege offen, wie ein Top-Experte solche Circuits ANGEHT: welche Arithmetik-/Decoder-/State-Prep-
Familien, welche Gate-Level-Optimierungs-Pipeline (HMR, Product-Caching, exakte Boolesche
Rewrites via SAT/Solver), wie Error-Margin als Währung gegen Circuit-Kosten getauscht wird,
und wann ein Family-Switch statt Grinding des Incumbent lohnt.

## Kontext
- Wer führt die Aufgabe aus: Solo-Kaggle-Wettbewerber (Quanten-Informatik + reversible Computing).
- Verfügbare Werkzeuge, Daten, Zugänge:
  - Google `kickmix` Simulator/Verifier (lokal, Minuten pro Circuit; exakte klassische Simulation
    pro legaler Input — das ist die "verifiable structure": nur reversible Logik + Phasing +
    Mess-basiertes Uncomputing (HMR)).
  - Qualtran, Python/numpy exakte Integer-Modelle (bit-exakt, was der Circuit berechnet),
    Z3-SAT / Solver für exakte Boolesche Rewrite-Entdeckung, Reverse-Gaussian-Elimination.
  - Öffentliche SOTA-Circuits (.kmb) + Builder-/Optimierungs-Quellen (Apache-2.0),
    Leaderboard-/Dataset-/Kernel-Monitoring.
- Rahmenbedingungen (ankernd, nicht zu ändern):
  - Score = (r_I · r_II · r_III)^(1/3); r_k = reference_cost_k / our_cost_k;
    cost = Q_peak · C; C = mean_executed_Toffolis + t_count/4 + Σ_rotations(0.56·log2(1/ε)+5.3).
  - Aktuelle Public-SOTA (Anker): invsqrt 62Q/1495CCX (err/tol 0.99932, gesättigt);
    dqi 892Q, R(ε₊)=1.19126, ~398k Toffoli/Shot (cost ∝ Q²·T); chem 428Q, λ_eff 47.037
    (Floor 46.79), E_gap-Marge 7e-7 (gesättigt).
  - 5 Submissions/Tag, deterministischer Verifier, Deadline 2027-01-20, Merger-Fenster 2027-01-13.
- Erfolg sieht so aus: Eine Kapsel, die sagt, WIE man einen dieser Circuits angreift
  (Familienwahl → Optimierungs-Pipeline → Margin-Exploit → Verifikation), mit Heuristiken und
  Fehlerbildern — nicht das gelöste Circuit selbst.

## Leitplanken für dieses Fachgebiet
Keine Änderung der Verifier-Parameter (Domain, Toleranzen, Shot-Zahlen, Seeds/Salts, Register).
Erlaubte Budgets dürfen ausgenutzt werden (z. B. dqi ε₊ < 1/16), Regeln nie. Jede nicht triviale
technische Aussage mit Quellenherkunft/Datenstand kennzeichnen. Beliebig spekulative "Quanten-
Supremacy"-Behauptungen vermeiden; auf exakt simulierbare, verifizierbare Struktur fokussieren.

## Regeln
1. Erfinde keine Quellen, Zahlen, Werkzeugfunktionen oder Normen. Wenn du etwas nicht sicher
   weißt, schreib „[zu prüfen]".
2. Kennzeichne jede nicht triviale Aussage:
   [FAKT] belegt (Quelle nennen) · [EMP] Erfahrungswert, eventuell umstritten ·
   [HYP] prüfbare Annahme · [SPEK] Vermutung.
3. Trenne Konsens der Fachleute von deiner persönlichen Präferenz.
4. Bevorzuge den minimalen ausreichenden Weg: so wenige Schritte und Werkzeuge wie möglich,
   aber nie weniger als für eine belastbare Prüfung nötig.
5. Fehlen dir entscheidende Angaben, stelle höchstens 3 Rückfragen. Sonst triff Annahmen und
   liste sie in Abschnitt 9 auf.
6. Wenn die Aufgabe falsch gestellt ist oder ein besserer Ansatz existiert, sag das zuerst.

## Ausgabe — genau diese Abschnitte

### 0. Aufgabenprofil
Ziel · Zielzustand (woran erkenne ich „fertig"?) · Einschränkungen · Risikoklasse
(niedrig/mittel/hoch, mit Begründung) · benötigte Evidenz · grobes Aufwandsbudget.

### 1. Denkweise
- Wie ein Experte das Problem einordnet: Problemtyp, die ersten 3–5 Fragen, die er sich stellt.
- Mentale Modelle und Faustregeln, jeweils mit „gilt wenn … / gilt nicht wenn …".
  (z. B. "Family-Switch ≈ 60 % in 2 Tagen vs Grinding ≈ 11 % in 3 Wochen";
  "Error-Margin ist Währung, die Circuit-Kosten kauft"; "cost ∝ Q²·T ⇒ Width-Cut zählt doppelt".)
- Typische Anfängerfehler und warum sie passieren.
- Was Experten bewusst NICHT tun.

### 2. Erfahrungswissen
Muster, Warnsignale, typische Häufigkeiten, Ausnahmen. Jede Zeile getaggt und mit Konfidenz
(hoch/mittel/niedrig). Decke ab: (a) Arithmetik-Familien für Fixed-Point-Funktionen
(Newton/Halley, Normalisierung, Seed-Tabellen, piecewise Polynome, Trade-off Seed-Genauigkeit
vs Iterationsanzahl vs Breite); (b) iterative Decoder als reversible Circuits (BP-Schedule,
Flag-Reuse, Approximation unter Fehlerbudget); (c) State-Prep + Erwartungswert-Messung
(Givens-Bäume, DF-THC, Winkel-Circuits, gelernte Gewichte, λ_eff-Faktorisierung);
(d) Gate-Level-Optimierung (HMR/Mess-basiertes Uncomputing, Product-Caching/symbolische
ANF-Deduplizierung, exakte Boolesche Rewrites via SAT, Pebbling/Breitenmanagement).

### 3. Werkzeuge (Tabelle)
| Werkzeug | wofür | Eingabe → Ausgabe | Voraussetzungen | Aufwand/Kosten |
| Zuverlässigkeit | Nebenwirkungen/Risiken | wann NICHT nutzen | Alternative |
Zusätzlich: welche Werkzeuge dieselbe Information liefern (redundant, also kein unabhängiger
Beleg) und welche sich ergänzen. (Erwartet u. a.: kickmix-Verifier, Qualtran, numpy-Integer-Modelle,
Z3/Solver, Reverse-Gaussian-Elimination, Symbolischer ANF-Pass, LP-Platzierung.)

### 4. Vorgehensweise
Nummerierte Schritte für den Angriff auf EINEN Benchmark. Für jeden Schritt: Zweck · Werkzeug ·
erwartetes Ergebnis · Prüfung · Entscheidungspunkt (was tun bei Ergebnis A / B / unklar?).
Kennzeichne den Kurzweg (Fälle, in denen 1–2 Schritte reichen) und den vollen Weg.
Schließe mit der Family-Entscheidungslogik ab: Wann Incumbent grinden, wann Familie wechseln,
wann Margin gegen Kosten tauschen.

### 5. Prüfung des Ergebnisses
Wie wird das Ergebnis gegen die Wirklichkeit geprüft (exakte Simulation pro Input, Fuzzing,
Determinismus-Check, Margin-vs-Tolerance-Buchhaltung)? Was zählt als ausreichender Beleg, was
ausdrücklich nicht? Wie vermeidet man "lokales PASS, aber Score sinkt" (Kostenmetrik ≠ Korrektheit)?

### 6. Fehlerbilder
| Fehler | Symptom | Ursache | Gegenmaßnahme |
(z. B.: Margin-Überschätzung → Verifier-FAIL erst am Rand; Width-Reduktion die Toffoli erhöht;
ε₊-Budget "gespart" aber auf frischem Salt-Samen gebrochen; HMR-Phase-Fix vergessen;
Product-Caching auf One-Shot-Arithmetik portiert → null echte Repeats.)

### 7. Stopp- und Eskalationsregeln
Wann aufhören (genug Evidenz / Diminishing Returns) · wann nachfragen · wann an einen Menschen
oder Spezialisten übergeben (z. B. Merger/Outreach für nicht-öffentliche Arbeit) · welche
Aktionen nie ohne Freigabe (Submission verbraucht, Merger-Annahme, Credit-Chain-Änderung).

### 8. Expertise-Kapsel (YAML, wiederverwendbar)
```yaml
id: qvc.verifiable_circuit_compilation.v1
anwendbar_wenn: []
nicht_anwendbar_wenn: []
voraussetzungen: []
denkwiese: []          # die 3–5 wichtigsten Faustregeln
werkzeuge: []          # Name + Zweck + wann nicht
vorgehen: []           # Kurzweg und voller Weg (pro Benchmark-Typ)
familienwahl: []       # Arithmetik / Decoder / State-Prep: wann welche Familie
margin_exploit: []     # wie Error-Margin gegen Kosten getauscht wird
pruefung: []
fehlerbilder: []
stopp: []
eskalation: []
offene_annahmen: []
```

### 9. Offene Annahmen und Prüfauftrag
Was ein echter Experte gegenlesen sollte, priorisiert; je Punkt die konkrete Frage,
die man ihm stellt. (Mindestens: "Gibt es eine invsqrt-Familie unter 62Q×1495CCX?",
"Ist 892Q der echte DQI-Breiten-Floor?", "Ist der λ_eff-Floor 46.79 familien-spezifisch?")
````

## Nachfragen für die zweite Runde
- **Härteprobe:** „Wende die Kapsel aus Abschnitt 8 Schritt für Schritt auf Benchmark II (DQI,
  892Q, R(ε₊)=1.19126, cost ∝ Q²·T) an: Welcher Angriffspunkt — Width / R-Frontier / Toffoli-Count /
  BP-Schedule / ε₊-Budget — gibt den größten ΔGM bei gegebenem Aufwand? Markiere jede Stelle, an
  der die Kapsel nicht trägt, und schlag eine Korrektur vor."
- **Zweite Meinung** (neuer Chat oder anderes Modell): „Hier ist eine Expertise-Kapsel für
  verifizierbare Quantenschaltkreis-Kompilierung. Finde die 5 wichtigsten Lücken oder Fehler,
  ohne neue Fakten zu erfinden — insbesondere bei den Family-Switch-Heuristiken und dem
  Margin-vs-Kosten-Trade-off."

> Die Ausgabe ist eine strukturierte Annahme, kein geprüftes Expertenwissen. Belastbar wird die
> Kapsel erst, wenn ein echter Experte Abschnitt 9 gegengelesen hat oder sie an echten
> Circuit-Läufen (unser lokaler kickmix-Loop) getragen hat.
