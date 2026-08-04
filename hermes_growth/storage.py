from __future__ import annotations

import errno
import json
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()
_LOCK_DEPTH = threading.local()


def _thread_lock(key: str) -> threading.RLock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


def _is_windows_lock_contention(exc: OSError) -> bool:
    return exc.errno in {errno.EACCES, errno.EAGAIN} or getattr(exc, "winerror", None) in {
        32,
        33,
    }


def _acquire_windows_lock(
    handle: Any,
    *,
    locking: Any,
    lock_mode: int,
    timeout: float = 10.0,
    retry_interval: float = 0.01,
    monotonic: Any = time.monotonic,
    sleeper: Any = time.sleep,
) -> None:
    deadline = monotonic() + timeout
    while True:
        try:
            locking(handle.fileno(), lock_mode, 1)
            return
        except OSError as exc:
            if not _is_windows_lock_contention(exc):
                raise
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError("timed out acquiring growth lock") from exc
            sleeper(min(retry_interval, remaining))


def _lock_file(handle: Any) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        _acquire_windows_lock(
            handle,
            locking=msvcrt.locking,
            lock_mode=msvcrt.LK_NBLCK,
        )
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _unlock_file(handle: Any) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def growth_lock(root: str | Path) -> Iterator[None]:
    directory = Path(root)
    directory.mkdir(parents=True, exist_ok=True)
    key = str(directory.resolve())
    lock = _thread_lock(key)
    with lock:
        depths = getattr(_LOCK_DEPTH, "values", None)
        if depths is None:
            depths = {}
            _LOCK_DEPTH.values = depths
        if depths.get(key, 0):
            depths[key] += 1
            try:
                yield
            finally:
                depths[key] -= 1
            return

        lock_path = directory / ".growth.lock"
        with lock_path.open("a+b") as handle:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
                os.fsync(handle.fileno())
            _lock_file(handle)
            depths[key] = 1
            try:
                yield
            finally:
                depths.pop(key, None)
                _unlock_file(handle)


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    encoded = (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")
    with growth_lock(path.parent):
        with path.open("ab", buffering=0) as handle:
            view = memoryview(encoded)
            while view:
                written = handle.write(view)
                if not written:
                    raise OSError(f"failed to append growth record: {path}")
                view = view[written:]
            handle.flush()
            os.fsync(handle.fileno())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with growth_lock(path.parent):
        if not path.exists():
            return []
        return [
            json.loads(line)
            for line in path.read_bytes().splitlines()
            if line.strip()
        ]


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    encoded = json.dumps(value, indent=2, sort_keys=True).encode("utf-8")
    with growth_lock(path.parent):
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f"{path.stem}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
