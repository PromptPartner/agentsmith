#!/usr/bin/env python3
"""Cross-platform tests for autonomous state atomicity and lifecycle ownership."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
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
                        value = json.loads(path.read_text(encoding="utf-8"))
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
