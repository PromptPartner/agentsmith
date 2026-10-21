#!/usr/bin/env python3
"""W2-06 native report binding and fail-closed aggregate contracts."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts/work-graph-release-evidence.py"
SPEC = importlib.util.spec_from_file_location("work_graph_release_evidence", SCRIPT)
assert SPEC and SPEC.loader
RECORDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RECORDER)


def git(*arguments: str) -> str:
    return subprocess.run(["git", *arguments], cwd=ROOT, text=True, capture_output=True,
                          check=True).stdout.strip()


class WorkGraphReleaseEvidenceTests(unittest.TestCase):
    def test_failure_diagnostics_keep_stage_line_and_exception_without_raw_output(self) -> None:
        synthetic_secret = "ghp_" + "abcdefghijklmnopqrstuvwxyz1234"
        stderr = (
            "FAIL: test_cleanup_preview_retains_foreign_and_source_artifacts "
            "(__main__.GraphDispatchTests.test_cleanup_preview_retains_foreign_and_source_artifacts)\n"
            "Traceback (most recent call last):\n"
            "  File \"/private/secret/repo/scripts/test-work-graph-dispatch.py\", line 260, "
            "in test_cleanup_preview_retains_foreign_and_source_artifacts\n"
            f"AssertionError: {synthetic_secret} /private/secret/repo\n"
        )
        self.assertEqual(RECORDER.failure_diagnostics("lifecycle", stderr), [
            {"test": "test_cleanup_preview_retains_foreign_and_source_artifacts",
             "stage": "lifecycle", "line": 260, "exception": "AssertionError"}
        ])
        self.assertNotIn(synthetic_secret, str(RECORDER.failure_diagnostics("lifecycle", stderr)))
        self.assertNotIn("/private/secret", str(RECORDER.failure_diagnostics("lifecycle", stderr)))

    def test_failure_labels_keep_test_names_without_raw_output(self) -> None:
        synthetic_secret = "ghp_" + "abcdefghijklmnopqrstuvwxyz1234"
        stderr = ("FAIL: test_coordination (__main__.FixtureTests.test_coordination)\n"
                  f"AssertionError: {synthetic_secret}\n"
                  "ERROR: test_resume (__main__.FixtureTests.test_resume)\r\n")
        self.assertEqual(RECORDER.failure_labels(stderr), ["test_coordination", "test_resume"])

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
                | {"failures": []}
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
        altered = self.report("windows")
        altered["phases"][-1]["failures"] = [
            {"test": "test_failed", "stage": "lifecycle", "line": 1, "exception": "AssertionError"}
        ]
        (self.root / "hidden-failure.json").write_text(json.dumps(altered), encoding="utf-8")
        variants["hidden-failure"] = [paths[0], paths[1], self.root / "hidden-failure.json"]
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
        self.assertIn("kernel.apparmor_restrict_unprivileged_userns", workflow)
        self.assertIn("bwrap --unshare-net --ro-bind / /", workflow)
        self.assertIn("Probe actual Linux verifier policy", workflow)
        guardrails = workflow.split("  posix-guardrails:", 1)[1]
        self.assertIn("Install Linux guardrail sandbox", guardrails)
        self.assertIn("kernel.apparmor_restrict_unprivileged_userns", guardrails)
        self.assertIn("bwrap --unshare-net --ro-bind / /", guardrails)
        for host in ("Linux", "macOS", "Windows"):
            self.assertIn(f"release-evidence/work-graph-{host}.json", workflow)


if __name__ == "__main__":
    unittest.main()
