#!/usr/bin/env python3
"""Risk map contracts: tiers from a committed policy, a fixed always-human floor, and renames
classified by both paths. The JSON must be byte-identical on macOS, Linux and Windows."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import risk_map  # noqa: E402

CORE = ROOT / "agentsmith.py"
POLICY = risk_map.POLICY_PATH
# Fixed identity and dates make the fixture commits, and so the JSON, identical on every host.
GIT_ENV = {
    "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "user@example.com",
    "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "user@example.com",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+0000", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+0000",
}


def policy(*rules: dict) -> bytes:
    return json.dumps({"schema_version": 1, "rules": list(rules)}).encode("utf-8")


class Fixture:
    """A real temporary Git repository with deterministic commits."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.env = {**os.environ, **GIT_ENV}
        root.mkdir(parents=True)
        self.git("init", "-q", "-b", "main")
        self.git("config", "core.autocrlf", "false")
        self.git("config", "commit.gpgsign", "false")

    def git(self, *args: str) -> str:
        result = subprocess.run(["git", "-C", str(self.root), *args], env=self.env,
                                capture_output=True, check=True)
        return result.stdout.decode("utf-8").strip()

    def write(self, files: dict[str, bytes | None]) -> None:
        for name, content in files.items():
            path = self.root / name
            if content is None:
                self.git("rm", "-q", "--", name)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            self.git("add", "--", name)

    def commit(self, files: dict[str, bytes | None] | None = None, message: str = "change") -> str:
        self.write(files or {})
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def move(self, old: str, new: str) -> None:
        (self.root / new).parent.mkdir(parents=True, exist_ok=True)
        self.git("mv", "--", old, new)


class PureClassifyTests(unittest.TestCase):
    def rules(self, *rules: dict) -> dict:
        return risk_map.load_policy(policy(*rules))

    def test_unmatched_path_is_human(self) -> None:
        report = risk_map.classify(["src/app.py"], self.rules({"paths": ["docs/**"], "tier": "A"}))
        self.assertEqual(report["tier"], "human")
        self.assertEqual(report["paths"], [{"path": "src/app.py", "tier": "human", "lenses": [],
                                            "matched": ["unmatched"]}])

    def test_missing_policy_makes_every_path_human(self) -> None:
        report = risk_map.classify(["docs/a.md"], risk_map.load_policy(None))
        self.assertEqual(report["tier"], "human")

    def test_highest_tier_wins_across_paths_and_rules(self) -> None:
        rules = self.rules({"paths": ["**"], "tier": "A"},
                           {"paths": ["src/auth/**"], "tier": "C", "lenses": ["security"]},
                           {"paths": ["src/**/*.sql"], "tier": "B", "lenses": ["data", "security"]})
        self.assertEqual(risk_map.classify(["docs/a.md"], rules)["tier"], "A")
        report = risk_map.classify(["docs/a.md", "src/auth/login.py", "src/db/q.sql"], rules)
        self.assertEqual(report["tier"], "C")
        self.assertEqual(report["lenses"], ["data", "security"])
        by_path = {row["path"]: row for row in report["paths"]}
        # Every matching rule counts, so an early broad rule cannot shadow a later strict one.
        self.assertEqual(by_path["src/auth/login.py"]["tier"], "C")
        self.assertEqual(by_path["src/auth/login.py"]["matched"], ["rule:1", "rule:2"])

    def test_glob_star_stays_inside_one_folder(self) -> None:
        rules = self.rules({"paths": ["docs/*"], "tier": "A"}, {"paths": ["**/*.md"], "tier": "B"})
        self.assertEqual(risk_map.classify(["docs/a.txt"], rules)["tier"], "A")
        self.assertEqual(risk_map.classify(["docs/deep/a.txt"], rules)["tier"], "human")
        self.assertEqual(risk_map.classify(["a.md"], rules)["tier"], "B")
        self.assertEqual(risk_map.classify(["x/y/a.md"], rules)["tier"], "B")

    def test_repeated_double_star_matches_like_one_and_stays_fast(self) -> None:
        # Each extra `**` multiplied the regex backtracking; twelve could hang classification.
        rules = self.rules({"paths": ["/".join(["**"] * 12) + "/x"], "tier": "A"})
        self.assertEqual(risk_map.classify(["x", "a/b/x"], rules)["tier"], "A")
        started = time.monotonic()
        self.assertEqual(risk_map.classify(["/".join(["a"] * 40) + "/y"], rules)["tier"], "human")
        self.assertLess(time.monotonic() - started, 1.0)

    def test_rules_match_ignoring_case(self) -> None:
        # macOS and Windows open Src/Auth/x.py in the folder a rule for src/auth/** describes.
        rules = self.rules({"paths": ["**"], "tier": "A"}, {"paths": ["src/auth/**"], "tier": "C"})
        self.assertEqual(risk_map.classify(["SRC/Auth/x.py"], rules)["tier"], "C")

    def test_floor_cannot_be_configured_away(self) -> None:
        rules = self.rules({"paths": ["**"], "tier": "A"})
        floor = (
            "AGENTS.md", "docs/AGENTS.md", "AGENTS.override.md", "CLAUDE.md", "src/deep/claude.md",
            "CLAUDE.local.md", "GEMINI.md", ".claude/settings.json", ".Claude/settings.json",
            "src/.claude/skills/x/SKILL.md", ".codex/config.toml", ".agents/skills/x/SKILL.md",
            ".cursor/rules/r.mdc", ".github/workflows/verify.yml", ".GitHub/Workflows/x.yml",
            ".github/actions/setup/action.yml", ".github/CODEOWNERS", ".harness/verify.conf",
            POLICY, ".agentsmith/agentsmith.py", "agentsmith.py", "scripts/autonomous-run.py",
            "native_launcher.py", "work_graph.py", "windows_verifier_sandbox.py", "risk_map.py",
            "scripts/verify.sh", "scripts/verify-local.ps1", ".env", ".env.local", "config/.ENV.production",
            "certs/server.pem", "deploy_key", "keys/id_rsa", "id_ed25519.pub", "secrets/token.txt",
            "app/Secrets/a.txt", "db/migrations/0001_init.sql", "migrations/x.py", "pkg/Migrations/y.go",
        )
        for path in floor:
            with self.subTest(path=path):
                row = risk_map.classify([path], rules)["paths"][0]
                self.assertEqual(row["tier"], "human")
                self.assertTrue(any(reason.startswith("floor:") for reason in row["matched"]), row)
        lookalikes = ("docs/agents-guide.md", "src/claude_client.py", "src/my.claude/x.py",
                      "docs/CLAUDE.md.txt", ".cursor-notes.md", ".github/ISSUE_TEMPLATE/bug.md",
                      "src/environment.py", "docs/migration-guide.md", "docs/keys.md", "scripts/test-x.py",
                      "src/agentsmith.py", "harness/notes.md")
        for path in lookalikes:
            with self.subTest(path=path):
                self.assertEqual(risk_map.classify([path], rules)["tier"], "A")

    def test_a_recorded_tier_cannot_be_lowered(self) -> None:
        for recorded in risk_map.TIERS:
            for proposed in risk_map.TIERS:
                with self.subTest(recorded=recorded, proposed=proposed):
                    result = risk_map.raise_tier(recorded, proposed)
                    self.assertEqual(result, max(recorded, proposed, key=risk_map.TIERS.index))
                    self.assertGreaterEqual(risk_map.TIERS.index(result), risk_map.TIERS.index(recorded))
        self.assertEqual(risk_map.raise_tier("C", "A"), "C")
        self.assertEqual(risk_map.raise_tier("human", "A"), "human")
        with self.assertRaises(ValueError):
            risk_map.raise_tier("C", "lower")

    def test_invalid_policy_is_rejected(self) -> None:
        bad = (
            b"{", b"[]", json.dumps({"rules": []}).encode(),
            json.dumps({"schema_version": 2, "rules": []}).encode(),
            policy({"paths": ["docs/**"], "tier": "D"}),
            policy({"paths": ["docs/**"], "tier": "a"}),
            policy({"paths": [], "tier": "A"}),
            policy({"paths": ["docs\\**"], "tier": "A"}),
            policy({"paths": ["/docs/**"], "tier": "A"}),
            policy({"paths": ["docs/**"], "tier": "A", "lenses": ["Bad Lens"]}),
            policy({"paths": ["docs/**"], "tier": "A", "skip_human": True}),
            json.dumps({"schema_version": 1, "rules": [], "floor": []}).encode(),
            b'{"schema_version": 1, "schema_version": 1, "rules": []}',
        )
        for data in bad:
            with self.subTest(data=data):
                with self.assertRaises(risk_map.PolicyError):
                    risk_map.load_policy(data)

    def test_sample_policy_is_valid(self) -> None:
        sample = (ROOT / "templates" / "risk-policy.json").read_bytes()
        rules = risk_map.load_policy(sample)
        self.assertEqual(risk_map.classify(["docs/guide.md"], rules)["tier"], "A")
        self.assertEqual(risk_map.classify(["AGENTS.md"], rules)["tier"], "human")

    def test_name_status_parsing_keeps_both_paths_of_renames_and_copies(self) -> None:
        raw = (b"M\0src/a b.py\0R087\0old/x.py\0.github/workflows/x.yml\0"
               b"C100\0src/k.py\0src/k copy.py\0D\0gone.txt\0A\0docs/caf\xc3\xa9.md\0T\0link\0")
        self.assertEqual(risk_map.parse_name_status(raw), [
            ".github/workflows/x.yml", "docs/café.md", "gone.txt", "link", "old/x.py",
            "src/a b.py", "src/k copy.py", "src/k.py"])


class RepoCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="agentsmith risk ")
        self.repo = Fixture(Path(self.temporary.name) / "repo")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def cli(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run([sys.executable, str(CORE), "risk", "classify", "--target", str(self.repo.root), *args],
                              capture_output=True, env={**os.environ, "PYTHONIOENCODING": "cp1252"})

    def base_with_policy(self) -> str:
        self.base_policy = policy(
            {"paths": ["docs/**", "**/*.md"], "tier": "A"},
            {"paths": ["src/**"], "tier": "B"},
            {"paths": ["src/auth/**"], "tier": "C", "lenses": ["security"]})
        return self.repo.commit({
            POLICY: self.base_policy,
            "src/app.py": b"x = 1\n", "src/auth/login.py": b"ok = True\n", "src/notes.md": b"notes\n",
            ".harness/verify.conf": b"unit :: true\n", "docs/a.md": b"a\n",
        }, "base")


class RangeTests(RepoCase):
    def test_rename_into_a_floor_path_is_human_and_lists_both_paths(self) -> None:
        base = self.base_with_policy()
        self.repo.move("src/notes.md", ".github/workflows/notes.md")
        head = self.repo.commit(message="move into workflows")
        report = risk_map.classify_range(self.repo.root, base, head)
        self.assertEqual(report["tier"], "human")
        self.assertEqual([row["path"] for row in report["paths"]], [".github/workflows/notes.md", "src/notes.md"])

    def test_rename_out_of_a_floor_path_is_human(self) -> None:
        base = self.base_with_policy()
        self.repo.move(".harness/verify.conf", "docs/verify.conf")
        head = self.repo.commit(message="move out of harness")
        report = risk_map.classify_range(self.repo.root, base, head)
        self.assertEqual(report["tier"], "human")
        self.assertIn(".harness/verify.conf", [row["path"] for row in report["paths"]])

    def test_rename_from_a_strict_area_keeps_its_tier(self) -> None:
        base = self.base_with_policy()
        self.repo.move("src/auth/login.py", "docs/login.py")
        head = self.repo.commit(message="move auth into docs")
        report = risk_map.classify_range(self.repo.root, base, head)
        self.assertEqual(report["tier"], "C")
        self.assertEqual(report["lenses"], ["security"])

    def test_candidate_cannot_relax_its_own_policy(self) -> None:
        base = self.base_with_policy()
        head = self.repo.commit({
            POLICY: policy({"paths": ["**"], "tier": "A"}),
            "src/auth/login.py": b"ok = False\n", "src/new.txt": b"new\n",
        }, "relax the policy")
        report = risk_map.classify_range(self.repo.root, base, head)
        by_path = {row["path"]: row for row in report["paths"]}
        self.assertEqual(report["tier"], "human")
        self.assertEqual(by_path[POLICY]["tier"], "human")
        self.assertEqual(by_path["src/auth/login.py"]["tier"], "C")
        self.assertEqual(by_path["src/new.txt"]["tier"], "B")
        self.assertEqual(report["policy"]["blob"], self.repo.git("rev-parse", f"{base}:{POLICY}"))
        # Without the policy edit, the same code change keeps the base policy's tier.
        head = self.repo.commit({POLICY: self.base_policy}, "restore the policy")
        self.assertEqual(risk_map.classify_range(self.repo.root, base, head)["tier"], "C")

    def test_policy_that_is_a_symlink_at_base_fails_closed(self) -> None:
        # Git stores a symlink as a blob; its target text must not be read as the policy.
        self.repo.commit({"docs/a.md": b"a\n"}, "docs")
        link = subprocess.run(["git", "-C", str(self.repo.root), "hash-object", "-w", "--stdin"], input=b"other.json",
                              capture_output=True, check=True).stdout.decode("ascii").strip()
        self.repo.git("update-index", "--add", "--cacheinfo", f"120000,{link},{POLICY}")
        base = self.repo.commit(message="policy as a link")
        head = self.repo.commit({"docs/a.md": b"b\n"}, "docs")
        with self.assertRaisesRegex(risk_map.PolicyError, "not a regular file"):
            risk_map.classify_range(self.repo.root, base, head)

    def test_policy_absent_at_base_is_human(self) -> None:
        base = self.repo.commit({"docs/a.md": b"a\n"}, "base")
        head = self.repo.commit({POLICY: policy({"paths": ["**"], "tier": "A"}), "docs/a.md": b"b\n"}, "add policy")
        report = risk_map.classify_range(self.repo.root, base, head)
        self.assertEqual(report["tier"], "human")
        self.assertIsNone(report["policy"]["blob"])
        self.assertEqual({row["tier"] for row in report["paths"]}, {"human"})

    def test_empty_range_is_human(self) -> None:
        base = self.base_with_policy()
        report = risk_map.classify_range(self.repo.root, base, base)
        self.assertEqual((report["tier"], report["paths"]), ("human", []))


class CliTests(RepoCase):
    def test_json_is_byte_identical_on_every_host(self) -> None:
        base = self.base_with_policy()
        self.repo.move("src/notes.md", "docs/nötes and spaces.md")
        head = self.repo.commit({"src/auth/login.py": None, "src/app.py": b"x = 2\n"}, "mixed change")
        first = self.cli("--base", base, "--head", head, "--json")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, self.cli("--base", base, "--head", head, "--json").stdout)
        self.assertNotIn(b"\r", first.stdout)
        self.assertNotIn(str(self.repo.root).encode("utf-8"), first.stdout)
        # The fixture pins identity, dates and bytes, so commit ids are the same on every host,
        # and the expected report is a literal: CI compares the same bytes on all three systems.
        self.assertEqual((base, head), ("fbd3381c15669c158cfeaf5f777bb6c066988742",
                                        "4cc7b6e44b8ec0a4c25354f8597ddb07219fd96e"))
        expected = (
            '{"base": "%s", "head": "%s", "lenses": ["security"], "paths": ['
            '{"lenses": [], "matched": ["rule:1"], "path": "docs/n\\u00f6tes and spaces.md", "tier": "A"}, '
            '{"lenses": [], "matched": ["rule:2"], "path": "src/app.py", "tier": "B"}, '
            '{"lenses": ["security"], "matched": ["rule:2", "rule:3"], "path": "src/auth/login.py", "tier": "C"}, '
            '{"lenses": [], "matched": ["rule:1", "rule:2"], "path": "src/notes.md", "tier": "B"}], '
            '"policy": {"blob": "%s", "path": ".harness/risk-policy.json"}, "schema_version": 1, "tier": "C"}\n'
        ) % (base, head, "be8addd6e793a425e446b870bb8820b3b29dd90f")
        self.assertEqual(first.stdout.decode("ascii"), expected)

    def test_text_output_names_tier_and_lenses(self) -> None:
        base = self.base_with_policy()
        head = self.repo.commit({"src/auth/login.py": b"ok = 1\n"}, "auth")
        result = self.cli("--base", base, "--head", head)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = result.stdout.decode("utf-8")
        self.assertIn("tier: C", text)
        self.assertIn("lenses: security", text)
        self.assertIn("src/auth/login.py", text)

    def test_bad_ref_and_bad_policy_fail_closed(self) -> None:
        base = self.base_with_policy()
        result = self.cli("--base", "no-such-ref", "--head", base, "--json")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"no-such-ref", result.stderr)
        broken = self.repo.commit({POLICY: b"{"}, "break policy")
        head = self.repo.commit({"docs/a.md": b"b\n"}, "docs")
        result = self.cli("--base", broken, "--head", head, "--json")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertIn(POLICY.encode(), result.stderr)


if __name__ == "__main__":
    unittest.main()
