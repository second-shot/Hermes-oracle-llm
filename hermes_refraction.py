"""Local-only refraction policy diagnostic."""

from __future__ import annotations

import argparse

from hermes_provider import get_lm_studio_base_url, get_model_provider, is_local_url


def run_test() -> int:
    provider = get_model_provider()
    base_url = get_lm_studio_base_url()
    if provider != "lm_studio" or not is_local_url(base_url):
        print("REFRACTION MISCONFIGURED")
        return 1
    print("REFRACTION TEST OK")
    print(f"provider: {provider}")
    print(f"base_url: {base_url}")
    print("mode: local/no-credit")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Hermes local refraction diagnostics")
    parser.add_argument("command", choices=["test"])
    args = parser.parse_args()
    return run_test() if args.command == "test" else 1


if __name__ == "__main__":
    raise SystemExit(main())
