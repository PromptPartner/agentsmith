#!/usr/bin/env python3
"""Inbox contracts: every row is derived from run, graph and spec state on each call, re-checked
against Git, and the list itself writes nothing. Claims are the one local write, outside the tree."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
import inbox  # noqa: E402

CORE = ROOT / "agentsmith.py"
CLEAN_ENV = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
GIT_ENV = {**CLEAN_ENV, "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "user@example.com",
           "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "user@example.com",
           "GIT_AUTHOR_DATE": "2026-11-01T00:00:00+0000", "GIT_COMMITTER_DATE": "2026-11-01T00:00:00+0000"}
NOW = 1_762_387_200.0  # a fixed clock: every age in these tests is relative to it
POLICY = json.dumps({"schema_version": 1, "rules": [{"paths": ["**"], "tier": "A"}]}).encode()
READ_ONLY_GH = {("auth", "status"), ("issue", "list"), ("pr", "list"), ("repo", "view")}


def iso(seconds_before_now: float) -> str:
    import datetime as dt
    return dt.datetime.fromtimestamp(NOW - seconds_before_now, dt.timezone.utc).isoformat(timespec="seconds")


class Repo:
    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(parents=True)
        self.git("init", "-q", "-b", "master")
        self.git("config", "commit.gpgsign", "false")
        self.common = Path(self.git("rev-parse", "--path-format=absolute", "--git-common-dir"))

    def git(self, *args: str) -> str:
        return subprocess.run(["git", "-C", str(self.root), *args], env=GIT_ENV, capture_output=True,
                              check=True).stdout.decode("utf-8").strip()

    def commit(self, files: dict[str, bytes], message: str) -> str:
        for name, content in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            self.git("add", "--", name)
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def branch(self, name: str, start: str, files: dict[str, bytes]) -> str:
        self.git("switch", "-q", "-c", name, start)
        commit = self.commit(files, f"work on {name}")
        self.git("switch", "-q", "master")
        return commit

    def run_state(self, run_id: str, **fields: object) -> Path:
        directory = self.common / "agentsmith-runs" / run_id
        directory.mkdir(parents=True, exist_ok=True)
        state = {"schema_version": 1, "run_id": run_id, "attempt": 1, "branch": f"agentsmith/{run_id}",
                 "worktree": str(self.root.parent / f"repo-{run_id}"), "state_path": str(directory / "state.json"),
                 "updated_at": iso(3600), "started_at": iso(7200), "active_pid": None, **fields}
        (directory / "state.json").write_text(json.dumps(state), encoding="utf-8")
        return directory


def dead_pid() -> int:
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    process.wait()
    return process.pid


class InboxCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="agentsmith inbox ")
        self.repo = Repo(Path(self.temporary.name) / "repo")
        self.base = self.repo.commit({".harness/risk-policy.json": POLICY, "README.md": b"x\n"}, "base")
        self.repo.git("update-ref", "refs/remotes/origin/master", self.base)
        self.repo.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/master")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def collect(self, **kwargs: object) -> dict:
        return inbox.collect(self.repo.root, now=lambda: NOW, **kwargs)

    def rows(self, report: dict) -> dict:
        return {(row["kind"], row["id"]): row for row in report["rows"]}


class RowKindTests(InboxCase):
    def test_every_row_kind_is_derived(self) -> None:
        accepted = self.repo.branch("agentsmith/acc", self.base, {"src/a.py": b"a\n"})
        self.repo.run_state("acc", status="accepted", base_head=self.base, accepted_commit=accepted)
        escalated = self.repo.branch("agentsmith/esc", self.base, {"docs/x.md": b"x\n"})
        self.repo.run_state("esc", status="escalated", base_head=self.base, reason="attempt cap reached (3)")
        self.repo.branch("agentsmith/int", self.base, {"src/b.py": b"b\n"})
        self.repo.run_state("int", status="interrupted", base_head=self.base, reason="stopped by operator")
        self.repo.branch("agentsmith/dead", self.base, {"src/c.py": b"c\n"})
        dead_dir = self.repo.run_state("dead", status="making", base_head=self.base, active_pid=dead_pid())
        (dead_dir / "controller.lock").write_text(json.dumps({"pid": dead_pid(), "token": "t"}), encoding="utf-8")
        candidate = self.repo.branch("agentsmith-graph/g1/candidate/001", self.base, {"src/d.py": b"d\n"})
        graph = self.repo.common / "agentsmith-graphs" / "g1"
        graph.mkdir(parents=True)
        (graph / "integration-candidate.json").write_text(json.dumps({
            "graph_id": "g1", "base_oid": self.base, "candidate_branch": "agentsmith-graph/g1/candidate/001",
            "candidate_commit": candidate, "created_at": iso(600), "human_approval_required": True}), encoding="utf-8")
        self.repo.commit({"docs/specs/new-thing.md": b"---\nstatus: draft\nroute: direct - small\n---\n# Spec\n",
                          "docs/specs/done.md": b"---\nstatus: accepted\n---\n# Spec\n",
                          ".harness/runs/next.json": json.dumps({"run_id": "next", "spec_path": "docs/specs/new-thing.md"}).encode(),
                          ".harness/runs/acc.json": json.dumps({"run_id": "acc", "spec_path": "docs/specs/done.md"}).encode()},
                         "specs and manifests")
        report = self.collect()
        rows = self.rows(report)
        self.assertEqual(set(rows), {("accepted", "acc"), ("escalated", "esc"), ("interrupted", "int"), ("dead", "dead"),
                                     ("integration", "g1"), ("spec", "docs/specs/new-thing.md"),
                                     ("manifest", ".harness/runs/next.json")}, report)
        self.assertEqual(report["warnings"], [])
        self.assertEqual(rows[("accepted", "acc")]["tier"], "A")
        self.assertEqual(rows[("integration", "g1")]["tier"], "A")
        self.assertEqual(rows[("escalated", "esc")]["tier"], "A")
        self.assertIsNone(rows[("spec", "docs/specs/new-thing.md")]["tier"])
        self.assertEqual(rows[("escalated", "esc")]["age_seconds"], 3600)
        self.assertEqual(rows[("integration", "g1")]["age"], "10m")
        self.assertIn("attempt cap reached (3)", rows[("escalated", "esc")]["next_step"])
        for row in report["rows"]:
            self.assertTrue(row["next_step"] and "\n" not in row["next_step"], row)
        self.assertEqual(escalated, self.repo.git("rev-parse", "agentsmith/esc"))

    def test_live_and_landed_work_is_not_waiting(self) -> None:
        live = self.repo.run_state("live", status="making", base_head=self.base)
        (live / "controller.lock").write_text(json.dumps({"pid": os.getpid(), "token": "t"}), encoding="utf-8")
        self.repo.git("branch", "agentsmith/live", self.base)
        landed = self.repo.branch("agentsmith/landed", self.base, {"src/a.py": b"a\n"})
        self.repo.run_state("landed", status="accepted", base_head=self.base, accepted_commit=landed)
        self.repo.git("update-ref", "refs/remotes/origin/master", landed)
        self.assertEqual(self.collect()["rows"], [])


class OriginBaseTests(InboxCase):
    def test_a_dangling_origin_head_falls_back_to_an_existing_base_with_a_warning(self) -> None:
        landed = self.repo.branch("agentsmith/landed", self.base, {"src/a.py": b"a\n"})
        self.repo.run_state("landed", status="accepted", base_head=self.base, accepted_commit=landed)
        self.repo.git("update-ref", "refs/remotes/origin/master", landed)
        self.repo.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/deleted-main")
        report = self.collect()
        self.assertEqual(report["rows"], [], report)
        self.assertTrue(any("origin/HEAD" in warning and "origin/master" in warning for warning in report["warnings"]),
                        report["warnings"])

    def test_a_named_base_that_is_missing_is_a_warning_not_a_silent_fallback(self) -> None:
        landed = self.repo.branch("agentsmith/landed", self.base, {"src/a.py": b"a\n"})
        self.repo.run_state("landed", status="accepted", base_head=self.base, accepted_commit=landed)
        self.repo.git("update-ref", "refs/remotes/origin/master", landed)
        report = self.collect(base="release")
        self.assertEqual([row["id"] for row in report["rows"]], ["landed"])
        self.assertTrue(any("origin/release" in warning for warning in report["warnings"]), report["warnings"])


class ContradictionTests(InboxCase):
    def test_rows_that_contradict_git_are_dropped_with_a_warning(self) -> None:
        self.repo.run_state("gone", status="escalated", base_head=self.base, reason="x")
        rewritten = self.repo.branch("agentsmith/rewritten", self.base, {"src/a.py": b"a\n"})
        self.repo.run_state("rewritten", status="accepted", base_head=self.base, accepted_commit=rewritten)
        self.repo.git("branch", "-f", "agentsmith/rewritten", self.base)
        self.repo.run_state("ghost", status="accepted", base_head=self.base, accepted_commit="f" * 40)
        self.repo.git("branch", "agentsmith/ghost", self.base)
        graph = self.repo.common / "agentsmith-graphs" / "g2"
        graph.mkdir(parents=True)
        (graph / "integration-candidate.json").write_text(json.dumps({
            "graph_id": "g2", "base_oid": self.base, "candidate_branch": "agentsmith-graph/g2/candidate/001",
            "candidate_commit": "e" * 40, "created_at": iso(60), "human_approval_required": True}), encoding="utf-8")
        broken = self.repo.common / "agentsmith-runs" / "broken"
        broken.mkdir(parents=True)
        (broken / "state.json").write_text("{not json", encoding="utf-8")
        report = self.collect()
        self.assertEqual(report["rows"], [])
        joined = "\n".join(report["warnings"])
        for name in ("gone", "rewritten", "ghost", "g2", "broken"):
            self.assertIn(name, joined)
        self.assertEqual(len(report["warnings"]), 5, report["warnings"])


class MalformedStateTests(InboxCase):
    def test_a_malformed_run_state_becomes_a_warning_and_other_rows_stay(self) -> None:
        self.repo.branch("agentsmith/good", self.base, {"src/a.py": b"a\n"})
        self.repo.run_state("good", status="escalated", base_head=self.base, reason="needs operator")
        for name, fields in (("list-status", {"status": []}), ("dict-branch", {"status": "escalated", "branch": {}}),
                             ("odd-pid", {"status": "making", "active_pid": [1]}),
                             ("odd-times", {"status": "interrupted", "updated_at": [], "base_head": 5})):
            self.repo.run_state(name, **{"base_head": self.base, **fields})
        report = self.collect()
        self.assertEqual([(row["kind"], row["id"]) for row in report["rows"]], [("escalated", "good")], report)
        for name in ("list-status", "dict-branch", "odd-pid", "odd-times"):
            self.assertTrue(any(warning.startswith(f"run {name}:") for warning in report["warnings"]), report["warnings"])


class NoWriteTests(InboxCase):
    def snapshot(self) -> dict[str, str]:
        files = {}
        for top in (self.repo.root,):
            for path in sorted(top.rglob("*")):
                if path.is_file():
                    stat = path.stat()
                    files[str(path)] = f"{stat.st_size}:{stat.st_mtime_ns}:{hashlib.sha256(path.read_bytes()).hexdigest()}"
                elif path.is_dir():
                    files[str(path)] = "dir"
        return files

    def test_listing_writes_no_file_in_the_tree_or_the_git_directory(self) -> None:
        accepted = self.repo.branch("agentsmith/acc", self.base, {"src/a.py": b"a\n"})
        self.repo.run_state("acc", status="accepted", base_head=self.base, accepted_commit=accepted)
        self.repo.commit({"docs/specs/s.md": b"---\nstatus: draft\n---\n"}, "spec")
        (self.repo.root / "docs" / "specs" / "s.md").write_bytes(b"---\nstatus: draft\n---\nedited\n")
        before = self.snapshot()
        self.collect()
        result = subprocess.run([sys.executable, str(CORE), "inbox", "--target", str(self.repo.root), "--json"],
                                env={**CLEAN_ENV, "PYTHONDONTWRITEBYTECODE": ""}, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.snapshot(), before)


class FakeGh:
    def __init__(self, issues: list, prs: list) -> None:
        self.issues, self.prs, self.calls = issues, prs, []

    def __call__(self, argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        verb = tuple(argv[1:3])
        # `gh auth status` prints text, not JSON (recorded from gh 2.101.0).
        value = {("auth", "status"): "github.com\n  Logged in to github.com account owner (keyring)\n", ("issue", "list"): self.issues, ("pr", "list"): self.prs,
                 ("repo", "view"): {"nameWithOwner": "owner/name"}}[verb]
        return subprocess.CompletedProcess(argv, 0, value if isinstance(value, str) else json.dumps(value), "")


class GitHubTests(InboxCase):
    ISSUES = [{"number": 12, "title": "Crash on start", "createdAt": iso(86400 * 3), "labels": [{"name": "bug"}],
               "url": "https://github.com/owner/name/issues/12"},
              {"number": 13, "title": "Idea", "createdAt": iso(3600), "labels": [], "url": "https://github.com/owner/name/issues/13"}]

    def test_issues_are_untriaged_rows_with_claims_and_reads_only(self) -> None:
        accepted = self.repo.branch("agentsmith/acc", self.base, {"src/a.py": b"a\n"})
        self.repo.run_state("acc", status="accepted", base_head=self.base, accepted_commit=accepted)
        inbox.claim(self.repo.root, 12, now=lambda: NOW)
        fake = FakeGh(self.ISSUES, [{"number": 70, "headRefOid": accepted, "url": "https://github.com/owner/name/pull/70"}])
        report = self.collect(gh=inbox.Gh(runner=fake, which=lambda _: "gh"), repo_name="owner/name")
        rows = self.rows(report)
        # The accepted commit is an open pull request's head, so it waits on that PR, not here.
        self.assertNotIn(("accepted", "acc"), rows)
        self.assertEqual(rows[("untriaged", "#12")]["age"], "3d")
        self.assertIn("claimed", rows[("untriaged", "#12")]["next_step"])
        self.assertIn("draft disposition", rows[("untriaged", "#13")]["next_step"])
        for argv in fake.calls:
            self.assertIn(tuple(argv[1:3]), READ_ONLY_GH, argv)

    def test_without_issues_gh_is_never_used(self) -> None:
        real_run = subprocess.run

        def guarded(argv, *args, **kwargs):
            if argv and argv[0] == "gh":
                raise AssertionError(f"gh called without --issues: {argv}")
            return real_run(argv, *args, **kwargs)
        with mock.patch("inbox.shutil.which", side_effect=AssertionError("gh looked up")), \
                mock.patch("inbox.subprocess.run", side_effect=guarded):
            self.collect()

    def test_missing_gh_fails_clearly_only_for_issues(self) -> None:
        with self.assertRaisesRegex(inbox.GhError, "GitHub CLI .gh. is not installed"):
            self.collect(gh=inbox.Gh(runner=FakeGh([], []), which=lambda _: None))
        if os.name == "nt":
            return  # a PATH with git but without gh needs a symbolic link; the in-process check covers Windows
        tools = Path(self.temporary.name) / "git-only"
        tools.mkdir()
        (tools / "git").symlink_to(shutil.which("git"))
        env = {**CLEAN_ENV, "PATH": str(tools)}
        result = subprocess.run([sys.executable, str(CORE), "inbox", "--target", str(self.repo.root), "--issues"],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("GitHub CLI (gh) is not installed", result.stderr)
        plain = subprocess.run([sys.executable, str(CORE), "inbox", "--target", str(self.repo.root)],
                               env=env, capture_output=True, text=True)
        self.assertEqual(plain.returncode, 0, plain.stderr)


class ClaimTests(InboxCase):
    def test_one_claim_per_item_outside_the_tracked_tree(self) -> None:
        path = inbox.claim(self.repo.root, 12, now=lambda: NOW)
        self.assertTrue(path.is_relative_to(self.repo.common))
        self.assertEqual(self.repo.git("status", "--porcelain"), "")
        with self.assertRaisesRegex(inbox.ClaimError, "already claimed"):
            inbox.claim(self.repo.root, 12, now=lambda: NOW)
        inbox.release(self.repo.root, 12)
        with self.assertRaisesRegex(inbox.ClaimError, "not claimed"):
            inbox.release(self.repo.root, 12)
        inbox.claim(self.repo.root, 12, now=lambda: NOW)

    def test_cli_claim_twice_exits_2(self) -> None:
        command = [sys.executable, str(CORE), "inbox", "claim", "7", "--target", str(self.repo.root)]
        first = subprocess.run(command, env=CLEAN_ENV, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        second = subprocess.run(command, env=CLEAN_ENV, capture_output=True, text=True)
        self.assertEqual(second.returncode, 2)
        self.assertIn("already claimed", second.stderr)
        released = subprocess.run([*command[:3], "release", "7", "--target", str(self.repo.root)],
                                  env=CLEAN_ENV, capture_output=True, text=True)
        self.assertEqual(released.returncode, 0, released.stderr)


if __name__ == "__main__":
    unittest.main()
