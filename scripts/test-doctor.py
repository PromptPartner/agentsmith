#!/usr/bin/env python3
"""Behavioral tests for doctor against effective installed state."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock


ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "agentsmith.py"


class DoctorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="agentsmith doctor ü ")
        self.root = Path(self.temporary.name)
        self.env = os.environ.copy()
        self.env.update(
            {
                "HOME": str(self.root / "home with spaces"),
                "USERPROFILE": str(self.root / "home with spaces"),
                "CODEX_HOME": str(self.root / "custom codex ü"),
                # Keep Windows on its locale decoder so Unicode Git paths exercise
                # doctor's explicit UTF-8 subprocess contract. Keep stdio UTF-8
                # so a UTF-8 parent can decode this locale-mode child reliably.
                "PYTHONUTF8": "0",
                "PYTHONIOENCODING": "utf-8",
            }
        )
        # Client settings from the operator's own shell must not redirect or silence fixtures.
        for name in (
            "PI_CODING_AGENT_DIR", "XDG_CONFIG_HOME", "OPENCODE_DISABLE_CLAUDE_CODE",
            "OPENCODE_DISABLE_CLAUDE_CODE_SKILLS",
        ):
            self.env.pop(name, None)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_core(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CORE), *arguments], cwd=ROOT, env=self.env,
            text=True, encoding="utf-8", errors="replace", capture_output=True, check=False,
        )

    def install(self, target: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        target.mkdir(parents=True, exist_ok=True)
        return self.run_core("install", "--target", str(target), *arguments)

    def doctor(self, target: Path, agent: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = self.run_core("doctor", "--agent", agent, "--target", str(target), "--json")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            payload = {}
        return result, payload

    @staticmethod
    def warning_codes(agent: dict) -> set[str]:
        return {warning.get("code", "") for warning in agent.get("warnings", [])}

    def test_consumer_install_prepares_autonomous_manifest(self) -> None:
        project = self.root / "fresh consumer"
        installed = self.install(project, "--agent", "codex", "--profile", "software-dev")
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        subprocess.run(["git", "-C", str(project), "init", "-q"], check=True)
        prepared = subprocess.run(
            [sys.executable, str(project / ".agentsmith/autonomous-run.py"), "prepare",
             "--run-id", "consumer", "--spec", "docs/specs/task.md", "--ticket", "TASK-1"],
            cwd=project, env=self.env, text=True, capture_output=True, check=False,
        )
        self.assertEqual(prepared.returncode, 0, prepared.stdout + prepared.stderr)
        manifest = json.loads((project / ".harness/runs/consumer.json").read_text())
        self.assertEqual(manifest["run_id"], "consumer")
        self.assertEqual(manifest["implementation_ticket"], "TASK-1")

    def test_strict_doctor_detects_missing_required_payloads(self) -> None:
        project = self.root / "incomplete consumer"
        installed = self.install(project, "--agent", "codex", "--profile", "software-dev")
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        for relative in (".agentsmith/native_launcher.py", ".agentsmith/autonomous-run.py",
                         ".harness/templates/autonomous-run.json"):
            with self.subTest(relative=relative):
                path = project / relative
                original = path.read_bytes() if path.exists() else None
                if path.exists():
                    path.unlink()
                strict = self.run_core("doctor", "--agent", "codex", "--target", str(project),
                                       "--strict", "--json")
                self.assertNotEqual(strict.returncode, 0, strict.stdout + strict.stderr)
                agent = json.loads(strict.stdout)["codex"]
                self.assertIn(relative, agent["runtime"]["missing_payloads"])
                self.assertIn("required-runtime-payload-missing", self.warning_codes(agent))
                if original is not None:
                    path.write_bytes(original)

    def test_strict_doctor_detects_an_edited_runtime_file(self) -> None:
        project = self.root / "edited runtime"
        installed = self.install(project, "--agent", "codex", "--profile", "software-dev")
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        state = json.loads((project / ".agentsmith/state.json").read_text(encoding="utf-8"))
        recorded = {item["path"]: item["sha256"] for item in state["installation"]["runtime_files"]}
        self.assertIn(".agentsmith/work_graph.py", recorded)
        self.assertIn(".agentsmith/autonomous-run.py", recorded)
        self.assertEqual(
            recorded[".agentsmith/work_graph.py"],
            hashlib.sha256((project / ".agentsmith/work_graph.py").read_bytes()).hexdigest(),
        )
        # The update planner must accept the new record, or the next update would refuse it.
        load_core().validate_installation_manifest(state)
        clean = self.run_core("doctor", "--agent", "codex", "--target", str(project), "--strict", "--json")
        self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
        self.assertEqual(json.loads(clean.stdout)["codex"]["runtime"]["modified_files"], [])
        with (project / ".agentsmith/work_graph.py").open("a", encoding="utf-8") as handle:
            handle.write("# local edit\n")
        strict = self.run_core("doctor", "--agent", "codex", "--target", str(project), "--strict", "--json")
        self.assertNotEqual(strict.returncode, 0, strict.stdout + strict.stderr)
        agent = json.loads(strict.stdout)["codex"]
        self.assertEqual(agent["runtime"]["modified_files"], [".agentsmith/work_graph.py"])
        self.assertIn("runtime-file-modified", self.warning_codes(agent))
        self.assertEqual(self.doctor(project, "codex")[0].returncode, 0, "a plain doctor run only warns")

    def test_reinstall_refreshes_managed_controller_and_preserves_draft_template(self) -> None:
        project = self.root / "reinstalled consumer"
        installed = self.install(project, "--agent", "codex", "--profile", "software-dev")
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        controller = project / ".agentsmith/autonomous-run.py"
        controller.write_text("# stale managed controller\n")
        template = project / ".harness/templates/autonomous-run.json"
        template.write_text('{"project_draft": true}\n')
        reinstalled = self.install(project, "--agent", "codex", "--profile", "software-dev")
        self.assertEqual(reinstalled.returncode, 0, reinstalled.stdout + reinstalled.stderr)
        self.assertEqual(controller.read_bytes(), (ROOT / "scripts/autonomous-run.py").read_bytes())
        self.assertEqual(json.loads(template.read_text()), {"project_draft": True})

    def test_autonomous_install_refuses_symlink_payload_paths(self) -> None:
        for relative in (".agentsmith/autonomous-run.py", ".harness/templates/autonomous-run.json",
                         ".agentsmith", ".harness/templates"):
            with self.subTest(relative=relative):
                project = self.root / ("unsafe project " + relative.replace("/", "-"))
                destination = project / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                outside = self.root / ("outside " + relative.replace("/", "-"))
                directory = relative in {".agentsmith", ".harness/templates"}
                if directory:
                    outside.mkdir()
                    sentinel = outside / "sentinel.txt"
                else:
                    sentinel = outside
                sentinel.write_text("preserve outside bytes\n")
                try:
                    destination.symlink_to(outside, target_is_directory=directory)
                except (OSError, NotImplementedError) as exc:
                    self.skipTest(f"symlinks unavailable: {exc}")
                installed = self.install(project, "--agent", "codex", "--profile", "software-dev")
                self.assertNotEqual(installed.returncode, 0, installed.stdout + installed.stderr)
                self.assertIn("symbolic link", installed.stdout + installed.stderr)
                self.assertEqual(sentinel.read_text(), "preserve outside bytes\n")
                self.assertTrue(destination.is_symlink())
                if directory:
                    self.assertEqual(sorted(p.name for p in outside.iterdir()), ["sentinel.txt"])

    def test_duplicate_full_cores_warn_but_profile_only_layer_does_not(self) -> None:
        global_install = self.run_core(
            "install", "--agent", "native", "--global", "--profile", "software-dev", "--assemble-only"
        )
        self.assertEqual(global_install.returncode, 0, global_install.stdout)
        full = self.root / "full project"
        layered = self.root / "layered project"
        self.assertEqual(
            self.install(full, "--agent", "native", "--profile", "software-dev", "--assemble-only").returncode, 0
        )
        self.assertEqual(
            self.install(
                layered, "--agent", "native", "--profile", "software-dev", "--profile-only", "--assemble-only"
            ).returncode, 0
        )
        full_result, full_payload = self.doctor(full, "codex")
        layered_result, layered_payload = self.doctor(layered, "codex")
        self.assertEqual(full_result.returncode, 0, full_result.stdout)
        full_agent = full_payload["codex"]
        layered_agent = layered_payload["codex"]
        self.assertIn("duplicate-managed-core", self.warning_codes(full_agent))
        self.assertGreater(full_agent["instructions"]["duplicate_tokens"], 0)
        self.assertIn("--profile-only", json.dumps(full_agent["warnings"]))
        self.assertNotIn("duplicate-managed-core", self.warning_codes(layered_agent))
        self.assertEqual(layered_agent["instructions"]["duplicate_tokens"], 0)
        self.assertEqual(
            [source["generated_core"] for source in layered_agent["instructions"]["sources"] if source["exists"]],
            [True, False],
        )

    def test_claude_duplicate_core_above_the_git_root_is_reported(self) -> None:
        # Claude Code loads CLAUDE.md from every ancestor, not only from the Git root down.
        outer = self.root / "outer workspace"
        inner = outer / "inner repo"
        self.assertEqual(self.install(outer, "--agent", "claude", "--profile", "software-dev", "--assemble-only").returncode, 0)
        self.assertEqual(self.install(inner, "--agent", "claude", "--profile", "software-dev", "--assemble-only").returncode, 0)
        subprocess.run(["git", "-C", str(inner), "init", "-q"], check=True)
        _, payload = self.doctor(inner, "claude")
        agent = payload["claude"]
        self.assertIn("duplicate-managed-core", self.warning_codes(agent))
        loaded = [Path(path) for path in agent["instructions"]["loaded_files"]]
        self.assertIn((outer / "CLAUDE.md").resolve(), loaded)
        self.assertIn((inner / "CLAUDE.md").resolve(), loaded)
        message = next(w["message"] for w in agent["warnings"] if w["code"] == "duplicate-managed-core")
        self.assertIn("Claude Code", message)
        self.assertIn(str((outer / "CLAUDE.md").resolve()), message)
        self.assertNotIn("legacy-managed-block", self.warning_codes(agent), "both copies belong to a current install")
        # Codex reads from the Git root down, so the outer copy is outside its chain.
        _, codex_payload = self.doctor(inner, "codex")
        self.assertNotIn("duplicate-managed-core", self.warning_codes(codex_payload["codex"]))
        self.assertNotIn(str((outer / "AGENTS.md").resolve()), codex_payload["codex"]["instructions"]["loaded_files"])

    def test_legacy_home_agents_block_is_reported_only_for_the_tool_that_loads_it(self) -> None:
        donor = self.root / "donor"
        self.assertEqual(self.install(donor, "--agent", "codex", "--profile", "general-admin", "--assemble-only").returncode, 0)
        home = Path(self.env["HOME"])
        home.mkdir(parents=True, exist_ok=True)
        legacy = home / "AGENTS.md"
        legacy.write_text((donor / "AGENTS.md").read_text(encoding="utf-8"), encoding="utf-8")
        repo = home / "work" / "repo"
        repo.mkdir(parents=True)
        subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
        _, claude_payload = self.doctor(repo, "claude")
        warning = next(w for w in claude_payload["claude"]["warnings"] if w["code"] == "legacy-managed-block")
        self.assertIn(str(legacy.resolve()), warning["message"])
        self.assertIn("Claude Code", warning["message"])
        _, codex_payload = self.doctor(repo, "codex")
        self.assertNotIn("legacy-managed-block", self.warning_codes(codex_payload["codex"]))
        # A clone carries the project's rules without the untracked install record; that is not legacy.
        (repo / "AGENTS.md").write_text((donor / "AGENTS.md").read_text(encoding="utf-8"), encoding="utf-8")
        _, clone_payload = self.doctor(repo, "codex")
        self.assertNotIn("legacy-managed-block", self.warning_codes(clone_payload["codex"]))
        # A CLAUDE.md in the folder chain stops Claude Code from reading AGENTS.md at all.
        (repo / "CLAUDE.md").write_text("# Project notes\n", encoding="utf-8")
        _, quiet = self.doctor(repo, "claude")
        self.assertNotIn("legacy-managed-block", self.warning_codes(quiet["claude"]))
        self.assertNotIn(str(legacy.resolve()), quiet["claude"]["instructions"]["loaded_files"])

    def test_codex_override_file_replaces_agents_md(self) -> None:
        repo = self.root / "override repo"
        self.assertEqual(self.install(repo, "--agent", "codex", "--profile", "general-admin", "--assemble-only").returncode, 0)
        subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
        (repo / "AGENTS.override.md").write_text("# Local override\n", encoding="utf-8")
        _, payload = self.doctor(repo, "codex")
        loaded = payload["codex"]["instructions"]["loaded_files"]
        self.assertIn(str((repo / "AGENTS.override.md").resolve()), loaded)
        self.assertNotIn(str((repo / "AGENTS.md").resolve()), loaded)

    def test_output_rewriting_pre_tool_hook_is_reported(self) -> None:
        project = self.root / "rewritten output"
        (project / ".claude").mkdir(parents=True)
        settings = Path(self.env["HOME"]) / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)

        def hooks(matcher: str, command: str) -> str:
            return json.dumps({"hooks": {"PreToolUse": [{"matcher": matcher, "hooks": [{"type": "command", "command": command}]}]}})

        settings.write_text(hooks("Write|Edit", "rtk hook claude"), encoding="utf-8")
        _, quiet = self.doctor(project, "claude")
        self.assertNotIn("output-rewriting-hook", self.warning_codes(quiet["claude"]), "only shell tools are rewritten")
        # Claude Code also reads the untracked project-local settings file.
        (project / ".claude" / "settings.local.json").write_text(hooks("Bash", "rtk hook claude"), encoding="utf-8")
        _, local = self.doctor(project, "claude")
        warning = next(w for w in local["claude"]["warnings"] if w["code"] == "output-rewriting-hook")
        self.assertIn("rtk hook claude", warning["message"])
        self.assertIn("settings.local.json", warning["message"])
        self.assertIn("rtk proxy", warning["recommendation"])
        codex_hooks = Path(self.env["CODEX_HOME"]) / "hooks.json"
        codex_hooks.parent.mkdir(parents=True, exist_ok=True)
        codex_hooks.write_text(hooks("*", "/usr/local/bin/rtk hook codex"), encoding="utf-8")
        _, codex = self.doctor(project, "codex")
        self.assertIn("output-rewriting-hook", self.warning_codes(codex["codex"]))

    def test_skill_that_cites_a_path_the_install_lacks_is_reported(self) -> None:
        project = self.root / "skill paths"
        installed = self.install(project, "--agent", "codex", "--profile", "software-dev", "--with-skills")
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        _, clean = self.doctor(project, "codex")
        cited = {w["message"] for w in clean["codex"]["warnings"] if w["code"] == "skill-path-missing"}
        # A skill that names the installed path and the source-checkout path needs only one of them.
        self.assertFalse(any("autonomous-run" in message or "wayfinder" in message for message in cited), cited)
        (project / ".harness" / "templates" / "plan.md").unlink()
        skill = project / ".agents" / "skills" / "handoff" / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\nSee `templates/missing-guide.md` and `.harness/runs/<id>.json`.\n", encoding="utf-8")
        _, payload = self.doctor(project, "codex")
        messages = {w["message"] for w in payload["codex"]["warnings"] if w["code"] == "skill-path-missing"}
        grill = next(message for message in messages if "grill-with-docs" in message)
        self.assertIn(".harness/templates/plan.md", grill)
        handoff = next(message for message in messages if "handoff" in message)
        self.assertIn("templates/missing-guide.md", handoff)
        self.assertNotIn(".harness/runs", handoff, "a placeholder path is created at run time")

    def test_superpowers_skills_named_without_the_plugin_are_reported(self) -> None:
        project = self.root / "superpowers project"
        (project / ".claude").mkdir(parents=True)
        (project / "CLAUDE.md").write_text("Use `superpowers:brainstorming` before building.\n", encoding="utf-8")
        _, missing = self.doctor(project, "claude")
        warning = next(w for w in missing["claude"]["warnings"] if w["code"] == "superpowers-not-enabled")
        self.assertIn("superpowers:brainstorming", warning["message"])
        settings = Path(self.env["HOME"]) / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps({"enabledPlugins": {"superpowers@claude-plugins-official": True}}), encoding="utf-8")
        _, enabled = self.doctor(project, "claude")
        self.assertNotIn("superpowers-not-enabled", self.warning_codes(enabled["claude"]))
        # Local settings override user settings, so a local opt-out disables it again.
        (project / ".claude" / "settings.local.json").write_text(
            json.dumps({"enabledPlugins": {"superpowers@claude-plugins-official": False}}), encoding="utf-8"
        )
        _, disabled = self.doctor(project, "claude")
        self.assertIn("superpowers-not-enabled", self.warning_codes(disabled["claude"]))
        _, codex = self.doctor(project, "codex")
        self.assertNotIn("superpowers-not-enabled", self.warning_codes(codex["codex"]))

    def git(self, repo: Path, *arguments: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.com", *arguments],
            check=True, text=True, capture_output=True,
        ).stdout.strip()

    def test_managed_block_behind_the_default_branch_is_reported(self) -> None:
        repo = self.root / "behind repo"
        self.assertEqual(self.install(repo, "--agent", "codex", "--profile", "general-admin", "--assemble-only").returncode, 0)
        self.git(repo, "init", "-q", "-b", "master")
        self.git(repo, "add", "AGENTS.md")
        self.git(repo, "commit", "-q", "--no-verify", "-m", "chore: rules")
        self.git(repo, "switch", "-q", "-c", "feature")
        _, same = self.doctor(repo, "codex")
        self.assertNotIn("managed-block-behind-default-branch", self.warning_codes(same["codex"]))
        self.git(repo, "switch", "-q", "master")
        rules = repo / "AGENTS.md"
        rules.write_text(rules.read_text(encoding="utf-8").replace("<!-- END AGENTSMITH -->", "Newer rule.\n<!-- END AGENTSMITH -->"), encoding="utf-8")
        self.git(repo, "commit", "-q", "--no-verify", "-am", "chore: newer rules")
        self.git(repo, "switch", "-q", "feature")
        _, behind = self.doctor(repo, "codex")
        warning = next(w for w in behind["codex"]["warnings"] if w["code"] == "managed-block-behind-default-branch")
        self.assertIn("master", warning["message"])
        self.assertIn("AGENTS.md", warning["message"])
        # A branch that changed the block itself is ahead, not behind.
        rules.write_text(rules.read_text(encoding="utf-8").replace("<!-- END AGENTSMITH -->", "Branch rule.\n<!-- END AGENTSMITH -->"), encoding="utf-8")
        self.git(repo, "commit", "-q", "--no-verify", "-am", "chore: branch rules")
        _, diverged = self.doctor(repo, "codex")
        self.assertNotIn("managed-block-behind-default-branch", self.warning_codes(diverged["codex"]))

    def test_trusted_native_install_reports_actual_owned_surfaces(self) -> None:
        project = self.root / "owned project ü"
        project.mkdir()
        subprocess.run(["git", "-C", str(project), "init", "-q"], check=True)
        installed = self.run_core(
            "install", "--agent", "native", "--profile", "software-dev", "--target", str(project),
            "--safety", "trusted", "--with-skills", "--with-mcp", "playwright",
            "--with-hooks", "--with-handoff-hooks",
        )
        self.assertEqual(installed.returncode, 0, installed.stdout)
        for agent_id in ("claude", "codex"):
            result, payload = self.doctor(project, agent_id)
            self.assertEqual(result.returncode, 0, result.stdout)
            agent = payload[agent_id]
            self.assertEqual(agent["safety"]["state"], "trusted")
            self.assertEqual(agent["skills"]["state"], "managed")
            self.assertEqual(agent["mcp"]["state"], "managed")
            self.assertEqual(agent["hooks"]["state"], "managed", f"{agent_id}: {agent['hooks']}")
            self.assertTrue(agent["hooks"]["current_runtime"])
            self.assertTrue(agent["hooks"]["scanner_current"])
            self.assertEqual(agent["statusline"]["state"], "managed" if agent_id == "claude" else "builtin")
            self.assertTrue(agent["statusline"]["active"])
            self.assertEqual(agent["runtime"]["state"], "current")
            self.assertIn("trusted-expanded-surface", self.warning_codes(agent))

    def test_container_safety_drops_only_the_codex_sandbox(self) -> None:
        # Inside Docker the Codex sandbox cannot start, so container mode keeps approvals but
        # lets the container be the isolation boundary (#47).
        project = self.root / "container project"
        project.mkdir()
        subprocess.run(["git", "-C", str(project), "init", "-q"], check=True)
        base = ("install", "--agent", "native", "--profile", "software-dev", "--target", str(project))
        installed = self.run_core(*base, "--safety", "container")
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        settings_path = Path(self.env["HOME"]) / ".claude" / "settings.json"
        codex_path = Path(self.env["CODEX_HOME"]) / "config.toml"
        self.assertEqual(json.loads(settings_path.read_text(encoding="utf-8"))["permissions"]["defaultMode"], "acceptEdits")
        codex = codex_path.read_text(encoding="utf-8")
        self.assertIn('approval_policy = "on-request"', codex)
        self.assertIn('sandbox_mode = "danger-full-access"', codex)
        state = json.loads((project / ".agentsmith" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["installation"]["safety"], {"claude": "container", "codex": "container"})
        if not load_core().detect_container():
            self.assertIn("no container was detected", installed.stdout + installed.stderr)
        for agent_id in ("claude", "codex"):
            result, payload = self.doctor(project, agent_id)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(payload[agent_id]["safety"]["state"], "container", agent_id)
        rerun = self.run_core(*base)
        self.assertEqual(rerun.returncode, 0, rerun.stdout + rerun.stderr)
        self.assertIn("from container to cautious", rerun.stdout + rerun.stderr)
        self.assertIn('sandbox_mode = "workspace-write"', codex_path.read_text(encoding="utf-8"))

    def test_unmanaged_nested_sources_and_missing_custom_global_are_reported(self) -> None:
        project = self.root / "nested repo"
        nested = project / "packages" / "apï"
        nested.mkdir(parents=True)
        subprocess.run(["git", "-C", str(project), "init", "-q"], check=True)
        (project / "AGENTS.md").write_text("# Foreign project instructions\n", encoding="utf-8")
        (nested / "AGENTS.md").write_text(
            """<!-- BEGIN AGENTSMITH — universal agent harness (managed by agentsmith — edit core/profiles, not here) -->
<!-- Generated. Profiles: software-dev. core=false. Edit core/ or profiles/, then re-run setup. -->
# Nested managed instructions
<!-- END AGENTSMITH -->
""",
            encoding="utf-8",
        )
        first, payload = self.doctor(nested, "codex")
        second, second_payload = self.doctor(nested, "codex")
        self.assertEqual(first.returncode, 0, first.stdout)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(payload, second_payload)
        sources = payload["codex"]["instructions"]["sources"]
        by_scope = {source["scope"]: source for source in sources}
        self.assertFalse(by_scope["global"]["exists"])
        self.assertEqual(Path(by_scope["global"]["path"]), (Path(self.env["CODEX_HOME"]) / "AGENTS.md").resolve())
        self.assertTrue(by_scope["project"]["exists"])
        self.assertFalse(by_scope["project"]["managed"])
        self.assertEqual(Path(by_scope["project"]["path"]), (project / "AGENTS.md").resolve())
        self.assertEqual(by_scope["nested"]["generated_core"], False)
        self.assertEqual(Path(by_scope["nested"]["path"]), (nested / "AGENTS.md").resolve())
        self.assertTrue(by_scope["nested"]["sha256"])
        self.assertGreater(by_scope["nested"]["tokens"], 0)

    def test_missing_and_conflicting_claude_generated_copy_are_warnings(self) -> None:
        project = self.root / "copy project"
        installed = self.install(project, "--agent", "native", "--profile", "general-admin", "--assemble-only")
        self.assertEqual(installed.returncode, 0, installed.stdout)
        claude_copy = project / "CLAUDE.md"
        original = claude_copy.read_text(encoding="utf-8")
        claude_copy.unlink()
        _, missing_payload = self.doctor(project, "claude")
        self.assertIn("missing-generated-copy", self.warning_codes(missing_payload["claude"]))
        claude_copy.write_text(original.replace("core=true", "core=false", 1), encoding="utf-8")
        _, conflict_payload = self.doctor(project, "claude")
        codes = self.warning_codes(conflict_payload["claude"])
        self.assertIn("conflicting-generator-metadata", codes)

    def test_claude_adapter_drift_fails_strict_and_reinstall_mirrors_canonical_customization(self) -> None:
        project = self.root / "adapter drift project"
        installed = self.install(
            project, "--agent", "claude", "--profile", "software-dev", "--with-skills"
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        canonical = project / ".agents" / "skills" / "handoff" / "SKILL.md"
        adapter = project / ".claude" / "skills" / "handoff" / "SKILL.md"
        self.assertEqual(canonical.read_bytes(), adapter.read_bytes())
        canonical.write_bytes(canonical.read_bytes() + b"\nCANONICAL CUSTOMIZATION\n")
        adapter.write_bytes(adapter.read_bytes() + b"\nSTALE ADAPTER EDIT\n")
        foreign = project / ".claude" / "skills" / "foreign-skill" / "references" / ".venv" / "probe.py"
        foreign.parent.mkdir(parents=True)
        foreign.write_bytes(b"# foreign virtual environment\n")

        strict = self.run_core(
            "doctor", "--agent", "claude", "--target", str(project), "--strict", "--json"
        )
        self.assertNotEqual(strict.returncode, 0, strict.stdout + strict.stderr)
        payload = json.loads(strict.stdout)["claude"]
        self.assertEqual(payload["skills"]["canonical_customized_names"], ["handoff"])
        self.assertEqual(payload["skills"]["adapter_diverged_names"], ["handoff"])
        self.assertIn("canonical-skill-customized", self.warning_codes(payload))
        self.assertIn("skill-adapter-diverged", self.warning_codes(payload))

        reinstalled = self.run_core(
            "install", "--agent", "claude", "--profile", "software-dev", "--target", str(project),
            "--with-skills",
        )
        self.assertEqual(reinstalled.returncode, 0, reinstalled.stdout + reinstalled.stderr)
        self.assertIn(b"CANONICAL CUSTOMIZATION", canonical.read_bytes())
        self.assertNotIn(b"STALE ADAPTER EDIT", adapter.read_bytes())
        self.assertEqual(canonical.read_bytes(), adapter.read_bytes())
        self.assertEqual(
            hashlib.sha256(canonical.read_bytes()).hexdigest(),
            hashlib.sha256(adapter.read_bytes()).hexdigest(),
        )
        self.assertEqual(foreign.read_bytes(), b"# foreign virtual environment\n")
        healthy = self.run_core(
            "doctor", "--agent", "claude", "--target", str(project), "--strict", "--json"
        )
        self.assertEqual(healthy.returncode, 0, healthy.stdout + healthy.stderr)
        healthy_skills = json.loads(healthy.stdout)["claude"]["skills"]
        self.assertEqual(healthy_skills["state"], "customized")
        self.assertEqual(healthy_skills["adapter_diverged_names"], [])

    def test_global_claude_reinstall_regenerates_owned_adapter_without_force(self) -> None:
        installed = self.run_core("install", "--agent", "claude", "--global", "--with-skills")
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        home = Path(self.env["HOME"])
        canonical = home / ".agents" / "skills" / "handoff" / "SKILL.md"
        adapter = home / ".claude" / "skills" / "handoff" / "SKILL.md"
        canonical_before = canonical.read_bytes()
        adapter.write_bytes(b"outdated owned adapter\n")

        reinstalled = self.run_core("install", "--agent", "claude", "--global", "--with-skills")

        self.assertEqual(reinstalled.returncode, 0, reinstalled.stdout + reinstalled.stderr)
        self.assertEqual(canonical.read_bytes(), canonical_before)
        self.assertEqual(adapter.read_bytes(), canonical.read_bytes())

    def test_global_opencode_install_doctor_and_uninstall(self) -> None:
        rules = Path(self.env["HOME"]) / ".config" / "opencode" / "AGENTS.md"
        rules.parent.mkdir(parents=True)
        rules.write_text("# My own OpenCode rules\n", encoding="utf-8")
        project = self.root / "unrelated project"
        project.mkdir()

        installed = self.run_core("install", "--agent", "opencode", "--global", "--profile", "software-dev")

        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        self.assertIn("installed for opencode", installed.stdout)
        text = rules.read_text(encoding="utf-8")
        self.assertIn("<!-- BEGIN AGENTSMITH", text)
        self.assertIn("<!-- END AGENTSMITH -->", text)
        self.assertIn("# My own OpenCode rules", text)
        strict = self.run_core("doctor", "--agent", "opencode", "--target", str(project), "--strict", "--json")
        self.assertEqual(strict.returncode, 0, strict.stdout + strict.stderr)
        sources = json.loads(strict.stdout)["opencode"]["instructions"]["sources"]
        self.assertEqual(Path(sources[0]["path"]), rules.resolve())
        self.assertEqual((sources[0]["scope"], sources[0]["managed_status"]), ("global", "managed"))

        removed = self.run_core("install", "--agent", "opencode", "--global", "--uninstall")

        self.assertEqual(removed.returncode, 0, removed.stdout + removed.stderr)
        self.assertEqual(rules.read_text(encoding="utf-8"), "# My own OpenCode rules\n")

    def test_global_install_refuses_two_agents_sharing_one_rules_file(self) -> None:
        shared = Path(self.env["HOME"]) / ".config" / "opencode"
        self.env["CODEX_HOME"] = str(shared)

        installed = self.run_core("install", "--agent", "codex,opencode", "--global", "--profile", "software-dev")

        self.assertNotEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        self.assertIn("same instruction file", installed.stderr)
        self.assertFalse((shared / "AGENTS.md").exists())
        self.assertFalse((Path(self.env["HOME"]) / ".agentsmith").exists())

    def test_global_opencode_install_reports_an_ignored_xdg_config_home(self) -> None:
        project = self.root / "xdg project"
        project.mkdir()
        self.env["XDG_CONFIG_HOME"] = str(self.root / "xdg config")

        installed = self.run_core("install", "--agent", "opencode", "--global", "--profile", "software-dev")

        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        self.assertIn("XDG_CONFIG_HOME", installed.stderr)
        _, payload = self.doctor(project, "opencode")
        self.assertIn("opencode-xdg-config-ignored", self.warning_codes(payload["opencode"]))

        self.env["XDG_CONFIG_HOME"] = str(Path(self.env["HOME"]) / ".config")
        matching = self.run_core("install", "--agent", "opencode", "--global", "--profile", "software-dev")
        self.assertEqual(matching.returncode, 0, matching.stdout + matching.stderr)
        self.assertNotIn("XDG_CONFIG_HOME", matching.stderr)
        _, matching_payload = self.doctor(project, "opencode")
        self.assertNotIn("opencode-xdg-config-ignored", self.warning_codes(matching_payload["opencode"]))

    def test_global_pi_install_honors_pi_coding_agent_dir(self) -> None:
        home = Path(self.env["HOME"])
        project = self.root / "pi project"
        project.mkdir()
        for configured, folder in (
            (str(self.root / "pi agent dir ü"), self.root / "pi agent dir ü"),
            ("~/custom pi ü", home / "custom pi ü"),
        ):
            with self.subTest(PI_CODING_AGENT_DIR=configured):
                self.env["PI_CODING_AGENT_DIR"] = configured
                rules = folder / "AGENTS.md"

                installed = self.run_core(
                    "install", "--agent", "pi", "--global", "--profile", "software-dev", "--with-skills",
                )

                self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
                self.assertIn("installed for pi", installed.stdout)
                self.assertIn("<!-- BEGIN AGENTSMITH", rules.read_text(encoding="utf-8"))
                self.assertFalse((home / ".pi").exists())
                # Pi reads user Agent Skills from HOME, not from its agent folder.
                self.assertTrue((home / ".agents" / "skills" / "handoff" / "SKILL.md").is_file())
                self.assertFalse((folder / ".agents").exists())
                strict = self.run_core("doctor", "--agent", "pi", "--target", str(project), "--strict", "--json")
                self.assertEqual(strict.returncode, 0, strict.stdout + strict.stderr)
                source = json.loads(strict.stdout)["pi"]["instructions"]["sources"][0]
                self.assertEqual(Path(source["path"]), rules.resolve())
                self.assertEqual((source["scope"], source["managed_status"]), ("global", "managed"))

                removed = self.run_core("install", "--agent", "pi", "--global", "--uninstall")

                self.assertEqual(removed.returncode, 0, removed.stdout + removed.stderr)
                self.assertFalse(rules.exists())

    def test_global_pi_uninstall_refuses_another_installations_rules(self) -> None:
        codex_rules = Path(self.env["CODEX_HOME"]) / "AGENTS.md"
        project = self.root / "project rules"
        installed = self.install(project, "--agent", "codex", "--profile", "software-dev")
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        self.env["PI_CODING_AGENT_DIR"] = str(self.root / "own pi agent")
        both = self.run_core("install", "--agent", "codex,pi", "--global", "--profile", "software-dev")
        self.assertEqual(both.returncode, 0, both.stdout + both.stderr)
        for label, pi_dir, protected, reason in (
            ("Codex's folder", Path(self.env["CODEX_HOME"]), codex_rules, "same instruction file"),
            ("a project installation", project, project / "AGENTS.md", "project installation"),
        ):
            with self.subTest(label):
                before = protected.read_bytes()
                self.env["PI_CODING_AGENT_DIR"] = str(pi_dir)

                removed = self.run_core("install", "--agent", "pi", "--global", "--uninstall")

                self.assertNotEqual(removed.returncode, 0, removed.stdout + removed.stderr)
                self.assertIn(reason, removed.stderr)
                self.assertEqual(protected.read_bytes(), before)
        self.assertTrue((self.root / "own pi agent" / "AGENTS.md").is_file())

    def test_global_pi_uninstall_leaves_rules_the_global_record_does_not_list(self) -> None:
        self.env["PI_CODING_AGENT_DIR"] = str(self.root / "unrecorded pi agent")
        rules = self.root / "unrecorded pi agent" / "AGENTS.md"
        with_pi = self.run_core("install", "--agent", "pi", "--global", "--profile", "software-dev")
        self.assertEqual(with_pi.returncode, 0, with_pi.stdout + with_pi.stderr)
        # Each global install replaces the recorded selection.
        codex_only = self.run_core("install", "--agent", "codex", "--global", "--profile", "software-dev")
        self.assertEqual(codex_only.returncode, 0, codex_only.stdout + codex_only.stderr)
        before = rules.read_bytes()

        removed = self.run_core("install", "--agent", "all", "--global", "--uninstall")

        self.assertEqual(removed.returncode, 0, removed.stdout + removed.stderr)
        self.assertIn("does not list pi", removed.stderr)
        self.assertEqual(rules.read_bytes(), before)
        self.assertFalse((Path(self.env["CODEX_HOME"]) / "AGENTS.md").exists())

    def test_opencode_with_claude_reports_duplicate_skill_discovery(self) -> None:
        project = self.root / "skill discovery project"
        project.mkdir()
        alone = self.run_core("install", "--agent", "opencode", "--global", "--with-skills")
        self.assertEqual(alone.returncode, 0, alone.stdout + alone.stderr)
        _, alone_payload = self.doctor(project, "opencode")
        self.assertNotIn("duplicate-skill-discovery", self.warning_codes(alone_payload["opencode"]))

        both = self.run_core("install", "--agent", "claude,opencode", "--global", "--with-skills")
        self.assertEqual(both.returncode, 0, both.stdout + both.stderr)
        strict = self.run_core("doctor", "--agent", "opencode", "--target", str(project), "--strict", "--json")
        self.assertEqual(strict.returncode, 0, strict.stdout + strict.stderr)
        warning = next(
            warning for warning in json.loads(strict.stdout)["opencode"]["warnings"]
            if warning["code"] == "duplicate-skill-discovery"
        )
        self.assertIn("handoff", warning["message"])
        self.assertIn("OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1", warning["recommendation"])
        _, claude_payload = self.doctor(project, "claude")
        self.assertNotIn("duplicate-skill-discovery", self.warning_codes(claude_payload["claude"]))

        self.env["OPENCODE_DISABLE_CLAUDE_CODE_SKILLS"] = "1"
        _, disabled_payload = self.doctor(project, "opencode")
        self.assertNotIn("duplicate-skill-discovery", self.warning_codes(disabled_payload["opencode"]))

    def test_skill_install_refuses_symlinked_adapter_root_before_external_writes(self) -> None:
        project = self.root / "symlinked adapter project"
        project.mkdir()
        external = self.root / "external skills"
        external.mkdir()
        (project / ".claude").mkdir()
        try:
            (project / ".claude" / "skills").symlink_to(external, target_is_directory=True)
        except (NotImplementedError, OSError) as exc:
            self.skipTest(f"symbolic links are unavailable: {exc}")

        installed = self.run_core(
            "install", "--agent", "claude", "--profile", "software-dev", "--target", str(project),
            "--with-skills",
        )

        self.assertNotEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        self.assertIn("symbolic link", installed.stderr)
        self.assertEqual(list(external.iterdir()), [])

    def test_strict_doctor_detects_adapter_only_symlink_drift(self) -> None:
        project = self.root / "adapter symlink drift"
        installed = self.install(
            project, "--agent", "claude", "--profile", "software-dev", "--with-skills"
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        adapter = project / ".claude" / "skills" / "handoff"
        try:
            (adapter / "extra-link.md").symlink_to("SKILL.md")
        except (NotImplementedError, OSError) as exc:
            self.skipTest(f"symbolic links are unavailable: {exc}")

        strict = self.run_core(
            "doctor", "--agent", "claude", "--target", str(project), "--strict", "--json"
        )

        self.assertNotEqual(strict.returncode, 0, strict.stdout + strict.stderr)
        skills = json.loads(strict.stdout)["claude"]["skills"]
        self.assertEqual(skills["adapter_diverged_names"], ["handoff"])



class HookFiringLogTests(unittest.TestCase):
    """Every shipped hook records when it acts, so doctor can name hooks that stopped firing."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="agentsmith hook log ")
        self.root = Path(self.temporary.name)
        self.env = os.environ.copy()
        home = self.root / "home"
        self.env.update({"HOME": str(home), "USERPROFILE": str(home), "CODEX_HOME": str(home / ".codex")})
        for name in ("PI_CODING_AGENT_DIR", "XDG_CONFIG_HOME", "HANDOFF_PCT_THRESHOLD"):
            self.env.pop(name, None)
        self.project = self.root / "project"
        self.project.mkdir()
        installed = subprocess.run(
            [sys.executable, str(CORE), "install", "--agent", "claude", "--target", str(self.project),
             "--profile", "software-dev", "--with-handoff-hooks"],
            cwd=ROOT, env=self.env, text=True, capture_output=True, check=False,
        )
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        self.runtime = self.project / ".agentsmith" / "agentsmith.py"
        self.log = self.project / ".agentsmith" / "logs" / "hook-events.jsonl"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def hook(self, name: str, payload: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.runtime), "hook", name], input=payload, cwd=self.project,
            env=self.env, text=True, capture_output=True, check=False,
        )

    def events(self) -> list[dict]:
        if not self.log.is_file():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def test_a_firing_hook_appends_one_line_without_prompt_text(self) -> None:
        quiet = self.hook("handoff-on-keyword", json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": "hello"}))
        self.assertEqual(quiet.returncode, 0)
        self.assertEqual(self.events(), [], "a hook that did nothing must not log")
        secret_prompt = "please wrap up now, token sk-do-not-log"
        fired = self.hook("handoff-on-keyword", json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": secret_prompt}))
        self.assertEqual(fired.returncode, 0)
        self.assertIn("agentsmith handoff", fired.stdout)
        [event] = self.events()
        self.assertEqual(set(event), {"ts", "hook", "event", "outcome"})
        self.assertEqual((event["hook"], event["event"], event["outcome"]), ("handoff-on-keyword", "UserPromptSubmit", "nudged"))
        self.assertNotIn("wrap up", self.log.read_text(encoding="utf-8"))
        self.assertNotIn("sk-do-not-log", self.log.read_text(encoding="utf-8"))
        # The log folder ignores itself, so a committed .agentsmith/ runtime stays clean in Git.
        self.assertEqual((self.log.parent / ".gitignore").read_text(encoding="utf-8"), "*\n")

    def test_logging_failure_never_breaks_the_hook(self) -> None:
        self.log.mkdir(parents=True)
        fired = self.hook("ui-design-reminder", json.dumps({"hook_event_name": "PreToolUse", "file_path": "a.tsx"}))
        self.assertEqual(fired.returncode, 0, fired.stderr)
        self.assertIn("DESIGN.md", fired.stdout)
        self.assertEqual(fired.stderr, "")

    def test_log_stays_bounded(self) -> None:
        line = json.dumps({"ts": "2026-01-01T00:00:00Z", "hook": "ui-design-reminder", "event": "PreToolUse", "outcome": "nudged"})
        self.log.parent.mkdir(parents=True)
        self.log.write_text((line + "\n") * 4000, encoding="utf-8")
        self.hook("ui-design-reminder", json.dumps({"hook_event_name": "PreToolUse", "file_path": "a.css"}))
        core = load_core()
        self.assertLessEqual(self.log.stat().st_size, core.HOOK_LOG_MAX_BYTES)
        events = self.events()
        self.assertEqual(events[-1]["hook"], "ui-design-reminder")
        self.assertNotEqual(events[-1]["ts"], "2026-01-01T00:00:00Z")

    def test_doctor_counts_firings_and_names_hooks_unused_for_30_days(self) -> None:
        old = "2026-01-01T00:00:00Z"
        recent = dt_now_iso()
        self.log.parent.mkdir(parents=True)
        self.log.write_text(
            json.dumps({"ts": old, "hook": "context-budget-nudge", "event": "Stop", "outcome": "blocked"}) + "\n"
            + json.dumps({"ts": recent, "hook": "handoff-on-keyword", "event": "UserPromptSubmit", "outcome": "nudged"}) + "\n",
            encoding="utf-8",
        )
        # Pretend the install is older than the window, so silence means the hook is not firing.
        state = self.project / ".agentsmith" / "state.json"
        os.utime(state, (0, 0))
        result = subprocess.run(
            [sys.executable, str(CORE), "doctor", "--agent", "claude", "--target", str(self.project), "--json"],
            cwd=ROOT, env=self.env, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        firings = json.loads(result.stdout)["claude"]["hook_firings"]
        self.assertEqual(firings["window_days"], 30)
        self.assertEqual(firings["counts"], {"handoff-on-keyword": 1})
        self.assertEqual(firings["unused"], ["context-budget-nudge"])
        codes = {warning["code"] for warning in json.loads(result.stdout)["claude"]["warnings"]}
        self.assertIn("hook-unused-30-days", codes)
        text = subprocess.run(
            [sys.executable, str(CORE), "doctor", "--agent", "claude", "--target", str(self.project)],
            cwd=ROOT, env=self.env, text=True, capture_output=True, check=False,
        ).stdout
        self.assertIn("hook firings (30 days): handoff-on-keyword=1", text)

    @unittest.skipIf(os.name == "nt" or not shutil.which("bash") or not shutil.which("git"), "POSIX Git hook")
    def test_shell_git_hook_records_a_block(self) -> None:
        subprocess.run(["git", "-C", str(self.project), "init", "-q", "-b", "master"], check=True)
        subprocess.run(["git", "-C", str(self.project), "-c", "user.name=Test", "-c", "user.email=test@example.com",
                        "commit", "-q", "--allow-empty", "--no-verify", "-m", "chore: start"], check=True)
        blocked = subprocess.run(
            ["bash", str(ROOT / "hooks" / "git" / "protect-main.sh")], cwd=self.project,
            env=self.env, text=True, capture_output=True, check=False,
        )
        self.assertEqual(blocked.returncode, 1)
        [event] = self.events()
        self.assertEqual((event["hook"], event["event"], event["outcome"]), ("protect-main", "pre-commit", "blocked"))
        message = self.root / "message"
        message.write_text("bad subject\n", encoding="utf-8")
        subprocess.run(["bash", str(ROOT / "hooks" / "git" / "conventional-commit.sh"), str(message)],
                       cwd=self.project, env=self.env, capture_output=True, check=False)
        self.assertEqual([item["hook"] for item in self.events()], ["protect-main", "conventional-commit"])


def dt_now_iso() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_core():
    import importlib.util
    spec = importlib.util.spec_from_file_location("agentsmith_doctor_core", CORE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ContainerDetectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.core = load_core()
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "proc" / "1").mkdir(parents=True)
        (self.root / "run").mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def detect(self, environ: dict[str, str] | None = None, system: str = "Linux") -> list[str]:
        return self.core.detect_container(root=self.root, environ=environ or {}, system=system)

    def test_plain_linux_host_is_not_a_container(self) -> None:
        (self.root / "proc" / "1" / "cgroup").write_text("0::/init.scope\n", encoding="utf-8")
        self.assertEqual(self.detect(), [])

    def test_each_container_signal_is_reported_as_evidence(self) -> None:
        (self.root / ".dockerenv").write_text("", encoding="utf-8")
        self.assertEqual(self.detect(), ["/.dockerenv"])
        (self.root / ".dockerenv").unlink()
        (self.root / "run" / ".containerenv").write_text("", encoding="utf-8")
        self.assertEqual(self.detect(), ["/run/.containerenv"])
        (self.root / "run" / ".containerenv").unlink()
        self.assertEqual(self.detect({"container": "podman"}), ["container=podman"])
        self.assertEqual(self.detect({"KUBERNETES_SERVICE_HOST": "10.0.0.1"}), ["KUBERNETES_SERVICE_HOST"])
        (self.root / "proc" / "1" / "cgroup").write_text("0::/system.slice/docker-1a2b.scope\n", encoding="utf-8")
        self.assertEqual(self.detect(), ["/proc/1/cgroup: docker"])

    def test_other_systems_never_report_a_container(self) -> None:
        (self.root / ".dockerenv").write_text("", encoding="utf-8")
        self.assertEqual(self.detect({"container": "docker"}, system="Darwin"), [])
        self.assertEqual(self.detect({"container": "docker"}, system="Windows"), [])


class SafetyInspectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.core = load_core()
        self.temporary = tempfile.TemporaryDirectory()
        self.home = Path(self.temporary.name)
        self.environment = unittest.mock.patch.dict(
            os.environ, {"HOME": str(self.home), "USERPROFILE": str(self.home), "CODEX_HOME": str(self.home / "codex")}
        )
        self.environment.start()

    def tearDown(self) -> None:
        self.environment.stop()
        self.temporary.cleanup()

    def test_shared_claude_mode_follows_the_recorded_safety(self) -> None:
        # Claude uses acceptEdits for cautious and container alike; only the record can tell them apart.
        settings = self.home / ".claude" / "settings.json"
        settings.parent.mkdir()
        settings.write_text(json.dumps({"permissions": {"defaultMode": "acceptEdits"}}), encoding="utf-8")
        self.assertEqual(self.core.inspect_safety("claude")["state"], "cautious")
        self.assertEqual(self.core.inspect_safety("claude", expected="container")["state"], "container")
        self.assertEqual(self.core.inspect_safety("claude", expected="trusted")["state"], "cautious")

    def test_codex_container_pair_is_recognized(self) -> None:
        config = self.home / "codex" / "config.toml"
        config.parent.mkdir()
        config.write_text('approval_policy = "on-request"\nsandbox_mode = "danger-full-access"\n', encoding="utf-8")
        self.assertEqual(self.core.inspect_safety("codex")["state"], "container")

    def test_cautious_codex_in_a_container_gets_an_advisory(self) -> None:
        advisory = self.core.container_safety_advisory
        self.assertEqual(advisory("codex", "cautious", ["/.dockerenv"])["code"], "codex-cautious-in-container")
        self.assertIsNone(advisory("codex", "cautious", []))
        for agent_id, state in (("codex", "container"), ("codex", "trusted"), ("claude", "cautious")):
            self.assertIsNone(advisory(agent_id, state, ["/.dockerenv"]), (agent_id, state))

    def test_doctor_runs_without_git(self) -> None:
        # Slim container images often ship without Git; doctor must still run there, or the advisory never shows.
        target = self.home / "project"
        target.mkdir()
        real_which, real_run = self.core.shutil.which, self.core.subprocess.run

        def run_without_git(command, *rest, **kw):
            if command and command[0] == "git":
                raise FileNotFoundError(2, "No such file or directory", "git")
            return real_run(command, *rest, **kw)

        # A missing Git is both absent from PATH and impossible to start.
        no_git_on_path = unittest.mock.patch.object(
            self.core.shutil, "which", side_effect=lambda name, *rest, **kw: None if name == "git" else real_which(name, *rest, **kw)
        )
        git_cannot_start = unittest.mock.patch.object(self.core.subprocess, "run", side_effect=run_without_git)
        args = self.core.parser().parse_args(["doctor", "--agent", "codex", "--target", str(target), "--json"])
        with no_git_on_path, git_cannot_start, \
                unittest.mock.patch("sys.stdout", new_callable=lambda: __import__("io").StringIO()) as output:
            self.core.cmd_doctor(args)
            self.assertEqual(self.core.doctor_project_root(target), target.resolve())
        self.assertIn("codex", json.loads(output.getvalue()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
