#!/usr/bin/env python3
"""End-to-end local graph dispatch with fake native clients and real Git worktrees."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest


ROOT = Path(__file__).resolve().parent.parent
CHILD_EXIT = re.compile(
    r"\Achild process exit=(-?[0-9]{1,5}) in (prepared|making|checking|retrying|resuming|accepted|escalated|interrupted|unknown); "
    r"exception=([A-Za-z_][A-Za-z0-9_.]{0,63}); location=(autonomous-run\.py:[1-9][0-9]{0,5}|unknown)\Z"
)


def failed_node_diagnostics(events_path: Path, child_root: Path) -> str:
    """Bound fixture failure details to event names and controller exit signatures."""
    details: list[str] = []
    if events_path.is_file():
        for raw in events_path.read_text(encoding="utf-8").splitlines()[-12:]:
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            kind, run_id = event.get("event"), event.get("run_id")
            if kind not in {"run_dispatched", "run_completed", "run_failed"} or run_id not in {"a", "b", "c"}:
                continue
            details.append(f"{kind}:{run_id}")
            signature = CHILD_EXIT.fullmatch(str(event.get("reason", ""))) if kind == "run_failed" else None
            if signature:
                details.append(f"exit={signature[1]} stage={signature[2]} "
                               f"exception={signature[3]} location={signature[4]}")
    for run_id in ("a", "b", "c"):
        path = child_root / run_id / "state.json"
        if path.is_file():
            try:
                status = json.loads(path.read_text(encoding="utf-8")).get("status")
            except (json.JSONDecodeError, OSError):
                continue
            if status in {"prepared", "making", "checking", "retrying", "resuming", "accepted", "escalated", "interrupted"}:
                details.append(f"child:{run_id}:{status}")
    return " ".join(details)[:999]


def git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(["git", *arguments], cwd=repo, text=True, capture_output=True, check=True)
    return result.stdout.strip()


class GraphDispatchTests(unittest.TestCase):
    def test_failed_node_diagnostics_exclude_paths_and_raw_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith graph diagnostics ") as temporary:
            root = Path(temporary)
            (root / "events.jsonl").write_text(json.dumps({
                "event": "run_failed", "run_id": "b",
                "reason": "child process exit=1 in making; exception=PermissionError; "
                          "location=autonomous-run.py:315",
            }) + "\n" + json.dumps({
                "event": "run_completed", "run_id": "a", "reason": "/private/secret raw output",
            }) + "\n", encoding="utf-8")
            child = root / "b" / "state.json"
            child.parent.mkdir()
            child.write_text(json.dumps({"status": "making", "reason": "ghp_secret /private/secret"}),
                             encoding="utf-8")
            details = failed_node_diagnostics(root / "events.jsonl", root)
            self.assertIn("exit=1", details)
            self.assertIn("PermissionError", details)
            self.assertIn("autonomous-run.py:315", details)
            self.assertIn("run_failed:b", details)
            self.assertIn("child:b:making", details)
            self.assertNotIn("ghp_secret", details)
            self.assertNotIn("/private/secret", details)
            self.assertLess(len(details), 1000)

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="agentsmith graph dispatch ")
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name).resolve() / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "Harness Test")
        git(self.repo, "config", "user.email", "user@example.com")
        spec = self.repo / "docs/specs/accepted.md"
        spec.parent.mkdir(parents=True)
        spec.write_text(
            "---\nstatus: accepted\ndecision_ticket: DEC-1\naccepted_by: Test Operator\n"
            "accepted_at: 2026-09-21\n---\n# Fixture\n", encoding="utf-8",
        )
        fake = Path(self.temporary.name) / "fake"
        fake.mkdir()
        (fake / "codex-home").mkdir()
        (fake / "codex-home" / "auth.json").write_text('{"auth_mode":"chatgpt"}', encoding="utf-8")
        self.fake_client = fake / "agent.py"
        self.fake_client.write_text(textwrap.dedent('''\
            import json
            from pathlib import Path
            import re
            import subprocess
            import sys
            import time

            argv = sys.argv[1:]
            prompt = argv[-1]
            match = re.search(r"Run ([A-Za-z0-9_-]+) for implementation ticket", prompt)
            if match is None:
                raise SystemExit("missing run identity")
            run_id = match.group(1)
            checker = "You are the independent checker" in prompt
            receipt_path = Path(argv[argv.index("-o") + 1]) if "-o" in argv else None
            changed = "src/shared.txt" if (Path(__file__).parent / "shared-mode").is_file() else f"src/{run_id}/change.txt"
            if not checker:
                failed_run = Path(__file__).parent / "fail-run.txt"
                if failed_run.is_file() and failed_run.read_text(encoding="utf-8").strip() == run_id:
                    raise SystemExit("configured fake maker failure")
                if run_id == "c" and not (Path("src/a/change.txt").is_file() and Path("src/b/change.txt").is_file()):
                    raise SystemExit("dependent node did not inherit predecessors")
                (Path(__file__).parent / "starts.log").open("a", encoding="utf-8").write(f"{run_id} {time.monotonic()}\\n")
                delay = Path(__file__).parent / "sleep-seconds.txt"
                time.sleep(float(delay.read_text(encoding="utf-8")) if delay.is_file() else 1.0)
                (Path(__file__).parent / "finishes.log").open("a", encoding="utf-8").write(f"{run_id} {time.monotonic()}\\n")
                path = Path(changed)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(run_id + "\\n", encoding="utf-8")
                subprocess.run(["git", "add", changed], check=True)
                committed = subprocess.run(["git", "commit", "-qm", "test: fake maker"],
                                           capture_output=True, text=True)
                if committed.returncode:
                    raise SystemExit("fake maker commit failed: " + (committed.stderr + committed.stdout).strip())
            commit = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
            status = "accepted" if checker else "completed"
            receipt = {"status": status, "summary": "fake role", "commit": commit,
                       "changed_paths": [changed], "evidence": ["fake test evidence"],
                       "unresolved": [], "next_state": status}
            if receipt_path is not None:
                receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
                print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 3, "output_tokens": 2}}))
            else:
                print(json.dumps({"type": "result", "total_cost_usd": 0.01, "structured_output": receipt}))
            '''), encoding="utf-8")
        self.environment = {
            **os.environ,
            "AGENTSMITH_CODEX_BIN": str(self.fake_client),
            "AGENTSMITH_CLAUDE_BIN": str(self.fake_client),
            "CODEX_HOME": str(fake / "codex-home"),
        }
        nodes = []
        for run_id, dependencies in (("a", []), ("b", []), ("c", ["a", "b"])):
            manifest = json.loads((ROOT / "templates/autonomous-run.json").read_text(encoding="utf-8"))
            manifest.update(run_id=run_id, spec_path="docs/specs/accepted.md", implementation_ticket=f"IMP-{run_id}")
            manifest["scope"]["allowed_paths"] = [f"src/{run_id}/**"]
            manifest["verify"]["command"] = (
                f'"{sys.executable}" -c "from pathlib import Path; assert Path(\'src/{run_id}/change.txt\').is_file()"'
            )
            manifest["limits"].update(wall_minutes=2, codex_goal_tokens=1000, claude_max_usd=1)
            path = self.repo / ".harness/runs" / f"{run_id}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
            path.write_bytes(payload)
            nodes.append({"run_id": run_id, "manifest_path": path.relative_to(self.repo).as_posix(),
                          "manifest_sha256": hashlib.sha256(payload).hexdigest(), "depends_on": dependencies})
        graph = {"schema_version": 1, "graph_id": "dispatch-fixture", "max_parallel": 2,
                 "integration_order": ["a", "b", "c"], "nodes": nodes}
        self.graph_path = ".harness/work-graph.json"
        (self.repo / self.graph_path).write_bytes((json.dumps(graph, indent=2) + "\n").encode("utf-8"))
        (self.repo / ".harness/verify.conf").write_text(
            f"combined :: \"{sys.executable}\" -c \"from pathlib import Path; assert all(Path('src/' + node + '/change.txt').is_file() for node in ('a', 'b', 'c'))\"\n",
            encoding="utf-8",
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "test: accepted graph")
        committed_graph = subprocess.run(["git", "show", f"HEAD:{self.graph_path}"],
                                         cwd=self.repo, capture_output=True, check=True).stdout
        self.assertEqual((self.repo / self.graph_path).read_bytes(), committed_graph,
                         "fixture graph must match its committed contract bytes")
        self.addCleanup(self._remove_worktrees)

    def _remove_worktrees(self) -> None:
        for path in (self.repo.parent / "repo-a", self.repo.parent / "repo-b", self.repo.parent / "repo-c",
                     self.repo.parent / "repo-dispatch-fixture-checkpoint-c",
                     self.repo.parent / "repo-dispatch-fixture-candidate-001"):
            if path.exists():
                subprocess.run(["git", "worktree", "remove", "--force", str(path)], cwd=self.repo,
                               capture_output=True, check=False)

    def invoke(self, action: str, *, diagnose_unexpected: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(ROOT / "agentsmith.py"), "graph", action, "--graph", self.graph_path,
             "--target", str(self.repo), "--json"], cwd=self.repo, env=self.environment,
            text=True, capture_output=True, check=False, timeout=180,
        )
        if diagnose_unexpected and action in {"start", "resume"} and result.returncode:
            events = self.repo / ".git/agentsmith-graphs/dispatch-fixture/events.jsonl"
            if events.is_file():
                result.stderr += "\nGraph events:\n" + events.read_text(encoding="utf-8")
            child_root = self.repo / ".git/agentsmith-runs"
            for state_path in sorted(child_root.glob("*/state.json")):
                state = json.loads(state_path.read_text(encoding="utf-8"))
                result.stderr += f"\n{state_path.parent.name}: {state.get('status')}: {state.get('reason')}\n"
                for verify_path in sorted(state_path.parent.glob("attempt-*-verify.txt")):
                    result.stderr += f"{verify_path.name}: {verify_path.read_text(encoding='utf-8')[:1000]}\n"
            for run_id in ("a", "b", "c"):
                worktree = self.repo.parent / f"repo-{run_id}"
                if worktree.is_dir():
                    dirty = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all"],
                                           cwd=worktree, env=self.environment, text=True,
                                           capture_output=True, check=False)
                    result.stderr += f"{run_id} Git status: {dirty.stdout[:1000]}{dirty.stderr[:300]}\n"
        return result

    def test_parallel_roots_and_dependent_checkpoint(self) -> None:
        started = self.invoke("start")
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        status = self.invoke("status")
        self.assertEqual(status.returncode, 0, status.stderr)
        report = json.loads(status.stdout)
        self.assertEqual(report["status"], "completed", started.stdout + started.stderr + json.dumps(report))
        self.assertEqual({node["run_id"]: node["status"] for node in report["nodes"]},
                         {"a": "completed", "b": "completed", "c": "completed"})
        child = self.repo.parent / "repo-c"
        self.assertEqual((child / "src/a/change.txt").read_text(encoding="utf-8"), "a\n")
        self.assertEqual((child / "src/b/change.txt").read_text(encoding="utf-8"), "b\n")
        starts = {
            name: float(value) for name, value in (
                line.split() for line in (self.fake_client.parent / "starts.log").read_text().splitlines()
            )
        }
        finishes = {
            name: float(value) for name, value in (
                line.split() for line in (self.fake_client.parent / "finishes.log").read_text().splitlines()
            )
        }
        self.assertLess(max(starts["a"], starts["b"]), min(finishes["a"], finishes["b"]))
        self.assertGreater(starts["c"], max(finishes["a"], finishes["b"]))
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")

    def test_failed_node_blocks_descendant_but_not_independent_peer(self) -> None:
        (self.fake_client.parent / "fail-run.txt").write_text("b", encoding="utf-8")
        started = self.invoke("start", diagnose_unexpected=False)
        details = failed_node_diagnostics(
            self.repo / ".git/agentsmith-graphs/dispatch-fixture/events.jsonl",
            self.repo / ".git/agentsmith-runs",
        )
        self.assertEqual(started.returncode, 2, details)
        report = json.loads(self.invoke("status").stdout)
        self.assertEqual({node["run_id"]: node["status"] for node in report["nodes"]},
                         {"a": "completed", "b": "failed", "c": "blocked"}, details)
        self.assertFalse((self.repo.parent / "repo-c").exists())

    def test_stop_then_resume_preserves_partial_work_and_limits(self) -> None:
        (self.fake_client.parent / "sleep-seconds.txt").write_text("20", encoding="utf-8")
        running = subprocess.Popen(
            [sys.executable, str(ROOT / "agentsmith.py"), "graph", "start", "--graph", self.graph_path,
             "--target", str(self.repo), "--json"],
            cwd=self.repo, env=self.environment, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        def reap_graph() -> None:
            if running.poll() is None:
                running.kill()
            running.communicate()
        self.addCleanup(reap_graph)
        common = Path(git(self.repo, "rev-parse", "--git-common-dir"))
        if not common.is_absolute():
            common = self.repo / common
        state_path = common / "agentsmith-graphs" / "dispatch-fixture" / "state.json"
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not (self.fake_client.parent / "starts.log").is_file():
            time.sleep(0.05)
        self.assertTrue((self.fake_client.parent / "starts.log").is_file(), "child maker did not start")
        duplicate = self.invoke("start")
        self.assertEqual(duplicate.returncode, 2, duplicate.stdout + duplicate.stderr)
        self.assertIn("already has local state", duplicate.stderr)
        stopped = self.invoke("stop")
        graph_output = running.communicate(timeout=1) if running.poll() is not None else ("", "")
        child_details = []
        for run_id in ("a", "b"):
            child_path = common / "agentsmith-runs" / run_id / "state.json"
            if child_path.is_file():
                child_details.append(child_path.read_text(encoding="utf-8"))
        self.assertEqual(stopped.returncode, 0,
                         stopped.stdout + stopped.stderr +
                         f" graph_process={running.poll()} graph_output={graph_output} child={child_details} graph_state={state_path.read_text(encoding='utf-8')}")
        running.communicate(timeout=15)
        self.assertTrue(state_path.is_file())
        saved = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertTrue(saved["stop_requested"])
        self.assertEqual(saved["status"], "stopped")
        dirty = self.repo.parent / "repo-a" / "research-notes.md"
        dirty.write_text("retain me\n", encoding="utf-8")
        refused = self.invoke("resume")
        self.assertEqual(refused.returncode, 2, refused.stdout + refused.stderr)
        self.assertEqual(json.loads(state_path.read_text(encoding="utf-8"))["status"], "stopped")
        self.assertEqual(dirty.read_text(encoding="utf-8"), "retain me\n")
        dirty.unlink()
        (self.fake_client.parent / "sleep-seconds.txt").unlink()
        # The controller checks this owner with OpenProcess on Windows. os.kill
        # sends a signal there, so the fixture uses an out-of-range test PID.
        stale_pid = 99_999_999
        (state_path.parent / "LOCK").write_text(
            json.dumps({"graph_id": "dispatch-fixture", "pid": stale_pid,
                        "token": "0" * 32}), encoding="utf-8",
        )
        resumed = self.invoke("resume")
        self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
        self.assertFalse((state_path.parent / "LOCK").exists())
        report = json.loads(self.invoke("status").stdout)
        self.assertEqual(report["status"], "completed")
        self.assertEqual(len(json.loads(state_path.read_text(encoding="utf-8"))["dispatches"]), 3)

    def test_cleanup_preview_retains_foreign_and_source_artifacts(self) -> None:
        started = self.invoke("start")
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        foreign = self.repo.parent / "repo-user-research"
        foreign.mkdir()
        (foreign / "notes.md").write_text("retain me\n", encoding="utf-8")
        preview = subprocess.run(
            [sys.executable, str(ROOT / "agentsmith.py"), "graph", "cleanup", "--preview",
             "--graph", self.graph_path, "--target", str(self.repo), "--json"],
            cwd=self.repo, env=self.environment, text=True, capture_output=True, check=False,
        )
        self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
        self.assertTrue(foreign.is_dir())
        self.assertEqual((foreign / "notes.md").read_text(encoding="utf-8"), "retain me\n")
        self.assertIn("repo-a", preview.stdout)
        self.assertNotIn("repo-user-research", preview.stdout)

    def test_changed_graph_contract_cannot_resume_stopped_run(self) -> None:
        (self.fake_client.parent / "sleep-seconds.txt").write_text("4", encoding="utf-8")
        running = subprocess.Popen(
            [sys.executable, str(ROOT / "agentsmith.py"), "graph", "start", "--graph", self.graph_path,
             "--target", str(self.repo), "--json"],
            cwd=self.repo, env=self.environment, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        def reap_graph() -> None:
            if running.poll() is None:
                running.kill()
            running.communicate()
        self.addCleanup(reap_graph)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not (self.fake_client.parent / "starts.log").is_file():
            time.sleep(0.05)
        self.assertTrue((self.fake_client.parent / "starts.log").is_file())
        stopped = self.invoke("stop")
        self.assertEqual(stopped.returncode, 0, stopped.stdout + stopped.stderr)
        running.communicate(timeout=15)
        graph_path = self.repo / self.graph_path
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        graph["max_parallel"] = 1
        graph_path.write_bytes((json.dumps(graph, indent=2) + "\n").encode("utf-8"))
        git(self.repo, "add", self.graph_path)
        git(self.repo, "commit", "-qm", "test: changed graph contract")
        refused = self.invoke("resume")
        self.assertEqual(refused.returncode, 2, refused.stdout + refused.stderr)
        self.assertIn("contract", refused.stderr)
        started_ids = {line.split()[0] for line in
                       (self.fake_client.parent / "starts.log").read_text(encoding="utf-8").splitlines()
                       if line.strip()}
        self.assertTrue(started_ids, "the stop fixture must observe a started maker")
        for run_id in started_ids:
            self.assertTrue((self.repo.parent / f"repo-{run_id}").is_dir(),
                            f"started maker {run_id} lost its source worktree")

    def test_explicit_cleanup_removes_only_clean_graph_worktree(self) -> None:
        started = self.invoke("start")
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        checkpoint = self.repo.parent / "repo-dispatch-fixture-checkpoint-c"
        self.assertTrue(checkpoint.is_dir())
        dirty = checkpoint / "research-notes.md"
        dirty.write_text("retain source material\n", encoding="utf-8")
        command = [sys.executable, str(ROOT / "agentsmith.py"), "graph", "cleanup", "--apply",
                   "--graph", self.graph_path, "--target", str(self.repo), "--json"]
        refused = subprocess.run(command, cwd=self.repo, env=self.environment, text=True,
                                 capture_output=True, check=False)
        self.assertEqual(refused.returncode, 2, refused.stdout + refused.stderr)
        self.assertTrue(dirty.is_file())
        dirty.unlink()
        applied = subprocess.run(command, cwd=self.repo, env=self.environment, text=True,
                                 capture_output=True, check=False)
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertFalse(checkpoint.exists())
        self.assertTrue((self.repo.parent / "repo-a").is_dir())
        self.assertTrue((self.repo.parent / "repo-b").is_dir())
        self.assertTrue((self.repo.parent / "repo-c").is_dir())
        self.assertTrue(git(self.repo, "show-ref", "--verify", "refs/heads/agentsmith-graph/dispatch-fixture/checkpoint/c"))
        self.assertEqual(json.loads(self.invoke("status").stdout)["status"], "completed")

    def test_integration_creates_verified_local_candidate_without_delivery(self) -> None:
        started = self.invoke("start")
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        integrated = self.invoke("integrate")
        self.assertEqual(integrated.returncode, 0, integrated.stdout + integrated.stderr)
        candidate = json.loads(integrated.stdout)
        self.assertEqual(candidate["schema_version"], 1)
        self.assertEqual(candidate["verification"]["exit_code"], 0)
        self.assertFalse(candidate["external_write_used"])
        self.assertTrue(candidate["human_approval_required"])
        self.assertEqual([item["run_id"] for item in candidate["sources"]], ["a", "b", "c"])
        self.assertEqual(git(self.repo, "remote"), "")
        self.assertEqual(git(self.repo, "rev-parse", f"refs/heads/{candidate['candidate_branch']}"),
                         candidate["candidate_commit"])
        state_path = self.repo / ".git/agentsmith-graphs/dispatch-fixture"
        receipt = state_path / "integration-candidate.json"
        self.assertEqual(json.loads(receipt.read_text(encoding="utf-8")), candidate)
        self.assertEqual(json.loads(self.invoke("status").stdout)["next_action"]["command"], "status")
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")

    def test_integration_refuses_dirty_source_without_creating_candidate(self) -> None:
        started = self.invoke("start")
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        source = self.repo.parent / "repo-a"
        (source / "research-notes.md").write_text("retain me\n", encoding="utf-8")
        integrated = self.invoke("integrate")
        self.assertEqual(integrated.returncode, 2, integrated.stdout + integrated.stderr)
        self.assertIn("dirty", integrated.stderr)
        self.assertFalse((self.repo.parent / "repo-dispatch-fixture-candidate-001").exists())
        self.assertEqual((source / "research-notes.md").read_text(encoding="utf-8"), "retain me\n")

    def test_integration_conflict_retains_both_accepted_sources(self) -> None:
        (self.fake_client.parent / "shared-mode").write_text("enabled\n", encoding="utf-8")
        graph_path = self.repo / self.graph_path
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        graph["nodes"] = graph["nodes"][:2]
        graph["integration_order"] = ["a", "b"]
        for node in graph["nodes"]:
            manifest_path = self.repo / node["manifest_path"]
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["scope"]["allowed_paths"] = ["src/shared.txt"]
            manifest["verify"]["command"] = f'"{sys.executable}" -c "from pathlib import Path; assert Path(\'src/shared.txt\').is_file()"'
            payload = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
            manifest_path.write_bytes(payload)
            node["manifest_sha256"] = hashlib.sha256(payload).hexdigest()
        graph_path.write_bytes((json.dumps(graph, indent=2) + "\n").encode("utf-8"))
        (self.repo / ".harness/verify.conf").write_text(
            f'combined :: "{sys.executable}" -c "from pathlib import Path; assert Path(\'src/shared.txt\').is_file()"\n',
            encoding="utf-8",
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "test: conflicting accepted scopes")
        started = self.invoke("start")
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        accepted = {run_id: git(self.repo, "rev-parse", f"refs/heads/agentsmith/{run_id}") for run_id in ("a", "b")}
        integrated = self.invoke("integrate")
        self.assertEqual(integrated.returncode, 2, integrated.stdout + integrated.stderr)
        self.assertIn("conflict", integrated.stderr.lower())
        self.assertEqual({run_id: git(self.repo, "rev-parse", f"refs/heads/agentsmith/{run_id}")
                          for run_id in ("a", "b")}, accepted)
        self.assertTrue((self.repo.parent / "repo-dispatch-fixture-candidate-001").is_dir())
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")

    def test_integration_retains_failed_full_verification_proof(self) -> None:
        (self.repo / ".harness/verify.conf").write_text("combined :: exit 1\n", encoding="utf-8")
        git(self.repo, "add", ".harness/verify.conf")
        git(self.repo, "commit", "-qm", "test: make combined verification fail")
        started = self.invoke("start")
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        integrated = self.invoke("integrate")
        self.assertEqual(integrated.returncode, 2, integrated.stdout + integrated.stderr)
        self.assertIn("failed full verification", integrated.stderr)
        proof = self.repo / ".git/agentsmith-graphs/dispatch-fixture/verification-001/receipt.json"
        self.assertEqual(json.loads(proof.read_text(encoding="utf-8"))["status"], "failed")
        self.assertTrue((self.repo.parent / "repo-dispatch-fixture-candidate-001").is_dir())


if __name__ == "__main__":
    unittest.main()
