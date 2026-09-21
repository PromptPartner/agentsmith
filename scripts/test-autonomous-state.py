#!/usr/bin/env python3
"""Cross-platform tests for autonomous state atomicity and lifecycle ownership."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
CONTROLLER_PATH = ROOT / "scripts" / "autonomous-run.py"
SPEC = importlib.util.spec_from_file_location("agentsmith_autonomous_state", CONTROLLER_PATH)
assert SPEC and SPEC.loader
CONTROLLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROLLER)


class AutonomousStateTests(unittest.TestCase):
    def test_legacy_scope_defaults_to_no_coordinated_resources(self) -> None:
        scope = {"allowed_paths": ["src/**"], "denied_paths": []}
        self.assertEqual(CONTROLLER.scope_resources(scope), [])
        self.assertNotIn("resources", scope)

    def test_resource_keys_are_lowercase_unique_coordination_identifiers(self) -> None:
        valid = ["port:3000", "db:local/test", "service:redis"]
        self.assertEqual(CONTROLLER.scope_resources({"resources": valid}), valid)

        for invalid in (
            ["PORT:3000"],
            ["port:Local"],
            ["port"],
            ["port:"],
            [":3000"],
            ["port:3000 extra"],
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(CONTROLLER.RunError, "scope.resources"):
                    CONTROLLER.scope_resources({"resources": invalid})

        with self.assertRaisesRegex(CONTROLLER.RunError, "unique"):
            CONTROLLER.scope_resources({"resources": ["port:3000", "port:3000"]})

    def test_fixed_prefix_stops_before_the_first_glob_segment(self) -> None:
        cases = {
            "src/**": "src",
            "src/components/*.tsx": "src/components",
            "docs/[ab]*/index.md": "docs",
            "README.md": "README.md",
            "**/*.md": ".",
            "*": ".",
        }
        for pattern, expected in cases.items():
            with self.subTest(pattern=pattern):
                self.assertEqual(CONTROLLER.fixed_prefix(pattern), expected)

    def test_scope_paths_reject_dot_segments_that_can_hide_overlap(self) -> None:
        with self.assertRaisesRegex(CONTROLLER.RunError, "repository-relative"):
            CONTROLLER.normalized_scope({"allowed_paths": ["src/./**"]})

    def test_unlocked_state_cannot_exempt_a_self_declared_git_ref(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith forged state ") as temporary:
            common = Path(temporary)
            run_dir = common / "agentsmith-runs" / "evil"
            run_dir.mkdir(parents=True)
            CONTROLLER.write_json(
                run_dir / "state.json",
                {"run_id": "evil", "branch": "agentsmith/evil"},
            )

            refs, logs, worktrees = CONTROLLER.registered_run_git_artifacts(
                common, "refs/heads/agentsmith/active"
            )

            self.assertEqual(refs, set())
            self.assertEqual(logs, set())
            self.assertEqual(worktrees, set())

    def test_prefix_overlap_is_segment_aware_and_bidirectional(self) -> None:
        self.assertTrue(CONTROLLER.prefixes_overlap("src", "src/widgets"))
        self.assertTrue(CONTROLLER.prefixes_overlap("src/widgets", "src"))
        self.assertTrue(CONTROLLER.prefixes_overlap("src", "src"))
        self.assertFalse(CONTROLLER.prefixes_overlap("src", "src2"))
        self.assertFalse(CONTROLLER.prefixes_overlap("docs", "src"))

    def test_wildcard_root_reserves_the_whole_repository(self) -> None:
        broad = {"allowed_paths": ["**/*.md"]}
        narrow = {"allowed_paths": ["src/**"]}
        self.assertEqual(CONTROLLER.scope_collision(broad, narrow), ("path", "."))
        self.assertEqual(CONTROLLER.scope_collision(narrow, broad), ("path", "."))

    def test_scope_collision_names_shared_paths_or_resources(self) -> None:
        parent = {"allowed_paths": ["src/**"], "resources": ["port:3000"]}
        child = {"allowed_paths": ["src/widgets/**"], "resources": ["service:redis"]}
        other_path_same_resource = {
            "allowed_paths": ["docs/**"],
            "resources": ["port:3000"],
        }
        disjoint = {"allowed_paths": ["tests/**"], "resources": ["db:local/test"]}

        self.assertEqual(CONTROLLER.scope_collision(parent, child), ("path", "src"))
        self.assertEqual(
            CONTROLLER.scope_collision(parent, other_path_same_resource),
            ("resource", "port:3000"),
        )
        self.assertIsNone(CONTROLLER.scope_collision(parent, disjoint))

    def test_atomic_replace_retries_a_transient_windows_sharing_denial(self) -> None:
        denial = PermissionError("destination is momentarily shared")
        denial.winerror = 5
        with (
            mock.patch.object(CONTROLLER.os, "name", "nt"),
            mock.patch.object(CONTROLLER.os, "replace", side_effect=[denial, None]) as replace,
            mock.patch.object(CONTROLLER.time, "sleep") as pause,
        ):
            CONTROLLER.replace_file(Path("source"), Path("destination"))
        self.assertEqual(replace.call_count, 2)
        pause.assert_called_once_with(0.01)

    def test_json_read_retries_a_transient_windows_sharing_denial(self) -> None:
        path = Path("state.json")
        denial = PermissionError(errno.EACCES, "destination is momentarily shared")
        with (
            mock.patch.object(CONTROLLER.os, "name", "nt"),
            mock.patch.object(
                Path,
                "read_text",
                side_effect=[denial] * 150 + ['{"ready": true}'],
            ) as read,
            mock.patch.object(CONTROLLER.time, "sleep") as pause,
        ):
            self.assertEqual(CONTROLLER.load_json(path), {"ready": True})
        self.assertEqual(read.call_count, 151)
        self.assertEqual(pause.call_count, 150)
        pause.assert_called_with(0.01)

    def test_process_liveness_recognizes_current_and_missing_processes(self) -> None:
        self.assertTrue(CONTROLLER.process_is_live(os.getpid()))
        stale_pid = next(
            pid for pid in range(99_999_999, 99_999_900, -1)
            if not CONTROLLER.process_is_live(pid)
        )
        self.assertFalse(CONTROLLER.process_is_live(stale_pid))

    def test_concurrent_atomic_writers_never_expose_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith state ü ") as temporary:
            path = Path(temporary) / "run with spaces" / "state.json"
            CONTROLLER.write_json(path, {"writer": -1, "sequence": -1})
            finished = threading.Event()
            failures: list[BaseException] = []

            def observe() -> None:
                while not finished.is_set():
                    try:
                        value = CONTROLLER.load_json(path)
                        if not isinstance(value.get("writer"), int):
                            raise AssertionError("state record lost its writer field")
                    except BaseException as exc:  # captured and asserted on the main test thread
                        failures.append(exc)
                        finished.set()

            observer = threading.Thread(target=observe)
            observer.start()
            try:
                with ThreadPoolExecutor(max_workers=8) as pool:
                    futures = [
                        pool.submit(CONTROLLER.write_json, path, {"writer": writer, "sequence": sequence})
                        for writer in range(8) for sequence in range(25)
                    ]
                    for future in futures:
                        future.result()
            finally:
                finished.set()
                observer.join()
            self.assertEqual(failures, [])
            json.loads(path.read_text(encoding="utf-8"))

    def test_live_lock_refusal_release_and_stale_recovery(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith lock ") as temporary:
            run_dir = Path(temporary)
            token = CONTROLLER.acquire_lifecycle_lock(run_dir, "fixture")
            with self.assertRaisesRegex(CONTROLLER.RunError, "live controller"):
                CONTROLLER.acquire_lifecycle_lock(run_dir, "fixture")
            CONTROLLER.release_lifecycle_lock(run_dir, token)
            self.assertFalse(CONTROLLER.lock_path(run_dir).exists())
            stale_pid = next(pid for pid in range(99_999_999, 99_999_900, -1) if not CONTROLLER.process_is_live(pid))
            CONTROLLER.lock_path(run_dir).write_text(
                json.dumps({"pid": stale_pid, "run_id": "fixture", "token": "stale"}) + "\n",
                encoding="utf-8",
            )
            recovered = CONTROLLER.acquire_lifecycle_lock(run_dir, "fixture")
            self.assertNotEqual(recovered, "stale")
            CONTROLLER.release_lifecycle_lock(run_dir, recovered)

    def test_repository_coordination_lock_serializes_and_reclaims_stale_owner(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith coordination ") as temporary:
            root = Path(temporary)
            first_entered = threading.Event()
            second_attempted = threading.Event()
            second_entered = threading.Event()
            release_first = threading.Event()
            observed_lock: list[Path] = []

            def first() -> None:
                with CONTROLLER.coordination_lock(root):
                    files = list(root.iterdir())
                    self.assertEqual(len(files), 1)
                    observed_lock.append(files[0])
                    first_entered.set()
                    self.assertTrue(release_first.wait(2))

            def second() -> None:
                self.assertTrue(first_entered.wait(2))
                second_attempted.set()
                with CONTROLLER.coordination_lock(root):
                    second_entered.set()

            with ThreadPoolExecutor(max_workers=2) as pool:
                first_future = pool.submit(first)
                second_future = pool.submit(second)
                self.assertTrue(first_entered.wait(2))
                self.assertTrue(second_attempted.wait(2))
                self.assertFalse(second_entered.wait(0.05))
                release_first.set()
                first_future.result()
                second_future.result()

            self.assertTrue(second_entered.is_set())
            lock = observed_lock[0]
            self.assertFalse(lock.exists())
            stale_pid = next(
                pid for pid in range(99_999_999, 99_999_900, -1)
                if not CONTROLLER.process_is_live(pid)
            )
            lock.write_text(
                json.dumps({"pid": stale_pid, "run_id": "coordination", "token": "stale"}) + "\n",
                encoding="utf-8",
            )
            with CONTROLLER.coordination_lock(root):
                self.assertTrue(lock.exists())
            self.assertFalse(lock.exists())

    def test_git_phase_allows_parallel_makers_but_checker_waits_for_both(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith git phase ") as temporary:
            repo = Path(temporary)
            makers_entered = threading.Barrier(3)
            release_makers = threading.Event()
            checker_entered = threading.Event()

            def maker() -> None:
                with CONTROLLER.git_phase(repo, "maker", timeout_seconds=3):
                    makers_entered.wait(timeout=2)
                    self.assertTrue(release_makers.wait(2))

            def checker() -> None:
                with CONTROLLER.git_phase(repo, "checker", timeout_seconds=3):
                    checker_entered.set()

            with mock.patch.object(CONTROLLER, "state_root", return_value=repo / "run-state"):
                with ThreadPoolExecutor(max_workers=3) as pool:
                    first = pool.submit(maker)
                    second = pool.submit(maker)
                    makers_entered.wait(timeout=2)
                    third = pool.submit(checker)
                    self.assertFalse(checker_entered.wait(0.1))
                    release_makers.set()
                    first.result()
                    second.result()
                    third.result()
            self.assertTrue(checker_entered.is_set())

    def test_git_phase_writer_waits_for_checker_and_reclaims_dead_owner(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith git phase ") as temporary:
            repo = Path(temporary)
            root = repo / "run-state"
            with mock.patch.object(CONTROLLER, "state_root", return_value=root):
                phase_dir = root / "git-phases"
                phase_dir.mkdir(parents=True)
                stale_pid = next(pid for pid in range(99_999_999, 99_999_900, -1)
                                 if not CONTROLLER.process_is_live(pid))
                (phase_dir / "stale.json").write_text(
                    json.dumps({"pid": stale_pid, "token": "stale", "phase": "checker"}),
                    encoding="utf-8",
                )
                with CONTROLLER.git_phase(repo, "writer", timeout_seconds=2):
                    self.assertFalse((phase_dir / "stale.json").exists())
                    with self.assertRaisesRegex(CONTROLLER.RunError, "git phase.*held"):
                        with CONTROLLER.git_phase(repo, "checker", timeout_seconds=0.05):
                            pass

    def test_maker_metadata_keeps_only_previously_verified_peer_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith peer snapshot ") as temporary:
            repo = Path(temporary)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
            (repo / "README.md").write_text("fixture\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)
            subprocess.run(["git", "-C", str(repo), "branch", "agentsmith/peer"], check=True)
            subprocess.run(["git", "-C", str(repo), "branch", "arbitrary-side-ref"], check=True)
            peer_ref = "refs/heads/agentsmith/peer"
            peer_log = Path("logs") / peer_ref
            with mock.patch.object(
                CONTROLLER, "registered_run_git_artifacts",
                side_effect=[({peer_ref}, {peer_log}, set()), (set(), set(), set())],
            ):
                before = CONTROLLER.git_metadata(repo)
                after = CONTROLLER.git_metadata(repo, known_peers=before["registered_peers"])
            self.assertEqual(before["refs"], after["refs"])
            self.assertTrue(any(ref.startswith("refs/heads/arbitrary-side-ref ")
                                for ref in after["refs"]))
            self.assertNotIn(peer_ref, " ".join(after["refs"]))

    def test_git_metadata_waits_for_transient_object_file_without_ignoring_persistent_one(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith transient object ") as temporary:
            repo = Path(temporary)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            objects = repo / ".git" / "objects" / "38"
            objects.mkdir()
            transient = objects / "tmp_obj_fixture"
            transient.write_bytes(b"incomplete Git object")
            clear = threading.Timer(0.15, transient.unlink)
            clear.start()
            try:
                snapshot = CONTROLLER.git_metadata(repo)
            finally:
                clear.join()
            self.assertFalse(any("tmp_obj_" in path for path, _ in snapshot["existing_objects"]))
            transient.write_bytes(b"persistent unexpected file")
            with self.assertRaisesRegex(CONTROLLER.RunError, "temporary Git object file did not settle"):
                CONTROLLER.git_metadata(repo)
            transient.unlink()
            maintenance = repo / ".git" / "objects" / "maintenance.lock"
            maintenance.write_bytes(b"Git auto-maintenance in progress")
            clear_maintenance = threading.Timer(0.15, maintenance.unlink)
            clear_maintenance.start()
            try:
                snapshot = CONTROLLER.git_metadata(repo)
            finally:
                clear_maintenance.join()
            self.assertFalse(any(path == "objects/maintenance.lock"
                                 for path, _ in snapshot["existing_objects"]))
            maintenance.write_bytes(b"persistent unexpected lock")
            with self.assertRaisesRegex(CONTROLLER.RunError, "temporary Git object file did not settle"):
                CONTROLLER.git_metadata(repo)

    def test_maker_metadata_recognizes_exact_peer_that_starts_and_ends_mid_window(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith peer window ") as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
            (repo / "README.md").write_text("fixture\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)
            before = CONTROLLER.git_metadata(repo)

            manifest = repo / "peer.json"
            manifest.write_text('{"run_id":"peer"}\n', encoding="utf-8")
            worktree = Path(temporary) / "peer-worktree"
            subprocess.run(["git", "-C", str(repo), "worktree", "add", "-qb",
                            "agentsmith/peer", str(worktree), "HEAD"], check=True)
            run_dir = CONTROLLER.state_root(repo) / "peer"
            run_dir.mkdir(parents=True)
            head = CONTROLLER.git(worktree, "rev-parse", "HEAD")
            CONTROLLER.write_json(run_dir / "state.json", {
                "run_id": "peer", "branch": "agentsmith/peer", "repo": str(repo),
                "manifest_path": str(manifest),
                "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "worktree": str(worktree), "status": "escalated",
                "started_epoch": time.time(), "terminal_head": head,
            })
            after = CONTROLLER.git_metadata(repo, known_peers=before["registered_peers"])
            self.assertEqual(before["refs"], after["refs"])
            self.assertEqual(before["protected_files"], after["protected_files"])

            resumed_state = CONTROLLER.load_json(run_dir / "state.json")
            resumed_state["started_epoch"] = time.time() - 100
            resumed_state["resumed_epoch"] = time.time()
            CONTROLLER.write_json(run_dir / "state.json", resumed_state)
            resumed_peer = CONTROLLER.git_metadata(repo, known_peers=before["registered_peers"])
            self.assertEqual(before["refs"], resumed_peer["refs"])

            subprocess.run(["git", "-C", str(repo), "branch", "arbitrary-side-ref"], check=True)
            tampered = CONTROLLER.git_metadata(repo, known_peers=before["registered_peers"])
            with self.assertRaisesRegex(CONTROLLER.RunError, "Git refs outside"):
                CONTROLLER.validate_git_transition(repo, before, tampered, "active", head, head)
            state_file = run_dir / "state.json"
            state = CONTROLLER.load_json(state_file)
            state["terminal_head"] = "0" * len(head)
            CONTROLLER.write_json(state_file, state)
            unverified = CONTROLLER.git_metadata(repo, known_peers=before["registered_peers"])
            self.assertIn("refs/heads/agentsmith/peer", " ".join(unverified["refs"]))

    def test_stop_request_creation_is_atomic_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith stop ") as temporary:
            run_dir = Path(temporary)
            with ThreadPoolExecutor(max_workers=8) as pool:
                futures = [pool.submit(CONTROLLER.create_stop_request, run_dir) for _ in range(40)]
                for future in futures:
                    future.result()
            stop = run_dir / "STOP"
            self.assertTrue(stop.is_file())
            self.assertEqual(stop.read_text(encoding="utf-8").count("requested_at="), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
