"""Curate materialization for the qvc_agent loop.

The *curate* path lets the agent ADOPT an already-verified public circuit: it
reads the ranked-candidate list and extracts the chosen ``.kmb`` from its
locator (zip / xz / plain file) into a fresh artifact dir, verifying the SHA-256
matches before returning the path.

The locator open/write logic mirrors ``work/frontier_1109/scripts/verify_one.py``
(``open_loc`` / ``write_loc``). This module is standalone: it does not import
:mod:`qvc_agent.client`, :mod:`qvc_agent.proposal`, or :mod:`qvc_discovery`.
"""
from __future__ import annotations

import hashlib
import json
import lzma
import zipfile
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parents[1]

CANDIDATES_RANKED = REPO / "work" / "frontier_1109" / "candidates_ranked.json"
CANDIDATES = REPO / "work" / "frontier_1109" / "candidates.json"


def load_candidates(task: str, path: Path = CANDIDATES_RANKED) -> List[Dict[str, Any]]:
    """Return the ranked-candidate list for ``task`` from ``path``.

    ``path`` is a JSON object mapping component name to a list of candidate
    dicts; this returns ``json.loads(path.read_text())[task]``. A missing task
    raises ``KeyError`` (the caller decides how to react).
    """
    return json.loads(path.read_text())[task]


def _open_loc(loc: Dict[str, Any]):
    """Open the source stream for a locator (zip member or plain file).

    When ``loc["inner"]`` is not ``None`` the source is a zip member opened via
    :func:`zipfile.ZipFile.open`; otherwise it is the plain file at
    ``loc["path"]``. If ``loc["xz"]`` is truthy the stream is additionally
    wrapped with :func:`lzma.open`. The returned object is a binary reader that
    the caller must close.
    """
    if loc["inner"] is not None:
        raw = zipfile.ZipFile(loc["path"]).open(loc["inner"])
    else:
        raw = open(loc["path"], "rb")
    return lzma.open(raw) if loc["xz"] else raw


def _write_loc(loc: Dict[str, Any], dst: Path, want_sha: str) -> None:
    """Stream the locator at ``loc`` into ``dst``, verifying its SHA-256.

    Chunks are read, written, and fed to a running SHA-256 hash. After writing,
    if the computed digest differs from ``want_sha`` a ``RuntimeError`` is
    raised (the partially-written ``dst`` is left in place for inspection).
    """
    h = hashlib.sha256()
    with _open_loc(loc) as fi, open(dst, "wb") as fo:
        while True:
            b = fi.read(1 << 22)
            if not b:
                break
            h.update(b)
            fo.write(b)
    if h.hexdigest() != want_sha:
        raise RuntimeError(f"sha mismatch {dst}: {h.hexdigest()} != {want_sha}")


def materialize(
    proposal: Dict[str, Any],
    out_dir: Path,
    *,
    comp: str = "invsqrt",
    candidates_path: Path = CANDIDATES,
) -> Path:
    """Materialize the artifact referenced by ``proposal`` into ``out_dir``.

    Looks up ``proposal["artifact_ref"]`` (a SHA-256) in
    ``candidates_path[comp]`` and writes the first locator's bytes to
    ``out_dir/{comp}.{ext}`` (default ext ``kmb``), verifying the SHA-256.
    Returns the destination path. Raises ``KeyError`` when the SHA is not a
    known candidate and ``RuntimeError`` on a SHA mismatch.
    """
    data = json.loads(candidates_path.read_text())[comp]
    sha = proposal["artifact_ref"]
    cand = data[sha]  # KeyError propagates when the sha is unknown
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{comp}.{cand.get('ext', 'kmb')}"
    _write_loc(cand["locs"][0], dst, sha)
    return dst
