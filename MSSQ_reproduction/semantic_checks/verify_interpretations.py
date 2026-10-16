"""验证题面解析中的关键逻辑边界，并回放已保存合法解及候选。

输入：封存题面解析结果、最终包的完整解集、候选题表。
输出：interpretation_validation.json，含边界反例检查、合法解回放和候选身份记录。
流程：用通用表达式解释器检查条件单向性、恰好/上下界、端点排除、相邻与等价；
再将已保存解代入从题面读取的表达式，核验命题支持数。此项不重新枚举解空间，
不以有限代入替代前一阶段的表达式比较，也不调用模型。原始数据全部只读。
"""
from pathlib import Path
import json,zipfile,hashlib
from parse_prompts import sched,freq,matching
HERE=Path(__file__).resolve().parent
class PackageFiles:
    def read(self,name):
        return (HERE.parent / name.removeprefix('MSSQ_reproduction/')).read_bytes()


def ev(e,a):
    if not isinstance(e,list):return e
    op=e[0]
    if op in ('var','slot'):return a[e[1]]
    if op=='number':return int(a[e[1]][1:])
    if op=='day':return (a[e[1]]-1)//3+1
    if op=='period':return (a[e[1]]-1)%3
    if op=='count':return sum(bool(ev(x,a)) for x in e[1])
    if op=='sum':return sum(ev(x,a) for x in e[1])+e[2]
    if op=='in':return ev(e[1],a) in e[2]
    if op=='range':return e[2]<=ev(e[1],a)<=e[3]
    if op=='between':return min(ev(e[2],a),ev(e[3],a))<ev(e[1],a)<max(ev(e[2],a),ev(e[3],a))
    if op=='absdiff':return abs(ev(e[1],a)-ev(e[2],a))
    if op=='implies':return not ev(e[1],a) or ev(e[2],a)
    if op=='and':return ev(e[1],a) and ev(e[2],a)
    if op=='not':return not ev(e[1],a)
    x,y=ev(e[1],a),ev(e[2],a)
    return {'eq':lambda:x==y,'ne':lambda:x!=y,'lt':lambda:x<y,'gt':lambda:x>y,'le':lambda:x<=y,'ge':lambda:x>=y}[op]()

def main():
    tests=[
        (sched('If A is scheduled before B, then C and D are not scheduled on the same day.'),{'A':3,'B':2,'C':1,'D':2},True),
        (sched('If A is scheduled before B, then C and D are not scheduled on the same day.'),{'A':1,'B':2,'C':1,'D':2},False),
        (sched('Exactly 1 of A are scheduled no earlier than B.'),{'A':2,'B':2},True),
        (sched('Exactly 1 of A are scheduled earlier than B.'),{'A':2,'B':2},False),
        (sched('Exactly 1 of A are scheduled strictly between B and C.'),{'A':2,'B':3,'C':1},True),
        (sched('Exactly 1 of A are scheduled strictly between B and C.'),{'A':1,'B':3,'C':1},False),
        (sched('A and B are scheduled in adjacent sessions'),{'A':3,'B':4},True),
        (sched('A and B are scheduled in adjacent sessions'),{'A':3,'B':3},False),
        (sched('There are at least 2 complete sessions strictly between the sessions assigned to A and B'),{'A':1,'B':3},False),
        (sched('There are at least 2 complete sessions strictly between the sessions assigned to A and B'),{'A':1,'B':4},True),
        (freq('Among D01, D02, the number of devices using a frequency in {F1} is exactly 1.'),{'D01':'F1','D02':'F1'},False),
        (freq('Among D01, D02, the number of devices using a frequency in {F1} is between 1 and 2, inclusive.'),{'D01':'F1','D02':'F1'},True),
        (freq('It is forbidden for D01 to use F1 while D02 uses F2.'),{'D01':'F1','D02':'F3'},True),
        (freq('It is forbidden for D01 to use F1 while D02 uses F2.'),{'D01':'F1','D02':'F2'},False),
        (matching('P01=V01 holds if and only if P02=V02 holds.',{}),{'P01':'V03','P02':'V04'},True),
        (matching('P01=V01 holds if and only if P02=V02 holds.',{}),{'P01':'V01','P02':'V04'},False),
        (matching('N(G1,H1) = N(G2,H1)-1.',{'G1':['P01'],'G2':['P02'],'H1':['V01']}),{'P01':'V02','P02':'V01'},True),
    ]
    assert all(ev(e,a)==expected for e,a,expected in tests)
    rows=[json.loads(l) for l in (HERE/'text_interpretations.jsonl').read_text(encoding='utf-8').splitlines()]
    z=PackageFiles(); cs={};qs={}
    for f in ['scheduling','frequency_assignment','bijective_matching']:
        for name,dest,key in [('csps',cs,'csp_id'),('quartets',qs,'quartet_id')]:
            for l in z.read(f'MSSQ_reproduction/formal/{f}/{name}.jsonl').decode('utf-8-sig').splitlines():
                x=json.loads(l);dest[f,x[key]]=x
    distinct={(r['family'],r['quartet_id'],r['language']):r for r in rows}; result=[]
    for (f,qid,lang),r in distinct.items():
        sols=cs[f,r['csp_id']]['solutions'];normalized=[{k:v+1 for k,v in s.items()} for s in sols] if f=='scheduling' else sols
        valid=all(all(ev(c['expression'],s) for c in r['constraints']) for s in normalized)
        support=sum(ev(r['proposition'],s) for s in normalized);expected=qs[f,qid]['support_count']
        assert valid and support==expected,(f,qid,lang,support,expected)
        result.append({'family':f,'quartet_id':qid,'language':lang,'solutions':len(sols),'all_saved_solutions_satisfy_text_constraints':valid,'text_support':support,'formal_support':expected})
    candidates=json.loads(z.read('MSSQ_reproduction/candidate/questions.json')); candidates_out=[]
    for q in candidates:
        if q['role']!='core':continue
        f=q['family'];r=distinct[f,q['quartet_id'],'en'];sols=cs[f,q['csp_id']]['solutions'];assignments=q['internal_assignments'];res={}
        for cond in ['B','C','D']:
            a=assignments[cond];normalized={k:v+1 for k,v in a.items()} if f=='scheduling' else a
            res[cond]={'in_saved_solution_set':a in sols,'proposition_holds':ev(r['proposition'],normalized)}
        assert res['B']['in_saved_solution_set'] and res['C']['in_saved_solution_set'] and not res['D']['in_saved_solution_set']
        assert res['B']['proposition_holds']==(q['task']=='may') and res['C']['proposition_holds']!=(q['task']=='may')
        assert res['D']['proposition_holds']==res['B']['proposition_holds']
        candidates_out.append({'item_id':q['item_id'],'csp_id':q['csp_id'],'task':q['task'],'candidates':res})
    output={'boundary_cases_passed':len(tests),'proposition_language_replays':result,'candidate_source_checks':candidates_out}
    (HERE/'interpretation_validation.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'boundary_cases_passed':len(tests),'proposition_language_replays_passed':len(result),'candidate_core_groups_checked':len(candidates_out)},indent=2))

if __name__=='__main__':main()
