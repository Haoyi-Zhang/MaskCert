"""Exercise the actual report-producing function without importing POSIX limits."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]


class ReproductionReportTests(unittest.TestCase):
    def test_path_arguments_are_serializable_in_summary_and_raw_command(self):
        tree=ast.parse((ROOT/'scripts/reproduce.py').read_text(encoding='utf-8'))
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        calls=[]
        class Child:
            returncode=0
            def communicate(self,timeout):
                return '{"checked":true}\n',''
        def popen(command,**kwargs):
            calls.append(command)
            return Child()
        namespace=dict(sys=sys,time=time,os=os,json=json,
            subprocess=SimpleNamespace(Popen=popen,PIPE=subprocess.PIPE,
                                       TimeoutExpired=subprocess.TimeoutExpired),
            TIMEOUT_SECONDS=120)
        # Compile the exact shipped run function; do not import resource on Windows.
        exec(compile(ast.Module(body=[node],type_ignores=[]),'reproduce.py','exec'),namespace)
        with tempfile.TemporaryDirectory(prefix='owned-report-path-') as temporary:
            directory=Path(temporary)
            raw=directory/'raw'
            raw.mkdir()
            namespace['re']=__import__('re')
            destination=directory/'observation.json'
            report=namespace['run'](directory,'benchmark_record_workflow.py',
                                    '--out',destination,raw_output=raw)
            restored=json.loads(json.dumps(report))
            self.assertEqual(restored['arguments'],['--out',str(destination)])
            self.assertTrue(restored['summary']['checked'])
            command=json.loads(next(raw.glob('*.command.json')).read_text(encoding='utf-8'))
            self.assertEqual(command['command'],calls[0])
            self.assertTrue(all(type(arg) is str for arg in command['command']))


if __name__=='__main__':unittest.main()
