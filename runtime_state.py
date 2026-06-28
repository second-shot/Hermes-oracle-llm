from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

if os.name == "nt":
    import msvcrt
else:
    import fcntl


MIGRATION_VERSION = 1
LEGACY_MAPPINGS = {
    Path("memory/structured.json"): Path("memory/structured.json"),
    Path("memory/logs.md"): Path("logs/sessions.md"),
    Path("data/employee"): Path("employee"),
    Path("data/security"): Path("security"),
    Path("data/sources"): Path("sources"),
}
REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)(authorization\s*:\s*bearer\s+)([^\s]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)\b(api[_-]?key|password|secret|token)\b(\s*[:=]\s*)([^\s'\",]+)"), r"\1\2[REDACTED]"),
    (re.compile(r"(?i)(['\"]?(?:api[_-]?key|password|secret|token)['\"]?\s*[:=]\s*['\"])([^'\"]+)(['\"])"), r"\1[REDACTED]\3"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), "[REDACTED]"),
)


@dataclass(frozen=True)
class RuntimeStatePaths:
    data_root: Path
    memory_dir: Path
    employee_dir: Path
    security_dir: Path
    sources_dir: Path
    logs_dir: Path
    migration_path: Path


def resolve_data_root(
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    values = os.environ if env is None else env
    if values.get("HERMES_DATA_DIR"):
        return Path(values["HERMES_DATA_DIR"]).expanduser().resolve()
    if values.get("LOCALAPPDATA"):
        return (Path(values["LOCALAPPDATA"]) / "Hermes").resolve()
    base = Path.home() if home is None else Path(home)
    return (base / ".local" / "share" / "Hermes").resolve()


def redact_text(value: str) -> str:
    text = value
    for pattern, replacement in REDACTION_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(temp_path, path)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


def atomic_write_json(path: Path, data: Any) -> None:
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def append_text(path: Path, text: str, *, redact: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    payload = redact_text(text) if redact else text
    atomic_write_text(path, existing + payload)


@contextmanager
def _exclusive_lock(path: Path) -> Iterable[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if os.name == "nt":
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _copy_file_if_missing(source: Path, destination: Path) -> str:
    if destination.exists():
        return "destination_exists"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=destination.parent, prefix=destination.name + ".", suffix=".tmp", delete=False) as handle:
            handle.write(source.read_bytes())
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(temp_path, destination)
        return "copied"
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


def _iter_legacy_files(source: Path, destination: Path) -> Iterable[tuple[Path, Path]]:
    if source.is_file():
        yield source, destination
        return
    if source.is_dir():
        for path in sorted(source.rglob("*")):
            if path.is_file():
                yield path, destination / path.relative_to(source)


def migrate_legacy_state(legacy_root: Path, data_root: Path) -> None:
    data_root.mkdir(parents=True, exist_ok=True)
    marker_path = data_root / "migration.json"
    lock_path = data_root / "migration.lock"
    with _exclusive_lock(lock_path):
        if marker_path.exists():
            try:
                marker = json.loads(marker_path.read_text(encoding="utf-8"))
                if marker.get("version") == MIGRATION_VERSION:
                    return
            except json.JSONDecodeError:
                pass

        results: list[dict[str, str]] = []
        for legacy_relative, runtime_relative in LEGACY_MAPPINGS.items():
            source_root = legacy_root / legacy_relative
            destination_root = data_root / runtime_relative
            if not source_root.exists():
                continue
            for source, destination in _iter_legacy_files(source_root, destination_root):
                status = _copy_file_if_missing(source, destination)
                results.append(
                    {
                        "source": str(source.relative_to(legacy_root)).replace("\\", "/"),
                        "destination": str(destination.relative_to(data_root)).replace("\\", "/"),
                        "status": status,
                    }
                )

        atomic_write_json(
            marker_path,
            {
                "version": MIGRATION_VERSION,
                "migrated_at": datetime.now(timezone.utc).isoformat(),
                "source_root": str(legacy_root.resolve()),
                "results": results,
            },
        )


def ensure_runtime_state(
    repository_root: Path,
    env: Mapping[str, str] | None = None,
) -> RuntimeStatePaths:
    data_root = resolve_data_root(env=env)
    migrate_legacy_state(repository_root, data_root)
    paths = RuntimeStatePaths(
        data_root=data_root,
        memory_dir=data_root / "memory",
        employee_dir=data_root / "employee",
        security_dir=data_root / "security",
        sources_dir=data_root / "sources",
        logs_dir=data_root / "logs",
        migration_path=data_root / "migration.json",
    )
    for path in (
        paths.data_root,
        paths.memory_dir,
        paths.employee_dir,
        paths.security_dir,
        paths.sources_dir,
        paths.logs_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
    return paths
