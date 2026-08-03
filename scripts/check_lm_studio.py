"""Check Hermes' configured local LM Studio server."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hermes_provider import lm_studio_healthcheck  # noqa: E402


def main() -> int:
    result = lm_studio_healthcheck()
    print(result["status"])
    if result.get("base_url"):
        print(f"base_url: {result['base_url']}")
    print(f"detail: {result['detail']}")
    return 0 if result["online"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
