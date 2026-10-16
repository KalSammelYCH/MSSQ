"""
第三族双射匹配正式实验的隔离逐题评分器。

输入为冻结quartet、manifest中的response_contract、任务名和模型原始正文；输出为统一的
严格评分对象。MUST/MAY只接受裸YES/NO标签，WIT/CEX只接受裸NONE或一个P01--P16到
V01--V16的JSON对象。构造答案会依次核对键集合、公开允许域、值的全双射、全部公开
等价/聚合平衡线索以及目标命题方向。本文件不枚举解空间、不生成题目、不访问网络，也不
导入共享评分代码，避免其他实验窗口修改共享脚本时影响已冻结运行。
"""

from __future__ import annotations

import json
from typing import Any


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


def _aggregate_residual(
    csp: dict[str, Any], assignment: dict[str, str], clue: dict[str, Any]
) -> int:
    def count(term: dict[str, str]) -> int:
        accepted = set(csp["value_groups"][term["value_group"]])
        return sum(
            assignment[entity] in accepted
            for entity in csp["entity_groups"][term["entity_group"]]
        )

    left = sum(count(term) for term in clue["left_terms"])
    right = sum(count(term) for term in clue["right_terms"])
    return left - right - int(clue["offset"])


def _clue_holds(
    csp: dict[str, Any], assignment: dict[str, str], clue: dict[str, Any]
) -> bool:
    if clue["kind"] == "equivalence":
        left = assignment[clue["left"]["entity"]] == clue["left"]["value"]
        right = assignment[clue["right"]["entity"]] == clue["right"]["value"]
        return left == right
    if clue["kind"] == "aggregate_balance":
        return _aggregate_residual(csp, assignment, clue) == 0
    return False


def _valid_assignment(csp: dict[str, Any], assignment: Any) -> bool:
    if not isinstance(assignment, dict):
        return False
    entities = list(csp.get("entities", []))
    values = list(csp.get("values", []))
    allowed = csp.get("allowed_values", {})
    if set(assignment) != set(entities) or set(allowed) != set(entities):
        return False
    if any(assignment[entity] not in allowed[entity] for entity in entities):
        return False
    assigned_values = list(assignment.values())
    if set(assigned_values) != set(values) or len(assigned_values) != len(set(assigned_values)):
        return False
    return all(_clue_holds(csp, assignment, clue) for clue in csp.get("clues", []))


def _proposition_holds(
    csp: dict[str, Any], assignment: dict[str, str], proposition: dict[str, Any]
) -> bool:
    args = proposition["args"]
    if proposition["kind"] == "entity_uses_value":
        return assignment[args["entity"]] == args["value"]
    if proposition["kind"] == "group_count_bound":
        accepted = set(csp["value_groups"][args["value_group"]])
        count = sum(
            assignment[entity] in accepted
            for entity in csp["entity_groups"][args["entity_group"]]
        )
        if args["operator"] == "at_least":
            return count >= int(args["threshold"])
        if args["operator"] == "at_most":
            return count <= int(args["threshold"])
    return False


def score_one(
    quartet: dict[str, Any], contract: dict[str, Any], task: str, text: Any
) -> dict[str, Any]:
    if task not in TASKS or not isinstance(text, str):
        return _empty(quartet, task, "task_or_text")
    value = text.strip()
    result = {
        "quartet_id": quartet.get("quartet_id"),
        "task": task,
        "gold_modal_class": quartet.get("modality"),
        "parse_ok": True,
        "parse_errors": [],
        "response_answer": None,
        "assignment_valid": False,
        "proposition_condition_met": False,
        "correct": False,
    }
    if task in {"must", "may"}:
        labels = contract.get("allowed_labels", [])
        if value not in labels or labels != ["YES", "NO"]:
            return _empty(quartet, task, "label")
        answer = value == "YES"
        result["response_answer"] = answer
        result["correct"] = answer == bool(quartet[f"gold_{task}"])
        return result

    none_label = contract.get("none_label", "NONE")
    expected_exists = bool(
        quartet["gold_may"] if task == "witness" else not quartet["gold_must"]
    )
    if value == none_label:
        result["response_answer"] = False
        result["correct"] = not expected_exists
        return result
    try:
        assignment = json.loads(value)
    except json.JSONDecodeError:
        return _empty(quartet, task, "assignment_json")
    if not isinstance(assignment, dict):
        return _empty(quartet, task, "assignment")
    result["response_answer"] = True
    csp = quartet.get("family_payload")
    if not isinstance(csp, dict):
        return _empty(quartet, task, "family_payload")
    valid = _valid_assignment(csp, assignment)
    holds = _proposition_holds(csp, assignment, quartet["proposition"]) if valid else False
    condition_met = holds if task == "witness" else not holds
    result["assignment_valid"] = valid
    result["proposition_condition_met"] = condition_met
    result["correct"] = bool(expected_exists and valid and condition_met)
    return result
