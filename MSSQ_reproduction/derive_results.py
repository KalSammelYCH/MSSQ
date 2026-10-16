"""沿用论文定义补齐附录及图表所需派生数值。
输入：已核验MAIN、S01/S02、候选与S05；输出本目录remaining。
按允许模态集合重建局部/子集/两种规则，按原六层整CSP重复抽样复算
既有三项差异与两项行为比较；不新增实验或选择指标，不修改源响应。
"""
from pathlib import Path
from collections import Counter,defaultdict
from itertools import combinations
import csv,json,sys,random
import numpy as np
from scipy.stats import spearmanr,kendalltau
ROOT=Path(__file__).resolve().parent;A=Path(sys.argv[1]);OUT=A/'remaining';OUT.mkdir(exist_ok=True)
import statistics_main as b
J=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def save(name,v):(OUT/name).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def write(name,rows):
    with (OUT/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)
def typed(p):
    rows=list(csv.DictReader(p.open(encoding='utf-8-sig')))
    for r in rows:
        for k in b.BOOL_FIELDS:
            if k in r:r[k]=b.parse_bool(r[k])
    return rows
rows=typed(A/'main/item_results.csv')
for r in rows:
    if not r['final_state']:
        r['final_state']='strict_success' if r['task_success'] else 'explicit_judgment_error' if r['task'] in ['must','may'] else 'erroneous_nonexistence_claim' if r['recognizable_answer'] is False else 'public_constraint_violation'
    assert r['final_state']
write('item_results.csv',rows)
TASKS=b.TASKS;MODES={'N','C','I'};POS={'must':{'N'},'may':{'N','C'},'witness':{'N','C'},'counterexample':{'I','C'}}
def allowed(r,rule):
    claim=b.predicted_claim(r)
    if claim is None or (rule=='verification_gated' and r['task'] in TASKS[2:] and claim and r['construction_valid'] is not True):return None
    return POS[r['task']] if claim else MODES-POS[r['task']]
def status(sets):
    return 'incompatible' if not set.intersection(MODES,*[s for s in sets if s is not None]) else 'indeterminate' if any(s is None for s in sets) else 'compatible'
def quartets(rs):
    grouped=defaultdict(dict)
    for r in rs:grouped[tuple(r[k] for k in ['model','family','language','csp_id','quartet_id'])][r['task']]=r
    result=[]
    for key,t in grouped.items():
        d=dict(zip(['model','family','language','csp_id','quartet_id'],key));d.update(stratum=t['must']['stratum'],gold_modality=t['must']['modality'],judgment_recovered=all(t[k]['task_success'] for k in TASKS[:2]),full_quartet_success=all(r['task_success'] for r in t.values()))
        for k,r in t.items():d[k+'_claim']=b.predicted_claim(r);d[k+'_valid']=r['construction_valid'] is True;d[k+'_task_success']=r['task_success'] is True
        d['contingent_two_sided']=d['witness_valid'] and d['counterexample_valid']
        for rule in ['verification_gated','existence_claim']:
            sets={k:allowed(t[k],rule) for k in TASKS};d[rule]=status(list(sets.values()))
            d[rule+'_both_local']=all(status([sets[k] for k in pair])=='compatible' for pair in [('may','witness'),('must','counterexample')])
            if rule=='verification_gated':
                for n in [2,3]:
                    for subset in combinations(TASKS,n):
                        name='_'.join(subset);d[name+'_status']=status([sets[k] for k in subset]);d[name+'_success']=all(t[k]['task_success'] for k in subset)
        d['compatibility_status']=d['verification_gated'];result.append(d)
    return result
qs=quartets(rows);save('quartets.json',qs);write('quartet_relations.csv',qs)
groups=[('model',m) for m in b.MODELS]+[('overall','ALL')]
cross=[];twosided=[];rules=[];local=[]
for scope,m in groups:
    sub=[q for q in qs if scope=='overall' or q['model']==m];cont=[q for q in sub if q['gold_modality']=='contingent']
    for jc in [True,False]:
        for st in ['compatible','incompatible','indeterminate']:cross.append(dict(scope=scope,model=m,judgment_recovered=str(jc),compatibility=st,n=sum(q['judgment_recovered']==jc and q['compatibility_status']==st for q in sub)))
    both=sum(q['contingent_two_sided'] for q in cont);full=sum(q['full_quartet_success'] for q in cont);wv=sum(q['witness_valid'] for q in cont);cv=sum(q['counterexample_valid'] for q in cont)
    twosided.append(dict(scope=scope,model=m,contingent_quartet_n=len(cont),two_sided_n=both,full_quartet_n=full,two_sided_without_correct_judgment_n=both-full,valid_witness_n=wv,valid_counterexample_n=cv,witness_only_n=wv-both,counterexample_only_n=cv-both,neither_n=len(cont)-wv-cv+both))
    for rule in ['verification_gated','existence_claim']:rules.append(dict(scope=scope,model=m,rule=rule,**{st+'_n':sum(q[rule]==st for q in sub) for st in ['compatible','incompatible','indeterminate']}))
    sublocal=[q for q in sub if q['verification_gated_both_local']];local.append(dict(model=m,n=len(sublocal),compatible=sum(q['compatibility_status']=='compatible' for q in sublocal),conflict=sum(q['compatibility_status']=='incompatible' for q in sublocal)))
write('cross.csv',cross);write('two_sided.csv',twosided);write('rule_sensitivity.csv',rules);save('local.json',local)
subset=[]
for n in [2,3]:
    for tasks in combinations(TASKS,n):
        name='_'.join(tasks);success=sum(q[name+'_success'] for q in qs);subset.append(dict(tasks=list(tasks),success=success,hidden=success-sum(q['full_quartet_success'] for q in qs),missed=sum(q['compatibility_status']=='incompatible' and q[name+'_status']!='incompatible' for q in qs)))
save('subsets.json',subset)
missed=[q for q in qs if q['compatibility_status']=='incompatible' and q['must_may_status']!='incompatible']
details={'missed':len(missed),'missed_judgment_status':dict(Counter(q['must_may_status'] for q in missed)),'missed_sources':dict(Counter('both_none' if q['witness_claim'] is False and q['counterexample_claim'] is False else 'verified' if q['witness_valid'] or q['counterexample_valid'] else 'one_none_unknown' for q in missed)),'rule_transitions':dict(Counter(q['verification_gated']+' -> '+q['existence_claim'] for q in qs)),'claim_wrong_compatible':sum(not q['judgment_recovered'] and q['existence_claim']=='compatible' for q in qs),'local_claim_n':sum(q['existence_claim_both_local'] for q in qs)}
for name,selection in [('ALL',qs),('official',[q for q in qs if q['model'] in ['DeepSeek-V4-Pro','GLM-5.2','Kimi-K2.6','Qwen3.8-Max']]),('no_gemini',[q for q in qs if q['model']!='Gemini 3.8 Flash'])]:
    modal=[q for q in selection if q['judgment_recovered']];both=[q for q in selection if q['contingent_two_sided']];missing=[q for q in both if q['must_claim'] is None or q['may_claim'] is None];details[name]=dict(modal=len(modal),failure=sum(not q['full_quartet_success'] for q in modal),both=len(both),wrong=sum(not q['judgment_recovered'] for q in both)-len(missing),unavailable=len(missing))
wrongmust=[q for q in qs if q['gold_modality']=='contingent' and q['witness_valid'] and q['must_claim'] is True];details['valid_wit_wrong_must']=dict(n=len(wrongmust),csps=len({(q['family'],q['csp_id']) for q in wrongmust}),models=len({q['model'] for q in wrongmust}))
# 同题重复的类别与两项现象；使用同一主实验行连接，不沿用旧字段。
repeat=J(A/'s01/item_results.json');key=lambda r:tuple(r[k] for k in ['model','family','language','quartet_id','task']);index={key(r):r for r in rows};first=[index[key(r)] for r in repeat];qa=quartets(first);qz=quartets(repeat);qkey=lambda q:tuple(q[k] for k in ['model','family','language','quartet_id']);z={qkey(q):q for q in qz}
def mclass(q):return (q['must_claim'],q['may_claim']) if q['must_claim'] is not None and q['may_claim'] is not None else 'unavailable'
repeat_summary=J(A/'s01/summary.json')
for m,summary in repeat_summary.items():summary['modal_stable']=sum(mclass(q)==mclass(z[qkey(q)]) for q in qa if m=='ALL pooled' or q['model']==m)
for name,part in [('main',qa),('repeat',qz)]:
    modal=[q for q in part if q['judgment_recovered']];both=[q for q in part if q['contingent_two_sided']];missing=sum(q['must_claim'] is None or q['may_claim'] is None for q in both)
    repeat_summary[name+'_conditional']=dict(modal=len(modal),failure=sum(not q['full_quartet_success'] for q in modal),both=len(both),wrong=sum(not q['judgment_recovered'] for q in both)-missing,missing=missing)
repeat_summary['recurrence']={'judgment_correct_construction_fail':sum(q['judgment_recovered'] and not q['full_quartet_success'] and z[qkey(q)]['judgment_recovered'] and not z[qkey(q)]['full_quartet_success'] for q in qa),'both_valid_wrong':sum(q['contingent_two_sided'] and not q['judgment_recovered'] and q['must_claim'] is not None and q['may_claim'] is not None and z[qkey(q)]['contingent_two_sided'] and not z[qkey(q)]['judgment_recovered'] and z[qkey(q)]['must_claim'] is not None and z[qkey(q)]['may_claim'] is not None for q in qa)}
av=[repeat_summary[m]['main_correct'] for m in b.MODELS];bv=[repeat_summary[m]['repeat_correct'] for m in b.MODELS];repeat_summary['rank']={'spearman':float(spearmanr(av,bv).statistic),'kendall':float(kendalltau(av,bv).statistic),'mean_absolute_pp':float(np.abs(np.array(av)-bv).mean()/96*100)};save('repeat_summary.json',repeat_summary)
# 六层共同抽样；用于原有三项总体差异和两项行为差异。
clusters=sorted({(r['family'],r['csp_id']) for r in rows});ci={c:i for i,c in enumerate(clusters)};strata={(r['family'],r['csp_id']):r['stratum'] for r in rows}
layers=[sorted(c for c in clusters if c[0]==f and strata[c]==st) for f in b.FAMILIES for st in b.STRATA];rng=random.Random(27017);weights=np.zeros((10000,24),int)
for i in range(10000):
    for layer in layers:
        for _ in range(4):weights[i,ci[rng.choice(layer)]]+=1
def cluster_counts(predicate,num=lambda r:r['task_success'] is True):
    arr=np.zeros((24,2))
    for r in rows:
        if predicate(r):arr[ci[r['family'],r['csp_id']]] += [num(r),1]
    return arr
def rates(arr):
    v=weights@arr;return v[:,0]/v[:,1]
effects=[]
for label,p1,p2 in [('Judgment -- construction',lambda r:r['task'] in TASKS[:2],lambda r:r['task'] in TASKS[2:]),('Necessary -- contingent',lambda r:r['modality']=='necessary',lambda r:r['modality']=='contingent'),('Impossible -- contingent',lambda r:r['modality']=='impossible',lambda r:r['modality']=='contingent')]:
    x,y=cluster_counts(p1),cluster_counts(p2);vals=100*(rates(x)-rates(y));loco=[]
    for c in clusters:
        parts=[]
        for arr in [x,y]:parts.append(np.mean([sum(arr[ci[k],0] for k in clusters if k!=c and k[0]==f)/sum(arr[ci[k],1] for k in clusters if k!=c and k[0]==f) for f in b.FAMILIES]))
        loco.append(100*(parts[0]-parts[1]))
    effects.append(dict(label=label,point_difference_pp=100*(x[:,0].sum()/x[:,1].sum()-y[:,0].sum()/y[:,1].sum()),sensitivity_low_pp=float(np.quantile(vals,.025)),sensitivity_high_pp=float(np.quantile(vals,.975)),loo_min_pp=min(loco),loo_max_pp=max(loco)))
write('core_effect_robustness.csv',effects)
taskrates=np.array([rates(cluster_counts(lambda r,t=t:r['task']==t)) for t in ['may','must','witness','counterexample']]);details['task_order_bootstrap']=float(np.all(taskrates[:-1]>taskrates[1:],axis=0).mean())
loo=[]
for m in b.MODELS:
    for c in clusters:
        score=np.mean([np.mean([r['task_success'] is True for r in rows if r['model']==m and r['family']==f and (r['family'],r['csp_id'])!=c]) for f in b.FAMILIES]);loo.append(dict(model=m,omitted_csp=c[1],leave_one_out_estimate=float(score)))
write('leave_one_csp_model.csv',loo)
behavior={};states=sorted({r['final_state'] for r in rows})
for m in b.MODELS:
    rr=[r for r in rows if r['model']==m];formed=[r for r in rr if r['semantic_recoverable']];req=[r for r in rr if r['construction_required']];complete=[r for r in req if r['semantic_recoverable'] and r['recognizable_answer'] and r['construction_complete']];valid=[r for r in complete if r['construction_valid']]
    pairs={'answer_formed':(len(formed),576),'success_given_answer':(sum(r['task_success'] is True for r in formed),len(formed)),'complete_construction_submission':(len(complete),192),'valid_given_complete_construction':(len(valid),len(complete))}
    behavior[m]={k:dict(n=n,denominator=d,rate=n/d) for k,(n,d) in pairs.items()};behavior[m]['states']={s:sum(r['final_state']==s for r in rr) for s in states};behavior[m]['false_none_required']=sum(r['final_state']=='erroneous_nonexistence_claim' for r in req)
# 行为比较按论文独立规定仅按家族分层；不能沿用上面的六层权重。
weights=np.zeros((10000,24),int);rng=random.Random(27017)
for i in range(10000):
    for family in b.FAMILIES:
        pool=sorted(c for c in clusters if c[0]==family)
        for _ in range(8):weights[i,ci[rng.choice(pool)]]+=1
details['behavior_bootstrap']={'seed':27017,'replicates':10000,'strata':'family','draws_per_family':8,'rng':'Python random.Random'}
details['behavior_intervals']={}
for name,ma,mb,den,num in [('GPT_GLM_validity','GPT-5.6 Sol','GLM-5.2',lambda r:r['construction_required'] and r['semantic_recoverable'] and r['recognizable_answer'] and r['construction_complete'],lambda r:r['construction_valid'] is True),('Qwen_DS_submission','Qwen3.8-Max','DeepSeek-V4-Pro',lambda r:r['construction_required'],lambda r:r['semantic_recoverable'] and r['recognizable_answer'] and r['construction_complete'])]:
    x=cluster_counts(lambda r:r['model']==ma and den(r),num);y=cluster_counts(lambda r:r['model']==mb and den(r),num);v=100*(rates(x)-rates(y));details['behavior_intervals'][name]=dict(point=100*(x[:,0].sum()/x[:,1].sum()-y[:,0].sum()/y[:,1].sum()),low=float(np.quantile(v,.025)),high=float(np.quantile(v,.975)))
save('behavior.json',behavior)
save('details.json',details)
print(json.dumps(details,ensure_ascii=False))

for name in ["behavior.json","details.json","local.json","repeat_summary.json","subsets.json"]:
    expected=J(ROOT/"reference/remaining"/name)
    if name=="details.json":expected["behavior_bootstrap"].pop("note",None)
    assert J(OUT/name)==expected,name
