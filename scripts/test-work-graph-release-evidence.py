#!/usr/bin/env python3
"""W2-06 native report binding and fail-closed aggregate contracts."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts/work-graph-release-evidence.py"


def git(*arguments: str) -> str:
    return subprocess.run(["git", *arguments], cwd=ROOT, text=True, capture_output=True,
                          check=True).stdout.strip()


class WorkGraphReleaseEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="agentsmith graph evidence ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.commit = git("rev-parse", "HEAD")
        self.tree = git("rev-parse", "HEAD^{tree}")

    def report(self, platform: str) -> dict:
        return {
            "schema_version": 1,
            "evidence_kind": "agentsmith-work-graph-native-platform",
            "status": "passed",
            "platform": platform,
            "git_commit": self.commit,
            "git_tree": self.tree,
            "dirty_before": False,
            "dirty_after": False,
            "python_version": "3.13.0",
            "recorded_at": "2026-09-21T10:00:00Z",
            "phases": [
                {"label": label, "command": ["python", script], "exit_code": 0,
                 "tests_run": minimum, "stdout_sha256": "a" * 64, "stderr_sha256": "b" * 64}
                for label, script, minimum in (
                    ("contracts", "scripts/test-work-graph-contracts.py", 6),
                    ("status", "scripts/test-work-graph-status.py", 6),
                    ("base", "scripts/test-autonomous-graph-base.py", 6),
                    ("cli", "scripts/test-work-graph-cli-surface.py", 2),
                    ("coordination", "scripts/test-autonomous-state.py", 20),
                    ("secret-scan", "scripts/test-secret-scan.py", 10),
                    ("lifecycle", "scripts/test-work-graph-dispatch.py", 10),
                )
            ],
            "external_write_used": False,
        }

    def aggregate(self, reports: list[Path], name: str = "aggregate.json") -> subprocess.CompletedProcess[str]:
        args = [sys.executable, str(SCRIPT), "aggregate", "--expected-commit", self.commit,
                "--output-root", str(self.root), "--output", str(self.root / name)]
        for report in reports:
            args.extend(("--report", str(report)))
        return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)

    def write_reports(self) -> list[Path]:
        paths = []
        for platform in ("linux", "macos", "windows"):
            path = self.root / f"{platform}.json"
            path.write_text(json.dumps(self.report(platform)) + "\n", encoding="utf-8")
            paths.append(path)
        return paths

    def test_aggregate_binds_three_passed_native_lifecycles_to_expected_tree(self) -> None:
        paths = self.write_reports()
        result = self.aggregate(paths)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        aggregate = json.loads((self.root / "aggregate.json").read_text(encoding="utf-8"))
        self.assertEqual(aggregate["git_commit"], self.commit)
        self.assertEqual(aggregate["git_tree"], self.tree)
        self.assertEqual(aggregate["platforms"], ["macos", "linux", "windows"])
        self.assertFalse(aggregate["external_write_used"])

    def test_aggregate_rejects_missing_duplicate_mismatched_and_partial_evidence(self) -> None:
        paths = self.write_reports()
        variants = {
            "missing": paths[:2],
            "duplicate": [paths[0], paths[0], paths[2]],
        }
        altered = self.report("windows")
        altered["git_tree"] = "9" * 40
        (self.root / "wrong-tree.json").write_text(json.dumps(altered), encoding="utf-8")
        variants["wrong-tree"] = [paths[0], paths[1], self.root / "wrong-tree.json"]
        wrong_all = []
        for platform in ("linux", "macos", "windows"):
            altered = self.report(platform)
            altered["git_tree"] = "8" * 40
            path = self.root / f"invented-{platform}.json"
            path.write_text(json.dumps(altered), encoding="utf-8")
            wrong_all.append(path)
        variants["invented-tree"] = wrong_all
        altered = self.report("windows")
        altered["git_commit"] = "7" * 40
        (self.root / "wrong-commit.json").write_text(json.dumps(altered), encoding="utf-8")
        variants["wrong-commit"] = [paths[0], paths[1], self.root / "wrong-commit.json"]
        altered = self.report("windows")
        altered["phases"][-1]["tests_run"] = 0
        (self.root / "skipped.json").write_text(json.dumps(altered), encoding="utf-8")
        variants["skipped"] = [paths[0], paths[1], self.root / "skipped.json"]
        altered = self.report("windows")
        altered["external_write_used"] = True
        (self.root / "external.json").write_text(json.dumps(altered), encoding="utf-8")
        variants["external"] = [paths[0], paths[1], self.root / "external.json"]
        altered = self.report("windows")
        altered["phases"][-1]["command"] = ["python", "unreviewed.py"]
        (self.root / "tampered-command.json").write_text(json.dumps(altered), encoding="utf-8")
        variants["tampered-command"] = [paths[0], paths[1], self.root / "tampered-command.json"]
        altered = self.report("windows")
        altered["phases"][-1]["exit_code"] = False
        (self.root / "boolean-exit.json").write_text(json.dumps(altered), encoding="utf-8")
        variants["boolean-exit"] = [paths[0], paths[1], self.root / "boolean-exit.json"]
        for name, selected in variants.items():
            with self.subTest(name=name):
                result = self.aggregate(selected, name + "-aggregate.json")
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.root / (name + "-aggregate.json")).exists())

    def test_aggregate_rejects_symlinked_input_and_output(self) -> None:
        paths = self.write_reports()
        link = self.root / "linked-report.json"
        try:
            link.symlink_to(paths[2])
        except OSError:
            self.skipTest("host cannot create a symlink")
        result = self.aggregate([paths[0], paths[1], link], "linked-input-aggregate.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "linked-input-aggregate.json").exists())
        target = self.root / "redirected.json"
        output = self.root / "linked-output.json"
        output.symlink_to(target)
        result = self.aggregate(paths, output.name)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(target.exists())

    def test_manual_workflow_records_each_native_host_and_aggregates_matching_reports(self) -> None:
        workflow = (ROOT / ".github/workflows/verify.yml").read_text(encoding="utf-8")
        self.assertIn("os: [ubuntu-latest, macos-latest, windows-latest]", workflow)
        self.assertIn("scripts/work-graph-release-evidence.py record", workflow)
        self.assertIn("scripts/work-graph-release-evidence.py aggregate", workflow)
        self.assertIn("needs: [w2-native-evidence, compatibility, posix-guardrails]", workflow)
        self.assertIn("needs.compatibility.result == 'success'", workflow)
        self.assertIn("needs.posix-guardrails.result == 'success'", workflow)
        for host in ("Linux", "macOS", "Windows"):
            self.assertIn(f"release-evidence/work-graph-{host}.json", workflow)


if __name__ == "__main__":
    unittest.main()
