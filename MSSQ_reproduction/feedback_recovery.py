"""反馈试验恢复函数：从回答提取唯一完整候选，保留原规则；题目从封装分支读取。"""
from __future__ import annotations
import json,re
from typing import Any
def quartet(branch):return branch['_bundled_quartet']


def json_values(text: str) -> list[Any]:
    values: list[Any] = []
    stripped = text.strip()
    if stripped == "NONE":
        return ["NONE"]
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char not in "{[\"":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if value not in values:
            values.append(value)
    return values


def recover(branch: dict[str, Any], text: str) -> tuple[Any, str | None]:
    q = quartet(branch)
    candidates = []
    for value in json_values(text):
        if value == "NONE":
            candidates.append(value)
        if not isinstance(value, dict):
            continue
        if branch["family"] == "scheduling":
            schedule = value.get("schedule", value)
            slot_count = q["profile"]["days"] * len(q["profile"]["periods"])
            expected_slots = {str(index) for index in range(1, slot_count + 1)}
            schedule_is_complete_shaped = (
                isinstance(schedule, dict)
                and set(schedule) == expected_slots
                and all(
                    isinstance(people, list) and all(isinstance(person, str) for person in people)
                    for people in schedule.values()
                )
                and sum(len(people) for people in schedule.values()) == q["profile"]["people_count"]
            )
            if schedule_is_complete_shaped:
                candidates.append({"answer": "存在", "schedule": schedule})
            answer_label = str(value.get("answer", "")).strip().lower()
            if value.get("schedule") is None and answer_label in {"no", "false", "不存在", "否"}:
                candidates.append("NONE")
        else:
            required = set(q["family_payload"].get("nodes", q["family_payload"].get("entities", [])))
            assignment = value.get("assignment", value)
            assignment_is_complete_shaped = (
                isinstance(assignment, dict)
                and len(assignment) == len(required)
                and (
                    "assignment" in value
                    or bool(set(assignment) & required)
                )
            )
            if assignment_is_complete_shaped:
                candidates.append(assignment)
            if str(value.get("answer", "")).lower() in {"no", "none", "不存在"} and value.get("assignment") is None:
                candidates.append("NONE")
    if re.search(r"(?<![A-Za-z0-9_])NONE(?![A-Za-z0-9_])", text) and not any(
            isinstance(value, dict) for value in candidates):
        candidates.append("NONE")
    unique = {json.dumps(v, ensure_ascii=False, sort_keys=True): v for v in candidates}
    return (next(iter(unique.values())), None) if len(unique) == 1 else (None, "no_unique_complete_result")
