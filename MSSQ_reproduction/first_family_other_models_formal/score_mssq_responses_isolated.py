"""
MSSQ 四元组响应的严格解析、局部验真与可复现评分。

输入为 `quartets.jsonl` 的公开约束、命题与 gold 字段，以及每行含
`quartet_id`、`task`、`response` 的模型响应 JSONL；输出为逐任务
`scores.jsonl`、汇总 `summary.json` 和便于人工复核的 `summary.md`。流程先按
四种既定 schema 严格解析（只去除空白并规范化代码中列出的中英文布尔标签），
再将完整排程转换为人员到零基场次的赋值，分别用独立的 `check_schedule()` 和
`evaluate_proposition()` 验证 C 与 p/非 p。推理摘要不调用 LLM，只记录结构、
公开约束 ID 和显式结论冲突；最后按同一 quartet 的四项证据计算组级指标。
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
import sys
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from first_family_other_models_formal.mssq_solver_isolated import (
    check_schedule,
    evaluate_proposition,
)


TASKS = ("must", "may", "witness", "counterexample")
SCORING_CONTRACT_VERSION = "mssq_strict_scorer_v1"
METRICS = (
    "must_accuracy",
    "may_accuracy",
    "witness_validity_rate",
    "counterexample_validity_rate",
    "parse_rate",
    "quartet_exact_pass",
    "modal_classification_accuracy",
    "judgment_evidence_consistency",
    "unsupported_possibility_rate",
    "unsupported_necessity_rate",
    "necessity_refutation_rate",
    "two_sided_search_success",
)

# 只允许这些明确列出的标签；不猜测自然语言、拼写或缺失字段的含义。
JUDGMENT_LABELS = {"是": True, "否": False, "true": True, "false": False, "yes": True, "no": False}
EXISTENCE_LABELS = {"存在": True, "不存在": False, "true": True, "false": False, "yes": True, "no": False}


def _empty_result(quartet: dict, task: str, error: str) -> dict:
    return {
        "quartet_id": quartet.get("quartet_id"),
        "task": task,
        "gold_modal_class": quartet.get("modal_class"),
        "parse_ok": False,
        "parse_errors": [error],
        "reasoning_structure_ok": False,
        "valid_constraint_id_rate": None,
        "valid_constraint_id_count": 0,
        "constraint_id_count": 0,
        "answer_reasoning_contradiction": False,
        "response_answer": None,
        "schedule_valid": False,
        "proposition_condition_met": False,
        "positive_evidence": None,
        "negative_evidence": None,
        "correct": False,
    }


def _normalize_label(value: Any, labels: dict[str, bool]) -> bool | None:
    if not isinstance(value, str):
        return None
    return labels.get(value.strip())


def _profile_for(quartet: dict) -> dict | None:
    profile = quartet.get("profile")
    return profile if isinstance(profile, dict) else None


def _expected_people(profile: dict) -> list[str]:
    people_count = profile.get("people_count")
    if not isinstance(people_count, int) or isinstance(people_count, bool) or not 1 <= people_count <= 26:
        return []
    return [chr(ord("A") + index) for index in range(people_count)]


def _parse_reasoning_summary(response: dict, valid_ids: set[str]) -> tuple[bool, int, int, list[str], list[str]]:
    errors: list[str] = []
    statements: list[str] = []
    summary = response.get("reasoning_summary")
    if not isinstance(summary, list) or not 1 <= len(summary) <= 8:
        return False, 0, 0, ["reasoning_summary"], statements
    valid_count = 0
    total_count = 0
    for step in summary:
        if not isinstance(step, dict):
            errors.append("reasoning_summary")
            continue
        if set(step) != {"constraint_ids", "statement"}:
            errors.append("reasoning_summary")
            continue
        constraint_ids = step["constraint_ids"]
        statement = step["statement"]
        if not isinstance(constraint_ids, list) or not all(isinstance(item, str) for item in constraint_ids):
            errors.append("reasoning_summary")
            continue
        if not isinstance(statement, str) or not statement.strip():
            errors.append("reasoning_summary")
            continue
        total_count += len(constraint_ids)
        valid_count += sum(item in valid_ids for item in constraint_ids)
        if any(item not in valid_ids for item in constraint_ids):
            errors.append("constraint_ids")
        statements.append(statement)
    return "reasoning_summary" not in errors, valid_count, total_count, errors, statements


def _explicit_statement_answer(statement: str, task: str) -> bool | None:
    """只识别“结论/答案：标签”这一显式形式，避免把自由文本当作推理裁判。"""
    compact = statement.strip().replace(" ", "")
    for prefix in ("结论：", "结论:", "答案：", "答案:"):
        if compact.startswith(prefix):
            label = compact[len(prefix):]
            labels = JUDGMENT_LABELS if task in {"must", "may"} else EXISTENCE_LABELS
            return labels.get(label)
    return None


def _schedule_to_assignment(schedule: Any, profile: dict) -> tuple[dict[str, int] | None, str | None]:
    if not isinstance(schedule, dict):
        return None, "schedule"
    periods = profile.get("periods")
    days = profile.get("days")
    if not isinstance(periods, list) or not isinstance(days, int) or isinstance(days, bool):
        return None, "profile"
    slot_count = days * len(periods)
    expected_keys = {str(index) for index in range(1, slot_count + 1)}
    if set(schedule) != expected_keys:
        return None, "schedule"
    assignment: dict[str, int] = {}
    for slot in range(1, slot_count + 1):
        people = schedule[str(slot)]
        if not isinstance(people, list) or not all(isinstance(person, str) for person in people):
            return None, "schedule"
        for person in people:
            if person in assignment:
                return None, "schedule"
            assignment[person] = slot - 1
    if set(assignment) != set(_expected_people(profile)):
        return None, "schedule"
    return assignment, None


def score_one(
    quartet: dict,
    task: str,
    response: Any,
    *,
    require_reasoning_summary: bool = True,
) -> dict:
    """严格评分一项已解码 JSON 响应或 JSON 字符串，不修补字段或排程。"""
    if task not in TASKS:
        return _empty_result(quartet, task, "task")
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except json.JSONDecodeError:
            return _empty_result(quartet, task, "response_json")
    if not isinstance(response, dict):
        return _empty_result(quartet, task, "response")
    profile = _profile_for(quartet)
    if profile is None:
        return _empty_result(quartet, task, "profile")

    expected_fields = {"answer"}
    if require_reasoning_summary:
        expected_fields.add("reasoning_summary")
    if task in {"witness", "counterexample"}:
        expected_fields.add("schedule")
    errors: list[str] = []
    if set(response) != expected_fields:
        errors.append("response_fields")
    valid_ids = {
        item.get("constraint_id")
        for item in quartet.get("constraints", [])
        if isinstance(item, dict) and isinstance(item.get("constraint_id"), str)
    }
    if require_reasoning_summary:
        reasoning_ok, valid_ids_count, id_count, reasoning_errors, statements = _parse_reasoning_summary(response, valid_ids)
        errors.extend(reasoning_errors)
    else:
        reasoning_ok, valid_ids_count, id_count, statements = True, 0, 0, []
    labels = JUDGMENT_LABELS if task in {"must", "may"} else EXISTENCE_LABELS
    answer = _normalize_label(response.get("answer"), labels)
    if answer is None:
        errors.append("answer")
    explicit_answers = [_explicit_statement_answer(statement, task) for statement in statements]
    contradiction = any(value is not None and answer is not None and value != answer for value in explicit_answers)

    result = {
        "quartet_id": quartet.get("quartet_id"),
        "task": task,
        "gold_modal_class": quartet.get("modal_class"),
        "parse_ok": not errors,
        "parse_errors": sorted(set(errors)),
        "reasoning_structure_ok": reasoning_ok,
        "valid_constraint_id_rate": valid_ids_count / id_count if id_count else None,
        "valid_constraint_id_count": valid_ids_count,
        "constraint_id_count": id_count,
        "answer_reasoning_contradiction": contradiction,
        "response_answer": answer,
        "schedule_valid": False,
        "proposition_condition_met": False,
        "positive_evidence": None,
        "negative_evidence": None,
        "correct": False,
    }
    if errors:
        return result

    if task == "must":
        result["correct"] = answer == quartet.get("gold_must")
        return result
    if task == "may":
        result["correct"] = answer == quartet.get("gold_may")
        return result

    expected_exists = quartet.get("gold_may") if task == "witness" else not quartet.get("gold_must")
    if not answer:
        if response["schedule"] is not None:
            result["parse_ok"] = False
            result["parse_errors"] = ["schedule"]
            return result
        result["correct"] = expected_exists is False
        return result

    assignment, schedule_error = _schedule_to_assignment(response["schedule"], profile)
    if schedule_error is not None or assignment is None:
        result["parse_ok"] = False
        result["parse_errors"] = [schedule_error or "schedule"]
        return result
    schedule_valid, _ = check_schedule(profile, quartet.get("constraints", []), assignment)
    proposition_true = evaluate_proposition(quartet["proposition"], assignment, profile)
    required_truth = task == "witness"
    condition_met = proposition_true is required_truth
    result["schedule_valid"] = schedule_valid
    result["proposition_condition_met"] = condition_met
    if task == "witness":
        result["positive_evidence"] = True if schedule_valid and condition_met else None
    else:
        result["negative_evidence"] = True if schedule_valid and condition_met else None
    result["correct"] = expected_exists is True and schedule_valid and condition_met
    return result


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _one_task_records(records: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        if record.get("task") in TASKS:
            grouped[record.get("quartet_id")].append(record)
    return grouped


def _task_map(records: list[dict]) -> dict[str, dict] | None:
    by_task: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_task[record["task"]].append(record)
    if set(by_task) != set(TASKS) or any(len(by_task[task]) != 1 for task in TASKS):
        return None
    return {task: by_task[task][0] for task in TASKS}


def _strict_judgment(record: dict) -> bool | None:
    """只接受通过完整响应 schema 的布尔判断声明。"""
    answer = record.get("response_answer")
    if record.get("parse_ok") is not True or not isinstance(answer, bool):
        return None
    return answer


def _strict_construction_claim(record: dict, evidence_field: str) -> bool | None:
    """不存在是严格存在性声明；存在只有在构造验真后才是可用声明。"""
    answer = _strict_judgment(record)
    if answer is None:
        return None
    if answer is False:
        return False
    return True if record.get(evidence_field) is True else None


def _strict_constructive_evidence(record: dict, evidence_field: str) -> bool:
    return (
        record.get("parse_ok") is True
        and record.get("response_answer") is True
        and record.get(evidence_field) is True
    )


def _inferred_modal(task_records: dict[str, dict] | None) -> str | None:
    """只由四项提交的严格声明/有效证据推导，不读取 correct 或 gold。"""
    if task_records is None:
        return None
    must_answer = _strict_judgment(task_records["must"])
    may_answer = _strict_judgment(task_records["may"])
    witness_exists = _strict_construction_claim(
        task_records["witness"],
        "positive_evidence",
    )
    counterexample_exists = _strict_construction_claim(
        task_records["counterexample"],
        "negative_evidence",
    )
    pattern = (must_answer, may_answer, witness_exists, counterexample_exists)
    if pattern == (True, True, True, False):
        return "necessary"
    if pattern == (False, True, True, True):
        return "contingent"
    if pattern == (False, False, False, True):
        return "impossible"
    return None


def aggregate_scores(records: list[dict]) -> dict:
    """按实际记录的任务分母聚合，缺失任务须由调用方先显式补成失败记录。

    分母规则：MUST/MAY 准确率及两类构造有效率各以对应 task 的全部评分
    记录为分母；解析率以全部四类评分记录为分母；Quartet Exact Pass、模态
    分类准确率和双侧搜索成功率以每个 quartet 一次为分母（缺失/重复 task 不能
    通过）；判断—构造一致性只比较严格 MUST/MAY 与严格构造存在性声明。回答
    “不存在”可作为存在性声明，但回答“存在”只有在完整排程验真后才可使用。
    无支持可能性率以严格 MAY=true 为分母；单个构造不能支持 necessity，因此旧
    unsupported_necessity_rate 固定为空，另报告严格 MUST=true 被有效反例推翻的
    necessity_refutation_rate 及显式分子、分母。
    """
    task_records = {task: [record for record in records if record.get("task") == task] for task in TASKS}
    by_quartet = _one_task_records(records)
    quartet_maps = {quartet_id: _task_map(group) for quartet_id, group in by_quartet.items()}
    classifications = {quartet_id: _inferred_modal(task_map) for quartet_id, task_map in quartet_maps.items()}
    gold_classes = {
        quartet_id: next(
            (record.get("gold_modal_class") for record in group if record.get("gold_modal_class") is not None),
            None,
        )
        for quartet_id, group in by_quartet.items()
    }
    complete_quartets = [
        quartet_id
        for quartet_id, task_map in quartet_maps.items()
        if task_map is not None
    ]
    valid_modal_denominator = [quartet_id for quartet_id in complete_quartets if gold_classes[quartet_id] is not None]
    contingent_ids = [quartet_id for quartet_id in complete_quartets if gold_classes[quartet_id] == "contingent"]

    def correct_count(task: str) -> int:
        return sum(record.get("correct") is True for record in task_records[task])

    all_records = [record for task in TASKS for record in task_records[task]]
    id_total = sum(record.get("constraint_id_count", 0) for record in all_records)
    id_valid = sum(record.get("valid_constraint_id_count", 0) for record in all_records)
    exact_count = sum(
        task_map is not None and all(task_map[task].get("correct") is True for task in TASKS)
        for task_map in quartet_maps.values()
    )
    consistency_total = 0
    consistency_count = 0
    unsupported_possibility_total = 0
    unsupported_possibility_count = 0
    necessity_refutation_total = 0
    necessity_refutation_count = 0
    two_sided_count = 0
    for quartet_id, task_map in quartet_maps.items():
        if task_map is None:
            continue
        must_answer = _strict_judgment(task_map["must"])
        may_answer = _strict_judgment(task_map["may"])
        witness_exists = _strict_construction_claim(
            task_map["witness"],
            "positive_evidence",
        )
        counterexample_exists = _strict_construction_claim(
            task_map["counterexample"],
            "negative_evidence",
        )
        positive_evidence = _strict_constructive_evidence(
            task_map["witness"],
            "positive_evidence",
        )
        negative_evidence = _strict_constructive_evidence(
            task_map["counterexample"],
            "negative_evidence",
        )
        if may_answer is not None and witness_exists is not None:
            consistency_total += 1
            consistency_count += may_answer == witness_exists
        if must_answer is not None and counterexample_exists is not None:
            consistency_total += 1
            consistency_count += must_answer == (not counterexample_exists)
        if may_answer is True:
            unsupported_possibility_total += 1
            unsupported_possibility_count += not positive_evidence
        if must_answer is True:
            necessity_refutation_total += 1
            necessity_refutation_count += negative_evidence
        if quartet_id in contingent_ids:
            two_sided_count += positive_evidence and negative_evidence

    summary = {
        "response_count": len(all_records),
        "must_accuracy": (
            _ratio(correct_count("must"), len(task_records["must"]))
            if task_records["must"] else None
        ),
        "may_accuracy": (
            _ratio(correct_count("may"), len(task_records["may"]))
            if task_records["may"] else None
        ),
        "witness_validity_rate": (
            _ratio(correct_count("witness"), len(task_records["witness"]))
            if task_records["witness"] else None
        ),
        "counterexample_validity_rate": (
            _ratio(correct_count("counterexample"), len(task_records["counterexample"]))
            if task_records["counterexample"] else None
        ),
        "parse_rate": _ratio(sum(record.get("parse_ok") is True for record in all_records), len(all_records)),
        "quartet_exact_pass": (
            _ratio(exact_count, len(complete_quartets)) if complete_quartets else None
        ),
        "modal_classification_accuracy": (
            _ratio(
                sum(
                    classifications[quartet_id] == gold_classes[quartet_id]
                    for quartet_id in valid_modal_denominator
                ),
                len(valid_modal_denominator),
            )
            if valid_modal_denominator else None
        ),
        "judgment_evidence_consistency": (
            _ratio(consistency_count, consistency_total) if consistency_total else None
        ),
        "judgment_evidence_consistency_numerator": consistency_count,
        "judgment_evidence_consistency_denominator": consistency_total,
        "unsupported_possibility_rate": (
            _ratio(unsupported_possibility_count, unsupported_possibility_total)
            if unsupported_possibility_total
            else None
        ),
        "unsupported_possibility_numerator": unsupported_possibility_count,
        "unsupported_possibility_denominator": unsupported_possibility_total,
        "unsupported_necessity_rate": None,
        "necessity_refutation_rate": (
            _ratio(necessity_refutation_count, necessity_refutation_total)
            if necessity_refutation_total
            else None
        ),
        "necessity_refutation_numerator": necessity_refutation_count,
        "necessity_refutation_denominator": necessity_refutation_total,
        "two_sided_search_success": (
            _ratio(two_sided_count, len(contingent_ids)) if contingent_ids else None
        ),
        "reasoning_summary_structure_rate": _ratio(sum(record.get("reasoning_structure_ok") is True for record in all_records), len(all_records)),
        "valid_constraint_id_rate": _ratio(id_valid, id_total) if id_total else None,
        "valid_constraint_id_numerator": id_valid,
        "valid_constraint_id_denominator": id_total,
        "answer_reasoning_contradiction_rate": _ratio(sum(record.get("answer_reasoning_contradiction") is True for record in all_records), len(all_records)),
        "modal_classifications": classifications,
    }
    return summary


def _read_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path} 第 {line_number} 行不是 JSON 对象")
        records.append(value)
    return records


def _read_response_lines(path: Path) -> list[tuple[int, dict | None, str | None]]:
    """逐行读取响应，保留无效 JSON 的行号供审计，绝不让单行输入中断评分。"""
    records: list[tuple[int, dict | None, str | None]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            records.append((line_number, None, "invalid_json"))
            continue
        if not isinstance(value, dict):
            records.append((line_number, None, "response_record"))
            continue
        records.append((line_number, value, None))
    return records


def _normalize_profiles(payload: dict) -> dict[str, dict]:
    profiles = payload.get("profiles", payload)
    if not isinstance(profiles, dict):
        raise ValueError("profiles 配置必须为对象")
    return {name: value for name, value in profiles.items() if isinstance(value, dict)}


def _load_profiles(profiles_path: str | Path | None) -> dict[str, dict]:
    if profiles_path is None:
        profiles_path = Path(__file__).resolve().parents[1] / "configs" / "profiles.json"
    payload = json.loads(Path(profiles_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("profiles 配置必须为对象")
    return _normalize_profiles(payload)


def _missing_result(quartet: dict, task: str, error: str) -> dict:
    return _empty_result(quartet, task, error)


def _format_metric(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.6f}"


def score_responses(
    quartets_path: str | Path,
    responses_path: str | Path,
    output_dir: str | Path,
    *,
    profiles: dict[str, dict] | None = None,
    profiles_path: str | Path | None = None,
    selected_prompt_ids: tuple[str, ...] | None = None,
    require_reasoning_summary: bool = True,
) -> dict:
    """读取四元组与响应 JSONL，拒绝重复覆盖并写出全部预期任务的评分工件。"""
    quartets = _read_jsonl(Path(quartets_path))
    if profiles is not None and profiles_path is not None:
        raise ValueError("只能提供一种 profile 来源：profiles 或 profiles_path")
    resolved_profiles = _load_profiles(profiles_path) if profiles is None else _normalize_profiles(profiles)
    by_quartet: dict[str, dict] = {}
    for quartet in quartets:
        quartet_id = quartet.get("quartet_id")
        if not isinstance(quartet_id, str) or quartet_id in by_quartet:
            raise ValueError("quartets.jsonl 中 quartet_id 必须唯一且为字符串")
        resolved = dict(quartet)
        if isinstance(resolved.get("profile"), str):
            resolved["profile"] = resolved_profiles.get(resolved["profile"])
        by_quartet[quartet_id] = resolved

    expected_pairs: list[tuple[str, str]]
    if selected_prompt_ids is None:
        expected_pairs = [
            (quartet_id, task)
            for quartet_id in by_quartet
            for task in TASKS
        ]
    else:
        expected_pairs = []
        for prompt_id in selected_prompt_ids:
            if not isinstance(prompt_id, str) or "__" not in prompt_id:
                raise ValueError("selected_prompt_ids 必须使用 quartet_id__task 格式")
            quartet_id, task = prompt_id.rsplit("__", 1)
            if quartet_id not in by_quartet or task not in TASKS:
                raise ValueError(f"selected_prompt_ids 含未知 Prompt：{prompt_id}")
            expected_pairs.append((quartet_id, task))
        if len(set(expected_pairs)) != len(expected_pairs):
            raise ValueError("selected_prompt_ids 不得重复")

    received: dict[tuple[str, str], list[Any]] = defaultdict(list)
    rejected_inputs: list[dict] = []
    for line_number, record, read_error in _read_response_lines(Path(responses_path)):
        if read_error is not None:
            rejected_inputs.append(
                {"line_number": line_number, "quartet_id": None, "task": None, "reason": read_error}
            )
            continue
        assert record is not None
        quartet_id = record.get("quartet_id")
        task = record.get("task")
        if not isinstance(quartet_id, str):
            reason = "quartet_id_type"
        elif not isinstance(task, str):
            reason = "task_type"
        elif quartet_id not in by_quartet:
            reason = "unknown_quartet_id"
        elif task not in TASKS:
            reason = "unknown_task"
        elif set(record) != {"quartet_id", "task", "response"}:
            reason = "top_level_fields"
        else:
            received[(quartet_id, task)].append(record["response"])
            continue
        rejected_inputs.append(
            {"line_number": line_number, "quartet_id": quartet_id, "task": task, "reason": reason}
        )

    scored: list[dict] = []
    duplicate_response_count = 0
    missing_response_count = 0
    for quartet_id, task in expected_pairs:
        quartet = by_quartet[quartet_id]
        responses = received.get((quartet_id, task), [])
        if not responses:
            missing_response_count += 1
            scored.append(_missing_result(quartet, task, "missing_response"))
        elif len(responses) > 1:
            duplicate_response_count += len(responses) - 1
            scored.append(_missing_result(quartet, task, "duplicate_response"))
        else:
            scored.append(
                score_one(
                    quartet,
                    task,
                    responses[0],
                    require_reasoning_summary=require_reasoning_summary,
                )
            )

    summary = aggregate_scores(scored)
    summary.update(
        {
            "missing_response_count": missing_response_count,
            "duplicate_response_count": duplicate_response_count,
            "unknown_response_count": len(rejected_inputs),
            "rejected_inputs": rejected_inputs,
        }
    )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "scores.jsonl").write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in scored),
        encoding="utf-8",
    )
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "rejected_inputs.jsonl").write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in rejected_inputs),
        encoding="utf-8",
    )
    lines = ["# MSSQ response scoring summary", ""]
    lines.extend(
        f"- {metric}: {_format_metric(summary[metric])}"
        for metric in METRICS
    )
    lines.extend(
        [
            "",
            "## Diagnostics",
            "",
            f"- response_count: {summary['response_count']}",
            f"- missing_response_count: {missing_response_count}",
            f"- duplicate_response_count: {duplicate_response_count}",
            f"- unknown_response_count: {summary['unknown_response_count']}",
            f"- reasoning_summary_structure_rate: {summary['reasoning_summary_structure_rate']:.6f}",
            f"- valid_constraint_id_rate: {_format_metric(summary['valid_constraint_id_rate'])}",
            f"- valid_constraint_id_denominator: {summary['valid_constraint_id_denominator']}",
            f"- answer_reasoning_contradiction_rate: {summary['answer_reasoning_contradiction_rate']:.6f}",
        ]
    )
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="严格评分 MSSQ 四元组响应")
    parser.add_argument("quartets_jsonl")
    parser.add_argument("responses_jsonl")
    parser.add_argument("output_dir")
    parser.add_argument("--profiles", dest="profiles_path")
    args = parser.parse_args()
    score_responses(args.quartets_jsonl, args.responses_jsonl, args.output_dir, profiles_path=args.profiles_path)


if __name__ == "__main__":
    main()
