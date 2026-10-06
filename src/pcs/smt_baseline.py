"""Transparent SMT-LIB safety adapter; native Z3 is an OPTIONAL trusted solver.

No proof-checking or model-counting claim is made. The full route constructs
row predicates directly from the input language. The reduced route requires a
live safe anchor. This adapter is not imported by the certificate checker.
"""
from pathlib import Path
import ctypes
import ctypes.util
import os
from .model import validate, Invalid
from .update_checker import SafeAnchor, _difference


def conjunction(parts):
    parts=list(parts)
    return 'true' if not parts else parts[0] if len(parts)==1 else '(and '+' '.join(parts)+')'


def disjunction(parts):
    parts=list(parts)
    return 'false' if not parts else parts[0] if len(parts)==1 else '(or '+' '.join(parts)+')'


def mask(xs):
    return disjunction(f'(and (<= {lo} y) (< y {hi}))' for lo,hi in xs)


def policy(p):
    return f'(and {mask(p["allow"])} (not {mask(p["exclude"])}))'


def row(r):
    return conjunction([f'(<= {r["lo"]} i)', f'(< i {r["hi"]})',
        f'(= (mod i {r["step"]}) {r["residue"]})', mask(r['guard'])])


def smt_problem(spec,plan,epoch=0,prefix=None,anchor=None,timeout_ms=10000):
    validate(spec,plan)
    n=spec['n'];prefix=n if prefix is None else prefix
    if type(epoch) is not int or not 0<=epoch<len(spec['epochs']):raise Invalid('epoch')
    if type(prefix) is not int or not 0<=prefix<=n:raise Invalid('prefix')
    if type(timeout_ms) is not int or not 1<=timeout_ms<=110000:raise Invalid('timeout')
    lines=['(set-logic QF_LIA)',f'(set-option :timeout {timeout_ms})',
           '(set-option :smt.threads 1)','(set-option :produce-models true)',
           '(declare-const i Int)',
           f'(define-fun y () Int (mod (+ (* {spec["a"]} i) {spec["b"]}) {n}))',
           f'(assert (and (<= 0 i) (< i {prefix})))',
           f'(define-fun wanted () Bool {policy(spec["epochs"][epoch])})']
    if anchor is None:
        relevant=[r for r in spec['history']+plan['future'] if r['epoch']==epoch]
        terms=[f'(ite {row(r)} 1 0)' for r in relevant]
    else:
        if not isinstance(anchor,SafeAnchor):raise Invalid('safe anchor required')
        oldspec,oldplan=anchor.inputs()
        if any(spec[k] != oldspec[k] for k in ('n','a','b')):
            raise Invalid('changed affine context')
        if len(spec['epochs']) != len(oldspec['epochs']) or spec['history'] != oldspec['history']:
            raise Invalid('changed history or epoch count')
        removed,added=_difference(oldplan,plan)
        rs=[oldplan['future'][j] for j in removed if oldplan['future'][j]['epoch']==epoch]
        aa=[plan['future'][j] for j in added if plan['future'][j]['epoch']==epoch]
        residual=f'(and {policy(oldspec["epochs"][epoch])} (not {disjunction(row(r) for r in rs)}))'
        terms=[f'(ite {residual} 1 0)']+[f'(ite {row(r)} 1 0)' for r in aa]
    mass='0' if not terms else terms[0] if len(terms)==1 else '(+ '+' '.join(terms)+')'
    lines.extend([f'(define-fun mass () Int {mass})',
                  '(assert (not (= mass (ite wanted 1 0))))','(check-sat)'])
    return '\n'.join(lines)+'\n'


class Z3Session:
    """Small checked-argument binding to the documented public C API."""
    def __init__(self,library=None):
        if library is None:
            bundled=Path(__file__).resolve().parents[2]/'third_party/z3/libz3.so.4'
            library=os.environ.get('Z3_LIBRARY_PATH')
            if not library:
                library=str(bundled) if bundled.exists() and os.name=='posix' else ctypes.util.find_library('z3')
        if not library:raise RuntimeError('optional libz3 dependency is unavailable')
        self.z=ctypes.CDLL(str(library));z=self.z
        z.Z3_get_full_version.restype=ctypes.c_char_p
        self.version=z.Z3_get_full_version().decode('ascii')
        z.Z3_mk_config.restype=ctypes.c_void_p
        z.Z3_mk_context.argtypes=[ctypes.c_void_p];z.Z3_mk_context.restype=ctypes.c_void_p
        z.Z3_del_config.argtypes=[ctypes.c_void_p];z.Z3_del_context.argtypes=[ctypes.c_void_p]
        z.Z3_eval_smtlib2_string.argtypes=[ctypes.c_void_p,ctypes.c_char_p]
        z.Z3_eval_smtlib2_string.restype=ctypes.c_char_p
        cfg=z.Z3_mk_config();self.context=z.Z3_mk_context(cfg);z.Z3_del_config(cfg)
        if not self.context:raise RuntimeError('Z3 context creation failed')
    def evaluate(self,text):
        if not isinstance(text,str) or '\x00' in text:raise ValueError('invalid SMT text')
        answer=self.z.Z3_eval_smtlib2_string(self.context,text.encode('utf-8'))
        if answer is None:raise RuntimeError('Z3 returned null output')
        answer=answer.decode('utf-8')
        if '(error' in answer:raise RuntimeError(answer)
        return answer
    def close(self):
        if self.context:self.z.Z3_del_context(self.context);self.context=None
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
