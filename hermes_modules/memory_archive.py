from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


RECORD_KINDS = {"project", "person", "entity", "decision", "task", "inventory", "note"}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\b(?:api[_-]?key|password|token|client[_-]?secret)\s*[:=]\s*\S+"),
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def default_database_path() -> Path:
    root = Path(os.environ.get("HERMES_DATA_DIR", Path.home() / ".hermes"))
    return root / "memory" / "archive.sqlite3"


@dataclass(frozen=True)
class ImportPreview:
    source_path: str
    source_type: str
    source_hash: str
    records: tuple[dict[str, Any], ...]
    duplicates: int
    rejected_sensitive: int

    def summary(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "source_type": self.source_type,
            "candidate_records": len(self.records),
            "duplicates": self.duplicates,
            "rejected_sensitive": self.rejected_sensitive,
            "commit_required": True,
        }


class MemoryArchive:
    """Provenance-preserving local memory with explicit two-step imports."""

    def __init__(self, database: str | Path | None = None) -> None:
        self.database = Path(database) if database else default_database_path()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.database)
        self.connection.row_factory = sqlite3.Row
        self._initialize()

    def close(self) -> None:
        self.connection.close()

    def _initialize(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS memory_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_hash TEXT NOT NULL UNIQUE,
                imported_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memory_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL REFERENCES memory_sources(id),
                kind TEXT NOT NULL,
                project TEXT NOT NULL DEFAULT '',
                entity TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 1,
                source_timestamp TEXT,
                content_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                deleted_at TEXT
            );
            CREATE INDEX IF NOT EXISTS memory_project_idx
                ON memory_records(project, kind, deleted_at);
            """
        )
        self.connection.commit()

    @staticmethod
    def _contains_sensitive(value: str) -> bool:
        return any(pattern.search(value) for pattern in SECRET_PATTERNS)

    @staticmethod
    def _normalize(record: dict[str, Any], fallback_title: str) -> dict[str, Any]:
        content = str(record.get("content", record.get("text", ""))).strip()
        if not content:
            raise ValueError("memory content is required")
        kind = str(record.get("kind", record.get("type", "note"))).lower()
        if kind not in RECORD_KINDS:
            kind = "note"
        confidence = float(record.get("confidence", 1))
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        return {
            "kind": kind,
            "project": str(record.get("project", "")).strip(),
            "entity": str(record.get("entity", "")).strip(),
            "title": str(record.get("title", fallback_title)).strip() or fallback_title,
            "content": content,
            "summary": str(record.get("summary", "")).strip(),
            "confidence": confidence,
            "source_timestamp": record.get("timestamp"),
            "content_hash": _digest(
                json.dumps(
                    {
                        "kind": kind,
                        "project": str(record.get("project", "")).strip(),
                        "content": content,
                    },
                    sort_keys=True,
                )
            ),
        }

    @staticmethod
    def _load(path: Path) -> list[dict[str, Any]]:
        suffix = path.suffix.lower()
        if suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                payload = payload.get("records", payload.get("conversations", [payload]))
            if not isinstance(payload, list):
                raise ValueError("JSON import must contain records or conversations")
            return [item if isinstance(item, dict) else {"content": str(item)} for item in payload]
        if suffix == ".csv":
            with path.open(encoding="utf-8", newline="") as handle:
                return list(csv.DictReader(handle))
        if suffix in {".md", ".markdown", ".txt"}:
            text = path.read_text(encoding="utf-8")
            chunks = [chunk.strip() for chunk in re.split(r"\n(?=#{1,3}\s)", text) if chunk.strip()]
            return [{"title": path.stem, "content": chunk} for chunk in chunks]
        raise ValueError("supported imports: JSON, Markdown, text, and CSV")

    def preview_import(self, path: str | Path) -> ImportPreview:
        source = Path(path).resolve()
        raw = source.read_text(encoding="utf-8")
        source_hash = _digest(raw)
        candidates: list[dict[str, Any]] = []
        duplicates = 0
        rejected = 0
        for index, record in enumerate(self._load(source), 1):
            normalized = self._normalize(record, f"{source.stem} #{index}")
            if self._contains_sensitive(normalized["content"]):
                rejected += 1
                continue
            exists = self.connection.execute(
                "SELECT 1 FROM memory_records WHERE content_hash = ?",
                (normalized["content_hash"],),
            ).fetchone()
            if exists:
                duplicates += 1
            else:
                candidates.append(normalized)
        return ImportPreview(
            source_path=str(source),
            source_type=source.suffix.lower().lstrip("."),
            source_hash=source_hash,
            records=tuple(candidates),
            duplicates=duplicates,
            rejected_sensitive=rejected,
        )

    def commit_import(self, preview: ImportPreview) -> list[int]:
        source_cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO memory_sources
                (source_path, source_type, source_hash, imported_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                preview.source_path,
                preview.source_type,
                preview.source_hash,
                _now(),
            ),
        )
        source_id = source_cursor.lastrowid
        if not source_id:
            row = self.connection.execute(
                "SELECT id FROM memory_sources WHERE source_hash = ?",
                (preview.source_hash,),
            ).fetchone()
            source_id = int(row["id"])
        created: list[int] = []
        for record in preview.records:
            cursor = self.connection.execute(
                """
                INSERT OR IGNORE INTO memory_records (
                    source_id, kind, project, entity, title, content, summary,
                    confidence, source_timestamp, content_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    record["kind"],
                    record["project"],
                    record["entity"],
                    record["title"],
                    record["content"],
                    record["summary"],
                    record["confidence"],
                    record["source_timestamp"],
                    record["content_hash"],
                    _now(),
                ),
            )
            if cursor.lastrowid:
                created.append(int(cursor.lastrowid))
        self.connection.commit()
        return created

    def soft_delete(self, record_id: int) -> None:
        self.connection.execute(
            "UPDATE memory_records SET deleted_at = ? WHERE id = ?",
            (_now(), record_id),
        )
        self.connection.commit()

    def restore(self, record_id: int) -> None:
        self.connection.execute(
            "UPDATE memory_records SET deleted_at = NULL WHERE id = ?",
            (record_id,),
        )
        self.connection.commit()

    def retrieve(
        self,
        query: str,
        *,
        project: str = "",
        tier: str = "working",
        budget_words: int = 400,
    ) -> list[dict[str, Any]]:
        if tier not in {"working", "project", "long-term"}:
            raise ValueError("tier must be working, project, or long-term")
        rows = self.connection.execute(
            """
            SELECT r.*, s.source_path
            FROM memory_records r
            JOIN memory_sources s ON s.id = r.source_id
            WHERE r.deleted_at IS NULL
              AND (? = '' OR r.project = ?)
            """,
            (project, project),
        ).fetchall()
        terms = {term for term in re.findall(r"\w+", query.lower()) if len(term) > 2}
        ranked = []
        for row in rows:
            item = dict(row)
            haystack = f"{item['title']} {item['content']} {item['summary']}".lower()
            overlap = sum(term in haystack for term in terms)
            if terms and not overlap:
                continue
            ranked.append((overlap, item))
        ranked.sort(key=lambda pair: (-pair[0], -pair[1]["confidence"], pair[1]["id"]))
        results = []
        used = 0
        for overlap, item in ranked:
            text = item["summary"] if tier == "long-term" and item["summary"] else item["content"]
            words = text.split()
            if used >= budget_words:
                break
            excerpt = " ".join(words[: max(0, budget_words - used)])
            used += len(excerpt.split())
            results.append(
                {
                    "id": item["id"],
                    "tier": tier,
                    "title": item["title"],
                    "content": excerpt,
                    "project": item["project"],
                    "confidence": item["confidence"],
                    "source": item["source_path"],
                    "reason_retrieved": f"{overlap} query terms matched",
                    "last_updated": item["created_at"],
                }
            )
        return results

    def export(self, path: str | Path) -> Path:
        target = Path(path)
        rows = [
            dict(row)
            for row in self.connection.execute(
                """
                SELECT r.*, s.source_path, s.source_hash
                FROM memory_records r
                JOIN memory_sources s ON s.id = r.source_id
                ORDER BY r.id
                """
            )
        ]
        target.write_text(json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8")
        return target

    def backup(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        destination = sqlite3.connect(target)
        try:
            self.connection.backup(destination)
        finally:
            destination.close()
        return target
