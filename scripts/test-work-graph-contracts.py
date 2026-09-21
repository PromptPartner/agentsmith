#!/usr/bin/env python3
"""W2-01 fixture and schema contracts; runtime CLI reds live in a separate file."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "work-graph" / "v1"
SCHEMAS = FIXTURES / "schemas"
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
SAFE_ID = re.compile(r"[A-Za-z0-9_-]+\Z")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_schema(test: unittest.TestCase, value: Any, schema: dict[str, Any], root: dict[str, Any]) -> None:
    if "$ref" in schema:
        target: Any = root
        for part in schema["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        assert_schema(test, value, target, root)
        return
    if "const" in schema:
        test.assertEqual(value, schema["const"])
    if "enum" in schema:
        test.assertIn(value, schema["enum"])
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        checks = {
            "object": lambda x: isinstance(x, dict),
            "array": lambda x: isinstance(x, list),
            "string": lambda x: isinstance(x, str),
            "integer": lambda x: isinstance(x, int) and not isinstance(x, bool),
            "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
            "boolean": lambda x: isinstance(x, bool),
            "null": lambda x: x is None,
        }
        test.assertTrue(any(checks[k](value) for k in types), f"wrong type: {value!r}")
    if isinstance(value, str):
        if "pattern" in schema:
            test.assertRegex(value, re.compile(schema["pattern"]))
        if "minLength" in schema:
            test.assertGreaterEqual(len(value), schema["minLength"])
    if isinstance(value, list):
        if "minItems" in schema:
            test.assertGreaterEqual(len(value), schema["minItems"])
        if "maxItems" in schema:
            test.assertLessEqual(len(value), schema["maxItems"])
        if schema.get("uniqueItems"):
            test.assertEqual(len(value), len({json.dumps(x, sort_keys=True) for x in value}))
        if "items" in schema:
            for item in value:
                assert_schema(test, item, schema["items"], root)
    if isinstance(value, dict):
        test.assertTrue(set(schema.get("required", [])) <= set(value))
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            test.assertTrue(set(value) <= set(properties))
        for key, item in value.items():
            if key in properties:
                assert_schema(test, item, properties[key], root)


def contract_error(graph: dict[str, Any], *, fixture_root: Path = ROOT) -> str | None:
    """Reference invariant oracle for fixtures, not the runtime graph validator."""
    if graph.get("schema_version") != 1:
        return "unsupported-schema"
    if not isinstance(graph.get("max_parallel"), int) or not 1 <= graph["max_parallel"] <= 2:
        return "invalid-concurrency"
    nodes = graph["nodes"]
    ids = [node["run_id"] for node in nodes]
    if len(ids) != len(set(ids)):
        return "duplicate-run-id"
    if set(graph["integration_order"]) != set(ids) or len(graph["integration_order"]) != len(ids):
        return "integration-order"
    by_id = {node["run_id"]: node for node in nodes}
    for node in nodes:
        if any(dep not in by_id for dep in node["depends_on"]):
            return "unknown-dependency"
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(run_id: str) -> bool:
        if run_id in visiting:
            return False
        if run_id in visited:
            return True
        visiting.add(run_id)
        if not all(visit(dep) for dep in by_id[run_id]["depends_on"]):
            return False
        visiting.remove(run_id)
        visited.add(run_id)
        return True

    if not all(visit(run_id) for run_id in ids):
        return "dependency-cycle"
    order = {run_id: index for index, run_id in enumerate(graph["integration_order"])}
    if any(order[dep] >= order[node["run_id"]] for node in nodes for dep in node["depends_on"]):
        return "integration-order"
    for node in nodes:
        path = Path(node["manifest_path"])
        if path.is_absolute() or ".." in path.parts:
            return "unsafe-manifest-path"
        manifest_path = fixture_root / path
        if not manifest_path.is_file():
            return "missing-manifest"
        raw = manifest_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != node["manifest_sha256"]:
            return "manifest-hash"
        manifest = json.loads(raw)
        if manifest.get("run_id") != node["run_id"]:
            return "manifest-run-id"
        scope = manifest.get("scope", {})
        for scope_path in scope.get("allowed_paths", []) + scope.get("denied_paths", []):
            scoped = Path(scope_path)
            if scoped.is_absolute() or ".." in scoped.parts:
                return "unsafe-scope"
        for scope_path in scope.get("allowed_paths", []):
            if scope_path.startswith(".git/"):
                return "unsafe-scope"
        resources = scope.get("resources", [])
        if len(resources) != len(set(resources)):
            return "conflicting-resources"
        limits = manifest.get("limits", {})
        if not isinstance(limits.get("max_attempts"), int) or not 1 <= limits["max_attempts"] <= 3:
            return "invalid-budget"
        if not isinstance(limits.get("wall_minutes"), int) or limits["wall_minutes"] <= 0:
            return "invalid-budget"
        if not isinstance(limits.get("codex_goal_tokens"), int) or limits["codex_goal_tokens"] <= 0:
            return "invalid-budget"
        if not isinstance(limits.get("claude_max_usd"), (int, float)) or limits["claude_max_usd"] <= 0:
            return "invalid-budget"
    return None


def set_pointer(value: Any, pointer: str, replacement: Any) -> None:
    target = value
    parts = pointer.strip("/").split("/")
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    final = parts[-1]
    target[int(final) if isinstance(target, list) else final] = replacement


class WorkGraphContractTests(unittest.TestCase):
    def test_schemas_are_closed_and_versioned(self) -> None:
        expected = {"work-graph", "local-state", "status", "event", "integration-candidate", "native-platform", "native-aggregate"}
        self.assertEqual({p.stem.removesuffix(".schema") for p in SCHEMAS.glob("*.schema.json")}, expected)
        for name in expected:
            schema = read_json(SCHEMAS / f"{name}.schema.json")
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertEqual(schema["properties"]["schema_version"]["const"], 1)
            self.assertIs(schema["additionalProperties"], False)

    def test_three_node_graph_pins_manifest_bytes_and_dependency_order(self) -> None:
        graph = read_json(FIXTURES / "work-graph.valid.json")
        schema = read_json(SCHEMAS / "work-graph.schema.json")
        assert_schema(self, graph, schema, schema)
        self.assertIsNone(contract_error(graph))
        self.assertEqual(graph["max_parallel"], 2)
        self.assertEqual(graph["integration_order"], ["sample_a", "sample_b", "sample_c"])
        self.assertEqual(graph["nodes"][2]["depends_on"], ["sample_a", "sample_b"])
        self.assertEqual(set(graph), {"schema_version", "graph_id", "max_parallel", "integration_order", "nodes"})

    def test_invalid_contract_fixtures_fail_for_named_reason(self) -> None:
        cases = read_json(FIXTURES / "invalid" / "cases.json")
        self.assertGreaterEqual(len(cases), 9)
        for case in cases:
            with self.subTest(case=case["name"]):
                graph = read_json(FIXTURES / "work-graph.valid.json")
                for patch in case.get("graph_patches", []):
                    set_pointer(graph, patch["path"], patch["value"])
                if "manifest_patch" in case:
                    with tempfile.TemporaryDirectory() as temporary:
                        root = Path(temporary)
                        destination = root / "tests" / "fixtures" / "work-graph" / "v1" / "manifests"
                        shutil.copytree(FIXTURES / "manifests", destination)
                        patch = case["manifest_patch"]
                        index = patch["node_index"]
                        manifest_path = root / graph["nodes"][index]["manifest_path"]
                        manifest = read_json(manifest_path)
                        set_pointer(manifest, patch["path"], patch["value"])
                        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
                        graph["nodes"][index]["manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
                        self.assertEqual(contract_error(graph, fixture_root=root), case["reason"])
                else:
                    self.assertEqual(contract_error(graph), case["reason"])

    def test_output_examples_match_versioned_schemas(self) -> None:
        for name in ("local-state", "status", "event", "integration-candidate", "native-platform", "native-aggregate"):
            with self.subTest(name=name):
                schema = read_json(SCHEMAS / f"{name}.schema.json")
                example = read_json(FIXTURES / "examples" / f"{name}.json")
                assert_schema(self, example, schema, schema)

    def test_status_contract_can_report_accepted_commit_lineage(self) -> None:
        schema = read_json(SCHEMAS / "status.schema.json")
        node = schema["$defs"]["node"]
        self.assertIn("accepted_commit", node["properties"])

    def test_transition_table_and_hashing_contract(self) -> None:
        transitions = read_json(FIXTURES / "transitions.json")
        self.assertEqual(transitions["schema_version"], 1)
        self.assertEqual(transitions["quiescent"], ["completed", "failed", "stopped"])
        self.assertEqual(transitions["absorbing"], ["completed", "failed"])
        self.assertEqual(transitions["graph"]["stopped"], ["running"])
        for state in transitions["absorbing"]:
            self.assertEqual(transitions["graph"][state], [])
        graph = FIXTURES / "work-graph.valid.json"
        example = read_json(FIXTURES / "examples" / "local-state.json")
        self.assertEqual(example["graph_sha256"], hashlib.sha256(graph.read_bytes()).hexdigest())
        self.assertTrue(HEX40.fullmatch(example["contract_commit"]))
        self.assertTrue(HEX64.fullmatch(example["graph_sha256"]))
        self.assertTrue(all(SAFE_ID.fullmatch(node["run_id"]) for node in read_json(graph)["nodes"]))


if __name__ == "__main__":
    unittest.main()
