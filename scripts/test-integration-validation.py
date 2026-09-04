#!/usr/bin/env python3
"""Fixture-driven regression tests for the integration validation checkpoint."""

from __future__ import annotations

import copy
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "agentsmith.py"
FIXTURES = ROOT / "tests" / "fixtures" / "integration-validation"
SPEC = importlib.util.spec_from_file_location("agentsmith_integration_validation", CORE)
assert SPEC and SPEC.loader
AGENTSMITH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AGENTSMITH)


def merge(base: object, patch: object) -> object:
    """Recursively merge fixture patches; one-item integration lists patch by index."""
    if isinstance(base, dict) and isinstance(patch, dict):
        result = copy.deepcopy(base)
        for key, value in patch.items():
            result[key] = merge(result[key], value) if key in result else copy.deepcopy(value)
        return result
    if isinstance(base, list) and isinstance(patch, list) and len(base) == len(patch) == 1:
        return [merge(base[0], patch[0])]
    return copy.deepcopy(patch)


def snapshot(path: Path) -> dict[str, str]:
    return {
        item.relative_to(path).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in path.rglob("*") if item.is_file()
    }


class IntegrationValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))

    def document(self, name: str) -> tuple[dict, dict]:
        case = next(item for item in self.fixture["cases"] if item["name"] == name)
        return merge(self.fixture["base"], case.get("patch", {})), case

    def test_fixture_matrix(self) -> None:
        for case in self.fixture["cases"]:
            with self.subTest(case=case["name"]):
                document = merge(self.fixture["base"], case.get("patch", {}))
                report = AGENTSMITH.validate_integration_checkpoint(document)
                codes = {issue["code"] for issue in report["issues"]}
                self.assertTrue(set(case.get("expected_codes", [])) <= codes, (case["name"], codes))
                self.assertTrue(set(case.get("forbidden_codes", [])).isdisjoint(codes), (case["name"], codes))
                if not case.get("expected_codes"):
                    self.assertTrue(report["complete"], (case["name"], codes))

    def test_cli_never_changes_existing_profile_or_browser_revisions(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith integration bytes ") as temporary:
            temporary_path = Path(temporary)
            protected = temporary_path / "protected"
            protected.mkdir()
            for source in (FIXTURES / "existing-profile", FIXTURES / "browser-cache"):
                destination = protected / source.name
                import shutil
                shutil.copytree(source, destination)
            before = snapshot(protected)
            document, _ = self.document("shared-cache-preserved")
            checkpoint = temporary_path / "checkpoint.json"
            checkpoint.write_text(json.dumps(document), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(CORE), "validate-integration", "--checkpoint", str(checkpoint)],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(before, snapshot(protected))
            revisions = [path.name for path in (protected / "browser-cache").iterdir()]
            self.assertEqual(sorted(revisions), ["chromium-100", "chromium-200"])

    def test_credentials_never_appear_in_normal_error_or_debug_output(self) -> None:
        document, _ = self.document("unpinned-package")
        token = "".join(("g", "hp_", "A" * 36))
        api_key = "".join(("s", "k-", "B" * 32))
        integration = document["integrations"][0]
        integration["configuration"]["args"].append(f"--token={token}")
        integration["configuration"]["env"] = {"API_TOKEN": api_key}
        with tempfile.TemporaryDirectory(prefix="agentsmith integration secrets ") as temporary:
            checkpoint = Path(temporary) / "checkpoint.json"
            checkpoint.write_text(json.dumps(document), encoding="utf-8")
            for extra in ([], ["--debug"]):
                result = subprocess.run(
                    [sys.executable, str(CORE), "validate-integration", "--checkpoint", str(checkpoint), *extra],
                    cwd=ROOT, text=True, capture_output=True, check=False,
                )
                output = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(token, output)
                self.assertNotIn(api_key, output)
                self.assertNotIn("--token=", output)
                self.assertNotIn("API_TOKEN", output)

            malformed = Path(temporary) / "malformed.json"
            malformed.write_text('{"env":{"API_TOKEN":"' + api_key + '"}', encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(CORE), "validate-integration", "--checkpoint", str(malformed), "--debug"],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
            self.assertNotIn(api_key, result.stdout + result.stderr)

    def test_validator_does_not_install_or_launch_any_integration(self) -> None:
        document, _ = self.document("exact-package-pin")
        with mock.patch.object(AGENTSMITH.subprocess, "run", side_effect=AssertionError("process launched")):
            report = AGENTSMITH.validate_integration_checkpoint(document)
        self.assertTrue(report["complete"])

    def test_cli_validation_skips_automatic_update_state_and_network(self) -> None:
        document, _ = self.document("exact-package-pin")
        with tempfile.TemporaryDirectory(prefix="agentsmith integration no update ") as temporary:
            checkpoint = Path(temporary) / "checkpoint.json"
            checkpoint.write_text(json.dumps(document), encoding="utf-8")
            with mock.patch.object(AGENTSMITH, "maybe_report_automatic_update") as update:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    result = AGENTSMITH.run(["validate-integration", "--checkpoint", str(checkpoint)])
            self.assertEqual(result, 0)
            update.assert_not_called()

    def test_shipped_mcp_defaults_pass_the_same_static_checks(self) -> None:
        defaults = json.loads((ROOT / "config" / "mcp.example.json").read_text(encoding="utf-8"))["mcpServers"]
        for name, configuration in defaults.items():
            with self.subTest(name=name):
                document, _ = self.document("exact-package-pin")
                integration = document["integrations"][0]
                integration["id"] = name
                integration["name"] = name
                integration["configuration"] = {
                    **copy.deepcopy(configuration),
                    "diagnostics": {"emit_full_argv": False, "emit_full_environment": False},
                }
                integration["package"]["discovered_version"] = AGENTSMITH.executable_package_version(configuration)
                if name != "playwright":
                    integration["resources"]["profile"] = {"mode": "not-applicable"}
                    integration["resources"]["browser_cache"] = {"mode": "not-applicable"}
                report = AGENTSMITH.validate_integration_checkpoint(document)
                self.assertTrue(report["complete"], (name, report["issues"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
