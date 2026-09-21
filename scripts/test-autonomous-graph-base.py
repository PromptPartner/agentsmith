#!/usr/bin/env python3
"""Graph-owned effective-base handoff for finite autonomous runs."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("agentsmith_graph_base_test", ROOT / "scripts" / "autonomous-run.py")
assert SPEC and SPEC.loader
CONTROLLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROLLER)
GRAPH_SPEC = importlib.util.spec_from_file_location("agentsmith_work_graph_failure", ROOT / "work_graph.py")
assert GRAPH_SPEC and GRAPH_SPEC.loader
GRAPH = importlib.util.module_from_spec(GRAPH_SPEC)
GRAPH_SPEC.loader.exec_module(GRAPH)


def git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(["git", *arguments], cwd=repo, text=True, capture_output=True, check=True)
    return result.stdout.strip()


class GraphBaseTests(unittest.TestCase):
    def test_unhandled_child_failure_reports_safe_exception_location(self) -> None:
        stderr = ('Traceback (most recent call last):\n'
                  '  File "D:\\a\\agentsmith\\scripts\\autonomous-run.py", line 1382, in execute\n'
                  '    read_sensitive_value()\n'
                  'PermissionError: hidden-secret-value\n')
        reason = GRAPH.child_failure_reason({"status": "checking", "reason": None}, 1, stderr)
        self.assertIn("checking", reason)
        self.assertIn("exit=1", reason)
        self.assertIn("PermissionError", reason)
        self.assertIn("autonomous-run.py:1382", reason)
        self.assertNotIn("hidden-secret-value", reason)
        self.assertNotIn("read_sensitive_value", reason)
        self.assertNotIn("D:\\a", reason)

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="agentsmith graph base ")
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name).resolve() / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "Harness Test")
        git(self.repo, "config", "user.email", "user@example.com")
        spec = self.repo / "docs/specs/accepted.md"
        spec.parent.mkdir(parents=True)
        spec.write_text("---\nstatus: accepted\ndecision_ticket: DEC-1\naccepted_by: Test Operator\n"
                        "accepted_at: 2026-09-21\n---\n# Fixture\n", encoding="utf-8")
        nodes = []
        for run_id, dependencies in (("a", []), ("b", ["a"])):
            manifest = json.loads((ROOT / "templates/autonomous-run.json").read_text(encoding="utf-8"))
            manifest.update(run_id=run_id, spec_path="docs/specs/accepted.md",
                            implementation_ticket=f"IMP-{run_id}")
            manifest["scope"]["allowed_paths"] = [f"src/{run_id}/**"]
            path = self.repo / ".harness/runs" / f"{run_id}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
            path.write_bytes(payload)
            nodes.append({"run_id": run_id, "manifest_path": path.relative_to(self.repo).as_posix(),
                          "manifest_sha256": hashlib.sha256(payload).hexdigest(),
                          "depends_on": dependencies})
        self.graph_path = ".harness/work-graph.json"
        graph = {"schema_version": 1, "graph_id": "fixture-graph", "max_parallel": 2,
                 "integration_order": ["a", "b"], "nodes": nodes}
        graph_bytes = (json.dumps(graph, indent=2, sort_keys=True) + "\n").encode()
        (self.repo / self.graph_path).write_bytes(graph_bytes)
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "test: approved graph")
        self.contract = git(self.repo, "rev-parse", "HEAD")
        self.graph_hash = hashlib.sha256(graph_bytes).hexdigest()
        self.graph = graph
        self.created_worktrees: list[Path] = []
        self.addCleanup(self._clean_worktrees)

    def _clean_worktrees(self) -> None:
        for path in reversed(self.created_worktrees):
            if path.exists():
                subprocess.run(["git", "worktree", "remove", "--force", str(path)], cwd=self.repo,
                               text=True, capture_output=True, check=False)

    def accepted_predecessor(self) -> str:
        worktree = Path(self.temporary.name) / "predecessor"
        git(self.repo, "worktree", "add", "-q", "-b", "agentsmith/a", str(worktree), self.contract)
        self.created_worktrees.append(worktree)
        inherited = worktree / "src/a/inherited.txt"
        inherited.parent.mkdir(parents=True)
        inherited.write_text("accepted predecessor\n", encoding="utf-8")
        git(worktree, "add", ".")
        git(worktree, "commit", "-qm", "test: predecessor")
        predecessor = git(worktree, "rev-parse", "HEAD")
        git(self.repo, "branch", "agentsmith-graph/fixture-graph/checkpoint/b", predecessor)
        receipt = {"status": "accepted", "commit": predecessor}
        state_dir = self.repo / ".git/agentsmith-runs/a"
        state_dir.mkdir(parents=True)
        state = {"run_id": "a", "manifest_sha256": self.graph["nodes"][0]["manifest_sha256"],
                 "repo": str(self.repo), "status": "accepted", "branch": "agentsmith/a",
                 "base_head": self.contract, "accepted_commit": predecessor,
                 "last_checker_receipt": receipt}
        (state_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
        graph_state_dir = self.repo / ".git/agentsmith-graphs/fixture-graph"
        graph_state_dir.mkdir(parents=True)
        graph_state = {"schema_version": 1, "graph_id": "fixture-graph",
                       "graph_sha256": self.graph_hash, "contract_commit": self.contract,
                       "checkpoints": [{"run_id": "b", "base_oid": self.contract,
                                        "checkpoint_oid": predecessor,
                                        "checkpoint_tree": git(self.repo, "rev-parse", f"{predecessor}^{{tree}}"),
                                        "sources": [{"run_id": "a", "accepted_commit": predecessor,
                                                     "receipt_sha256": hashlib.sha256(json.dumps(receipt, sort_keys=True).encode()).hexdigest()}],
                                        "created_at": "2026-09-21T00:00:00Z"}]}
        (graph_state_dir / "state.json").write_text(json.dumps(graph_state), encoding="utf-8")
        return predecessor

    def _start(self, *flags: str, run_id: str = "b") -> int:
        args = CONTROLLER.parser().parse_args(["start", str(self.repo / f".harness/runs/{run_id}.json"), *flags])
        with (mock.patch.object(CONTROLLER, "repo_root", return_value=self.repo),
              mock.patch.object(CONTROLLER, "run_controller", return_value=0)):
            return CONTROLLER.start(args)

    def _repo_root(self, path: Path) -> Path:
        return self.repo if path == Path.cwd() else path.resolve()

    def test_dependent_run_inherits_pinned_checkpoint_not_manifest_head(self) -> None:
        checkpoint = self.accepted_predecessor()
        self.assertNotEqual(subprocess.run(["git", "cat-file", "-e", f"{self.contract}:src/a/inherited.txt"],
                                           cwd=self.repo, capture_output=True).returncode, 0)
        self.assertEqual(self._start("--graph", self.graph_path, "--effective-base", checkpoint), 0)
        child = self.repo.parent / "repo-b"
        self.created_worktrees.append(child)
        self.assertEqual((child / "src/a/inherited.txt").read_text(encoding="utf-8"),
                         "accepted predecessor\n")
        state = json.loads((self.repo / ".git/agentsmith-runs/b/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["base_head"], checkpoint)
        self.assertEqual(state["graph_sha256"], self.graph_hash)
        self.assertEqual(state["contract_commit"], self.contract)

    def test_root_run_must_use_exact_contract_commit(self) -> None:
        self.assertEqual(self._start("--graph", self.graph_path, "--effective-base", self.contract,
                                     run_id="a"), 0)
        child = self.repo.parent / "repo-a"
        self.created_worktrees.append(child)
        state = json.loads((self.repo / ".git/agentsmith-runs/a/state.json").read_text(encoding="utf-8"))
        self.assertEqual((state["base_head"], state["effective_base_oid"]),
                         (self.contract, self.contract))

    def test_installed_runtime_uses_sibling_graph_validator_and_fails_closed_if_missing(self) -> None:
        installed = self.repo / ".agentsmith"
        installed.mkdir()
        validator = installed / "work_graph.py"
        validator.write_text("# managed validator fixture\n", encoding="utf-8")
        with mock.patch.object(CONTROLLER, "__file__", str(installed / "autonomous-run.py")):
            self.assertEqual(CONTROLLER.graph_validator_source(), validator)
            validator.unlink()
            with self.assertRaisesRegex(CONTROLLER.RunError, "unavailable"):
                CONTROLLER.graph_validator_source()

    def test_checkpoint_cannot_change_accepted_spec_bytes(self) -> None:
        self.accepted_predecessor()
        worktree = self.repo.parent / "altered-checkpoint"
        git(self.repo, "worktree", "add", "-q", str(worktree),
            "agentsmith-graph/fixture-graph/checkpoint/b")
        self.created_worktrees.append(worktree)
        spec = worktree / "docs/specs/accepted.md"
        spec.write_text(spec.read_text(encoding="utf-8") + "\nChanged contract\n", encoding="utf-8")
        git(worktree, "add", ".")
        git(worktree, "commit", "-qm", "test: altered checkpoint spec")
        checkpoint = git(worktree, "rev-parse", "HEAD")
        graph_state_path = self.repo / ".git/agentsmith-graphs/fixture-graph/state.json"
        graph_state = json.loads(graph_state_path.read_text(encoding="utf-8"))
        graph_state["checkpoints"][0]["checkpoint_oid"] = checkpoint
        graph_state["checkpoints"][0]["checkpoint_tree"] = git(self.repo, "rev-parse", f"{checkpoint}^{{tree}}")
        graph_state_path.write_text(json.dumps(graph_state), encoding="utf-8")
        with self.assertRaisesRegex(CONTROLLER.RunError, "accepted spec bytes changed"):
            self._start("--graph", self.graph_path, "--effective-base", checkpoint)
        self.assertFalse((self.repo / ".git/agentsmith-runs/b/state.json").exists())

    def test_arbitrary_base_and_graph_contract_drift_are_rejected_without_child_artifacts(self) -> None:
        checkpoint = self.accepted_predecessor()
        with self.assertRaisesRegex(CONTROLLER.RunError, "checkpoint|effective base"):
            self._start("--graph", self.graph_path, "--effective-base", self.contract)
        with self.assertRaisesRegex(CONTROLLER.RunError, "40|hex|effective base"):
            self._start("--graph", self.graph_path, "--effective-base", "abc")
        self.assertFalse((self.repo / ".git/agentsmith-runs/b/state.json").exists())
        self.assertFalse((self.repo.parent / "repo-b").exists())
        self.assertNotEqual(subprocess.run(["git", "show-ref", "--verify", "refs/heads/agentsmith/b"],
                                          cwd=self.repo, capture_output=True).returncode, 0)
        # A committed graph change invalidates the prior checkpoint receipt and contract OID.
        self.graph["max_parallel"] = 1
        (self.repo / self.graph_path).write_text(json.dumps(self.graph, sort_keys=True) + "\n", encoding="utf-8")
        git(self.repo, "add", self.graph_path)
        git(self.repo, "commit", "-qm", "test: changed graph")
        with self.assertRaises(CONTROLLER.RunError):
            self._start("--graph", self.graph_path, "--effective-base", checkpoint)

    def test_resume_revalidates_checkpoint_without_resetting_child_limits(self) -> None:
        checkpoint = self.accepted_predecessor()
        self.assertEqual(self._start("--graph", self.graph_path, "--effective-base", checkpoint), 0)
        child = self.repo.parent / "repo-b"
        self.created_worktrees.append(child)
        state_path = self.repo / ".git/agentsmith-runs/b/state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state.update(status="interrupted", attempt=2, codex_tokens_used=17,
                     claude_cost_usd=1.25)
        state_path.write_text(json.dumps(state), encoding="utf-8")
        args = CONTROLLER.parser().parse_args(["resume", "b"])
        with (mock.patch.object(CONTROLLER, "repo_root", side_effect=self._repo_root),
              mock.patch.object(CONTROLLER, "run_controller", return_value=0)):
            self.assertEqual(CONTROLLER.resume(args), 0)
        resumed = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual((resumed["attempt"], resumed["codex_tokens_used"], resumed["claude_cost_usd"]),
                         (2, 17, 1.25))
        graph_state_path = self.repo / ".git/agentsmith-graphs/fixture-graph/state.json"
        graph_state = json.loads(graph_state_path.read_text(encoding="utf-8"))
        graph_state["checkpoints"][0]["checkpoint_oid"] = self.contract
        graph_state_path.write_text(json.dumps(graph_state), encoding="utf-8")
        with (mock.patch.object(CONTROLLER, "repo_root", side_effect=self._repo_root),
              mock.patch.object(CONTROLLER, "run_controller", return_value=0)):
            with self.assertRaisesRegex(CONTROLLER.RunError, "checkpoint|graph"):
                CONTROLLER.resume(args)
        unchanged = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual((unchanged["attempt"], unchanged["codex_tokens_used"],
                          unchanged["claude_cost_usd"]), (2, 17, 1.25))


if __name__ == "__main__":
    unittest.main()
