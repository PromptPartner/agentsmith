#!/usr/bin/env python3
"""Offline qualification evidence acceptance regressions."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import qualification as q
ROOT = Path(__file__).resolve().parent.parent


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='qualification test ')
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name).resolve()
        self.raw = self.path / 'raw.log'
        self.raw.write_text('synthetic captured attempt and successful control\n')
        proof = q.artifact(self.raw)
        self.inventory = {'sources': [proof], 'cells': [{
            'host': 'macos', 'kernel': 'fixture-kernel', 'architecture': 'arm64',
            'client': 'codex', 'version': 'synthetic-1', 'backend': 'fixture',
            'role': 'maker', 'policy': proof, 'tool_inventory': proof,
            'tools': [{'name': 'apply_patch', 'mutation': True, 'read': False,
                       'enabled': True, 'evidence': proof},
                      {'name': 'read_file', 'mutation': False, 'read': True,
                       'enabled': True, 'evidence': proof},
                      {'name': 'disabled_write', 'mutation': True, 'read': False,
                       'enabled': False, 'evidence': proof}],
            'layouts': {layout: proof for layout in q.LAYOUTS}, 'prerequisites': True}]}
        tool_snapshot = self.path / 'tool-inventory.json'
        cell = self.inventory['cells'][0]
        tool_snapshot.write_text(json.dumps({'scope': 'built-in-file-tools', 'client': cell['client'],
            'version': cell['version'], 'policy_sha256': cell['policy']['sha256'], 'complete': True,
            'tools': [{k: t[k] for k in ('name', 'mutation', 'read', 'enabled')} for t in cell['tools']]}))
        cell['tool_inventory'] = q.artifact(tool_snapshot)
        self.manifest = q.build_manifest(self.inventory)
        self.ledger = q.new_ledger(self.manifest)

    def passing(self, variant, kind='native'):
        value = {'variant': variant['id'], 'result': 'pass', 'kind': kind,
                 'reason': 'synthetic acceptance-schema control only', 'artifacts': [q.artifact(self.raw)],
                 'control_artifacts': [q.artifact(self.raw)], 'attempt': {**{k: variant[k] for k in ('operation', 'target', 'tool', 'payload', 'alias')},
                             'input': ['fixture', 'probe'], 'launch_observed': True},
                 'control': {'operation': variant['operation'], 'result': 'pass',
                             'input': ['fixture', 'allowed-control'], 'launch_observed': True},
                 'observation': 'permission-denied',
                 'source_sha256': q.digest(self.inventory['sources']),
                 'policy_sha256': self.inventory['cells'][0]['policy']['sha256']}
        if variant['case'] == 'C01':
            value['observation'] = 'allowed-edit-commit'
        if variant['operation'] == 'candidate-edit':
            value['observation'] = 'candidate-rejected'
        if variant['case'] == 'C07':
            value.update(observation='bounded-policy', effective_policy_bounded=True,
                         policy_evaluation_reached=True, hook_sentinel_fired=False,
                         connector_sentinel_fired=False)
        if variant['operation'] == 'read-inventory':
            value['observation'] = 'read-inventory-observed'
        if variant['tool'] == 'verifier' and variant['case'] == 'C08':
            value['observation'] = 'verifier-isolated'
        if variant['operation'] == 'receipt-parse-bind':
            value['observation'] = 'receipt-rejected'
        if variant['operation'] == 'missing-prerequisite':
            value['observation'] = 'launch-refused'
        if variant['applicability'] == 'excluded':
            value.update(exclusion=variant['reason'], applicability_artifacts=[q.artifact(self.raw), self.inventory['cells'][0]['tool_inventory']])
        return value

    def full(self, kind='native'):
        value = copy.deepcopy(self.ledger)
        value['records'] = [self.passing(v, kind) for v in self.manifest['variants']]
        return value

    def test_all_cases_operations_and_layouts_expanded(self):
        rows = self.manifest['variants']
        self.assertEqual({r['case'] for r in rows}, {f'C{i:02}' for i in range(1, 11)})
        self.assertEqual({r['layout'] for r in rows}, set(q.LAYOUTS))
        c02 = [r for r in rows if r['case'] == 'C02']
        self.assertEqual(len(c02), 2 * 4 * len(q.TARGETS))
        self.assertEqual(len([r for r in rows if r['case'] == 'C07']), 2 * 5)
        self.assertEqual(len(rows), len({r['id'] for r in rows}))

    def test_initial_native_not_run_retained(self):
        self.assertTrue(all(r['result'] == 'not-run' for r in self.ledger['records']))
        self.assertFalse(q.check(self.manifest, self.ledger)['qualified'])

    def test_manifest_shrink_cannot_redefine_completeness(self):
        value = copy.deepcopy(self.manifest)
        value['variants'].pop()
        value['sha256'] = q.digest({k: v for k, v in value.items() if k != 'sha256'})
        with self.assertRaises(q.EvidenceError):
            q.check(value, self.full())

    def test_missing_rows_rejected_by_gate(self):
        value = self.full()
        value['records'].pop()
        self.assertFalse(q.check(self.manifest, value)['complete'])

    def test_duplicate_rows_rejected(self):
        value = self.full()
        value['records'].append(copy.deepcopy(value['records'][0]))
        with self.assertRaises(q.EvidenceError):
            q.check(self.manifest, value)

    def test_nonpassing_retained_and_blocks(self):
        for result in ('not-run', 'fail', 'undetermined'):
            with self.subTest(result=result):
                value = self.full()
                value['records'][0]['result'] = result
                self.assertFalse(q.check(self.manifest, value)['complete'])
                q.validate_ledger(self.manifest, value)

    def test_fixtures_never_qualify_native(self):
        value = self.full('fixture')
        self.assertFalse(q.check(self.manifest, value)['qualified'])
        result = q.check(self.manifest, value, require_native=False)
        self.assertTrue(result['complete'])
        self.assertFalse(result['qualified'])

    def test_full_synthetic_native_schema_control(self):
        self.assertTrue(q.check(self.manifest, self.full())['complete'])
        self.assertFalse(q.check(self.manifest, self.full())['qualified'])

    def test_exclusion_requires_exact_applicability(self):
        value = self.full()
        excluded = next(r for r in value['records'] if 'exclusion' in r)
        excluded.pop('applicability_artifacts')
        with self.assertRaises(q.EvidenceError):
            q.check(self.manifest, value)
        value = self.full()
        value['records'][0]['exclusion'] = 'model-refusal'
        with self.assertRaises(q.EvidenceError):
            q.check(self.manifest, value)

    def test_model_refusal_not_policy_denial(self):
        for observation in ('model-refusal', 'provider-failure', 'missing-tool', 'invalid-payload'):
            value = self.full()
            value['records'][0]['observation'] = observation
            with self.assertRaises(q.EvidenceError):
                q.check(self.manifest, value)

    def test_c07_requires_policy_and_no_sentinel_execution(self):
        for key in ('policy_evaluation_reached', 'effective_policy_bounded',
                    'hook_sentinel_fired', 'connector_sentinel_fired'):
            value = self.full()
            row = next(r for r in value['records'] if '/C07/' in r['variant'])
            row[key] = not row[key]
            with self.assertRaises(q.EvidenceError):
                q.check(self.manifest, value)

    def test_unknown_observation_and_wrong_operation_rejected(self):
        value = self.full()
        value['records'][0]['observation'] = 'looks-safe'
        with self.assertRaises(q.EvidenceError):
            q.check(self.manifest, value)
        value = self.full()
        value['records'][0]['attempt']['operation'] = 'different-operation'
        with self.assertRaises(q.EvidenceError):
            q.check(self.manifest, value)

    def test_no_launch_or_same_operation_control_rejected(self):
        for section, key, wrong in (('attempt', 'launch_observed', False),
                                    ('control', 'operation', 'different'),
                                    ('control', 'result', 'undetermined')):
            value = self.full()
            value['records'][0][section][key] = wrong
            with self.assertRaises(q.EvidenceError):
                q.check(self.manifest, value)

    def test_exclusions_cannot_use_unrelated_raw_artifact(self):
        other = self.path / 'unrelated.log'
        other.write_text('unrelated applicability claim')
        value = self.full()
        row = next(r for r in value['records'] if 'exclusion' in r)
        row['applicability_artifacts'] = [q.artifact(other)]
        with self.assertRaises(q.EvidenceError):
            q.check(self.manifest, value)

    def test_source_policy_and_raw_hashes_bound(self):
        for field in ('source_sha256', 'policy_sha256'):
            value = self.full()
            value['records'][0][field] = '0' * 64
            with self.assertRaises(q.EvidenceError):
                q.check(self.manifest, value)
        self.raw.write_text('changed after frozen snapshot')
        with self.assertRaises(q.EvidenceError):
            q.check(self.manifest, self.ledger)

    def test_version_and_tool_changes_invalidate_manifest(self):
        value = copy.deepcopy(self.manifest)
        value['inventory']['cells'][0]['version'] = 'new-version'
        with self.assertRaises(q.EvidenceError):
            q.check(value, self.full())

    def test_no_positive_control_no_pass(self):
        value = self.full()
        value['records'][0].pop('control_artifacts')
        with self.assertRaises(q.EvidenceError):
            q.check(self.manifest, value)

    def test_observation_cannot_be_overwritten(self):
        first = self.passing(self.manifest['variants'][0])
        value = q.record(self.manifest, self.ledger, first)
        with self.assertRaises(q.EvidenceError):
            q.record(self.manifest, value, first)
        self.assertEqual(self.ledger['records'][0]['result'], 'not-run')

    def test_fixture_and_native_records_remain_distinct(self):
        first = self.passing(self.manifest['variants'][0], 'fixture')
        value = q.record(self.manifest, self.ledger, first)
        self.assertEqual(len(value['records']), len(self.ledger['records']) + 1)
        self.assertFalse(q.check(self.manifest, value)['complete'])

    def test_unsupported_host_never_qualifies(self):
        self.inventory['cells'][0]['host'] = 'windows'
        manifest = q.build_manifest(self.inventory)
        ledger = q.new_ledger(manifest)
        self.assertEqual({r['case'] for r in manifest['variants']}, {'C10'})
        self.assertTrue(any(b['reason'] == 'unsupported cells cannot qualify' for b in q.check(manifest, ledger)['blockers']))

    def test_incomplete_tool_inventory_blocks_gate(self):
        cell = self.inventory['cells'][0]
        snapshot = self.path / 'incomplete-tools.json'
        value = json.loads(Path(cell['tool_inventory']['path']).read_text())
        value['complete'] = False
        snapshot.write_text(json.dumps(value))
        cell['tool_inventory'] = q.artifact(snapshot)
        manifest = q.build_manifest(self.inventory)
        result = q.check(manifest, q.new_ledger(manifest))
        self.assertTrue(any('coverage unproven' in b['reason'] for b in result['blockers']))

    def test_shell_cannot_replace_builtin_inventory(self):
        self.inventory['cells'][0]['tools'][0]['name'] = 'exec_command'
        with self.assertRaises(q.EvidenceError):
            q.build_manifest(self.inventory)

    def test_duplicate_cells_and_incomplete_inventory_rejected(self):
        self.inventory['cells'].append(copy.deepcopy(self.inventory['cells'][0]))
        with self.assertRaises(q.EvidenceError):
            q.build_manifest(self.inventory)

    def test_cli_real_manifest_init_record_check_and_no_overwrite(self):
        def run(*args):
            return subprocess.run([sys.executable, str(ROOT / 'scripts/qualification-evidence.py'), *args],
                                  capture_output=True, text=True)
        inventory = self.path / 'inventory.json'
        inventory.write_text(json.dumps(self.inventory))
        manifest = self.path / 'manifest.json'
        ledger = self.path / 'ledger.json'
        report = self.path / 'report.json'
        self.assertEqual(run('manifest', '--inventory', str(inventory), '--output', str(manifest)).returncode, 0)
        self.assertEqual(run('init', '--manifest', str(manifest), '--output', str(ledger)).returncode, 0)
        entry = self.path / 'entry.json'
        entry.write_text(json.dumps(self.passing(self.manifest['variants'][0], 'fixture')))
        next_ledger = self.path / 'ledger-2.json'
        self.assertEqual(run('record', '--manifest', str(manifest), '--ledger', str(ledger), '--entry', str(entry), '--output', str(next_ledger)).returncode, 0)
        self.assertEqual(run('check', '--manifest', str(manifest), '--ledger', str(next_ledger), '--output', str(report)).returncode, 1)
        self.assertFalse(json.loads(report.read_text())['qualified'])
        previous = ledger.read_bytes()
        self.assertEqual(run('init', '--manifest', str(manifest), '--output', str(ledger)).returncode, 2)
        self.assertEqual(ledger.read_bytes(), previous)


if __name__ == '__main__':
    unittest.main()
