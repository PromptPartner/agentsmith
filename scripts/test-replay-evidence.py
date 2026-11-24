#!/usr/bin/env python3
"""SF-18b replayable feature evidence: the controller records a demo transcript at acceptance, the
pull-request body and the inbox row link it, `evidence` records that the operator opened it, and
`deliver` records whether that happened before the delivery check. Real runs with fake clients."""

from __future__ import annotations

import _fixture_git  # first: keeps every Git fixture out of an inherited repository
_fixture_git.isolate()
import sys
sys.dont_write_bytecode = True  # loading the deliver suite must not leave compiled files behind
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parent.parent
CONTROLLER_PATH = ROOT / "scripts" / "autonomous-run.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONTROLLER = load("agentsmith_replay_controller", CONTROLLER_PATH)
# The deliver suite's real-run fixture: an accepted contract, a local bare origin, fake clients.
DELIVER = load("agentsmith_replay_deliver_fixture", ROOT / "scripts" / "test-deliver.py")
sys.path.insert(0, str(ROOT))
import inbox  # noqa: E402

DEMO = "\n## Demo\n\n```sh\ncat src/change.txt\necho 'demo note' >&2\n```\n"


@unittest.skipUnless(DELIVER.sandbox_available(), "a real run needs the macOS or Linux role sandbox")
class ReplayEvidenceTests(unittest.TestCase):
    setUp = DELIVER.DeliverTests.setUp
    git = DELIVER.DeliverTests.git
    calibrate = DELIVER.DeliverTests.calibrate
    accepted_run = DELIVER.DeliverTests.accepted_run
    deliver = DELIVER.DeliverTests.deliver
    state = DELIVER.DeliverTests.state

    def run_dir(self, repo: Path, run_id: str = "deliver") -> Path:
        return repo / ".git/agentsmith-runs" / run_id

    def events(self, repo: Path, kind: str, run_id: str = "deliver") -> list[dict]:
        lines = (self.run_dir(repo, run_id) / "events.jsonl").read_text(encoding="utf-8").splitlines()
        return [record for record in map(json.loads, lines) if record.get("event") == kind]

    def evidence(self, repo: Path, run_id: str = "deliver") -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(CONTROLLER_PATH), "evidence", run_id], cwd=repo, env=self.env,
                              text=True, capture_output=True, check=False)

    def dry_run(self, repo: Path) -> dict:
        result = self.deliver(repo, "--dry-run", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_a_cli_lap_records_a_controller_transcript_linked_in_the_pull_request_body(self) -> None:
        repo = self.accepted_run(spec_note=DEMO)
        state = self.state(repo)
        demo = state["demo"]
        transcript = self.run_dir(repo) / demo["file"]
        self.assertEqual(demo["file"], "attempt-1-demo.txt")
        self.assertEqual(demo["commit"], state["accepted_commit"])
        self.assertEqual(demo["exit_code"], 0)
        self.assertEqual(hashlib.sha256(transcript.read_bytes()).hexdigest(), demo["sha256"])
        text = transcript.read_text(encoding="utf-8")
        # The controller ran the accepted spec's command on the accepted commit: the maker's
        # receipt plays no part in it.
        self.assertIn("$ cat src/change.txt", text)
        self.assertIn("fixed", text)
        self.assertIn("demo note", text)
        self.assertIn("exit status: 0", text)
        # No unredacted copy of the demo output stays in the run folder.
        self.assertEqual(sorted(path.name for path in self.run_dir(repo).glob("attempt-1-demo*")
                                if path.suffix in {".stdout", ".stderr"}), [])
        report = self.dry_run(repo)
        body = report["body"]
        self.assertIn("### Demo", body)
        self.assertIn(demo["sha256"], body)
        self.assertIn("autonomous-run.py evidence deliver", body)
        self.assertIn("fixed", body)
        self.assertIn("not opened", body)
        self.assertEqual(report["demo"]["sha256"], demo["sha256"])
        self.assertIs(report["demo"]["opened_before_delivery"], False)
        checked = self.events(repo, "delivery_checked")
        self.assertEqual(len(checked), 1)
        self.assertIs(checked[0]["evidence_opened"], False)
        self.assertEqual(checked[0]["evidence_sha256"], demo["sha256"])
        self.assertEqual(checked[0]["mode"], "dry-run")
        self.assertEqual(checked[0]["head"], state["accepted_commit"])

    def test_opening_the_transcript_records_the_event_and_deliver_records_it_was_opened(self) -> None:
        repo = self.accepted_run(spec_note=DEMO)
        demo = self.state(repo)["demo"]
        self.assertEqual(self.events(repo, "evidence_opened"), [])
        opened = self.evidence(repo)
        self.assertEqual(opened.returncode, 0, opened.stdout + opened.stderr)
        self.assertIn("$ cat src/change.txt", opened.stdout)
        self.assertIn("fixed", opened.stdout)
        self.assertIn(demo["sha256"], opened.stdout)
        records = self.events(repo, "evidence_opened")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["sha256"], demo["sha256"])
        self.assertEqual(records[0]["artefact"], "attempt-1-demo.txt")
        self.assertEqual(records[0]["commit"], demo["commit"])
        report = self.dry_run(repo)
        self.assertIs(report["demo"]["opened_before_delivery"], True)
        self.assertNotIn("not opened", report["body"])
        self.assertIs(self.events(repo, "delivery_checked")[-1]["evidence_opened"], True)

    def test_a_changed_transcript_is_refused_by_evidence_and_by_deliver(self) -> None:
        repo = self.accepted_run(spec_note=DEMO)
        transcript = self.run_dir(repo) / self.state(repo)["demo"]["file"]
        transcript.write_text(transcript.read_text(encoding="utf-8") + "forged line\n", encoding="utf-8")
        opened = self.evidence(repo)
        self.assertEqual(opened.returncode, 2)
        self.assertIn("changed after the controller recorded it", opened.stderr)
        self.assertNotIn("forged line", opened.stdout)
        self.assertEqual(self.events(repo, "evidence_opened"), [])
        result = self.deliver(repo, "--dry-run")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("deliver refused", result.stderr)
        self.assertIn("changed after the controller recorded it", result.stderr)

    def test_demo_output_is_untrusted_redacted_bounded_and_sandboxed(self) -> None:
        outside = self.root / "escaped.txt"
        # The token is assembled when the demo runs, so neither this file nor the spec holds it.
        demo = ("\n## Demo\n\n```sh\nprintf 'key %s%s\\n' 'gh' 'p_Z9y8Z9y8Z9y8Z9y8Z9y8Z9y8Z9y8'\n"
                "printf 'home %s/x\\n' \"" + str(Path.home()) + "\"\n"
                "printf 'bell \\033[2J\\n'\n"
                "head -c 300000 /dev/zero | tr '\\0' x\n"
                f"echo escape > '{outside}'\n```\n")
        repo = self.accepted_run(spec_note=demo)
        record = self.state(repo)["demo"]
        text = (self.run_dir(repo) / record["file"]).read_text(encoding="utf-8")
        token = "gh" + "p_" + "Z9y8" * 7  # the command splits it; only the printed value is a secret
        self.assertFalse(token in text, "the printed token must be redacted")
        self.assertIn("[redacted: GitHub token]", text)
        self.assertFalse(str(Path.home()) in text, "no home folder")
        self.assertFalse("\x1b" in text, "no raw escape")
        self.assertIn("\\x1b", text)
        self.assertLess(len(text), 70000)
        self.assertIn("output cut", text)
        self.assertTrue(record["truncated"])
        self.assertGreaterEqual(record["redactions"], 1)
        # The demo runs in the verifier sandbox: it cannot write outside its worktree.
        self.assertFalse(outside.exists())
        self.assertNotEqual(record["exit_code"], 0)
        body = self.dry_run(repo)["body"]
        self.assertFalse(token in body, "the body must not hold the token")
        self.assertLess(len(body), 20000)

    def test_a_landing_without_a_demo_says_so(self) -> None:
        repo = self.accepted_run()
        self.assertNotIn("demo", self.state(repo))
        opened = self.evidence(repo)
        self.assertEqual(opened.returncode, 2)
        self.assertIn("no demo transcript", opened.stderr)
        report = self.dry_run(repo)
        self.assertIn("### Demo", report["body"])
        self.assertIn("no replayable demonstration", report["body"])
        self.assertIsNone(report["demo"])
        checked = self.events(repo, "delivery_checked")[-1]
        self.assertIs(checked["evidence_opened"], False)
        self.assertIsNone(checked["evidence_sha256"])

    def test_the_inbox_row_links_the_transcript_and_shows_whether_it_was_opened(self) -> None:
        repo = self.accepted_run(spec_note=DEMO)
        demo = self.state(repo)["demo"]

        def row() -> dict:
            rows = [item for item in inbox.collect(repo)["rows"] if item["id"] == "deliver"]
            self.assertEqual(len(rows), 1)
            return rows[0]

        before = row()
        self.assertEqual(before["kind"], "accepted")
        self.assertEqual(before["evidence"], {"artefact": "attempt-1-demo.txt", "sha256": demo["sha256"],
                                              "command": "autonomous-run.py evidence deliver", "opened": False})
        self.assertIn("autonomous-run.py evidence deliver", before["next_step"])
        self.assertIn("not opened", before["next_step"])
        self.assertEqual(self.evidence(repo).returncode, 0)
        after = row()
        self.assertIs(after["evidence"]["opened"], True)
        self.assertNotIn("not opened", after["next_step"])

    def test_a_held_run_records_its_demo_too(self) -> None:
        repo = self.accepted_run(spec_note=DEMO, calibrated=False)
        state = self.state(repo)
        self.assertEqual(state["status"], "awaiting-human")
        self.assertEqual(state["demo"]["commit"], state["held_commit"])
        self.assertEqual(self.evidence(repo).returncode, 0)


class DemoGuideTests(unittest.TestCase):
    def test_the_skill_asks_the_operator_to_watch_the_demo_themselves(self) -> None:
        skill = (ROOT / "skills/autonomous-run/SKILL.md").read_text(encoding="utf-8")
        step = skill.split("## Land an accepted run (attended)", 1)[1].split("\n## ", 1)[0]
        self.assertIn("autonomous-run.py evidence <run-id>", step)
        self.assertIn("Do not run `evidence` for them", step)

    def test_docs_describe_the_demo_and_say_ui_artefacts_are_not_supported(self) -> None:
        docs = (ROOT / "docs/21-autonomous-runs.md").read_text(encoding="utf-8")
        section = docs.split("### Replayable demo evidence", 1)[1].split("\n### ", 1)[0]
        for required in ("## Demo", "evidence <run-id>", "evidence_opened", "delivery_checked",
                         "Not yet supported: screenshots and video"):
            self.assertIn(required, section)


class DemoHardeningTests(unittest.TestCase):
    """Findings of an independent Codex test of SF-18b, each reproduced without a real run."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="agentsmith-replay-")
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name).resolve()
        self.run = self.tmp / "run"
        self.run.mkdir()
        self.text = b"ORIGINAL\n"
        self.state = {"run_id": "x", "status": "accepted", "repo": str(ROOT), "attempt": 1,
                      "state_path": str(self.run / "state.json"), "deadline_epoch": time.time() + 60,
                      "demo_command": "echo demo",
                      "demo": {"file": "attempt-1-demo.txt", "sha256": hashlib.sha256(self.text).hexdigest(),
                               "commit": "a" * 40, "exit_code": 0, "command": "echo demo"}}

    def fake_runner(self, *, write: bool = True, interrupt: bool = False, seen: dict | None = None):
        def runner(command, cwd, timeout, env, *, state, prefix, **options):
            if seen is not None:
                seen.update(options)
            if write:
                (self.run / f"{prefix}.stdout").write_text("raw secret output\n", encoding="utf-8")
                (self.run / f"{prefix}.stderr").write_text("raw\n", encoding="utf-8")
            if interrupt:
                raise CONTROLLER.RunInterrupted("stopped by operator")
            return subprocess.CompletedProcess([command], 0, "ok\n", "")
        original = CONTROLLER.sandboxed_verify
        self.addCleanup(setattr, CONTROLLER, "sandboxed_verify", original)
        CONTROLLER.sandboxed_verify = runner

    def raw_files(self) -> list[str]:
        return sorted(path.name for path in self.run.rglob("*") if "-demo-raw." in path.name
                      and path.suffix in {".stdout", ".stderr"})

    # Finding 1: the transcript is read once, without following a link, and hashed from that read.
    def test_a_symlinked_transcript_is_refused_even_when_its_target_matches(self) -> None:
        target = self.tmp / "elsewhere.txt"
        target.write_bytes(self.text)
        (self.run / "attempt-1-demo.txt").symlink_to(target)
        with self.assertRaisesRegex(CONTROLLER.RunError, "not a regular file"):
            CONTROLLER.checked_demo(self.state)

    def test_the_text_shown_is_the_text_that_was_hashed(self) -> None:
        # A swap between a hash and a second read is simulated by a hash that always matches.
        (self.run / "attempt-1-demo.txt").write_bytes(b"FORGED!!\n")
        original = CONTROLLER.file_digest
        self.addCleanup(setattr, CONTROLLER, "file_digest", original)
        CONTROLLER.file_digest = lambda path: self.state["demo"]["sha256"]
        with self.assertRaisesRegex(CONTROLLER.RunError, "changed after the controller recorded it"):
            CONTROLLER.checked_demo(self.state)

    # Finding 2: no unredacted output stays on disk, whatever ends the demo.
    def test_an_interrupted_demo_leaves_no_raw_output(self) -> None:
        self.fake_runner(interrupt=True)
        with self.assertRaises(CONTROLLER.RunInterrupted):
            CONTROLLER.record_demo(self.state, {}, self.tmp, "a" * 40)
        self.assertEqual(self.raw_files(), [])

    def test_raw_output_left_by_an_earlier_attempt_is_removed_not_archived(self) -> None:
        for suffix in (".stdout", ".stderr"):
            (self.run / f"attempt-1-demo-raw{suffix}").write_text("stale secret\n", encoding="utf-8")
        self.fake_runner(write=False)
        CONTROLLER.record_demo(self.state, {}, self.tmp, "a" * 40)
        self.assertEqual(self.raw_files(), [])

    # Finding 3: what is read back is bounded before it reaches memory.
    def test_the_demo_reads_back_a_bounded_amount_of_output(self) -> None:
        seen: dict = {}
        self.fake_runner(seen=seen)
        CONTROLLER.record_demo(self.state, {}, self.tmp, "a" * 40)
        self.assertEqual(seen.get("read_limit"), CONTROLLER.DEMO_READ_LIMIT)
        self.assertLessEqual(CONTROLLER.DEMO_READ_LIMIT, 4 * CONTROLLER.DEMO_STREAM_LIMIT)

    def test_a_bounded_supervised_read_never_loads_more_than_its_limit(self) -> None:
        state = {"state_path": str(self.run / "state.json"), "attempt": 1}
        result = CONTROLLER.verifier_process(["/bin/bash", "-c", "head -c 300000 /dev/zero | tr '\\0' x"],
                                             self.tmp, 30, dict(os.environ), state, "probe", read_limit=1000)
        self.assertEqual(result.returncode, 0)
        self.assertLessEqual(len(result.stdout), 1000)

    # Finding 5: a run id cannot leave the runs folder.

class DemoSectionTests(unittest.TestCase):
    SPEC = "---\nstatus: accepted\n---\n# Spec\n"

    def test_the_first_fenced_block_under_demo_is_the_command(self) -> None:
        text = self.SPEC + "## Demo\n\nRun it:\n\n```bash\nmytool --help\nmytool run\n```\n\n```\nignored\n```\n"
        self.assertEqual(CONTROLLER.spec_demo_command(text), "mytool --help\nmytool run")

    def test_no_demo_section_means_no_command(self) -> None:
        self.assertIsNone(CONTROLLER.spec_demo_command(self.SPEC + "## Acceptance and evidence\n- it works\n"))

    def test_a_demo_heading_inside_a_fence_does_not_count(self) -> None:
        text = self.SPEC + "```text\n## Demo\n```\n\n## Other\n\n```sh\nnot a demo\n```\n"
        self.assertIsNone(CONTROLLER.spec_demo_command(text))

    def test_a_demo_section_without_a_command_is_refused(self) -> None:
        for body in ("## Demo\n\nWe will show it.\n\n## Next\n\n```sh\nlater\n```\n", "## Demo\n\n```sh\n\n```\n"):
            with self.subTest(body=body), self.assertRaisesRegex(CONTROLLER.RunError, "## Demo"):
                CONTROLLER.spec_demo_command(self.SPEC + body)

    def test_the_transcript_is_redacted_capped_and_printable(self) -> None:
        token = "gh" + "p_" + "A1b2" * 8
        record = CONTROLLER.demo_transcript("tool", 0, False, "ok " + token + "\n" + "y" * 50000, "\x07warn\n",
                                            ROOT)
        text, redactions, truncated = record
        self.assertNotIn(token, text)
        self.assertIn("[redacted: GitHub token]", text)
        self.assertIn("\\x07warn", text)
        self.assertTrue(truncated)
        self.assertEqual(redactions, 1)
        self.assertLess(len(text), 2 * CONTROLLER.DEMO_STREAM_LIMIT + 1000)


if __name__ == "__main__":
    unittest.main()
