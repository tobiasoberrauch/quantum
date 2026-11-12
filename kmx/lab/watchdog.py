"""Wächter für einen Generatorprozess: Wanduhr, Speicher und Plattenplatz.

macOS ignoriert RLIMIT_AS, und RLIMIT_FSIZE begrenzt nur die einzelne Datei. Der
Elternprozess fragt deshalb in kurzen Abständen den physischen Speicher des Prozesses
(`proc_pid_rusage`, phys_footprint) und die belegten Blöcke des Arbeitsverzeichnisses
ab und beendet die ganze Prozessgruppe bei Überschreitung.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import signal
import subprocess
import time
from dataclasses import dataclass

POLL_S = 0.05
STOP_TIMEOUT, STOP_MEMORY, STOP_DISK, STOP_FILES = "timeout", "memory", "disk", "files"
_RUSAGE_INFO_V0 = 0
_BLOCK = 512  # Einheit von st_blocks


class _RusageInfoV0(ctypes.Structure):
    _fields_ = [
        ("uuid", ctypes.c_uint8 * 16),
        ("user_time", ctypes.c_uint64),
        ("system_time", ctypes.c_uint64),
        ("pkg_idle_wkups", ctypes.c_uint64),
        ("interrupt_wkups", ctypes.c_uint64),
        ("pageins", ctypes.c_uint64),
        ("wired_size", ctypes.c_uint64),
        ("resident_size", ctypes.c_uint64),
        ("phys_footprint", ctypes.c_uint64),
        ("proc_start_abstime", ctypes.c_uint64),
        ("proc_exit_abstime", ctypes.c_uint64),
    ]


def _libproc() -> ctypes.CDLL | None:
    path = ctypes.util.find_library("proc") or "/usr/lib/libproc.dylib"
    try:
        return ctypes.CDLL(path)
    except OSError:
        return None


_LIBPROC = _libproc()


def memory_bytes(pid: int) -> int | None:
    """Physischer Speicher (phys_footprint, sonst RSS) des Prozesses oder None."""
    if _LIBPROC is not None:
        info = _RusageInfoV0()
        rc = _LIBPROC.proc_pid_rusage(pid, _RUSAGE_INFO_V0, ctypes.byref(info))
        if rc == 0:
            return max(info.phys_footprint, info.resident_size)
    try:
        out = subprocess.run(
            ["/bin/ps", "-o", "rss=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return int(out) * 1024 if out.isdigit() else None


def disk_usage(root: str, max_entries: int) -> tuple[int, int]:
    """(belegte Bytes, Einträge) unter `root`, ohne Symlinks zu folgen; zählt
    höchstens `max_entries` + 1 Einträge."""
    total, count, stack = 0, 0, [root]
    while stack and count <= max_entries:
        try:
            with os.scandir(stack.pop()) as it:
                for entry in it:
                    count += 1
                    try:
                        st = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    total += st.st_blocks * _BLOCK
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(entry.path)
        except OSError:
            continue
    return total, count


@dataclass(frozen=True)
class Budget:
    timeout_s: float
    memory_bytes: int
    disk_bytes: int
    max_files: int


def _over_budget(pid: int, work_dir: str, budget: Budget) -> str:
    mem = memory_bytes(pid)
    if mem is not None and mem > budget.memory_bytes:
        return STOP_MEMORY
    used, entries = disk_usage(work_dir, budget.max_files)
    if entries > budget.max_files:
        return STOP_FILES
    return STOP_DISK if used > budget.disk_bytes else ""


def _kill_group(proc: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        proc.kill()
    proc.wait()


def watch(
    proc: subprocess.Popen[bytes], work_dir: str, budget: Budget
) -> tuple[int | None, str]:
    """Wartet auf den Prozess; (Exit-Code, Abbruchgrund oder '')."""
    deadline = time.monotonic() + budget.timeout_s
    while True:
        try:
            return proc.wait(timeout=POLL_S), ""
        except subprocess.TimeoutExpired:
            pass
        reason = _over_budget(proc.pid, work_dir, budget)
        if not reason and time.monotonic() >= deadline:
            reason = STOP_TIMEOUT
        if reason:
            _kill_group(proc)
            return None, reason
