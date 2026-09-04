#!/usr/bin/env python3
"""Cross-platform behavioral tests for durable verification receipts."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "agentsmith.py"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
FINAL_STATUSES = {"passed", "failed", "error"}
SPEC = importlib.util.spec_from_file_location("agentsmith_verify_receipts", CORE)
assert SPEC and SPEC.loader
AGENTSMITH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AGENTSMITH)


def shell_command(*arguments: str) -> str:
    """Quote one argv for the native shell used by agentsmith verify."""
    return subprocess.list2cmdline(list(arguments)) if os.name == "nt" else shlex.join(arguments)


class VerifyReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="agentsmith verify receipt ü ")
        self.root = Path(self.temporary.name) / "project with spaces ü"
        (self.root / ".harness").mkdir(parents=True)
        self.helper = self.root / "phase helper ü.py"
        self.helper.write_text(
            """from pathlib import Path
import sys
import time

action = sys.argv[1]
if action == "emit":
    print(sys.argv[2], flush=True)
elif action == "emit_pem":
    print("-----BEGIN RSA PRIV" + "ATE KEY-----", flush=True)
    print("c3VwZXItc2VjcmV0LWtleS1ib2R5", flush=True)
    print("YW5vdGhlci1zZWNyZXQtbGluZQ==", flush=True)
    print("-----END RSA PRIV" + "ATE KEY-----", flush=True)
elif action == "emit_mismatched_pem":
    print("-----BEGIN RSA PRIV" + "ATE KEY-----", flush=True)
    print("cHJpdmF0ZS1ibG9jay1wcmVmaXg=", flush=True)
    print("-----END EC PRIV" + "ATE KEY-----", flush=True)
    print("bXVzdC1yZW1haW4taGlkZGVu", flush=True)
    print("-----END RSA PRIV" + "ATE KEY-----", flush=True)
elif action == "emit_prefixed_pem_end":
    print("-----BEGIN RSA PRIV" + "ATE KEY-----", flush=True)
    print("-----END RSA PRIV" + "ATE KEYCHAIN-----", flush=True)
    print("Zmlyc3QtaGlkZGVuLWJvZHk=", flush=True)
    print("XEND RSA PRIV" + "ATE KEYX", flush=True)
    print("c2Vjb25kLWhpZGRlbi1ib2R5", flush=True)
    print("X-----END RSA PRIV" + "ATE KEY-----X", flush=True)
    print("ZGFzaGVkLWRlY29yYXRlZC1oaWRkZW4=", flush=True)
    print("-----END RSA PRIV" + "ATE KEY EXTRA-----", flush=True)
    print("dGhpcmQtaGlkZGVuLWJvZHk=", flush=True)
    print("END RSA PRIV" + "ATE KEY EXTRA", flush=True)
    print("Zm91cnRoLWhpZGRlbi1ib2R5", flush=True)
    print("END RSA PRIV" + "ATE KEY: EXTRA", flush=True)
    print("ZmlmdGgtaGlkZGVuLWJvZHk=", flush=True)
    print("-----END RSA PRIV" + "ATE KEY-----", flush=True)
elif action == "fail":
    print(sys.argv[2], flush=True)
    raise SystemExit(int(sys.argv[3]))
elif action == "mark":
    Path(sys.argv[2]).write_text(sys.argv[3], encoding="utf-8")
elif action == "sleep":
    print("phase waiting", flush=True)
    time.sleep(float(sys.argv[2]))
else:
    raise SystemExit(99)
""",
            encoding="utf-8",
        )
        self.env = os.environ.copy()
        self.env["PYTHONUTF8"] = "1"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def phase(self, action: str, *arguments: str) -> str:
        return shell_command(sys.executable, str(self.helper), action, *arguments)

    def configure(self, *phases: tuple[str, str]) -> Path:
        conf = self.root / ".harness" / "verify.conf"
        conf.write_text(
            "".join(f"{label} :: {command}\n" for label, command in phases),
            encoding="utf-8",
        )
        return conf

    def run_verify(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        resolved_arguments = list(arguments)
        if "--record" in resolved_arguments and "--tree-class" not in resolved_arguments:
            resolved_arguments.extend(("--tree-class", "operator-worktree"))
        return subprocess.run(
            [sys.executable, str(CORE), "verify", "--target", str(self.root), *resolved_arguments],
            cwd=ROOT,
            env=self.env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=30,
        )

    @staticmethod
    def read_receipt(directory: Path) -> dict:
        return json.loads((directory / "receipt.json").read_text(encoding="utf-8"))

    @staticmethod
    def artifact(directory: Path, stored_path: str) -> Path:
        candidate = Path(stored_path)
        return candidate if candidate.is_absolute() else directory / candidate

    def assert_timestamp(self, value: object) -> None:
        self.assertIsInstance(value, str)
        dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))

    def assert_valid_receipt(self, directory: Path, receipt: dict, *, final: bool) -> None:
        self.assertEqual(receipt["schema_version"], 1)
        self.assertEqual(Path(receipt["target"]), self.root.resolve())
        self.assertIn(
            receipt["tree_class"],
            {"clean-clone", "disposable-fixture", "linked-worktree", "operator-worktree"},
        )
        self.assert_timestamp(receipt["started_at"])
        self.assert_timestamp(receipt["updated_at"])
        if final:
            self.assertIn(receipt["status"], FINAL_STATUSES)
            self.assert_timestamp(receipt["completed_at"])
        else:
            self.assertEqual(receipt["status"], "running")
            self.assertIsNone(receipt["completed_at"])

        configuration = receipt["configuration"]
        self.assertEqual(Path(configuration["path"]), (self.root / ".harness" / "verify.conf").resolve())
        self.assertRegex(configuration["sha256"], SHA256)

        git = receipt["git"]
        self.assertIsInstance(git["available"], bool)
        self.assertIn("head", git)
        self.assertIn("branch", git)
        self.assertIn("dirty", git)
        observed_platform = receipt["platform"]
        self.assertEqual(observed_platform["os"], platform.system())
        self.assertEqual(observed_platform["python_version"], platform.python_version())

        for index, phase in enumerate(receipt["phases"], 1):
            self.assertEqual(phase["index"], index)
            self.assertIn(phase["status"], {"pending", "running", "passed", "failed", "error"})
            self.assertIsInstance(phase["redactions"], list)
            if phase["status"] in FINAL_STATUSES:
                self.assert_timestamp(phase["started_at"])
                self.assert_timestamp(phase["completed_at"])
                self.assertIsInstance(phase["duration_seconds"], (int, float))
                self.assertGreaterEqual(phase["duration_seconds"], 0)
                if phase["status"] in {"passed", "failed"}:
                    self.assertIsInstance(phase["exit_code"], int)
                self.assertEqual(set(phase["output_paths"]), set(phase["output_hashes"]))
                for stream, stored_path in phase["output_paths"].items():
                    path = self.artifact(directory, stored_path)
                    self.assertTrue(path.is_file(), f"missing {stream} artifact: {path}")
                    content = path.read_bytes()
                    self.assertEqual(phase["output_hashes"][stream], hashlib.sha256(content).hexdigest())
                    self.assertRegex(phase["output_hashes"][stream], SHA256)

    def test_successful_multi_phase_run_records_metadata_and_stable_output_hashes(self) -> None:
        conf = self.configure(
            ("build ü", self.phase("emit", "first output ü")),
            ("tests", self.phase("emit", "second output")),
        )
        first_directory = self.root / "receipt one ü"
        first = self.run_verify("--record", first_directory.name)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        receipt = self.read_receipt(first_directory)
        self.assert_valid_receipt(first_directory, receipt, final=True)
        self.assertEqual(receipt["status"], "passed")
        self.assertIsNone(receipt["only"])
        self.assertEqual(receipt["configuration"]["sha256"], hashlib.sha256(conf.read_bytes()).hexdigest())
        self.assertEqual([phase["status"] for phase in receipt["phases"]], ["passed", "passed"])
        self.assertIn("first output ü", first.stdout)
        self.assertIn("second output", first.stdout)

        second_directory = self.root / "receipt two ü"
        second = self.run_verify("--record", second_directory.name)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        second_receipt = self.read_receipt(second_directory)
        self.assertEqual(
            [phase["output_hashes"] for phase in receipt["phases"]],
            [phase["output_hashes"] for phase in second_receipt["phases"]],
        )
        self.assertEqual(
            [phase["output_paths"] for phase in receipt["phases"]],
            [phase["output_paths"] for phase in second_receipt["phases"]],
            "equivalent phases should use deterministic relative sidecar paths",
        )
        for phase in receipt["phases"]:
            self.assertTrue(all(not Path(path).is_absolute() for path in phase["output_paths"].values()))

    def test_failure_stops_later_phases_and_preserves_process_exit_code(self) -> None:
        marker = self.root / "must not run.txt"
        self.configure(
            ("first", self.phase("emit", "before failure")),
            ("failing", self.phase("fail", "expected failure", "7")),
            ("later", self.phase("mark", str(marker), "ran")),
        )
        directory = self.root / "failed receipt"
        result = self.run_verify("--record", directory.name)
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        self.assertFalse(marker.exists())
        receipt = self.read_receipt(directory)
        self.assert_valid_receipt(directory, receipt, final=True)
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual([phase["status"] for phase in receipt["phases"]], ["passed", "failed", "pending"])
        self.assertEqual(receipt["phases"][1]["exit_code"], 7)

    def test_running_receipt_is_durable_between_phase_updates(self) -> None:
        self.configure(
            ("first", self.phase("emit", "finished first")),
            ("waiting", self.phase("sleep", "30")),
        )
        directory = self.root / "partial receipt"
        command = [
            sys.executable,
            str(CORE),
            "verify",
            "--target",
            str(self.root),
            "--record",
            directory.name,
            "--tree-class",
            "operator-worktree",
        ]
        process_options: dict[str, object] = {}
        if os.name == "nt":
            process_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            process_options["start_new_session"] = True
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            **process_options,
        )
        try:
            deadline = time.monotonic() + 10
            receipt: dict = {}
            while time.monotonic() < deadline:
                try:
                    receipt = self.read_receipt(directory)
                except (FileNotFoundError, json.JSONDecodeError):
                    time.sleep(0.05)
                    continue
                statuses = [phase["status"] for phase in receipt.get("phases", [])]
                if statuses == ["passed", "running"]:
                    break
                time.sleep(0.05)
            else:
                self.fail(f"receipt never reached durable partial state: {receipt}")
            self.assert_valid_receipt(directory, receipt, final=False)
        finally:
            if process.poll() is None:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        capture_output=True,
                        check=False,
                    )
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
            if process.stdout is not None:
                process.stdout.close()

    def test_git_and_non_git_targets_record_truthful_repository_state(self) -> None:
        self.configure(("check", self.phase("emit", "ok")))
        non_git_directory = Path(self.temporary.name) / "non git receipt"
        non_git = self.run_verify("--record", str(non_git_directory))
        self.assertEqual(non_git.returncode, 0, non_git.stdout + non_git.stderr)
        non_git_metadata = self.read_receipt(non_git_directory)["git"]
        self.assertIsNone(non_git_metadata["head"])
        self.assertIsNone(non_git_metadata["branch"])
        self.assertIsNone(non_git_metadata["dirty"])

        subprocess.run(["git", "-C", str(self.root), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "Receipt Test"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email", "user@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", ".harness/verify.conf", self.helper.name], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "test: establish fixture"], check=True)

        clean_directory = self.root / "clean git receipt"
        clean_result = self.run_verify("--record", clean_directory.name)
        self.assertEqual(clean_result.returncode, 0, clean_result.stdout + clean_result.stderr)
        clean_metadata = self.read_receipt(clean_directory)["git"]
        self.assertTrue(clean_metadata["available"])
        self.assertRegex(clean_metadata["head"], r"[0-9a-f]{40}\Z")
        self.assertTrue(clean_metadata["branch"])
        self.assertFalse(clean_metadata["dirty"])

        (self.root / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        git_directory = self.root / "git receipt"
        git_result = self.run_verify("--record", git_directory.name)
        self.assertEqual(git_result.returncode, 0, git_result.stdout + git_result.stderr)
        git_metadata = self.read_receipt(git_directory)["git"]
        self.assertTrue(git_metadata["available"])
        self.assertRegex(git_metadata["head"], r"[0-9a-f]{40}\Z")
        self.assertTrue(git_metadata["branch"])
        self.assertTrue(git_metadata["dirty"])

    def test_record_requires_explicit_tree_class_and_clean_class_rejects_dirty_git(self) -> None:
        self.configure(("check", self.phase("emit", "ok")))
        missing = subprocess.run(
            [sys.executable, str(CORE), "verify", "--target", str(self.root), "--record", "missing-class"],
            cwd=ROOT, env=self.env, text=True, capture_output=True, check=False,
        )
        self.assertEqual(missing.returncode, 2)
        self.assertIn("tree class", missing.stderr.lower())

        subprocess.run(["git", "-C", str(self.root), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "Receipt Test"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email", "user@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "test: clean baseline"], check=True)
        local = self.root / "operator-local.txt"
        local.write_text("private operator bytes\n", encoding="utf-8")
        before = local.read_bytes()

        rejected = self.run_verify("--record", "false-clean", "--tree-class", "clean-clone")
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("clean-clone", rejected.stderr)
        self.assertEqual(before, local.read_bytes())
        self.assertFalse((self.root / "false-clean").exists())

        accepted = self.run_verify("--record", "operator", "--tree-class", "operator-worktree")
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        receipt = self.read_receipt(self.root / "operator")
        self.assertEqual(receipt["tree_class"], "operator-worktree")
        self.assertTrue(receipt["git"]["dirty"])
        self.assertEqual(before, local.read_bytes())

    def test_only_records_selected_filter_and_selected_phases(self) -> None:
        marker = self.root / "excluded.txt"
        self.configure(
            ("unit ü", self.phase("emit", "selected")),
            ("integration", self.phase("mark", str(marker), "ran")),
        )
        directory = self.root / "only receipt"
        result = self.run_verify("--only", "unit", "--record", directory.name)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(marker.exists())
        receipt = self.read_receipt(directory)
        self.assertEqual(receipt["only"], "unit")
        self.assertEqual([phase["label"] for phase in receipt["phases"]], ["unit ü"])

    def test_existing_destination_is_refused_before_any_phase_runs(self) -> None:
        marker = self.root / "ran.txt"
        self.configure(("write marker", self.phase("mark", str(marker), "ran")))
        directory = self.root / "existing receipt"
        directory.mkdir()
        sentinel = directory / "keep.txt"
        sentinel.write_text("keep\n", encoding="utf-8")
        result = self.run_verify("--record", directory.name)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("exist", result.stderr.lower())
        self.assertFalse(marker.exists())
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")
        self.assertFalse((directory / "receipt.json").exists())

    def test_record_cannot_be_combined_with_list(self) -> None:
        self.configure(("check", self.phase("emit", "must not run")))
        directory = self.root / "listed receipt"
        result = self.run_verify("--list", "--record", directory.name)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("--list", result.stderr)
        self.assertIn("--record", result.stderr)
        self.assertFalse(directory.exists())

    def test_capture_setup_error_finishes_an_honest_error_receipt(self) -> None:
        self.configure(("check", self.phase("emit", "must not run")))
        directory = self.root / "error receipt"
        arguments = argparse.Namespace(
            target=str(self.root), only=None, list=False, record=directory.name,
            tree_class="operator-worktree",
        )

        def fail_capture(_command: str, _root: Path, stdout_path: Path, stderr_path: Path) -> None:
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text("", encoding="utf-8")
            raise OSError("capture unavailable")

        with (
            mock.patch.object(AGENTSMITH, "recorded_verify_phase", side_effect=fail_capture),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaisesRegex(AGENTSMITH.CliError, "recording failed"),
        ):
            AGENTSMITH.cmd_verify(arguments)
        receipt = self.read_receipt(directory)
        self.assert_valid_receipt(directory, receipt, final=True)
        self.assertEqual(receipt["status"], "error")
        self.assertEqual(receipt["phases"][0]["status"], "error")
        self.assertIsNone(receipt["phases"][0]["exit_code"])

    def test_secret_shaped_output_and_command_are_redacted_everywhere(self) -> None:
        secret_value = "s" + "k-" + "A" * 32
        self.configure((secret_value, self.phase("fail", secret_value, "9")))
        directory = self.root / "redacted receipt"
        result = self.run_verify("--record", directory.name)
        self.assertEqual(result.returncode, 9, result.stdout + result.stderr)
        receipt = self.read_receipt(directory)
        serialized = json.dumps(receipt, ensure_ascii=False)
        sidecars = "".join(
            self.artifact(directory, path).read_text(encoding="utf-8")
            for phase in receipt["phases"]
            for path in phase["output_paths"].values()
        )
        exposed = result.stdout + result.stderr + serialized + sidecars
        self.assertNotIn(secret_value, exposed)
        self.assertIn("[REDACTED]", exposed)
        self.assertIn("OpenAI-style key", receipt["phases"][0]["redactions"])

    def test_multiline_pem_private_key_is_redacted_as_a_complete_block(self) -> None:
        self.configure(("pem output", self.phase("emit_pem")))
        directory = self.root / "pem receipt"
        result = self.run_verify("--record", directory.name)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        receipt = self.read_receipt(directory)
        serialized = json.dumps(receipt, ensure_ascii=False)
        sidecars = "".join(
            self.artifact(directory, path).read_text(encoding="utf-8")
            for phase in receipt["phases"]
            for path in phase["output_paths"].values()
        )
        exposed = result.stdout + result.stderr + serialized + sidecars
        self.assertNotIn("c3VwZXItc2VjcmV0LWtleS1ib2R5", exposed)
        self.assertNotIn("YW5vdGhlci1zZWNyZXQtbGluZQ==", exposed)
        self.assertNotIn("END RSA PRIVATE KEY", exposed)
        self.assertIn("[REDACTED]", exposed)
        self.assertIn("PEM private key", receipt["phases"][0]["redactions"])

    def test_mismatched_pem_end_marker_does_not_end_redaction(self) -> None:
        self.configure(("mismatched pem output", self.phase("emit_mismatched_pem")))
        directory = self.root / "mismatched pem receipt"
        result = self.run_verify("--record", directory.name)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        receipt = self.read_receipt(directory)
        serialized = json.dumps(receipt, ensure_ascii=False)
        sidecars = "".join(
            self.artifact(directory, path).read_text(encoding="utf-8")
            for phase in receipt["phases"]
            for path in phase["output_paths"].values()
        )
        exposed = result.stdout + result.stderr + serialized + sidecars
        self.assertNotIn("cHJpdmF0ZS1ibG9jay1wcmVmaXg=", exposed)
        self.assertNotIn("bXVzdC1yZW1haW4taGlkZGVu", exposed)
        self.assertNotIn("END EC PRIVATE KEY", exposed)
        self.assertNotIn("END RSA PRIVATE KEY", exposed)
        self.assertIn("[REDACTED]", exposed)

    def test_prefixed_pem_end_markers_do_not_end_redaction(self) -> None:
        self.configure(("prefixed pem ends", self.phase("emit_prefixed_pem_end")))
        directory = self.root / "prefixed pem receipt"
        result = self.run_verify("--record", directory.name)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        receipt = self.read_receipt(directory)
        serialized = json.dumps(receipt, ensure_ascii=False)
        sidecars = "".join(
            self.artifact(directory, path).read_text(encoding="utf-8")
            for phase in receipt["phases"]
            for path in phase["output_paths"].values()
        )
        exposed = result.stdout + result.stderr + serialized + sidecars
        for hidden in (
            "Zmlyc3QtaGlkZGVuLWJvZHk=",
            "c2Vjb25kLWhpZGRlbi1ib2R5",
            "ZGFzaGVkLWRlY29yYXRlZC1oaWRkZW4=",
            "dGhpcmQtaGlkZGVuLWJvZHk=",
            "Zm91cnRoLWhpZGRlbi1ib2R5",
            "ZmlmdGgtaGlkZGVuLWJvZHk=",
            "END RSA PRIVATE KEYCHAIN",
            "XEND RSA PRIVATE KEYX",
            "END RSA PRIVATE KEY EXTRA",
            "END RSA PRIVATE KEY: EXTRA",
        ):
            self.assertNotIn(hidden, exposed)
        self.assertIn("[REDACTED]", exposed)


if __name__ == "__main__":
    unittest.main()
