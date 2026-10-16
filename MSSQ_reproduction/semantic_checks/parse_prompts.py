"""从最终公开题面读取语义，不调用生成器、渲染器、原评分器或形式记录。

输入：prompts_only.jsonl，含最终包的576份题面及身份、哈希。
输出：text_interpretations.jsonl，逐条保留原句、解析表达式、命题和任务方向；
      parse_summary.json，覆盖和未解析项；parser_seal.json，比较前解析结果哈希。
流程：按题面标题分段，分别读取中英文实际文字，将严格/非严格边界、条件方向、
计数对象、等价与合法候选请求转换为中立表达式。未知句式报错，不跳过或默认成功。
这是辅助程序语义复核，不是独立人工审核；作者已接触过旧项目，不能宣称盲审。
解析与后续形式记录适配程序分离；不修改原题、Gold、采用回答、论文或发送包。
"""
from pathlib import Path
import re,json,hashlib,collections

HERE=Path(__file__).resolve().parent
PERIOD={'morning':0,'afternoon':1,'evening':2,'上午':0,'下午':1,'晚上':2}
def var(x): return ['var',x]
def slot(x): return ['slot',x]
def day(x): return ['day',x]
def period(x): return ['period',x]
def cmp(op,a,b):
    if op in ('eq','ne') and json.dumps(a)>json.dumps(b): a,b=b,a
    return [op,a,b]
def distance(a,b): return ['absdiff',*sorted([a,b],key=lambda x:json.dumps(x))]
def count(predicates): return ['count',sorted(predicates,key=lambda x:json.dumps(x))]
def bounds(term,lo,hi): return ['range',term,int(lo),int(hi)]
def ids(s,pattern): return re.findall(pattern,s)
def groupcount(entities,values):
    return count([['in',var(x),sorted(values)] for x in sorted(entities)])
def match(p,s): return re.fullmatch(p,s,flags=re.I)

def sched(s):
    s=s.strip().rstrip('。.')
    m=match(r'If (.+), then (.+)',s) or match(r'如果 (.+)，那么 (.+)',s)
    if m:return ['implies',sched(m[1]),sched(m[2])]
    m=match(r'Exactly (\d+) of ([A-R, ]+) (?:are|is) scheduled (.+)',s)
    if m:
        k=int(m[1]); people=ids(m[2],r'[A-R]'); tail=m[3]
        z=match(r'on Day (\d+)',tail)
        if z:pred=[cmp('eq',day(x),int(z[1])) for x in people]
        else:
            z=match(r'in the (morning|afternoon|evening) period',tail)
            if z:pred=[cmp('eq',period(x),PERIOD[z[1]]) for x in people]
            else:
                z=match(r'(earlier than|later than|no earlier than|no later than) ([A-R])',tail)
                if z:pred=[cmp({'earlier than':'lt','later than':'gt','no earlier than':'ge','no later than':'le'}[z[1]],slot(x),slot(z[2])) for x in people]
                else:
                    z=match(r'strictly between ([A-R]) and ([A-R])',tail)
                    if not z:raise ValueError(s)
                    pred=[['between',slot(x),*sorted([slot(z[1]),slot(z[2])])] for x in people]
        return cmp('eq',count(pred),k)
    m=match(r'在 ([A-R、]+) 中，恰好 (\d+) 人(.+)',s)
    if m:
        people=ids(m[1],r'[A-R]');k=int(m[2]);tail=m[3]
        z=match(r'排在 ([A-R]) (之前|之后)',tail)
        if z:pred=[cmp('lt' if z[2]=='之前' else 'gt',slot(x),slot(z[1])) for x in people]
        else:
            z=match(r'(不早于|不晚于) ([A-R])',tail)
            if z:pred=[cmp('ge' if z[1]=='不早于' else 'le',slot(x),slot(z[2])) for x in people]
            else:
                z=match(r'排在 ([A-R]) 与 ([A-R]) 之间',tail)
                if not z:raise ValueError(s)
                pred=[['between',slot(x),*sorted([slot(z[1]),slot(z[2])])] for x in people]
        return cmp('eq',count(pred),k)
    m=match(r'([A-R、]+) 中恰好 (\d+) 人(被安排在第 (\d+) 天|排在(上午|下午|晚上)时段)',s)
    if m:
        pred=[cmp('eq',day(x),int(m[4])) if m[4] else cmp('eq',period(x),PERIOD[m[5]]) for x in ids(m[1],r'[A-R]')]
        return cmp('eq',count(pred),int(m[2]))
    m=match(r'([A-R]) is scheduled on Day (\d+)',s) or match(r'([A-R]) 在第 (\d+) 天',s)
    if m:return cmp('eq',day(m[1]),int(m[2]))
    m=match(r'([A-R]) is scheduled in Session (\d+)',s) or match(r'([A-R]) 在第 (\d+) 场',s)
    if m:return cmp('eq',slot(m[1]),int(m[2]))
    m=match(r'([A-R]) is scheduled in the (morning|afternoon|evening) period',s) or match(r'([A-R]) 在(上午|下午|晚上)时段',s)
    if m:return cmp('eq',period(m[1]),PERIOD[m[2]])
    m=match(r'([A-R]) is scheduled before ([A-R])',s) or match(r'([A-R]) 早于 ([A-R])',s)
    if m:return cmp('lt',slot(m[1]),slot(m[2]))
    m=match(r'([A-R]) and ([A-R]) are (.+)',s) or match(r'([A-R]) 与 ([A-R]) (.+)',s)
    if m:
        a,b,t=m.groups()
        if t in ('scheduled on the same day','同一天'):return cmp('eq',day(a),day(b))
        if t in ('not scheduled on the same day','不在同一天'):return cmp('ne',day(a),day(b))
        if t in ('scheduled in the same session','同场'):return cmp('eq',slot(a),slot(b))
        if t in ('scheduled in the same daily period type','在同一时段类型'):return cmp('eq',period(a),period(b))
        if t in ('scheduled in adjacent sessions','的场次相邻'):return cmp('eq',distance(slot(a),slot(b)),1)
        if t in ('scheduled neither in the same session nor in adjacent sessions','不同场且不在相邻场次','不同场且场次不相邻'):return cmp('ge',distance(slot(a),slot(b)),2)
    m=match(r'There are at least (\d+) complete sessions strictly between the sessions assigned to ([A-R]) and ([A-R])',s)
    if m:return cmp('ge',distance(slot(m[2]),slot(m[3])),int(m[1])+1)
    m=match(r'([A-R]) 与 ([A-R]) 的场次之间至少隔着 (\d+) 场',s)
    if m:return cmp('ge',distance(slot(m[1]),slot(m[2])),int(m[3])+1)
    raise ValueError(s)

def freq(s):
    s=s.strip().rstrip('。.')
    m=match(r'If, (among .+), then, (among .+)',s) or match(r'若(在 .+)，则(在 .+)',s)
    if m:return ['implies',freq(m[1]),freq(m[2])]
    m=match(r'Among (.+), the number of devices using a frequency in \{(.+)\} is (.+)',s)
    if m:
        g,v,b=m.groups();z=match(r'exactly (\d+)',b)
        if z:lo=hi=int(z[1])
        else:
            z=match(r'between (\d+) and (\d+), inclusive',b)
            if not z:raise ValueError(s)
            lo,hi=int(z[1]),int(z[2])
        return bounds(groupcount(ids(g,r'D\d+'),ids(v,r'F\d+')),lo,hi)
    m=match(r'在 (.+) 中，(恰有 (\d+)|有 (\d+) 至 (\d+)) 台设备使用 \{(.+)\} 中的频率',s)
    if m:return bounds(groupcount(ids(m[1],r'D\d+'),ids(m[6],r'F\d+')),m[3] or m[4],m[3] or m[5])
    m=match(r'(D\d+) and (D\d+) must use different frequencies',s) or match(r'(?:Devices )?(D\d+) and (D\d+) use different frequencies',s) or match(r'(?:设备 )?(D\d+) 与 (D\d+) (?:不得使用相同频率|使用不同频率)',s)
    if m:return cmp('ne',var(m[1]),var(m[2]))
    m=match(r'Devices (D\d+) and (D\d+) use the same frequency',s) or match(r'设备 (D\d+) 与 (D\d+) 使用相同频率',s)
    if m:return cmp('eq',var(m[1]),var(m[2]))
    m=match(r'Device (D\d+) uses frequency (F\d+)',s) or match(r'设备 (D\d+) 使用频率 (F\d+)',s)
    if m:return cmp('eq',var(m[1]),m[2])
    m=match(r'It is forbidden for (D\d+) to use (F\d+) while (D\d+) uses (F\d+)',s) or match(r'不得同时令 (D\d+) 使用 (F\d+)，并令 (D\d+) 使用 (F\d+)',s)
    if m:return ['not',['and',cmp('eq',var(m[1]),m[2]),cmp('eq',var(m[3]),m[4])]]
    m=match(r'The absolute difference between the frequency numbers used by (D\d+) and (D\d+) must be between (\d+) and (\d+), inclusive',s) or match(r'(D\d+) 与 (D\d+) 的频率编号之差的绝对值必须在 (\d+) 至 (\d+) 之间（含端点）',s)
    if m:return bounds(distance(['number',m[1]],['number',m[2]]),m[3],m[4])
    m=match(r'If (D\d+) uses (F\d+), then (D\d+) must use a frequency in \{(.+)\}',s) or match(r'若 (D\d+) 使用 (F\d+)，则 (D\d+) 必须使用 \{(.+)\} 中的频率',s)
    if m:return ['implies',cmp('eq',var(m[1]),m[2]),['in',var(m[3]),sorted(ids(m[4],r'F\d+'))]]
    raise ValueError(s)

def matching(s,groups):
    s=s.strip().rstrip('。.')
    m=match(r'(P\d+)=(V\d+) holds if and only if (P\d+)=(V\d+) holds',s) or match(r'(P\d+)=(V\d+) 与 (P\d+)=(V\d+) 要么同时成立，要么同时不成立',s)
    if m:return cmp('eq',cmp('eq',var(m[1]),m[2]),cmp('eq',var(m[3]),m[4]))
    m=match(r'Entity (P\d+) uses matching value (V\d+)',s) or match(r'实体 (P\d+) 使用匹配值 (V\d+)',s)
    if m:return cmp('eq',var(m[1]),m[2])
    m=match(r'N\((\w+),(\w+)\) (?:is )?(at most|at least|至多为|至少为) (\d+)',s)
    if m:return cmp('le' if m[3] in ('at most','至多为') else 'ge',groupcount(groups[m[1]],groups[m[2]]),int(m[4]))
    def linear(t):
        terms=re.findall(r'N\((\w+),(\w+)\)',t);tail=re.sub(r'N\(\w+,\w+\)','',t).replace(' ','').lstrip('+');offset=int(tail.replace('+','')) if tail.strip('+') else 0
        return ['sum',sorted([groupcount(groups[g],groups[h]) for g,h in terms],key=lambda x:json.dumps(x)),offset]
    if re.fullmatch(r'(?:N\(\w+,\w+\)\+)*N\(\w+,\w+\) = (?:N\(\w+,\w+\)\+)*N\(\w+,\w+\)(?:[+-]\d+)?',s):
        a,b=s.split(' = ');return cmp('eq',linear(a),linear(b))
    raise ValueError(s)

def task_direction(t):
    # Interpret the actual request, rather than relying on its stored task label.
    rules=[('must',['holds in every valid','每一个合法','在每个合法完整赋值中都成立']),
           ('may',['at least one valid','至少存在一个','在至少一个合法完整赋值中成立']),
           ('counterexample',['but not the target proposition','falsifying the target proposition','但目标命题不成立','使目标命题不成立']),
           ('witness',['and the target proposition exists','satisfying the target proposition exists','且目标命题成立','使目标命题成立'])]
    found=[k for k,phrases in rules if any(p in t for p in phrases)]
    # Chinese MAY includes the witness phrase, disambiguated by the explicit request to judge existence.
    if found==['may','witness']:found=['may']
    if len(found)!=1:raise ValueError(('task',found,t[:230]))
    return found[0]

def parse(r):
    text=r['text'];fam=r['family'];lang=r['language'];lines=text.splitlines()
    groups={m[1]:re.findall(r'[PV]\d+',m[2]) for line in lines if (m:=re.fullmatch(r'\[((?:S?[GH])\w*)\] (.+)',line))}
    constraints=[]
    for line in lines:
        m=re.fullmatch(r'\[([CS]\d+)\] (.+)',line)
        if m:
            exp=sched(m[2]) if fam=='scheduling' else freq(m[2]) if fam=='frequency_assignment' else matching(m[2],groups)
            constraints.append({'id':m[1],'text':m[2],'expression':exp})
    prop=re.search(r'## (?:Target proposition|目标命题)\n+([^\n]+)',text)[1]
    pe=sched(prop) if fam=='scheduling' else freq(prop) if fam=='frequency_assignment' else matching(prop,groups)
    tail=re.split(r'## (?:Requirements|要求|Output|输出要求)\n',text)[-1]
    task=task_direction(tail);assert task==r['task'],(task,r['task'])
    scenario=re.split(r'## (?:Scenario|场景)\n',text)[1].split('## ')[0].strip()
    domains={}
    for line in lines:
        m=re.fullmatch(r'- (D\d+): (.+)',line) or re.fullmatch(r'\[(P\d+)\] (.+)',line)
        if m:domains[m[1]]=sorted(ids(m[2],r'[FV]\d+'))
    if fam=='scheduling':
        base={'people':ids(re.search(r'(?:People: |人员：)([^\n]+)',text)[1],r'[A-R]'),'days':int(re.search(r'(?:Number of days: |天数：)(\d+)',text)[1]),'periods':['morning','afternoon','evening'],'sessions':9,'capacity':2,'adjacent_distance':1,'cross_day_adjacency':True,'person_once_explicit':'every person appearing exactly once' in scenario}
        assert ('exactly 2 people' in scenario or '每场恰好 2 人' in scenario)
        assert ('differ by exactly 1' in scenario or '绝对值为 1' in scenario)
        assert ('across day boundaries' in scenario or '分属相邻两天' in scenario)
        assert ('morning, afternoon, evening' in scenario or '上午、下午、晚上' in scenario)
        assert ('1 through 9' in scenario or '1 至 9' in scenario)
    elif fam=='frequency_assignment':
        base={'one_value_per_entity':True,'values':ids(re.search(r'(?:Available frequencies: |可用频率：)([^\n]+)',text)[1],r'F\d+')}
        assert ('choose exactly one frequency from its own allowed list' in scenario or '选择且只选择一个频率' in scenario)
    else:
        base={'one_value_per_entity':True,'all_values_once':True,'entities':[f'P{i:02}' for i in range(1,17)],'values':[f'V{i:02}' for i in range(1,17)]}
        assert ('every value must be used exactly once' in scenario or '每个值也必须恰好使用一次' in scenario)
        assert ('P01 through P16' in scenario or 'P01到P16' in scenario)
        assert ('N(G,H) be the number of entities' in text or 'N(G,H) 为实体组 G 中最终取值属于值组 H 的实体数' in text)
    return {k:v for k,v in r.items() if k!='text'}|{'scenario_text':scenario,'scenario':base,'domains':domains,'groups':groups,'constraints':constraints,'proposition_text':prop,'proposition':pe,'task_interpretation':task,'request_text':tail}

if __name__=='__main__':
    rows=[json.loads(s) for s in (HERE/'prompts_only.jsonl').read_text(encoding='utf-8').splitlines()];out=[];errors=[]
    for r in rows:
        try:out.append(parse(r))
        except Exception as e:errors.append({'prompt':r['prompt_id'],'error':str(e)})
    summary={'prompts':len(rows),'parsed':len(out),'errors':errors,'unique_csp_languages':len({(r['family'],r['csp_id'],r['language']) for r in out}),'unique_proposition_languages':len({(r['family'],r['quartet_id'],r['language']) for r in out})}
    (HERE/'parse_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    if not errors:
        p=HERE/'text_interpretations.jsonl';p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in out),encoding='utf-8')
        seal={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in ['parse_prompts.py','prompts_only.jsonl','text_interpretations.jsonl']}
        (HERE/'parser_seal.json').write_text(json.dumps(seal,indent=2),encoding='utf-8')
    print(json.dumps({**summary,'errors':errors[:6]},ensure_ascii=False,indent=2))
