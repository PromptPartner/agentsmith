#!/usr/bin/env python3
"""Stage-observed public-CLI recovery fixtures. Never certifies native clients.

Repositories, configuration, argv, outputs, monotonic observations and controller artifacts
are retained under the chosen evidence directory. No inference occurs. Polling waits for
named barriers and persisted launch records, never assumes a stage after a fixed sleep.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path, value): Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
def write_exclusive(path,value):
    with Path(path).open('x') as out: out.write(json.dumps(value,indent=2,sort_keys=True)+'\n')
def required_variants():
    return ([f'normal/{p}' for p in ('codex-claude','claude-codex','codex-codex','claude-claude')]
            + [f'{c}/{s}' for c in ('R01','R02','R04') for s in ('making','verifying','checking')]
            + [f'R03/{r}-{a}' for r in ('maker','checker') for a in ('exit','kill')]
            + ['R05/post-commit','R06/validating','R07/codex','R07/claude']
            + [f'R08/{v}' for v in ('dirty-tree','moved-candidate','changed-spec','changed-manifest','changed-base','live-lock','scope-conflict')]
            + [f'R09/{v}' for v in ('abandoned','wrong-path','wrong-identity','locked')]
            + ['R10/verifying','R10/checking'])

def expected_pair(variant):
    return variant.split('/')[1] if variant.startswith('normal/') else ('claude-codex' if variant=='R07/claude' else 'codex-claude')

def validate_records(root, records, require_native=False, require_complete=False):
    if require_native: raise ValueError('offline fixture recorder cannot qualify native recovery')
    seen = set()
    for r in records:
        if r['variant'] not in required_variants() or r['variant'] in seen: raise ValueError('unknown or duplicate variant')
        seen.add(r['variant'])
        if r['result'] not in ('pass','fail','not-run','undetermined'): raise ValueError('invalid result')
        if r.get('evidence_kind')!='fixture': raise ValueError('fixture evidence cannot be relabeled native')
        for name, expected in r.get('artifacts', {}).items():
            p = (Path(root) / name).resolve()
            if not p.is_relative_to(Path(root).resolve()) or not p.is_file() or digest(p) != expected:
                raise ValueError('missing, escaped or changed raw artifact')
        if r['result'] == 'pass':
            proof=r.get('proof', {})
            if set(proof) != {'state','red_control','observations','source_snapshot','case_contract'}:
                raise ValueError('pass lacks typed observed proof')
            if any(name not in r.get('artifacts',{}) for name in proof.values()):
                raise ValueError('typed proof is not hash-bound')
            values={key:json.loads((Path(root)/name).read_text()) for key,name in proof.items()}
            contract=values['case_contract']
            expected={'schema_version':1,'variant':r['variant'],'pair':expected_pair(r['variant'])}
            if contract!=expected: raise ValueError('exact variant/pair contract mismatch')
            case_started=[x for x in values['observations'] if 'case_started' in x]
            if len(case_started)!=1 or case_started[0].get('case_started')!=r['variant'] or case_started[0].get('pair')!=expected['pair']:
                raise ValueError('exact observed variant/pair mismatch')
            if values['red_control'].get('exit',0)==0: raise ValueError('missing failing red control')
            state=values['state']; case=r['variant'].split('/')[0]
            if case=='normal' and (state.get('status')!='accepted' or not state.get('accepted_commit')):
                raise ValueError('normal cycle not accepted and commit-bound')
            if case!='normal' and not any('injection' in x for x in values['observations']):
                raise ValueError('fault lacks observed injection')
            snapshot=values['source_snapshot']
            required={'source/scripts/autonomous-run.py','source/native_launcher.py','source/windows_verifier_sandbox.py','source/scripts/qualification-recovery.py','source/docs/26-native-qualification-contract.md'}
            if set(snapshot)!=required or any(r['artifacts'].get(k)!=v for k,v in snapshot.items()):
                raise ValueError('source snapshot is not bound to retained frozen sources')
            obs=values['observations']; detail=r['variant'].split('/')[1]
            injections=[x for x in obs if x.get('injection')==case]
            if case!='normal':
                if len(injections)!=1 or not isinstance(injections[0].get('monotonic_ns'),int): raise ValueError('missing named monotonic injection')
                inj=injections[0]
                if inj.get('variant')!=r['variant']: raise ValueError('exact injection variant mismatch')
                expected={'making':'making','verifying':'verifying','checking':'checking','validating':'validating','post-commit':'making','codex':'making','claude':'making'}.get(detail)
                if expected and inj['state'].get('stage')!=expected: raise ValueError('injected at wrong persisted stage')
                if not inj.get('controller_pid') or (case not in ('R06','R07') and not inj.get('active_pid')): raise ValueError('missing observed process launch')
            if case in ('R05','R07','R08','R09') and state.get('status')=='accepted' and not (case=='R09' and detail=='abandoned'):
                raise ValueError('refusal/interruption falsely accepted')
            if case=='R01':
                ack=[x for x in obs if 'stop_ack_ns' in x]
                if len(ack)!=1 or not ack[0].get('stop_acknowledged') or ack[0]['stop_ack_ns']-inj['monotonic_ns']>5_000_000_000 or ack[0].get('fault_status')!='interrupted': raise ValueError('missing/late stop acknowledgement')
            if case in ('R01','R02','R03'):
                bound=[x for x in obs if 'automatic_extinction_ns' in x and 'controller_termination_ns' in x]
                if len(bound)!=1: raise ValueError('missing separate termination/extinction timings')
                if case=='R02' and (bound[0].get('fault_status')!='escalated' or not any(x.get('post_expiry_launch_count_unchanged') and x.get('deadline_preserved') for x in obs)): raise ValueError('deadline resume launched or accepted work')
                if case=='R03' and bound[0].get('fault_status') not in ('escalated','interrupted'): raise ValueError('role failure falsely accepted')
                start=bound[0].get('deadline_injection_ns',inj['monotonic_ns'])
                if any(not (-1_000_000_000 if case=='R02' else 0)<=bound[0][k]-start<=15_000_000_000 for k in ('controller_termination_ns','automatic_extinction_ns')): raise ValueError('extinction bound exceeded')
            if case=='R04':
                names=('owner_death_ns','live_group_resume_refused_ns','explicit_cleanup','group_death_ns','lock_reclaimed_ns')
                if any(not any(k in x for x in obs) for k in names): raise ValueError('missing survival/refusal/reclamation evidence')
                if state.get('status')!='accepted': raise ValueError('reclaimed run not recovered')
            if case in ('R06','R10') or (case=='R09' and detail=='abandoned'):
                if state.get('status')!='accepted' or state.get('attempt')!=inj['state']['attempt'] or state.get('accepted_commit')!=inj['state']['candidate_commit']: raise ValueError('recovered candidate/attempt changed')
            run=Path(root)/Path(proof['state']).parent
            if state.get('status')=='accepted':
                verify=run/f"attempt-{state['attempt']}-verify.json"
                checker=run/f"attempt-{state['attempt']}-checker-receipt.json"
                for path in (verify,checker):
                    if path.relative_to(root).as_posix() not in r['artifacts']: raise ValueError('missing bound acceptance receipt')
                v=json.loads(verify.read_text()); c=json.loads(checker.read_text())
                if v.get('candidate_commit')!=state.get('accepted_commit') or c.get('commit')!=state.get('accepted_commit'):
                    raise ValueError('stale candidate evidence')
                output=run/f"attempt-{state['attempt']}-verify.txt"
                if output.relative_to(root).as_posix() not in r['artifacts']: raise ValueError('missing raw verifier output')
                if v.get('exit_code')!=0 or c.get('status')!='accepted' or not any(str(x).strip() for x in c.get('evidence',[])) or c.get('unresolved')!=[]:
                    raise ValueError('failed verifier/checker cannot qualify acceptance')
                if v.get('checker_receipt_sha256')!=digest(checker) or v.get('output_sha256')!=digest(output):
                    raise ValueError('receipt/output binding mismatch')
                if any(v.get(k)!=state.get(sk) for k,sk in (('base_commit','base_head'),('spec_sha256','spec_sha256'),('manifest_sha256','manifest_sha256'))):
                    raise ValueError('verification contract binding mismatch')
                if v.get('runtime_sha256')!={'controller':snapshot['source/scripts/autonomous-run.py'],'launcher':snapshot['source/native_launcher.py']}:
                    raise ValueError('runtime snapshot binding mismatch')
            if case=='R07':
                events=run/'events.jsonl'
                if events.relative_to(root).as_posix() not in r['artifacts']: raise ValueError('unbound accounting events')
                usage=[json.loads(line) for line in events.read_text().splitlines() if json.loads(line).get('event')=='usage_recorded']
                if len(usage)!=1 or state.get('usage_pending') or not state.get('usage_accounting_incomplete'):
                    raise ValueError('duplicate or incomplete usage replay evidence')
            if case in ('R01','R02','R03'):
                last=[x for x in values['observations'] if 'members' in x]
                if not last or last[-1]['members']: raise ValueError('orphaned descendants')

    if require_complete and (seen != set(required_variants()) or any(r['result']!='pass' for r in records)):
        raise ValueError('missing or nonpassing required recovery variants')
    return True

# Source embedded in this frozen runner is copied into every disposable fixture.
AGENT = r'''#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys, time
root = pathlib.Path(__file__).resolve().parent
cfg = json.loads((root/'config.json').read_text())
role = 'checker' if 'independent checker' in sys.argv[-1] else 'maker'
def gate(name):
 print('BARRIER:'+name, flush=True)
 child = subprocess.Popen(['/bin/sleep','600'])
 (root/(name+'.child')).write_text(str(child.pid))
 while not (root/(name+'.release')).exists(): time.sleep(.02)
 child.terminate(); child.wait()
with (root/'launches.jsonl').open('a') as f:
 f.write(json.dumps({'role':role,'pid':os.getpid(),'group':os.getpgrp(),'monotonic_ns':time.monotonic_ns(),'argv':sys.argv})+'\n')
usage = {'type':'turn.completed','usage':{'input_tokens':7,'output_tokens':3}} if '-o' in sys.argv else {'type':'result','total_cost_usd':0.125}
print(json.dumps(usage), flush=True)
if cfg.get('hold') == role: gate(role)
cfg = json.loads((root/'config.json').read_text())
if cfg.get('exit') == role: sys.exit(17)
if role == 'maker':
 pathlib.Path('src/change.txt').write_text('fixed\n')
 subprocess.run(['git','add','src/change.txt'],check=True)
 subprocess.run(['git','commit','-qm','test(fixture): satisfy bounded red check'],check=True)
 if cfg.get('hold') == 'post-commit': gate('post-commit')
commit = subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
payload = {'status':'completed' if role == 'maker' else 'accepted','summary':'deterministic fixture','commit':commit,'changed_paths':['src/change.txt'],'evidence':['fixture verifier checks fixed value'],'unresolved':[],'next_state':'checking' if role == 'maker' else 'accepted'}
if '-o' in sys.argv: pathlib.Path(sys.argv[sys.argv.index('-o')+1]).write_text(json.dumps(payload))
else: print(json.dumps({'type':'result','total_cost_usd':0.125,'structured_output':payload}),flush=True)
'''
WRAPPER = r'''import importlib.util, json, pathlib, sys, time
root = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, SOURCE)
spec = importlib.util.spec_from_file_location('controller', SOURCE+'/scripts/autonomous-run.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
def gate(name):
 print('BARRIER:'+name,flush=True)
 while not (root/(name+'.release')).exists(): time.sleep(.02)
original_stage=m.checkpoint_stage
original_usage=m.record_role_usage
original_save=m.save_state
def stage(state,name):
 original_stage(state,name)
 cfg=json.loads((root/'config.json').read_text())
 if cfg.get('hold') == name: gate(name)
def usage(*args):
 cfg=json.loads((root/'config.json').read_text())
 if cfg.get('hold') == 'accounting' and args[2]=='maker': gate('accounting')
 return original_usage(*args)
m.checkpoint_stage=stage; m.record_role_usage=usage
sys.exit(m.main())
'''
VERIFY = r'''import pathlib, subprocess, time
root = pathlib.Path(ROOT_PATH)
print('BARRIER:verify',flush=True)
while not (root/'verify.release').exists(): time.sleep(.02)
assert pathlib.Path('src/change.txt').read_text() == 'fixed\n'
print('red check now green',flush=True)
'''

class Fixture:
    def __init__(self, directory, hold=None, pair='codex-claude'):
        self.directory = directory; directory.mkdir(parents=True)
        self.repo = directory/'repo'; self.repo.mkdir()
        self.cfg={'hold':hold}; write(directory/'config.json',self.cfg)
        (directory/'agent').write_text(AGENT); (directory/'agent').chmod(0o755)
        (directory/'controller.py').write_text('SOURCE='+repr(str(directory.parent/'source'))+'\n'+WRAPPER)
        (directory/'verify.py').write_text('ROOT_PATH='+repr(str(directory))+'\n'+VERIFY)
        (directory/'auth').mkdir(); write(directory/'auth/auth.json',{'auth_mode':'chatgpt','tokens':{}})
        self.env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','TMPDIR','SHELL','SYSTEMROOT')}
        self.env.update(HOME=str(directory/'home'),CLAUDE_CONFIG_DIR=str(directory/'claude-home'),AGENTSMITH_CODEX_BIN=str(directory/'agent'),AGENTSMITH_CLAUDE_BIN=str(directory/'agent'),CODEX_HOME=str(directory/'auth'))
        self.git('init','-q'); self.git('config','user.name','Qualification Fixture'); self.git('config','user.email','user@example.com')
        (self.repo/'docs/specs').mkdir(parents=True); (self.repo/'src').mkdir()
        (self.repo/'src/change.txt').write_text('broken\n')
        (self.repo/'docs/specs/task.md').write_text('---\nstatus: accepted\ndecision_ticket: FIXTURE\naccepted_by: Fixture Operator\naccepted_at: 2026-10-05\n---\n# Fixture\n## Destination\nFix bounded value.\n')
        (self.repo/'.harness/runs').mkdir(parents=True)
        manifest=json.loads((ROOT/'templates/autonomous-run.json').read_text())
        manifest.update(run_id='fixture',spec_path='docs/specs/task.md',implementation_ticket='FIXTURE-IMPLEMENTATION')
        for role,runtime in zip(('maker','checker'),pair.split('-')):
            manifest['roles'][role].update(runtime=runtime,model='deterministic-fixture')
        manifest['scope']['allowed_paths']=['src/**']; manifest['limits'].update(max_attempts=3,wall_minutes=1)
        manifest['verify']['command']=shlex.join([sys.executable,str(directory/'verify.py')])
        write(self.repo/'.harness/runs/fixture.json',manifest)
        peer=json.loads(json.dumps(manifest)); peer['run_id']='fixture-peer'
        write(self.repo/'.harness/runs/fixture-peer.json',peer)
        self.git('add','.'); self.git('commit','-qm','test(fixture): freeze red input and contract')
        self.state_path=self.repo/'.git/agentsmith-runs/fixture/state.json'
        self.processes=[]; self.observations=[]; self.counter=0
        self.release('verify') if hold!='verify' else None
        red=subprocess.run([sys.executable,'-c',"from pathlib import Path; assert Path('src/change.txt').read_text() == 'fixed\\n'"],cwd=self.repo,capture_output=True,text=True)
        write(directory/'red-control.json',{'exit':red.returncode,'stdout':red.stdout,'stderr':red.stderr})
        assert red.returncode!=0
    def git(self,*args,cwd=None):
        return subprocess.check_output(['git','-C',str(cwd or self.repo),*args],text=True).strip()
    def state(self): return json.loads(self.state_path.read_text())
    def configure(self,**values): self.cfg.update(values); write(self.directory/'config.json',self.cfg)
    def release(self,name): (self.directory/(name+'.release')).touch()
    def call(self,*args,background=False):
        self.counter+=1; prefix=self.directory/f'cli-{self.counter}'
        argv=[sys.executable,str(self.directory/'controller.py'),*args]
        write(prefix.with_suffix('.argv.json'),{'argv':argv,'monotonic_ns':time.monotonic_ns()})
        out=prefix.with_suffix('.stdout').open('w'); err=prefix.with_suffix('.stderr').open('w')
        p=subprocess.Popen(argv,cwd=self.repo,env=self.env,stdout=out,stderr=err); out.close(); err.close()
        self.processes.append(p)
        if background: return p
        try: rc=p.wait(timeout=25)
        except subprocess.TimeoutExpired: p.kill(); p.wait(); raise RuntimeError('CLI exceeded fixture timeout')
        write(prefix.with_suffix('.exit.json'),{'exit_code':rc,'monotonic_ns':time.monotonic_ns()})
        return rc
    def wait(self,predicate,timeout=20):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            if predicate(): return
            time.sleep(.02)
        raise RuntimeError('named stage/launch barrier not reached')
    def barrier(self,name):
        def observed():
            if not self.state_path.exists(): return False
            run=self.state_path.parent; state=self.state()
            expected={'maker':'making','checker':'checking','verify':'verifying','post-commit':'making','accounting':'making','validating':'validating'}[name]
            if state.get('stage')!=expected: return False
            if name in ('validating','accounting'):
                texts=list(self.directory.glob('cli-*.stdout'))
            else:
                role='maker' if name=='post-commit' else name
                prefix=f"attempt-{state['attempt']}-{role}"
                launch=run/(prefix+'-launch.json'); output=run/(prefix+'.stdout')
                if not launch.exists() or not output.exists() or json.loads(launch.read_text()).get('pid')!=state.get('active_pid'): return False
                texts=[output]
            return any('BARRIER:'+name in p.read_text() for p in texts)
        self.wait(observed)
        self.observations.append({'barrier':name,'state':self.state(),'monotonic_ns':time.monotonic_ns()})
    def live_group(self,pid):
        text=subprocess.check_output(['ps','-axo','pid=,pgid=,stat='],text=True)
        members=[line.strip() for line in text.splitlines() if len(line.split())==3 and line.split()[1]==str(pid) and not line.split()[2].startswith('Z')]
        self.observations.append({'group':pid,'members':members,'monotonic_ns':time.monotonic_ns()})
        return bool(members)
    def cleanup_group(self,pid):
        if pid and self.live_group(pid):
            # Only groups identified by this disposable controller's persisted launch.
            launches=list((self.repo/'.git/agentsmith-runs').glob('*/*-launch.json'))
            assert any(json.loads(p.read_text()).get('pid')==pid for p in launches)
            self.observations.append({'explicit_cleanup':pid,'monotonic_ns':time.monotonic_ns()})
            try: os.killpg(pid,signal.SIGKILL)
            except ProcessLookupError: pass
            self.wait(lambda:not self.live_group(pid),5)
            self.observations.append({'group_death_ns':time.monotonic_ns()})
    def finish(self):
        for p in self.processes:
            if p.poll() is None: p.kill(); p.wait()
        if self.state_path.exists():
            for state_path in (self.repo/'.git/agentsmith-runs').glob('*/state.json'):
                self.cleanup_group(json.loads(state_path.read_text()).get('active_pid'))
            self.call('status','fixture')
        write(self.directory/'observations.json',self.observations)
        return {p.relative_to(self.directory).as_posix():digest(p) for p in self.directory.rglob('*') if p.is_file() and '.git' not in p.parts}

def execute_variant(f,variant):
    case, detail=variant.split('/')
    if case=='normal':
        assert f.call('start','.harness/runs/fixture.json')==0
        assert f.state()['status']=='accepted'
        return
    if case=='R06': barrier='validating'
    elif case=='R07': barrier='accounting'
    elif case=='R05': barrier='post-commit'
    elif case=='R03': barrier=detail.split('-')[0]
    elif case in ('R08','R09'): barrier='checker'
    else: barrier={'making':'maker','verifying':'verify','checking':'checker'}[detail]
    f.configure(hold=barrier)
    if barrier=='verify': (f.directory/'verify.release').unlink(missing_ok=True)
    p=f.call('start','.harness/runs/fixture.json',background=True); f.barrier(barrier)
    state=f.state(); pid=state.get('active_pid'); candidate=state.get('candidate_commit'); attempt=state['attempt']
    injection=time.monotonic_ns(); f.observations.append({'injection':case,'variant':variant,'monotonic_ns':injection,'controller_pid':p.pid,'active_pid':pid,'state':state})
    if case=='R08' and detail=='live-lock':
        before=(f.directory/'launches.jsonl').read_text()
        assert f.call('resume','fixture')!=0
        assert (f.directory/'launches.jsonl').read_text()==before
        f.call('stop','fixture'); p.wait(timeout=15)
        return
    if case=='R01' or case=='R10':
        f.call('stop','fixture')
        f.observations.append({'stop_ack_ns':time.monotonic_ns(),'stop_acknowledged':f.state()['status']=='interrupted','fault_status':f.state()['status']})
        p.wait(timeout=15); terminated=time.monotonic_ns()
        assert f.state()['status']=='interrupted'; assert not f.live_group(pid)
        f.observations.append({'automatic_extinction_ns':time.monotonic_ns(),'controller_termination_ns':terminated,'fault_status':f.state()['status']})
        assert (time.monotonic_ns()-injection)/1e9<=15
    elif case=='R03':
        if detail.endswith('exit'): f.configure(exit=barrier); f.release(barrier)
        else: os.kill(pid,signal.SIGKILL)
        p.wait(timeout=15); terminated=time.monotonic_ns()
        assert f.state()['status']!='accepted'; assert not f.live_group(pid)
        f.observations.append({'automatic_extinction_ns':time.monotonic_ns(),'controller_termination_ns':terminated,'fault_status':f.state()['status']})
        assert (time.monotonic_ns()-injection)/1e9<=15
    elif case=='R02':
        # Original persisted one-minute deadline, never reset to accelerate the test.
        expiry_ns=injection+int(max(0,state['deadline_epoch']-time.time())*1e9)
        p.wait(timeout=75); terminated=time.monotonic_ns()
        assert f.state()['status']!='accepted'; assert not f.live_group(pid)
        extinct=time.monotonic_ns()
        f.observations.append({'deadline_injection_ns':expiry_ns,'controller_termination_ns':terminated,'automatic_extinction_ns':extinct,'fault_status':f.state()['status'],'deadline_rounding_seconds':1})
        assert -1 <= (terminated-expiry_ns)/1e9 <= 15 and -1 <= (extinct-expiry_ns)/1e9 <= 15
        deadline=state['deadline_epoch']; before=(f.directory/'launches.jsonl').read_text(); assert f.call('resume','fixture')!=0
        assert (f.directory/'launches.jsonl').read_text()==before
        f.observations.append({'post_expiry_launch_count_unchanged':True,'deadline_preserved':f.state()['deadline_epoch']==deadline})
        assert f.state()['deadline_epoch']==deadline
        return
    else:
        p.kill(); p.wait(); f.observations.append({'owner_death_ns':time.monotonic_ns()})
        if pid and f.live_group(pid):
            assert f.call('resume','fixture')!=0
            f.observations.append({'live_group_resume_refused_ns':time.monotonic_ns()})
            f.cleanup_group(pid)
    f.configure(hold=None,exit=None); f.release(barrier); f.release('verify')
    if case=='R05':
        assert f.call('resume','fixture')!=0
        assert 'advanced HEAD' in '\n'.join(p.read_text() for p in f.directory.glob('cli-*.stderr'))
        return
    if case=='R07':
        usagekey='codex_tokens_used' if detail=='codex' else 'claude_cost_usd'
        assert f.call('resume','fixture')!=0
        recovered=f.state(); assert recovered.get('usage_accounting_incomplete') is True
        before=recovered[usagekey]; assert before>0
        assert f.call('resume','fixture')!=0; assert f.state()[usagekey]==before
        return
    if case=='R08':
        wt=Path(state['worktree']); m=f.repo/'.harness/runs/fixture.json'
        if detail=='dirty-tree': (wt/'src/change.txt').write_text('dirty\n')
        elif detail=='moved-candidate':
            (wt/'src/change.txt').write_text('advanced\n'); f.git('add','.',cwd=wt); f.git('commit','-qm','fixture advance',cwd=wt)
        elif detail=='changed-spec': (f.repo/'docs/specs/task.md').write_text('changed\n')
        elif detail=='changed-manifest': v=json.loads(m.read_text()); v['limits']['wall_minutes']=2; write(m,v)
        elif detail=='changed-base': f.git('commit','--allow-empty','-qm','fixture base moved')
        elif detail=='scope-conflict':
            f.configure(hold='checker'); (f.directory/'checker.release').unlink(missing_ok=True)
            peer=f.call('start','.harness/runs/fixture-peer.json',background=True)
            peerstate=f.repo/'.git/agentsmith-runs/fixture-peer/state.json'
            f.wait(lambda:peerstate.exists() and json.loads(peerstate.read_text()).get('stage')=='checking' and json.loads(peerstate.read_text()).get('active_pid'))
            f.wait(lambda:sum(json.loads(line)['role']=='checker' for line in (f.directory/'launches.jsonl').read_text().splitlines())==2)
            before=(f.directory/'launches.jsonl').read_text()
            assert f.call('resume','fixture')!=0
            assert (f.directory/'launches.jsonl').read_text()==before
            errors='\n'.join(p.read_text() for p in f.directory.glob('cli-*.stderr'))
            assert 'overlapping path scope' in errors
            f.call('stop','fixture-peer'); peer.wait(timeout=15)
            return
        before=(f.directory/'launches.jsonl').read_text()
        assert f.call('resume','fixture')!=0; assert (f.directory/'launches.jsonl').read_text()==before
        return
    if case=='R09':
        check=Path(state['checker_worktree'])
        if detail=='wrong-path': s=f.state(); s['checker_worktree']=str(f.directory/'unrelated'); write(f.state_path,s)
        elif detail=='wrong-identity':
            f.git('worktree','remove','--force',str(check)); check.mkdir(); subprocess.run(['git','init','-q',str(check)],check=True)
        elif detail=='locked': f.git('worktree','lock',str(check))
        if detail!='abandoned':
            assert f.call('resume','fixture')!=0; assert check.exists(); return
    if case=='R10':
        # Repeat a real stage interruption before the final successful resume.
        f.configure(hold=barrier)
        (f.directory/(barrier+'.release')).unlink(missing_ok=True)
        if barrier=='verify': (f.directory/'verify.release').unlink(missing_ok=True)
        q=f.call('resume','fixture',background=True)
        # Old logs may still contain barrier; require a new live launch first.
        f.wait(lambda: f.state().get('active_pid') and f.state()['active_pid']!=pid)
        f.barrier(barrier); f.call('stop','fixture'); q.wait(timeout=15)
        f.configure(hold=None); f.release(barrier); f.release('verify')
    assert f.call('resume','fixture')==0
    end=f.state(); assert end['status']=='accepted'
    if case=='R04': f.observations.append({'lock_reclaimed_ns':time.monotonic_ns(),'controller_token':end['controller_token']})
    if candidate:
        assert end.get('accepted_commit')==candidate and end['attempt']==attempt
    if case in ('R06','R09','R10'):
        launches=[json.loads(line) for line in (f.directory/'launches.jsonl').read_text().splitlines()]
        assert sum(r['role']=='maker' for r in launches)==1
    if case=='R10': assert list(f.state_path.parent.glob('archive/*/*'))


def run(output,only=None):
    output=Path(output).resolve(); output.mkdir(parents=True,exist_ok=False)
    for relative in ('scripts/autonomous-run.py','native_launcher.py','windows_verifier_sandbox.py','scripts/qualification-recovery.py','docs/26-native-qualification-contract.md'):
        dest=output/'source'/relative; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(ROOT/relative,dest)
    write(output/'snapshot.json',{p.relative_to(output).as_posix():digest(p) for p in (output/'source').rglob('*') if p.is_file()})
    records=[]
    for variant in required_variants():
        r={'variant':variant,'result':'not-run','evidence_kind':'fixture','artifacts':{},'reason':'not selected','host':sys.platform}
        if only is not None and variant not in only: records.append(r); continue
        directory=output/variant.replace('/','--'); f=None
        try:
            pair=expected_pair(variant)
            f=Fixture(directory,pair=pair)
            write_exclusive(directory/'case-contract.json',{'schema_version':1,'variant':variant,'pair':pair})
            f.observations.append({'case_started':variant,'pair':pair,'monotonic_ns':time.monotonic_ns()})
            execute_variant(f,variant); r.update(result='pass',reason='observed deterministic CLI fixture; no native qualification')
        except Exception as e: r.update(result='undetermined' if isinstance(e,RuntimeError) else 'fail',reason=str(e) or type(e).__name__)
        finally:
            if f:
                try: f.finish()
                except Exception as e: r.update(result='fail',reason='cleanup/status failed: '+str(e))
            # Freeze raw trusted artifacts too, including .git run-state and archived usage.
            if directory.exists():
                r['artifacts']={p.relative_to(output).as_posix():digest(p) for p in directory.rglob('*') if p.is_file()}
            if r['result']=='pass':
                r['proof']={'state':f.state_path.relative_to(output).as_posix(),
                            'red_control':(directory/'red-control.json').relative_to(output).as_posix(),
                            'observations':(directory/'observations.json').relative_to(output).as_posix(),
                            'source_snapshot':'snapshot.json','case_contract':(directory/'case-contract.json').relative_to(output).as_posix()}
                r['artifacts']['snapshot.json']=digest(output/'snapshot.json')
                r['artifacts'].update(json.loads((output/'snapshot.json').read_text()))
            records.append(r); write_exclusive(output/f'ledger-{len(records):04d}.json',{'schema_version':1,'required_variants':required_variants(),'records':records,'native_qualified':False,'offline_complete':len(records)==len(required_variants()) and all(x['result']=='pass' for x in records)})
        print(variant+': '+r['result']+' '+r['reason'],flush=True)
    validate_records(output,records)
    write_exclusive(output/'ledger.json',{'schema_version':1,'required_variants':required_variants(),'records':records,'native_qualified':False,'offline_complete':all(x['result']=='pass' for x in records)})
    return records

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',required=True); parser.add_argument('--only',action='append'); parser.add_argument('--check',action='store_true'); parser.add_argument('--require-native',action='store_true')
    args=parser.parse_args()
    if args.check:
        ledger=json.loads((Path(args.output)/'ledger.json').read_text())
        if ledger.get('required_variants')!=required_variants(): raise ValueError('submitted ledger cannot redefine completeness')
        validate_records(Path(args.output).resolve(),ledger['records'],require_native=args.require_native,require_complete=True)
        print('Offline recovery evidence complete; native qualification remains pending.')
        sys.exit(0)
    records=run(args.output,args.only)
    sys.exit(1 if any(r['result']=='fail' for r in records) else 0)
