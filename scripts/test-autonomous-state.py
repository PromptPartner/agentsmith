#!/usr/bin/env python3
"""Cross-platform tests for autonomous state atomicity and lifecycle ownership."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import contextlib
import errno
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import shutil
import shlex
import tempfile
import threading
import time
from typing import Any
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
CONTROLLER_PATH = ROOT / "scripts" / "autonomous-run.py"
SPEC = importlib.util.spec_from_file_location("agentsmith_autonomous_state", CONTROLLER_PATH)
assert SPEC and SPEC.loader
CONTROLLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROLLER)


class AutonomousStateTests(unittest.TestCase):
    def test_git_paths_preserve_unicode_under_windows_locale_decoding(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith git ü ") as temporary:
            repo = Path(temporary).resolve() / "fresh consumer"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            template = repo / ".harness/templates/autonomous-run.json"
            template.parent.mkdir(parents=True)
            shutil.copy2(ROOT / "templates/autonomous-run.json", template)
            args = CONTROLLER.parser().parse_args([
                "prepare", "--run-id", "consumer", "--spec", "docs/specs/task.md",
                "--ticket", "TASK-1",
            ])
            with mock.patch.object(subprocess, "_text_encoding", return_value="cp1252"):
                self.assertEqual(CONTROLLER.repo_root(repo), repo)
                self.assertEqual(Path(CONTROLLER.git(repo, "rev-parse", "--show-toplevel")), repo)
                with mock.patch.object(CONTROLLER.Path, "cwd", return_value=repo):
                    self.assertEqual(CONTROLLER.prepare(args), 0)
            manifest = json.loads((repo / ".harness/runs/consumer.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["run_id"], "consumer")
            self.assertEqual(manifest["implementation_ticket"], "TASK-1")

    def test_verifier_cannot_replace_trusted_contract_in_temporary_repository(self) -> None:
        if CONTROLLER.sys.platform != 'darwin':
            self.skipTest('macOS verifier execution probe')
        with tempfile.TemporaryDirectory(dir='/tmp') as temporary:
            repo = Path(temporary).resolve()
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            manifest = repo/'manifest.json'
            manifest.write_text('original')
            checkout = repo/'candidate'
            checkout.mkdir()
            directory = repo/'.git/agentsmith-runs/probe'
            directory.mkdir(parents=True)
            state = {'repo': str(repo), 'worktree': str(checkout), 'spec_path': 'spec.md',
                     'manifest_path': str(manifest), 'state_path': str(directory/'state.json'), 'attempt': 1}
            command = shlex.join([CONTROLLER.sys.executable, '-c',
                                  'import pathlib,sys; pathlib.Path(sys.argv[1]).write_text("forged")', str(manifest)])
            result = CONTROLLER.sandboxed_verify(command, checkout, 10, CONTROLLER.verifier_env(), state=state)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(manifest.read_text(), 'original')

    def test_orphaned_group_is_live_even_after_its_leader_exits(self) -> None:
        if os.name == 'nt':
            self.skipTest('POSIX process group probe')
        script = ('import subprocess,sys; p=subprocess.Popen([sys.executable,"-c",'
                  '"import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)"],'
                  'stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); print(p.pid,flush=True)')
        leader = subprocess.Popen([CONTROLLER.sys.executable, '-c', script], start_new_session=True,
                                  text=True, stdout=subprocess.PIPE)
        leader.communicate(timeout=10)
        try:
            self.assertFalse(CONTROLLER.process_is_live(leader.pid))
            self.assertTrue(CONTROLLER.process_group_is_live(leader.pid))
        finally:
            CONTROLLER.terminate_process_tree(leader.pid)
        for _ in range(100):
            if not CONTROLLER.process_group_is_live(leader.pid):
                break
            time.sleep(0.02)
        self.assertFalse(CONTROLLER.process_group_is_live(leader.pid))

    def test_codex_native_maker_can_commit_without_writing_trusted_state(self) -> None:
        executable = shutil.which('codex')
        if executable is None or CONTROLLER.sys.platform != 'darwin':
            self.skipTest('native Codex Git probe requires a local supported client')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repo, workspace = root/'repo', root/'maker'
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            for key, value in [('user.name', 'Fixture'), ('user.email', 'fixture@example.com')]:
                subprocess.run(['git', '-C', str(repo), 'config', key, value], check=True)
            (repo/'base').write_text('base')
            subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(repo), 'commit', '-qm', 'baseline'], check=True)
            subprocess.run(['git', '-C', str(repo), 'worktree', 'add', '-qb', 'maker', str(workspace)], check=True)
            trusted = repo/'.git/agentsmith-runs/probe'
            state = {'repo': str(repo), 'worktree': str(workspace), 'state_path': str(trusted/'state.json'),
                     'manifest_path': str(repo/'manifest.json'), 'spec_path': 'spec.md',
                     'attempt': 1, 'deadline_epoch': time.time()+30}
            manifest = {'roles': {'maker': {'runtime': 'codex', 'model': 'fixture', 'effort': 'high'}}, 'limits': {}}
            class Observed(Exception):
                pass
            with mock.patch.object(CONTROLLER, 'build_native_command', side_effect=Observed) as launch:
                with self.assertRaises(Observed):
                    CONTROLLER.launch_role(state, manifest, 'maker', 'make')
            policy = CONTROLLER.codex_permissions(workspace, launch.call_args.kwargs['extra_write_dirs'],
                                                 protected_write_paths=launch.call_args.kwargs['protected_write_paths'])
            prefix = [executable, 'sandbox', '--permission-profile', 'agentsmith', '-c',
                      'permissions='+CONTROLLER.toml_inline({'agentsmith': policy}), '--']
            (workspace/'candidate').write_text('candidate')
            result = CONTROLLER.run([*prefix, '/bin/bash', '-c', 'git add candidate && git commit -qm candidate'], workspace)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = CONTROLLER.run([*prefix, CONTROLLER.sys.executable, '-c',
                                     'import pathlib,sys; pathlib.Path(sys.argv[1]).write_text("forged")',
                                     str(trusted/'forged')], workspace)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((trusted/'forged').exists())

    def test_verifier_timeout_stops_descendants_and_preserves_output(self) -> None:
        if os.name == 'nt':
            self.skipTest('POSIX process group probe')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = {'state_path': str(root / 'state.json'), 'attempt': 1}
            script = ('import subprocess,sys,time; '
                      'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); '
                      'print(p.pid,flush=True); time.sleep(60)')
            with self.assertRaises(subprocess.TimeoutExpired):
                CONTROLLER.verifier_process([CONTROLLER.sys.executable, '-c', script], root,
                                            0.3, CONTROLLER.verifier_env(), state)
            child = int((root / 'attempt-1-verify.stdout').read_text().strip())
            for _ in range(100):
                if not CONTROLLER.process_is_live(child):
                    break
                time.sleep(0.02)
            self.assertFalse(CONTROLLER.process_is_live(child))
            self.assertIsNone(json.loads((root/'state.json').read_text())['active_pid'])
            self.assertNotEqual(json.loads((root/'attempt-1-verify-exit.json').read_text())['exit_code'], 0)

    def test_codex_native_profile_denies_trusted_writes_inside_git_grant(self) -> None:
        executable = shutil.which('codex')
        if executable is None or CONTROLLER.sys.platform != 'darwin':
            self.skipTest('native Codex sandbox probe requires a local supported client')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            common = root / 'common'
            trusted = common / 'agentsmith-runs'
            trusted.mkdir(parents=True)
            protected = trusted / 'state.json'
            protected.write_text('original')
            permissions = CONTROLLER.codex_permissions(root, [common], protected_write_paths=[trusted])
            prefix = [executable, 'sandbox', '--permission-profile', 'agentsmith', '-c',
                      'permissions=' + CONTROLLER.toml_inline({'agentsmith': permissions}), '--']
            script = 'import pathlib,sys; pathlib.Path(sys.argv[1]).write_text("forged")'
            result = CONTROLLER.run([*prefix, CONTROLLER.sys.executable, '-c', script, str(protected)], root)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(protected.read_text(), 'original')
            result = CONTROLLER.run([*prefix, CONTROLLER.sys.executable, '-c', script, str(root / 'allowed')], root)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = CONTROLLER.run([*prefix, 'mv', str(common), str(root/'escaped')], root)
            self.assertNotEqual(result.returncode, 0, result.stderr)
            self.assertTrue(protected.exists())
            command = CONTROLLER.build_native_command('codex', 'make', root, root/'schema', root/'receipt',
                                                      extra_write_dirs=[common], protected_write_paths=[trusted])
            self.assertIn('default_permissions="agentsmith"', command)
            self.assertIn('--strict-config', command)
            self.assertNotIn('--sandbox', command)

    def test_claude_native_policy_covers_bash_and_builtin_file_tools(self) -> None:
        protected = ROOT / 'trusted'
        settings = CONTROLLER.claude_sandbox_settings(ROOT, [ROOT], protected_write_paths=[protected])
        self.assertIn(str(protected), settings['sandbox']['filesystem']['denyWrite'])
        self.assertIn(f'Edit(/{protected}/**)', settings['permissions']['deny'])

    def test_claude_qualification_settings_disable_hooks_explicitly(self) -> None:
        # C07: project-source exclusion alone does not express the hook boundary.
        for role in ('maker', 'checker'):
            with self.subTest(role=role):
                settings = CONTROLLER.claude_sandbox_settings(
                    ROOT, read_only=role == 'checker', protected_write_paths=[ROOT/'trusted'])
                self.assertIs(settings.get('disableAllHooks'), True)
                self.assertFalse(settings['enableAllProjectMcpServers'])
                self.assertFalse(settings['sandbox']['allowUnsandboxedCommands'])

    def test_claude_checker_denies_bash_writes_to_checkout(self) -> None:
        settings = CONTROLLER.claude_sandbox_settings(ROOT, read_only=True)
        self.assertIn(str(ROOT), settings['sandbox']['filesystem'].get('denyWrite', []))

    def test_trusted_boundary_fails_closed_on_unsupported_host(self) -> None:
        with mock.patch.object(CONTROLLER.sys, 'platform', 'unsupported'):
            with self.assertRaisesRegex(CONTROLLER.RunError, 'trusted-state sandbox'):
                CONTROLLER.require_native_role_sandbox()

    def test_resume_original_spec_must_match_committed_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix='qualification spec drift ') as temporary:
            repo = Path(temporary).resolve()
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            subprocess.run(['git', '-C', str(repo), 'config', 'user.name', 'Test'], check=True)
            subprocess.run(['git', '-C', str(repo), 'config', 'user.email', 'user@example.com'], check=True)
            spec = repo/'spec.md'
            spec.write_bytes(b'accepted contract\n')
            (repo/'.gitattributes').write_bytes(b'*.md text eol=lf\n')
            subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(repo), 'commit', '-qm', 'baseline'], check=True)
            CONTROLLER.validate_original_spec(repo, Path('spec.md'), 'HEAD')
            # Git-normalized line endings are the same contract on Windows.
            spec.write_bytes(b'accepted contract\r\n')
            CONTROLLER.validate_original_spec(repo, Path('spec.md'), 'HEAD')
            spec.write_bytes(b'changed contract\n')
            with self.assertRaisesRegex(CONTROLLER.RunError, 'original spec changed'):
                CONTROLLER.validate_original_spec(repo, Path('spec.md'), 'HEAD')
            spec.unlink()
            with self.assertRaisesRegex(CONTROLLER.RunError, 'original spec changed'):
                CONTROLLER.validate_original_spec(repo, Path('spec.md'), 'HEAD')

    def test_recovery_does_not_relaunch_completed_maker(self) -> None:
        state = {'attempt': 1, 'stage': 'verifying', 'maker_receipt': {'status': 'completed'}}
        self.assertTrue(CONTROLLER.pending_candidate(state))
        state['stage'] = 'checking'
        self.assertTrue(CONTROLLER.pending_candidate(state))
        state['stage'] = 'making'
        self.assertFalse(CONTROLLER.pending_candidate(state))

    def test_acceptance_requires_nonblank_evidence_and_no_unresolved_findings(self) -> None:
        for evidence in ([], [""], ["   "]):
            self.assertFalse(CONTROLLER.acceptance_ready(0, {"status": "accepted", "evidence": evidence, "unresolved": []}))
        receipt = {"status": "accepted", "evidence": ["required checks pass"], "unresolved": []}
        self.assertTrue(CONTROLLER.acceptance_ready(0, receipt))
        self.assertFalse(CONTROLLER.acceptance_ready(126, receipt))
        self.assertFalse(CONTROLLER.acceptance_ready(0, {**receipt, "unresolved": ["missing check"]}))

    def test_execution_requires_explicit_role_models_and_effort(self) -> None:
        manifest = json.loads((ROOT / "templates/autonomous-run.json").read_text())
        manifest.update(run_id="fixture", spec_path="docs/specs/accepted.md", implementation_ticket="IMP-1")
        spec = "---\nstatus: accepted\naccepted_by: Operator\naccepted_at: 2026-10-04\ndecision_ticket: DEC-1\n---\n"
        for config in manifest["roles"].values():
            config.update(model="fixture-model", effort="high")
        for role in ("maker", "checker"):
            for key in ("model", "effort"):
                with self.subTest(role=role, key=key):
                    original = manifest["roles"][role][key]
                    manifest["roles"][role][key] = ""
                    with mock.patch.object(CONTROLLER, "git", return_value=spec):
                        with self.assertRaisesRegex(CONTROLLER.RunError, f"roles.{role}.{key}"):
                            CONTROLLER.validate_manifest(manifest, ROOT)
                    manifest["roles"][role][key] = original

    def test_codex_read_only_command_has_no_write_roots(self) -> None:
        command = CONTROLLER.build_native_command(
            "codex", "check", ROOT, ROOT / "schema.json", ROOT / "receipt.json",
            read_only=True, extra_write_dirs=[ROOT],
        )
        self.assertEqual(command[command.index("--sandbox") + 1], "read-only")
        self.assertNotIn("--add-dir", command)

    def test_codex_checker_passes_read_only_to_shared_launcher(self) -> None:
        state = {"worktree": str(ROOT), "repo": str(ROOT), "state_path": str(ROOT / "state.json"),
                 "attempt": 1, "deadline_epoch": time.time() + 30,
                 "manifest_path": str(ROOT / 'manifest.json'), "spec_path": 'spec.md'}
        manifest = {"roles": {"checker": {"runtime": "codex", "model": "fixture", "effort": "high"}},
                    "limits": {}}
        class LaunchObserved(Exception):
            pass
        with (mock.patch.object(CONTROLLER, "write_json"),
              mock.patch.object(CONTROLLER, "build_native_command", side_effect=LaunchObserved) as launch):
            with self.assertRaises(LaunchObserved):
                CONTROLLER.launch_role(state, manifest, "checker", "check")
        self.assertTrue(launch.call_args.kwargs.get("read_only"))

    def test_verification_policy_and_baseline_tests_cannot_be_weakened(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
            for name in (".harness/verify.conf", "tests/test_baseline.py", "test_acceptance.py", "acceptance_test.py", ".agentsmith/agentsmith.py", "src/app.py"):
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("baseline\n")
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "baseline"], check=True)
            base = CONTROLLER.git(repo, "rev-parse", "HEAD")
            state = {"worktree": str(repo), "base_head": base, "spec_sha256": "spec", "manifest_sha256": "manifest"}
            proof = CONTROLLER.verification_binding(state, {"verify": {"command": "check"}}, base)
            self.assertEqual(proof["verify_configuration_sha256"], hashlib.sha256(b"baseline\n").hexdigest())
            for name in (".harness/verify.conf", "tests/test_baseline.py", "test_acceptance.py", "acceptance_test.py", ".agentsmith/agentsmith.py"):
                with self.subTest(path=name):
                    (repo / name).write_text("weakened\n")
                    subprocess.run(["git", "-C", str(repo), "commit", "-qam", "candidate"], check=True)
                    with self.assertRaisesRegex(CONTROLLER.RunError, "protected verification"):
                        CONTROLLER.validate_verification_changes(repo, base, "HEAD", {})
                    subprocess.run(["git", "-C", str(repo), "reset", "--hard", base], capture_output=True, check=True)
            (repo / "src/app.py").write_text("implementation\n")
            (repo / "tests/test_new.py").write_text("new regression\n")
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "candidate"], check=True)
            CONTROLLER.validate_verification_changes(repo, base, "HEAD", {})

    def committed_fixture(self, repo: Path, files: dict[str, str]) -> str:
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
        for name, content in files.items():
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "baseline"], check=True)
        return CONTROLLER.git(repo, "rev-parse", "HEAD")

    def test_moving_a_protected_input_into_scope_is_still_rejected(self) -> None:
        # Git reports a move under its new path only unless rename detection is switched off, so a
        # maker could carry an approved check or the verify policy out of the paths that guard it.
        manifest = {"scope": {"allowed_paths": ["src/**"], "denied_paths": ["tests/**", ".harness/**"]}}
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            base = self.committed_fixture(repo, {
                ".harness/verify.conf": "tests :: python3 -m unittest discover -s tests\n",
                "tests/test_baseline.py": "import unittest\n\n\nclass Baseline(unittest.TestCase):\n"
                                          "    def test_sum(self):\n        self.assertEqual(1 + 1, 2)\n",
                "src/app.py": "def add(a, b):\n    return a + b\n",
            })
            for source, destination in ((".harness/verify.conf", "src/verify.conf"),
                                        ("tests/test_baseline.py", "src/moved_checks.py")):
                with self.subTest(source=source):
                    subprocess.run(["git", "-C", str(repo), "mv", source, destination], check=True)
                    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "candidate"], check=True)
                    paths = CONTROLLER.changed_paths(repo, base)
                    self.assertEqual(sorted(paths), sorted([source, destination]))
                    self.assertEqual([path for path in paths if not CONTROLLER.path_allowed(path, manifest)],
                                     [source])
                    with self.assertRaises(CONTROLLER.RunError) as rejected:
                        CONTROLLER.validate_verification_changes(repo, base, "HEAD", {})
                    self.assertIn("protected verification", str(rejected.exception))
                    self.assertIn(source, str(rejected.exception))
                    subprocess.run(["git", "-C", str(repo), "reset", "--hard", base], capture_output=True, check=True)

    def test_move_inside_scope_counts_as_two_allowed_paths(self) -> None:
        manifest = {"scope": {"allowed_paths": ["src/**"], "denied_paths": ["tests/**"]}}
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            base = self.committed_fixture(repo, {"src/app.py": "def add(a, b):\n    return a + b\n"})
            subprocess.run(["git", "-C", str(repo), "mv", "src/app.py", "src/core.py"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "candidate"], check=True)
            paths = CONTROLLER.changed_paths(repo, base)
            self.assertEqual(sorted(paths), ["src/app.py", "src/core.py"])
            self.assertTrue(all(CONTROLLER.path_allowed(path, manifest) for path in paths))
            CONTROLLER.validate_verification_changes(repo, base, "HEAD", {})

    def test_scope_rules_see_the_exact_name_where_git_would_quote_it(self) -> None:
        # Git's display listing wraps a non-ASCII name in quotes and escapes it, so a rule written
        # with the real name would not match the listed one.
        denied = "priv\u00e9/notes.md"
        manifest = {"scope": {"allowed_paths": ["**"], "denied_paths": ["priv\u00e9/**"]}}
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            base = self.committed_fixture(repo, {denied: "base\n", "src/app.py": "base\n"})
            (repo / denied).write_text("edited\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "commit", "-qam", "candidate"], check=True)
            paths = CONTROLLER.changed_paths(repo, base)
            self.assertEqual(paths, [denied])
            self.assertFalse(CONTROLLER.path_allowed(paths[0], manifest))

    def test_changed_paths_keep_leading_whitespace_of_a_name(self) -> None:
        # " src/" is a different directory from "src/"; a trimmed listing would move the file
        # into the allowed scope. The commit is built without the filesystem to suit every host.
        manifest = {"scope": {"allowed_paths": ["src/**"], "denied_paths": []}}
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            base = self.committed_fixture(repo, {"src/app.py": "base\n"})
            blob = subprocess.run(["git", "-C", str(repo), "hash-object", "-w", "--stdin"], input="extra\n",
                                  text=True, capture_output=True, check=True).stdout.strip()
            subprocess.run(["git", "-C", str(repo), "update-index", "--add", "--cacheinfo",
                            "100644", blob, " src/extra.py"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "candidate"], check=True)
            paths = CONTROLLER.changed_paths(repo, base)
            self.assertEqual(paths, [" src/extra.py"])
            self.assertFalse(CONTROLLER.path_allowed(paths[0], manifest))

    def test_file_names_are_shown_with_control_characters_escaped(self) -> None:
        # The maker chooses these names and the controller prints them to the operator's terminal.
        shown = CONTROLLER.shown_paths(["clear\x1b[2J.txt", "two\nlines.txt", "priv\u00e9/notes.md"])
        self.assertEqual(shown, "clear\\x1b[2J.txt, two\\nlines.txt, priv\u00e9/notes.md")

    def test_protected_input_rejection_escapes_control_characters_in_a_name(self) -> None:
        # Git on Windows refuses to store such a name, so the two path lists are supplied here.
        crafted = ".harness/clear\x1b[2J.conf"
        with mock.patch.object(CONTROLLER, "git_paths", side_effect=[[], [crafted]]):
            with self.assertRaises(CONTROLLER.RunError) as rejected:
                CONTROLLER.validate_verification_changes(Path("."), "base", "head", {})
        self.assertIn("protected verification inputs", str(rejected.exception))
        self.assertIn(".harness/clear\\x1b[2J.conf", str(rejected.exception))
        self.assertNotIn("\x1b", str(rejected.exception))

    def test_role_prompts_say_how_a_receipt_lists_a_moved_file(self) -> None:
        # Both roles must return the controller's own path list, so each must be told its rule.
        state = {"run_id": "fixture", "base_head": "0123abc"}
        manifest = {"implementation_ticket": "IMP-1", "spec_path": "docs/specs/fixture.md",
                    "scope": {"allowed_paths": ["src/**"], "denied_paths": []},
                    "verify": {"command": "check"}, "limits": {},
                    "roles": {"maker": {"runtime": "claude"}, "checker": {"runtime": "codex"}}}
        for role in ("maker", "checker"):
            with self.subTest(role=role):
                prompt = CONTROLLER.role_prompt(state, manifest, role)
                self.assertIn("git -c core.quotepath=off diff --name-only --no-renames 0123abc HEAD", prompt)
                self.assertIn("old path and the new path", prompt)

    def test_coordination_lock_acquire_retries_windows_sharing_denial(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith coordination acquire ") as temporary:
            root = Path(temporary)
            lock = root / "coordination.lock"
            open_file = os.open
            attempts = 0

            def transient_open(path: str | os.PathLike[str], flags: int, mode: int = 0o777) -> int:
                nonlocal attempts
                if os.fspath(path) == os.fspath(lock):
                    attempts += 1
                    if attempts <= 2:
                        error = PermissionError(errno.EACCES, "another controller is deleting the lock")
                        error.winerror = 32
                        raise error
                return open_file(path, flags, mode)

            with mock.patch.object(CONTROLLER.os, "name", "nt"), mock.patch.object(CONTROLLER.os, "open", transient_open):
                with CONTROLLER.coordination_lock(root):
                    self.assertTrue(lock.is_file())
            self.assertEqual(attempts, 3)
            self.assertFalse(lock.exists())

    def test_coordination_lock_acquire_fails_closed_after_persistent_windows_denial(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith coordination timeout ") as temporary:
            root = Path(temporary)
            denial = PermissionError(errno.EACCES, "persistent sharing denial")
            denial.winerror = 32
            with (mock.patch.object(CONTROLLER.os, "name", "nt"),
                  mock.patch.object(CONTROLLER.os, "open", side_effect=denial) as open_file,
                  mock.patch.object(CONTROLLER.time, "monotonic", side_effect=[0.0, 61.0])):
                with self.assertRaisesRegex(CONTROLLER.RunError, "cannot acquire repository coordination lock"):
                    with CONTROLLER.coordination_lock(root):
                        self.fail("lock unexpectedly acquired")
            self.assertEqual(open_file.call_count, 1)

    def test_coordination_lock_release_retries_windows_reader_sharing_denial(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith coordination release ") as temporary:
            root = Path(temporary)
            lock = root / "coordination.lock"
            unlink = Path.unlink
            attempts = 0

            def transient_unlink(path: Path, *args: Any, **kwargs: Any) -> None:
                nonlocal attempts
                if path == lock:
                    attempts += 1
                    if attempts <= 2:
                        error = PermissionError(errno.EACCES, "another controller is reading the lock")
                        error.winerror = 32
                        raise error
                unlink(path, *args, **kwargs)

            with mock.patch.object(CONTROLLER.os, "name", "nt"), mock.patch.object(Path, "unlink", transient_unlink):
                with CONTROLLER.coordination_lock(root):
                    self.assertTrue(lock.is_file())
            self.assertEqual(attempts, 3)
            self.assertFalse(lock.exists())

    def test_coordination_lock_release_fails_closed_after_persistent_windows_denial(self) -> None:
        lock = Path("coordination.lock")
        denial = PermissionError(errno.EACCES, "persistent sharing denial")
        denial.winerror = 32
        with (mock.patch.object(CONTROLLER.os, "name", "nt"),
              mock.patch.object(Path, "unlink", side_effect=denial) as unlink,
              mock.patch.object(CONTROLLER.time, "sleep") as pause):
            with self.assertRaisesRegex(CONTROLLER.RunError, "cannot remove repository coordination lock"):
                CONTROLLER.unlink_coordination_lock(lock)
        self.assertEqual(unlink.call_count, 500)
        self.assertEqual(pause.call_count, 499)

    def test_native_role_disables_automatic_git_object_repacking(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith role git maintenance ") as temporary:
            repo = Path(temporary)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "config", "gc.auto", "1"], cwd=repo, check=True)
            subprocess.run(["git", "config", "maintenance.auto", "true"], cwd=repo, check=True)
            with CONTROLLER.native_role_environment("claude", repo) as maker_env:
                gc_auto = subprocess.run(["git", "config", "--get", "gc.auto"], cwd=repo,
                                         env=maker_env, text=True, capture_output=True, check=True)
                maintenance_auto = subprocess.run(["git", "config", "--get", "maintenance.auto"],
                                                  cwd=repo, env=maker_env, text=True,
                                                  capture_output=True, check=True)
            self.assertEqual(gc_auto.stdout.strip(), "0")
            self.assertEqual(maintenance_auto.stdout.strip(), "false")
            self.assertEqual(subprocess.check_output(["git", "config", "--get", "gc.auto"],
                                                     cwd=repo, text=True).strip(), "1")
            self.assertEqual(subprocess.check_output(["git", "config", "--get", "maintenance.auto"],
                                                     cwd=repo, text=True).strip(), "true")

    def test_native_role_git_conversion_matches_controller_clean_check(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith role git config ") as temporary:
            repo = Path(temporary)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            (repo / "change.txt").write_bytes(b"changed\r\n")
            controller_env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull,
                              "GIT_CONFIG_NOSYSTEM": "1"}
            for key in tuple(controller_env):
                if key.startswith("GIT_CONFIG_COUNT") or key.startswith("GIT_CONFIG_KEY_") or key.startswith("GIT_CONFIG_VALUE_"):
                    controller_env.pop(key)
            maker_with_host_conversion = {**controller_env, "GIT_CONFIG_COUNT": "1",
                                          "GIT_CONFIG_KEY_0": "core.autocrlf",
                                          "GIT_CONFIG_VALUE_0": "true"}
            subprocess.run(["git", "add", "change.txt"], cwd=repo, env=maker_with_host_conversion,
                           check=True)
            subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                            "commit", "-q", "-m", "fixture"], cwd=repo,
                           env=maker_with_host_conversion, check=True)
            committed_blob = subprocess.check_output(["git", "rev-parse", "HEAD:change.txt"],
                                                     cwd=repo, env=controller_env, text=True).strip()
            controller_blob = subprocess.check_output(
                ["git", "hash-object", "--path=change.txt", "change.txt"],
                cwd=repo, env=controller_env, text=True,
            ).strip()
            self.assertNotEqual(controller_blob, committed_blob)

            subprocess.run(["git", "rm", "--cached", "-q", "change.txt"], cwd=repo,
                           env=controller_env, check=True)
            with mock.patch.dict(os.environ, controller_env, clear=True):
                with CONTROLLER.native_role_environment("claude", repo) as maker_env:
                    self.assertEqual(maker_env["GIT_CONFIG_KEY_0"], "core.autocrlf")
                    self.assertEqual(maker_env["GIT_CONFIG_VALUE_0"], "false")
                    subprocess.run(["git", "add", "change.txt"], cwd=repo, env=maker_env, check=True)
                    subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                                    "commit", "-q", "-m", "same conversion"], cwd=repo,
                                   env=maker_env, check=True)
            clean = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo,
                                            env=controller_env, text=True)
            self.assertEqual(clean, "")
            committed_blob = subprocess.check_output(["git", "rev-parse", "HEAD:change.txt"],
                                                     cwd=repo, env=controller_env, text=True).strip()
            controller_blob = subprocess.check_output(
                ["git", "hash-object", "--path=change.txt", "change.txt"],
                cwd=repo, env=controller_env, text=True,
            ).strip()
            self.assertEqual(controller_blob, committed_blob)

    def test_generated_server_info_refs_do_not_impersonate_protected_git_writes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith server info ") as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                            "commit", "-q", "--allow-empty", "-m", "fixture"], cwd=repo, check=True)
            worktree = Path(temporary) / "peer"
            subprocess.run(["git", "worktree", "add", "-q", "-b", "peer", str(worktree)],
                           cwd=repo, check=True)
            before = CONTROLLER.git_metadata(worktree)
            ref = subprocess.check_output(["git", "symbolic-ref", "HEAD"], cwd=worktree,
                                          text=True).strip()
            oid = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=worktree,
                                          text=True).strip()
            info = repo / ".git/info/refs"
            info.write_text(f"{oid}\t{ref}\n", encoding="ascii")
            CONTROLLER.validate_git_unchanged(before, CONTROLLER.git_metadata(worktree), "maker")
            info.write_text("unauthorized metadata\n", encoding="ascii")
            with self.assertRaisesRegex(CONTROLLER.RunError, "protected_files"):
                CONTROLLER.validate_git_unchanged(before, CONTROLLER.git_metadata(worktree), "maker")

    def test_linux_verifier_prepares_temp_worktree_after_tmpfs_mount(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith verifier mount ") as temporary:
            repo = Path(temporary) / "repo"
            common = repo / ".git"
            common.mkdir(parents=True)
            with (
                mock.patch.object(CONTROLLER.sys, "platform", "linux"),
                mock.patch.object(CONTROLLER.shutil, "which", return_value="/usr/bin/bwrap"),
                mock.patch.object(CONTROLLER, "resolved_git_path", return_value=common),
                mock.patch.object(CONTROLLER, "verifier_process", return_value=subprocess.CompletedProcess([], 0, "", "")) as run,
            ):
                CONTROLLER.sandboxed_verify("true", repo, 10, CONTROLLER.verifier_env())
            args = run.call_args.args[0]
            tmpfs_index = next(index for index in range(len(args) - 1)
                               if args[index:index + 2] == ["--tmpfs", "/tmp"])
            remount_index = next(index for index in range(len(args) - 1)
                                 if args[index:index + 2] == ["--remount-ro", "/tmp"])
            bind_index = args.index("--bind")
            self.assertLess(tmpfs_index, remount_index)
            self.assertLess(remount_index, bind_index)
            if not Path.home().resolve().is_relative_to(Path("/tmp")):
                home_remount_index = next(index for index in range(len(args) - 1)
                                          if args[index:index + 2] == ["--remount-ro", str(Path.home().resolve())])
                self.assertLess(home_remount_index, bind_index)
            if repo.resolve().is_relative_to(Path("/tmp")):
                directory_index = next(index for index in range(len(args) - 1)
                                       if args[index:index + 2] == ["--dir", str(repo)])
                self.assertLess(directory_index, remount_index)

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

    def test_repository_coordination_lock_waits_for_owner_publication(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith lock publication ") as temporary:
            root = Path(temporary)
            lock = CONTROLLER.coordination_lock_path(root)
            lock.write_text("", encoding="utf-8")
            publish = threading.Timer(0.05, lambda: lock.write_text(
                json.dumps({"pid": os.getpid(), "run_id": "coordination", "token": "pub" + "lished"}),
                encoding="utf-8"))
            publish.start()
            try:
                self.assertEqual(CONTROLLER.read_coordination_lock(root)["token"], "published")
            finally:
                publish.join()
            lock.write_text("{malformed", encoding="utf-8")
            with self.assertRaisesRegex(CONTROLLER.RunError, "cannot verify repository coordination lock"):
                CONTROLLER.read_coordination_lock(root)

    def test_repository_coordination_lock_waits_for_slow_live_owner(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith slow coordination ") as temporary:
            root = Path(temporary)
            lock = CONTROLLER.coordination_lock_path(root)
            lock.write_text(json.dumps({"pid": os.getpid(), "run_id": "coordination",
                                        "token": "slow-" + "owner"}) + "\n", encoding="utf-8")

            class Clock:
                elapsed = 0.0

                def monotonic(self) -> float:
                    return self.elapsed

                def sleep(self, _: float) -> None:
                    self.elapsed += 1.0
                    if self.elapsed >= 11.0:
                        lock.unlink(missing_ok=True)

            clock = Clock()
            with mock.patch.object(CONTROLLER, "time", clock):
                with CONTROLLER.coordination_lock(root):
                    self.assertGreaterEqual(clock.elapsed, 11.0)
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

    def test_peer_inspection_propagates_operator_interruption(self) -> None:
        # Cancellation must reach run_controller, rather than look like corrupt peer state.
        with tempfile.TemporaryDirectory(prefix="agentsmith interrupted peer ") as temporary:
            common = Path(temporary)
            state_file = common / "agentsmith-runs" / "peer" / "state.json"
            state_file.parent.mkdir(parents=True)
            state_file.write_text("{}\n", encoding="utf-8")
            for inspect in (
                lambda: CONTROLLER.registered_run_git_artifacts(common, "refs/heads/active"),
                lambda: CONTROLLER.terminal_peer_git_artifacts(common, "refs/heads/active", set()),
                lambda: CONTROLLER.live_run_scope(common, state_file.parent, {"run_id": "peer"}),
            ):
                with self.subTest(inspect=inspect), mock.patch.object(
                    CONTROLLER, "load_json", side_effect=CONTROLLER.RunInterrupted("stopped by operator")
                ):
                    with self.assertRaises(CONTROLLER.RunInterrupted):
                        inspect()
            # Unverifiable peers still earn no metadata exemption.
            with mock.patch.object(CONTROLLER, "load_json", side_effect=CONTROLLER.RunError("bad state")):
                self.assertEqual(CONTROLLER.registered_run_git_artifacts(common, "refs/heads/active"),
                                 (set(), set(), set()))
                self.assertEqual(CONTROLLER.terminal_peer_git_artifacts(common, "refs/heads/active", set()),
                                 (set(), set(), set()))

    def test_controller_persists_sigterm_during_peer_inspection(self) -> None:
        # The stop no longer cuts the peer read short. The read finishes and the controller
        # records the interruption at its next checkpoint, so nothing can swallow the stop.
        with tempfile.TemporaryDirectory(prefix="agentsmith peer signal ") as temporary:
            common = Path(temporary)
            peer = common / "agentsmith-runs" / "peer" / "state.json"
            peer.parent.mkdir(parents=True)
            peer.write_text("{}\n", encoding="utf-8")
            directory = common / "controller"
            directory.mkdir()
            state = {"run_id": "active", "state_path": str(directory / "state.json"),
                     "worktree": str(common), "status": "making", "attempt": 1, "active_pid": None}

            def inspect_peer(state: dict[str, Any], _manifest: dict[str, Any]) -> int:
                CONTROLLER.registered_run_git_artifacts(common, "refs/heads/active")
                CONTROLLER.checkpoint_stage(state, "validating")
                return 0

            def stop_during_read(_path: Path) -> dict[str, Any]:
                CONTROLLER.signal.raise_signal(CONTROLLER.signal.SIGTERM)
                return {}

            with mock.patch.object(CONTROLLER, "execute", side_effect=inspect_peer), mock.patch.object(
                CONTROLLER, "load_json", side_effect=stop_during_read
            ), mock.patch.object(CONTROLLER, "git", return_value="a" * 40):
                self.assertEqual(CONTROLLER.run_controller(state, {}), 130)
            durable = json.loads((directory / "state.json").read_text())
            self.assertEqual(durable["status"], "interrupted")
            self.assertEqual(durable["stage"], "validating")
            self.assertIsNone(durable["active_pid"])
            events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
            self.assertEqual([event["event"] for event in events], ["stage_started", "run_interrupted"])

    def stopped_controller_outcome(self, common: Path, *, write_json: Any = None, git: Any = None,
                                   execute: Any = None) -> tuple[Any, dict[str, Any], list[str]]:
        # `stop` ends the role first, so the controller usually learns of the stop from the
        # role's exit. Its own signal arrives afterwards, at a point the caller chooses.
        directory = common / "controller"
        directory.mkdir()
        state = {"run_id": "active", "state_path": str(directory / "state.json"),
                 "worktree": str(common), "status": "making", "active_pid": 123}
        with mock.patch.object(
            CONTROLLER, "execute", side_effect=execute or CONTROLLER.RunInterrupted("stopped by operator")
        ), mock.patch.object(
            CONTROLLER, "write_json", side_effect=write_json or CONTROLLER.write_json
        ), mock.patch.object(CONTROLLER, "git", side_effect=git or (lambda *_args, **_kwargs: "a" * 40)):
            try:
                outcome: Any = CONTROLLER.run_controller(state, {})
            except CONTROLLER.RunInterrupted as escaped:
                outcome = escaped
        durable = json.loads((directory / "state.json").read_text())
        log = directory / "events.jsonl"
        events = [json.loads(line)["event"] for line in log.read_text().splitlines()] if log.exists() else []
        return outcome, durable, events

    def test_stop_signal_inside_the_interruption_record_keeps_its_event(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith stop record ") as temporary:
            write_state = CONTROLLER.write_json
            signalled: list[bool] = []

            def stop_during_record(path: Path, value: dict[str, Any]) -> None:
                if value.get("status") == "interrupted" and not signalled:
                    signalled.append(True)
                    CONTROLLER.signal.raise_signal(CONTROLLER.signal.SIGTERM)
                write_state(path, value)

            outcome, durable, events = self.stopped_controller_outcome(
                Path(temporary), write_json=stop_during_record)
            self.assertEqual(signalled, [True])
            self.assertEqual(events, ["run_interrupted"])
            self.assertEqual(outcome, 130)
            self.assertEqual(durable["status"], "interrupted")
            self.assertIsNone(durable["active_pid"])

    def test_stop_signal_during_terminal_cleanup_still_exits_as_interrupted(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith stop cleanup ") as temporary:
            signalled: list[bool] = []

            def stop_during_cleanup(*_args: Any, **_kwargs: Any) -> str:
                signalled.append(True)
                CONTROLLER.signal.raise_signal(CONTROLLER.signal.SIGTERM)
                return "a" * 40

            outcome, durable, events = self.stopped_controller_outcome(
                Path(temporary), git=stop_during_cleanup)
            self.assertEqual(signalled, [True])
            self.assertEqual(outcome, 130)
            self.assertEqual(events, ["run_interrupted"])
            self.assertEqual(durable["terminal_head"], "a" * 40)

    def test_stop_signal_inside_the_escalation_record_keeps_the_escalation(self) -> None:
        # Once the run has decided its own result, a late stop changes nothing.
        with tempfile.TemporaryDirectory(prefix="agentsmith stop escalation ") as temporary:
            write_state = CONTROLLER.write_json
            signalled: list[bool] = []

            def scope_error(_state: dict[str, Any], _manifest: dict[str, Any]) -> int:
                raise CONTROLLER.RunError("maker changed paths outside scope: forbidden.txt")

            def stop_during_record(path: Path, value: dict[str, Any]) -> None:
                if value.get("status") == "escalated" and not signalled:
                    signalled.append(True)
                    CONTROLLER.signal.raise_signal(CONTROLLER.signal.SIGTERM)
                write_state(path, value)

            outcome, durable, events = self.stopped_controller_outcome(
                Path(temporary), execute=scope_error, write_json=stop_during_record)
            self.assertEqual(signalled, [True])
            self.assertEqual(outcome, 2)
            self.assertEqual(events, ["run_escalated"])
            self.assertEqual(durable["status"], "escalated")

    def test_stop_signal_after_the_acceptance_record_keeps_the_acceptance(self) -> None:
        for point in ("while reporting", "during terminal cleanup"):
            with self.subTest(point=point), \
                    tempfile.TemporaryDirectory(prefix="agentsmith stop acceptance ") as temporary:
                signalled: list[bool] = []

                def stop_now() -> None:
                    signalled.append(True)
                    CONTROLLER.signal.raise_signal(CONTROLLER.signal.SIGTERM)

                def accept(state: dict[str, Any], _manifest: dict[str, Any]) -> int:
                    # The end of execute(): decide, record, report.
                    state["status"] = "accepted"
                    state["stage"] = "accepted"
                    state["accepted_commit"] = "b" * 40
                    CONTROLLER.save_state(state, "run_accepted", commit="b" * 40)
                    if point == "while reporting":
                        stop_now()
                    return 0

                def stop_during_cleanup(*_args: Any, **_kwargs: Any) -> str:
                    stop_now()
                    return "a" * 40

                outcome, durable, events = self.stopped_controller_outcome(
                    Path(temporary), execute=accept,
                    git=stop_during_cleanup if point == "during terminal cleanup" else None)
                self.assertEqual(signalled, [True])
                self.assertEqual(outcome, 0)
                self.assertEqual(events, ["run_accepted"])
                self.assertEqual(durable["status"], "accepted")
                self.assertEqual(durable["terminal_head"], "a" * 40)

    def test_stop_signal_after_the_controller_returns_keeps_the_exit_code(self) -> None:
        # The process still releases its lifecycle lock after the controller returns, so a stop
        # signal then must not end it by the default action.
        child = (
            "import importlib.util, signal, sys, tempfile\n"
            "from pathlib import Path\n"
            "from unittest import mock\n"
            "spec = importlib.util.spec_from_file_location('controller', sys.argv[1])\n"
            "c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)\n"
            "def accept(state, _manifest):\n"
            "    state['status'] = 'accepted'\n"
            "    return 0\n"
            "outcome = accept if sys.argv[2] == 'accepted' else c.RunInterrupted('stopped by operator')\n"
            "with tempfile.TemporaryDirectory() as temporary:\n"
            "    directory = Path(temporary) / 'controller'; directory.mkdir()\n"
            "    state = {'run_id': 'active', 'state_path': str(directory / 'state.json'),\n"
            "             'worktree': temporary, 'status': 'making', 'active_pid': None}\n"
            "    with mock.patch.object(c, 'execute', side_effect=outcome), \\\n"
            "            mock.patch.object(c, 'git', return_value='a' * 40):\n"
            "        code = c.run_controller(state, {})\n"
            "    signal.raise_signal(signal.SIGTERM)\n"
            "    print('lock released', flush=True)\n"
            "raise SystemExit(code)\n"
        )
        for result_name, expected in (("interrupted", 130), ("accepted", 0)):
            with self.subTest(result=result_name):
                result = subprocess.run(
                    [CONTROLLER.sys.executable, "-c", child, str(CONTROLLER_PATH), result_name],
                    capture_output=True, text=True, check=False, timeout=60)
                self.assertEqual((result.returncode, result.stdout.strip()),
                                 (expected, "lock released"), result.stderr)

    def test_stop_signal_during_a_git_call_lets_the_call_finish(self) -> None:
        # A handler that raises can land inside `subprocess` itself. One stop landed after
        # `subprocess` had taken its private wait lock during `git worktree remove`; the lock was
        # never released and the controller waited for five hours. The call must finish, and
        # the stop is recorded at the next safe point.
        if os.name == "nt":
            self.skipTest("Windows ends the controller on SIGTERM without calling a handler")
        child = (
            "import importlib.util, json, sys, tempfile\n"
            "from pathlib import Path\n"
            "from unittest import mock\n"
            "spec = importlib.util.spec_from_file_location('controller', sys.argv[1])\n"
            "c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)\n"
            "signaller = 'import os, signal, time; os.kill(os.getppid(), signal.SIGTERM); time.sleep(0.5)'\n"
            "def work(state, _manifest):\n"
            "    result = c.run([sys.executable, '-c', signaller], Path(state['worktree']))\n"
            "    print('call finished', result.returncode, flush=True)\n"
            "    c.checkpoint_stage(state, 'verifying')\n"
            "    print('stop not noticed', flush=True)\n"
            "    return 0\n"
            "with tempfile.TemporaryDirectory() as temporary:\n"
            "    directory = Path(temporary) / 'controller'; directory.mkdir()\n"
            "    state = {'run_id': 'active', 'state_path': str(directory / 'state.json'),\n"
            "             'worktree': temporary, 'status': 'checking', 'attempt': 1, 'active_pid': None}\n"
            "    with mock.patch.object(c, 'execute', side_effect=work), \\\n"
            "            mock.patch.object(c, 'git', return_value='a' * 40):\n"
            "        code = c.run_controller(state, {})\n"
            "    durable = json.loads((directory / 'state.json').read_text())\n"
            "    log = (directory / 'events.jsonl').read_text().splitlines()\n"
            "    events = ' '.join(json.loads(line)['event'] for line in log)\n"
            "    print('outcome', code, durable['status'], durable.get('stage'), events, flush=True)\n"
        )
        result = subprocess.run([CONTROLLER.sys.executable, "-c", child, str(CONTROLLER_PATH)],
                                capture_output=True, text=True, check=False, timeout=60)
        self.assertEqual(result.stdout.splitlines(),
                         ["call finished 0",
                          "outcome 130 interrupted verifying stage_started run_interrupted"],
                         result.stderr)

    def test_stop_ends_a_wait_for_a_git_phase_but_not_its_release(self) -> None:
        # The handler no longer raises, so a wait to acquire must notice the stop itself. A
        # release must not: raising there would leave the lease for other runs to wait on.
        with tempfile.TemporaryDirectory(prefix="agentsmith phase stop ") as temporary:
            repo = Path(temporary)
            root = repo / "run-state"
            phase_dir = root / "git-phases"
            try:
                with mock.patch.object(CONTROLLER, "state_root", return_value=root):
                    with CONTROLLER.git_phase(repo, "writer", timeout_seconds=2):
                        stop = threading.Timer(0.2, setattr, (CONTROLLER, "_stop_signal_received", True))
                        started = time.monotonic()
                        stop.start()
                        with self.assertRaises(CONTROLLER.RunInterrupted):
                            with CONTROLLER.git_phase(repo, "checker", timeout_seconds=30):
                                pass
                        self.assertLess(time.monotonic() - started, 5)
                        # A peer holds the coordination lock while this phase is released.
                        CONTROLLER.coordination_lock_path(root).write_text(
                            json.dumps({"pid": os.getpid(), "run_id": "coordination", "token": "peer"}),
                            encoding="utf-8")
                        free = threading.Timer(0.3, CONTROLLER.coordination_lock_path(root).unlink)
                        free.start()
                    free.join()
                    self.assertEqual(list(phase_dir.glob("*.json")), [])
            finally:
                CONTROLLER._stop_signal_received = False

    def test_stop_signal_ends_a_process_that_stop_could_not_see(self) -> None:
        # `stop` ends the process it finds in state.json. One started just after that read is
        # ended by the controller: its handler signals the pid it knows in memory, and the wait
        # notices the stop even when the process ignores that signal.
        if os.name == "nt":
            self.skipTest("POSIX process groups")
        children = {
            "accepts SIGTERM": "import time; time.sleep(30)",
            "ignores SIGTERM": "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)",
        }
        for name, child in children.items():
            with self.subTest(child=name), \
                    tempfile.TemporaryDirectory(prefix="agentsmith stop unseen ") as temporary:
                directory = Path(temporary) / "controller"
                directory.mkdir()
                state = {"run_id": "active", "state_path": str(directory / "state.json"),
                         "worktree": temporary, "status": "checking", "attempt": 1, "active_pid": None}

                def verify(state: dict[str, Any], _manifest: dict[str, Any]) -> int:
                    signal_later = threading.Timer(
                        0.5, os.kill, (os.getpid(), CONTROLLER.signal.SIGTERM))
                    signal_later.start()
                    try:
                        CONTROLLER.verifier_process([CONTROLLER.sys.executable, "-c", child],
                                                    Path(temporary), 60, dict(os.environ), state)
                    finally:
                        signal_later.cancel()
                    return 0

                started = time.monotonic()
                with mock.patch.object(CONTROLLER, "execute", side_effect=verify), \
                        mock.patch.object(CONTROLLER, "git", return_value="a" * 40):
                    self.assertEqual(CONTROLLER.run_controller(state, {}), 130)
                self.assertLess(time.monotonic() - started, 15)
                exit_record = json.loads((directory / "attempt-1-verify-exit.json").read_text())
                self.assertNotEqual(exit_record["exit_code"], 0)
                durable = json.loads((directory / "state.json").read_text())
                self.assertEqual((durable["status"], durable["active_pid"]), ("interrupted", None))

    def test_terminating_a_group_that_holds_only_a_zombie_is_not_an_error(self) -> None:
        # The stop handler can end a role before the controller's own cleanup runs, so the
        # cleanup can meet a group whose only member has exited but is not reaped yet.
        if os.name == "nt":
            self.skipTest("POSIX process groups")
        process = subprocess.Popen([CONTROLLER.sys.executable, "-c", "pass"], start_new_session=True)
        try:
            for _ in range(500):
                if not CONTROLLER.process_group_is_live(process.pid):
                    break
                time.sleep(0.01)
            CONTROLLER.terminate_process_tree(process.pid)
        finally:
            process.wait(timeout=10)

    def run_with_fake_roles(self, common: Path, *, max_attempts: int, checker_status: str,
                            stop_during_checker: bool = False,
                            stop_maker_phase_wait_on_attempt: int = 0) -> tuple[int, dict[str, Any], list[str]]:
        """Drive the real attempt loop with Git and the roles replaced by fakes, so a stop can be
        delivered at an exact point of it."""
        directory = common / "controller"
        directory.mkdir()
        worktree = common / "worktree"
        worktree.mkdir()
        head = {"value": "a" * 40}
        state = {"run_id": "active", "state_path": str(directory / "state.json"),
                 "worktree": str(worktree), "repo": str(common), "branch": "agentsmith/active",
                 "base_head": "a" * 40, "status": "prepared", "attempt": 0, "active_pid": None,
                 "deadline_epoch": time.time() + 600}
        manifest = {"limits": {"max_attempts": max_attempts}, "verify": {"command": "true"},
                    "spec_path": "docs/specs/task.md", "implementation_ticket": "TASK-1",
                    "scope": {"allowed_paths": ["a.txt"], "denied_paths": []},
                    "roles": {"maker": {"runtime": "claude"}, "checker": {"runtime": "claude"}}}

        def fake_git(_repo: Path, *args: str, check: bool = True) -> str:
            return head["value"] if args == ("rev-parse", "HEAD") else ""

        @contextlib.contextmanager
        def fake_phase(_repo: Path, phase: str, **_kwargs: Any):
            if phase == "maker" and state["attempt"] == stop_maker_phase_wait_on_attempt:
                raise CONTROLLER.RunInterrupted("stopped by operator")  # the stop ends the wait
            yield

        def fake_role(state: dict[str, Any], _manifest: dict[str, Any], role: str, _prompt: str,
                      **_kwargs: Any) -> dict[str, Any]:
            status = "completed"
            if role == "maker":
                head["value"] = str(state["attempt"]) * 40
            else:
                status = checker_status
                if stop_during_checker:
                    os.kill(os.getpid(), CONTROLLER.signal.SIGTERM)
            return {"status": status, "summary": role, "commit": head["value"],
                    "changed_paths": ["a.txt"], "evidence": ["fake evidence"], "unresolved": [],
                    "next_state": ""}

        @contextlib.contextmanager
        def fake_checker_worktree(*args: Any):
            yield args[-1]

        verified = subprocess.CompletedProcess([], 0, "", "")
        with contextlib.ExitStack() as fakes:
            for name, value in {
                "git": fake_git, "git_phase": fake_phase, "launch_role": fake_role,
                "checker_worktree_session": fake_checker_worktree,
                "coordination_lock": lambda *_args, **_kwargs: contextlib.nullcontext(),
                "git_metadata": lambda *_args, **_kwargs: {"registered_peers": {}},
                "validate_git_transition": lambda *_args: None,
                "validate_git_unchanged": lambda *_args: None,
                "validate_verification_changes": lambda *_args, **_kwargs: None,
                "verification_binding": lambda *_args: {},
                "ignored_paths": lambda *_args: set(), "clean": lambda *_args: True,
                "changed_paths": lambda *_args: ["a.txt"], "path_allowed": lambda *_args: True,
                "sandboxed_verify": lambda *_args, **_kwargs: verified,
                "file_digest": lambda *_args: "0" * 64,
            }.items():
                fakes.enter_context(mock.patch.object(CONTROLLER, name, side_effect=value))
            outcome = CONTROLLER.run_controller(state, manifest)
        durable = json.loads((directory / "state.json").read_text())
        events = [json.loads(line)["event"] for line in (directory / "events.jsonl").read_text().splitlines()]
        return outcome, durable, events

    def test_fake_roles_reach_acceptance_without_a_stop(self) -> None:
        # Control for the cases below: the fakes alone lead to an accepted run.
        with tempfile.TemporaryDirectory(prefix="agentsmith fake roles ") as temporary:
            outcome, durable, events = self.run_with_fake_roles(
                Path(temporary), max_attempts=1, checker_status="accepted")
            self.assertEqual((outcome, durable["status"], events[-1]), (0, "accepted", "run_accepted"))

    def test_stop_before_the_acceptance_record_interrupts_the_run(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith stop before acceptance ") as temporary:
            outcome, durable, events = self.run_with_fake_roles(
                Path(temporary), max_attempts=1, checker_status="accepted", stop_during_checker=True)
            self.assertEqual((outcome, durable["status"]), (130, "interrupted"))
            self.assertNotIn("run_accepted", events)

    def test_stop_before_the_attempt_cap_record_interrupts_the_run(self) -> None:
        # The checker rejects the last attempt while a stop is pending: the stop wins over the
        # attempt-cap escalation, as it does over acceptance.
        with tempfile.TemporaryDirectory(prefix="agentsmith stop before cap ") as temporary:
            outcome, durable, events = self.run_with_fake_roles(
                Path(temporary), max_attempts=1, checker_status="rejected", stop_during_checker=True)
            self.assertEqual((outcome, durable["status"]), (130, "interrupted"))
            self.assertNotIn("run_escalated", events)

    def test_stop_while_an_attempt_waits_for_its_git_phase_keeps_the_run_resumable(self) -> None:
        # Attempt 1 moves HEAD and is rejected; the stop ends attempt 2's wait for the maker
        # phase. Resume rejects a `making` checkpoint whose start differs from HEAD, so the
        # checkpoint must already carry this attempt's start.
        with tempfile.TemporaryDirectory(prefix="agentsmith stop phase wait ") as temporary:
            outcome, durable, _events = self.run_with_fake_roles(
                Path(temporary), max_attempts=2, checker_status="rejected",
                stop_maker_phase_wait_on_attempt=2)
            self.assertEqual((outcome, durable["status"], durable["stage"], durable["attempt"]),
                             (130, "interrupted", "making", 2))
            self.assertEqual(durable["maker_before_head"], "1" * 40)

    def test_stop_reports_a_run_that_already_finished(self) -> None:
        for status in ("accepted", "escalated"):
            with self.subTest(status=status), \
                    tempfile.TemporaryDirectory(prefix="agentsmith stop finished ") as temporary:
                run_dir = Path(temporary)
                state = {"run_id": "done", "state_path": str(run_dir / "state.json"),
                         "status": status, "active_pid": None}
                with mock.patch.object(CONTROLLER, "repo_root", return_value=run_dir), \
                        mock.patch.object(CONTROLLER, "load_run", return_value=state), \
                        mock.patch.object(CONTROLLER, "read_lock", return_value=None), \
                        mock.patch("sys.stdout", new_callable=io.StringIO) as output:
                    self.assertEqual(CONTROLLER.stop(mock.Mock(run_id="done")), 0)
                self.assertIn(f"done already finished as {status}; the stop changed nothing",
                              output.getvalue())

    def test_checker_recovery_clears_the_entry_a_stopped_removal_left(self) -> None:
        # `git worktree remove` deletes the folder before the entry under .git/worktrees, so a
        # stop between the two leaves the entry. Resume compares Git metadata with the snapshot
        # taken before the maker, and the leftover entry escalated every resume.
        for shape in ("complete entry", "entry without gitdir", "foreign entry"):
            with self.subTest(shape=shape), \
                    tempfile.TemporaryDirectory(prefix="agentsmith checker recovery ") as temporary:
                root = Path(temporary).resolve()
                repo = root / "repo"
                subprocess.run(["git", "init", "-q", str(repo)], check=True)
                subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c",
                                "user.email=test@example.com", "commit", "-q", "--allow-empty",
                                "-m", "fixture"], check=True)
                worktree = root / "run"
                subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", "-b",
                                "agentsmith/fixture", str(worktree)], check=True)
                checker = worktree.with_name(f"{worktree.name}-check-1")
                entry = repo / ".git" / "worktrees" / checker.name
                if shape == "foreign entry":
                    # Another worktree took the checker's entry name; it is not this run's.
                    foreign = root / "elsewhere" / checker.name
                    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", "--detach",
                                    str(foreign), "HEAD"], check=True)
                    foreign_gitdir = (entry / "gitdir").read_text(encoding="utf-8")
                before = CONTROLLER.git_metadata(worktree)
                if shape != "foreign entry":
                    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", "--detach",
                                    str(checker), "HEAD"], check=True)
                    shutil.rmtree(checker)
                    if shape == "entry without gitdir":
                        (entry / "gitdir").unlink()
                self.assertTrue(entry.is_dir())
                run_dir = root / "state"
                run_dir.mkdir()
                state = {"repo": str(repo), "worktree": str(worktree), "attempt": 1,
                         "checker_worktree": str(checker), "state_path": str(run_dir / "state.json")}
                with mock.patch.object(CONTROLLER, "remaining_seconds", return_value=60):
                    CONTROLLER.recover_checker_worktree(state, {})
                self.assertNotIn("checker_worktree", state)
                after = CONTROLLER.git_metadata(worktree, known_peers=before["registered_peers"])
                self.assertEqual(after["protected_files"], before["protected_files"])
                if shape == "foreign entry":
                    self.assertEqual((entry / "gitdir").read_text(encoding="utf-8"), foreign_gitdir)
                    continue
                self.assertFalse(entry.exists())
                # The next checker session adds the same path again.
                subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", "--detach",
                                str(checker), "HEAD"], check=True)

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
            self.assertIn("refs/heads/agentsmith/peer", " ".join(CONTROLLER.git_metadata(repo)["refs"]))

    def test_maker_metadata_recognizes_peer_started_during_initial_snapshot(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith snapshot race ") as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
            (repo / "README.md").write_text("fixture\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)
            manifest = repo / "peer.json"
            manifest.write_text('{"run_id":"peer"}\n', encoding="utf-8")
            worktree = Path(temporary) / "peer-worktree"
            original_git = CONTROLLER.git
            created = False

            def create_peer_after_ref_read(path: Path, *args: str, **kwargs: Any) -> str:
                nonlocal created
                result = original_git(path, *args, **kwargs)
                if args and args[0] == "for-each-ref" and not created:
                    created = True
                    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-qb",
                                    "agentsmith/peer", str(worktree), "HEAD"], check=True)
                    run_dir = CONTROLLER.state_root(repo) / "peer"
                    run_dir.mkdir(parents=True)
                    CONTROLLER.write_json(run_dir / "state.json", {
                        "run_id": "peer", "branch": "agentsmith/peer", "repo": str(repo),
                        "manifest_path": str(manifest),
                        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                        "worktree": str(worktree), "status": "accepted",
                        "started_epoch": time.time(),
                        "terminal_head": original_git(worktree, "rev-parse", "HEAD"),
                    })
                return result

            with mock.patch.object(CONTROLLER, "git", side_effect=create_peer_after_ref_read):
                before = CONTROLLER.git_metadata(repo)
            self.assertTrue(created)
            after = CONTROLLER.git_metadata(repo, known_peers=before["registered_peers"])
            self.assertEqual(before["refs"], after["refs"])

    def test_maker_metadata_keeps_ref_seen_before_peer_state_exists(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith peer ref race ") as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
            (repo / "README.md").write_text("fixture\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)
            worktree = Path(temporary) / "peer-worktree"
            subprocess.run(["git", "-C", str(repo), "worktree", "add", "-qb",
                            "agentsmith/peer", str(worktree), "HEAD"], check=True)
            before = CONTROLLER.git_metadata(repo)
            self.assertIn("refs/heads/agentsmith/peer", " ".join(before["refs"]))

            manifest = repo / "peer.json"
            manifest.write_text('{"run_id":"peer"}\n', encoding="utf-8")
            run_dir = CONTROLLER.state_root(repo) / "peer"
            run_dir.mkdir(parents=True)
            CONTROLLER.write_json(run_dir / "state.json", {
                "run_id": "peer", "branch": "agentsmith/peer", "repo": str(repo),
                "manifest_path": str(manifest),
                "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "worktree": str(worktree), "status": "accepted",
                "started_epoch": time.time(),
                "terminal_head": CONTROLLER.git(worktree, "rev-parse", "HEAD"),
            })
            after = CONTROLLER.git_metadata(repo, known_peers=before["registered_peers"])
            self.assertEqual(before["refs"], after["refs"])
            (worktree / "change.txt").write_text("peer change\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(worktree), "add", "change.txt"], check=True)
            subprocess.run(["git", "-C", str(worktree), "commit", "-qm", "peer change"], check=True)
            state = CONTROLLER.load_json(run_dir / "state.json")
            state["terminal_head"] = CONTROLLER.git(worktree, "rev-parse", "HEAD")
            CONTROLLER.write_json(run_dir / "state.json", state)
            changed = CONTROLLER.git_metadata(repo, known_peers=before["registered_peers"])
            main_head = CONTROLLER.git(repo, "rev-parse", "HEAD")
            with self.assertRaisesRegex(CONTROLLER.RunError, "Git refs outside"):
                CONTROLLER.validate_git_transition(repo, before, changed, "main", main_head, main_head)

    def test_maker_metadata_exempts_verified_terminal_peer_across_resume(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentsmith terminal peer ") as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
            (repo / "README.md").write_text("fixture\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)
            manifest = repo / "peer.json"
            manifest.write_text('{"run_id":"peer"}\n', encoding="utf-8")
            worktree = Path(temporary) / "peer-worktree"
            subprocess.run(["git", "-C", str(repo), "worktree", "add", "-qb",
                            "agentsmith/peer", str(worktree), "HEAD"], check=True)
            run_dir = CONTROLLER.state_root(repo) / "peer"
            run_dir.mkdir(parents=True)
            CONTROLLER.write_json(run_dir / "state.json", {
                "run_id": "peer", "branch": "agentsmith/peer", "repo": str(repo),
                "manifest_path": str(manifest),
                "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "worktree": str(worktree), "status": "interrupted",
                "started_epoch": time.time() - 10,
                "terminal_head": CONTROLLER.git(worktree, "rev-parse", "HEAD"),
            })
            before = CONTROLLER.git_metadata(repo)
            self.assertNotIn("refs/heads/agentsmith/peer", " ".join(before["refs"]))
            (worktree / "change.txt").write_text("resumed peer\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(worktree), "add", "change.txt"], check=True)
            subprocess.run(["git", "-C", str(worktree), "commit", "-qm", "resumed peer"], check=True)
            state = CONTROLLER.load_json(run_dir / "state.json")
            state.update(status="accepted", resumed_epoch=time.time(),
                         terminal_head=CONTROLLER.git(worktree, "rev-parse", "HEAD"))
            CONTROLLER.write_json(run_dir / "state.json", state)
            after = CONTROLLER.git_metadata(repo, known_peers=before["registered_peers"])
            self.assertEqual(before["refs"], after["refs"])
            self.assertEqual(before["protected_files"], after["protected_files"])

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
