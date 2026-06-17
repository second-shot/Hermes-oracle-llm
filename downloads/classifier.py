"""Deterministic file classification for Hermes V5 Download Brain.

No external dependencies. No LLM calls. This module only uses filename,
extension, and lightweight rule matching so it can run safely and cheaply on
local machines.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable

CATEGORY_EXTENSIONS: Dict[str, set[str]] = {
    "documents": {
        ".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt",
        ".pages", ".epub",
    },
    "images": {
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".bmp",
        ".tiff", ".svg",
    },
    "videos": {
        ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v",
    },
    "audio": {
        ".mp3", ".wav", ".aiff", ".flac", ".m4a", ".ogg", ".mid", ".midi",
    },
    "archives": {
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
    },
    "code": {
        ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".json",
        ".yaml", ".yml", ".toml", ".sh", ".bat", ".ps1", ".sql",
    },
    "spreadsheets": {
        ".csv", ".xls", ".xlsx", ".ods", ".tsv",
    },
}

PROJECT_KEYWORDS: Dict[str, tuple[str, ...]] = {
    "personal": (
        "passport", "birth", "bank", "statement", "id", "identity", "uc",
        "universal credit", "benefit", "hmrc", "dwp", "council", "medical",
    ),
    "vehicle": (
        "mini", "cooper", "mot", "insurance", "v5", "vehicle", "car", "bmw",
        "mechanic", "garage", "engine", "wheel", "tyre",
    ),
    "resale": (
        "inventory", "vinted", "ebay", "depop", "grailed", "vestiaire", "sale",
        "sold", "listing", "jacket", "shoes", "watch", "gold", "silver", "jewellery",
        "jewelry", "hallmark", "scrap", "copper",
    ),
    "hermes": (
        "hermes", "oracle", "mia", "operator", "kernel", "agent", "mlx", "qwen",
        "llama", "smolvlm", "model", "runtime",
    ),
    "creative": (
        "music", "video", "visual", "film", "poster", "flyer", "song", "audio",
        "stage", "design", "art", "painting",
    ),
    "community": (
        "housing", "squat", "community", "hackney", "legal", "church", "school",
        "trust", "meeting", "collective",
    ),
}


def classify_category(path: str | Path) -> str:
    """Classify a file into a broad intake category."""
    suffix = Path(path).suffix.lower()
    for category, extensions in CATEGORY_EXTENSIONS.items():
        if suffix in extensions:
            return category
    return "unknown"


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def route_project(path: str | Path) -> str:
    """Route a file to the most likely Hermes project domain."""
    name = Path(path).name.lower().replace("_", " ").replace("-", " ")
    for project, keywords in PROJECT_KEYWORDS.items():
        if _contains_any(name, keywords):
            return project
    category = classify_category(path)
    if category in {"images", "videos", "audio"}:
        return "creative"
    if category in {"documents", "spreadsheets"}:
        return "inbox"
    return "unsorted"


def priority_hint(path: str | Path) -> str:
    """Return a simple processing priority hint."""
    name = Path(path).name.lower()
    urgent_terms = ("passport", "uc", "dwp", "invoice", "deadline", "legal", "court", "mot")
    money_terms = ("gold", "silver", "jewellery", "watch", "sold", "inventory", "vinted", "ebay")
    if _contains_any(name, urgent_terms):
        return "now"
    if _contains_any(name, money_terms):
        return "prep"
    return "hold"
