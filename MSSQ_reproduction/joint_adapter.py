"""
Joint离线路径适配：输入包内dataset和manifest，供答案提取函数查询输出合同及Gold键集合。
输出为解析和赋值映射接口；所有依赖均从包内读取。
"""
import json
from joint_parse import parse_joint_response,_schedule_to_assignment,_reasoning_ids_valid


def read_jsonl(path):
    return [json.loads(x) for x in path.read_text(encoding='utf-8-sig').splitlines() if x.strip()]


def _expected_requires_construction(direction,judgment,labels):
    positive,negative=labels
    return (direction=='may_witness' and judgment==positive) or (direction=='must_counterexample' and judgment==negative)
