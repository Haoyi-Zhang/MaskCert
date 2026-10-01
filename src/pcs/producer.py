"""Untrusted producer: Euclidean transcripts and symbolic defect evaluation."""
from __future__ import annotations
from math import gcd
import json
from typing import Callable, TextIO
from .model import validate, integer


def overlap(xs, ys):
    out=[]; i=j=0
    while i < len(xs) and j < len(ys):
        l=max(xs[i][0],ys[j][0]); h=min(xs[i][1],ys[j][1])
        if l < h: out.append([l,h])
        if xs[i][1] <= ys[j][1]: i+=1
        else: j+=1
    return out


def subtract(xs, ys):
    out=[]
    for l,h in xs:
        c=l
        for u,v in ys:
            if v <= c: continue
            if u >= h: break
            if c < u: out.append([c,min(u,h)])
            c=max(c,v)
            if c >= h: break
        if c < h: out.append([c,h])
    return out


def progression(r, prefix):
    lo=r['lo']; hi=min(r['hi'],prefix); s=r['step']; rem=r['residue']
    first=lo+(rem-lo)%s
    return (first,s,max(0,(hi-1-first)//s+1))


def intersect_rows(x,y,prefix):
    lo=max(x['lo'],y['lo']); hi=min(x['hi'],y['hi'],prefix)
    s=x['step']; t=y['step']; g=gcd(s,t)
    delta=y['residue']-x['residue']
    if delta % g or lo >= hi: return (0,1,0)
    q=t//g
    k=0 if q==1 else (delta//g * pow(s//g,-1,q))%q
    step=s*q; rem=(x['residue']+s*k)%step
    first=lo+(rem-lo)%step
    return (first,step,max(0,(hi-1-first)//step+1))


def floor_value(n,m,a,b):
    total=0
    while True:
        qa,a=divmod(a,m); qb,b=divmod(b,m)
        total += qa*n*(n-1)//2 + qb*n
        y=a*n+b
        if y < m: return total
        n,b=divmod(y,m); m,a=a,m


def floor_transcript(n,m,a,b):
    total=0; steps=[]
    while True:
        qa,a0=divmod(a,m); qb,b0=divmod(b,m)
        total += qa*n*(n-1)//2 + qb*n
        h,rem=divmod(a0*n+b0,m)
        steps.append([qa,qb,h])
        if h==0: return total,steps
        n,m,a,b=h,a0,m,rem


def count(ap, masks, n,a,b, floor):
    first,step,length=ap
    if length==0 or not masks: return 0
    if masks==[[0,n]]: return length
    aa=a*step; bb=a*first+b
    return sum(floor(length,n,aa,bb+n-l)-floor(length,n,aa,bb+n-h)
               for l,h in masks)


def defects(spec,plan,prefix=None, floor=floor_value):
    validate(spec,plan)
    n,a,b=(spec[k] for k in ('n','a','b'))
    if prefix is None: prefix=n
    integer(prefix,0,n)
    rows=spec['history']+plan['future']; out=[]
    for e,policy in enumerate(spec['epochs']):
        allowed=subtract(policy['allow'],policy['exclude'])
        rs=[r for r in rows if r['epoch']==e]
        base=count((0,1,prefix),allowed,n,a,b,floor)
        mass=auth=pairs=0
        for r in rs:
            p=progression(r,prefix)
            mass+=count(p,r['guard'],n,a,b,floor)
            auth+=count(p,overlap(r['guard'],allowed),n,a,b,floor)
        for i,x in enumerate(rs):
            for y in rs[i+1:]:
                p=intersect_rows(x,y,prefix)
                if p[2]==0: continue
                g=overlap(overlap(x['guard'],y['guard']),allowed)
                pairs+=count(p,g,n,a,b,floor)
        out.append(base+mass-2*auth+2*pairs)
    return out


def write_certificate(spec,plan,stream: TextIO,prefix=None):
    validate(spec,plan)
    if prefix is None: prefix=spec['n']
    integer(prefix,0,spec['n'])
    def emit(x): stream.write(json.dumps(x,separators=(',',':'))+'\n')
    emit({'prefix':prefix})
    def witnessed(n,m,a,b):
        value,steps=floor_transcript(n,m,a,b)
        emit([value,steps]); return value
    ds=defects(spec,plan,prefix,witnessed)
    emit({'defects':ds,'accepted':all(d==0 for d in ds)})
    return ds


def locate(spec,plan):
    """Least (epoch,counter) defect; not a shortest physical execution trace."""
    ds=defects(spec,plan)
    if not any(ds): return None
    e=next(i for i,d in enumerate(ds) if d)
    low,high=0,spec['n']
    while high-low > 1:
        mid=(low+high)//2
        if defects(spec,plan,mid)[e]: high=mid
        else: low=mid
    x=low; target=(spec['a']*x+spec['b'])%spec['n']
    allowed=subtract(spec['epochs'][e]['allow'],spec['epochs'][e]['exclude'])
    authorized=any(l<=target<h for l,h in allowed)
    hits=[]
    for i,r in enumerate(spec['history']+plan['future']):
        if (r['epoch']==e and r['lo']<=x<r['hi'] and x%r['step']==r['residue']
            and any(l<=target<h for l,h in r['guard'])):
            hits.append(i)
    kind='forbidden' if not authorized else ('omission' if not hits else 'collision')
    return {'epoch':e,'counter':x,'target':target,'kind':kind,
            'rows':hits[:2] if kind=='collision' else hits[:1]}
