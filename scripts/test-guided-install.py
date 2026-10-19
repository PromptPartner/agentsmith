#!/usr/bin/env python3
"""Contracts for the beginner-facing installation experience."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("agentsmith", ROOT / "agentsmith.py")
assert SPEC and SPEC.loader
agentsmith = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(agentsmith)

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
            plan = agentsmith.apply_wizard_answers(args, lambda _prompt: next(answers))
            self.assertFalse(target.exists(), "the wizard must not write before install applies")
            self.assertTrue(plan["confirmed"])
            self.assertEqual(Path(args.target), target.resolve())
            self.assertEqual(args.profile, ["software-dev"])
            self.assertEqual(args.agent, ["codex"])
            self.assertEqual(args.safety, "cautious")
            self.assertTrue(args.initialize_git)
            self.assertIn("daily Git", args.operator_bio)

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
