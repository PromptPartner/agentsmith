#!/usr/bin/env python3
"""Behavioral tests for the staged stable-release updater."""

from __future__ import annotations

import json
import io
import hashlib
import hmac
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stderr, redirect_stdout


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "agentsmith.py"
sys.path.insert(0, str(ROOT))
import agentsmith as runtime  # noqa: E402


def integrity(payload: dict[str, object], key: bytes) -> str:
    unsigned = {key: value for key, value in payload.items() if key != "integrity"}
    canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "hmac-sha256:" + hmac.new(key, canonical, hashlib.sha256).hexdigest()


class UpdateCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="agentsmith update ü ")
        self.root = Path(self.temporary.name)
        self.seed = self.root / "seed"
        self.remote = self.root / "remote.git"
        self.seed.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Updater Test")
        self.git("config", "user.email", "user@example.com")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def git(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["git", "-C", str(self.seed), *arguments],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def commit_and_tag(
        self,
        version: str,
        *,
        broken_doctor: bool = False,
        broken_runtime_health: bool = False,
        candidate_execution_probe: Path | None = None,
        statusline_probe: str | None = None,
    ) -> None:
        for directory in ("config", "core", "profiles", "scripts", "skills", "templates"):
            destination = self.seed / directory
            if not destination.exists():
                shutil.copytree(ROOT / directory, destination)
        for helper in ("native_launcher.py", "evaluate.py"):
            shutil.copy2(ROOT / helper, self.seed / helper)
        (self.seed / "VERSION").write_text(version + "\n", encoding="utf-8")
        runtime = CORE.read_text(encoding="utf-8")
        runtime = re.sub(r'^VERSION = "[^"]+"$', f'VERSION = "{version}"', runtime, count=1, flags=re.MULTILINE)
        if broken_doctor:
            runtime = runtime.replace(
                '\nif __name__ == "__main__":',
                '\ndef cmd_doctor(args: object) -> int:\n    return 9\n\nif __name__ == "__main__":',
                1,
            )
        if broken_runtime_health:
            runtime = runtime.replace(
                '\nif __name__ == "__main__":',
                '\ndef copy_runtime(target: Path, *, dry_run: bool) -> Path:\n'
                '    return target / ".agentsmith" / "agentsmith.py"\n\n'
                'if __name__ == "__main__":',
                1,
            )
        if candidate_execution_probe is not None:
            runtime = runtime.replace(
                '\nif __name__ == "__main__":',
                f'\nPath({json.dumps(str(candidate_execution_probe))}).write_text("candidate executed", encoding="utf-8")\n\n'
                'if __name__ == "__main__":',
                1,
            )
        (self.seed / "agentsmith.py").write_text(runtime, encoding="utf-8")
        if statusline_probe is not None:
            statusline = self.seed / "config" / "statusline.py"
            statusline.write_text(
                statusline.read_text(encoding="utf-8") + f"\n# {statusline_probe}\n",
                encoding="utf-8",
            )
        identity = (ROOT / "core" / "00-identity.md").read_text(encoding="utf-8")
        identity += f"\nRELEASE_PROBE_{version.replace('.', '_').replace('-', '_')}\n"
        (self.seed / "core" / "00-identity.md").write_text(identity, encoding="utf-8")
        skill = (ROOT / "skills" / "handoff" / "SKILL.md").read_text(encoding="utf-8")
        skill += f"\nRELEASE_SKILL_PROBE_{version.replace('.', '_').replace('-', '_')}\n"
        (self.seed / "skills" / "handoff" / "SKILL.md").write_text(skill, encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", f"release {version}")
        self.git("tag", f"v{version}")

    def run_core(self, *arguments: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CORE), *arguments],
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

    def test_check_selects_highest_stable_semver_and_excludes_prereleases(self) -> None:
        for version in ("0.2.0", "0.3.0-rc.1", "0.2.7", "1.0.0-beta.2"):
            self.commit_and_tag(version)
        self.git("tag", "not-a-release")
        cloned = subprocess.run(
            ["git", "clone", "-q", "--bare", str(self.seed), str(self.remote)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(cloned.returncode, 0, cloned.stdout + cloned.stderr)

        result = self.run_core("update", "check", "--from", str(self.remote), "--json")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["current_version"], "0.2.0")
        self.assertEqual(payload["latest_version"], "0.2.7")
        self.assertEqual(payload["tag"], "v0.2.7")
        self.assertTrue(payload["update_available"])
        self.assertEqual(payload["remote"], str(self.remote))

    def test_fresh_install_records_versioned_update_manifest_without_project_path(self) -> None:
        target = self.root / "project"
        target.mkdir()
        isolated_home = self.root / "home"
        environment = {
            **os.environ,
            "HOME": str(isolated_home),
            "CODEX_HOME": str(self.root / "codex-home"),
        }

        result = self.run_core(
            "install",
            "--agent", "codex",
            "--profile", "software-dev",
            "--target", str(target),
            "--operator-name", "Update Test",
            "--tracker", "Linear",
            "--tracker-writes", "ask",
            "--safety", "trusted",
            "--with-skills",
            "--with-mcp", "context7",
            "--with-handoff-hooks",
            env=environment,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        state = json.loads((target / ".agentsmith" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["schema_version"], 1)
        installation = state["installation"]
        self.assertEqual(installation["installed_version"], "0.2.0")
        self.assertEqual(installation["scope"], "project")
        self.assertEqual(installation["agents"], ["codex"])
        self.assertEqual(installation["profiles"], ["software-dev"])
        self.assertTrue(installation["include_core"])
        self.assertFalse(installation["assemble_only"])
        self.assertEqual(installation["safety"], {"codex": "trusted"})
        self.assertEqual(installation["tracker"], {"name": "Linear", "writes": "ask"})
        self.assertEqual(
            installation["capabilities"],
            {"handoff_hooks": True, "hooks": False, "mcp": ["context7"], "skills": True, "ui_design_hook": False},
        )
        self.assertNotIn(str(target), json.dumps(state))

    def test_saved_plan_verifies_release_and_is_installation_write_free(self) -> None:
        self.commit_and_tag("0.2.0")
        self.commit_and_tag("0.2.1")
        cloned = subprocess.run(
            ["git", "clone", "-q", "--bare", str(self.seed), str(self.remote)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(cloned.returncode, 0, cloned.stdout + cloned.stderr)
        target = self.root / "planned project"
        target.mkdir()
        environment = {
            **os.environ,
            "HOME": str(self.root / "home"),
            "CODEX_HOME": str(self.root / "codex-home"),
        }
        installed = self.run_core(
            "install", "--agent", "codex", "--profile", "software-dev",
            "--target", str(target), "--operator-name", "Plan Test",
            env=environment,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        before = {
            path.relative_to(target): path.read_bytes()
            for path in target.rglob("*")
            if path.is_file()
        }
        plan_path = self.root / "plans" / "update.json"

        result = self.run_core(
            "update", "plan", "--target", str(target), "--version", "v0.2.1",
            "--from", str(self.remote), "--save", str(plan_path),
            env=environment,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        after = {
            path.relative_to(target): path.read_bytes()
            for path in target.rglob("*")
            if path.is_file()
        }
        self.assertEqual(after, before)
        second_plan_path = self.root / "second-apply-plan.json"
        second_plan = self.run_core(
            "update", "plan", "--target", str(target), "--version", "v0.2.1",
            "--from", str(self.remote), "--save", str(second_plan_path), env=environment,
        )
        self.assertEqual(second_plan.returncode, 0, second_plan.stdout + second_plan.stderr)
        second_fingerprints = {
            item["path"] for item in json.loads(second_plan_path.read_text(encoding="utf-8"))["fingerprints"]
        }
        self.assertNotIn(".agentsmith/update-integrity.key", second_fingerprints)
        self.assertFalse(any("update-receipts" in path or "update-backups" in path for path in second_fingerprints))
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertEqual(plan["schema_version"], 1)
        self.assertEqual(plan["scope"], "project")
        self.assertEqual(plan["target"], str(target.resolve()))
        self.assertEqual(plan["release"]["tag"], "v0.2.1")
        self.assertEqual(plan["release"]["version"], "0.2.1")
        self.assertEqual(plan["release"]["commit"], self.git("rev-list", "-n", "1", "v0.2.1").stdout.strip())
        fingerprints = {item["path"]: item["sha256"] for item in plan["fingerprints"]}
        self.assertIn("AGENTS.md", fingerprints)
        self.assertIn(".agentsmith/agentsmith.py", fingerprints)
        self.assertIn("doctor --strict", " ".join(plan["verification"]))
        self.assertTrue(plan["integrity"].startswith("hmac-sha256:"))
        self.assertTrue(plan["proposed_changes"])
        self.assertTrue(all(set(item) == {
            "root", "path", "operation", "before_sha256", "before_mode", "after_sha256", "after_mode"
        } for item in plan["proposed_changes"]))
        runtime_change = next(item for item in plan["proposed_changes"] if item["path"] == ".agentsmith/agentsmith.py")
        self.assertEqual(runtime_change["operation"], "replace")
        self.assertEqual(runtime_change["before_sha256"], fingerprints[".agentsmith/agentsmith.py"])
        self.assertRegex(runtime_change["after_sha256"], r"^[0-9a-f]{64}$")

    def test_planning_treats_candidate_release_code_as_data(self) -> None:
        execution_probe = self.root / "candidate-executed-outside-shadow"
        self.commit_and_tag("0.2.0")
        self.commit_and_tag("0.2.1", candidate_execution_probe=execution_probe)
        cloned = subprocess.run(
            ["git", "clone", "-q", "--bare", str(self.seed), str(self.remote)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(cloned.returncode, 0, cloned.stdout + cloned.stderr)
        target = self.root / "data-only planning project"
        target.mkdir()
        environment = {
            **os.environ,
            "HOME": str(self.root / "data-only-home"),
            "CODEX_HOME": str(self.root / "data-only-codex"),
        }
        installed = self.run_core(
            "install", "--agent", "codex", "--profile", "software-dev", "--target", str(target),
            env=environment,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)

        planned = self.run_core(
            "update", "plan", "--target", str(target), "--version", "v0.2.1",
            "--from", str(self.remote), "--save", str(self.root / "data-only-plan.json"), env=environment,
        )

        self.assertEqual(planned.returncode, 0, planned.stdout + planned.stderr)
        self.assertFalse(execution_probe.exists())

    def test_apply_and_rollback_preserve_foreign_content_and_restore_exact_bytes(self) -> None:
        self.commit_and_tag("0.2.0")
        self.commit_and_tag("0.2.1")
        cloned = subprocess.run(
            ["git", "clone", "-q", "--bare", str(self.seed), str(self.remote)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(cloned.returncode, 0, cloned.stdout + cloned.stderr)
        target = self.root / "rollback project"
        target.mkdir()
        environment = {
            **os.environ,
            "HOME": str(self.root / "home"),
            "CODEX_HOME": str(self.root / "codex-home"),
        }
        installed = self.run_core(
            "install", "--agent", "codex", "--profile", "software-dev",
            "--target", str(target), "--operator-name", "Rollback Test",
            env=environment,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        agents_path = target / "AGENTS.md"
        agents_path.write_text("# Foreign heading\n\n" + agents_path.read_text(encoding="utf-8"), encoding="utf-8")
        research = target / "docs" / "research" / "source.md"
        research.parent.mkdir(parents=True, exist_ok=True)
        research.write_bytes(b"costly source material\n")
        plan_path = self.root / "apply-plan.json"
        planned = self.run_core(
            "update", "plan", "--target", str(target), "--version", "v0.2.1",
            "--from", str(self.remote), "--save", str(plan_path), env=environment,
        )
        self.assertEqual(planned.returncode, 0, planned.stdout + planned.stderr)
        before = {
            path.relative_to(target): path.read_bytes()
            for path in target.rglob("*")
            if path.is_file()
        }

        applied = self.run_core("update", "apply", "--plan", str(plan_path), env=environment)

        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        updated_agents = agents_path.read_text(encoding="utf-8")
        self.assertIn("# Foreign heading", updated_agents)
        self.assertIn("RELEASE_PROBE_0_2_1", updated_agents)
        self.assertEqual(research.read_bytes(), b"costly source material\n")
        updated_runtime = (target / ".agentsmith" / "agentsmith.py").read_text(encoding="utf-8")
        self.assertIn('VERSION = "0.2.1"', updated_runtime)
        receipt_line = next(line for line in applied.stdout.splitlines() if "rollback receipt:" in line)
        receipt_path = Path(receipt_line.split("rollback receipt:", 1)[1].strip())
        self.assertFalse(receipt_path.is_relative_to(target))
        self.assertTrue(receipt_path.is_file())
        if os.name != "nt":
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            agents_change = next(item for item in receipt["changes"] if item["path"] == "AGENTS.md")
            agents_path.chmod(agents_change["after_mode"] ^ 0o100)
            refused_mode_change = self.run_core(
                "update", "rollback", "--receipt", str(receipt_path), env=environment,
            )
            self.assertNotEqual(refused_mode_change.returncode, 0)
            self.assertIn("changed after update", refused_mode_change.stderr)
            agents_path.chmod(agents_change["after_mode"])

        rolled_back = self.run_core("update", "rollback", "--receipt", str(receipt_path), env=environment)

        self.assertEqual(rolled_back.returncode, 0, rolled_back.stdout + rolled_back.stderr)
        after = {
            path.relative_to(target): path.read_bytes()
            for path in target.rglob("*")
            if path.is_file()
        }
        self.assertEqual(after, before)
        later_plan_path = self.root / "plan-after-receipt.json"
        later_plan = self.run_core(
            "update", "plan", "--target", str(target), "--version", "v0.2.1",
            "--from", str(self.remote), "--save", str(later_plan_path), env=environment,
        )
        self.assertEqual(later_plan.returncode, 0, later_plan.stdout + later_plan.stderr)
        later_fingerprints = {
            item["path"] for item in json.loads(later_plan_path.read_text(encoding="utf-8"))["fingerprints"]
        }
        self.assertFalse(any("update-receipts" in path or "update-backups" in path for path in later_fingerprints))

    def test_rollback_preflights_all_backups_and_duplicate_paths_before_writing(self) -> None:
        self.commit_and_tag("0.2.0")
        self.commit_and_tag("0.2.1")
        cloned = subprocess.run(
            ["git", "clone", "-q", "--bare", str(self.seed), str(self.remote)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(cloned.returncode, 0, cloned.stdout + cloned.stderr)

        def change_snapshot(receipt: dict[str, object]) -> dict[Path, tuple[bytes, int]]:
            roots = receipt["roots"]
            assert isinstance(roots, dict)
            changes = receipt["changes"]
            assert isinstance(changes, list)
            return {
                path: (path.read_bytes(), path.stat().st_mode & 0o777)
                for change in changes
                if isinstance(change, dict)
                for path in [Path(str(roots[change["root"]])) / str(change["path"])]
                if path.is_file()
            }

        for failure in ("missing", "corrupt", "duplicate"):
            with self.subTest(failure=failure):
                target = self.root / f"rollback-preflight-{failure}-project"
                target.mkdir()
                home = self.root / f"rollback-preflight-{failure}-home"
                environment = {
                    **os.environ,
                    "HOME": str(home),
                    "CODEX_HOME": str(self.root / f"rollback-preflight-{failure}-codex"),
                }
                installed = self.run_core(
                    "install", "--agent", "codex", "--profile", "software-dev", "--target", str(target),
                    env=environment,
                )
                self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
                plan_path = self.root / f"rollback-preflight-{failure}-plan.json"
                planned = self.run_core(
                    "update", "plan", "--target", str(target), "--version", "v0.2.1",
                    "--from", str(self.remote), "--save", str(plan_path), env=environment,
                )
                self.assertEqual(planned.returncode, 0, planned.stdout + planned.stderr)
                applied = self.run_core("update", "apply", "--plan", str(plan_path), env=environment)
                self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
                receipt_line = next(line for line in applied.stdout.splitlines() if "rollback receipt:" in line)
                receipt_path = Path(receipt_line.split("rollback receipt:", 1)[1].strip())
                original_receipt = receipt_path.read_bytes()
                receipt = json.loads(original_receipt)
                updated = change_snapshot(receipt)
                self.assertGreater(len(updated), 1)

                if failure == "duplicate":
                    receipt["changes"].append(dict(receipt["changes"][0]))
                    key = (home / ".agentsmith" / "update-integrity.key").read_bytes()
                    receipt["integrity"] = integrity(receipt, key)
                    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
                else:
                    candidate = next(
                        change for change in receipt["changes"][:-1] if change["existed"]
                    )
                    backup_path = Path(receipt["backup_root"]) / candidate["root"] / candidate["path"]
                    original_backup = backup_path.read_bytes()
                    held_backup = backup_path.with_name(backup_path.name + ".held")
                    if failure == "missing":
                        backup_path.rename(held_backup)
                    else:
                        backup_path.write_bytes(b"corrupt rollback backup")

                refused = self.run_core(
                    "update", "rollback", "--receipt", str(receipt_path), env=environment,
                )

                self.assertNotEqual(refused.returncode, 0)
                expected_error = "duplicate" if failure == "duplicate" else "backup"
                self.assertIn(expected_error, refused.stderr.lower())
                self.assertEqual(change_snapshot(json.loads(original_receipt)), updated)

                if failure == "duplicate":
                    receipt_path.write_bytes(original_receipt)
                elif failure == "missing":
                    held_backup.rename(backup_path)
                else:
                    backup_path.write_bytes(original_backup)
                rolled_back = self.run_core(
                    "update", "rollback", "--receipt", str(receipt_path), env=environment,
                )
                self.assertEqual(rolled_back.returncode, 0, rolled_back.stdout + rolled_back.stderr)

    def test_configure_requires_explicit_weekly_opt_in_and_can_turn_it_off(self) -> None:
        environment = {
            **os.environ,
            "HOME": str(self.root / "home"),
            "CODEX_HOME": str(self.root / "codex-home"),
        }

        enabled = self.run_core("update", "configure", "--auto-check", "weekly", env=environment)

        self.assertEqual(enabled.returncode, 0, enabled.stdout + enabled.stderr)
        state_path = Path(environment["HOME"]) / ".agentsmith" / "state.json"
        enabled_state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(enabled_state["update_policy"], {"auto_check": "weekly"})

        disabled = self.run_core("update", "configure", "--auto-check", "off", env=environment)

        self.assertEqual(disabled.returncode, 0, disabled.stdout + disabled.stderr)
        disabled_state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(disabled_state["update_policy"], {"auto_check": "off"})

    def test_global_mcp_is_rejected_before_any_installation_write(self) -> None:
        environment = {
            **os.environ,
            "HOME": str(self.root / "global-mcp-home"),
            "CODEX_HOME": str(self.root / "global-mcp-codex"),
        }

        result = self.run_core(
            "install", "--agent", "codex", "--global", "--with-mcp", "context7", env=environment,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("project-scoped", result.stderr)
        self.assertFalse(Path(environment["HOME"]).exists())
        self.assertFalse(Path(environment["CODEX_HOME"]).exists())

    def test_offline_check_fails_without_creating_installation_state(self) -> None:
        environment = {
            **os.environ,
            "HOME": str(self.root / "offline-home"),
            "CODEX_HOME": str(self.root / "offline-codex"),
        }

        result = self.run_core(
            "update", "check", "--from", str(self.root / "missing-remote.git"), "--json",
            env=environment,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no installation changes were made", result.stderr)
        self.assertFalse((Path(environment["HOME"]) / ".agentsmith").exists())

    def test_plan_fails_closed_on_malformed_existing_state_before_remote_access(self) -> None:
        target = self.root / "malformed-state-project"
        state_path = target / ".agentsmith" / "state.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text("{not json\n", encoding="utf-8")
        environment = {
            **os.environ,
            "HOME": str(self.root / "malformed-home"),
            "CODEX_HOME": str(self.root / "malformed-codex"),
        }

        result = self.run_core(
            "update", "plan", "--target", str(target), "--from", str(self.root / "must-not-be-read.git"),
            env=environment,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("malformed update state", result.stderr)
        self.assertEqual(state_path.read_text(encoding="utf-8"), "{not json\n")

    def test_apply_rejects_unknown_plan_fields_and_post_plan_fingerprint_drift(self) -> None:
        self.commit_and_tag("0.2.0")
        self.commit_and_tag("0.2.1")
        cloned = subprocess.run(
            ["git", "clone", "-q", "--bare", str(self.seed), str(self.remote)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(cloned.returncode, 0, cloned.stdout + cloned.stderr)
        target = self.root / "drift project"
        target.mkdir()
        environment = {
            **os.environ,
            "HOME": str(self.root / "drift-home"),
            "CODEX_HOME": str(self.root / "drift-codex"),
        }
        installed = self.run_core(
            "install", "--agent", "codex", "--profile", "software-dev", "--target", str(target),
            env=environment,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        plan_path = self.root / "guarded-plan.json"
        planned = self.run_core(
            "update", "plan", "--target", str(target), "--version", "v0.2.1",
            "--from", str(self.remote), "--save", str(plan_path), env=environment,
        )
        self.assertEqual(planned.returncode, 0, planned.stdout + planned.stderr)
        original = plan_path.read_bytes()
        tampered = json.loads(original)
        tampered["unexpected_command"] = ["do", "not", "run"]
        plan_path.write_text(json.dumps(tampered, indent=2) + "\n", encoding="utf-8")

        rejected = self.run_core("update", "apply", "--plan", str(plan_path), env=environment)

        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("integrity check failed", rejected.stderr)
        tampered["integrity"] = integrity(
            tampered, (Path(environment["HOME"]) / ".agentsmith" / "update-integrity.key").read_bytes()
        )
        plan_path.write_text(json.dumps(tampered, indent=2) + "\n", encoding="utf-8")
        rejected = self.run_core("update", "apply", "--plan", str(plan_path), env=environment)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("not supported", rejected.stderr)
        mismatched = json.loads(original)
        mismatched["proposed_changes"][0]["after_sha256"] = "0" * 64
        mismatched["integrity"] = integrity(
            mismatched, (Path(environment["HOME"]) / ".agentsmith" / "update-integrity.key").read_bytes()
        )
        plan_path.write_text(json.dumps(mismatched, indent=2) + "\n", encoding="utf-8")
        mismatch_rejected = self.run_core("update", "apply", "--plan", str(plan_path), env=environment)
        self.assertNotEqual(mismatch_rejected.returncode, 0)
        self.assertIn("do not match the authenticated plan", mismatch_rejected.stderr)
        plan_path.write_bytes(original)
        agents = target / "AGENTS.md"
        agents.write_text(agents.read_text(encoding="utf-8") + "\npost-plan operator edit\n", encoding="utf-8")
        drifted = self.run_core("update", "apply", "--plan", str(plan_path), env=environment)
        self.assertNotEqual(drifted.returncode, 0)
        self.assertIn("changed after planning", drifted.stderr)
        self.assertNotIn('VERSION = "0.2.1"', (target / ".agentsmith" / "agentsmith.py").read_text(encoding="utf-8"))

    def test_plan_reconstructs_provable_pre_manifest_state_without_migration_write(self) -> None:
        self.commit_and_tag("0.2.0")
        self.commit_and_tag("0.2.1")
        cloned = subprocess.run(
            ["git", "clone", "-q", "--bare", str(self.seed), str(self.remote)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(cloned.returncode, 0, cloned.stdout + cloned.stderr)
        target = self.root / "legacy project"
        target.mkdir()
        environment = {
            **os.environ,
            "HOME": str(self.root / "legacy-home"),
            "CODEX_HOME": str(self.root / "legacy-codex"),
        }
        installed = self.run_core(
            "install", "--agent", "codex", "--profile", "software-dev", "--target", str(target),
            "--operator-name", "Legacy Operator", "--safety", "trusted", env=environment,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        legacy_state_path = target / ".agentsmith" / "state.json"
        legacy_state_path.write_text("{}\n", encoding="utf-8")
        before = legacy_state_path.read_bytes()
        plan_path = self.root / "legacy-plan.json"

        planned = self.run_core(
            "update", "plan", "--target", str(target), "--version", "v0.2.1",
            "--from", str(self.remote), "--save", str(plan_path), env=environment,
        )

        self.assertEqual(planned.returncode, 0, planned.stdout + planned.stderr)
        self.assertEqual(legacy_state_path.read_bytes(), before)
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertTrue(plan["migration_warnings"])
        self.assertEqual(plan["installation"]["agents"], ["codex"])
        self.assertEqual(plan["installation"]["profiles"], ["software-dev"])
        self.assertFalse(plan["installation"]["assemble_only"])
        self.assertEqual(plan["installation"]["safety"], {"codex": "trusted"})
        self.assertEqual(plan["installation"]["operator"]["name"], "Legacy Operator")

    def test_assemble_only_is_preserved_for_project_and_global_updates(self) -> None:
        self.commit_and_tag("0.2.0")
        self.commit_and_tag("0.2.1")
        cloned = subprocess.run(
            ["git", "clone", "-q", "--bare", str(self.seed), str(self.remote)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(cloned.returncode, 0, cloned.stdout + cloned.stderr)
        for scope in ("project", "global"):
            with self.subTest(scope=scope):
                target = self.root / f"assemble-only-{scope}-project"
                target.mkdir()
                home = self.root / f"assemble-only-{scope}-home"
                codex_home = self.root / f"assemble-only-{scope}-codex"
                environment = {**os.environ, "HOME": str(home), "CODEX_HOME": str(codex_home)}
                scope_arguments = ["--global"] if scope == "global" else ["--target", str(target)]
                installed = self.run_core(
                    "install", "--agent", "claude,codex", "--profile", "software-dev",
                    "--assemble-only", *scope_arguments, env=environment,
                )
                self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
                state_root = home if scope == "global" else target
                state_path = state_root / ".agentsmith" / "state.json"
                state = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertTrue(state["installation"]["assemble_only"])
                self.assertEqual(state["installation"]["safety"], {})
                home_state_path = home / ".agentsmith" / "state.json"
                home_state = json.loads(home_state_path.read_text(encoding="utf-8")) if home_state_path.exists() else {}
                self.assertNotIn("native_safety", home_state)
                native_paths = [
                    home / ".claude" / "settings.json",
                    home / ".claude" / "agentsmith-statusline.py",
                    codex_home / "config.toml",
                ]
                self.assertTrue(all(not path.exists() for path in native_paths))
                plan_path = self.root / f"assemble-only-{scope}-plan.json"

                planned = self.run_core(
                    "update", "plan", *scope_arguments, "--version", "v0.2.1",
                    "--from", str(self.remote), "--save", str(plan_path), env=environment,
                )

                self.assertEqual(planned.returncode, 0, planned.stdout + planned.stderr)
                plan = json.loads(plan_path.read_text(encoding="utf-8"))
                self.assertTrue(plan["installation"]["assemble_only"])
                self.assertFalse(any(
                    item["path"] in {".claude/settings.json", ".claude/agentsmith-statusline.py", "config.toml"}
                    for item in plan["proposed_changes"]
                ))
                applied = self.run_core("update", "apply", "--plan", str(plan_path), env=environment)
                self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
                self.assertTrue(all(not path.exists() for path in native_paths))
                updated = json.loads(state_path.read_text(encoding="utf-8"))["installation"]
                self.assertTrue(updated["assemble_only"])
                self.assertEqual(updated["safety"], {})

    def test_assemble_only_migration_requires_unambiguous_native_ownership(self) -> None:
        self.commit_and_tag("0.2.1")
        cloned = subprocess.run(
            ["git", "clone", "-q", "--bare", str(self.seed), str(self.remote)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(cloned.returncode, 0, cloned.stdout + cloned.stderr)
        project = self.root / "legacy-assemble-only-project"
        project.mkdir()
        project_home = self.root / "legacy-assemble-only-home"
        project_environment = {
            **os.environ,
            "HOME": str(project_home),
            "CODEX_HOME": str(self.root / "legacy-assemble-only-codex"),
        }
        installed = self.run_core(
            "install", "--agent", "claude", "--profile", "software-dev", "--assemble-only",
            "--target", str(project), env=project_environment,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        (project / ".agentsmith" / "state.json").write_text("{}\n", encoding="utf-8")
        plan_path = self.root / "legacy-assemble-only-plan.json"

        planned = self.run_core(
            "update", "plan", "--target", str(project), "--version", "v0.2.1",
            "--from", str(self.remote), "--save", str(plan_path), env=project_environment,
        )

        self.assertEqual(planned.returncode, 0, planned.stdout + planned.stderr)
        self.assertTrue(json.loads(plan_path.read_text(encoding="utf-8"))["installation"]["assemble_only"])

        global_home = self.root / "legacy-mixed-home"
        global_codex = self.root / "legacy-mixed-codex"
        global_environment = {**os.environ, "HOME": str(global_home), "CODEX_HOME": str(global_codex)}
        global_installed = self.run_core(
            "install", "--agent", "claude,codex", "--global", "--profile", "software-dev",
            env=global_environment,
        )
        self.assertEqual(global_installed.returncode, 0, global_installed.stdout + global_installed.stderr)
        global_state_path = global_home / ".agentsmith" / "state.json"
        global_state = json.loads(global_state_path.read_text(encoding="utf-8"))
        global_state.pop("installation")
        global_state.pop("schema_version")
        global_state["native_safety"].pop("codex")
        global_state_path.write_text(json.dumps(global_state) + "\n", encoding="utf-8")

        mixed = self.run_core(
            "update", "plan", "--global", "--version", "v0.2.1", "--from", str(self.remote),
            env=global_environment,
        )

        self.assertNotEqual(mixed.returncode, 0)
        self.assertIn("assemble-only", mixed.stderr)

        global_state["native_safety"] = {"claude": None, "codex": None}
        global_state_path.write_text(json.dumps(global_state) + "\n", encoding="utf-8")
        invalid = self.run_core(
            "update", "plan", "--global", "--version", "v0.2.1", "--from", str(self.remote),
            env=global_environment,
        )
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("assemble-only", invalid.stderr)

    def test_schema_one_manifest_without_assemble_only_requires_reinstall(self) -> None:
        target = self.root / "old-schema-one"
        target.mkdir()
        environment = {
            **os.environ,
            "HOME": str(self.root / "old-schema-home"),
            "CODEX_HOME": str(self.root / "old-schema-codex"),
        }
        installed = self.run_core(
            "install", "--agent", "codex", "--profile", "software-dev", "--target", str(target),
            env=environment,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        state_path = target / ".agentsmith" / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["installation"].pop("assemble_only", None)
        state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")

        planned = self.run_core(
            "update", "plan", "--target", str(target), "--from", str(self.root / "unused.git"),
            env=environment,
        )

        self.assertNotEqual(planned.returncode, 0)
        self.assertIn("--assemble-only", planned.stderr)
        self.assertIn("rerun install", planned.stderr)

        state["installation"]["assemble_only"] = "false"
        state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")
        malformed = self.run_core(
            "update", "plan", "--target", str(target), "--from", str(self.root / "unused.git"),
            env=environment,
        )
        self.assertNotEqual(malformed.returncode, 0)
        self.assertIn("must be true or false", malformed.stderr)

    def test_global_update_is_scoped_and_rolls_back_managed_home_files(self) -> None:
        self.commit_and_tag("0.2.0")
        self.commit_and_tag("0.2.1")
        cloned = subprocess.run(
            ["git", "clone", "-q", "--bare", str(self.seed), str(self.remote)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(cloned.returncode, 0, cloned.stdout + cloned.stderr)
        home = self.root / "global-home"
        codex_home = self.root / "global-codex"
        environment = {**os.environ, "HOME": str(home), "CODEX_HOME": str(codex_home)}
        installed = self.run_core(
            "install", "--agent", "codex", "--global", "--profile", "software-dev",
            "--operator-name", "Global Operator", "--with-handoff-hooks", env=environment,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        managed_paths = [
            home / ".agentsmith" / "state.json",
            home / ".agentsmith" / "agentsmith.py",
            codex_home / "AGENTS.md",
            codex_home / "config.toml",
            codex_home / "hooks.json",
        ]
        before = {path: path.read_bytes() for path in managed_paths}
        plan_path = self.root / "global-plan.json"
        planned = self.run_core(
            "update", "plan", "--global", "--version", "v0.2.1", "--from", str(self.remote),
            "--save", str(plan_path), env=environment,
        )
        self.assertEqual(planned.returncode, 0, planned.stdout + planned.stderr)

        applied = self.run_core("update", "apply", "--plan", str(plan_path), env=environment)

        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertIn("RELEASE_PROBE_0_2_1", (codex_home / "AGENTS.md").read_text(encoding="utf-8"))
        hooks = json.loads((codex_home / "hooks.json").read_text(encoding="utf-8"))
        commands = [
            hook["command"]
            for entry in hooks["hooks"]["UserPromptSubmit"]
            for hook in entry["hooks"]
        ]
        self.assertTrue(any(str(home.resolve() / ".agentsmith" / "agentsmith.py") in command for command in commands))
        self.assertFalse(any("agentsmith-apply-" in command for command in commands))
        receipt_line = next(line for line in applied.stdout.splitlines() if "rollback receipt:" in line)
        receipt_path = Path(receipt_line.split("rollback receipt:", 1)[1].strip())
        rolled_back = self.run_core("update", "rollback", "--receipt", str(receipt_path), env=environment)
        self.assertEqual(rolled_back.returncode, 0, rolled_back.stdout + rolled_back.stderr)
        self.assertEqual({path: path.read_bytes() for path in managed_paths}, before)

    def test_update_refreshes_owned_skills_but_preserves_customized_skill(self) -> None:
        self.commit_and_tag("0.2.0")
        self.commit_and_tag("0.2.1")
        cloned = subprocess.run(
            ["git", "clone", "-q", "--bare", str(self.seed), str(self.remote)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(cloned.returncode, 0, cloned.stdout + cloned.stderr)
        target = self.root / "skills project"
        target.mkdir()
        environment = {
            **os.environ,
            "HOME": str(self.root / "skills-home"),
            "CODEX_HOME": str(self.root / "skills-codex"),
        }
        installed = self.run_core(
            "install", "--agent", "codex", "--profile", "software-dev", "--target", str(target),
            "--with-skills", env=environment,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        customized = target / ".agents" / "skills" / "example-skill" / "SKILL.md"
        state_path = target / ".agentsmith" / "state.json"
        original_inventory = json.loads(state_path.read_text(encoding="utf-8"))["installation"]["managed_files"]
        original_baseline = next(
            item["sha256"] for item in original_inventory
            if item["path"] == ".agents/skills/example-skill/SKILL.md"
        )
        customized.write_text(customized.read_text(encoding="utf-8") + "\nLOCAL CUSTOMIZATION\n", encoding="utf-8")
        rerun = self.run_core(
            "install", "--agent", "codex", "--profile", "software-dev", "--target", str(target),
            env=environment,
        )
        self.assertEqual(rerun.returncode, 0, rerun.stdout + rerun.stderr)
        rerun_inventory = json.loads(state_path.read_text(encoding="utf-8"))["installation"]["managed_files"]
        rerun_baseline = next(
            item["sha256"] for item in rerun_inventory
            if item["path"] == ".agents/skills/example-skill/SKILL.md"
        )
        self.assertEqual(rerun_baseline, original_baseline)
        self.assertNotEqual(rerun_baseline, hashlib.sha256(customized.read_bytes()).hexdigest())
        plan_path = self.root / "skills-plan.json"
        planned = self.run_core(
            "update", "plan", "--target", str(target), "--version", "v0.2.1",
            "--from", str(self.remote), "--save", str(plan_path), env=environment,
        )
        self.assertEqual(planned.returncode, 0, planned.stdout + planned.stderr)

        applied = self.run_core("update", "apply", "--plan", str(plan_path), env=environment)

        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        handoff = target / ".agents" / "skills" / "handoff" / "SKILL.md"
        self.assertIn("RELEASE_SKILL_PROBE_0_2_1", handoff.read_text(encoding="utf-8"))
        self.assertIn("LOCAL CUSTOMIZATION", customized.read_text(encoding="utf-8"))

    def test_colliding_skills_remain_foreign_until_force_replaces_them(self) -> None:
        self.commit_and_tag("0.2.0")
        self.commit_and_tag("0.2.1")
        cloned = subprocess.run(
            ["git", "clone", "-q", "--bare", str(self.seed), str(self.remote)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(cloned.returncode, 0, cloned.stdout + cloned.stderr)
        target = self.root / "colliding-skills-project"
        target.mkdir()
        environment = {
            **os.environ,
            "HOME": str(self.root / "colliding-skills-home"),
            "CODEX_HOME": str(self.root / "colliding-skills-codex"),
        }
        collisions = [
            target / ".agents" / "skills" / "handoff" / "SKILL.md",
            target / ".claude" / "skills" / "handoff" / "SKILL.md",
        ]
        for index, path in enumerate(collisions):
            path.parent.mkdir(parents=True)
            if index == 0:
                path.write_bytes((ROOT / "skills" / "handoff" / "SKILL.md").read_bytes())
            else:
                path.write_text(f"FOREIGN COLLISION {index}\n", encoding="utf-8")
        before = {path: path.read_bytes() for path in collisions}

        installed = self.run_core(
            "install", "--agent", "claude", "--profile", "software-dev", "--target", str(target),
            "--with-skills", env=environment,
        )

        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        self.assertEqual({path: path.read_bytes() for path in collisions}, before)
        state_path = target / ".agentsmith" / "state.json"
        inventory_paths = {
            item["path"]
            for item in json.loads(state_path.read_text(encoding="utf-8"))["installation"]["managed_files"]
        }
        self.assertFalse(any(path.endswith("/handoff/SKILL.md") for path in inventory_paths))
        plan_path = self.root / "colliding-skills-plan.json"
        planned = self.run_core(
            "update", "plan", "--target", str(target), "--version", "v0.2.1",
            "--from", str(self.remote), "--save", str(plan_path), env=environment,
        )
        self.assertEqual(planned.returncode, 0, planned.stdout + planned.stderr)
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertFalse(any("/handoff/" in f"/{item['path']}/" for item in plan["proposed_changes"]))

        applied = self.run_core("update", "apply", "--plan", str(plan_path), env=environment)

        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertEqual({path: path.read_bytes() for path in collisions}, before)
        updated_inventory = {
            item["path"]
            for item in json.loads(state_path.read_text(encoding="utf-8"))["installation"]["managed_files"]
        }
        self.assertFalse(any(path.endswith("/handoff/SKILL.md") for path in updated_inventory))
        uninstalled = self.run_core(
            "install", "--agent", "claude", "--target", str(target), "--uninstall", env=environment,
        )
        self.assertEqual(uninstalled.returncode, 0, uninstalled.stdout + uninstalled.stderr)
        self.assertTrue(all(path.is_file() for path in collisions))
        self.assertEqual({path: path.read_bytes() for path in collisions}, before)

        force_target = self.root / "forced-colliding-skills-project"
        force_target.mkdir()
        forced_collisions = [
            force_target / ".agents" / "skills" / "handoff" / "SKILL.md",
            force_target / ".claude" / "skills" / "handoff" / "SKILL.md",
        ]
        for path in forced_collisions:
            path.parent.mkdir(parents=True)
            path.write_text("FOREIGN BEFORE FORCE\n", encoding="utf-8")
        forced = self.run_core(
            "install", "--agent", "claude", "--profile", "software-dev", "--target", str(force_target),
            "--with-skills", "--force", env=environment,
        )
        self.assertEqual(forced.returncode, 0, forced.stdout + forced.stderr)
        self.assertTrue(all(b"FOREIGN BEFORE FORCE" not in path.read_bytes() for path in forced_collisions))
        forced_inventory = {
            item["path"]
            for item in json.loads(
                (force_target / ".agentsmith" / "state.json").read_text(encoding="utf-8")
            )["installation"]["managed_files"]
        }
        self.assertTrue(all(
            path.relative_to(force_target).as_posix() in forced_inventory for path in forced_collisions
        ))

    def test_project_mcp_is_authenticated_updated_and_rolled_back_with_foreign_servers(self) -> None:
        self.commit_and_tag("0.2.0")
        self.commit_and_tag("0.2.1")
        cloned = subprocess.run(
            ["git", "clone", "-q", "--bare", str(self.seed), str(self.remote)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(cloned.returncode, 0, cloned.stdout + cloned.stderr)
        for agent_id in ("claude", "codex"):
            with self.subTest(agent=agent_id):
                target = self.root / f"{agent_id}-mcp-project"
                target.mkdir()
                environment = {
                    **os.environ,
                    "HOME": str(self.root / f"{agent_id}-mcp-home"),
                    "CODEX_HOME": str(self.root / f"{agent_id}-mcp-codex-home"),
                }
                installed = self.run_core(
                    "install", "--agent", agent_id, "--profile", "software-dev", "--target", str(target),
                    "--with-mcp", "context7", env=environment,
                )
                self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
                if agent_id == "claude":
                    mcp_path = target / ".mcp.json"
                    foreign = {
                        "mcpServers": {"foreign": {"command": "foreign", "args": ["--keep"]}},
                        "foreignTopLevel": {"keep": True},
                    }
                    mcp_path.write_text(json.dumps(foreign, indent=2) + "\n", encoding="utf-8")
                else:
                    mcp_path = target / ".codex" / "config.toml"
                    mcp_path.write_text(
                        'foreign_setting = "keep"\n\n[mcp_servers.foreign]\n'
                        'command = "foreign"\nargs = ["--keep"]\n',
                        encoding="utf-8",
                    )
                before = mcp_path.read_bytes()
                plan_path = self.root / f"{agent_id}-mcp-plan.json"

                planned = self.run_core(
                    "update", "plan", "--target", str(target), "--version", "v0.2.1",
                    "--from", str(self.remote), "--save", str(plan_path), env=environment,
                )

                self.assertEqual(planned.returncode, 0, planned.stdout + planned.stderr)
                plan = json.loads(plan_path.read_text(encoding="utf-8"))
                relative = ".mcp.json" if agent_id == "claude" else ".codex/config.toml"
                fingerprint = next(
                    item for item in plan["fingerprints"]
                    if item["root"] == "target" and item["path"] == relative
                )
                self.assertEqual(fingerprint["sha256"], hashlib.sha256(before).hexdigest())
                self.assertTrue(any(
                    item["root"] == "target" and item["path"] == relative
                    for item in plan["proposed_changes"]
                ))

                applied = self.run_core("update", "apply", "--plan", str(plan_path), env=environment)

                self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
                inspected = runtime.inspect_mcp(
                    agent_id,
                    {"skills_tools": {"mcp": {"client_support": "native"}}},
                    target,
                )
                self.assertEqual(inspected["managed_names"], ["context7"])
                self.assertEqual(inspected["foreign_names"], ["foreign"])
                if agent_id == "claude":
                    updated = json.loads(mcp_path.read_text(encoding="utf-8"))
                    self.assertEqual(updated["foreignTopLevel"], {"keep": True})
                    self.assertEqual(
                        updated["mcpServers"]["foreign"],
                        {"command": "foreign", "args": ["--keep"]},
                    )
                else:
                    import tomllib
                    updated = tomllib.loads(mcp_path.read_text(encoding="utf-8"))
                    self.assertEqual(updated["foreign_setting"], "keep")
                    self.assertEqual(
                        updated["mcp_servers"]["foreign"],
                        {"command": "foreign", "args": ["--keep"]},
                    )
                receipt_line = next(line for line in applied.stdout.splitlines() if "rollback receipt:" in line)
                receipt_path = Path(receipt_line.split("rollback receipt:", 1)[1].strip())
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                self.assertTrue(any(item["root"] == "target" and item["path"] == relative for item in receipt["changes"]))

                rolled_back = self.run_core(
                    "update", "rollback", "--receipt", str(receipt_path), env=environment,
                )

                self.assertEqual(rolled_back.returncode, 0, rolled_back.stdout + rolled_back.stderr)
                self.assertEqual(mcp_path.read_bytes(), before)

    def test_weekly_check_reports_only_and_offline_failure_does_not_block_command(self) -> None:
        home = self.root / "weekly-home"
        codex_home = self.root / "weekly-codex"
        environment = {"HOME": str(home), "CODEX_HOME": str(codex_home)}
        state_path = home / ".agentsmith" / "state.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text(json.dumps({"update_policy": {"auto_check": "weekly"}}) + "\n", encoding="utf-8")
        output = io.StringIO()
        errors = io.StringIO()
        with mock.patch.dict(os.environ, environment, clear=False), mock.patch.object(
            runtime, "stable_release_tags", return_value=[((0, 2, 1), "v0.2.1")]
        ) as checked, redirect_stdout(output), redirect_stderr(errors):
            result = runtime.run(["agents", "list"])
        self.assertEqual(result, 0)
        checked.assert_called_once_with(runtime.OFFICIAL_REMOTE, timeout_seconds=3)
        self.assertIn("update available: v0.2.1", output.getvalue())
        self.assertIn("claude", output.getvalue())

        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["update_policy"]["last_attempt_at"] = "2000-01-01T00:00:00+00:00"
        state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")
        with mock.patch.dict(os.environ, environment, clear=False), mock.patch.object(
            runtime, "stable_release_tags", side_effect=runtime.CliError("offline")
        ), redirect_stdout(io.StringIO()), redirect_stderr(errors):
            offline_result = runtime.run(["agents", "list"])
        self.assertEqual(offline_result, 0)
        self.assertIn("weekly update check skipped", errors.getvalue())

        state["update_policy"]["last_attempt_at"] = "2000-01-01T00:00:00+00:00"
        state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")
        write_errors = io.StringIO()
        with mock.patch.dict(os.environ, environment, clear=False), mock.patch.object(
            runtime, "record_state", side_effect=PermissionError("read-only home")
        ), redirect_stdout(io.StringIO()), redirect_stderr(write_errors):
            write_failure_result = runtime.run(["agents", "list"])
        self.assertEqual(write_failure_result, 0)
        self.assertIn("weekly update check skipped", write_errors.getvalue())

    def test_failed_post_apply_health_check_restores_pre_update_bytes_automatically(self) -> None:
        self.commit_and_tag("0.2.0")
        self.commit_and_tag("0.2.1", broken_doctor=True)
        cloned = subprocess.run(
            ["git", "clone", "-q", "--bare", str(self.seed), str(self.remote)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(cloned.returncode, 0, cloned.stdout + cloned.stderr)
        target = self.root / "failed apply project"
        target.mkdir()
        environment = {
            **os.environ,
            "HOME": str(self.root / "failed-home"),
            "CODEX_HOME": str(self.root / "failed-codex"),
        }
        installed = self.run_core(
            "install", "--agent", "codex", "--profile", "software-dev", "--target", str(target),
            env=environment,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        plan_path = self.root / "failed-plan.json"
        planned = self.run_core(
            "update", "plan", "--target", str(target), "--version", "v0.2.1",
            "--from", str(self.remote), "--save", str(plan_path), env=environment,
        )
        self.assertEqual(planned.returncode, 0, planned.stdout + planned.stderr)
        before = {path.relative_to(target): path.read_bytes() for path in target.rglob("*") if path.is_file()}

        applied = self.run_core("update", "apply", "--plan", str(plan_path), env=environment)

        self.assertNotEqual(applied.returncode, 0)
        self.assertIn("Post-update doctor failed", applied.stderr)
        after = {path.relative_to(target): path.read_bytes() for path in target.rglob("*") if path.is_file()}
        self.assertEqual(after, before)
        receipt_root = Path(environment["HOME"]) / ".agentsmith" / "update-receipts"
        self.assertFalse(receipt_root.exists())

    def test_apply_rejects_changed_candidate_installer_semantics_for_project_scope(self) -> None:
        self.commit_and_tag("0.2.0")
        self.commit_and_tag("0.2.1", broken_runtime_health=True)
        cloned = subprocess.run(
            ["git", "clone", "-q", "--bare", str(self.seed), str(self.remote)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(cloned.returncode, 0, cloned.stdout + cloned.stderr)
        target = self.root / "stale runtime project"
        target.mkdir()
        environment = {
            **os.environ,
            "HOME": str(self.root / "stale-project-home"),
            "CODEX_HOME": str(self.root / "stale-project-codex"),
        }
        installed = self.run_core(
            "install", "--agent", "codex", "--profile", "software-dev", "--target", str(target),
            env=environment,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        before = {path.relative_to(target): path.read_bytes() for path in target.rglob("*") if path.is_file()}
        plan_path = self.root / "stale-project-plan.json"
        planned = self.run_core(
            "update", "plan", "--target", str(target), "--version", "v0.2.1",
            "--from", str(self.remote), "--save", str(plan_path), env=environment,
        )
        self.assertEqual(planned.returncode, 0, planned.stdout + planned.stderr)

        applied = self.run_core("update", "apply", "--plan", str(plan_path), env=environment)

        self.assertNotEqual(applied.returncode, 0)
        self.assertIn("staged managed changes do not match the authenticated plan", applied.stderr)
        after = {path.relative_to(target): path.read_bytes() for path in target.rglob("*") if path.is_file()}
        self.assertEqual(after, before)

    def test_apply_rejects_changed_candidate_installer_semantics_for_global_scope(self) -> None:
        self.commit_and_tag("0.2.0")
        self.commit_and_tag("0.2.1", broken_runtime_health=True)
        cloned = subprocess.run(
            ["git", "clone", "-q", "--bare", str(self.seed), str(self.remote)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(cloned.returncode, 0, cloned.stdout + cloned.stderr)
        home = self.root / "stale-global-home"
        codex_home = self.root / "stale-global-codex"
        environment = {**os.environ, "HOME": str(home), "CODEX_HOME": str(codex_home)}
        installed = self.run_core(
            "install", "--agent", "codex", "--global", "--with-handoff-hooks", env=environment,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        observed = [
            home / ".agentsmith" / "state.json",
            home / ".agentsmith" / "agentsmith.py",
            codex_home / "AGENTS.md",
            codex_home / "config.toml",
            codex_home / "hooks.json",
        ]
        before = {path: path.read_bytes() for path in observed}
        plan_path = self.root / "stale-global-plan.json"
        planned = self.run_core(
            "update", "plan", "--global", "--version", "v0.2.1",
            "--from", str(self.remote), "--save", str(plan_path), env=environment,
        )
        self.assertEqual(planned.returncode, 0, planned.stdout + planned.stderr)

        applied = self.run_core("update", "apply", "--plan", str(plan_path), env=environment)

        self.assertNotEqual(applied.returncode, 0)
        self.assertIn("staged managed changes do not match the authenticated plan", applied.stderr)
        self.assertEqual({path: path.read_bytes() for path in observed}, before)

    def test_atomic_replace_retries_transient_sharing_denial_with_a_fixed_cap(self) -> None:
        source = Path("temporary-update-file")
        destination = Path("managed-destination")
        with mock.patch.object(
            Path, "replace", side_effect=[PermissionError("sharing violation"), PermissionError("sharing violation"), None]
        ) as replaced, mock.patch.object(runtime.time, "sleep") as slept:
            runtime.replace_with_retry(source, destination)
        self.assertEqual(replaced.call_count, 3)
        self.assertEqual([call.args[0] for call in slept.call_args_list], [0.05, 0.1])

    def test_shadow_path_translation_rewrites_canonical_aliases(self) -> None:
        shadow = self.root / "alias" / ".." / "shadow"
        canonical_shadow = shadow.resolve()
        actual = self.root / "actual"
        content = str(canonical_shadow / ".agentsmith" / "agentsmith.py").encode("utf-8")

        translated = runtime.translate_root_paths(
            content,
            {"target": shadow},
            {"target": str(actual)},
        ).decode("utf-8")

        self.assertEqual(translated, str(actual / ".agentsmith" / "agentsmith.py"))

    def test_proposal_mismatch_summary_names_paths_and_fields_without_contents(self) -> None:
        expected = [{
            "root": "home",
            "path": ".agentsmith/state.json",
            "operation": "replace",
            "before_sha256": "a" * 64,
            "before_mode": 0o600,
            "after_sha256": "b" * 64,
            "after_mode": 0o600,
        }]
        actual = [{**expected[0], "after_sha256": "c" * 64, "after_mode": 0o666}, {
            "root": "home",
            "path": ".claude/settings.json",
            "operation": "create",
            "before_sha256": None,
            "before_mode": None,
            "after_sha256": "d" * 64,
            "after_mode": 0o600,
        }]

        summary = runtime.proposal_mismatch_summary(expected, actual)

        self.assertEqual(
            summary,
            "changed home:.agentsmith/state.json (after_mode, after_sha256); "
            "unexpected home:.claude/settings.json",
        )
        self.assertNotIn("b" * 64, summary)
        self.assertNotIn("c" * 64, summary)

    def test_translated_statusline_hash_tracks_the_translated_wrapper_bytes(self) -> None:
        home = self.root / "translated-home"
        wrapper_path = home / ".claude" / "agentsmith-statusline.ps1"
        before = b"shadow-specific wrapper\n"
        after = b"live-path wrapper\n"
        state = {
            "native_statuslines": {
                "claude": {
                    "files": {str(wrapper_path): hashlib.sha256(before).hexdigest()},
                },
            },
        }
        translated = {
            "home": {
                ".agentsmith/state.json": (
                    (json.dumps(state, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
                    0o600,
                ),
                ".claude/agentsmith-statusline.ps1": (after, 0o600),
            },
        }

        runtime.refresh_translated_statusline_hashes(
            {"roots": {"home": str(home)}}, translated
        )

        rendered = json.loads(translated["home"][".agentsmith/state.json"][0])
        recorded = rendered["native_statuslines"]["claude"]["files"][str(wrapper_path)]
        self.assertEqual(recorded, hashlib.sha256(after).hexdigest())

    def test_doctor_tilde_paths_use_the_runtime_home_override(self) -> None:
        isolated_home = self.root / "doctor-runtime-home"

        with mock.patch.object(runtime, "home_dir", return_value=isolated_home):
            resolved = runtime.resolve_doctor_path("~/.claude/CLAUDE.md")

        self.assertEqual(resolved, (isolated_home / ".claude" / "CLAUDE.md").resolve())

    def test_statusline_update_is_staged_without_touching_live_installation(self) -> None:
        self.commit_and_tag("0.2.0")
        self.commit_and_tag("0.2.1", statusline_probe="RELEASE_STATUSLINE_PROBE_0_2_1")
        cloned = subprocess.run(
            ["git", "clone", "-q", "--bare", str(self.seed), str(self.remote)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(cloned.returncode, 0, cloned.stdout + cloned.stderr)
        target = self.root / "statusline project"
        target.mkdir()
        home = self.root / "statusline-home"
        environment = {
            **os.environ,
            "HOME": str(home),
            "CODEX_HOME": str(self.root / "statusline-codex"),
        }
        installed = self.run_core(
            "install", "--agent", "claude", "--profile", "software-dev", "--target", str(target),
            env=environment,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        helper = home / ".claude" / "agentsmith-statusline.py"
        self.assertNotIn("RELEASE_STATUSLINE_PROBE_0_2_1", helper.read_text(encoding="utf-8"))
        watched_roots = (target, home, Path(environment["CODEX_HOME"]))
        before = {
            path: (path.read_bytes(), path.stat().st_mode & 0o777)
            for root in watched_roots
            if root.exists()
            for path in root.rglob("*")
            if path.is_file()
        }
        before_backups = {
            path
            for root in watched_roots if root.exists()
            for path in root.rglob("*.bak.*")
        }
        plan_path = self.root / "statusline-plan.json"

        planned = self.run_core(
            "update", "plan", "--target", str(target), "--version", "v0.2.1",
            "--from", str(self.remote), "--save", str(plan_path), env=environment,
        )

        self.assertEqual(planned.returncode, 0, planned.stdout + planned.stderr)
        after = {
            path: (path.read_bytes(), path.stat().st_mode & 0o777)
            for root in watched_roots
            if root.exists()
            for path in root.rglob("*")
            if path.is_file() and path.name != "update-integrity.key"
        }
        self.assertEqual(after, before)
        self.assertEqual({
            path
            for root in watched_roots if root.exists()
            for path in root.rglob("*.bak.*")
        }, before_backups)
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        helper_change = next(
            item for item in plan["proposed_changes"]
            if item["root"] == "home" and item["path"] == ".claude/agentsmith-statusline.py"
        )
        self.assertEqual(helper_change["operation"], "replace")
        self.assertNotIn("RELEASE_STATUSLINE_PROBE_0_2_1", helper.read_text(encoding="utf-8"))

        applied = self.run_core("update", "apply", "--plan", str(plan_path), env=environment)

        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertIn("RELEASE_STATUSLINE_PROBE_0_2_1", helper.read_text(encoding="utf-8"))

    def test_native_hook_update_points_to_real_runtime_not_discarded_shadow(self) -> None:
        self.commit_and_tag("0.2.0")
        self.commit_and_tag("0.2.1")
        cloned = subprocess.run(
            ["git", "clone", "-q", "--bare", str(self.seed), str(self.remote)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(cloned.returncode, 0, cloned.stdout + cloned.stderr)
        target = self.root / "hook project"
        target.mkdir()
        environment = {
            **os.environ,
            "HOME": str(self.root / "hook-home"),
            "CODEX_HOME": str(self.root / "hook-codex"),
        }
        installed = self.run_core(
            "install", "--agent", "codex", "--profile", "software-dev", "--target", str(target),
            "--with-handoff-hooks", env=environment,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        plan_path = self.root / "hook-plan.json"
        planned = self.run_core(
            "update", "plan", "--target", str(target), "--version", "v0.2.1",
            "--from", str(self.remote), "--save", str(plan_path), env=environment,
        )
        self.assertEqual(planned.returncode, 0, planned.stdout + planned.stderr)

        applied = self.run_core("update", "apply", "--plan", str(plan_path), env=environment)

        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        hooks = json.loads((Path(environment["CODEX_HOME"]) / "hooks.json").read_text(encoding="utf-8"))
        commands = [
            hook["command"]
            for entry in hooks["hooks"]["UserPromptSubmit"]
            for hook in entry["hooks"]
        ]
        self.assertTrue(any(str(target.resolve() / ".agentsmith" / "agentsmith.py") in command for command in commands))
        self.assertFalse(any("agentsmith-apply-" in command for command in commands))

    def test_plain_installer_rerun_does_not_forget_still_managed_capabilities(self) -> None:
        target = self.root / "capability rerun"
        target.mkdir()
        environment = {
            **os.environ,
            "HOME": str(self.root / "capability-home"),
            "CODEX_HOME": str(self.root / "capability-codex"),
        }
        first = self.run_core(
            "install", "--agent", "codex", "--profile", "software-dev", "--target", str(target),
            "--with-skills", "--with-mcp", "context7", "--with-handoff-hooks", env=environment,
        )
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)

        second = self.run_core(
            "install", "--agent", "codex", "--profile", "software-dev", "--target", str(target),
            env=environment,
        )

        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        state = json.loads((target / ".agentsmith" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(
            state["installation"]["capabilities"],
            {"handoff_hooks": True, "hooks": False, "mcp": ["context7"], "skills": True, "ui_design_hook": False},
        )

    def test_cautious_rerun_cannot_make_the_next_update_restore_trusted_safety(self) -> None:
        self.commit_and_tag("0.2.0")
        self.commit_and_tag("0.2.1")
        cloned = subprocess.run(
            ["git", "clone", "-q", "--bare", str(self.seed), str(self.remote)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(cloned.returncode, 0, cloned.stdout + cloned.stderr)
        target = self.root / "safety project"
        target.mkdir()
        environment = {
            **os.environ,
            "HOME": str(self.root / "safety-home"),
            "CODEX_HOME": str(self.root / "safety-codex"),
        }
        trusted = self.run_core(
            "install", "--agent", "codex", "--profile", "software-dev", "--target", str(target),
            "--safety", "trusted", env=environment,
        )
        self.assertEqual(trusted.returncode, 0, trusted.stdout + trusted.stderr)
        cautious = self.run_core(
            "install", "--agent", "codex", "--profile", "software-dev", "--target", str(target),
            env=environment,
        )
        self.assertEqual(cautious.returncode, 0, cautious.stdout + cautious.stderr)
        state_path = target / ".agentsmith" / "state.json"
        self.assertEqual(json.loads(state_path.read_text(encoding="utf-8"))["installation"]["safety"], {"codex": "cautious"})
        plan_path = self.root / "cautious-plan.json"
        planned = self.run_core(
            "update", "plan", "--target", str(target), "--version", "v0.2.1",
            "--from", str(self.remote), "--save", str(plan_path), env=environment,
        )
        self.assertEqual(planned.returncode, 0, planned.stdout + planned.stderr)
        self.assertEqual(json.loads(plan_path.read_text(encoding="utf-8"))["installation"]["safety"], {"codex": "cautious"})
        applied = self.run_core("update", "apply", "--plan", str(plan_path), env=environment)
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        config = (Path(environment["CODEX_HOME"]) / "config.toml").read_text(encoding="utf-8")
        self.assertIn('approval_policy = "on-request"', config)
        self.assertIn('sandbox_mode = "workspace-write"', config)

    def test_update_plan_rejects_a_symbolic_link_in_a_managed_path(self) -> None:
        self.commit_and_tag("0.2.0")
        self.commit_and_tag("0.2.1")
        cloned = subprocess.run(
            ["git", "clone", "-q", "--bare", str(self.seed), str(self.remote)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(cloned.returncode, 0, cloned.stdout + cloned.stderr)
        target = self.root / "symlink project"
        target.mkdir()
        environment = {
            **os.environ,
            "HOME": str(self.root / "symlink-home"),
            "CODEX_HOME": str(self.root / "symlink-codex"),
        }
        installed = self.run_core(
            "install", "--agent", "codex", "--profile", "software-dev", "--target", str(target),
            env=environment,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        moved_state = self.root / "moved-agentsmith-state"
        shutil.move(str(target / ".agentsmith"), moved_state)
        (target / ".agentsmith").symlink_to(moved_state, target_is_directory=True)

        planned = self.run_core(
            "update", "plan", "--target", str(target), "--version", "v0.2.1",
            "--from", str(self.remote), env=environment,
        )

        self.assertNotEqual(planned.returncode, 0)
        self.assertIn("symbolic link", planned.stderr)


if __name__ == "__main__":
    unittest.main()
