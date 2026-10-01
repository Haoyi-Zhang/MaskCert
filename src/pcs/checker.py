"""Separate symbolic checker. Does not import the producer or its arithmetic.
The JSON/schema validation and Python integer runtime are shared trusted code.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from .model import (Invalid, validate, integer, keys, loads,
                    MAX_CERTIFICATE_BYTES, MAX_CERTIFICATE_LINE_BYTES,
                    MAX_FLOOR_STEPS, MAX_TRANSCRIPT_INTEGER)


def meet(left,right):
    # Endpoint sweep rather than the producer's two-pointer intersection.
    events=[]
    for source,spans in enumerate((left,right)):
        for l,h in spans:
            events.extend(((l,source,1),(h,source,-1)))
    events.sort(); active=[0,0]; result=[]; previous=None
    i=0
    while i < len(events):
        point=events[i][0]
        if previous is not None and previous<point and active==[1,1]:
            if result and result[-1][1]==previous: result[-1][1]=point
            else: result.append([previous,point])
        while i<len(events) and events[i][0]==point:
            _,source,delta=events[i]; active[source]+=delta; i+=1
        previous=point
    return result


def permitted(policy,n):
    complement=[]; last=0
    for lo,hi in policy['exclude']:
        if last<lo: complement.append([last,lo])
        last=hi
    if last<n: complement.append([last,n])
    return meet(policy['allow'],complement)


def extended(a,b):
    old_r,r=a,b; old_s,s=1,0; old_t,t=0,1
    while r:
        q=old_r//r
        old_r,r=r,old_r-q*r
        old_s,s=s,old_s-q*s
        old_t,t=t,old_t-q*t
    return old_r,old_s,old_t


def lattice(rows,prefix):
    lo=0; hi=prefix; modulus=1; residue=0
    for row in rows:
        lo=max(lo,row['lo']); hi=min(hi,row['hi'])
        step=row['step']; other=row['residue']
        g,u,_=extended(modulus,step)
        diff=other-residue
        if diff%g: return (0,1,0)
        new_modulus=modulus*(step//g)
        residue=(residue+modulus*(diff//g)*u)%new_modulus
        modulus=new_modulus
    start=residue+(-((residue-lo)//modulus))*modulus
    length=0 if start>=hi else (hi-start+modulus-1)//modulus
    return (start,modulus,length)


class TranscriptReader:
    def __init__(self,lines: Iterable[str]):
        self.lines=iter(lines); self.bytes=0; self.calls=0; self.steps=0
    def take(self):
        try: line=next(self.lines)
        except StopIteration as ex: raise Invalid('truncated certificate') from ex
        self.bytes+=len(line.encode('utf-8'))
        encoded = line.encode('utf-8')
        if len(encoded) > MAX_CERTIFICATE_LINE_BYTES:
            raise Invalid('certificate line byte bound')
        if self.bytes > MAX_CERTIFICATE_BYTES:
            raise Invalid('certificate total byte bound')
        return loads(line)
    def finish(self):
        try: next(self.lines)
        except StopIteration: return
        raise Invalid('trailing certificate records')
    def floor(self,n,m,a,b):
        record=self.take(); self.calls+=1
        if type(record) is not list or len(record)!=2:
            raise Invalid('floor record shape')
        value=integer(record[0], 0, MAX_TRANSCRIPT_INTEGER); steps=record[1]
        if type(steps) is not list or not 1 <= len(steps) <= MAX_FLOOR_STEPS:
            raise Invalid('Euclidean transcript length')
        expected=0
        for position,step in enumerate(steps):
            self.steps+=1
            if type(step) is not list or len(step)!=3:
                raise Invalid('Euclidean step shape')
            qa,qb,h=(integer(v, 0, MAX_TRANSCRIPT_INTEGER) for v in step)
            ra=a-qa*m; rb=b-qb*m
            if not (0<=ra<m and 0<=rb<m):
                raise Invalid('invalid quotient witness')
            expected += qa*n*(n-1)//2 + qb*n
            remainder=ra*n+rb-h*m
            if not 0<=remainder<m:
                raise Invalid('invalid transpose witness')
            if h==0:
                if position+1!=len(steps) or expected!=value:
                    raise Invalid('bad terminal value')
                return value
            if ra==0: raise Invalid('zero next modulus')
            n,m,a,b=h,ra,m,remainder
        raise Invalid('missing terminal step')


def masked(lattice_,mask,n,a,b,reader):
    first,delta,number=lattice_
    if not mask or number==0: return 0
    if len(mask)==1 and mask[0]==[0,n]: return number
    result=0
    for low,high in mask:
        upper=reader.floor(number,n,a*delta,a*first+b+n-low)
        lower=reader.floor(number,n,a*delta,a*first+b+n-high)
        result+=upper-lower
    return result


@dataclass(frozen=True)
class Checked:
    accepted: bool
    defects: tuple[int,...]
    calls: int
    steps: int
    certificate_bytes: int


def verify(spec,plan,lines,prefix=None):
    validate(spec,plan)
    n=spec['n']; a=spec['a']; b=spec['b']
    if prefix is None: prefix=n
    integer(prefix,0,n)
    reader=TranscriptReader(lines)
    header=reader.take(); keys(header,{'prefix'})
    integer(header['prefix'],0,n)
    if header['prefix']!=prefix: raise Invalid('wrong certificate prefix')
    all_rows=spec['history']+plan['future']; defects=[]
    for epoch,policy in enumerate(spec['epochs']):
        desired=permitted(policy,n)
        selected=[r for r in all_rows if r['epoch']==epoch]
        base=masked((0,1,prefix),desired,n,a,b,reader)
        terms=base
        for row in selected:
            grid=lattice([row],prefix)
            terms+=masked(grid,row['guard'],n,a,b,reader)
            terms-=2*masked(grid,meet(row['guard'],desired),n,a,b,reader)
        for left in range(len(selected)):
            for right in range(left+1,len(selected)):
                pair=lattice([selected[left],selected[right]],prefix)
                if pair[2]==0: continue
                mask=meet(meet(selected[left]['guard'],selected[right]['guard']),desired)
                terms+=2*masked(pair,mask,n,a,b,reader)
        if terms<0: raise Invalid('negative defect contradicts invariants')
        defects.append(terms)
    trailer=reader.take(); keys(trailer,{'defects','accepted'})
    if (type(trailer['defects']) is not list or len(trailer['defects'])!=len(defects)
        or any(type(x) is not int for x in trailer['defects'])
        or type(trailer['accepted']) is not bool):
        raise Invalid('trailer types')
    accepted=not any(defects)
    if trailer['defects']!=defects or trailer['accepted']!=accepted:
        raise Invalid('trailer mismatch')
    reader.finish()
    return Checked(accepted,tuple(defects),reader.calls,reader.steps,reader.bytes)


def check_witness(spec,plan,witness,full_lines,before_lines,through_lines):
    """Check least canonical defective rank using two prefix certificates."""
    full=verify(spec,plan,full_lines)
    if full.accepted: raise Invalid('safe plan has no defect witness')
    keys(witness,{'epoch','counter','target','kind','rows'})
    e=integer(witness['epoch'],0,len(spec['epochs'])-1)
    x=integer(witness['counter'],0,spec['n']-1)
    if any(full.defects[:e]) or not full.defects[e]:
        raise Invalid('not the first defective epoch')
    before=verify(spec,plan,before_lines,x)
    through=verify(spec,plan,through_lines,x+1)
    if before.defects[e]!=0 or through.defects[e]<=0:
        raise Invalid('not the first defective rank')
    y=(spec['a']*x+spec['b'])%spec['n']
    integer(witness['target'],0,spec['n']-1)
    if y!=witness['target']: raise Invalid('wrong target')
    u=permitted(spec['epochs'][e],spec['n'])
    allowed=any(l<=y<h for l,h in u)
    hits=[]
    for j,r in enumerate(spec['history']+plan['future']):
        if (r['epoch']==e and r['lo']<=x<r['hi'] and x%r['step']==r['residue']
            and any(l<=y<h for l,h in r['guard'])): hits.append(j)
    kind='forbidden' if not allowed else ('omission' if len(hits)==0 else 'collision')
    chosen=hits[:2] if kind=='collision' else hits[:1]
    if (type(witness['rows']) is not list or any(type(i) is not int for i in witness['rows'])
        or witness['kind']!=kind or witness['rows']!=chosen):
        raise Invalid('invalid event witness')
    return True
