"""将已封存的题面语义表达式与最终包形式记录逐项比较。

输入：text_interpretations.jsonl及parser_seal.json、包内形式约束文件。
输出：alignment_rows.jsonl、alignment_summary.json、formal_inputs.json。
流程：先校验题面解析程序和结果未变，再单独读取正式约束字段（不使用其文字字段）；
独立将正式字段转换为中立表达式，核对全部编号约束、定义域、组、命题及任务方向。
同一条约束在12份提示中重复出现，汇总同时列出逐提示覆盖与去重覆盖，避免虚增。
报告范围为编号约束、定义域、组、命题及任务方向。
不导入原生成器/渲染器/验证器，不调用API，不改变源数据、旧结果或稿件。
"""
from pathlib import Path
import json,zipfile,hashlib,collections
from parse_prompts import var,slot,day,period,cmp,distance,count,bounds,groupcount
HERE=Path(__file__).resolve().parent
class PackageFiles:
    def read(self,name):
        return (HERE.parent / name.removeprefix('MSSQ_reproduction/')).read_bytes()


def scheduling_rule(r):
    p=r['params'];k=r['template_type']
    if k=='count_order':
        st=p['subtype']
        pred=[['between',slot(x),*sorted([slot(p['pivot_x']),slot(p['pivot_y'])])] if st=='between' else cmp({'earlier':'lt','later':'gt','not_earlier':'ge','not_later':'le'}[st],slot(x),slot(p['pivot_x'])) for x in p['set']]
        return cmp('eq',count(pred),p['k_value'])
    if k=='count_day_tod':
        pred=[cmp('eq',day(x),p['day']) if 'day' in p else cmp('eq',period(x),p['period_idx']) for x in p['set']]
        return cmp('eq',count(pred),p['k_value'])
    if k=='simple_relation':
        a,b=slot(p['person_x']),slot(p['person_y'])
        return cmp('lt',a,b) if p['subtype']=='before' else cmp('ge',distance(a,b),2)
    if k=='conditional':
        ct=p['cond_type'];st=p['cons_cons_type']
        a=cmp('eq',day(p['person']),p['day']) if ct=='on_day' else cmp('eq',period(p['person']),p['period_idx']) if ct=='on_period' else cmp('lt',slot(p['person_x']),slot(p['person_y']))
        if st=='same_period_count':b=cmp('eq',count([cmp('eq',period(x),p['cons_period_idx']) for x in p['cons_set']]),p['cons_k_value'])
        elif st=='not_same_day':b=cmp('ne',day(p['cons_person_y']),day(p['cons_person_z']))
        elif st=='not_adjacent':b=cmp('ge',distance(slot(p['cons_person_y']),slot(p['cons_person_z'])),2)
        else:raise ValueError(st)
        return ['implies',a,b]
    raise ValueError(k)

def frequency_rule(p):
    k=p['kind']
    if k=='conflict_neq':return cmp('ne',var(p['node_a']),var(p['node_b']))
    if k=='group_band_count':return bounds(groupcount(p['nodes'],p['frequencies']),p['minimum'],p['maximum'])
    if k=='conditional_group_band_count':return ['implies',bounds(groupcount(p['trigger_nodes'],p['trigger_frequencies']),p['trigger_minimum'],p['trigger_maximum']),bounds(groupcount(p['target_nodes'],p['target_frequencies']),p['target_minimum'],p['target_maximum'])]
    if k=='forbidden_frequency_pair':return ['not',['and',cmp('eq',var(p['node_a']),p['frequency_a']),cmp('eq',var(p['node_b']),p['frequency_b'])]]
    if k=='pair_channel_distance':return bounds(distance(['number',p['node_a']],['number',p['node_b']]),p['minimum'],p['maximum'])
    if k=='conditional_allowed_frequencies':return ['implies',cmp('eq',var(p['trigger_node']),p['trigger_frequency']),['in',var(p['target_node']),sorted(p['target_frequencies'])]]
    raise ValueError(k)

def matching_rule(p,c):
    def atom(x):return cmp('eq',var(x['entity']),x['value'])
    def terms(ts,offset):return ['sum',sorted([groupcount(c['entity_groups'][t['entity_group']],c['value_groups'][t['value_group']]) for t in ts],key=lambda x:json.dumps(x)),offset]
    if p['kind']=='equivalence':return cmp('eq',atom(p['left']),atom(p['right']))
    if p['kind']=='aggregate_balance':return cmp('eq',terms(p['left_terms'],0),terms(p['right_terms'],p['offset']))
    raise ValueError(p['kind'])

def proposition(f,p,c):
    if f=='scheduling':
        k=p['type']
        if k=='person_in_slot':return cmp('eq',slot(p['person']),p['slot']+1)
        if k=='person_in_day':return cmp('eq',day(p['person']),p['day'])
        if k=='person_in_period':return cmp('eq',period(p['person']),p['period_idx'])
        a,b=p['person_x'],p['person_y']
        if k in ('same_day','same_session','same_period'):
            fun={'same_day':day,'same_session':slot,'same_period':period}[k];return cmp('eq',fun(a),fun(b))
        if k=='before':return cmp('lt',slot(a),slot(b))
        if k=='adjacent':return cmp('eq',distance(slot(a),slot(b)),1)
        if k=='not_adjacent':return cmp('ge',distance(slot(a),slot(b)),2)
        if k=='minimum_gap':return cmp('ge',distance(slot(a),slot(b)),p['gap']+1)
    else:
        k=p['kind'];a=p['args']
        if k=='node_uses_frequency':return cmp('eq',var(a['node']),a['frequency'])
        if k in ('nodes_same_frequency','nodes_different_frequency'):return cmp('eq' if k=='nodes_same_frequency' else 'ne',var(a['node_a']),var(a['node_b']))
        if k=='entity_uses_value':return cmp('eq',var(a['entity']),a['value'])
        if k=='group_count_bound':return cmp('le' if a['operator']=='at_most' else 'ge',groupcount(c['entity_groups'][a['entity_group']],c['value_groups'][a['value_group']]),a['threshold'])
    raise ValueError(p)

def main():
    seal=json.loads((HERE/'parser_seal.json').read_text())
    for n,h in seal.items():assert hashlib.sha256((HERE/n).read_bytes()).hexdigest()==h,n
    rows=[json.loads(l) for l in (HERE/'text_interpretations.jsonl').read_text(encoding='utf-8').splitlines()]
    z=PackageFiles();cs={};qs={};source_hashes={}
    profiles=json.loads(z.read('MSSQ_reproduction/configs/profiles.json'))['profiles']
    for f in ['scheduling','frequency_assignment','bijective_matching']:
        for name,dest,idkey in [('csps',cs,'csp_id'),('quartets',qs,'quartet_id')]:
            n=f'MSSQ_reproduction/formal/{f}/{name}.jsonl';data=z.read(n);source_hashes[n]=hashlib.sha256(data).hexdigest()
            for x in map(json.loads,data.decode('utf-8-sig').splitlines()):dest[f,x[idkey]]=x
    checks=[];notes=[];types=collections.Counter();unique={};props={}
    for r in rows:
        f=r['family'];rec=cs[f,r['csp_id']];q=qs[f,r['quartet_id']];c=rec.get('csp',rec.get('family_payload',rec))
        if f=='scheduling':rules={x['constraint_id']:scheduling_rule(x) for x in rec['constraints']};domains={};groups={}
        elif f=='frequency_assignment':
            raw=[{'kind':'conflict_neq','node_a':a,'node_b':b} for a,b in c['conflict_edges']]+c['heterogeneous_constraints']
            rules={f'C{i+1}':frequency_rule(x) for i,x in enumerate(raw)};domains={k:sorted(v) for k,v in c['allowed_frequencies'].items()};groups={}
        else:rules={x['id']:matching_rule(x,c) for x in c['clues']};domains={k:sorted(v) for k,v in c['allowed_values'].items()};groups=c['entity_groups']|c['value_groups']
        actual={x['id']:x['expression'] for x in r['constraints']}
        if f=='scheduling':
            p=profiles[rec['profile']];b=r['scenario'];base_ok=(b['people']==[chr(65+i) for i in range(p['people_count'])] and b['days']==p['days'] and len(b['periods'])==len(p['periods']) and b['sessions']==p['days']*len(p['periods']) and b['capacity']==p['slot_capacity']['value'])
        elif f=='frequency_assignment':base_ok=(r['scenario']['values']==c['frequencies'] and sorted(domains)==sorted(c['nodes']))
        else:base_ok=(r['scenario']['entities']==c['entities'] and r['scenario']['values']==c['values'])
        ok=actual==rules and domains==r['domains'] and groups==r['groups'] and proposition(f,q['proposition'],c)==r['proposition'] and base_ok
        mismatches=[{'id':k,'text_expression':actual.get(k),'formal_expression':rules.get(k)} for k in actual.keys()|rules.keys() if actual.get(k)!=rules.get(k)]
        checks.append({'family':f,'language':r['language'],'prompt_id':r['prompt_id'],'csp_id':r['csp_id'],'quartet_id':r['quartet_id'],'constraints_match':actual==rules,'domains_match':domains==r['domains'],'groups_match':groups==r['groups'],'proposition_match':proposition(f,q['proposition'],c)==r['proposition'],'task_match':r['task']==r['task_interpretation'],'scenario_parameters_match':base_ok,'matched':ok,'mismatches':mismatches})
        for x in r['constraints']:unique[f,r['csp_id'],r['language'],x['id']]=x
        props[f,r['quartet_id'],r['language']]=r['proposition']
    counts=collections.Counter(f for f,c,l,i in unique)
    summary={'prompts_checked':len(rows),'constraints_domains_groups_propositions_matched':sum(x['matched'] for x in checks),'task_directions_matched':sum(x['task_match'] for x in checks),'csp_language_pairs':len({(r['family'],r['csp_id'],r['language']) for r in rows}),'distinct_numbered_constraints_per_language':{f:n//2 for f,n in counts.items()},'constraint_instances_both_languages':len(unique),'proposition_instances_both_languages':len(props)}
    (HERE/'alignment_rows.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in checks),encoding='utf-8')
    (HERE/'alignment_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    (HERE/'formal_inputs.json').write_text(json.dumps(source_hashes,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2));print('first_mismatches',json.dumps([x for x in checks if not x['matched']][:2],ensure_ascii=False))

if __name__=='__main__':main()
