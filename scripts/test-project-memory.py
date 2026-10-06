#!/usr/bin/env python3
"""Local Markdown recall boundaries and startup references."""
from pathlib import Path
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import project_memory as memory


@unittest.skipUnless(hasattr(os, 'O_NOFOLLOW') and os.open in os.supports_dir_fd, 'safe recall is unsupported on this platform')
class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def note(self, path, body, metadata=None):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        if metadata:
            body = '<!-- agentsmith-memory: ' + json.dumps(metadata) + ' -->\n' + body
        p.write_text(body, encoding='utf-8')
        return p

    def test_legacy_unicode_and_hash(self):
        self.note('docs/research/a.md', '# Zürich\nCafé architecture')
        report = memory.search(self.root, 'café')
        self.assertTrue(report['complete'])
        self.assertEqual(report['schema_version'], 1)
        self.assertEqual(report['matches'][0]['title'], 'Zürich')
        self.assertEqual(len(report['matches'][0]['content_hash']), 64)
        self.assertIn('Café', memory.read(self.root, 'docs/research/a.md')['content'])

    def test_excludes_archives_captured_material_and_symlinks(self):
        for segment in ('_archive', 'archive', 'sources', 'artifacts', 'captured-sources',
                        'ecc-nasiko-sources-2026-10-06', 'vendor_artifacts_2026'):
            self.note(f'docs/research/{segment}/x.md', '# excluded\nneedle')
        outside = self.note('private.md', '# outside\nneedle')
        (self.root/'docs/research/link.md').symlink_to(outside)
        report = memory.search(self.root, 'needle')
        self.assertEqual(report['matches'], [])
        self.assertFalse(report['complete'])
        for path in ('private.md', '../private.md', 'docs/research/link.md', '/etc/passwd'):
            with self.assertRaises(memory.MemoryError):
                memory.read(self.root, path)

    def test_symlink_root_and_project_ancestor_rejected(self):
        actual = self.root/'actual'
        actual.mkdir()
        (self.root/'docs').symlink_to(actual, target_is_directory=True)
        with self.assertRaises(memory.MemoryError):
            memory.read(self.root, 'docs/research/x.md')
        alias = self.root/'alias'
        alias.symlink_to(actual, target_is_directory=True)
        with self.assertRaises(memory.MemoryError):
            memory.read(alias, 'docs/research/x.md')

    def test_bounds_distinguish_no_match(self):
        self.note('docs/research/a.md', '# A\nneedle')
        self.note('docs/research/b.md', '# B\nneedle')
        self.assertFalse(memory.search(self.root, 'absent', max_documents=1)['complete'])
        self.assertFalse(memory.search(self.root, 'needle', max_bytes=3)['complete'])
        self.assertFalse(memory.search(self.root, 'needle', timeout=0)['complete'])
        self.assertTrue(memory.search(self.root, 'absent')['complete'])

    def test_startup_branch_links_drift_supersession_and_no_bodies(self):
        self.note('docs/research/a.md', '# Reference\nPRIVATE BODY')
        self.note('.harness/handoffs/a.md', '# Handoff\nPRIVATE HANDOFF',
                  {'version':1, 'branch':'feature', 'commit':'old', 'links':['docs/research/a.md']})
        self.assertEqual(memory.startup(self.root, branch='other')['references'], [])
        report = memory.startup(self.root, branch='feature', commit='new')
        self.assertEqual(len(report['references']), 2)
        self.assertIn('drift', report['output'].lower())
        self.assertNotIn('PRIVATE', report['output'])
        self.assertLessEqual(len(report['output']), 2000)
        self.note('.harness/handoffs/a.md', '# Handoff',
                  {'version':1, 'branch':'feature', 'superseded_by':'.harness/handoffs/b.md'})
        self.assertEqual(memory.startup(self.root, branch='feature')['references'], [])

    def test_legacy_branch_is_explicit_and_latest(self):
        self.note('.harness/handoffs/a.md', '# Legacy\n**Branch / version:** feature abcdef123456\n')
        self.assertEqual(len(memory.startup(self.root, branch='feature')['references']), 1)
        self.assertEqual(memory.startup(self.root, branch='unrelated')['references'], [])
        self.note('.harness/handoffs/b.md', '# Unknown branch\nfeature')
        self.assertEqual(len(memory.startup(self.root, branch='feature')['references']), 1)

    def test_actual_scaffold_branch_format(self):
        self.note('.harness/handoffs/scaffold.md', '# Handoff — task\n\n'
                  '**Branch:** feature   **HEAD:** abcdef123456   **Uncommitted files:** 0\n'
                  '- **Branch / commit:** feature / abcdef123456\n')
        report = memory.startup(self.root, branch='feature', commit='987654321abc')
        self.assertEqual(len(report['references']), 1)
        self.assertIn('drift', report['output'].lower())

    def test_startup_total_budget_includes_post_discovery(self):
        with patch.object(memory, '_discover', return_value=([], [], 0)), \
             patch.object(memory.time, 'monotonic', side_effect=[0, 0, 3]):
            report = memory.startup(self.root, branch='feature')
        self.assertFalse(report['complete'])
        self.assertTrue(report['output'])

    def test_redaction_and_controls(self):
        token = 'ghp_' + 'abcdefghijklmnopqrstuvwxyz1234'
        self.note('docs/feedback/a.md', '# '+token+'\x1b[31m\n'+token+'\x00')
        report = memory.read(self.root, 'docs/feedback/a.md')
        self.assertNotIn(token, json.dumps(report))
        self.assertNotIn('\x1b', report['title'])
        self.assertNotIn('\x00', report['content'])

    def test_stale_link_hash_and_invalid_metadata(self):
        self.note('docs/research/a.md', '# Current')
        self.note('.harness/handoffs/a.md', '# Handoff', {'version':1,'branch':'feature',
                   'links':[{'path':'docs/research/a.md','content_hash':'0'*64}]})
        report = memory.startup(self.root, branch='feature')
        self.assertIn('hash', report['output'].lower())
        self.note('docs/feedback/b.md', '<!-- agentsmith-memory: {broken} -->\n# Bad')
        self.assertFalse(memory.search(self.root, 'Bad')['complete'])

    def test_metadata_boolean_and_duplicate_keys_rejected(self):
        for header in ('{"version":true,"branch":"feature"}',
                       '{"version":1,"branch":"feature","status":"archived","status":"active"}'):
            self.note('.harness/handoffs/a.md', '<!-- agentsmith-memory: '+header+' -->\n# Handoff')
            report = memory.search(self.root, 'Handoff')
            self.assertFalse(report['complete'])
            self.assertEqual(report['matches'], [])
            self.assertEqual(memory.startup(self.root, branch='feature')['references'], [])

    def test_diagnostics_bounded_with_omitted_count(self):
        directory = self.root/'docs/research'
        directory.mkdir(parents=True)
        for i in range(100):
            (directory/f'{i}.md').symlink_to(self.root/'missing')
        report = memory.search(self.root, 'absent')
        self.assertFalse(report['complete'])
        self.assertLessEqual(len(report['diagnostics']), 21)
        self.assertIn('80', report['diagnostics'][-1])
        startup = memory.startup(self.root, branch='feature')
        self.assertFalse(startup['complete'])
        self.assertIn('80', startup['diagnostics'][-1])

    def test_startup_full_paths_and_display_budget(self):
        prefix = 'docs/research/' + '/'.join(['segment1234567890']*22)
        linked = prefix + '/reference.md'
        self.note(linked, '# Reference')
        self.note('.harness/handoffs/a.md', '# Handoff',
                  {'version':1,'branch':'feature','commit':'abcdef1','links':[linked]})
        report = memory.startup(self.root, branch='feature', commit='9999999')
        self.assertIn(linked, report['output'])
        self.assertIn('specs remain authoritative', report['output'])
        huge = 'docs/feedback/' + '/'.join(['segment1234567890']*48) + '/reference.md'
        self.note(huge, '# Huge path')
        self.note('.harness/handoffs/a.md', '# Handoff',
                  {'version':1,'branch':'feature','commit':'abcdef1','links':[linked, huge]})
        report = memory.startup(self.root, branch='feature', commit='9999999')
        self.assertEqual(len(report['references']), 2)
        self.assertFalse(report['complete'])
        self.assertIn('display', report['output'].lower())
        self.assertIn('drift', report['output'].lower())
        self.assertLessEqual(len(report['output']), 2000)


class UnsupportedTests(unittest.TestCase):
    def test_unsupported_startup_is_incomplete(self):
        with patch.object(memory, '_flags', side_effect=memory.MemoryError('unsupported')):
            report=memory.startup(Path.cwd(),branch='test')
        self.assertFalse(report['complete'])
        self.assertEqual(report['references'],[])

if __name__ == '__main__':
    unittest.main()
