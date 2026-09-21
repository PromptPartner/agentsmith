#!/usr/bin/env python3
"""Native negative proof for the Windows verifier boundary."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
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
            before_repo = subprocess.run(["icacls", str(repo)], capture_output=True,
                                         text=True, check=True).stdout
            before_git = subprocess.run(["icacls", str(repo / ".git")], capture_output=True,
                                        text=True, check=True).stdout
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                listener.listen(1)
                command = f'"{sys.executable}" "{probe}" "{sibling}" {listener.getsockname()[1]}'
                result = controller.sandboxed_verify(command, repo, 20, controller.verifier_env())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("boundary passed", result.stdout)
            self.assertEqual((repo / "inside.txt").read_text(encoding="utf-8"), "allowed")
            self.assertFalse(sibling.exists())
            self.assertEqual(subprocess.run(["icacls", str(repo)], capture_output=True,
                                            text=True, check=True).stdout, before_repo)
            self.assertEqual(subprocess.run(["icacls", str(repo / ".git")], capture_output=True,
                                            text=True, check=True).stdout, before_git)
            self.assertEqual(list(repo.glob(".agentsmith-verifier-*")), [])


if __name__ == "__main__":
    unittest.main()
