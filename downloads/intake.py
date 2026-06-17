"""Hermes V5 Download Brain intake pipeline.

The pipeline is intentionally deterministic: scan, classify, route, queue,
report. It does not delete, move, upload, or mutate user files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .classifier import classify_category, priority_hint, route_project
from .metadata import collect_metadata, default_downloads_dir, is_safe_regular_file
from .queue import DownloadQueue


class DownloadBrain:
    def __init__(
        self,
        downloads_dir: str | Path | None = None,
        queue_path: str | Path = "memory/downloads_queue.json",
        manifest_path: str | Path = "memory/downloads_manifest.json",
    ):
        self.downloads_dir = Path(downloads_dir) if downloads_dir else default_downloads_dir()
        self.queue = DownloadQueue(queue_path)
        self.manifest_path = Path(manifest_path)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

    def scan(self) -> List[Dict[str, Any]]:
        if not self.downloads_dir.exists():
            return []
        items: List[Dict[str, Any]] = []
        for path in sorted(self.downloads_dir.iterdir(), key=lambda item: item.name.lower()):
            if not is_safe_regular_file(path):
                continue
            metadata = collect_metadata(path)
            metadata["category"] = classify_category(path)
            metadata["project"] = route_project(path)
            metadata["priority"] = priority_hint(path)
            metadata["intake_action"] = self.suggest_action(metadata)
            items.append(metadata)
        return items

    def suggest_action(self, item: Dict[str, Any]) -> str:
        project = item.get("project")
        category = item.get("category")
        priority = item.get("priority")
        if priority == "now":
            return "review_now"
        if project == "resale":
            return "send_to_operator"
        if project == "hermes":
            return "send_to_research_or_build"
        if project == "personal":
            return "send_to_identity_memory"
        if category == "unknown":
            return "manual_review"
        return "queue_for_later"

    def run(self) -> Dict[str, Any]:
        items = self.scan()
        queue_stats = self.queue.upsert_many(items)
        summary = self.summarize(items, queue_stats)
        self.write_manifest(items, summary)
        return summary

    def summarize(self, items: List[Dict[str, Any]], queue_stats: Dict[str, int]) -> Dict[str, Any]:
        by_category: Dict[str, int] = {}
        by_project: Dict[str, int] = {}
        by_priority: Dict[str, int] = {}
        for item in items:
            by_category[item["category"]] = by_category.get(item["category"], 0) + 1
            by_project[item["project"]] = by_project.get(item["project"], 0) + 1
            by_priority[item["priority"]] = by_priority.get(item["priority"], 0) + 1
        return {
            "downloads_dir": str(self.downloads_dir),
            "scanned_files": len(items),
            "queue": queue_stats,
            "by_category": by_category,
            "by_project": by_project,
            "by_priority": by_priority,
            "next_actions": self.next_actions(items),
        }

    def next_actions(self, items: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        ranked = sorted(
            items,
            key=lambda item: {"now": 0, "prep": 1, "hold": 2}.get(item.get("priority"), 3),
        )
        return [
            {
                "filename": item["filename"],
                "project": item["project"],
                "priority": item["priority"],
                "action": item["intake_action"],
            }
            for item in ranked[:10]
        ]

    def write_manifest(self, items: List[Dict[str, Any]], summary: Dict[str, Any]) -> None:
        payload = {"summary": summary, "items": items}
        with self.manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)


def run_download_intake(downloads_dir: str | Path | None = None) -> Dict[str, Any]:
    return DownloadBrain(downloads_dir=downloads_dir).run()
