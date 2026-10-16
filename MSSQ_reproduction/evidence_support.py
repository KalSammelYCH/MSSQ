"""用途：候选复现的原始字段提取和确定性核验函数。输入正文/形式CSP/赋值，输出字段及合法性；使用包内scoring执行验证，无模型调用。"""
from pathlib import Path
import json,hashlib,re
import scoring
REPRO=Path(__file__).resolve().parent

def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda:f.read(1024*1024), b''):
            h.update(data)
    return h.hexdigest()


def read_stream(path):
    final, finishes, models = [], [], set()
    done = False
    usage = None
    bad = events = reasoning_chars = 0
    h = hashlib.sha256()
    with path.open('rb') as f:
        for raw in f:
            h.update(raw)
            if not raw.startswith(b'data:'):
                continue
            payload = raw[5:].strip()
            if payload == b'[DONE]':
                done = True
                continue
            try:
                event = json.loads(payload)
            except (ValueError, UnicodeDecodeError):
                bad += 1
                continue
            events += 1
            if event.get('model'):
                models.add(event['model'])
            if isinstance(event.get('usage'), dict):
                usage = event['usage']
            for choice in event.get('choices', []):
                assert choice.get('index',0) == 0
                delta = choice.get('delta') or {}
                if isinstance(delta.get('content'), str):
                    final.append(delta['content'])
                if isinstance(delta.get('reasoning_content'), str):
                    reasoning_chars += len(delta['reasoning_content'])
                if choice.get('finish_reason') is not None:
                    finishes.append(choice['finish_reason'])
    return dict(final_text=''.join(final), finish_reasons=finishes, done=done, usage=usage,
                malformed_events=bad, events=events, reasoning_characters=reasoning_chars,
                response_models=sorted(models), stream_sha256=h.hexdigest())


def evaluate(text, meta, prompt):
    result = dict(json_object=False, contract_valid=False, answer=None, answer_correct=None,
                  candidate_valid_response=None,candidate_valid_correct=None,
                  proposition_response=None,proposition_correct=None,summary=None,format_issues=[])
    if not text.strip():
        result['format_issues']=['empty_final_content']
        return result
    try:
        value = json.loads(text)
    except ValueError:
        result['format_issues']=['not_single_json']
        return result
    if not isinstance(value,dict):
        result['format_issues']=['not_json_object']
        return result
    result['json_object'] = True
    answer = value.get('answer')
    if isinstance(answer,str) and answer in ['yes','no']:
        result['answer'] = answer
        result['answer_correct'] = answer == meta['gold_answer']
    else:
        result['format_issues'].append('answer_not_yes_no')
    required={'answer','reasoning_summary'}
    if meta['condition'] != 'no_candidate':
        required |= {'candidate_valid','candidate_proposition_holds'}
        for field, saved, correctness, gold in [
            ('candidate_valid','candidate_valid_response','candidate_valid_correct',meta['candidate_valid']),
            ('candidate_proposition_holds','proposition_response','proposition_correct',meta['candidate_proposition_holds'])]:
            if type(value.get(field)) is bool:
                result[saved]=value[field]
                result[correctness]=value[field] == gold
            else:
                result['format_issues'].append(field+'_not_boolean')
    if set(value)!=required:
        result['format_issues'].append('unexpected_or_missing_keys')
    summary=value.get('reasoning_summary')
    allowed=set(re.findall(r'^\[([^\]]+)\]',prompt,flags=re.M))
    if not isinstance(summary,list) or len(summary)!=1 or not isinstance(summary[0],dict):
        result['format_issues'].append('summary_shape')
    else:
        s=summary[0]
        result['summary']=s
        if set(s)!={'constraint_ids','statement'} or not isinstance(s.get('statement'),str):
            result['format_issues'].append('summary_fields')
        if not isinstance(s.get('constraint_ids'),list) or any(not isinstance(x,str) or x not in allowed for x in s.get('constraint_ids',[])):
            result['format_issues'].append('summary_ids')
        # 句数和说明是否支持最终判断另行人工阅读；不用简单标点规则替代语义核查。
    result['contract_valid']=not result['format_issues']
    return result


def check(family, q, assignment, profiles):
    if family == 'scheduling':
        profile = profiles[q['profile']] if isinstance(q['profile'], str) else q['profile']
        valid, _ = scoring.check_schedule(profile, q['constraints'], assignment)
        holds = scoring.evaluate_proposition(q['proposition'], assignment, profile)
    elif family == 'frequency_assignment':
        gen = scoring.FrequencyGenerator()
        valid = gen.validate_assignment(q['family_payload'], assignment)
        holds = gen.evaluate_proposition(q['family_payload'], assignment, q['proposition'])
    else:
        valid = scoring.bijective_valid_assignment(q['family_payload'], assignment)
        holds = scoring.bijective_proposition_holds(q['family_payload'], assignment, q['proposition'])
    return bool(valid), bool(holds)

