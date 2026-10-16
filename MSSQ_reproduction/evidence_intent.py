# 目的：执行统一答案判读原则：最终意图明确即可评分，格式只记备注。
# 输入：模型最终正文、冻结Gold元数据、题面；不读取隐藏推理，不更改原始正文。
# 输出：判断/候选字段评分、可读说明及格式偏离；正确性不受围栏或说明容器形式影响。
# 流程：复用原字段评分→识别完整JSON代码围栏→读取原对象字段→保留格式标记及提取方式。
# 目前自动处理本批实际出现的两种格式偏离。程序未提取的其他文本须人工审阅最终意图，
# 不能仅因自动解析失败判为无答案；多处冲突且无法确定最终判断时才保留不确定性。
import json
import re

import evidence_support as fields


def evaluate(text, meta, prompt):
    payload = text
    fenced = re.fullmatch(r'\s*```(?:json)?\s*\n([\s\S]*?)\n```\s*', text, flags=re.I)
    if fenced:
        payload = fenced.group(1)
    result = fields.evaluate(payload, meta, prompt)
    if fenced:
        result['format_issues'].append('markdown_code_fence')
    # 说明对象/数组的差异不改变已经明确的answer或候选字段，也不丢弃可读的说明原文。
    try:
        value = json.loads(payload)
    except ValueError:
        value = None
    if isinstance(value, dict) and isinstance(value.get('reasoning_summary'), dict):
        result['summary'] = value['reasoning_summary']
    result['contract_valid'] = not result['format_issues']
    result['final_answer_extraction'] = 'fenced_json_fields' if fenced else 'json_fields' if result['json_object'] else 'requires_manual_final_text_review'
    return result
