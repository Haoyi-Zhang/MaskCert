"""Owned finite schemas, not imported scanner configurations."""
from copy import deepcopy
import random
from math import gcd

def spans_from_bits(bits):
    result=[]; start=None
    for i,bit in enumerate(bits+[False]):
        if bit and start is None: start=i
        if not bit and start is not None:
            result.append([start,i]); start=None
    return result

def mkrow(e,l,h,s,r,g):
    return dict(epoch=e,lo=l,hi=h,step=s,residue=r,guard=deepcopy(g))

def base(n,a=1,b=0,old=3,new=5,epochs=1,exclusions=True):
    a%=n; b%=n
    if gcd(a,n)!=1: raise ValueError('bad test map')
    cut=n//3
    # Intervals scale with n, never with a real address.
    exclude=([[n//3,2*n//3]] if n>=3 and exclusions else [])
    spec=dict(n=n,a=a,b=b,epochs=[],history=[])
    future=[]
    for e in range(epochs):
        allow=[[0,n]] if e%2==0 or n<2 else [[n//2,n]]
        spec['epochs'].append(dict(allow=allow,exclude=deepcopy(exclude)))
        # Calculate guards via elementary interval slicing here, independent of src.
        bounds=sorted({0,n,*[x for p in allow+exclude for x in p]})
        guard=[]
        for l,h in zip(bounds,bounds[1:]):
            if any(u<=l<v for u,v in allow) and not any(u<=l<v for u,v in exclude):
                if guard and guard[-1][1]==l: guard[-1][1]=h
                else: guard.append([l,h])
        for r in range(old): spec['history'].append(mkrow(e,0,cut,old,r,guard))
        for r in range(new): future.append(mkrow(e,cut,n,new,r,guard))
    plan=dict(context={k:spec[k] for k in ('n','a','b')},future=future)
    return spec,plan

def arbitrary(seed,n):
    rng=random.Random(seed)
    coprime=[x for x in range(n) if gcd(x,n)==1]
    a=rng.choice(coprime); b=rng.randrange(n)
    allow=spans_from_bits([rng.randrange(4)>0 for _ in range(n)])
    exclude=spans_from_bits([rng.randrange(5)==0 for _ in range(n)])
    spec=dict(n=n,a=a,b=b,epochs=[dict(allow=allow,exclude=exclude)],history=[])
    rows=[]
    for _ in range(rng.randrange(1,10)):
        l=rng.randrange(n+1); h=rng.randrange(l,n+1); s=rng.randrange(1,9)
        guard=spans_from_bits([rng.randrange(3)>0 for _ in range(n)])
        rows.append(mkrow(0,l,h,s,rng.randrange(s),guard))
    return spec,dict(context={k:spec[k] for k in ('n','a','b')},future=rows)
