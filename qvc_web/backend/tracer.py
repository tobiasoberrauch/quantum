"""Thread-safe ring buffers for live model-call tracing and log capture."""
from __future__ import annotations

import logging
import threading


class RingBuffer:
    """Bounded, thread-safe FIFO of arbitrary records."""

    def __init__(self, maxlen: int = 4000) -> None:
        self._lock = threading.Lock()
        self._items: list = []
        self._maxlen = max(1, int(maxlen))

    def append(self, item) -> None:
        with self._lock:
            self._items.append(item)
            if len(self._items) > self._maxlen:
                del self._items[: len(self._items) - self._maxlen]

    def snapshot(self) -> list:
        with self._lock:
            return list(self._items)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


TRACE = RingBuffer()  # one record per call_models invocation
LOGS = RingBuffer()   # one record per captured log line


class _LogCapture(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            LOGS.append({"ts": round(record.created, 3),
                         "level": record.levelname,
                         "msg": record.getMessage()})
        except Exception:  # never let logging break a run
            pass


def install_log_capture(logger_name: str = "qvc") -> None:
    """Attach a capturing handler to the named logger exactly once."""
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    if not any(isinstance(h, _LogCapture) for h in logger.handlers):
        logger.addHandler(_LogCapture())
