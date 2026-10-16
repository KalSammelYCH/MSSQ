"""
第二族频率分配正式实验的隔离逐题评分器。

输入是一条冻结quartet、对应manifest中的response_contract、任务名及模型原始正文；输出为
可直接写入JSONL的严格评分对象。评分先检查单一JSON对象、字段集合、恰好一条短理由、公开
约束编号和语言标签，再把WIT/CEX的完整D01--D26频率assignment交给隔离Generator验证
全部冲突边、允许频率、聚合计数及目标方向。MUST/MAY只比较Gold布尔值；不存在型构造必须
使用null assignment。该文件不生成题、不枚举解集、不访问网络，也不导入共享评分器。
"""

from __future__ import annotations

import json
import re
from typing import Any

from first_family_other_models_formal.mssq_csp_families_isolated import Generator


TASKS = {"must", "may", "witness", "counterexample"}


def _empty(quartet: dict[str, Any], task: str, error: str) -> dict[str, Any]:
    return {
        "quartet_id": quartet.get("quartet_id"),
        "task": task,
        "gold_modal_class": quartet.get("modality"),
        "parse_ok": False,
        "parse_errors": [error],
        "response_answer": None,
        "assignment_valid": False,
        "proposition_condition_met": False,
        "correct": False,
    }


def score_one(
    quartet: dict[str, Any], contract: dict[str, Any], task: str, text: Any
) -> dict[str, Any]:
    if task not in TASKS or contract.get("task") != task:
        return _empty(quartet, task, "task")
    if not isinstance(text, str):
        return _empty(quartet, task, "missing_response_text")
    try:
        response = json.loads(text.strip())
    except json.JSONDecodeError:
        return _empty(quartet, task, "response_json")
    if not isinstance(response, dict):
        return _empty(quartet, task, "response")
    errors: list[str] = []
    expected_fields = set(contract.get("fields", []))
    if set(response) != expected_fields:
        errors.append("response_fields")
    summaries = response.get("reasoning_summary")
    reason_contract = contract.get("reasoning_summary", {})
    if not isinstance(summaries, list) or len(summaries) != reason_contract.get(
        "exact_item_count", 1
    ):
        errors.append("reasoning_summary_item_count")
    else:
        summary = summaries[0]
        if not isinstance(summary, dict) or set(summary) != set(
            reason_contract.get("item_fields", ["constraint_ids", "statement"])
        ):
            errors.append("reasoning_summary_fields")
        else:
            ids = summary.get("constraint_ids")
            allowed = set(contract.get("allowed_constraint_ids", []))
            if (
                not isinstance(ids, list)
                or any(not isinstance(value, str) or value not in allowed for value in ids)
            ):
                errors.append("reasoning_constraint_ids")
            statement = summary.get("statement")
            if not isinstance(statement, str) or not statement.strip():
                errors.append("reasoning_statement")
            elif len(
                [part for part in re.split(r"[。！？!?]+", statement) if part.strip()]
            ) > reason_contract.get("statement_max_sentences", 2):
                errors.append("reasoning_statement_too_long")
    labels = contract.get("answer_labels", [])
    answer = response.get("answer")
    if answer not in labels or len(labels) != 2:
        errors.append("answer")
        normalized_answer = None
    else:
        normalized_answer = answer == labels[0]
    result = {
        "quartet_id": quartet.get("quartet_id"),
        "task": task,
        "gold_modal_class": quartet.get("modality"),
        "parse_ok": not errors,
        "parse_errors": sorted(set(errors)),
        "response_answer": normalized_answer,
        "assignment_valid": False,
        "proposition_condition_met": False,
        "correct": False,
    }
    if errors:
        return result
    if task in {"must", "may"}:
        result["correct"] = normalized_answer == quartet[f"gold_{task}"]
        return result
    assignment = response.get("assignment")
    expected_exists = quartet["gold_may"] if task == "witness" else not quartet["gold_must"]
    if normalized_answer is False:
        if assignment is not None:
            result["parse_ok"] = False
            result["parse_errors"] = ["assignment"]
            return result
        result["correct"] = expected_exists is False
        return result
    generator = Generator()
    csp = quartet.get("family_payload")
    if not isinstance(assignment, dict) or not isinstance(csp, dict):
        result["parse_ok"] = False
        result["parse_errors"] = ["assignment"]
        return result
    valid = generator.validate_assignment(csp, assignment)
    holds = generator.evaluate_proposition(csp, assignment, quartet["proposition"]) if valid else False
    condition_met = holds if task == "witness" else not holds
    result["assignment_valid"] = valid
    result["proposition_condition_met"] = condition_met
    result["correct"] = bool(expected_exists and valid and condition_met)
    return result
