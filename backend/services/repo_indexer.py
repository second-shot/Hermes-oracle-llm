from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from backend.services.provider_registry import DEFAULT_CONFIG_PATH, load_rotation_config


class RepoIndexer:
    def __init__(
        self,
        project_root: str | Path,
        config_path: str | Path = DEFAULT_CONFIG_PATH,
        hermes_dir: str | Path | None = None,
    ) -> None:
        self.project_root = Path(project_root)
        self.config = load_rotation_config(config_path)
        self.hermes_dir = Path(hermes_dir) if hermes_dir else self.project_root / ".hermes"
        self.hermes_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.hermes_dir / "repo_index.json"
        self.symbol_index_path = self.hermes_dir / "symbol_index.json"
        reflection = self.config.get("repo_reflection", {})
        self.ignore = set(reflection.get("ignore", []))
        self.max_files = int(reflection.get("max_files_per_task", 8))
        self.max_lines = int(reflection.get("max_lines_per_file", 260))

    def _is_ignored(self, path: Path) -> bool:
        parts = set(path.parts)
        return any(token in parts for token in self.ignore)

    def _git_diff_files(self) -> list[str]:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.project_root), "diff", "--name-only", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            return []
        if result.returncode != 0:
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def _config_files(self) -> list[str]:
        candidates = []
        for path in self.project_root.iterdir():
            if path.is_file() and path.suffix.lower() in {".json", ".yaml", ".yml", ".toml", ".ini"}:
                candidates.append(path.name)
        return candidates

    def _extract_symbols(self, text: str) -> list[str]:
        return re.findall(r"^\s*(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", text, flags=re.MULTILINE)

    def build_index(
        self,
        startup: bool = False,
        mentioned_files: list[str] | None = None,
        recent_errors: list[str] | None = None,
        use_git_diff: bool = True,
    ) -> dict[str, Any]:
        if startup and self.config.get("repo_reflection", {}).get("never_scan_full_repo_on_startup", True):
            empty = {"files": {}, "symbols": {}, "startup_limited": True}
            self.index_path.write_text(json.dumps(empty, indent=2), encoding="utf-8")
            self.symbol_index_path.write_text(json.dumps({}, indent=2), encoding="utf-8")
            return empty

        ordered: list[str] = []
        for group in (mentioned_files or [], recent_errors or [], self._git_diff_files() if use_git_diff else [], self._config_files()):
            for item in group:
                if item and item not in ordered:
                    ordered.append(item)

        if not ordered:
            for path in self.project_root.rglob("*"):
                if len(ordered) >= self.max_files:
                    break
                if path.is_file() and not self._is_ignored(path):
                    ordered.append(str(path.relative_to(self.project_root)).replace("\\", "/"))

        files: dict[str, Any] = {}
        symbols: dict[str, list[str]] = {}
        for relative_name in ordered:
            if len(files) >= self.max_files:
                break
            path = self.project_root / relative_name
            if not path.exists() or not path.is_file() or self._is_ignored(path):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            preview_lines = text.splitlines()[: self.max_lines]
            relative = str(path.relative_to(self.project_root)).replace("\\", "/")
            files[relative] = {
                "line_count": min(len(text.splitlines()), self.max_lines),
                "preview": "\n".join(preview_lines),
            }
            file_symbols = self._extract_symbols(text)
            if file_symbols:
                symbols[relative] = file_symbols

        index = {"files": files, "symbols": symbols, "startup_limited": False}
        self.index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
        self.symbol_index_path.write_text(json.dumps(symbols, indent=2), encoding="utf-8")
        return index
