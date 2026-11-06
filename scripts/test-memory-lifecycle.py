#!/usr/bin/env python3
"""Exercise installed startup registration and reference delivery across clients."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(hasattr(os, 'O_NOFOLLOW') and os.open in os.supports_dir_fd, 'safe recall is unsupported on this platform')
class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.target = self.base / 'project ü'
        self.target.mkdir()
        self.env = {**os.environ, 'HOME': str(self.base / 'home'), 'CODEX_HOME': str(self.base / 'codex')}
        subprocess.run(['git','init','-q','-b','memory-test',str(self.target)], check=True)
        note = self.target / '.harness/handoffs/handoff.md'
        note.parent.mkdir(parents=True)
        note.write_text('# Recover café\n<!-- agentsmith-memory: {"version":1,"branch":"memory-test"} -->\nPRIVATE BODY SENTINEL\n')

    def tearDown(self): self.temp.cleanup()
    def cli(self, *args, input=None):
        return subprocess.run([sys.executable, str(ROOT / 'agentsmith.py'), *args], env=self.env, input=input, text=True, capture_output=True, cwd=self.target)
    def install(self, *flags):
        result = self.cli('install','--agent','native','--profile','software-dev','--target',str(self.target), *flags)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    def payload(self, source='startup'):
        return json.dumps({'hook_event_name':'SessionStart','source':source,'cwd':str(self.target)})
    def test_manual_cli_and_opt_in(self):
        self.install()
        self.assertEqual(self.cli('hook','memory-startup',input=self.payload()).stdout,'')
        result = self.cli('memory','search','café','--json')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['matches'][0]['path'],'.harness/handoffs/handoff.md')
        self.install('--with-memory-startup')
        self.install() # unchanged selection remains durable
        for config in (self.target/'.claude/settings.json', self.target/'.codex/hooks.json'):
            groups = json.loads(config.read_text())['hooks']['SessionStart']
            own = [g for g in groups if any('hook memory-startup' in h.get('command','') for h in g['hooks'])]
            self.assertEqual(len(own),1)
            self.assertEqual(own[0]['matcher'],'^(startup|resume)$')
            # Invoke the exact configured launcher, not an in-memory function.
            command = own[0]['hooks'][0]['command']
            observed = subprocess.run(command, shell=True, cwd=self.target, env=self.env,input=self.payload(),text=True,capture_output=True)
            self.assertEqual(observed.returncode,0,observed.stderr)
            output=json.loads(observed.stdout)['hookSpecificOutput']
            self.assertEqual(output['hookEventName'],'SessionStart')
            self.assertIn('handoff.md',output['additionalContext'])
            self.assertNotIn('PRIVATE BODY SENTINEL',output['additionalContext'])
        for source in ('compact','clear','bogus'):
            self.assertEqual(self.cli('hook','memory-startup',input=self.payload(source)).stdout,'')
        self.assertEqual(self.cli('hook','memory-startup',input='malformed').returncode,0)
        self.install('--without-memory-startup')
        self.assertEqual(self.cli('hook','memory-startup',input=self.payload()).stdout,'')
        for config in (self.target/'.claude/settings.json', self.target/'.codex/hooks.json'):
            if config.exists(): self.assertNotIn('hook memory-startup',config.read_text())

    @unittest.skipIf(os.name == 'nt', 'the slow Git stand-in is a shell script')
    def test_a_slow_git_still_finds_the_handoff(self):
        # macOS run 42276115183: the hook printed nothing. Reading the branch had a 0.25 s limit, and
        # a cold or loaded runner can take longer to start git (on macOS /usr/bin/git is an xcrun
        # shim); without the branch no handoff matches, so the context was silently empty.
        import shutil
        shim = self.base / 'slow-git'
        shim.mkdir()
        (shim / 'git').write_text(f'#!/bin/sh\nsleep 0.5\nexec {shutil.which("git")} "$@"\n')
        (shim / 'git').chmod(0o755)
        self.install('--with-memory-startup')
        groups = json.loads((self.target/'.claude/settings.json').read_text())['hooks']['SessionStart']
        command = [g for g in groups if any('hook memory-startup' in h.get('command','') for h in g['hooks'])][0]['hooks'][0]['command']
        slow = {**self.env, 'PATH': str(shim) + os.pathsep + self.env['PATH']}
        observed = subprocess.run(command, shell=True, cwd=self.target, env=slow, input=self.payload(), text=True, capture_output=True)
        self.assertEqual(observed.returncode, 0, observed.stderr)
        self.assertIn('handoff.md', observed.stdout, f'stdout={observed.stdout!r} stderr={observed.stderr!r}')

    def test_project_decline_preserves_other_project_registration(self):
        self.install('--with-memory-startup')
        other = self.base / 'other'
        other.mkdir()
        result = self.cli('install','--agent','native','--profile','software-dev','--target',str(other),'--without-memory-startup')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('hook memory-startup', (self.target/'.claude/settings.json').read_text())
        self.assertNotIn('hook memory-startup', (self.base/'home/.claude/settings.json').read_text())

    def test_global_handler_defers_to_project_choice_and_uninstall(self):
        result = self.cli('install', '--agent', 'native', '--global', '--with-memory-startup')
        self.assertEqual(result.returncode,0,result.stderr)
        global_groups = json.loads((self.base/'codex/hooks.json').read_text())['hooks']['SessionStart']
        command = global_groups[0]['hooks'][0]['command']
        def run():
            return subprocess.run(command,shell=True,cwd=self.target,env=self.env,input=self.payload(),text=True,capture_output=True)
        self.assertIn('handoff.md',run().stdout)
        self.install('--with-memory-startup')
        self.assertEqual(run().stdout,'') # project handler owns this selection
        self.install('--without-memory-startup')
        self.assertEqual(run().stdout,'')
        self.install('--with-memory-startup')
        self.install('--uninstall')
        self.assertEqual(self.cli('hook','memory-startup',input=self.payload()).stdout,'')

class Watchdog(unittest.TestCase):
    def test_timeout_is_advisory(self):
        import io
        from unittest.mock import patch
        from contextlib import redirect_stdout
        sys.path.insert(0,str(ROOT))
        import agentsmith as a
        args=a.parser().parse_args(['hook','memory-startup'])
        payload=json.dumps({'hook_event_name':'SessionStart','source':'startup','cwd':str(ROOT)})
        output=io.StringIO()
        with patch('sys.stdin',io.StringIO(payload)), patch.object(a.subprocess,'run',side_effect=subprocess.TimeoutExpired('recall',2)), redirect_stdout(output):
            self.assertEqual(a.cmd_memory_startup_hook(args),0)
        self.assertIn('timed out',json.loads(output.getvalue())['hookSpecificOutput']['additionalContext'])

    def test_a_git_timeout_is_reported_not_silent(self):
        import io
        from unittest.mock import patch
        from contextlib import redirect_stdout
        sys.path.insert(0,str(ROOT))
        import agentsmith as a
        with patch.object(a.subprocess,'run',side_effect=subprocess.TimeoutExpired('git',a.MEMORY_GIT_TIMEOUT_SECONDS)):
            self.assertEqual(a.memory_git_identity(ROOT),(None,None,True))
        args=a.parser().parse_args(['memory','startup','--target',str(ROOT),'--json'])
        output=io.StringIO()
        with patch.object(a,'memory_git_identity',return_value=(None,None,True)), \
                patch('project_memory.startup',return_value={'schema_version':1,'operation':'startup','references':[],'complete':True,'diagnostics':[],'output':''}), \
                redirect_stdout(output):
            a.cmd_memory(args)
        report=json.loads(output.getvalue())
        self.assertFalse(report['complete'])
        self.assertIn('did not answer in time',report['output'])

if __name__=='__main__': unittest.main()
