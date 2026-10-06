"""Parsimonious Boolean encodings of the mask-aware defect.

This is an application encoder, not a certified upstream model counter. Every
introduced AND/XOR variable is defined in both directions; auxiliary variables
therefore do not multiply the number of models. The primary variables encode
one source counter and two local fault-token indices.

The anchor-reduced encoder requires an actual in-process SafeAnchor. It uses
checker-side exact matching only to remove unchanged rows; neither encoding
calls symbolic floor sums or an explicit semantic oracle.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, TextIO
from .model import Invalid, integer, validate

MAX_BOOLEAN_VARIABLES = 500_000
MAX_BOOLEAN_CLAUSES = 2_000_000


class Circuit:
    def __init__(self):
        self.variables = 1
        self.clauses = [(1,)]
        self.gates: list[tuple[int,str,int,int]] = []
        self.inputs: dict[str,tuple[int,...]] = {}
        self._cache = {}
        self._mods = {}
        self.true, self.false = 1, -1

    def fresh(self):
        self.variables += 1
        if self.variables > MAX_BOOLEAN_VARIABLES:
            raise Invalid('Boolean variable resource bound')
        return self.variables

    def input(self, name: str, width: int):
        if name in self.inputs or width < 1:
            raise Invalid('Boolean input declaration')
        bits = tuple(self.fresh() for _ in range(width))
        self.inputs[name] = bits
        return bits

    def emit(self, *clauses):
        if len(self.clauses) + len(clauses) > MAX_BOOLEAN_CLAUSES:
            raise Invalid('Boolean clause resource bound')
        self.clauses.extend(tuple(c) for c in clauses)

    def AND(self, a: int, b: int) -> int:
        if a == self.false or b == self.false or a == -b:
            return self.false
        if a == self.true:
            return b
        if b == self.true or a == b:
            return a
        a, b = sorted((a,b))
        key=('and',a,b)
        if key in self._cache:
            return self._cache[key]
        v=self.fresh(); self._cache[key]=v
        self.emit((-v,a),(-v,b),(v,-a,-b))
        self.gates.append((v,'and',a,b))
        return v

    def XOR(self, a: int, b: int) -> int:
        if a == b:
            return self.false
        if a == -b:
            return self.true
        if a == self.false:
            return b
        if b == self.false:
            return a
        if a == self.true:
            return -b
        if b == self.true:
            return -a
        a,b=sorted((a,b)); key=('xor',a,b)
        if key in self._cache:
            return self._cache[key]
        v=self.fresh(); self._cache[key]=v
        self.emit((-a,-b,-v),(a,b,-v),(a,-b,v),(-a,b,v))
        self.gates.append((v,'xor',a,b))
        return v

    def OR(self, a: int, b: int) -> int:
        return -self.AND(-a,-b)

    def all(self, literals: Iterable[int]) -> int:
        result=self.true
        for literal in literals:
            result=self.AND(result,literal)
        return result

    def any(self, literals: Iterable[int]) -> int:
        return -self.all(-literal for literal in literals)

    def const(self, value: int, width: int):
        return tuple(self.true if (value>>j)&1 else self.false for j in range(width))

    def pad(self, bits, width: int):
        return tuple(bits[:width]) + (self.false,)*max(0,width-len(bits))

    def mux(self, condition: int, yes, no):
        width=max(len(yes),len(no)); yes=self.pad(yes,width); no=self.pad(no,width)
        return tuple(self.OR(self.AND(condition,a),self.AND(-condition,b)) for a,b in zip(yes,no))

    def add(self, left, right, width: int):
        left,right=self.pad(left,width),self.pad(right,width)
        carry=self.false; output=[]
        for a,b in zip(left,right):
            ab=self.XOR(a,b)
            output.append(self.XOR(ab,carry))
            carry=self.OR(self.AND(a,b),self.AND(ab,carry))
        return tuple(output)

    def less(self, left, right) -> int:
        width=max(len(left),len(right)); left,right=self.pad(left,width),self.pad(right,width)
        # More significant bits encountered later override the low-bit result.
        answer=self.false
        for a,b in zip(left,right):
            answer=self.OR(self.AND(-a,b),self.AND(-self.XOR(a,b),answer))
        return answer

    def less_const(self, bits, value: int) -> int:
        if value <= 0:
            return self.false
        if value >= 1<<len(bits):
            return self.true
        return self.less(bits,self.const(value,len(bits)))

    def equal_const(self, bits, value: int) -> int:
        if value < 0 or value >= 1<<len(bits):
            return self.false
        return self.all(bit if (value>>j)&1 else -bit for j,bit in enumerate(bits))

    def interval(self, bits, lo: int, hi: int) -> int:
        return self.AND(-self.less_const(bits,lo),self.less_const(bits,hi))

    def mask(self, bits, spans) -> int:
        return self.any(self.interval(bits,lo,hi) for lo,hi in spans)

    def modulo(self, bits, modulus: int):
        if modulus < 1:
            raise Invalid('positive Boolean modulus required')
        key=(tuple(bits),modulus)
        if key in self._mods:
            return self._mods[key]
        width=max(1,(modulus-1).bit_length())
        if modulus == 1:
            result=self.const(0,1)
        elif modulus&(modulus-1)==0:
            result=self.pad(bits,width)
        else:
            # A w+1-bit remainder can represent every intermediate below 2m.
            w=modulus.bit_length()+1
            rem=self.const(0,w)
            for bit in reversed(bits):
                shifted=(bit,)+rem[:-1]
                subtract=self.add(shifted,self.const((1<<w)-modulus,w),w)
                rem=self.mux(-self.less_const(shifted,modulus),subtract,shifted)
            result=rem[:width]
        self._mods[key]=result
        return result

    def affine(self, index, n: int, a: int, b: int):
        width=max(1,(a*(n-1)+b).bit_length())
        value=self.const(b,width)
        for j in range(a.bit_length()):
            if (a>>j)&1:
                shifted=(self.false,)*j+tuple(index)
                value=self.add(value,shifted,width)
        return self.modulo(value,n)

    def row(self, row, epoch: int, index, target):
        if row['epoch'] != epoch:
            return self.false
        source=self.interval(index,row['lo'],row['hi'])
        residue=self.equal_const(self.modulo(index,row['step']),row['residue'])
        return self.all((source,residue,self.mask(target,row['guard'])))

    def desired(self, policy, target):
        return self.AND(self.mask(target,policy['allow']),-self.mask(target,policy['exclude']))

    def evaluate(self, assignment: dict[str,int], check_clauses=True):
        if set(assignment)!=set(self.inputs):
            raise Invalid('incomplete circuit primary assignment')
        values={1:True}
        for name,bits in self.inputs.items():
            value=assignment[name]
            if type(value) is not int or not 0<=value<1<<len(bits):
                raise Invalid('primary input range')
            for j,bit in enumerate(bits):
                values[bit]=bool((value>>j)&1)
        def val(lit):
            return values[abs(lit)] if lit>0 else not values[abs(lit)]
        for v,operation,a,b in self.gates:
            values[v]=(val(a) and val(b)) if operation=='and' else (val(a)!=val(b))
        if len(values)!=self.variables:
            raise AssertionError('unconstrained or multiply defined Boolean variable')
        if check_clauses:
            return all(any(val(lit) for lit in clause) for clause in self.clauses)
        return values

    def write_dimacs(self, stream: TextIO):
        stream.write('c mask-aware exact local-defect tokens; bidirectional gates\n')
        for name,bits in self.inputs.items():
            stream.write('c input '+name+' '+' '.join(map(str,bits))+'\n')
        stream.write(f'p cnf {self.variables} {len(self.clauses)}\n')
        for clause in self.clauses:
            stream.write(' '.join(map(str,clause))+' 0\n')


def _tokens(c: Circuit, index, target, policy, multiplicity, prefix: int, max_m: int):
    # m=0 contributes one omission token; m>=1 contributes (m-1)^2
    # authorized tokens. Unauthorized targets contribute m tokens, not m^2.
    width=len(multiplicity)
    p=c.input('p',width); q=c.input('q',width)
    desired=c.desired(policy,target)
    zero=c.equal_const(multiplicity,0)
    predecessor=c.add(multiplicity,c.const((1<<width)-1,width),width)
    bothzero=c.AND(c.equal_const(p,0),c.equal_const(q,0))
    square=c.all((-zero,c.less(p,predecessor),c.less(q,predecessor)))
    authorized=c.OR(c.AND(zero,bothzero),square)
    forbidden=c.AND(c.less(p,multiplicity),c.equal_const(q,0))
    fault=c.OR(c.AND(desired,authorized),c.AND(-desired,forbidden))
    c.emit((c.AND(c.less_const(index,prefix),fault),))
    return c


def encode_full(spec: dict, plan: dict, epoch: int=0, prefix: int|None=None) -> Circuit:
    validate(spec,plan)
    n=spec['n']; integer(epoch,0,len(spec['epochs'])-1)
    if prefix is None: prefix=n
    integer(prefix,0,n)
    c=Circuit(); index=c.input('i',max(1,(n-1).bit_length()))
    target=c.affine(index,n,spec['a'],spec['b'])
    rows=[row for row in spec['history']+plan['future'] if row['epoch']==epoch]
    width=max(1,len(rows).bit_length())
    multiplicity=c.const(0,width)
    for row in rows:
        multiplicity=c.add(multiplicity,(c.row(row,epoch,index,target),),width)
    return _tokens(c,index,target,spec['epochs'][epoch],multiplicity,prefix,len(rows))


def encode_update(anchor, spec: dict, plan: dict, epoch: int=0, prefix: int|None=None) -> Circuit:
    # Import the checker capability, never a producer or an arithmetic oracle.
    from .update_checker import SafeAnchor, _difference
    if type(anchor) is not SafeAnchor:
        raise Invalid('safe anchor required for reduced Boolean encoding')
    old_spec,old_plan=anchor.inputs()
    validate(spec,plan)
    if (any(spec[k]!=old_spec[k] for k in ('n','a','b'))
        or len(spec['epochs'])!=len(old_spec['epochs'])
        or spec['history']!=old_spec['history']):
        raise Invalid('incompatible anchor context/history')
    n=spec['n']; integer(epoch,0,len(spec['epochs'])-1)
    if prefix is None:prefix=n
    integer(prefix,0,n)
    removed,added=_difference(old_plan,plan)
    R=[old_plan['future'][j] for j in removed if old_plan['future'][j]['epoch']==epoch]
    A=[plan['future'][j] for j in added if plan['future'][j]['epoch']==epoch]
    c=Circuit(); index=c.input('i',max(1,(n-1).bit_length()))
    target=c.affine(index,n,spec['a'],spec['b'])
    old_wanted=c.desired(old_spec['epochs'][epoch],target)
    removed_bit=c.any(c.row(row,epoch,index,target) for row in R)
    background=c.AND(old_wanted,-removed_bit)
    width=max(1,(len(A)+1).bit_length())
    multiplicity=c.pad((background,),width)
    for row in A:
        multiplicity=c.add(multiplicity,(c.row(row,epoch,index,target),),width)
    return _tokens(c,index,target,spec['epochs'][epoch],multiplicity,prefix,len(A)+1)
