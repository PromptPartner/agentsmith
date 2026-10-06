#!/usr/bin/env python3
"""Selection and disclosure contracts; configuration writes use temporary homes."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agentsmith as a
import unittest
import json
import tempfile
import subprocess
from unittest.mock import patch

class Effects(unittest.TestCase):
    def test_complete_disclosure(self):
        rows = a.capability_effects({'handoff_hooks': True, 'mcp': ['context7']})
        self.assertEqual(set(rows), {'handoff_hooks', 'mcp'})
        for row in rows.values():
            self.assertEqual(set(row), {'version', 'files', 'process_control', 'egress', 'context', 'records'})
        self.assertIn('provider', rows['handoff_hooks']['egress'])

    def test_expansion_requires_explicit_selection(self):
        old = a.capability_effects({'hooks': True})
        old['hooks']['version'] = 0
        args = a.parser().parse_args(['install', '--profile', 'software-dev'])
        with self.assertRaises(a.CliError):
            a.review_capability_effects({'capabilities': {'hooks': True}, 'effects': old}, args)
        args.with_hooks = True
        a.review_capability_effects({'capabilities': {'hooks': True}, 'effects': old}, args)

    def test_partial_effect_record_requires_selection(self):
        args = a.parser().parse_args(['install', '--profile', 'software-dev'])
        with self.assertRaises(a.CliError):
            a.review_capability_effects({'capabilities': {'hooks': True}, 'effects': {}}, args)

    def test_candidate_expansion_rejected_before_installer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            changed = a.capability_effects({'hooks': True})
            changed['hooks']['version'] = 2
            (path / 'agentsmith.py').write_text('CAPABILITY_EFFECTS = ' + repr(changed))
            with self.assertRaises(a.CliError):
                a.check_candidate_effects(path, {'capabilities': {'hooks': True}, 'effects': a.capability_effects({'hooks': True})})

    def test_unchanged_and_legacy_remain_durable(self):
        args = a.parser().parse_args(['install', '--profile', 'software-dev'])
        for record in ({'capabilities': {'hooks': True}}, {'capabilities': {'hooks': True}, 'effects': a.capability_effects({'hooks': True})}):
            a.review_capability_effects(record, args)

class Ownership(unittest.TestCase):
    def test_real_install_preview_discloses_before_any_write(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(a.ROOT / 'agentsmith.py'), 'install', '--agent', 'codex', '--profile', 'software-dev', '--with-handoff-hooks', '--dry-run', '--target', directory], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Capability handoff_hooks', result.stdout)
            self.assertLess(result.stdout.index('Capability handoff_hooks'), result.stdout.index('would reconcile'))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_registration_preserves_foreign_siblings_and_suffix_mentions(self):
        data = {'hooks': {'Stop': [{'hooks': [
            {'command': 'python agentsmith.py hook context-budget-nudge'},
            {'command': 'foreign-tool --label context-budget-nudge'}]}]}}
        a.append_unique_hook(data, 'Stop', 'python /new/agentsmith.py hook context-budget-nudge')
        commands = [h['command'] for group in data['hooks']['Stop'] for h in group['hooks']]
        self.assertIn('foreign-tool --label context-budget-nudge', commands)
        self.assertEqual(len(commands), 2)

    def test_uninstall_preserves_foreign_handler_in_shared_group(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'hooks.json'
            path.write_text(json.dumps({'hooks': {'SessionStart': [{'matcher': 'startup', 'hooks': [
                {'type': 'command', 'command': 'python agentsmith.py hook old'},
                {'type': 'command', 'command': 'foreign-tool'}]}]}}))
            a.remove_owned_hooks(path, dry_run=False)
            self.assertEqual(json.loads(path.read_text())['hooks']['SessionStart'][0]['hooks'][0]['command'], 'foreign-tool')

if __name__ == '__main__': unittest.main()
