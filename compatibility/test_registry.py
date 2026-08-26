"""Standard-library conformance checks for the compatibility registry."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config"

EXPECTED_IDS = {
    "claude",
    "codex",
    "github-copilot",
    "cursor",
    "gemini-cli",
    "windsurf-devin",
    "cline",
    "roo-code",
    "aider",
    "continue",
    "openhands",
    "goose",
    "opencode",
    "jetbrains-junie",
    "zed",
    "jules",
}


class RegistryContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads((CONFIG / "agents.json").read_text(encoding="utf-8"))
        cls.schema = json.loads((CONFIG / "agents.schema.json").read_text(encoding="utf-8"))

    def test_contract_vocabulary_is_closed(self) -> None:
        self.assertEqual(self.registry["schema_version"], 1)
        self.assertEqual(self.registry["canonical_instructions"], "AGENTS.md")
        self.assertEqual(
            self.registry["dimensions"],
            ["instructions", "skills_tools", "native_runtime"],
        )
        self.assertEqual(
            set(self.registry["support_tiers"]),
            {"native", "certified", "community-compatible"},
        )
        self.assertEqual(
            set(self.registry["evidence_types"]),
            {"fixture", "observed", "manual"},
        )

    def test_exactly_the_sixteen_planned_targets_are_registered(self) -> None:
        agents = self.registry["agents"]
        ids = [agent["id"] for agent in agents]
        self.assertEqual(len(ids), 16)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), EXPECTED_IDS)

    def test_native_tier_is_limited_to_claude_and_codex(self) -> None:
        native = {
            agent["id"]
            for agent in self.registry["agents"]
            if agent["target_tier"] == "native"
        }
        self.assertEqual(native, {"claude", "codex"})

    def test_selector_groups_are_exact_and_closed(self) -> None:
        groups = self.registry["groups"]
        self.assertEqual(set(groups), {"native", "standard", "local", "all"})
        self.assertEqual(set(groups["native"]), {"claude", "codex"})
        self.assertEqual(set(groups["all"]), EXPECTED_IDS)
        self.assertTrue(set(groups["standard"]) <= EXPECTED_IDS)
        self.assertTrue(set(groups["local"]) <= EXPECTED_IDS)

    def test_no_fixture_only_target_is_certified(self) -> None:
        for agent in self.registry["agents"]:
            if {entry["type"] for entry in agent["evidence"]} == {"fixture"}:
                self.assertNotEqual(agent["certification"], "passed", agent["id"])

    def test_paths_and_capability_dimensions_are_present(self) -> None:
        capability_states = {"supported", "unsupported", "unverified"}
        management_states = {"native", "planned", "none"}
        for agent in self.registry["agents"]:
            instructions = agent["instructions"]
            self.assertIn("global_paths", instructions, agent["id"])
            self.assertTrue(instructions["project_paths"], agent["id"])
            for section, key in (
                ("skills_tools", "agent_skills"),
                ("skills_tools", "mcp"),
                ("native_runtime", "hooks"),
                ("native_runtime", "doctor"),
                ("native_runtime", "lifecycle"),
            ):
                capability = agent[section][key]
                self.assertIn(capability["client_support"], capability_states)
                self.assertIn(capability["agentsmith_management"], management_states)

    def test_backends_are_excluded_as_agent_targets(self) -> None:
        ids = {agent["id"] for agent in self.registry["agents"]}
        excluded = {entry["id"] for entry in self.registry["exclusions"]}
        self.assertTrue({"tabby", "lm-studio"}.issubset(excluded))
        self.assertTrue(ids.isdisjoint(excluded))

    def test_schema_declares_the_same_closed_sets(self) -> None:
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], 1)
        self.assertEqual(
            set(self.schema["properties"]["evidence_types"]["required"]),
            {"fixture", "observed", "manual"},
        )
        self.assertEqual(
            self.schema["properties"]["agents"]["minItems"],
            self.schema["properties"]["agents"]["maxItems"],
        )


if __name__ == "__main__":
    unittest.main()
