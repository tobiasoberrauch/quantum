"""Runner ohne pytest: `python -m tests.kmx [--bugs] [Begriff ...]`.

Sammelt die Funktionen test_* (mit --bugs auch bug_*) aller Module tests/kmx/test_*.py
in Datei- und Definitionsreihenfolge und führt sie mit eingefangener Ausgabe aus.
Exit-Code 1, sobald ein Test fehlschlägt.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import pkgutil
import sys
import time
from collections.abc import Callable
from pathlib import Path

PACKAGE = "tests.kmx"
FAILURE_NOTE_CHARS = 300

TestCase = tuple[str, Callable[[], object]]


def collect(prefix: str, filters: list[str]) -> list[TestCase]:
    """Alle Funktionen `prefix*` der Testmodule, deren Name einen der Filter enthält."""
    cases: list[TestCase] = []
    names = sorted(
        info.name
        for info in pkgutil.iter_modules([str(Path(__file__).parent)])
        if info.name.startswith("test_")
    )
    for name in names:
        if filters and not any(f in name for f in filters):
            continue
        module = importlib.import_module(f"{PACKAGE}.{name}")
        cases += [
            (f"{name}.{attr}", fn)
            for attr, fn in vars(module).items()
            if attr.startswith(prefix) and callable(fn)
        ]
    return cases


def run_case(name: str, fn: Callable[[], object]) -> tuple[str, str]:
    """Führt einen Test aus; Rückgabe (Status, Anmerkung)."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            fn()
    # auch SystemExit aus argparse soll als Fehlschlag zählen
    except BaseException as e:
        if isinstance(e, KeyboardInterrupt):
            raise
        status = "BUG?" if name.split(".")[-1].startswith("bug_") else "FAIL"
        return status, f"  {type(e).__name__}: {str(e)[:FAILURE_NOTE_CHARS]}"
    return "PASS", ""


def main(argv: list[str]) -> int:
    include_bugs = "--bugs" in argv
    filters = [a for a in argv if not a.startswith("--")]
    tests = collect("test_", filters)
    bugs = collect("bug_", filters) if include_bugs else []
    failed, t_all = 0, time.time()
    for name, fn in tests + bugs:
        t0 = time.time()
        status, note = run_case(name, fn)
        failed += status == "FAIL"
        print(f"{status} {name} ({time.time() - t0:.2f}s){note}")
    print(
        f"{len(tests) - failed}/{len(tests)} Tests bestanden in "
        f"{time.time() - t_all:.1f}s"
        + (f" | {len(bugs)} BUG?-Fälle zusätzlich ausgeführt" if bugs else "")
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
