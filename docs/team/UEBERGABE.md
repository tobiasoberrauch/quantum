# Übergabe an die drei Arbeitsstränge

Stand: 13.11.2026. Alle Pfade sind relativ zur Wurzel des Repos `quantum`, sofern nicht anders
angegeben. Jeder Pfad wurde am 13.11.2026 auf Existenz geprüft.

**Wichtig vorab:** Die Ordner `work/`, `runs/` und `data/` liegen nicht im Git-Repo, sondern nur
auf dem Arbeitsrechner. Wer dort keinen Zugang hat, braucht ein Paket (siehe Abschnitt 6).

---

## 1. Richtigstellung zur Herkunft der Ausgangsstände

Die Anfrage nennt einen „eigenen 62-Qubit-Schaltkreis und seinen Generator“. Den gibt es so nicht.

| Aufgabe | Ausgangsstand | Herkunft | Generator vorhanden? |
|---|---|---|---|
| invsqrt, 62 Qubits (a15b0d73, 9c708f7b) | 22,11 und 22,20 | Fund unseres Überwachungslaufs im öffentlichen Bestand, soweit belegbar | **Nein** |
| invsqrt, 46 Qubits (321aff83) | 25,91 | öffentliches Paket von Syed Asad Ali | Ja, im Paket |
| dqi, 892 Qubits (e9f54be3) | 65,23 | öffentlicher Bestand | **Nein** |
| dqi, 893 Qubits (Nachbau) | 63,14 | öffentlicher Generator einer anderen Linie | Ja, `work/dqi_builder_repro/` |
| dqi, 889 Qubits (7cbe8ecf) | 67,75 | öffentliches Paket von Syed Asad Ali | Ja, im Paket |
| chem (b0cc7e3c) | 11,22 | öffentlicher Bestand | Nein, nur fremde Compiler |
| chem (6418ec8e) | 11,31 | öffentliches Paket von Syed Asad Ali | Ja, im Paket |

Folge für Tag 1: Die bytegenaue Reproduktion ist nur für die drei Schaltkreise aus dem
öffentlichen Paket möglich. Für die eingereichten Stände gibt es nur die fertigen Dateien; dort
heißt Reproduktion: Prüfprogramm laufen lassen und Kosten auf die letzte Stelle treffen.

In `STELLENAUSSCHREIBUNGEN.md` steht an mehreren Stellen „unser Schaltkreis“. Gemeint ist: der
Schaltkreis, den wir eingereicht haben, nicht einer, den wir selbst erzeugt haben.

---

## 2. Gemeinsame Übergaben

### 2.1 Offizielle Prüfprogramme

| Was | Pfad |
|---|---|
| Wurzel der Prüfprogramme | `data/verifiers/` (Verweis auf `.kaggle_data/competition/verifiers/`) |
| invsqrt | `data/verifiers/invsqrt/verify_submission_invsqrt.py` |
| invsqrt, Referenzschaltkreis | `data/verifiers/invsqrt/nr_reference_circuit.py` |
| dqi | `data/verifiers/dqi/verify_submission_dqi.py` |
| dqi, Referenzschaltkreis | `data/verifiers/dqi/dqi_reference_circuit.py` |
| chem | `data/verifiers/dfthcsos/verify.py` |
| chem, Beschreibung der Wertung | `data/verifiers/dfthcsos/SCORING_README.md` |
| chem, Unterbau | `data/verifiers/dfthcsos/scoreinfra/` |

Referenzkosten für das Verhältnis (Verhältnis = Referenz geteilt durch eigene Kosten):

| Aufgabe | Referenzkosten |
|---|---|
| invsqrt | 2.076.774,233715282 |
| dqi | 24.439.463.583.672,93 |
| chem | 3.355.599.588,3155375 |

### 2.2 Seed-Logik (alle drei Aufgaben gleich aufgebaut)

- Ohne Salt: Seed = SHA-256 der `.kmb`-Bytes als ganze Zahl.
- Mit Salt: Seed = SHA-256 der Zeichenkette aus Schaltkreis-Hash und Salt.
- Bei chem geht der Hash über die gesamte Einreichung (Schaltkreise, Zerlegung, Baum).
- Der Seed bestimmt die Messergebnisse (`HMR`, `R`) und bei dqi auch die gezogenen Testfälle.
- Unsere lokalen Läufe nutzen den Salt `notebook-verification`. Die eingereichte Wertung 25,2952
  stimmte mit der lokalen Vorhersage überein.
- **Offen:** Welchen Salt Kaggle verwendet, wissen wir nicht sicher. Das öffentliche Paket nennt
  für seinen dqi-Schaltkreis zwei Fehlschüsse in Kaggles Ziehung, lokal sind es null. Jede
  Änderung an den Bytes eines Schaltkreises zieht neue Zufallswerte.

### 2.3 kickmix, kmx und Versionen

| Komponente | Version | Ort |
|---|---|---|
| kickmix | 0.1.dev0 | `qualtran/kickmix/` (übersetzt für Python 3.13 auf macOS/ARM) |
| kmx (unser Optimierer und Labor) | 5 | `kmx/`, Einstieg `python -m kmx` |
| Python | 3.13.13 | Umgebung `.venv-chem/` |
| NumPy / SciPy / JAX | 2.5.4 / 1.18.1 / 0.12.0.1 | `.venv-chem/` |

Auf anderen Betriebssystemen muss kickmix aus den Wettbewerbsdaten neu installiert werden.
kmx-Dokumentation: `docs/` (Einsteiger- und Architekturseiten).

### 2.4 Ergebnis- und Fehlschlag-Logbuch

Das Logbuch liegt außerhalb des Repos unter `~/.agent-memory/kaggle-qvc/` (26 Notizen). Die
wichtigsten:

| Notiz | Inhalt |
|---|---|
| `2026-11-12-apex-zyklus1-chem-qat.md` | Aktuellster Stand, alle Messungen und Fehlschläge aus Zyklus 1, öffentliches Paket |
| `2026-11-11-harvest-portfolio-submit.md` | Eingereichter Stand, Ablauf der Einreichung |
| `2026-11-11-invsqrt-reharvest-subagent.md` | Öffentliche invsqrt-Kandidaten und ihre geprüften Kosten |
| `2026-11-10-dqi-builder-source-map.md` | Aufbau des öffentlichen dqi-Generators (893 Qubits) |
| `2026-11-10-dqi-merger-research.md` | Untersuchung, ob sich dqi-Linien kombinieren lassen |
| `2026-11-10-chem-compiler-bench.md` | Vergleich der chem-Compiler |
| `2026-11-10-chem-del-and-audit.md` | Suche nach einsparbaren Toffolis in chem |
| `2026-11-10-rreset-rule-check.md` | Regelprüfung zum Zurücksetzen von Qubits |
| `2026-11-11-main-py-beam-search-local-optimal.md` | Automatische Vereinfachung ist lokal ausgereizt |

Rohdaten der Experimente aus Zyklus 1: `work/apex_1112/<rolle>/`.

### 2.5 Rechenressourcen

- Ein Rechner: Apple M3 Max, 16 Kerne, 128 GB Arbeitsspeicher, keine Grafikkarte.
- Gemessene Prüfzeiten bei ruhigem Rechner: chem 16 s, dqi 65 bis 95 s, invsqrt 3 bis 4,5 min.
  Unter Last verdoppeln sie sich.
- Es darf nur eine offizielle Prüfung gleichzeitig laufen. Sperre:
  `until mkdir /tmp/vqcc_verify.lock 2>/dev/null; do sleep 5; done` und danach
  `rmdir /tmp/vqcc_verify.lock`.

### 2.6 Einreichungszugang

- Eingereicht wird ausschließlich über das Kaggle-Konto des Teamleiters, nach dessen Freigabe im
  Einzelfall. Zugangsdaten werden nicht weitergegeben.
- Einreichfertige, geprüfte Pakete:

| Paket | Wertung lokal | Pfad |
|---|---|---|
| Eingereichter Stand plus invsqrt 9c708f7b | 25,3285 | `work/apex_1112/harvester/build_9c70/submission.zip` |
| Öffentliches Paket komplett | 27,0784 | `work/apex_1112/harvester/build_syed/submission.zip` |

- Werkzeuge: `work/apex_1112/harvester/build_9c70.py` (Paket bauen),
  `work/apex_1112/harvester/verify_zip.py` (Paket aus den Zip-Bytes prüfen),
  `work/apex_1112/harvester/refresh_1112/verify_cand.py` und `verify_chem.py` (Einzelprüfung).

---

## 3. invsqrt

### 3.1 Artefakte

| Was | Pfad |
|---|---|
| 62 Qubits, eingereicht (a15b0d73, 22,1109) | `runs/agent/autonomous/20261110T145822Z/cycle1/artifacts/a15b0d73f720/invsqrt.kmb` |
| 62 Qubits, bester (9c708f7b, 22,1984) | `runs/agent/autonomous/20261112T033747Z/cycle1/artifacts/9c708f7b9abc/invsqrt.kmb` |
| 46 Qubits (321aff83, 25,9070) | Datei `invsqrt.kmb` im öffentlichen Paket (siehe 3.2) |
| Prüfergebnis 46 Qubits | `work/apex_1112/harvester/refresh_1112/verify_invsqrt_321aff83.json` |
| Analyse der 62-Qubit-Schaltkreise | `work/apex_1112/pebble/` (Vergleich a15b gegen 9c70, Qubit-Spitzenlast, Epilog-Untersuchung) |

### 3.2 Öffentlicher Generator

- Paket: `work/apex_1112/harvester/refresh_1112/dl/syed3000__vqcc-own-circuit-portfolio/vqcc-own-circuit-portfolio.zip`
  (SHA-256 `2629441e…5a6f`, Apache-2.0).
- Quellen daraus entnommen: `work/apex_1112/harvester/refresh_1112/src_peek/invsqrt.zip`.
- Aufruf laut README des Pakets:
  `bash build.sh <kickmix-Ordner> <Prüfprogramm-Ordner> <Ausgabe-Ordner>`.
- Aufbau: ein Stapel von Umbau-Schritten mit fester Reihenfolge (`src/patches/PATCH_ORDER.txt`).
- Von uns bisher nur gelesen, nicht ausgeführt.

### 3.3 Definition der Aufgabe

Die Aufgabe ist keine Festkomma-Ausgabe, sondern eine Phase:

```
|x>|0...0>  ->  exp(2 pi i beta / sqrt(x)) |x>|0...0>
```

| Größe | Wert |
|---|---|
| Bits je Impulskomponente `n_p` | 10 |
| Breite des Registers `x` | 22 Qubits, niedrigstes Bit zuerst |
| Wertebereich | `x` von 1 bis 3.133.452 (= 3·(2^10 − 2)²) |
| `beta` | 1 |
| Läufe | jedes `x` 64-mal, zusammen 200.540.928 |
| Bedingungen | `x` unverändert, alle anderen Qubits wieder null |

### 3.4 Fehlertoleranz

- Die Phase muss für jedes `x` höchstens `tol(x) = 2^-24 · beta / sqrt(x)` Umdrehungen vom Soll
  `beta / sqrt(x)` (modulo 1) abweichen.
- Gerechnet wird in 64-Bit-Festkomma, Einheit 2^-64 Umdrehungen. Soll und Toleranz kommen exakt
  aus `r = isqrt(floor(2^130 · beta² / x))`: Soll = `r` auf das unterste Bit gerundet, Toleranz =
  `r` um 25 Stellen nach rechts geschoben.
- Kennzahl im Ergebnis: `worst_error_over_tolerance` (9c708f7b: 0,99932; 321aff83: 0,97358).

### 3.5 Toffoli-Äquivalent und Kosten

```
Kosten = Q · C
C      = Toffolis + T / 4
```

- **Toffolis:** Mittelwert der ausgeführten `CCX`, `CCZ` und `CSWAP` pro Lauf.
- **Phasengatter `Z_POW`:** Clifford-Winkel kosten nichts, T-Winkel kosten 1 T, alle anderen
  kosten `0,56 · log2(1/eps) + 5,3` T.
- **`eps`:** Das Prüfprogramm wählt das größte `eps`, das noch passt. Die Summe
  `n_rot · 2 · eps` muss in den Rest der Toleranz passen, den der simulierte Fehler übrig lässt:
  `2 pi · min_x (tol(x) − |Fehler(x)|)`. Wer die Toleranz knapper ausschöpft, zahlt also mehr
  pro Rotation.
- **Q:** `circuit.num_qubits`.

Beispiel 321aff83: 46 Qubits, 1.511,57 Toffolis, 1 T, 33 Rotationen mit `eps` = 6,4·10^-13,
Toffoli-Äquivalent 1.742,67, Kosten 80.162,79.

---

## 4. dqi

### 4.1 Artefakte

| Was | Pfad |
|---|---|
| 892 Qubits, eingereicht (e9f54be3, 65,2264) | `work/frontier_1110/harvest_1110/tmpusp_h51n.kmb` |
| 889 Qubits (7cbe8ecf, 67,7494) | Datei `dqi.kmb` im öffentlichen Paket (Pfad siehe 3.2), 455 MB |
| Prüfergebnis 889 Qubits | `work/apex_1112/harvester/refresh_1112/verify_dqi_7cbe8ecf.json` |
| Öffentlicher Generator, Quellen | `work/apex_1112/harvester/refresh_1112/src_peek/dqi.zip` |
| Älterer öffentlicher Generator (893 Qubits, 63,14), lauffähig nachgebaut | `work/dqi_builder_repro/` |
| Bitparalleler Simulator und `.kmb`-Schreiber | `work/apex_1112/gf2-guru/zero_sim.py`, `edit_kmb.py` |
| Untersuchung der Generator-Stellschrauben | `work/apex_1112/dag-surgeon/` |

### 4.2 Reed-Solomon-Instanz

| Parameter | Wert |
|---|---|
| Körper | GF(2^12), 4.096 Elemente, `alpha = km.GF2Field(12).primitive_element` |
| Codelänge `m` | 4.095 |
| Zahl der Syndrome `n` | 70 |
| Korrigierbare Fehler `l = n // 2` | 35 |
| `r` (Zahl akzeptierter Werte) | 2.016 |
| Läufe | 102.400 |
| `log2_delta` | −128 |

Register (niedrigstes Bit zuerst, je 12 Bit, paarweise getrennt, keine weiteren erlaubt):

- `S0..S69`: Quantenregister mit den Syndromen `S_i = sum_j e_j · alpha^((i+1)·j)`.
- `E0..E4094`: klassische Register mit den Messwerten `M_j`.

Vertrag pro Lauf: Syndrome unverändert, alle anderen Qubits wieder null, globale Phase mal
`(-1)^(sum_j popcount(e_j & M_j))`. `Z_POW`-Gatter sind verboten.

Testverteilung: Fehlergewicht `k` aus 0 bis 35 mit Wahrscheinlichkeit `w_k²`, wobei `w` der
Haupteigenvektor der DQI-Matrix `A` ist (`A[k,k] = k·(q−2r)/sqrt(r·(q−r))`,
`A[k−1,k] = sqrt(k·(m−k+1))`, `q = 4096`). Dann `k` gleichverteilte Positionen mit
gleichverteilten Werten ungleich null und unabhängige, gleichverteilte `M_j`.

### 4.3 Kosten und Wiederholungsfaktor

```
Kosten     = R(eps_plus) · Q² · T
R(eps)     = ln(2) / −ln(1/2 + 2 · sqrt(eps))        für 0 <= eps < 1/16
eps_plus   = einseitige obere Clopper-Pearson-Schranke für k Fehlschüsse aus N Läufen
             bei Vertrauen 1 − 2^log2_delta
k          = value_errors + phase_errors
```

- `eps_plus >= 1/16` führt zur Ablehnung.
- `T` ist die mittlere Zahl ausgeführter Toffolis pro Lauf.
- Bei `k = 0` und 102.400 Läufen: `eps_plus` = 8,6606·10^-4, `R` = 1,1912605.
- Umsetzung: Funktionen `clopper_pearson_upper_bound` und `repetition_overhead` in
  `verify_submission_dqi.py`.
- Aus unserer Messung: Bei etwa 25 Fehlschüssen liegt `R` bei rund 1,222, also 2,6 % höher. Ein
  Fehlschuss auf 100.000 Läufe kostet damit mehr als 400 Toffolis.

---

## 5. chem

### 5.1 Artefakte

| Was | Pfad |
|---|---|
| Eingereichte Zerlegung (b0cc7e3c, 11,2224) | `work/frontier_1110/harvest_1110/chem_b0cc7e3c/submission.npz` |
| Die 15 Winkel-Schaltkreise dazu | `work/frontier_1110/harvest_1110/chem_b0cc7e3c/angle_k_0.kmb` bis `angle_k_14.kmb` |
| Winkeltabellen | in `submission.npz` enthalten (1.220 Wörter zu je 75 Bit, Form R=8, B=143, C=44); die Schaltkreise laden genau diese Wörter |
| Öffentlicher Stand (6418ec8e, 11,3122) | Dateien `dfthcsos__*` im öffentlichen Paket (Pfad siehe 3.2) |
| Prüfergebnis öffentlicher Stand | `work/apex_1112/harvester/refresh_1112/verify_chem_syed6418.json` |
| Öffentliches Compilerpaket | `work/apex_1112/harvester/refresh_1112/src_peek/dfthcsos.zip` (Compiler, Pläne je Schaltkreis, Trainings-Skripte) |
| FeMoCo-Ausgangsdaten | `data/verifiers/dfthcsos/FeMoCo76o113e.fcidump` (122 MB), `FeMoCo76o113e.fixed_shifts.npz` |
| Unser Trainer (JAX, mit Rundung im Training) | `work/chem_gpu/train_gpu.py` |
| Empfindlichkeits- und Spielraum-Messung | `work/apex_1112/chem_qrom_guru/` (`slack.py`, `sens.py`, `sens.json`) |
| Laufender Systembau (Kostenmodell, Compiler, Trainer, Pipeline) | `work/apex_chem/` — noch nicht abgenommen |
| Früherer Bericht zu kleinerem Rang | `work/chem_lower_rank/report_E.md` |

### 5.2 Kosten

```
Kosten     = lambda_eff · T_total · Q_total
lambda_eff = sqrt(E_gap · (2·Lambda − E_gap))
T_total    = Toffolis der Winkel-Schaltkreise (Mittel pro Lauf, hin und zurück)
           + äußere + innere Zustandsvorbereitung (Kostenmodell SpinFreeData_V1)
           + 2 · (N − 1) · (2·brot − 1)            Givens-Rotationen
Q_total    = dauerhafte Qubits der äußeren und inneren Vorbereitung
           + J · brot                              Winkel-Wortregister
           + max(äußerer, innerer, Winkel-Arbeitsbereich)
```

- `brot` ist die Rotationsgenauigkeit in Bit und gilt für alle Schaltkreise gemeinsam.
- Das Kostenmodell nutzt `R, B, C, N`, `chi = KEEP_BITS = 10` und `beta = brot`.
- Winkel aus Wort: `theta / pi = Wort / 2^(brot − 1)`.
- Eingereichter Stand: `lambda_eff` 46,91510, `T_total` 14.926, `Q_total` 427, `brot` 8.
- Öffentlicher Stand: `lambda_eff` 46,90735, `T_total` 14.810, `Q_total` 427, `brot` 8,
  `error_1` 19,61037 mHa, `error_2` 19,99878 mHa.

### 5.3 Die beiden Fehlermaße

Beide werden aus den Wörtern berechnet, die die Schaltkreise tatsächlich laden. Grenze jeweils
20 mHa (0,020 Hartree), Gleichheit ist erlaubt.

- **`error_1`:** Frobenius-Norm `|| sum_j lambda_j v_j v_j^T − h1_prime ||_F`. Sie misst, wie gut
  die Ein-Teilchen-Zeilen den korrigierten Ein-Teilchen-Operator `h1_prime` wiedergeben.
  `lambda_j` sind die Eigenwerte von `h1_prime`. Der Wert sinkt mit wachsendem `brot`.
- **`error_2`:** Frobenius-Norm des Zwei-Teilchen-Rests zwischen den Referenzintegralen und der
  eingereichten Zerlegung.
- Die genaue Rechenvorschrift steht im Docstring von `evaluate_words` in
  `data/verifiers/dfthcsos/verify.py` (ab Zeile 270) und in
  `data/verifiers/dfthcsos/scoreinfra/dfthc_math.py`. **Bitte von dort übernehmen, nicht aus
  dieser Zusammenfassung.**

Weitere Ablehnungsgründe:

| Bedingung | Grenze |
|---|---|
| rohes `Lambda` | muss größer als 49,0 sein |
| `E_gap` | muss größer als 3,914898 Hartree sein und im Bereich (0, 2·Lambda) liegen |
| Qubits je Winkel-Schaltkreis | höchstens 128 |
| Register-Vertrag | Schaltkreise müssen widerspruchsfreie Wörter laden |

Eingereichter Stand: `error_1` 19,99974 mHa, `error_2` 19,99997 mHa, `Lambda` 283,07, `E_gap`
5,7·10^-8 über der Untergrenze. Es gibt praktisch keinen Spielraum.

---

## 6. Offene Punkte vor Tag 1

1. **Zugang zu den Dateien.** `work/`, `runs/` und `data/` liegen nur auf dem Arbeitsrechner.
   Benötigt wird eine Entscheidung, auf welchem Weg die Kollegen sie bekommen. Ein Paket mit
   allem Genannten wäre rund 1,2 GB groß (davon dqi-Schaltkreise 0,9 GB).
2. **Logbuch.** Es liegt außerhalb des Repos und enthält auch Notizen zu anderen Themen im
   selben Speicher. Für die Weitergabe müssten nur die Notizen aus `kaggle-qvc/` kopiert werden.
3. **Öffentliche Generatoren sind ungeprüft.** Keiner der drei wurde bei uns ausgeführt. Tag 1
   prüft, ob `build.sh` die veröffentlichten Dateien bytegenau erzeugt.
4. **Salt auf Kaggle** ist nicht bekannt (siehe 2.2).
5. **Nennung der Quelle.** Das öffentliche Paket steht unter Apache-2.0; der Autor bittet um
   Nennung „lineage starting from Syed Asad Ali“, wenn darauf aufgebaut wird.
