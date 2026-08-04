from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hermes_modules.memory_archive import MemoryArchive


class MemoryArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.archive = MemoryArchive(self.root / "memory.sqlite3")

    def tearDown(self) -> None:
        self.archive.close()
        self.temp.cleanup()

    def source(self, records) -> Path:
        path = self.root / "import.json"
        path.write_text(json.dumps(records), encoding="utf-8")
        return path

    def test_import_requires_preview_then_commit(self) -> None:
        preview = self.archive.preview_import(
            self.source(
                [{"kind": "decision", "project": "Hermes", "content": "Use local models"}]
            )
        )
        self.assertEqual(preview.summary()["candidate_records"], 1)
        self.assertTrue(preview.summary()["commit_required"])
        self.assertEqual(len(self.archive.commit_import(preview)), 1)

    def test_duplicate_detection(self) -> None:
        path = self.source([{"content": "Same note", "project": "Hermes"}])
        self.archive.commit_import(self.archive.preview_import(path))
        second = self.archive.preview_import(path)
        self.assertEqual(second.duplicates, 1)
        self.assertEqual(second.records, ())

    def test_sensitive_records_are_rejected(self) -> None:
        preview = self.archive.preview_import(
            self.source([{"content": "api_key=do-not-ingest-this"}])
        )
        self.assertEqual(preview.rejected_sensitive, 1)
        self.assertEqual(preview.records, ())

    def test_retrieval_has_budget_reason_and_provenance(self) -> None:
        path = self.source(
            [
                {
                    "kind": "project",
                    "project": "Hermes",
                    "title": "Routing",
                    "content": "Local model routing remains free and deterministic",
                }
            ]
        )
        self.archive.commit_import(self.archive.preview_import(path))
        result = self.archive.retrieve(
            "local routing", project="Hermes", budget_words=4
        )[0]
        self.assertLessEqual(len(result["content"].split()), 4)
        self.assertIn("matched", result["reason_retrieved"])
        self.assertEqual(Path(result["source"]), path.resolve())

    def test_deletion_is_reversible_and_backup_opens(self) -> None:
        path = self.source([{"content": "Recoverable note"}])
        record_id = self.archive.commit_import(self.archive.preview_import(path))[0]
        self.archive.soft_delete(record_id)
        self.assertEqual(self.archive.retrieve("Recoverable"), [])
        self.archive.restore(record_id)
        self.assertEqual(len(self.archive.retrieve("Recoverable")), 1)
        self.assertTrue(self.archive.backup(self.root / "backup.sqlite3").is_file())


if __name__ == "__main__":
    unittest.main()
