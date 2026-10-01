"""Bounded exact oracles; neither imports symbolic arithmetic."""
from array import array
from .model import validate, Invalid, integer, EXPLICIT_ORACLE_LIMIT


def is_allowed(policy,y):
    return (any(l<=y<h for l,h in policy['allow'])
            and not any(l<=y<h for l,h in policy['exclude']))


def require_explicit_domain(n):
    integer(n, 1, EXPLICIT_ORACLE_LIMIT)
    return n


def enumerate_counters(spec,plan,prefix=None):
    validate(spec,plan)
    n=require_explicit_domain(spec['n'])
    if prefix is None: prefix=n
    integer(prefix, 0, n)
    out=[]; first=None
    for e,pol in enumerate(spec['epochs']):
        defect=0
        for x in range(prefix):
            y=(spec['a']*x+spec['b'])%n
            ids=[j for j,r in enumerate(spec['history']+plan['future'])
                 if r['epoch']==e and r['lo']<=x<r['hi'] and x%r['step']==r['residue']
                 and any(l<=y<h for l,h in r['guard'])]
            permitted=is_allowed(pol,y)
            local=(len(ids)-1)**2 if permitted else len(ids)
            defect+=local
            if local and first is None:
                kind='forbidden' if not permitted else ('omission' if not ids else 'collision')
                first={'epoch':e,'counter':x,'target':y,'kind':kind,
                       'rows':ids[:2] if kind=='collision' else ids[:1]}
        out.append(defect)
    return out,first


def replay_audit(spec,plan):
    validate(spec,plan); n=require_explicit_domain(spec['n'])
    defects=[]
    for e,pol in enumerate(spec['epochs']):
        seen=array('I',[0])*n
        for r in spec['history']+plan['future']:
            if r['epoch']!=e: continue
            first=next((x for x in range(r['lo'],min(r['hi'],r['lo']+r['step']))
                        if x%r['step']==r['residue']),r['hi'])
            for x in range(first,r['hi'],r['step']):
                y=(spec['a']*x+spec['b'])%n
                if any(l<=y<h for l,h in r['guard']): seen[y]+=1
        defects.append(sum((v-1)**2 if is_allowed(pol,y) else v for y,v in enumerate(seen)))
    return defects
