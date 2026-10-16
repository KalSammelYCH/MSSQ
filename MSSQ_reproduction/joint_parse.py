"""Joint解析纯函数：输入输出合同及回答，执行原严格解析；不访问模型。"""
from __future__ import annotations
import json,re
from pathlib import Path
from typing import Any
def _read_jsonl(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8-sig").splitlines() if x.strip()]

class DuplicateKeyError(ValueError):
    pass


def _object_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate_json_key:{key}")
        result[key] = value
    return result


def _sentence_count(text: str) -> int:
    return len([part for part in re.split(r"[。！？!?]+", text.strip()) if part.strip()])


def parse_joint_response(text: Any, contract: dict[str, Any]) -> tuple[Any, str | None]:
    """严格解析一个 Joint JSON；成功时保留完整对象供后续联合评分。"""

    if not isinstance(text, str):
        return None, "missing_response_text"
    value = text.strip()
    if not value.startswith("{") or not value.endswith("}"):
        return None, "json_prefix_or_suffix"
    try:
        parsed = json.loads(value, object_pairs_hook=_object_no_duplicates)
    except DuplicateKeyError as error:
        return None, str(error)
    except json.JSONDecodeError:
        return None, "invalid_json"
    if not isinstance(parsed, dict):
        return None, "response_not_object"
    fields = contract.get("fields")
    if not isinstance(fields, list) or set(parsed) != set(fields):
        return None, "response_fields_mismatch"
    if parsed.get("judgment") not in contract.get("judgment_labels", []):
        return None, "invalid_judgment_label"

    reasoning = contract.get("reasoning_summary")
    if reasoning is not None:
        summaries = parsed.get("reasoning_summary")
        if not isinstance(summaries, list):
            return None, "reasoning_summary_not_array"
        if "exact_item_count" in reasoning and len(summaries) != reasoning["exact_item_count"]:
            return None, "reasoning_summary_item_count"
        if not reasoning.get("min_item_count", 0) <= len(summaries) <= reasoning.get("max_item_count", 10**9):
            return None, "reasoning_summary_item_count"
        for item in summaries:
            if not isinstance(item, dict) or set(item) != {"constraint_ids", "statement"}:
                return None, "reasoning_summary_fields"
            ids = item["constraint_ids"]
            statement = item["statement"]
            if not isinstance(ids, list) or any(not isinstance(x, str) for x in ids):
                return None, "reasoning_constraint_ids_type"
            if not isinstance(statement, str) or not statement.strip():
                return None, "empty_reasoning_statement"
            if _sentence_count(statement) > reasoning.get("statement_max_sentences", 10**9):
                return None, "reasoning_statement_too_many_sentences"
    return parsed, None


def _schedule_to_assignment(schedule: Any) -> dict[str, int] | None:
    expected_sessions = {str(i) for i in range(1, 10)}
    if not isinstance(schedule, dict) or set(schedule) != expected_sessions:
        return None
    result: dict[str, int] = {}
    for session, people in schedule.items():
        if not isinstance(people, list) or any(not isinstance(person, str) for person in people):
            return None
        for person in people:
            if person in result:
                return None
            result[person] = int(session)
    return result


def _reasoning_ids_valid(dataset_dir: Path, manifest: dict[str, Any], parsed: dict[str, Any]) -> bool:
    summaries = parsed.get("reasoning_summary")
    if summaries is None:
        return True
    prompt = (dataset_dir / manifest["prompt_path"]).read_text(encoding="utf-8-sig")
    allowed = set(re.findall(r"\bC\d+\b", prompt))
    return all(set(item["constraint_ids"]).issubset(allowed) for item in summaries)
