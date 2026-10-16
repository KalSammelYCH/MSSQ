"""对外离线复现入口。
输入：采用回答、与原文绑定的答案提取记录、形式问题和完整解集。
输出：新目录中的逐题评分、主实验与补充实验统计、区间和核验报告。
流程：先校验文件哈希；对已提取的明确答案重新运行确定性验证器；将计算结果
与参考值对照，再按论文规定的整CSP抽样及同题配对生成统计。不发网络请求，
不重新选择采用回答，不覆盖输入或已有输出。答案提取记录可与附带原文人工对照。
"""
from pathlib import Path
from collections import Counter,defaultdict
from itertools import permutations
import argparse,csv,gzip,hashlib,json,random,subprocess,sys
import numpy as np
import extraction_replay
from functools import lru_cache
import scoring as s,statistics_main as b,evidence_support,main_counts,s02_intervals
ROOT=Path(__file__).resolve().parent
def j(p):return json.loads(p.read_text(encoding='utf8'))
def jl(p):return [json.loads(x) for x in p.read_text(encoding='utf8').splitlines() if x.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def write(p,rs):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',encoding='utf8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rs for k in r)));w.writeheader();w.writerows(rs)
def records(name):
 with gzip.open(ROOT/'responses'/(name+'.jsonl.gz'),'rt',encoding='utf8') as f:
  for line in f:yield json.loads(line)
def ik(r):return tuple(r[k] for k in ['model','family','language','quartet_id','task'])
def equivalent(a,z):
 if isinstance(a,dict):return a.keys()==z.keys() and all(equivalent(a[k],z[k]) for k in a)
 if isinstance(a,list):return len(a)==len(z) and all(equivalent(x,y) for x,y in zip(a,z))
 if isinstance(a,(float,int)) and not isinstance(a,bool):return abs(a-z)<1e-9
 return a==z
@lru_cache(maxsize=3)
def solution_index(family):
 return {r['csp_id']:{json.dumps(a,sort_keys=True) for a in r['solutions']} for r in jl(ROOT/'formal'/family/'csps.jsonl')}
def membership(r,q,c,v):
 if not v['construction_complete']:return
 a=c['construction']
 if r['family']=='scheduling':
  profile=q['profile'];profile=j(ROOT/'configs/profiles.json')['profiles'][profile] if isinstance(profile,str) else profile
  a,_=s._schedule_to_assignment(a,profile)
 legal=json.dumps(a,sort_keys=True) in solution_index(r['family'])[q['csp_id']]
 assert legal==v['public_constraints_valid'],(r['model'],r['prompt_id'],'solution-set membership')
def replay(name,Q):
 rows=[]
 for e in records(name):
  r=e['item'];x=e['extraction'];raw=e['response'];q=Q[r['family'],r['quartet_id']]
  if 'response_text_sha256' in x:assert hashlib.sha256((raw.get('response_text') or '').encode()).hexdigest()==x['response_text_sha256']
  extraction_replay.verify(name,e,q)
  v=s.evaluate_candidate({'slot':r|{'gold_must':q['gold_must'],'gold_may':q['gold_may']},'quartet':q},x['candidate'])
  membership(r,q,x['candidate'],v)
  success=bool(x.get('recoverable',True) and v['strict_success'])
  assert success==(r['task_success'] is True),(name,r['model'],r['prompt_id'])
  r.update(task_success=success)
  rows.append(r)
 return rows
def pairing(qr):
 modes=b.MODALITIES;langs=['en','zh'];models=sorted(b.MODELS);blocks=defaultdict(set)
 for r in qr:blocks[r['family'],r['stratum']].add(r['csp_id'])
 index={(r['model'],r['family'],r['csp_id'],r['gold_modality'],r['language']):r for r in qr}
 def flags(r):return (int(r['must_task_success'] and r['may_task_success']),int(r['witness_task_success'] and r['counterexample_task_success']))
 pmf=np.array([1.]);observed=0;cross=Counter(flags(r) for r in qr)
 for (fam,st),cs in sorted(blocks.items()):
  cs=sorted(cs);assert len(cs)==4
  a=np.array([[[[flags(index[m,fam,c,g,l]) for l in langs] for g in modes] for c in cs] for m in models])
  jj,cc=a[...,0],a[...,1];observed+=int((jj*cc).sum())
  vals=[int((jj*cc[:,list(p)]).sum()) for p in permutations(range(4))]
  pmf=np.convolve(pmf,np.bincount(vals)/24)
 return dict(observed=observed,expected=float(pmf@np.arange(len(pmf))),reference_low=int(np.searchsorted(pmf.cumsum(),.025)),reference_high=int(np.searchsorted(pmf.cumsum(),.975)),both=cross[1,1],judgment_only=cross[1,0],construction_only=cross[0,1],neither=cross[0,0])
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--skip-bootstrap',action='store_true');args=p.parse_args();out=args.output.resolve()
 assert not out.exists(),'Choose a new output directory.'
 assert not out.is_relative_to(ROOT),'Output must be outside the reproduction folder.'
 for name,hashvalue in j(ROOT/'manifest.json')['files'].items():assert sha(ROOT/name)==hashvalue,name
 out.mkdir(parents=True)
 Q={(fam,r['quartet_id']):r for fam in b.FAMILIES for r in jl(ROOT/'formal'/fam/'quartets.jsonl')}
 profiles=j(ROOT/'configs/profiles.json')['profiles']
 # Independently recount both subspaces from complete stored solution sets.
 gold=[]
 for fam in b.FAMILIES:
  cs={r['csp_id']:r for r in jl(ROOT/'formal'/fam/'csps.jsonl')}
  for (ff,qid),q in Q.items():
   if ff!=fam:continue
   sols=cs[q['csp_id']]['solutions'];positive=0
   for a in sols:
    valid,holds=evidence_support.check(fam,q,a,profiles);assert valid;positive+=holds
   assert q['gold_must']==(positive==len(sols)) and q['gold_may']==(positive>0)
   assert positive==q['support_count']
   gold.append(dict(family=fam,quartet_id=qid,positive=positive,negative=len(sols)-positive))
 write(out/'gold_counts.csv',gold)
 rows=replay('MAIN',Q);assert len(rows)==4608 and sum(r['task_success'] for r in rows)==2399
 write(out/'main/item_results.csv',rows);mm={ik(r):r for r in rows}
 qr=b.build_quartet_records(rows);directions=b.build_contingent_direction_records(rows)
 for q in qr:
  for task in b.TASKS:q[task+'_task_success']=mm[tuple(q[k] for k in ['model','family','language','quartet_id'])+(task,)]['task_success']
 write(out/'main/quartet_relations.csv',qr)
 counts,contrib,events,split=main_counts.detail_counts(rows)
 assert counts==j(ROOT/'reference/main/counts.json');save(out/'main/counts.json',counts);write(out/'main/compatibility_split.csv',split);write(out/'main/wrong_judgment_quartets.csv',events)
 for dims in [['model'],['model','family'],['model','language'],['model','task'],['model','modality']]:write(out/'main'/('_'.join(dims)+'.csv'),b.group_metrics(rows,dims))
 for dims in [['model'],['model','task']]:write(out/'main'/('resources_'+'_'.join(dims)+'.csv'),b.resource_summary(rows,dims))
 pair=pairing(qr);assert pair['observed']==157 and abs(pair['expected']-139.75)<1e-9 and (pair['reference_low'],pair['reference_high'])==(128,152);save(out/'pairing.json',pair)
 print('MAIN scores, formal Gold and pairing reference verified.',flush=True)
 repeat=replay('S01',Q);assert len(repeat)==768 and sum(r['task_success'] for r in repeat)==302
 save(out/'s01/item_results.json',repeat);first=[mm[ik(r)] for r in repeat];a=b.build_quartet_records(first);z=b.build_quartet_records(repeat)
 qkey=lambda r:tuple(r[k] for k in ['model','family','language','quartet_id']);za={qkey(r):r for r in z};summary={}
 for model in ['ALL pooled']+b.MODELS:
  rr=[r for r in repeat if model=='ALL pooled' or r['model']==model];mr=[r for r in first if model=='ALL pooled' or r['model']==model];qq=[q for q in a if model=='ALL pooled' or q['model']==model]
  summary[model]={'main_correct':sum(r['task_success'] is True for r in mr),'repeat_correct':sum(r['task_success'] is True for r in rr),'main_complete_constructions':sum(r['construction_complete'] is True for r in mr),'repeat_complete_constructions':sum(r['construction_complete'] is True for r in rr),'main_valid_constructions':sum(r['construction_valid'] is True for r in mr),'repeat_valid_constructions':sum(r['construction_valid'] is True for r in rr),'main_modal':sum(q['modal_recovery_status']=='correct' for q in qq),'repeat_modal':sum(za[qkey(q)]['modal_recovery_status']=='correct' for q in qq),'main_full':sum(q['full_quartet_success'] for q in qq),'repeat_full':sum(za[qkey(q)]['full_quartet_success'] for q in qq),'compatibility_stable':sum(q['compatibility_status']==za[qkey(q)]['compatibility_status'] for q in qq),'main_compatibility':dict(Counter(q['compatibility_status'] for q in qq)),'repeat_compatibility':dict(Counter(za[qkey(q)]['compatibility_status'] for q in qq)),'full_transitions':dict(Counter('both' if q['full_quartet_success'] and za[qkey(q)]['full_quartet_success'] else 'lost' if q['full_quartet_success'] else 'added' if za[qkey(q)]['full_quartet_success'] else 'neither' for q in qq))}
 assert summary==j(ROOT/'reference/s01/summary.json');save(out/'s01/summary.json',summary)
 joints=[]
 for e in records('S02'):
  r=e['item'];x=e['extraction'];q=Q[r['family'],r['quartet_id']];jt,ct=r['joint_direction'].split('_',1)
  extraction_replay.joint(e,q)
  v=s.evaluate_candidate({'slot':r|{'task':ct,'gold_must':q['gold_must'],'gold_may':q['gold_may']},'quartet':q},{'answer':True,'construction':x['construction']})
  membership(r,q,{'construction':x['construction']},v)
  jc=x['judgment'] is not None and x['judgment']==q['gold_'+jt];cc=bool(v['strict_success'])
  assert jc==r['joint_judgment_correct'] and cc==r['joint_construction_valid'] and (jc and cc)==r['joint_task_success']
  k=tuple(r[f] for f in ['model','family','language','quartet_id']);i=mm[k+(jt,)]['task_success'] and mm[k+(ct,)]['task_success'];assert i==r['independent_pair_success']
  assert mm[k+(ct,)]['task_success']==r['independent_construction_success'];joints.append(r)
 assert len(joints)==768 and sum(r['joint_task_success'] for r in joints)==206
 save(out/'s02/paired_item_results.json',joints)
 repair=replay('S05',Q)
 annotations={(r['anchor_id'],r['arm']):r for r in j(ROOT/'inputs/repair_annotations.json')}
 for r in repair:r.update(annotations[r['anchor_id'],r['arm']],construction_valid=r['task_success'])
 stages=[]
 for kind in ['invalid_complete_construction','false_nonexistence']:
  for arm in sorted({r['arm'] for r in repair if r['original_failure_status']==kind}):
   sub=[r for r in repair if r['original_failure_status']==kind and r['arm']==arm]
   stages.append(dict(original_failure_status=kind,arm=arm,n=len(sub),**{k+'_n':sum(r[k] for r in sub) for k in ['task_success','construction_submitted','construction_valid','truncated','semantic_recoverable','explicit_refusal']}))
 groups=defaultdict(dict)
 for r in repair:groups[r['anchor_id']][r['arm']]=r
 comparisons=[('invalid_reject_minus_blind','reject_only','blind','invalid_complete_construction'),('invalid_diagnostic_minus_blind','diagnostic','blind','invalid_complete_construction'),('invalid_diagnostic_minus_reject','diagnostic','reject_only','invalid_complete_construction'),('false_none_existence_minus_blind_all','existence_certified','blind','false_nonexistence')];pairs=[]
 for name,aa,bb,kind in comparisons:
  cells=Counter((g[aa]['task_success'],g[bb]['task_success']) for g in groups.values() if next(iter(g.values()))['original_failure_status']==kind);n=sum(cells.values());sa=cells[True,True]+cells[True,False];sb=cells[True,True]+cells[False,True]
  pairs.append(dict(comparison=name,arm_a=aa,arm_b=bb,n_pairs=n,arm_a_success_n=sa,arm_b_success_n=sb,a_only_n=cells[True,False],b_only_n=cells[False,True],both_success_n=cells[True,True],both_failure_n=cells[False,False],paired_success_difference_n=sa-sb,paired_rate_difference_pp=100*(sa-sb)/n))
 rr={'stages':stages,'pairs':pairs};assert rr==j(ROOT/'reference/remaining/repair.json')
 save(out/'s05/repair.json',rr);write(out/'s05/item_results.csv',repair)
 candidates=[];questions={r['item_id']:r for r in j(ROOT/'candidate/questions.json')}
 for e in records('candidate'):
  extraction_replay.candidate(e)
  r=e['item'];x=e['extraction'];q=Q[r['family'],r['quartet_id']];isA=r['condition_code']=='A'
  assert bool(x['answer'] is not None and x['answer']==(r['gold_answer']=='yes'))==r['answer_correct'],(r['model'],r['request_id'])
  if not isA:
   assignment=questions[r['item_id']]['internal_assignments'][r['condition_code']]
   valid,holds=evidence_support.check(r['family'],q,assignment,profiles)
   assert valid==r['candidate_valid'] and holds==r['candidate_proposition_holds']
   assert (x['candidate_valid']==valid if x['candidate_valid'] is not None else None)==r['candidate_valid_correct']
   assert (x['proposition_holds']==holds if x['proposition_holds'] is not None else None)==r['proposition_correct']
  candidates.append(dict(r,available=x['answer'] is not None,output_tokens=e['output_tokens']))
 core=[r for r in candidates if r['role']=='core'];control=[r for r in candidates if r['role']!='core'];cc=[r for r in core if r['condition_code']=='C' and not r['answer_correct']]
 cres={'n':len(candidates),'correct':sum(r['answer_correct'] for r in candidates),'core':{c:sum(r['answer_correct'] for r in core if r['condition_code']==c) for c in 'ABCD'},'C_wrong':len(cc),'C_wrong_with_both_checks':sum(r['candidate_valid_correct'] is True and r['proposition_correct'] is True for r in cc),'tokens':sum(r['output_tokens'] for r in candidates)}
 transitions=Counter();byitem=defaultdict(Counter)
 for m in b.MODELS:
  for item in sorted({r['item_id'] for r in core}):
   t={r['condition_code']:r for r in core if r['model']==m and r['item_id']==item};a,c=t['A'],t['C']
   label='missing_A' if not a['available'] else 'correct_to_wrong' if a['answer_correct'] and not c['answer_correct'] else 'wrong_to_correct' if not a['answer_correct'] and c['answer_correct'] else 'both_correct' if a['answer_correct'] else 'both_wrong';transitions[label]+=1;byitem[item][label]+=1
 cres.update(A_C=dict(transitions),A_C_by_item=byitem)
 assert cres['core']==dict(A=21,B=46,C=14,D=37) and cres['C_wrong_with_both_checks']==31 and cres['correct']==158
 assert cres['tokens']==j(ROOT/'reference/candidate/table_summary.json')['tokens']
 save(out/'candidate/summary.json',cres);write(out/'candidate/item_results.csv',candidates)
 evidence=j(ROOT/'candidate/explicit_constructions.json')
 for e in evidence:
  q=questions[e['request_id'].split('_')[0]];valid,holds=evidence_support.check(q['family'],Q[q['family'],q['quartet_id']],e['assignment'],profiles)
  assert valid==e['valid'] and holds==e['proposition_holds']
 save(out/'candidate/explicit_constructions.json',evidence)
 print('S-01, S-02, S-05 and candidate scores verified.',flush=True)
 if not args.skip_bootstrap:
  ci,method=b.build_bootstrap(rows,qr,directions);write(out/'main/model_bootstrap_intervals.csv',ci);save(out/'main/bootstrap_method.json',method)
  expected=list(csv.DictReader((ROOT/'reference/main/model_bootstrap_intervals.csv').open(encoding='utf8')))
  assert len(ci)==len(expected)
  for aa,zz in zip(ci,expected):
   for k,v in aa.items():assert str(v)==zz[k] or isinstance(v,(int,float)) and abs(v-float(zz[k]))<1e-9,(k,v,zz[k])
  strata={(r['family'],r['csp_id']):r['stratum'] for r in rows};layers=[sorted(c for c,v in strata.items() if c[0]==f and v==st) for f in b.FAMILIES for st in b.STRATA]
  rng=random.Random(27017);samples=[[],[]]
  for _ in range(10000):
   weights=Counter(rng.choice(layer) for layer in layers for _ in range(4));tot=[sum(w*contrib[c][i] for c,w in weights.items()) for i in range(4)]
   for i in range(2):
    if tot[2*i+1]:samples[i].append(tot[2*i]/tot[2*i+1])
  result=j(ROOT/'reference/main/conditional_intervals.json')
  for i,r in enumerate(result['metrics']):assert abs(b.percentile(samples[i],.025)-r['low'])<1e-12 and abs(b.percentile(samples[i],.975)-r['high'])<1e-12
  save(out/'main/conditional_intervals.json',result)
  for name,v in s02_intervals.build(joints).items():
   save(out/'s02'/name,v)
   if name in ['intervals.json','summary.json','leave_one_csp_out.json']:assert equivalent(v,j(ROOT/'reference/s02'/name)),name
  subprocess.run([sys.executable,'-B',str(ROOT/'derive_results.py'),str(out)],check=True)
 subprocess.run([sys.executable,'-B',str(ROOT/'additional_checks.py'),str(out/'additional_checks')],check=True)
 save(out/'verification.json',{'success':True,'MAIN':4608,'S01':768,'S02':768,'S05':len(repair),'candidate':240,'main_successes':2399,'full_quartets':157,'bootstrap_replayed':not args.skip_bootstrap,'adopted_responses_only':True})
 print('All requested offline checks passed.',flush=True)
if __name__=='__main__':main()
