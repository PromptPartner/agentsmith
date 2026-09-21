#!/usr/bin/env python3
"""Read-only work-graph CLI contracts, exercised through a disposable Git repository."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "agentsmith.py"
TEMPLATE = ROOT / "templates" / "autonomous-run.json"


def git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(["git", *arguments], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def invoke(repo: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), "graph", *arguments, "--target", str(repo), "--json"],
        cwd=repo, capture_output=True, text=True, check=False,
    )


class WorkGraphStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="agentsmith graph status ")
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "Harness Test")
        git(self.repo, "config", "user.email", "user@example.com")
        spec = self.repo / "docs" / "specs" / "accepted.md"
        spec.parent.mkdir(parents=True)
        spec.write_text(
            "---\nstatus: accepted\ndecision_ticket: DEC-1\naccepted_by: Test Operator\n"
            "accepted_at: 2026-09-21\n---\n# Fixture\n", encoding="utf-8",
        )
        graph_nodes = []
        for run_id, scope, dependencies in (
            ("a", "src/a/**", []), ("b", "src/b/**", []), ("c", "src/c/**", ["a", "b"]),
        ):
            manifest = json.loads(TEMPLATE.read_text(encoding="utf-8"))
            manifest.update(run_id=run_id, spec_path="docs/specs/accepted.md", implementation_ticket=f"IMP-{run_id}")
            manifest["scope"]["allowed_paths"] = [scope]
            path = self.repo / ".harness" / "runs" / f"{run_id}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
            path.write_bytes(payload)
            graph_nodes.append({
                "run_id": run_id,
                "manifest_path": path.relative_to(self.repo).as_posix(),
                "manifest_sha256": hashlib.sha256(payload).hexdigest(),
                "depends_on": dependencies,
            })
        self.graph_path = self.repo / ".harness" / "work-graph.json"
        self.graph = {
            "schema_version": 1, "graph_id": "fixture-graph", "max_parallel": 2,
            "integration_order": ["a", "b", "c"], "nodes": graph_nodes,
        }
        self._write_graph()
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "test: accepted graph fixture")

    def _write_graph(self) -> None:
        self.graph_path.write_bytes((json.dumps(self.graph, indent=2, sort_keys=True) + "\n").encode())

    def test_validate_and_status_are_read_only(self) -> None:
        before_head = git(self.repo, "rev-parse", "HEAD")
        before_refs = git(self.repo, "show-ref")
        validated = invoke(self.repo, "validate", "--graph", ".harness/work-graph.json")
        self.assertEqual(validated.returncode, 0, validated.stderr)
        report = json.loads(validated.stdout)
        self.assertEqual(report["graph_id"], "fixture-graph")
        self.assertEqual(report["contract_commit"], before_head)

        status = invoke(self.repo, "status", "--graph", ".harness/work-graph.json")
        self.assertEqual(status.returncode, 0, status.stderr)
        nodes = {node["run_id"]: node for node in json.loads(status.stdout)["nodes"]}
        self.assertEqual({key: nodes[key]["status"] for key in nodes},
                         {"a": "ready", "b": "ready", "c": "waiting"})
        self.assertIn("a", nodes["c"]["reason"])
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), before_head)
        self.assertEqual(git(self.repo, "show-ref"), before_refs)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertFalse((self.repo / ".git" / "agentsmith-graphs").exists())

    def test_cycle_and_contract_drift_fail_before_writes(self) -> None:
        self.graph["nodes"][0]["depends_on"] = ["c"]
        self._write_graph()
        drift = invoke(self.repo, "validate", "--graph", ".harness/work-graph.json")
        self.assertNotEqual(drift.returncode, 0)
        self.assertIn("committed", drift.stderr.lower())
        git(self.repo, "add", ".harness/work-graph.json")
        git(self.repo, "commit", "-qm", "test: invalid cycle fixture")
        cycle = invoke(self.repo, "validate", "--graph", ".harness/work-graph.json")
        self.assertNotEqual(cycle.returncode, 0)
        self.assertIn("cycle", cycle.stderr.lower())
        self.assertFalse((self.repo / ".git" / "agentsmith-graphs").exists())

    def test_malformed_order_fails_as_a_contract_error(self) -> None:
        self.graph["integration_order"][0] = ["a"]
        self._write_graph()
        git(self.repo, "add", ".harness/work-graph.json")
        git(self.repo, "commit", "-qm", "test: malformed order fixture")
        result = invoke(self.repo, "validate", "--graph", ".harness/work-graph.json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("integration_order", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_scope_collision_waits_without_rejecting_valid_graph(self) -> None:
        path = self.repo / ".harness" / "runs" / "b.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["scope"]["allowed_paths"] = ["src/a/nested/**"]
        payload = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
        path.write_bytes(payload)
        self.graph["nodes"][1]["manifest_sha256"] = hashlib.sha256(payload).hexdigest()
        self._write_graph()
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "test: conflicting scope fixture")
        result = invoke(self.repo, "status", "--graph", ".harness/work-graph.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        nodes = {node["run_id"]: node for node in json.loads(result.stdout)["nodes"]}
        self.assertEqual(nodes["a"]["status"], "ready")
        self.assertEqual(nodes["b"]["status"], "conflicting")
        self.assertIn("a", nodes["b"]["reason"])

    def test_unsafe_scope_and_zero_budget_are_rejected(self) -> None:
        path = self.repo / ".harness" / "runs" / "a.json"
        original_manifest = json.loads(path.read_text(encoding="utf-8"))
        for key, value, phrase in (
            ("scope", [".git/**"], "scope"),
            ("limits", 0, "budget"),
        ):
            with self.subTest(key=key):
                manifest = json.loads(json.dumps(original_manifest))
                if key == "scope":
                    manifest["scope"]["allowed_paths"] = value
                else:
                    manifest["limits"]["codex_goal_tokens"] = value
                payload = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
                path.write_bytes(payload)
                self.graph["nodes"][0]["manifest_sha256"] = hashlib.sha256(payload).hexdigest()
                self._write_graph()
                git(self.repo, "add", ".")
                git(self.repo, "commit", "-qm", f"test: invalid {key} fixture")
                result = invoke(self.repo, "validate", "--graph", ".harness/work-graph.json")
                self.assertEqual(result.returncode, 2)
                self.assertIn(phrase, result.stderr.lower())
                self.assertNotIn("Traceback", result.stderr)

    def test_graph_state_symlink_is_rejected_without_external_write(self) -> None:
        outside = Path(self.temporary.name) / "foreign-state"
        outside.mkdir()
        link = self.repo / ".git" / "agentsmith-graphs"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        result = invoke(self.repo, "status", "--graph", ".harness/work-graph.json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("symlink", result.stderr)
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
