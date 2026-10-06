from common import ROOT,bounded,finish
bounded()
import ast,json,subprocess,sys,tempfile
from pathlib import Path
from io import StringIO
from copy import deepcopy
from pcs.producer import write_certificate
from pcs.update_producer import write_update
from pcs.update_checker import establish_anchor,verify_update,advance_anchor
from pcs.model import Invalid


def full(s,p):
    out=StringIO();write_certificate(s,p,out);return out.getvalue()
def update(os,op,s,p):
    out=StringIO();write_update(os,op,s,p,out);return out.getvalue()

def main():
    records=[]
    s={'n':64,'a':5,'b':7,'epochs':[{'allow':[[0,64]],'exclude':[]}],'history':[]}
    def row(lo,hi):return {'epoch':0,'lo':lo,'hi':hi,'step':1,'residue':0,'guard':[[0,64]]}
    p={'context':{k:s[k] for k in ('n','a','b')},'future':[row(0,64)]}
    safe=deepcopy(p);safe['future']=[row(0,32),row(32,64)]
    unsafe=deepcopy(p);unsafe['future']=[row(0,2),row(3,64)]
    anchor=establish_anchor(s,p,StringIO(full(s,p)))
    advanced=advance_anchor(anchor,s,safe,StringIO(update(s,p,s,safe)))
    back=advance_anchor(advanced,s,p,StringIO(update(s,safe,s,p)))
    assert back.inputs()==(s,p);records.append('two accepted updates advance and restore the anchor')
    try:advance_anchor(anchor,s,unsafe,StringIO(update(s,p,s,unsafe)))
    except Invalid:records.append('unsafe update cannot advance anchor')
    else:raise AssertionError('unsafe anchor accepted')
    with tempfile.TemporaryDirectory(prefix='mask-update-cli-') as td:
        d=Path(td)
        for name,data in [('old-declaration',s),('declaration',s),('old-plan',p),('safe',safe),('unsafe',unsafe)]:
            (d/(name+'.json')).write_text(json.dumps(data))
        (d/'old.jsonl').write_text(full(s,p))
        common=[str(d/'old-declaration.json'),str(d/'old-plan.json'),str(d/'old.jsonl'),str(d/'declaration.json')]
        calls=[]
        def run(arguments,expected):
            completed=subprocess.run([sys.executable,str(ROOT/'pcs-update.py')]+arguments,capture_output=True,text=True,timeout=15)
            assert completed.returncode==expected,(arguments,completed.stdout,completed.stderr)
            calls.append({'arguments':[Path(x).name if x.startswith(str(d)) else x for x in arguments],
                          'expected':expected,'observed':completed.returncode,'stdout':completed.stdout,'stderr':completed.stderr})
        for name,expected in [('safe',0),('unsafe',1)]:
            args=common+[str(d/(name+'.json'))]
            run(['certify']+args+['--out',str(d/(name+'.jsonl'))],0)
            run(['check']+args+[str(d/(name+'.jsonl'))],expected)
        raw=(d/'unsafe.jsonl').read_text().splitlines(True)
        (d/'damaged.jsonl').write_text(''.join(raw[:-1]))
        run(['check']+common+[str(d/'unsafe.json'),str(d/'damaged.jsonl')],2)
        run(['diagnose']+common+[str(d/'unsafe.json'),str(d/'witness')],0)
        run(['check-witness']+common+[str(d/'unsafe.json'),str(d/'witness')],0)
        w=json.loads((d/'witness/witness.json').read_text())
        assert w=={'epoch':0,'counter':2,'target':17,'kind':'omission','rows':[]}
        a=(d/'witness/before.jsonl').read_text();b=(d/'witness/through.jsonl').read_text()
        (d/'witness/before.jsonl').write_text(b);(d/'witness/through.jsonl').write_text(a)
        run(['check-witness']+common+[str(d/'unsafe.json'),str(d/'witness')],2)
        run(['certify']+common+[str(d/'safe.json'),'--out',str(d/'safe.jsonl')],2)
        assert json.loads((d/'safe.jsonl').read_text().splitlines()[-1])['accepted'] is True
    prohibited={'producer','oracle','update_producer','boolean_encoding','smt_baseline'}
    imports=[]
    for name in ['checker.py','update_checker.py']:
        tree=ast.parse((ROOT/'src/pcs'/name).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom) and node.module:
                imports.append([name,node.module]);assert not (set(node.module.split('.'))&prohibited)
            if isinstance(node,ast.Import):
                for alias in node.names:assert not(set(alias.name.split('.'))&prohibited)
    # Runtime import tripwire starts in a fresh Python interpreter.
    source="""import sys,importlib.abc
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[-1] in {'producer','oracle','update_producer','boolean_encoding','smt_baseline'}:
   raise RuntimeError('forbidden import '+fullname)
sys.meta_path.insert(0,Block())
from pcs.checker import verify
from pcs.update_checker import establish_anchor,verify_update
print('checker-only imports succeeded')
"""
    import os
    env=dict(os.environ,PYTHONPATH=str(ROOT/'src'))
    done=subprocess.run([sys.executable,'-c',source],cwd=ROOT/'src',env=env,capture_output=True,text=True,timeout=15)
    assert done.returncode==0,done.stderr
    finish('update-contract.json',dict(all_checks_passed=True,checks=records,cli_calls=calls,
       cli_calls_compared=len(calls),checker_imports=imports,runtime_import_tripwire=done.stdout.strip(),
       explicit_shared_trusted_components=['pcs.model','pcs.checker arithmetic used by update checker','Python runtime and bigint'],
       not_claimed=['independent team implementation','proof-assistant verification','cryptographic authentication']))
if __name__=='__main__':main()
