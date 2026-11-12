"""`python -m kmx ...`: gleichwertig zu `python main.py ...`."""

import sys

from kmx.cli import main

if __name__ == "__main__":
    sys.exit(main(prog="python -m kmx"))
