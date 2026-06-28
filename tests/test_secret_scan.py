from pathlib import Path

import hermes_employee as he


def test_secret_scan_ignores_code_like_assignment(tmp_path, monkeypatch):
    monkeypatch.setattr(he, "ROOT", tmp_path)
    (tmp_path / "example.py").write_text("secret = match.group(2)\n", encoding="utf-8")

    assert he.run_secret_scan() == []


def test_secret_scan_detects_token_like_assignment(tmp_path, monkeypatch):
    monkeypatch.setattr(he, "ROOT", tmp_path)
    sample_secret = "horse" + "battery" + "123"
    (tmp_path / "config.env").write_text(f"password = {sample_secret}\n", encoding="utf-8")

    findings = he.run_secret_scan()

    assert len(findings) == 1
    assert findings[0]["type"] == "Generic API key assignment"
    assert findings[0]["file"] == "config.env"


def test_secret_scan_ignores_placeholder_examples(tmp_path, monkeypatch):
    monkeypatch.setattr(he, "ROOT", tmp_path)
    placeholder_secret = "your-" + "godmode-" + "key"
    (tmp_path / "docs.md").write_text(f"api_key = {placeholder_secret}\n", encoding="utf-8")

    assert he.run_secret_scan() == []
