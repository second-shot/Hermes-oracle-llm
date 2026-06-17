import json
from pathlib import Path

from downloads.classifier import classify_category, priority_hint, route_project
from downloads.intake import DownloadBrain


def test_download_classifier_routes_known_files():
    assert classify_category("passport.pdf") == "documents"
    assert classify_category("inventory.jpg") == "images"
    assert classify_category("script.py") == "code"
    assert route_project("passport.pdf") == "personal"
    assert route_project("mini_manual.pdf") == "vehicle"
    assert route_project("gold_watch.jpg") == "resale"
    assert priority_hint("passport.pdf") == "now"


def test_download_brain_scans_and_persists_queue(tmp_path):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    (downloads / "passport.pdf").write_text("sample", encoding="utf-8")
    (downloads / "inventory.jpg").write_text("sample", encoding="utf-8")

    queue_path = tmp_path / "memory" / "downloads_queue.json"
    manifest_path = tmp_path / "memory" / "downloads_manifest.json"
    brain = DownloadBrain(downloads_dir=downloads, queue_path=queue_path, manifest_path=manifest_path)
    summary = brain.run()

    assert summary["scanned_files"] == 2
    assert summary["queue"]["created"] == 2
    assert summary["by_project"]["personal"] == 1
    assert summary["by_project"]["resale"] == 1
    assert queue_path.exists()
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(manifest["items"]) == 2
