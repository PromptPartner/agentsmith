#!/usr/bin/env python3
"""Behavioral tests for doctor against effective installed state."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


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
            }
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_core(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CORE), *arguments], cwd=ROOT, env=self.env,
            text=True, capture_output=True, check=False,
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
        self.assertEqual(by_scope["nested"]["generated_core"], False)
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
