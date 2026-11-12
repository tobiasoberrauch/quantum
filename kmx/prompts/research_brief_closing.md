
## Bereits automatisch erledigt
Kommutierende Auslöschung; Entfernen nie feuernder oder linear ausdrückbarer Toffolis auf der ganzen Domäne; Zusammenfassen von Toffoli-Gruppen mit Rang <= 1; Measurement-Based Uncomputation für reversible Uncompute-Ketten; optimale Drahtzuteilung bei fester Gatterreihenfolge.

## Fragen an die Recherche
1. Welche Konstruktionen senken die Toffoli-Zahl der teuersten Abschnitte oben strukturell (Addierer, Multiplizierer, Quadrierer, Tabellen-Lookup/QROM, Vergleicher, Schiebenetze)? Bitte mit Toffoli- und Ancilla-Formeln.
2. Welche Tricks nutzen die Mittelwert-Bewertung aus (klassisch bedingte Arbeit, datenabhängiges Überspringen)?
3. Wie lässt sich die Scratch-Spitze senken (Pebbling, Compute/Uncompute-Reihenfolge, Wiederverwendung über HMR)?
4. Welche Genauigkeits- und Trunkierungsreserven sind bei dieser Aufgabe üblich, und wie prüft man sie exakt?
5. Welche öffentlichen Lösungen oder Notebooks zu diesem Wettbewerb beschreiben konkrete Architekturen und Zahlen?

## Gewünschtes Ergebnisformat (Playbook)
Liste von Hypothesen. Je Hypothese: Idee in einem Satz; erwarteter Gewinn in Toffoli oder Qubits; betroffener Abschnitt; Rezept in kickmix-Instruktionen (X, CX, CCX, CSWAP, Z, CZ, CCZ, HMR, R, if bN); woran man erkennt, dass es nicht passt; Quelle.
Speichere das Ergebnis als Textdatei und gib es dem Agenten mit --playbook mit.
