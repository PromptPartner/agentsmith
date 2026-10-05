#!/usr/bin/env python3
"""Evidence integrity tests: fixture records cannot stand in for native qualification."""
import importlib.util
import pathlib
import json
import tempfile
import unittest
from unittest import mock
spec = importlib.util.spec_from_file_location('recovery', pathlib.Path(__file__).with_name('qualification-recovery.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class EvidenceTests(unittest.TestCase):
    def test_expanded_matrix(self):
        ids = m.required_variants()
        self.assertEqual(len(ids), len(set(ids)))
        for stage in ('making', 'verifying', 'checking'):
            for case in ('R01', 'R02', 'R04'):
                self.assertIn(f'{case}/{stage}', ids)
        self.assertIn('R08/scope-conflict', ids)
        self.assertIn('R07/claude', ids)
        self.assertIn('R07/codex', ids)
        self.assertIn('R09/locked', ids)

    def test_raw_hash_tampering_and_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            raw = root / 'raw.txt'
            raw.write_text('actual evidence')
            record = {'variant': 'normal/codex-claude', 'result': 'pass', 'evidence_kind': 'fixture',
                      'artifacts': {'raw.txt': m.digest(raw)}}
            with self.assertRaises(ValueError): m.validate_records(root, [record])
            with self.assertRaises(ValueError): m.validate_records(root, [record, record])
            raw.write_text('replaced evidence')
            with self.assertRaises(ValueError): m.validate_records(root, [record])

    def test_false_pass_and_native_claim_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            record = {'variant': 'R01/making', 'result': 'pass', 'evidence_kind': 'fixture', 'artifacts': {}}
            with self.assertRaises(ValueError): m.validate_records(root, [record])
            record['result'] = 'not-run'
            m.validate_records(root, [record])
            with self.assertRaises(ValueError): m.validate_records(root, [record], require_complete=True)
            with self.assertRaises(ValueError): m.validate_records(root, [record], require_native=True)


    def proof(self, root, variant='normal/codex-claude'):
        sources=('scripts/autonomous-run.py','native_launcher.py','windows_verifier_sandbox.py','scripts/qualification-recovery.py','docs/26-native-qualification-contract.md')
        snapshot={}
        for name in sources:
            p=root/'source'/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text('frozen source '+name)
            snapshot[p.relative_to(root).as_posix()]=m.digest(p)
        m.write(root/'snapshot.json',snapshot)
        m.write(root/'red.json',{'exit':1})
        m.write(root/'state.json',{'status':'accepted','attempt':1,'accepted_commit':'a'*40,'base_head':'b'*40,'spec_sha256':'s','manifest_sha256':'m'})
        m.write(root/'obs.json',[{'case_started':variant,'pair':m.expected_pair(variant),'monotonic_ns':1}])
        m.write(root/'case-contract.json',{'schema_version':1,'variant':variant,'pair':m.expected_pair(variant)})
        m.write(root/'attempt-1-checker-receipt.json',{'commit':'a'*40,'status':'accepted','evidence':['raw proof'],'unresolved':[]})
        (root/'attempt-1-verify.txt').write_text('raw verifier output')
        m.write(root/'attempt-1-verify.json',{'candidate_commit':'a'*40,'exit_code':0,'checker_receipt_sha256':m.digest(root/'attempt-1-checker-receipt.json'),'output_sha256':m.digest(root/'attempt-1-verify.txt'),'base_commit':'b'*40,'spec_sha256':'s','manifest_sha256':'m','runtime_sha256':{'controller':snapshot['source/scripts/autonomous-run.py'],'launcher':snapshot['source/native_launcher.py']}})
        record={'variant':variant,'result':'pass','evidence_kind':'fixture','proof':{'state':'state.json','red_control':'red.json','observations':'obs.json','source_snapshot':'snapshot.json','case_contract':'case-contract.json'}}
        self.rehash(root,record)
        return record

    def rehash(self,root,record):
        record['artifacts']={p.relative_to(root).as_posix():m.digest(p) for p in root.rglob('*') if p.is_file()}

    def test_windows_relative_evidence_paths_use_portable_contract_keys(self):
        original_relative_to = pathlib.Path.relative_to
        def windows_relative_to(path, *arguments, **kwargs):
            relative = original_relative_to(path, *arguments, **kwargs)
            return pathlib.PureWindowsPath(*relative.parts)
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            with mock.patch.object(pathlib.Path, 'relative_to', windows_relative_to):
                record = self.proof(root)
                m.validate_records(root, [record])
                snapshot = json.loads((root / 'snapshot.json').read_text())
                self.assertIn('source/scripts/autonomous-run.py', snapshot)
                self.assertTrue(all('\\' not in name for name in record['artifacts']))

    def test_stale_candidate_is_not_accepted_even_with_new_hash(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d); r=self.proof(root)
            m.validate_records(root,[r])
            m.write(root/'attempt-1-checker-receipt.json',{'commit':'b'*40}); self.rehash(root,r)
            with self.assertRaisesRegex(ValueError,'stale candidate'): m.validate_records(root,[r])

    def test_duplicate_usage_and_orphan_descendants_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d); r=self.proof(root,'R07/codex')
            m.write(root/'state.json',{'status':'escalated','usage_accounting_incomplete':True})
            m.write(root/'obs.json',[{'case_started':'R07/codex','pair':m.expected_pair('R07/codex'),'monotonic_ns':1},{'injection':'R07','variant':'R07/codex','monotonic_ns':100,'controller_pid':5,'state':{'stage':'making'}}])
            (root/'events.jsonl').write_text('\n'.join([json.dumps({'event':'usage_recorded'})]*2))
            self.rehash(root,r)
            with self.assertRaisesRegex(ValueError,'duplicate'): m.validate_records(root,[r])
            r['variant']='R01/making'
            m.write(root/'case-contract.json',{'schema_version':1,'variant':r['variant'],'pair':m.expected_pair(r['variant'])})
            m.write(root/'state.json',{'status':'interrupted'})
            m.write(root/'obs.json',[{'case_started':'R01/making','pair':m.expected_pair('R01/making'),'monotonic_ns':1},{'injection':'R01','variant':'R01/making','monotonic_ns':100,'controller_pid':5,'active_pid':6,'state':{'stage':'making'}}, {'stop_ack_ns':200,'stop_acknowledged':True,'fault_status':'interrupted'}, {'controller_termination_ns':300,'automatic_extinction_ns':400}, {'group':6,'members':['6 6 S'],'monotonic_ns':500}])
            self.rehash(root,r)
            with self.assertRaisesRegex(ValueError,'orphan'): m.validate_records(root,[r])

    def test_fixture_native_promotion_and_fake_source_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d); r=self.proof(root)
            with self.assertRaises(ValueError): m.validate_records(root,[r],require_native=True)
            r['evidence_kind']='native'
            with self.assertRaises(ValueError): m.validate_records(root,[r])
            r['evidence_kind']='fixture'; m.write(root/'snapshot.json',{'invented':'hash'}); self.rehash(root,r)
            with self.assertRaisesRegex(ValueError,'source snapshot'): m.validate_records(root,[r])

    def test_escaped_proof_rejected_before_read(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d); r=self.proof(root)
            r['artifacts']['../outside']='fake'
            with self.assertRaisesRegex(ValueError,'escaped'): m.validate_records(root,[r])


    def test_failed_verifier_or_checker_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d); r=self.proof(root)
            v=json.loads((root/'attempt-1-verify.json').read_text()); v['exit_code']=1
            m.write(root/'attempt-1-verify.json',v); self.rehash(root,r)
            with self.assertRaisesRegex(ValueError,'failed verifier'): m.validate_records(root,[r])
            v['exit_code']=0; m.write(root/'attempt-1-verify.json',v)
            c=json.loads((root/'attempt-1-checker-receipt.json').read_text()); c['status']='rejected'
            m.write(root/'attempt-1-checker-receipt.json',c); self.rehash(root,r)
            with self.assertRaisesRegex(ValueError,'failed verifier'): m.validate_records(root,[r])


    def test_exact_variant_cannot_be_relabelled(self):
        for original in ('normal/codex-claude','R08/changed-spec','R09/wrong-path','R03/checker-kill'):
            with self.subTest(original=original), tempfile.TemporaryDirectory() as d:
                root=pathlib.Path(d); r=self.proof(root,original)
                case=original.split('/')[0]
                if case!='normal':
                    m.write(root/'state.json',{'status':'escalated'})
                    obs=[{'case_started':original,'pair':m.expected_pair(original),'monotonic_ns':1},{'injection':case,'variant':original,'monotonic_ns':100,'controller_pid':5,'active_pid':6,'state':{'stage':'checking'}}]
                    if case=='R03': obs += [{'controller_termination_ns':200,'automatic_extinction_ns':300,'fault_status':'escalated'}, {'group':6,'members':[],'monotonic_ns':300}]
                    m.write(root/'obs.json',obs); self.rehash(root,r)
                m.validate_records(root,[r])
                for target in m.required_variants():
                    if target.startswith(case+'/') and target!=original:
                        clone=json.loads(json.dumps(r)); clone['variant']=target
                        with self.subTest(target=target), self.assertRaises(ValueError): m.validate_records(root,[clone])

if __name__ == '__main__': unittest.main()
