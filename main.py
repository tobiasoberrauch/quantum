"""Einstiegspunkt des kickmix-Optimierers; die Logik steht im Paket `kmx`
(gleichwertig: python -m kmx).

Aufrufformen und Optionen: python main.py --help
"""

import sys

from kmx.cli import main

if __name__ == "__main__":
    sys.exit(main())
