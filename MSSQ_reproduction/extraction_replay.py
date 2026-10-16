"""从采用回答重新提取明确答案，并核对随包提取记录。
输入：原文、任务合同、形式变量列表及已经记录的个案判读；输出统一候选。
流程：复用各实验原有解析器；明确个案沿用附带记录，其他回答重跑文本解析。
只检查提取是否一致，正确性由独立验证器计算，不以Gold补全模型答案。
"""
from pathlib import Path
import json,re
import scoring,repeat_recovery,s02_components,feedback_recovery,evidence_glm_decisions,evidence_intent
ROOT=Path(__file__).resolve().parent
def j(name):return json.loads((ROOT/name).read_text(encoding='utf8'))
def yn(a):return {'yes':True,'no':False,'true':True,'false':False,'是':True,'否':False,'存在':True,'不存在':False}.get(str(a).strip().lower())
def obj(t):
 for i,c in enumerate(t):
  if c!='{':continue
  try:o,_=json.JSONDecoder().raw_decode(t[i:])
  except ValueError:continue
  if isinstance(o,dict) and any(k in o for k in ['answer','judgment','assignment']):return o
 if t.strip().upper() in ['YES','NO','NONE','是','否','不存在']:return {'answer':t.strip()}
 return {}
def frequency(o,q,task):
 if task in ['must','may']:
  a=yn(o.get('answer',o.get('judgment')));return {'answer':a,'construction':None} if a is not None else None
 a=o.get('assignment')
 if isinstance(a,dict):
  nodes=q['family_payload']['nodes']
  if set(nodes)<=set(a):a={n:a[n] for n in nodes}
  return {'answer':True,'construction':a}
 if str(o.get('answer',o.get('judgment',''))).strip().lower() in ['none','no','不存在','无','否'] or a=='NONE' or 'assignment' in o and a is None:return {'answer':False,'construction':None}
 return None
def verify(name,e,q):
 r,x,raw=e['item'],e['extraction'],e['response'];text=raw.get('response_text') or '';method=x['method']
 if name=='MAIN':
  if method in ['recorded_adjudication','recorded_final_answer']:return
  c,_=scoring.recover_from_text(r['family'],r['task'],text)
  if c is None:
   reasoning=raw.get('reasoning_content') or '';markers=list(re.finditer(r'(?:FINAL\s+ANSWER|FINAL|最终答案)\s*[:：]',reasoning,re.I))
   if len(markers)==1:c,_=scoring.recover_from_text(r['family'],r['task'],reasoning[markers[0].end():])
 elif name=='S01':
  if method=='final_answer':c=frequency(obj(text),q,r['task'])
  elif method=='terminal_unavailable':c=None
  else:
   key='|'.join(r[k] for k in ['model','family','language','prompt_id']);a=j('inputs/s01_recovery.json')[key]
   contract=j('inputs/contracts.json').get('|'.join(r[k] for k in ['family','language','prompt_id']))
   c,_,_=repeat_recovery.recover_adopted_candidate(a,{'slot':r,'quartet':q,'contract':contract},raw)
 elif name=='S05':
  if method=='final_fields':c=frequency(obj(text),q,r['task'])
  else:
   qq=dict(q)
   if r['family']=='scheduling' and isinstance(q['profile'],str):qq['profile']=j('configs/profiles.json')['profiles'][q['profile']]
   a,err=feedback_recovery.recover(r|{'_bundled_quartet':qq},text);c=None
   if err is None:c={'answer':a!='NONE','construction':None if a=='NONE' else a.get('schedule') if r['family']=='scheduling' and isinstance(a,dict) else a}
 else:return
 assert c==x['candidate'],(name,r['model'],r['prompt_id'],'extraction mismatch')
def joint(e,q):
 r,x,raw=e['item'],e['extraction'],e['response'];method=x['method']
 if method=='existing_explicit_adoption':return
 if method=='final_fields':
  o=obj(raw.get('response_text') or '');a=yn(o.get('judgment',o.get('answer')));c=o.get('assignment')
 else:
  m=j('inputs/joint_contracts.json')[r['prompt_id']];v=s02_components.extract({'model':r['model'],'manifest':m,'response':raw,'stream_payload':[raw.get('response_text') or '',raw.get('reasoning_content') or '']})
  labels=m['response_contract']['judgment_labels'];a=True if v['judgment']==labels[0] else False if v['judgment']==labels[1] else None;c=v['construction']
 if r['family']=='frequency_assignment' and isinstance(c,dict) and set(q['family_payload']['nodes'])<=set(c):c={n:c[n] for n in q['family_payload']['nodes']}
 assert (a,c)==(x['judgment'],x['construction']),(r['model'],r['prompt_id'],'joint extraction')
def candidate(e):
 r,x,raw=e['item'],e['extraction'],e['response'];text=raw.get('response_text') or ''
 if x['method'] in ['final_fields','explicit_final_prose']:
  o=obj(text);a=yn(o.get('answer'));cv=o.get('candidate_valid');ph=o.get('candidate_proposition_holds')
  if x['method']=='explicit_final_prose':
   assert 'the supplied assignment is consistent and also has D01=D04=F3' in text;cv=ph=True
 else:
  meta=r|{'final_text':text,'condition':'no_candidate' if r['condition_code']=='A' else 'candidate'};prompt=raw['request']['body']['messages'][0]['content']
  v=evidence_glm_decisions.read_final_intent(meta,prompt) if r['model']=='GLM-5.2' else evidence_intent.evaluate(text,meta,prompt)
  a=yn(v['answer']);cv=v['candidate_valid_response'];ph=v['proposition_response']
 assert (a,cv,ph)==(x['answer'],x['candidate_valid'],x['proposition_holds']),(r['model'],r['request_id'],'candidate extraction')
