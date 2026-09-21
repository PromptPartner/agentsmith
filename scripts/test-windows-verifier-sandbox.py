#!/usr/bin/env python3
"""Native negative proof for the Windows verifier boundary."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
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


ROOT = Path(__file__).resolve().parent.parent


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
                self.assertTrue((repo / "verifier-started").is_file(), "verifier did not start")
                lock.unlink()
                result = future.result(timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("transient lock passed", result.stdout)
            self.assertFalse(lock.exists())
            self.assertEqual(subprocess.run(["icacls", str(repo / ".git")], capture_output=True,
                                            text=True, check=True).stdout, before)


if __name__ == "__main__":
    unittest.main()
