"""复算论文新增检查。输入为包内采用回答、Gold与候选结果；输出至指定的新结果目录。
流程：重验赋值合法性及方向，再逐题剔除候选面板并对照参考结果；不修改输入、不调用模型。
"""
from pathlib import Path
from collections import Counter,defaultdict
import json,sys,hashlib
import reproduce as r
import scoring as s
ROOT=Path(__file__).resolve().parent
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
Q={(fam,q['quartet_id']):q for fam in r.b.FAMILIES for q in r.jl(ROOT/'formal'/fam/'quartets.jsonl')}
counts=Counter();by_model=defaultdict(Counter)
for e in r.records('MAIN'):
 row=e['item'];candidate=e['extraction']['candidate']
 if row['task'] not in ('witness','counterexample'):continue
 q=Q[row['family'],row['quartet_id']]
 v=s.evaluate_candidate({'slot':row|{'gold_must':q['gold_must'],'gold_may':q['gold_may']},'quartet':q},candidate)
 r.membership(row,q,candidate,v)
 cat='no_complete_assignment'
 if v['construction_complete']:
  cat='constraint_invalid' if not v['public_constraints_valid'] else 'legal_requested_direction' if v['target_direction_valid'] else 'legal_wrong_direction'
 counts[cat]+=1;by_model[row['model']][cat]+=1
assert counts==dict(no_complete_assignment=1664,constraint_invalid=214,legal_requested_direction=426)
r.save(out/'assignment_direction.json',dict(tasks=sum(counts.values()),counts=dict(counts),by_model=dict(by_model),legal_wrong_direction=counts['legal_wrong_direction']))
SOURCE=ROOT/'candidate/paired_results.json'
source_hash=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
rows=r.j(SOURCE);models=sorted({r['model'] for r in rows});items=[f'E{i:02}' for i in range(1,7)]
core=[r for r in rows if r['item_id'] in items]
index={(r['model'],r['item_id'],r['condition_code']):r for r in core}
assert len(core)==len(index)==192
reference=dict(core=dict(A=21,B=46,C=14,D=37),C_wrong=34,C_wrong_with_both_checks=31)
def summarize(kept):
    sub = [r for r in core if r['item_id'] in kept]
    counts = {c:sum(r['answer_correct'] is True for r in sub if r['condition_code']==c) for c in 'ABCD'}
    crows = [r for r in sub if r['condition_code']=='C']
    wrong = [r for r in crows if r['answer'] is not None and r['answer_correct'] is False]
    checked = [r for r in wrong if r['candidate_valid_correct'] is True and r['proposition_correct'] is True]
    transitions = Counter()
    for m in models:
        for i in kept:
            a,c = index[m,i,'A'],index[m,i,'C']
            if a['answer'] is None:
                transitions['missing_A_to_correct_C' if c['answer_correct'] else 'missing_A_to_wrong_C'] += 1
            else:
                transitions[{(True,True):'both_correct',(True,False):'correct_to_wrong',(False,True):'wrong_to_correct',(False,False):'both_wrong'}[a['answer_correct'],c['answer_correct']]] += 1
    return {'kept_items':kept,'positions_per_condition':8*len(kept),'correct_by_condition':counts,
            'C_wrong':len(wrong),'C_wrong_with_correct_checks':len(checked),
            'C_error_checked_fraction':len(checked)/len(wrong) if wrong else None,
            'C_checked_error_models':sorted({r['model'] for r in checked}),
            'C_checked_error_items':sorted({r['item_id'] for r in checked}),
            'A_C_transitions':dict(transitions),
            'C_correct_by_model':{m:sum(index[m,i,'C']['answer_correct'] is True for i in kept) for m in models},
            'condition_correct_by_model':{m:{c:sum(index[m,i,c]['answer_correct'] is True for i in kept) for c in 'ABCD'} for m in models}}
full = summarize(items)
assert full['correct_by_condition']==reference['core']
assert (full['C_wrong'],full['C_wrong_with_correct_checks'])==(reference['C_wrong'],reference['C_wrong_with_both_checks'])==(34,31)
assert full['A_C_transitions']['correct_to_wrong']==13 and full['A_C_transitions']['wrong_to_correct']==4
single = {i:summarize([j for j in items if j!=i]) for i in items}
by_item = {i:summarize([i]) for i in items}
without_02_03 = summarize([i for i in items if i not in ['E02','E03']])
results={'source_sha256':source_hash,'full':full,'by_item':by_item,'leave_one_out':single,'remove_E02_E03':without_02_03}
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==source_hash
assert results==r.j(ROOT/'reference/candidate/leave_one_out.json')
r.save(out/'candidate_leave_one_out.json',results)
print('Assignment-direction and candidate sensitivity checks passed.')
