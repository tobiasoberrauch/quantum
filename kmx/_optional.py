"""Optionale Abhängigkeiten an EINER Stelle: kickmix (Gegenprüfung, .kmb) und numpy
(exakter invsqrt-Score). Fehlt eine Bibliothek, ist der Name None.
"""

# Bewusst `Exception` statt ImportError: auch eine kaputte Installation (Fehler beim
# Import selbst) soll auf den Pfad ohne die Bibliothek zurückfallen statt den
# Optimierer abzubrechen; die Ausgabe sagt dann, dass geschätzt bzw. übersprungen wird.
try:
    import kickmix
except Exception:  # noqa: BLE001
    kickmix = None

try:
    import numpy as np
except Exception:  # noqa: BLE001
    np = None
