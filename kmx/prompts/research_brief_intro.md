# Research-Auftrag: kickmix-Schaltkreis weiter verkleinern

## Aufgabe und Bewertung
Wettbewerb: Google Quantum AI - Verifiable Quantum Circuit Compilation (Kaggle), Paper arXiv:2610.23832.
Score S = Q x (Toffoli + T/4), kleiner ist besser. Q = größter Qubit-Index + 1. Toffoli = CCX/CCZ/CSWAP im Mittel pro Shot (klassisch bedingte Gatter zählen nur bei Ausführung). CX, CZ, X, Z, SWAP, HMR sind frei. Feine Z_POW-Rotationen kosten 0.56*log2(1/eps)+5.3 T.
