#!/usr/bin/env python3
"""Contracts for the beginner-facing installation experience."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("agentsmith", ROOT / "agentsmith.py")
assert SPEC and SPEC.loader
agentsmith = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(agentsmith)
WIZARD_GOLDEN = ROOT / "tests" / "fixtures" / "wizard" / "interactive-golden.json"
WIZARD_SCENARIOS = {
    "new-project": ["en", "new", "<TARGET>/fresh", "codex", "1", "2", "", "", "yes"],
    "existing-all-and-reprompt": ["", "", "", "claude", "all", "general-admin", "2", "invalid", "", "", "yes"],
    "advanced-user-scope": ["en", "existing", "<TARGET>", "github-copilot", "recommended", "3", "trusted",
                            "y", "user", "deep-research", "skills,hooks", "yes"],
}


def record_wizard_scenario(name: str) -> dict:
    """Run one scripted interactive wizard and return its prompts, output and resulting choices."""
    import contextlib
    import io
    with tempfile.TemporaryDirectory() as temporary:
        target = Path(temporary).resolve()
        answers = iter(value.replace("<TARGET>", str(target)) for value in WIZARD_SCENARIOS[name])
        prompts: list[str] = []
        args = agentsmith.parser().parse_args(["install", "--wizard", "--lang", "en"])
        output = io.StringIO()
        previous = Path.cwd()
        os.chdir(target)
        try:
            with mock.patch.object(agentsmith.shutil, "which", return_value=None), \
                    contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                plan = agentsmith.apply_wizard_answers(args, lambda prompt: (prompts.append(prompt), next(answers))[1])
        finally:
            os.chdir(previous)
        fields = ("agent", "profile", "target", "global_mode", "operator_bio", "safety", "initialize_git",
                  "wizard_language", "with_skills", "with_mcp", "with_hooks", "with_handoff_hooks",
                  "with_ui_design_hook", "with_memory_startup")
        result = {"prompts": prompts, "output": output.getvalue(), "plan": plan,
                  "args": {field: getattr(args, field, None) for field in fields}}

        def anonymize(value):
            # Replace on the data, not on JSON text, so Windows backslashes match too.
            if isinstance(value, str):
                return value.replace(str(target), "<TARGET>")
            if isinstance(value, list):
                return [anonymize(item) for item in value]
            if isinstance(value, dict):
                return {key: anonymize(item) for key, item in value.items()}
            return value
        return anonymize(json.loads(json.dumps(result)))


class GuidedInstallContracts(unittest.TestCase):
    def test_profile_catalog_is_structured_and_complete(self) -> None:
        catalog = agentsmith.profile_catalog()
        profile_files = {path.stem for path in (ROOT / "profiles").glob("*.md")}
        self.assertEqual({item["name"] for item in catalog}, profile_files)
        for item in catalog:
            self.assertIn(item["kind"], {"primary", "modifier"})
            self.assertTrue(item["examples"])
            self.assertTrue(item["verification_focus"])
        autonomous = next(item for item in catalog if item["name"] == "autonomous-loops")
        self.assertEqual(autonomous["kind"], "modifier")

    def test_new_project_wizard_defers_writes_and_sets_safe_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "new-project"
            answers = iter([
                "en",       # language
                "new",      # project kind
                str(target), # project path
                "codex",    # agent
                "1",        # software development goal
                "2",        # experienced developer, new to AI agents
                "",         # keep cautious safety
                "",         # skip advanced options
                "yes",      # confirm
            ])
            args = argparse.Namespace(
                agent=None, profile=None, target=None, global_mode=False,
                profile_only=False, safety="cautious", with_skills=False,
                with_mcp=None, with_hooks=False, with_handoff_hooks=False,
                with_ui_design_hook=False, operator_name=None, operator_role=None,
                operator_bio=None, tracker=None, tracker_writes=None,
                design_system=None, dry_run=False, wizard=True,
            )
            plan = agentsmith.apply_wizard_answers(args, lambda _prompt: next(answers))
            self.assertFalse(target.exists(), "the wizard must not write before install applies")
            self.assertTrue(plan["confirmed"])
            self.assertEqual(Path(args.target), target.resolve())
            self.assertEqual(args.profile, ["software-dev"])
            self.assertEqual(args.agent, ["codex"])
            self.assertEqual(args.safety, "cautious")
            self.assertTrue(args.initialize_git)
            self.assertIn("daily Git", args.operator_bio)

    def test_wizard_without_terminal_fails_before_output(self) -> None:
        # A script that pipes stdin must not read "exit 0" as a finished install.
        for argv in ([], ["install", "--wizard"]):
            with self.subTest(argv=argv), tempfile.TemporaryDirectory() as temporary:
                home = Path(temporary) / "home"
                project = Path(temporary) / "project"
                home.mkdir()
                project.mkdir()
                environment = {**os.environ, "HOME": str(home), "USERPROFILE": str(home),
                               "CODEX_HOME": str(home / ".codex")}
                result = subprocess.run(
                    [sys.executable, str(ROOT / "agentsmith.py"), *argv],
                    cwd=project, env=environment, stdin=subprocess.DEVNULL,
                    capture_output=True, text=True, timeout=60,
                )
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertIn("--agent", result.stderr)
                self.assertIn("--profile", result.stderr)
                self.assertEqual(list(home.iterdir()), [])
                self.assertEqual(list(project.iterdir()), [])

    def test_interactive_prompt_sequence_is_stable(self) -> None:
        # Pins the interactive wizard while the answers file and schema share its question table.
        golden = json.loads(WIZARD_GOLDEN.read_text(encoding="utf-8"))
        self.assertEqual(set(golden), set(WIZARD_SCENARIOS))
        for name in WIZARD_SCENARIOS:
            with self.subTest(scenario=name):
                self.assertEqual(record_wizard_scenario(name), golden[name])

    def test_existing_project_recommendation_uses_repository_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            (target / "pyproject.toml").write_text("[project]\nname='sample'\n", encoding="utf-8")
            recommendation = agentsmith.wizard_profile_recommendation(target)
            self.assertEqual(recommendation["profile"], "software-dev")
            self.assertTrue(any("pyproject.toml" in item for item in recommendation["evidence"]))

    def test_new_project_plan_applies_end_to_end_after_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            target = Path(temporary) / "new-project"
            home.mkdir()
            answers = iter(["en", "new", str(target), "github-copilot", "1", "2", "", "", "yes"])
            args = agentsmith.parser().parse_args(["install", "--wizard"])
            with mock.patch.dict(agentsmith.os.environ, {"HOME": str(home)}):
                agentsmith.apply_wizard_answers(args, lambda _prompt: next(answers))
                self.assertEqual(agentsmith.cmd_install(args), 0)
            self.assertTrue((target / ".git").is_dir())
            self.assertIn("Profile: Software Development", (target / "AGENTS.md").read_text(encoding="utf-8"))
            state = json.loads((target / ".agentsmith" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["installation"]["profiles"], ["software-dev"])
            self.assertEqual(state["installation"]["runtime"]["mode"], "project-python")

    def test_all_wizard_locales_have_the_english_message_keys(self) -> None:
        locales = json.loads((ROOT / "config" / "wizard-locales.json").read_text(encoding="utf-8"))
        self.assertEqual(set(locales), {"en", "de", "es", "fr", "zh-CN"})
        keys = set(locales["en"])
        self.assertGreater(len(keys), 15)
        for language, messages in locales.items():
            self.assertEqual(set(messages), keys, language)

    def test_readme_translations_and_footer_link_are_present(self) -> None:
        names = ("README.md", "README.de.md", "README.es.md", "README.fr.md", "README.zh-CN.md")
        for name in names:
            text = (ROOT / name).read_text(encoding="utf-8")
            for other in names:
                if other != name:
                    self.assertIn(other, text)
        site = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        self.assertRegex(
            site,
            r'<a href="https://promptpartner\.ai/" target="_blank" rel="noopener noreferrer">promptpartner\.ai</a>',
        )

    def test_frozen_cli_remains_central_instead_of_copying_python_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / "agentsmith"
            binary.write_bytes(b"standalone")
            target = Path(temporary) / "project"
            with mock.patch.object(agentsmith.sys, "frozen", True, create=True), mock.patch.object(
                agentsmith.sys, "executable", str(binary)
            ):
                runtime = agentsmith.copy_runtime(target, dry_run=False)
                args = agentsmith.parser().parse_args([
                    "install", "--agent", "github-copilot", "--profile", "software-dev", "--target", str(target)
                ])
                target.mkdir()
                agentsmith.record_installation_manifest(
                    target, ["github-copilot"], ["software-dev"], args, {}, []
                )
            self.assertEqual(runtime, binary.resolve())
            self.assertFalse((target / ".agentsmith" / "agentsmith.py").exists())
            state_text = (target / ".agentsmith" / "state.json").read_text(encoding="utf-8")
            state = json.loads(state_text)
            self.assertEqual(state["installation"]["runtime"]["path"], "agentsmith")
            self.assertNotIn(str(Path(temporary)), state_text)

    def test_guided_install_contracts_run_in_ci_and_the_compile_gate(self) -> None:
        # These contracts only ran locally, so a wizard regression could merge with green CI.
        workflow = (ROOT / ".github" / "workflows" / "verify.yml").read_text(encoding="utf-8")
        compile_step = next(line for line in workflow.splitlines() if "python -m py_compile" in line)
        self.assertIn("scripts/test-guided-install.py", compile_step)
        self.assertIn("run: python scripts/test-guided-install.py", workflow)
        gate = (ROOT / ".harness" / "verify.conf").read_text(encoding="utf-8")
        python_core = next(line for line in gate.splitlines() if line.startswith("python-core ::"))
        self.assertIn("scripts/test-guided-install.py", python_core)

    def test_docs_describe_only_questions_the_wizard_asks(self) -> None:
        # The wizard asks no tracker or UI question; docs that say so send users looking for it.
        stale = {
            "docs/14-project-tracker-guide.md": "The wizard asks this right after",
            "docs/11-designing-uis.md": "Does this project have a UI?",
            "hooks/README.md": "tell the wizard the project has a UI",
        }
        for name, phrase in stale.items():
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertFalse(phrase in text, f"{name} still says: {phrase}")
        install = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
        self.assertIn("needs an interactive terminal", install)
        troubleshooting = (ROOT / "docs" / "17-troubleshooting.md").read_text(encoding="utf-8")
        self.assertIn("needs an interactive terminal", troubleshooting)

    def test_standalone_build_covers_the_four_initial_targets(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "standalone.yml").read_text(encoding="utf-8")
        for value in ("ubuntu-24.04", "windows-2025", "macos-15", "macos-15-intel"):
            self.assertIn(value, workflow)
        spec = (ROOT / "agentsmith.spec").read_text(encoding="utf-8")
        for data_root in ("core", "profiles", "config", "templates", "skills"):
            self.assertIn(f"'{data_root}'", spec)


if __name__ == "__main__":
    unittest.main()
