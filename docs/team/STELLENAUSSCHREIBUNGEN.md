# Stellenausschreibungen: drei Aufgaben-Experten für die Verifiable Quantum Circuit Compilation

Stand: 13.11.2026

Wir suchen drei Fachleute, je eine Person für eine der drei Aufgaben des Kaggle-Wettbewerbs
„Google Verifiable Quantum Circuit Compilation“. Jede Person verantwortet ihre Aufgabe allein
und vollständig: vom Verständnis der Kostenformel bis zum offiziell geprüften Schaltkreis.

Offene Angaben, die vor der Veröffentlichung ergänzt werden müssen, stehen in
[eckigen Klammern].

---

## Inhalt

1. [Rahmen für alle drei Stellen](#1-rahmen-für-alle-drei-stellen)
2. [Stelle A: Reversible Arithmetik (invsqrt)](#2-stelle-a-expertein-für-reversible-arithmetik-invsqrt)
3. [Stelle B: Quanten-Fehlerkorrektur-Dekodierer (dqi)](#3-stelle-b-expertein-für-reed-solomon-dekodierung-auf-quantenschaltkreisen-dqi)
4. [Stelle C: Quantenchemie-Kompilierung (chem)](#4-stelle-c-expertein-für-quantenchemie-kompilierung-chem)
5. [Auswahlverfahren](#5-auswahlverfahren)
6. [Vergleich der drei Profile](#6-vergleich-der-drei-profile)

---

## 1. Rahmen für alle drei Stellen

### 1.1 Worum es geht

Der Wettbewerb bewertet drei Quantenschaltkreise. Jeder wird von einem offiziellen Prüfprogramm
auf Korrektheit getestet und erhält Kosten. Die Wertung ist das geometrische Mittel der drei
Verhältnisse „Referenzkosten geteilt durch eigene Kosten“. Ein Prozent Gewinn in einer Aufgabe
bringt also ein Drittel Prozent in der Gesamtwertung.

| Aufgabe | Was der Schaltkreis tut | Kostenformel | Unser Stand | Bestes öffentlich Verfügbares |
|---|---|---|---|---|
| invsqrt | Kehrwert der Quadratwurzel in Festkomma | Qubits × Toffoli-Äquivalent | 22,11 (eigener bester: 22,20) | 25,91 |
| dqi | Reed-Solomon-Dekodierung für Decoded Quantum Interferometry | Wiederholungsfaktor × Qubits² × Toffolis | 65,23 | 67,75 |
| chem | Blockkodierung des FeMoCo-Hamiltonoperators (DF-THC) | λ × Toffolis × Qubits | 11,22 | 11,31 |

Gesamtwertung eingereicht: 25,30. Spitze der Rangliste: 29,91. Ziel: 30.

### 1.2 Termine

| Termin | Datum |
|---|---|
| Meilenstein-Notebook | 20.11.2026 |
| Teamzusammenschluss und Anmeldung | 13.01.2027 |
| Letzte Einreichung | 20.01.2027 |

### 1.3 Was wir aus eigener Arbeit wissen

Diese Befunde bestimmen das Profil. Wer sich bewirbt, sollte sie kennen.

- **Feinschliff am fertigen Schaltkreis ist ausgereizt.** Wir haben auf Gatterebene nach
  einsparbaren Toffolis gesucht und bei dqi keine einzige belastbare Stelle gefunden. Ein Versuch
  mit 3.075 scheinbar sicheren Stellen fiel im Prüfprogramm mit 7.076 Wertefehlern durch.
- **Die großen Sprünge kommen aus Neukonstruktion.** Der beste öffentliche invsqrt-Schaltkreis
  braucht 46 statt 62 Qubits und nimmt dafür mehr Toffolis in Kauf. Er ist trotzdem 17 % besser.
- **Für alle drei Aufgaben gibt es seit dem 12.11.2026 öffentliche Generator-Quellen**
  (Apache-2.0). Die Arbeit beginnt also nicht bei null, sondern beim Verstehen und Übertreffen
  eines vorhandenen Generators.
- **Stichproben täuschen.** Zustände, die auf 25.000 Testläufen immer null waren, waren auf
  weiteren Läufen nicht null. Aussagen über Korrektheit brauchen einen Beweis oder die
  offizielle Prüfung.

### 1.4 Anforderungen an alle drei Personen

**Arbeitsweise**

- Vor jedem Bau eine untere Schranke und den erwarteten Gewinn ausrechnen. Ohne Rechnung kein Code.
- Jede Behauptung mit dem offiziellen Prüfprogramm belegen. „Sollte funktionieren“ zählt nicht.
- Negative Ergebnisse genauso sauber festhalten wie positive, mit Zahlen und Pfad zum Beleg.
- Selbstständig arbeiten: Aufgabe verstehen, Engpass finden, Lösung bauen, prüfen, berichten.

**Technische Grundlagen**

- Sehr gutes Python, dazu NumPy. Für große Schaltkreise zusätzlich C++ oder Rust.
- Lineare Algebra über GF(2) und das Rechnen mit Booleschen Funktionen (algebraische Normalform).
- Reversible Logik: Toffoli-, CNOT- und CSWAP-Netze, Hilfsqubits, sauberes Aufräumen.
- Messbasiertes Aufräumen: ein Hilfsqubit messen und die Phase klassisch korrigieren, statt es
  mit Toffolis zurückzurechnen.
- Git, reproduzierbare Läufe, Prüfsummen für jedes Artefakt.
- Englisch für Fachliteratur, Deutsch oder Englisch für die Zusammenarbeit.

**Werkzeuge, die alle beherrschen müssen**

| Werkzeug | Wofür |
|---|---|
| kickmix (Bibliothek des Wettbewerbs) | Schaltkreise im Format `.kmb` und `.kmx` laden, schreiben, simulieren |
| Offizielle Prüfprogramme | Korrektheit und Kosten jedes Schaltkreises |
| Eigene bitparallele Simulatoren | Viele Eingaben gleichzeitig durch einen Schaltkreis schicken |
| `kmx` (unser Optimierer und Labor) | Schaltkreis-Kennzahlen, automatische Vereinfachung, Hypothesenprüfung |
| SAT- oder SMT-Löser (zum Beispiel Z3) | Äquivalenz kleiner Teilschaltkreise beweisen |

**Zusammenarbeit mit KI-Agenten**

Wir arbeiten mit orchestrierten KI-Agenten, die Hypothesen ausrechnen, Code bauen und Ergebnisse
gegenprüfen. Wer hier arbeitet, schreibt den Agenten genaue Aufträge, prüft ihre Ergebnisse
kritisch und erkennt, wenn eine plausibel klingende Aussage falsch ist.

### 1.5 Was wir bieten

- Einen funktionierenden Unterbau: Prüf-Pipeline, Simulatoren, Ergebnis-Logbuch, Agenten-Workflows.
- Alle bisherigen Messungen und Fehlschläge dokumentiert, damit niemand dieselbe Sackgasse zweimal läuft.
- [Vergütung, Vertragsform, Umfang, Laufzeit]
- [Arbeitsort, Rechenressourcen, Ansprechperson und Bewerbungsweg]

---

## 2. Stelle A: Expert:in für reversible Arithmetik (invsqrt)

### 2.1 Die Aufgabe

Der Schaltkreis berechnet den Kehrwert der Quadratwurzel einer Festkommazahl und muss für alle
Eingaben innerhalb einer Fehlertoleranz liegen. Das Prüfprogramm testet rund 200 Millionen
Eingaben. Die Kosten sind Qubits mal Toffoli-Äquivalent; in das Toffoli-Äquivalent gehen auch
Rotationen ein.

| Kennzahl | Unser bester | Bester öffentlicher |
|---|---|---|
| Qubits | 62 | 46 |
| Mittlere Toffolis pro Durchlauf | 1.214 | 1.512 |
| Toffoli-Äquivalent | 1.509 | 1.743 |
| Ausnutzung der Fehlertoleranz | 99,93 % | 97,36 % |
| Verhältnis zur Referenz | 22,20 | 25,91 |

### 2.2 Verantwortung

- Die Rechenvorschrift selbst entwerfen: Startwert, Iterationen, Wortbreiten, Rundung.
- Den Tausch zwischen Qubits und Toffolis ausloten und das Optimum des Produkts finden.
- Die Fehlertoleranz gezielt ausschöpfen, ohne bei anderem Zufallsstartwert durchzufallen.
- Den öffentlichen Generator nachbauen, verstehen und übertreffen.

### 2.3 Fachliche Expertise

**Muss**

- Reversible Festkomma-Arithmetik: Addierer (Ripple-Carry, Carry-Lookahead), Multiplizierer,
  Quadrierer, Schieben, Normalisieren.
- Numerische Verfahren für die inverse Wurzel: Newton-Iteration, stückweise Polynome,
  Tabellen-Startwerte, und wie sich ihre Fehler durch die Iterationen fortpflanzen.
- Fehleranalyse in Festkomma: welche Bitbreite an welcher Stelle wirklich nötig ist.
- Qubit-Wiederverwendung: Lebensdauern von Hilfsqubits, Reihenfolge der Berechnung,
  Pebbling-Strategien.
- Messbasiertes Aufräumen und temporäre UND-Gatter mit halbierten Kosten.
- Tabellenzugriffe im Schaltkreis (QROM, unäre Iteration) für Startwerte und Koeffizienten.

**Erwünscht**

- Erfahrung mit Arithmetik aus der Kryptanalyse-Literatur (modulare Arithmetik für Shor,
  Fenstertechniken), weil dort dieselben Tricks entwickelt wurden.
- Synthese von Rotationen und deren Kostenabwägung gegen Toffolis.
- Hardware-Arithmetik aus dem Chipentwurf (CORDIC, Goldschmidt, Tabellen plus Interpolation).

### 2.4 Fähigkeiten

- Eine Rechenvorschrift in wenigen Stunden als reversibles Netz aufschreiben und durchzählen.
- Die schlechteste Eingabe eines Entwurfs gezielt finden, statt auf Stichproben zu hoffen.
- Einen fremden Schaltkreis mit 35.000 Operationen in Blöcke zerlegen und jeden Block benennen.
- Für eine Idee vorab sagen, wie viele Toffolis ein eingespartes Qubit höchstens kosten darf.
  Bei unserem Stand sind das rund 25 Toffolis pro Qubit.

### 2.5 Werkzeuge

| Werkzeug | Erwartung |
|---|---|
| kickmix, `.kmb`-Leser und -Schreiber | sicher |
| Bitparalleler Simulator über alle Eingaben | selbst schreiben können |
| Qualtran oder ein vergleichbares Baukasten-System für Arithmetik | Erfahrung |
| Ressourcenschätzer (zum Beispiel Azure Quantum Resource Estimator) | Grundkenntnis |
| Z3 oder ein SAT-Löser für Blockäquivalenz | Erfahrung |
| Suchverfahren über Entwurfsparameter (Gittersuche, evolutionär) | Erfahrung |

### 2.6 Lebenslauf und Erfahrung

- Studium der Informatik, Mathematik, Physik oder Elektrotechnik; Promotion oder gleichwertige
  Forschungspraxis in Quantenalgorithmen, reversibler Logik oder Rechnerarithmetik ist typisch.
- Mindestens ein eigener, veröffentlichter oder öffentlich einsehbarer reversibler
  Arithmetik-Schaltkreis mit nachvollziehbarer Ressourcenzählung.
- Alternativ: mehrere Jahre Entwurf von Arithmetik-Einheiten für Chips oder FPGAs mit
  nachweisbarem Wechsel in die reversible Welt.
- Erfahrung mit Wettbewerben oder Benchmarks, bei denen ein automatisches Prüfprogramm entscheidet.

### 2.7 Arbeitsprobe

Gegeben ist unser Schaltkreis mit 62 Qubits. Liefern Sie in fünf Arbeitstagen:

1. eine Blockzerlegung mit Qubit-Spitzenlast je Block,
2. eine begründete Schranke, wie weit die Qubit-Zahl bei dieser Rechenvorschrift sinken kann,
3. einen geprüften Schaltkreis, der besser ist als 22,20, oder eine belegte Begründung, warum
   dieser Ansatz das nicht hergibt.

### 2.8 Erfolgskriterien

| Zeitraum | Ziel |
|---|---|
| 2 Wochen | Öffentlichen Generator bytegenau nachgebaut, Kostenmodell je Baustein steht |
| 6 Wochen | Geprüfter Schaltkreis über 25,91 |
| Bis 13.01.2027 | Verhältnis 28 oder höher |

---

## 3. Stelle B: Expert:in für Reed-Solomon-Dekodierung auf Quantenschaltkreisen (dqi)

### 3.1 Die Aufgabe

Der Schaltkreis dekodiert einen Reed-Solomon-Code reversibel, als Kernstück von Decoded Quantum
Interferometry. Die Instanz arbeitet über einem Körper mit 4.096 Elementen. Der Schaltkreis hat
über 50 Millionen Operationen. Die Kosten sind Wiederholungsfaktor mal Qubits im Quadrat mal
mittlere Toffolis. Jeder Fehlschuss im Prüfprogramm erhöht den Wiederholungsfaktor.

| Kennzahl | Unser eingereichter | Bester öffentlicher |
|---|---|---|
| Qubits | 892 | 889 |
| Mittlere Toffolis | 395.305 | 383.156 |
| Operationen | 58,3 Millionen | 52,9 Millionen |
| Fehlschüsse bei 102.400 Läufen | 0 | 0 lokal, 2 in Kaggles Ziehung |
| Verhältnis zur Referenz | 65,23 | 67,75 |

Wichtig für die Abwägung: Ein Qubit ist bei unserem Stand rund 910 Toffolis wert, weil die
Qubits quadratisch eingehen. Ein einziger Fehlschuss auf 100.000 Läufe kostet mehr als 400 Toffolis.

### 3.2 Verantwortung

- Den Dekodierer als Ganzes neu durchdenken: Syndrom, Schlüsselgleichung, Fehlerorte, Fehlerwerte.
- Die Qubit-Spitzenlast senken, auch wenn das Toffolis kostet, solange die Rechnung aufgeht.
- Körperarithmetik (Multiplikation, Inversion) auf minimale Kosten trimmen.
- Deterministische Korrektheit sichern. Bausteine, die nur „fast immer“ stimmen, sind tabu.
- Bau- und Prüfzeiten bei 50 Millionen Operationen beherrschbar halten.

### 3.3 Fachliche Expertise

**Muss**

- Algebraische Kodierungstheorie: Reed-Solomon-Codes, Berlekamp-Massey, erweiterter
  euklidischer Algorithmus, Chien-Suche, Forney-Formel.
- Arithmetik in endlichen Körpern der Charakteristik 2: Polynom- und Normalbasen, Turmkörper,
  Multiplikation nach Karatsuba, Inversion nach Itoh-Tsujii und über Normen in Teilkörpern.
- Reversible Umsetzung von Algorithmen mit datenabhängigem Ablauf: Verzweigungen in
  gleichförmige, kontrollierte Schritte überführen.
- Pebbling und Speicherplanung für lange Berechnungen mit vielen Zwischenergebnissen.
- Lineare Abbildungen über GF(2) als reine CNOT-Netze erkennen und aus der Toffoli-Zählung
  herausnehmen.
- Messbasiertes Aufräumen samt sauberer Phasenbuchhaltung über Tausende klassischer Bits.

**Erwünscht**

- Kenntnis von Decoded Quantum Interferometry und der zugehörigen Ressourcenschätzungen.
- Erfahrung mit reversiblen Schaltkreisen für elliptische Kurven über binären Körpern, weil
  dort dieselbe Körperarithmetik optimiert wurde.
- Projektive oder inversionsfreie Formulierungen, die teure Inversionen vermeiden.
- Hochleistungs-Programmierung: Schaltkreise dieser Größe in Sekunden erzeugen und simulieren.

### 3.4 Fähigkeiten

- Aus der Kostenformel sofort ableiten, welcher Tausch sich lohnt und welcher nicht.
- Den Qubit-Spitzenwert eines Generators einer konkreten Stelle im Ablauf zuordnen.
- Seltene Sonderfälle (zum Beispiel ein Körperelement ist null) vollständig behandeln und beweisen.
- Einen fremden Generator ohne Dokumentation lesen und seine Stellschrauben finden.
- Für jeden Umbau vorab einen Beweis oder einen symbolischen Test planen, nicht nur Stichproben.

### 3.5 Werkzeuge

| Werkzeug | Erwartung |
|---|---|
| kickmix, `.kmb`-Schreiber mit Einfügen und Umwandeln von Operationen | sicher |
| Bitparalleler Simulator mit Bedingungsstapel und Messbits | selbst schreiben können |
| SageMath oder Magma für Körperarithmetik und Gegenrechnung | sicher |
| Symbolische Auswertung über GF(2) | Erfahrung |
| C++ oder Rust für Generator und Simulator | sicher |
| Profiler und Speicheranalyse | Erfahrung |

### 3.6 Lebenslauf und Erfahrung

- Studium der Mathematik, Informatik oder Elektrotechnik mit Schwerpunkt Kodierungstheorie,
  Kryptographie oder Computeralgebra; Promotion oder gleichwertige Forschungspraxis ist typisch.
- Nachweisbare Umsetzung eines algebraischen Dekodierers, in Hardware, Software oder reversibel.
- Mindestens ein Projekt mit Körperarithmetik unter harten Ressourcengrenzen (Chip, FPGA,
  eingebettete Kryptographie oder Quantenschaltkreis).
- Erfahrung mit sehr großen erzeugten Artefakten und automatisierten Prüfungen.

### 3.7 Arbeitsprobe

Gegeben sind der öffentliche Generator und sein Schaltkreis mit 889 Qubits. Liefern Sie in fünf
Arbeitstagen:

1. den Ablauf des Dekodierers als Blockfolge mit Qubits und Toffolis je Block,
2. die Stelle, die den Qubit-Spitzenwert bestimmt, mit Beleg,
3. einen Vorschlag mit ausgerechnetem Gewinn, der entweder mindestens 10 Qubits spart oder
   mindestens 3 % der Toffolis, samt Plan für den Korrektheitsnachweis.

### 3.8 Erfolgskriterien

| Zeitraum | Ziel |
|---|---|
| 2 Wochen | Generator bytegenau nachgebaut, Kostenaufteilung je Block steht |
| 6 Wochen | Geprüfter Schaltkreis über 70 ohne Fehlschüsse |
| Bis 13.01.2027 | Verhältnis 78 oder höher |

---

## 4. Stelle C: Expert:in für Quantenchemie-Kompilierung (chem)

### 4.1 Die Aufgabe

Eingereicht wird eine Zerlegung des FeMoCo-Hamiltonoperators (doppelt faktorisierte
Tensor-Hyperkontraktion mit Summe-von-Quadraten-Anteil) als Zahlenwerk, dazu 15 Schaltkreise, die
Winkeltabellen laden. Die Kosten sind λ mal Toffolis mal Qubits. Zwei Fehlermaße müssen jeweils
unter 20 Millihartree bleiben. Jeder Winkel-Schaltkreis darf höchstens 128 Qubits haben.

| Kennzahl | Unser eingereichter | Bester öffentlicher |
|---|---|---|
| λ | 46,915 | 46,907 |
| Toffolis | 14.926 | 14.810 |
| Qubits | 427 | 427 |
| Fehler 1 / Fehler 2 in Millihartree | 19,99974 / 19,99997 | 19,61037 / 19,99878 |
| Rotationsgenauigkeit | 8 Bit, global für alle Schaltkreise | 8 Bit |
| Verhältnis zur Referenz | 11,22 | 11,31 |

Aufteilung unserer Toffolis: rund 8.264 für das Laden der Tabellen, 4.095 für die innere
Auswahl, 2.250 für Givens-Rotationen, 317 für die äußere Auswahl.

Was wir schon gemessen haben: Die Fehlergrenze ist vollständig ausgeschöpft. Einfaches Runden
der Winkel von 8 auf 7 Bit sprengt sie um den Faktor 100. Gelingt der Schritt auf 7 Bit durch
Training bei gleichem λ, wären höchstens 9,7 % zu holen.

### 4.2 Verantwortung

- Die Zerlegung neu optimieren: Form, Rang, Gewichte, mit λ und beiden Fehlermaßen als Ziel.
- Training mit eingebauter Quantisierung aufsetzen, damit die Winkel schon beim Lernen auf dem
  Bitraster liegen.
- Den Compiler für die Winkel-Schaltkreise verbessern, weil das Laden über die Hälfte kostet.
- Die Kostenformel des Prüfprogramms vollständig nachbilden, damit jede Änderung vorab bewertbar ist.

### 4.3 Fachliche Expertise

**Muss**

- Elektronenstruktur in zweiter Quantisierung: Ein- und Zweielektronenintegrale, aktive Räume.
- Tensorzerlegungen des Coulomb-Operators: doppelte Faktorisierung, Tensor-Hyperkontraktion,
  komprimierte Varianten und ihre Wirkung auf λ.
- Qubitisierung und Blockkodierung: PREPARE und SELECT, Linearkombination unitärer Operatoren,
  warum λ die Laufzeit bestimmt.
- Kosten der Datenlader: QROM, Auswahl mit Tausch-Netz, unäre Iteration, Aufräumen per Messung.
- Givens-Rotationen für Basiswechsel und die Wirkung endlicher Winkelgenauigkeit auf den Fehler.
- Numerische Optimierung mit Nebenbedingungen und Gradienten durch nicht differenzierbare
  Rundung (Straight-Through-Schätzer).

**Erwünscht**

- Summe-von-Quadraten-Darstellungen und Spektrallücken-Verstärkung zur Senkung von λ.
- Symmetrieausnutzung und Verschiebungen des Hamiltonoperators, die λ senken, ohne das Spektrum
  zu ändern.
- Synthese Boolescher Funktionen: die Winkeltabellen als Paritäts- und affine Netze mit wenig
  Toffolis darstellen.
- Erfahrung mit FeMoCo oder ähnlich großen aktiven Räumen.

### 4.4 Fähigkeiten

- Aus einer Zerlegung die drei Faktoren der Kosten getrennt vorhersagen, bevor ein Schaltkreis
  gebaut wird.
- Erkennen, ob ein Fehlerbudget durch bessere Verteilung oder nur durch mehr Bits zu retten ist.
- Ein Training so aufsetzen, dass es auf einem Rechner ohne Grafikkarte in Stunden konvergiert.
- Tabellen mit 1.220 Wörtern zu je 75 Bit so umordnen und umkodieren, dass der Lader billiger wird.
- Zwei Compiler fair vergleichen: gleiche Eingabe, gleiche Zählweise, offizielle Prüfung.

### 4.5 Werkzeuge

| Werkzeug | Erwartung |
|---|---|
| JAX mit Optax oder PyTorch | sicher |
| PySCF, OpenFermion | sicher |
| Qualtran oder vergleichbare Bausteine für Blockkodierungen | Erfahrung |
| Offizielle Bewertungsfunktionen des Wettbewerbs für Fehler und Kosten | sicher nach Einarbeitung |
| Optimierer mit Nebenbedingungen (SQP, Barriere-Verfahren, L-BFGS) | sicher |
| kickmix für die Winkel-Schaltkreise | Erfahrung |
| Werkzeuge für Logiksynthese (zum Beispiel ABC) oder eigene Paritäts-Synthese | erwünscht |

### 4.6 Lebenslauf und Erfahrung

- Studium der Chemie, Physik oder Informatik mit Schwerpunkt Quantenchemie oder
  Quantenalgorithmen; Promotion oder gleichwertige Forschungspraxis ist typisch.
- Mindestens eine eigene Ressourcenschätzung für eine Molekül-Simulation per Qubitisierung, mit
  ausgewiesenem λ und Toffoli-Zahlen.
- Nachweisbare Erfahrung mit Tensorzerlegungen von Zweielektronenintegralen.
- Praxis im Training von Modellen mit Quantisierung oder in gemischt-ganzzahliger Optimierung.
- Erfahrung mit dem Zusammenspiel von Numerik und Schaltkreisbau, nicht nur mit einer der Seiten.

### 4.7 Arbeitsprobe

Gegeben sind unsere eingereichte Zerlegung und die öffentliche Compiler-Quelle. Liefern Sie in
fünf Arbeitstagen:

1. eine Nachbildung der Kostenformel, die unsere Kosten auf die letzte Stelle trifft,
2. eine Empfindlichkeitsanalyse: welche Parameter das Fehlerbudget am stärksten belasten,
3. eine geprüfte Einreichung besser als 11,31 oder eine belegte Schranke, warum mit dieser Form
   der Zerlegung nicht mehr geht.

### 4.8 Erfolgskriterien

| Zeitraum | Ziel |
|---|---|
| 2 Wochen | Öffentlichen Stand nachgebaut, Trainer startet von dort und hält beide Fehlergrenzen |
| 6 Wochen | Geprüfte Einreichung über 12,4 (7 Bit oder gleichwertiger Gewinn) |
| Bis 13.01.2027 | Verhältnis 14 oder höher |

---

## 5. Auswahlverfahren

| Schritt | Inhalt | Dauer |
|---|---|---|
| 1. Unterlagen | Lebenslauf, zwei eigene Arbeiten mit Zahlen (Veröffentlichung, Code oder Bericht) | – |
| 2. Fachgespräch | Kostenformel der Aufgabe erklären, einen Tausch live durchrechnen | 60 Minuten |
| 3. Arbeitsprobe | Siehe Abschnitt 2.7, 3.7 oder 4.7, vergütet | 5 Arbeitstage |
| 4. Abschlussgespräch | Ergebnis vorstellen, Fehlschläge einordnen, Plan bis Januar | 60 Minuten |

**Worauf wir in den Unterlagen achten**

- Konkrete Ressourcenzahlen aus eigener Arbeit, nicht nur Methodennamen.
- Mindestens ein ehrlich beschriebener Fehlschlag mit Ursache.
- Öffentlich einsehbarer Code oder ein nachvollziehbarer Bericht.

**Ausschlussgründe**

- Behauptungen ohne Prüfung durch das offizielle Programm.
- Ergebnisse aus fremden Quellen ohne Nennung. Öffentliche Quellen dürfen genutzt werden, die
  Herkunft muss genannt sein.

---

## 6. Vergleich der drei Profile

| | Stelle A: invsqrt | Stelle B: dqi | Stelle C: chem |
|---|---|---|---|
| Kernfach | Rechnerarithmetik, reversibel | Kodierungstheorie und Körperarithmetik | Quantenchemie und Optimierung |
| Typische Herkunft | Quantenalgorithmen, Chipentwurf | Kryptographie, Computeralgebra | Theoretische Chemie, Quantenalgorithmen |
| Größe des Schaltkreises | 35.000 Operationen | über 50 Millionen Operationen | 15 kleine Schaltkreise plus Zahlenwerk |
| Wichtigster Hebel | Qubits gegen Toffolis tauschen | Qubit-Spitzenlast senken | λ senken, Bitbreite senken, Lader verbilligen |
| Größtes Risiko | Fehlertoleranz bei anderem Zufallsstartwert | Seltene Sonderfälle, Fehlschüsse | Fehlergrenze ohne jeden Spielraum |
| Wichtigstes Werkzeug | Simulator über alle Eingaben | Computeralgebra-System | Differenzierbarer Trainer |
| Ziel bis 13.01.2027 | 28 | 78 | 14 |

Die drei Ziele zusammen ergeben eine Gesamtwertung von rund 31,3. Bleibt eine Aufgabe auf dem
heutigen öffentlichen Stand, sieht es so aus:

| Auf öffentlichem Stand bleibt | Gesamtwertung |
|---|---|
| invsqrt (25,91) | 30,5 |
| dqi (67,75) | 29,8 |
| chem (11,31) | 29,1 |

Für 30 müssen also dqi und chem ihre Ziele erreichen; invsqrt allein darf stehen bleiben.
