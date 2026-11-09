"""Loop log + agent-memory notes for the qvc_agent loop.

This module is standalone: it does NOT import :mod:`qvc_agent.client`,
:mod:`qvc_agent.proposal`, or :mod:`qvc_discovery`.

Two concerns live here:

* A per-run JSONL *loop log* (:func:`append_loop_log` / :func:`read_loop_log`)
  that records one line per round of the agent loop.
* Dated *agent-memory* notes (:func:`write_memory_note` / :func:`load_memory`)
  stored under :data:`AGENT_MEMORY_QVC`, so later runs can read back what worked
  and what did not.

Nothing here ever writes a secret to disk.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

AGENT_MEMORY_QVC = Path.home() / ".agent-memory" / "kaggle-qvc"


def _clean(value: Any) -> str:
    """Normalize a possibly-None value to a stripped string ('' for None/blank)."""
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return value.strip()


def _resolve_dir(value: Any) -> Optional[Path]:
    """Resolve a path argument to a Path, or None when it is unusable (None/blank)."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return Path(s).expanduser()


def append_loop_log(run_dir: Any, record: Any) -> None:
    """Append ``record`` as one JSON line to ``run_dir/loop.jsonl``.

    Creates ``run_dir`` if it does not exist. Raises ``ValueError`` when
    ``run_dir`` or ``record`` is missing/blank, since a silently dropped write
    would lose loop state.
    """
    rd = _resolve_dir(run_dir)
    if rd is None:
        raise ValueError("run_dir is required")
    if record is None:
        raise ValueError("record must not be None")
    rd.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False)
    with open(rd / "loop.jsonl", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_loop_log(run_dir: Any) -> List[Dict[str, Any]]:
    """Read ``run_dir/loop.jsonl`` into a list of dicts, in file order.

    Blank lines are skipped; a missing file or directory yields ``[]``.
    """
    rd = _resolve_dir(run_dir)
    if rd is None:
        return []
    p = rd / "loop.jsonl"
    if not p.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    with open(p, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            rows.append(obj)
    return rows


def load_memory(task: Any, base: Any = AGENT_MEMORY_QVC) -> str:
    """Concatenate the contents of every ``base/*.md`` whose name contains ``task``.

    Returns ``""`` when there is nothing to read. An empty/blank ``task`` matches
    nothing (guards against the empty-substring case matching every file).
    """
    t = _clean(task)
    if not t:
        return ""
    b = _resolve_dir(base)
    if b is None:
        b = AGENT_MEMORY_QVC
    if not b.is_dir():
        return ""
    parts: List[str] = []
    for p in sorted(b.glob("*.md")):
        if t in p.name:
            try:
                parts.append(p.read_text(encoding="utf-8"))
            except OSError:
                continue
    return "".join(parts)


def write_memory_note(
    task: Any,
    summary: Any,
    base: Any = AGENT_MEMORY_QVC,
    date: Optional[str] = None,
) -> Path:
    """Write/append a dated note for ``task`` under ``base`` and return its path.

    Creates ``base`` if it does not exist (the loop may pass a fresh
    ``memory_base``). The file is named ``{date}-agent-loop-{task}.md``; ``date``
    defaults to today (``YYYY-MM-DD``). A new file gets a ``# Agent-Loop <task>``
    header; an existing file gets a new dated section appended. ``summary`` is
    written verbatim. Raises ``ValueError`` when ``task`` is missing/blank.
    """
    t = _clean(task)
    if not t:
        raise ValueError("task is required")
    d = _clean(date)
    if not d:
        d = datetime.date.today().isoformat()
    b = _resolve_dir(base)
    if b is None:
        b = AGENT_MEMORY_QVC
    b.mkdir(parents=True, exist_ok=True)

    summary_text = "" if summary is None else str(summary)
    section = f"## {d}\n\n{summary_text}\n"

    path = b / f"{d}-agent-loop-{t}.md"
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing and not existing.endswith("\n"):
            existing += "\n"
        path.write_text(existing + "\n" + section, encoding="utf-8")
    else:
        path.write_text(f"# Agent-Loop {t}\n\n{section}", encoding="utf-8")
    return path
