#!/usr/bin/env python3
"""Native negative proof for the Windows verifier boundary."""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor
import contextlib
import ctypes
import importlib.util
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SANDBOX_SPEC = importlib.util.spec_from_file_location("agentsmith_verifier_sandbox_unit",
                                                      ROOT / "windows_verifier_sandbox.py")
assert SANDBOX_SPEC and SANDBOX_SPEC.loader
SANDBOX = importlib.util.module_from_spec(SANDBOX_SPEC)
SANDBOX_SPEC.loader.exec_module(SANDBOX)


class FakeAdvapi:
    """Replays one Windows last-error per security call; 0 means the file answers."""

    def __init__(self, errors: list[int]) -> None:
        self.errors = list(errors)
        self.last_error = 0
        self.calls = 0

    def GetFileSecurityW(self, path: str, information: int, descriptor: object,
                         length: int, needed: object) -> bool:
        self.calls += 1
        self.last_error = self.errors.pop(0) if self.errors else 0
        if self.last_error:
            return False
        if descriptor is None:
            needed._obj.value = 4  # type: ignore[attr-defined]
            self.last_error = 122  # ERROR_INSUFFICIENT_BUFFER answers a size query.
            return False
        ctypes.memmove(descriptor, b"DACL", 4)
        return True

    def SetFileSecurityW(self, path: str, information: int, descriptor: object) -> bool:
        self.calls += 1
        self.last_error = self.errors.pop(0) if self.errors else 0
        return not self.last_error


def verifier_outcome(future: Future[subprocess.CompletedProcess[str]]) -> str:
    """Names why a sandboxed verifier never wrote its start marker."""
    if not future.done():
        return "still running after the wait"
    try:
        result = future.result()
    except Exception as error:
        return f"raised {type(error).__name__}: {error}"
    return f"exited {result.returncode}; stderr={result.stderr!r}"


class DeletePendingLockTests(unittest.TestCase):
    """A peer's removed coordination.lock stays delete-pending and reports error 5 briefly."""

    lock = Path("coordination.lock")

    @contextlib.contextmanager
    def replay(self, fake: FakeAdvapi) -> Iterator[mock.MagicMock]:
        with (mock.patch.object(SANDBOX.ctypes, "get_last_error", create=True,
                                side_effect=lambda: fake.last_error),
              mock.patch.object(time, "sleep") as pause):
            yield pause

    def test_snapshot_skips_lock_removed_while_delete_pending(self) -> None:
        fake = FakeAdvapi([5, 5, 2])
        with self.replay(fake) as pause:
            self.assertIsNone(SANDBOX._original_dacl(self.lock, fake))
        self.assertEqual((fake.calls, pause.call_count), (3, 2))

    def test_snapshot_reads_lock_recreated_after_delete_pending(self) -> None:
        fake = FakeAdvapi([0, 5])
        with self.replay(fake):
            self.assertEqual(SANDBOX._original_dacl(self.lock, fake), b"DACL")
        self.assertEqual(fake.calls, 4)

    def test_snapshot_persistent_or_other_denial_still_fails_closed(self) -> None:
        fake = FakeAdvapi([5] * 500)
        with self.replay(fake), self.assertRaisesRegex(SANDBOX.SandboxError,
                                                       "GetFileSecurityW .*Windows error 5"):
            SANDBOX._original_dacl(self.lock, fake)
        self.assertEqual(fake.calls, 500)
        fake = FakeAdvapi([1314])
        with self.replay(fake) as pause, self.assertRaisesRegex(SANDBOX.SandboxError,
                                                                "Windows error 1314"):
            SANDBOX._original_dacl(self.lock, fake)
        self.assertEqual((fake.calls, pause.call_count), (1, 0))

    def test_restore_skips_lock_removed_while_delete_pending(self) -> None:
        fake = FakeAdvapi([5, 2])
        with self.replay(fake) as pause:
            SANDBOX._restore_dacl(self.lock, b"DACL", fake)
        self.assertEqual((fake.calls, pause.call_count), (2, 1))
        fake = FakeAdvapi([5] * 500)
        with self.replay(fake), self.assertRaisesRegex(SANDBOX.SandboxError,
                                                       "SetFileSecurityW .*Windows error 5"):
            SANDBOX._restore_dacl(self.lock, b"DACL", fake)
        self.assertEqual(fake.calls, 500)


class VerifierStartFailureTests(unittest.TestCase):
    """A verifier that never writes its start marker must say why, not only that it did not."""

    def test_reports_a_verifier_still_running(self) -> None:
        self.assertEqual(verifier_outcome(Future()), "still running after the wait")

    def test_reports_exit_code_and_stderr_of_an_early_exit(self) -> None:
        done: Future[subprocess.CompletedProcess[str]] = Future()
        done.set_result(subprocess.CompletedProcess(["verify"], 126, "", "CreateProcessW failed"))
        self.assertEqual(verifier_outcome(done), "exited 126; stderr='CreateProcessW failed'")

    def test_reports_an_exception_raised_by_the_launch(self) -> None:
        raised: Future[subprocess.CompletedProcess[str]] = Future()
        raised.set_exception(OSError("access denied"))
        self.assertEqual(verifier_outcome(raised), "raised OSError: access denied")


class WindowsVerifierSandboxTests(unittest.TestCase):
    maxDiff = None

    @unittest.skipUnless(os.name == "nt", "requires native Windows AppContainer")
    def test_worktree_write_sibling_and_network_denial_and_acl_cleanup(self) -> None:
        spec = importlib.util.spec_from_file_location("agentsmith_verifier_test",
                                                   ROOT / "scripts/autonomous-run.py")
        assert spec and spec.loader
        controller = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(controller)
        with tempfile.TemporaryDirectory(prefix="agentsmith windows verifier ") as temporary:
            root = Path(temporary)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            (repo / "input.txt").write_text("approved input", encoding="utf-8")
            sibling = root / "forbidden.txt"
            probe = repo / "probe.py"
            probe.write_text(
                "from pathlib import Path\n"
                "import socket, sys\n"
                "assert Path('input.txt').read_text(encoding='utf-8') == 'approved input'\n"
                "Path('inside.txt').write_text('allowed', encoding='utf-8')\n"
                "try:\n"
                "    Path(sys.argv[1]).write_text('escaped', encoding='utf-8')\n"
                "except OSError:\n"
                "    pass\n"
                "else:\n"
                "    raise SystemExit('sibling write succeeded')\n"
                "with socket.socket() as connection:\n"
                "    connection.settimeout(2)\n"
                "    try:\n"
                "        connection.connect(('127.0.0.1', int(sys.argv[2])))\n"
                "    except OSError:\n"
                "        pass\n"
                "    else:\n"
                "        raise SystemExit('network connection succeeded')\n"
                "print('boundary passed')\n", encoding="utf-8",
            )
            git_command = shutil.which("git")
            self.assertIsNotNone(git_command)
            git_executable = Path(git_command).resolve()
            acl_paths = (repo, repo / ".git", repo / "input.txt", probe,
                         Path(sys.prefix).resolve(), Path(sys.executable).resolve(),
                         git_executable.parent.parent, git_executable)
            before_acls = {
                path: subprocess.run(["icacls", str(path)], capture_output=True,
                                     text=True, check=True).stdout for path in acl_paths
            }
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                listener.listen(1)
                command = f'"{sys.executable}" "{probe}" "{sibling}" {listener.getsockname()[1]}'
                result = controller.sandboxed_verify(command, repo, 20, controller.verifier_env())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("boundary passed", result.stdout)
            self.assertEqual((repo / "inside.txt").read_text(encoding="utf-8"), "allowed")
            self.assertFalse(sibling.exists())
            for path, before in before_acls.items():
                with self.subTest(path=str(path)):
                    self.assertEqual(subprocess.run(["icacls", str(path)], capture_output=True,
                                                    text=True, check=True).stdout, before)
            self.assertEqual(list(repo.glob(".agentsmith-verifier-*")), [])

    @unittest.skipUnless(os.name == "nt", "requires native Windows AppContainer")
    def test_parallel_verifiers_restore_shared_toolchain_acls(self) -> None:
        spec = importlib.util.spec_from_file_location("agentsmith_parallel_verifier_test",
                                                   ROOT / "scripts/autonomous-run.py")
        assert spec and spec.loader
        controller = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(controller)
        with tempfile.TemporaryDirectory(prefix="agentsmith parallel windows verifiers ") as temporary:
            root = Path(temporary)
            repos = [root / name for name in ("repo-a", "repo-b")]
            commands = []
            for repo in repos:
                repo.mkdir()
                subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
                (repo / "input.txt").write_text("approved", encoding="utf-8")
                probe = repo / "probe.py"
                probe.write_text(
                    "from pathlib import Path\n"
                    "import sys, time\n"
                    "assert Path('input.txt').read_text(encoding='utf-8') == 'approved'\n"
                    "Path('inside.txt').write_text('allowed', encoding='utf-8')\n"
                    "try:\n"
                    "    Path(sys.argv[1]).write_text('escaped', encoding='utf-8')\n"
                    "except OSError:\n"
                    "    pass\n"
                    "else:\n"
                    "    raise SystemExit('sibling write succeeded')\n"
                    "time.sleep(1)\n"
                    "print('parallel boundary passed')\n", encoding="utf-8",
                )
                commands.append(f'"{sys.executable}" "{probe}" "{root / (repo.name + "-forbidden.txt")}"')
            git_command = shutil.which("git")
            self.assertIsNotNone(git_command)
            git_executable = Path(git_command).resolve()
            acl_paths = (Path(sys.prefix).resolve(), Path(sys.executable).resolve(),
                         git_executable.parent.parent, git_executable, *repos)
            before_acls = {
                path: subprocess.run(["icacls", str(path)], capture_output=True,
                                     text=True, check=True).stdout for path in acl_paths
            }
            barrier = threading.Barrier(2)

            def verify(index: int) -> subprocess.CompletedProcess[str]:
                barrier.wait(timeout=10)
                return controller.sandboxed_verify(commands[index], repos[index], 90,
                                                   controller.verifier_env())

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(verify, index) for index in range(2)]
                results = [future.result(timeout=180) for future in futures]
            for result in results:
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("parallel boundary passed", result.stdout)
            for repo in repos:
                self.assertEqual((repo / "inside.txt").read_text(encoding="utf-8"), "allowed")
                self.assertFalse((root / (repo.name + "-forbidden.txt")).exists())
                self.assertEqual(list(repo.glob(".agentsmith-verifier-*")), [])
            for path, before in before_acls.items():
                with self.subTest(path=str(path)):
                    self.assertEqual(subprocess.run(["icacls", str(path)], capture_output=True,
                                                    text=True, check=True).stdout, before)

    @unittest.skipUnless(os.name == "nt", "requires native Windows AppContainer")
    def test_deleted_git_lock_does_not_fail_acl_cleanup(self) -> None:
        spec = importlib.util.spec_from_file_location("agentsmith_transient_lock_verifier_test",
                                                   ROOT / "scripts/autonomous-run.py")
        assert spec and spec.loader
        controller = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(controller)
        with tempfile.TemporaryDirectory(prefix="agentsmith transient windows lock ") as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            lock = repo / ".git/agentsmith-runs/coordination.lock"
            lock.parent.mkdir(parents=True)
            lock.write_text("temporary owner", encoding="utf-8")
            probe = repo / "probe.py"
            probe.write_text(
                "from pathlib import Path\n"
                "import time\n"
                "Path('verifier-started').write_text('yes', encoding='utf-8')\n"
                "time.sleep(2)\n"
                "print('transient lock passed')\n", encoding="utf-8",
            )
            before = subprocess.run(["icacls", str(repo / ".git")], capture_output=True,
                                    text=True, check=True).stdout
            command = f'"{sys.executable}" "{probe}"'
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(controller.sandboxed_verify, command, repo, 30,
                                     controller.verifier_env())
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline and not (repo / "verifier-started").is_file():
                    time.sleep(0.05)
                if not (repo / "verifier-started").is_file():
                    self.fail(f"verifier did not start: {verifier_outcome(future)}")
                lock.unlink()
                result = future.result(timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("transient lock passed", result.stdout)
            self.assertFalse(lock.exists())
            self.assertEqual(subprocess.run(["icacls", str(repo / ".git")], capture_output=True,
                                            text=True, check=True).stdout, before)


if __name__ == "__main__":
    unittest.main()
