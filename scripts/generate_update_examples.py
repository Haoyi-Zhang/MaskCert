"""Generate the documented cold/warm update examples in the current copy."""
from common import ROOT,bounded,finish
bounded()
from copy import deepcopy
from io import StringIO
import json
from pcs.producer import write_certificate
from pcs.update_producer import write_update,locate_update
from pcs.update_checker import establish_anchor,verify_update,check_update_witness

def main():
 directory=ROOT/'examples/updates';directory.mkdir(parents=True,exist_ok=True)
 spec={'n':64,'a':5,'b':7,'epochs':[{'allow':[[0,64]],'exclude':[]}],'history':[]}
 def row(lo,hi): return {'epoch':0,'lo':lo,'hi':hi,'step':1,'residue':0,'guard':[[0,64]]}
 old={'context':{k:spec[k] for k in ('n','a','b')},'future':[row(0,64)]}
 safe=deepcopy(old);safe['future']=[row(0,32),row(32,64)]
 unsafe=deepcopy(old);unsafe['future']=[row(0,2),row(3,64)]
 for name,obj in [('declaration',spec),('old-plan',old),('safe-plan',safe),('unsafe-plan',unsafe)]:
  (directory/(name+'.json')).write_text(json.dumps(obj,indent=2)+'\n')
 base=StringIO();write_certificate(spec,old,base);raw=base.getvalue()
 (directory/'old-certificate.jsonl').write_text(raw)
 anchor=establish_anchor(spec,old,StringIO(raw));results={}
 for name,plan in [('safe',safe),('unsafe',unsafe)]:
  stream=StringIO();write_update(spec,old,spec,plan,stream);text=stream.getvalue()
  (directory/(name+'-update.jsonl')).write_text(text)
  result=verify_update(anchor,spec,plan,StringIO(text));assert result.accepted==(name=='safe')
  results[name]={'defects':result.defects,'accepted':result.accepted}
 witness=locate_update(spec,old,spec,unsafe)
 assert witness=={'epoch':0,'counter':2,'target':17,'kind':'omission','rows':[]}
 bundle=directory/'witness';bundle.mkdir(exist_ok=True);certs=[]
 for filename,prefix in [('full',None),('before',witness['counter']),('through',witness['counter']+1)]:
  stream=StringIO();write_update(spec,old,spec,unsafe,stream,prefix);text=stream.getvalue();certs.append(text)
  (bundle/(filename+'.jsonl')).write_text(text)
 (bundle/'witness.json').write_text(json.dumps(witness,indent=2)+'\n')
 assert check_update_witness(anchor,spec,unsafe,witness,*(StringIO(t) for t in certs))
 finish('update-examples.json',dict(all_checks_passed=True,examples=results,witness=witness,
     provenance='same small API-contract plans; not added as independent performance workloads'))
if __name__=='__main__':main()
