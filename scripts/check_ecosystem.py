from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services.ecosystem_control import EcosystemControlPlane


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Hermes Oracle modules, cost posture and upkeep gates.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when active modules have blockers.")
    args = parser.parse_args()

    snapshot = EcosystemControlPlane().snapshot()
    print(json.dumps(snapshot, indent=2))
    if args.strict and snapshot["upkeep"]["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
