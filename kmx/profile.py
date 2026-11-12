"""Toffoli-Profil eines Schaltkreises entlang seiner INFO_TAG-Segmente (@enter/@exit)
oder, ohne Tags, in gleich großen Abschnitten."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypedDict

from kmx.ops import TOFFOLI_LIKE, Op

SEGMENT_ENTER_TAG = "@enter:"
SEGMENT_EXIT_TAG = "@exit:"
PROFILE_CHUNK_COUNT = 20  # ohne Tags: Profil in so vielen gleich großen Abschnitten
# mit Tags: so viele Ebenen des @enter-Pfads bilden den Segmentnamen
PROFILE_PATH_DEPTH = 2
PROFILE_DEFAULT_ROWS = 40
PROFILE_ROWS_SHOWN = 25  # Zeilen des Toffoli-Profils im Research-Brief und in `info`
TOP_LEVEL_SEGMENT = "(oberste Ebene)"
UNKNOWN_SEGMENT = "(unbekannt)"


class ProfileRow(TypedDict):
    """Eine Zeile des Profils (die Schlüssel gehen so auch an das Modell)."""

    segment: str
    toffoli: int
    instruktionen: int
    von: int
    bis: int


def follow_segment_tag(path: list[str], tag_op: Op) -> None:
    """Führt den @enter/@exit-Pfad über eine INFO_TAG-Instruktion (mit Text) fort."""
    tag = tag_op.text.strip('"')
    if tag.startswith(SEGMENT_ENTER_TAG):
        path.append(tag[len(SEGMENT_ENTER_TAG) :])
    elif tag.startswith(SEGMENT_EXIT_TAG) and path:
        path.pop()


def segment_path_at(ops: Sequence[Op], idx: int) -> str:
    """Voller @enter-Pfad, in dem Instruktion `idx` liegt."""
    path: list[str] = []
    for o in ops[:idx]:
        if o.name == "INFO_TAG" and o.text:
            follow_segment_tag(path, o)
    return "/".join(path) or UNKNOWN_SEGMENT


def profile_segments(
    ops: Sequence[Op], max_rows: int = PROFILE_DEFAULT_ROWS
) -> list[ProfileRow]:
    """Toffoli-Profil entlang der INFO_TAG-Struktur (@enter/@exit); ohne Tags in
    gleich großen Abschnitten. Teuerste Segmente zuerst."""
    rows: dict[str, ProfileRow] = {}
    path: list[str] = []
    tagged = any(
        o.name == "INFO_TAG" and o.text and SEGMENT_ENTER_TAG in o.text for o in ops
    )
    chunk = max(1, len(ops) // PROFILE_CHUNK_COUNT)
    for i, o in enumerate(ops):
        if o.name == "INFO_TAG" and o.text:
            follow_segment_tag(path, o)
            continue
        if tagged:
            key = "/".join(path[:PROFILE_PATH_DEPTH]) or TOP_LEVEL_SEGMENT
        else:
            first = i // chunk * chunk
            key = f"idx {first}..{min(len(ops), first + chunk) - 1}"
        row = rows.setdefault(
            key, {"segment": key, "toffoli": 0, "instruktionen": 0, "von": i, "bis": i}
        )
        row["toffoli"] += o.name in TOFFOLI_LIKE
        row["instruktionen"] += 1
        row["bis"] = i
    ranked = sorted(rows.values(), key=lambda row: -row["toffoli"])
    return ranked[:max_rows]
