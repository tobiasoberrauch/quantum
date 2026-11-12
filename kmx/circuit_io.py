"""Lesen und Schreiben von Schaltkreisen (.kmx als Text, .kmb über kickmix) und
atomares Schreiben von Textdateien.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from collections.abc import Sequence

from kmx._optional import kickmix
from kmx.ops import KmxError, Op, format_ops, parse_text

KMB_SUFFIX = ".kmb"
KMB_NEEDS_KICKMIX = (
    "Das Binärformat .kmb braucht die kickmix-Bibliothek (pip install kickmix)."
)


def _require_kickmix_for_kmb() -> None:
    if kickmix is None:
        raise KmxError(KMB_NEEDS_KICKMIX)


def read_circuit(path: str) -> list[Op]:
    """Liest einen Schaltkreis: .kmx als Text, .kmb über die kickmix-Bibliothek."""
    if path.lower().endswith(KMB_SUFFIX):
        _require_kickmix_for_kmb()
        return parse_text(str(kickmix.Circuit.from_file(path, format="kmb")))
    with open(path, encoding="utf-8") as f:
        return parse_text(f.read())


def write_circuit(path: str, ops: Sequence[Op]) -> None:
    """Schreibt einen Schaltkreis: .kmx als Text, .kmb über die kickmix-Bibliothek."""
    if path.lower().endswith(KMB_SUFFIX):
        _require_kickmix_for_kmb()
        kickmix.Circuit(format_ops(ops)).to_file(path, format="kmb")
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(format_ops(ops))


def unlink_if_present(path: str) -> None:
    """Löscht `path`, falls vorhanden (Aufräumen nach Abbruch, Fehler egal)."""
    with contextlib.suppress(OSError):
        os.unlink(path)


def apply_default_mode(path: str) -> None:
    """mkstemp erzeugt Dateien mit 0600; Ausgaben sollen wie mit open() angelegt
    lesbar sein (0666 & ~umask)."""
    umask = os.umask(0)
    os.umask(umask)
    os.chmod(path, 0o666 & ~umask)


def atomic_write_text(path: str, text: str) -> None:
    """Schreibt `text` erst in eine Temporärdatei im Zielverzeichnis und
    ersetzt das Ziel dann atomar."""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".kmx-write-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        apply_default_mode(tmp)
        os.replace(tmp, path)
    except BaseException:
        unlink_if_present(tmp)
        raise
