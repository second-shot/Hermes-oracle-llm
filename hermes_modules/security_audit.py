from __future__ import annotations

import argparse
import json
import os
import re
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping


SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\b(?:api[_-]?key|password|token|client[_-]?secret)\s*[:=]\s*[\"']?[^\s\"']+"),
)
OFFENSIVE_PATTERNS = (
    "credential theft",
    "steal password",
    "phishing",
    "persistence",
    "reverse shell",
    "disable antivirus",
    "bypass authorization",
    "malware",
    "ransomware",
    "exploit payload",
)
CONFIG_SUFFIXES = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".py"}


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    evidence_path: str
    recommendation: str
    verification: str


def authorize_request(request: str) -> tuple[bool, str]:
    lowered = request.lower()
    if any(pattern in lowered for pattern in OFFENSIVE_PATTERNS):
        return False, "Refused: Hermes security supports defensive, authorized work only."
    return True, "Allowed defensive request."


class SecurityAuditor:
    """Offline, redacted audit of a Hermes repository and explicit runtime snapshot."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()

    def _relative(self, path: Path, line: int | None = None) -> str:
        value = str(path.resolve().relative_to(self.project_root)).replace("\\", "/")
        return f"{value}:{line}" if line else value

    def _candidate_files(self) -> Iterable[Path]:
        excluded = {".git", ".venv", "venv", "node_modules", "__pycache__"}
        for path in self.project_root.rglob("*"):
            if not path.is_file() or any(part in excluded for part in path.parts):
                continue
            if (
                path.suffix.lower() in CONFIG_SUFFIXES
                or path.name.startswith(".env")
                or "log" in path.parts
            ):
                yield path

    def audit_files(self) -> list[Finding]:
        findings: list[Finding] = []
        for path in self._candidate_files():
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line_number, line in enumerate(text.splitlines(), 1):
                evidence = self._relative(path, line_number)
                if any(pattern.search(line) for pattern in SECRET_PATTERNS):
                    findings.append(
                        Finding(
                            "critical",
                            "secret-like-value",
                            evidence,
                            "Remove the value, rotate it outside Hermes, and use an environment variable.",
                            f"Re-run security audit and confirm {evidence} is absent.",
                        )
                    )
                if re.search(r"(?i)(?:host|bind)\s*[:=]\s*[\"']?0\.0\.0\.0", line):
                    findings.append(
                        Finding(
                            "high",
                            "unsafe-bind",
                            evidence,
                            "Bind to 127.0.0.1 unless an approved network boundary exists.",
                            "Start Hermes and confirm the listener is on 127.0.0.1.",
                        )
                    )
                if re.search(r"(?i)(?:debug\s*[:=]\s*true|DEBUG\s*=\s*1)", line):
                    findings.append(
                        Finding(
                            "medium",
                            "debug-enabled",
                            evidence,
                            "Disable debug mode in checked-in configuration.",
                            "Re-run the audit and application smoke tests.",
                        )
                    )
                if "*" in line and re.search(r"(?i)(?:allow_origins|cors)", line):
                    findings.append(
                        Finding(
                            "high",
                            "permissive-cors",
                            evidence,
                            "Replace wildcard CORS with explicit localhost origins.",
                            "Confirm unlisted origins receive no CORS permission.",
                        )
                    )
                if re.search(
                    r"(?i)(?:cloud_enabled|paid_models_allowed)\s*[:=]\s*true", line
                ):
                    findings.append(
                        Finding(
                            "high",
                            "cloud-enabled",
                            evidence,
                            "Keep paid/cloud providers disabled by default and approval-gated.",
                            "Run the free-only policy tests.",
                        )
                    )
            if path.name.startswith(".env") or "secret" in path.name.lower():
                try:
                    mode = stat.S_IMODE(path.stat().st_mode)
                    if mode & (stat.S_IRWXG | stat.S_IRWXO):
                        findings.append(
                            Finding(
                                "medium",
                                "weak-file-permissions",
                                self._relative(path),
                                "Restrict the file to the current user.",
                                f"Check permissions for {self._relative(path)}.",
                            )
                        )
                except OSError:
                    pass
        return findings

    @staticmethod
    def audit_environment(environment: Mapping[str, str] | None = None) -> list[Finding]:
        environment = environment if environment is not None else os.environ
        findings = []
        for key in ("HERMES_CLOUD_ENABLED", "OPENAI_ENABLED", "DEBUG"):
            if str(environment.get(key, "")).strip().lower() in {"1", "true", "yes", "on"}:
                findings.append(
                    Finding(
                        "high" if "CLOUD" in key or "OPENAI" in key else "medium",
                        "unsafe-environment",
                        f"environment:{key}",
                        f"Unset {key} for the local-only default.",
                        f"Confirm {key} is unset; its value is intentionally redacted.",
                    )
                )
        return findings

    @staticmethod
    def audit_process_snapshot(
        processes: Iterable[Mapping[str, object]],
    ) -> list[Finding]:
        findings = []
        hermes = [process for process in processes if process.get("service") == "hermes"]
        if len(hermes) > 1:
            findings.append(
                Finding(
                    "high",
                    "duplicate-hermes-process",
                    "runtime:process-snapshot",
                    "Stop duplicate Hermes processes using the operator-approved process manager.",
                    "Provide a new snapshot with exactly one Hermes process.",
                )
            )
        ports: dict[object, int] = {}
        for process in processes:
            port = process.get("port")
            if port is not None:
                ports[port] = ports.get(port, 0) + 1
        if any(count > 1 for count in ports.values()):
            findings.append(
                Finding(
                    "high",
                    "conflicting-port",
                    "runtime:process-snapshot",
                    "Assign one local service per port and restart only with approval.",
                    "Provide a snapshot with unique listening ports.",
                )
            )
        return findings

    def report(
        self,
        *,
        environment: Mapping[str, str] | None = None,
        processes: Iterable[Mapping[str, object]] = (),
    ) -> dict[str, object]:
        findings = (
            self.audit_files()
            + self.audit_environment(environment)
            + self.audit_process_snapshot(processes)
        )
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        findings.sort(key=lambda finding: (order[finding.severity], finding.evidence_path))
        return {
            "status": "pass" if not findings else "attention",
            "network_used": False,
            "secrets_redacted": True,
            "findings": [asdict(finding) for finding in findings],
        }

    def apply_safe_remediations(
        self,
        relative_path: str,
        *,
        approved: bool,
    ) -> bool:
        if not approved:
            raise PermissionError("explicit approval is required")
        path = (self.project_root / relative_path).resolve()
        if self.project_root not in path.parents:
            raise ValueError("remediation target must stay inside the repository")
        if path.suffix.lower() not in CONFIG_SUFFIXES and path.suffix.lower() != ".md":
            raise ValueError("only repository configuration and documentation are supported")
        original = path.read_text(encoding="utf-8")
        updated = original.replace("0.0.0.0", "127.0.0.1")
        updated = re.sub(r"(?i)(debug\s*[:=]\s*)true", r"\1false", updated)
        if updated == original:
            return False
        path.write_text(updated, encoding="utf-8")
        return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline Hermes defensive audit")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    report = SecurityAuditor(args.root).report()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
