"""用途：保留原GLM五条最终意图提取记录；输入原文与元数据，输出明确字段。使用原断言及规则，不按Gold选择答案，不改变原始正文。"""
import evidence_intent as intent

MANUAL_NOTES = {
 'E04_2': '正文缺外层花括号，answer=yes明确；只补解析括号。',
 'E05_4': 'content包含长篇草稿及</think>；采用其后唯一末尾JSON的answer=no。正文明确称候选不合法、P13=V06，因此候选命题不成立。',
 'E06_1': 'answer误填MUST，说明明确断言no valid complete assignment can make the target true；MAY最终意图为no。',
 'E06_2': '说明明确称The supplied candidate violates C17 and C18，提取candidate_valid=false；未明确判断给定候选命题，不补该字段。',
 'E01_3': 'answer=yes明确，但说明转为A与H而非所问C与H；候选两项均未明确报告，保留缺失，不影响判断评分。'
}

def read_final_intent(raw, prompt):
    rid, text = raw['request_id'], raw['final_text']
    payload = text
    if rid == 'E04_2':
        payload = '{' + text.strip() + '}'
    if rid == 'E05_4':
        assert '</think>' in text
        payload = text.rsplit('</think>', 1)[1].strip()
    result = intent.evaluate(payload, raw, prompt)
    if rid == 'E06_1':
        assert 'no valid complete assignment can make the target true' in text
        result['answer'] = 'no'
        result['answer_correct'] = 'no' == raw['gold_answer']
    if rid in ['E05_4', 'E06_2']:
        assert ('not fully valid' in payload if rid == 'E05_4' else 'The supplied candidate violates C17 and C18' in payload)
        result['candidate_valid_response'] = False
        result['candidate_valid_correct'] = raw['candidate_valid'] is False
    if rid == 'E05_4':
        assert 'candidate assignment with P13=V06' in payload and 'P13=V05' in payload
        result['proposition_response'] = False
        result['proposition_correct'] = raw['candidate_proposition_holds'] is False
    if rid in MANUAL_NOTES:
        result['manual_intent_note'] = MANUAL_NOTES[rid]
        result['final_answer_extraction'] = 'reviewed_final_content'
    return result

