from __future__ import annotations

from typing import Any


def ok(data: dict[str, Any], meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "status": "ok",
        "data": data,
        "meta": meta or {},
    }


def error(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "status": "error",
        "error": {
            "code": code,
            "message": message,
        },
        "details": details or {},
    }

