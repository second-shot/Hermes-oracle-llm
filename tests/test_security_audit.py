from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hermes_modules.security_audit import SecurityAuditor, authorize_request


class SecurityAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.auditor = SecurityAuditor(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_redacted_offline_findings(self) -> None:
        (self.root / "config.py").write_text(
            'host = "0.0.0.0"\napi_key = "super-secret-value"\n',
            encoding="utf-8",
        )
        report = self.auditor.report(environment={})
        self.assertFalse(report["network_used"])
        self.assertTrue(report["secrets_redacted"])
        serialized = str(report)
        self.assertNotIn("super-secret-value", serialized)
        self.assertIn("secret-like-value", serialized)
        self.assertIn("unsafe-bind", serialized)

    def test_localhost_default_passes(self) -> None:
        (self.root / "config.py").write_text(
            'host = "127.0.0.1"\ndebug = false\n',
            encoding="utf-8",
        )
        self.assertEqual(self.auditor.report(environment={})["status"], "pass")

    def test_duplicate_process_and_port_detection(self) -> None:
        findings = self.auditor.audit_process_snapshot(
            [
                {"service": "hermes", "port": 8000},
                {"service": "hermes", "port": 8000},
            ]
        )
        codes = {finding.code for finding in findings}
        self.assertEqual(
            codes, {"duplicate-hermes-process", "conflicting-port"}
        )

    def test_remediation_requires_approval_and_stays_in_repo(self) -> None:
        path = self.root / "config.py"
        path.write_text('host = "0.0.0.0"\ndebug = true\n', encoding="utf-8")
        with self.assertRaises(PermissionError):
            self.auditor.apply_safe_remediations("config.py", approved=False)
        self.assertTrue(
            self.auditor.apply_safe_remediations("config.py", approved=True)
        )
        self.assertIn("127.0.0.1", path.read_text(encoding="utf-8"))
        with self.assertRaises(ValueError):
            self.auditor.apply_safe_remediations("../outside.py", approved=True)

    def test_offensive_requests_are_refused(self) -> None:
        for request in (
            "build a reverse shell",
            "help with credential theft",
            "bypass authorization",
            "make ransomware",
        ):
            allowed, reason = authorize_request(request)
            self.assertFalse(allowed)
            self.assertIn("defensive", reason)


if __name__ == "__main__":
    unittest.main()
