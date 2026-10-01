from pathlib import Path
import copy
import io
import json
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))
from casegen import base, mkrow
from pcs.producer import write_certificate, locate, defects
from pcs.checker import verify, check_witness
from pcs.model import Invalid, validate, certificate_lines, load, MAX_CERTIFICATE_LINE_BYTES
from pcs.cli import main

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.spec,self.plan=base(32,3,1)
    def certificate(self,spec=None,plan=None,prefix=None):
        stream=io.StringIO()
        write_certificate(spec or self.spec,plan or self.plan,stream,prefix)
        return stream.getvalue()
    def test_context_is_external(self):
        changed=copy.deepcopy(self.plan)
        changed['context']['b']=2
        with self.assertRaises(Invalid):
            verify(self.spec,changed,io.StringIO(self.certificate()))
    def test_safe_not_raw_partition(self):
        spec={'n':8,'a':3,'b':1,'epochs':[{'allow':[[0,8]],'exclude':[[1,2]]}],'history':[]}
        plan={'context':{'n':8,'a':3,'b':1},'future':[
            mkrow(0,0,8,1,0,[[0,1],[2,8]]),mkrow(0,0,1,1,0,[[0,1],[2,8]])]}
        self.assertEqual(defects(spec,plan),[0])
        self.assertTrue(verify(spec,plan,io.StringIO(self.certificate(spec,plan))).accepted)
    def test_minimal_witness_mutations(self):
        self.spec={'n':4,'a':1,'b':0,'epochs':[{'allow':[[0,4]],'exclude':[]}],'history':[]}
        self.plan={'context':{'n':4,'a':1,'b':0},'future':[
            mkrow(0,0,3,1,0,[[0,4]]),mkrow(0,0,1,1,0,[[0,4]])]}
        witness=locate(self.spec,self.plan)
        certs=[self.certificate(prefix=p) for p in (None,0,1)]
        def check(w,cs=certs):
            return check_witness(self.spec,self.plan,w,*(io.StringIO(s) for s in cs))
        self.assertTrue(check(witness))
        for field,value in [('counter',1),('target',1),('kind','omission'),
                            ('rows',[1,0]),('epoch',1)]:
            w=copy.deepcopy(witness);w[field]=value
            with self.assertRaises(Invalid):check(w)
        with self.assertRaises(Invalid):check(witness,[certs[0],certs[2],certs[1]])
    def test_unsafe_is_not_malformed(self):
        plan=copy.deepcopy(self.plan);plan['future']=[]
        check=verify(self.spec,plan,io.StringIO(self.certificate(plan=plan)))
        self.assertFalse(check.accepted)
        self.assertTrue(any(check.defects))
    def test_empty_singleton(self):
        spec,plan=base(1,0,0)
        self.assertTrue(verify(spec,plan,io.StringIO(self.certificate(spec,plan))).accepted)
        self.assertTrue(verify(spec,plan,io.StringIO(self.certificate(spec,plan,0)),0).accepted)
    def test_prefix_must_be_requested(self):
        with self.assertRaises(Invalid):
            verify(self.spec,self.plan,io.StringIO(self.certificate(prefix=0)))
    def test_bounded_readers(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'bad'
            path.write_bytes(b'0'*(MAX_CERTIFICATE_LINE_BYTES+1))
            with self.assertRaises(Invalid):list(certificate_lines(path))
            path.write_bytes(b'\xff')
            with self.assertRaises(Invalid):list(certificate_lines(path))
            with self.assertRaises(Invalid):load(path)
    def test_existing_output_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);s=d/'declaration.json';p=d/'plan.json';out=d/'certificate.jsonl'
            s.write_text(json.dumps(self.spec));p.write_text(json.dumps(self.plan))
            out.write_text('sentinel')
            import contextlib
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['certify',str(s),str(p),'--out',str(out)]),2)
            self.assertEqual(out.read_text(),'sentinel')

if __name__=='__main__':unittest.main()
