#!/usr/bin/env python3
"""Contracts for the beginner-facing installation experience."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
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


def record_wizard_scenario(name: str, container: list[str] | None = None) -> dict:
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
                    mock.patch.object(agentsmith, "detect_container", return_value=container or []), \
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
                value = value.replace(str(target), "<TARGET>")
                return value.replace("\\", "/") if "<TARGET>" in value else value
            if isinstance(value, list):
                return [anonymize(item) for item in value]
            if isinstance(value, dict):
                return {key: anonymize(item) for key, item in value.items()}
            return value
        return anonymize(json.loads(json.dumps(result)))

STANDALONE_WORKFLOW = ROOT / ".github" / "workflows" / "standalone.yml"
RELEASE_ASSETS = (
    "agentsmith-linux-x86_64",
    "agentsmith-linux-arm64",
    "agentsmith-windows-x86_64",
    "agentsmith-macos-arm64",
    "agentsmith-macos-x86_64",
)


def standalone_jobs() -> dict[str, str]:
    """Split the standalone workflow into job bodies without adding a YAML dependency."""
    body = STANDALONE_WORKFLOW.read_text(encoding="utf-8").split("\njobs:\n", 1)[1]
    parts = re.split(r"^  ([A-Za-z0-9_-]+):\n", body, flags=re.M)
    return dict(zip(parts[1::2], parts[2::2]))


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
            # Pin detection off: inside a container the wizard rightly defaults to container safety.
            with mock.patch.object(agentsmith, "detect_container", return_value=[]):
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

    def test_wizard_schema_is_versioned_and_complete(self) -> None:
        # A host product renders these questions itself, so the schema must match the wizard.
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            (target / "pyproject.toml").write_text("[project]\nname='sample'\n", encoding="utf-8")
            args = agentsmith.parser().parse_args(["wizard", "schema", "--json", "--target", str(target)])
            schema = agentsmith.wizard_schema(args)
        self.assertEqual(schema["schema_version"], 1)
        self.assertEqual(schema["agentsmith_version"], agentsmith.VERSION)
        self.assertEqual([item["key"] for item in schema["questions"]],
                         [item["key"] for item in agentsmith.WIZARD_QUESTIONS])
        self.assertEqual(set(schema["messages"]), set(agentsmith.WIZARD_LANGUAGES))
        for item in schema["questions"]:
            self.assertIn(item["prompt_key"], schema["messages"]["en"], item["key"])
        questions = {item["key"]: item for item in schema["questions"]}
        self.assertEqual(questions["language"]["default"]["computed"], "locale_environment")
        self.assertEqual(questions["agent"]["default"]["computed"], "agent_detection")
        self.assertIsInstance(questions["agent"]["default"]["value"], list)
        self.assertIn("native", questions["agent"]["choices"])
        self.assertTrue(questions["target"]["required_in_answers"])
        self.assertEqual(questions["goal"]["when"], {"project_kind": "new"})
        self.assertEqual(questions["goal"]["profiles"]["1"], "software-dev")
        self.assertEqual(questions["profile"]["default"]["resolved"], "software-dev")
        self.assertTrue(any("pyproject.toml" in item for item in questions["profile"]["default"]["evidence"]))
        self.assertIn("recommended", questions["profile"]["choices"])
        self.assertEqual(questions["capabilities"]["choices"], list(agentsmith.WIZARD_CAPABILITIES))

    def test_wizard_schema_cli_prints_only_json_and_skips_the_update_check(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            state = home / ".agentsmith" / "state.json"
            state.parent.mkdir()
            # A due weekly update check would print to stdout and record an attempt.
            state.write_text(json.dumps({"update_policy": {"auto_check": "weekly"}}), encoding="utf-8")
            before = state.read_text(encoding="utf-8")
            environment = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
            result = subprocess.run(
                [sys.executable, str(ROOT / "agentsmith.py"), "wizard", "schema", "--json"],
                env=environment, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["schema_version"], 1)
            self.assertEqual(state.read_text(encoding="utf-8"), before)

    def test_answers_match_interactive_plan(self) -> None:
        # The answers file must produce exactly what the same answers produce interactively.
        cases = {
            "new-project": {"language": "en", "project_kind": "new", "target": "<TARGET>/fresh",
                            "agent": ["codex"], "goal": "1", "experience": "2", "confirm": "yes"},
            "advanced-user-scope": {"language": "en", "project_kind": "existing", "target": "<TARGET>",
                                    "agent": ["github-copilot"], "profile": "recommended", "experience": "3",
                                    "safety": "trusted", "advanced": "y", "scope": "user",
                                    "extra_profiles": ["deep-research"], "capabilities": ["skills", "hooks"],
                                    "confirm": "yes"},
        }
        golden = json.loads(WIZARD_GOLDEN.read_text(encoding="utf-8"))
        for name, answers in cases.items():
            with self.subTest(scenario=name), tempfile.TemporaryDirectory() as temporary:
                target = Path(temporary).resolve()
                document = {"schema_version": 1,
                            **{key: value.replace("<TARGET>", str(target)) if isinstance(value, str) else value
                               for key, value in answers.items()}}
                answers_file = target / "answers.json"
                answers_file.write_text(json.dumps(document), encoding="utf-8")
                args = agentsmith.parser().parse_args(["install", "--answers", str(answers_file)])
                with mock.patch.object(agentsmith.shutil, "which", return_value=None), \
                        mock.patch.object(agentsmith, "detect_container", return_value=[]), \
                        mock.patch("sys.stdout", new_callable=lambda: __import__("io").StringIO()):
                    agentsmith.apply_wizard_answers_file(args)
                expected = golden[name]["args"]
                for field, value in expected.items():
                    actual = getattr(args, field, None)
                    if isinstance(actual, str):
                        actual = actual.replace(str(target), "<TARGET>")
                        actual = actual.replace("\\", "/") if "<TARGET>" in actual else actual
                    self.assertEqual(actual, value, field)

    def test_wizard_output_survives_a_legacy_windows_pipe(self) -> None:
        # A Windows pipe encodes stdout as cp1252, which cannot hold the zh-CN strings.
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            home.mkdir()
            environment = {**os.environ, "HOME": str(home), "USERPROFILE": str(home),
                           "PYTHONIOENCODING": "cp1252"}
            schema = subprocess.run(
                [sys.executable, str(ROOT / "agentsmith.py"), "wizard", "schema", "--json"],
                env=environment, stdin=subprocess.DEVNULL, capture_output=True, timeout=60,
            )
            self.assertEqual(schema.returncode, 0, schema.stderr.decode("utf-8", "replace"))
            messages = json.loads(schema.stdout.decode("ascii"))["messages"]
            self.assertEqual(messages["zh-CN"]["language"], agentsmith.load_wizard_locales()["zh-CN"]["language"])
            answers_file = Path(temporary) / "answers.json"
            answers_file.write_text(json.dumps({
                "schema_version": 1, "language": "zh-CN", "project_kind": "new",
                "target": str(Path(temporary) / "fresh"), "agent": ["github-copilot"],
            }), encoding="utf-8")
            install = subprocess.run(
                [sys.executable, str(ROOT / "agentsmith.py"), "install", "--answers", str(answers_file), "--dry-run"],
                env=environment, stdin=subprocess.DEVNULL, capture_output=True, timeout=120,
            )
            self.assertEqual(install.returncode, 0, install.stderr.decode("utf-8", "replace"))

    def test_answers_errors_are_aggregated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            answers_file = Path(temporary) / "answers.json"
            answers_file.write_text(json.dumps({
                "schema_version": 2, "safty": "trusted", "safety": "reckless",
                "scope": "user", "experience": 2,
            }), encoding="utf-8")
            args = agentsmith.parser().parse_args(["install", "--answers", str(answers_file)])
            with self.assertRaises(agentsmith.CliError) as raised:
                agentsmith.apply_wizard_answers_file(args)
        message = str(raised.exception)
        for fragment in ("schema_version", "safty", "safety", "scope", "experience", "target", "confirm"):
            self.assertIn(fragment, message)

    def test_answers_install_without_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            home.mkdir()
            target = Path(temporary) / "fresh"
            answers_file = Path(temporary) / "answers.json"
            answers_file.write_text(json.dumps({
                "schema_version": 1, "project_kind": "new", "target": str(target),
                "agent": ["github-copilot"], "goal": "1", "confirm": "yes",
            }), encoding="utf-8")
            environment = {**os.environ, "HOME": str(home), "USERPROFILE": str(home),
                           "CODEX_HOME": str(home / ".codex")}

            def install(*extra: str) -> subprocess.CompletedProcess:
                return subprocess.run(
                    [sys.executable, str(ROOT / "agentsmith.py"), "install", "--answers", str(answers_file), *extra],
                    cwd=temporary, env=environment, stdin=subprocess.DEVNULL,
                    capture_output=True, text=True, timeout=120,
                )

            dry = install("--dry-run")
            self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)
            self.assertFalse(target.exists(), "a dry run must not create the project")
            both = install("--wizard")
            self.assertEqual(both.returncode, 2)
            self.assertIn("--answers", both.stderr)
            real = install()
            self.assertEqual(real.returncode, 0, real.stdout + real.stderr)
            self.assertTrue((target / ".git").is_dir())
            self.assertIn("Profile: Software Development", (target / "AGENTS.md").read_text(encoding="utf-8"))
    def test_wizard_input_that_ends_early_is_a_clean_refusal(self) -> None:
        # Windows reports the NUL device as a terminal, and a pipe can end mid-wizard; neither may crash.
        with mock.patch.object(agentsmith, "stdin_is_interactive", return_value=True), \
                mock.patch.object(agentsmith, "maybe_report_automatic_update"), \
                mock.patch.object(agentsmith, "apply_wizard_answers", side_effect=EOFError), \
                mock.patch("sys.stdout", new_callable=lambda: __import__("io").StringIO()):
            with self.assertRaises(agentsmith.CliError) as raised:
                agentsmith.run(["install", "--wizard"])
        self.assertIn("nothing was changed", str(raised.exception))

    def test_windows_console_check_does_not_trust_isatty_alone(self) -> None:
        # On Windows, NUL reports isatty() but is not a console; without a console API answer, assume no terminal.
        fake_stdin = mock.Mock()
        fake_stdin.isatty.return_value = True
        fake_stdin.fileno.return_value = 0
        with mock.patch.object(agentsmith.sys, "stdin", fake_stdin), mock.patch.object(agentsmith.os, "name", "nt"), \
                mock.patch.dict(sys.modules, {"msvcrt": None}):
            self.assertFalse(agentsmith.stdin_is_interactive())
        fake_stdin.isatty.return_value = False
        with mock.patch.object(agentsmith.sys, "stdin", fake_stdin):
            self.assertFalse(agentsmith.stdin_is_interactive())

    def test_wizard_offers_container_safety_only_inside_a_container(self) -> None:
        # Inside Docker, cautious Codex cannot start its sandbox; the wizard explains and defaults to container.
        inside = record_wizard_scenario("new-project", container=["/.dockerenv"])
        self.assertEqual(inside["args"]["safety"], "container")
        self.assertIn("Agent permissions [cautious/trusted/container] [container]: ", inside["prompts"])
        self.assertIn("/.dockerenv", inside["output"])
        outside = record_wizard_scenario("new-project")
        self.assertEqual(outside["args"]["safety"], "cautious")
        self.assertNotIn("container", " ".join(outside["prompts"]))

    def test_schema_and_answers_follow_the_container_rule(self) -> None:
        args = agentsmith.parser().parse_args(["wizard", "schema", "--json"])
        with mock.patch.object(agentsmith, "detect_container", return_value=[]):
            outside = {item["key"]: item for item in agentsmith.wizard_schema(args)["questions"]}
        with mock.patch.object(agentsmith, "detect_container", return_value=["/.dockerenv"]):
            inside = {item["key"]: item for item in agentsmith.wizard_schema(args)["questions"]}
        self.assertEqual(outside["safety"]["choices"], ["cautious", "trusted"])
        self.assertEqual(inside["safety"]["choices"], ["cautious", "trusted", "container"])
        self.assertEqual(inside["safety"]["default"]["value"], "container")
        self.assertEqual(inside["safety"]["evidence"], ["/.dockerenv"])
        with tempfile.TemporaryDirectory() as temporary:
            answers_file = Path(temporary) / "answers.json"
            answers_file.write_text(json.dumps({
                "schema_version": 1, "project_kind": "new", "target": str(Path(temporary) / "fresh"),
                "agent": ["codex"], "safety": "container", "confirm": "yes",
            }), encoding="utf-8")
            install = ["install", "--answers", str(answers_file)]
            with mock.patch.object(agentsmith, "detect_container", return_value=[]):
                with self.assertRaises(agentsmith.CliError) as refused:
                    agentsmith.apply_wizard_answers_file(agentsmith.parser().parse_args(install))
            self.assertIn("safety", str(refused.exception))
            args = agentsmith.parser().parse_args(install)
            with mock.patch.object(agentsmith, "detect_container", return_value=["/.dockerenv"]), \
                    mock.patch("sys.stdout", new_callable=lambda: __import__("io").StringIO()):
                agentsmith.apply_wizard_answers_file(args)
            self.assertEqual(args.safety, "container")

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

    def test_install_docs_explain_the_answers_file_and_schema(self) -> None:
        for name in ("INSTALL.md", "AGENT-INSTALL.md", "docs/12-whats-built-in.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            for phrase in ("--answers", "wizard schema --json"):
                self.assertTrue(phrase in text, f"{name} does not mention {phrase}")

    def test_safety_docs_point_to_a_section_that_exists(self) -> None:
        # Seven places pointed to README sections that do not exist; they now share one real section.
        broken = ("Permissions and trusted mode", "Permissions & dangerous mode")
        for path in [*ROOT.glob("*.md"), *(ROOT / "docs").glob("*.md"), *(ROOT / "templates").glob("*.md"),
                     *(ROOT / "config").glob("*.example")]:
            text = path.read_text(encoding="utf-8")
            for phrase in broken:
                self.assertFalse(phrase in text, f"{path.relative_to(ROOT)} still points to: {phrase}")
        model = (ROOT / "docs" / "15-safety-model.md").read_text(encoding="utf-8")
        self.assertIn("## Safety modes", model)
        for phrase in ("`container`", "--assemble-only", "danger-full-access"):
            self.assertIn(phrase, model)
        troubleshooting = (ROOT / "docs" / "17-troubleshooting.md").read_text(encoding="utf-8")
        self.assertIn("No permissions to create a new namespace", troubleshooting)
        help_text = " ".join(agentsmith.parser()._subparsers._group_actions[0].choices["install"].format_help().split())
        self.assertIn("container", help_text)
        self.assertIn("leave Claude and Codex permissions", help_text)

    def test_standalone_update_refusal_points_to_a_verified_release_download(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / "agentsmith"
            binary.write_bytes(b"standalone")
            target = Path(temporary) / "project"
            with mock.patch.object(agentsmith.sys, "frozen", True, create=True), mock.patch.object(
                agentsmith.sys, "executable", str(binary)
            ):
                args = agentsmith.parser().parse_args([
                    "install", "--agent", "github-copilot", "--profile", "software-dev", "--target", str(target)
                ])
                target.mkdir()
                agentsmith.record_installation_manifest(
                    target, ["github-copilot"], ["software-dev"], args, {}, []
                )
            with self.assertRaises(agentsmith.CliError) as raised:
                agentsmith.cmd_update_plan(argparse.Namespace(global_mode=False, target=str(target)))
        message = str(raised.exception)
        self.assertNotRegex(message, r"(?i)\bsigned\b")
        self.assertIn("SHA256SUMS", message)

    def test_release_download_guidance_matches_unsigned_checksummed_assets(self) -> None:
        guides = {name: (ROOT / name).read_text(encoding="utf-8") for name in ("INSTALL.md", "AGENT-INSTALL.md")}
        for name, text in guides.items():
            self.assertNotRegex(text, r"(?i)\bsigned\b|platform signature", name)
            self.assertIn("SHA256SUMS", text, name)
            self.assertIn("gh attestation verify", text, name)
        # `--repo` alone accepts any workflow run in the repository, including a manual branch build,
        # so every guide pins the release workflow and the release tag.
        guides["RELEASING.md"] = (ROOT / "RELEASING.md").read_text(encoding="utf-8")
        for name, text in guides.items():
            self.assertIn("--signer-workflow PromptPartner/agentsmith/.github/workflows/standalone.yml", text, name)
            self.assertIn("--source-ref refs/tags/", text, name)
        for asset in RELEASE_ASSETS:
            self.assertIn(asset, guides["INSTALL.md"])
        # (states the builds are unsigned, retired claim that they are signed)
        readmes = {
            "README.md": ("unsigned", "signed installer"),
            "README.de.md": ("nicht signiert", "signierte Installationsprogramm"),
            "README.es.md": ("no están firmad", "instalador firmado"),
            "README.fr.md": ("pas signés", "installation signé"),
            "README.zh-CN.md": ("未签名", "已签名安装程序"),
        }
        for name, (unsigned, retired) in readmes.items():
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn(unsigned, text, name)
            self.assertNotIn(retired, text, name)

    def test_standalone_build_covers_every_release_target(self) -> None:
        workflow = STANDALONE_WORKFLOW.read_text(encoding="utf-8")
        for value in ("ubuntu-24.04", "ubuntu-24.04-arm", "windows-2025", "macos-15", "macos-15-intel"):
            self.assertIn(f"os: {value}\n", workflow)
        for asset in RELEASE_ASSETS:
            self.assertIn(f"asset: {asset}\n", workflow)
        spec = (ROOT / "agentsmith.spec").read_text(encoding="utf-8")
        for data_root in ("core", "profiles", "config", "templates", "skills"):
            self.assertIn(f"'{data_root}'", spec)

    def test_checksums_cover_every_archive_on_every_run(self) -> None:
        checksums = standalone_jobs()["checksums"]
        header = checksums.split("steps:", 1)[0]
        self.assertIn("needs: build", header)
        self.assertNotIn("if:", header, "pull requests must exercise the checksum job too")
        self.assertIn("merge-multiple: true", checksums)
        self.assertIn(f'-eq {len(RELEASE_ASSETS)}', checksums)
        self.assertIn("sha256sum", checksums)
        self.assertIn("name: SHA256SUMS", checksums)
        attest = checksums.split("uses: actions/attest@", 1)
        self.assertEqual(len(attest), 2, "SHA256SUMS needs a build attestation")
        self.assertIn("if: github.event_name != 'pull_request'", attest[0].rsplit("- name:", 1)[1])
        self.assertIn("subject-path: release-assets/SHA256SUMS", attest[1])

    def test_release_job_drafts_only_for_a_tag_that_matches_the_cli_version(self) -> None:
        workflow = STANDALONE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("tags: ['v*']", workflow)
        release = standalone_jobs()["release"]
        header = release.split("steps:", 1)[0]
        self.assertIn("needs: checksums", header)
        self.assertIn("if: startsWith(github.ref, 'refs/tags/v')", header)
        source = (ROOT / "agentsmith.py").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r'^VERSION = "([^"]+)"$', source, re.M), [agentsmith.VERSION])
        self.assertIn('^VERSION = "', release)
        self.assertIn('"v${version}"', release)
        self.assertIn("sha256sum -c SHA256SUMS", release)
        create = release.index("gh release create")
        self.assertLess(release.index('"v${version}"'), create)
        self.assertLess(release.index("sha256sum -c SHA256SUMS"), create)
        self.assertIn("--draft", release[create:])
        self.assertIn("--verify-tag", release[create:])

    def test_only_the_release_job_can_write_repository_contents(self) -> None:
        workflow = STANDALONE_WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("contents: write", workflow.split("\njobs:\n", 1)[0])
        jobs = standalone_jobs()
        self.assertEqual(set(jobs), {"build", "checksums", "release"})
        for name, body in jobs.items():
            self.assertEqual("contents: write" in body, name == "release", name)


if __name__ == "__main__":
    unittest.main()
