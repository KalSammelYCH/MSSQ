"""恢复与评分纯函数：输入返回内容和题目，提取候选后核验；函数体沿用冻结实现，文件依赖改为包内路径。"""
from __future__ import annotations
import hashlib, json, re
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parent
from first_family_other_models_formal.mssq_csp_families_isolated import Generator as FrequencyGenerator
from first_family_other_models_formal.mssq_solver_isolated import check_schedule, evaluate_proposition
from first_family_other_models_formal.score_mssq_responses_isolated import _schedule_to_assignment, score_one as score_scheduling
from first_family_other_models_formal.third_family_bijective_scorer_isolated import _proposition_holds as bijective_proposition_holds, _valid_assignment as bijective_valid_assignment


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def canonical_sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(payload)


def balanced_json_objects(text: str) -> list[Any]:
    objects: list[Any] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if start is None:
            if char == "{":
                start = index
                depth = 1
                in_string = False
                escaped = False
            continue
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : index + 1]
                try:
                    objects.append(json.loads(candidate))
                except json.JSONDecodeError:
                    pass
                start = None
    return objects


def bool_label(value: Any, construction: bool) -> bool | None:
    if isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    labels = {
        "是": True,
        "否": False,
        "yes": True,
        "no": False,
        "true": True,
        "false": False,
        "存在": True,
        "不存在": False,
        "none": False,
    }
    answer = labels.get(value)
    if construction and value in {"是", "否"}:
        return answer
    return answer


def canonical_candidate(family: str, task: str, value: Any) -> dict[str, Any] | None:
    construction = task in {"witness", "counterexample"}
    if family == "bijective_matching":
        if task in {"must", "may"}:
            if isinstance(value, str) and value.strip().upper() in {"YES", "NO"}:
                return {"answer": value.strip().upper() == "YES", "construction": None}
            return None
        if isinstance(value, str) and value.strip().upper() == "NONE":
            return {"answer": False, "construction": None}
        if isinstance(value, dict):
            return {"answer": True, "construction": value}
        return None
    if not isinstance(value, dict):
        return None
    answer = bool_label(value.get("answer"), construction)
    if answer is None:
        return None
    if not construction:
        return {"answer": answer, "construction": None, "raw_object": value}
    key = "schedule" if family == "scheduling" else "assignment"
    payload = value.get(key)
    if construction and answer is True and payload is not None and not isinstance(payload, dict):
        return None
    if construction and answer is False and payload is not None:
        return None
    return {"answer": answer, "construction": payload, "raw_object": value}


def anchored_field_candidate(family: str, task: str, text: str) -> dict[str, Any] | None:
    """从损坏的外层 JSON 中只恢复明确的顶层 answer 与独立可解码构造字段。"""
    answer_match = re.search(r'["\']answer["\']\s*:\s*([^,}\r\n]{1,80})', text, re.I)
    if answer_match is None or answer_match.start() > 200:
        return None
    segment = answer_match.group(1)
    labels = re.findall(
        r"(?<![A-Za-z\u4e00-\u9fff])(not\s+exist|does\s+not\s+exist|不存在|exists?|存在|yes|no|true|false|是|否)(?![A-Za-z\u4e00-\u9fff])",
        segment,
        re.I,
    )
    normalized = set()
    for label in labels:
        value = label.strip().lower()
        if value in {"yes", "true", "exist", "exists", "存在", "是"}:
            normalized.add(True)
        elif value in {"no", "false", "not exist", "does not exist", "不存在", "否"}:
            normalized.add(False)
    if len(normalized) != 1:
        return None
    answer = next(iter(normalized))
    if task in {"must", "may"}:
        return {"answer": answer, "construction": None}
    if answer is False:
        return {"answer": False, "construction": None}
    key = "schedule" if family == "scheduling" else "assignment"
    payload_match = re.search(rf'["\']{key}["\']\s*:\s*', text, re.I)
    if payload_match is None:
        return {"answer": True, "construction": None}
    try:
        payload, _ = json.JSONDecoder().raw_decode(text[payload_match.end() :].lstrip())
    except json.JSONDecodeError:
        return {"answer": True, "construction": None}
    if payload is None:
        return {"answer": True, "construction": None}
    if not isinstance(payload, dict):
        return None
    return {"answer": True, "construction": payload}


def recover_from_text(family: str, task: str, text: Any) -> tuple[dict[str, Any] | None, str]:
    if not isinstance(text, str) or not text.strip():
        return None, "missing_text"
    stripped = text.strip().lstrip("\ufeff\u200b").strip()
    direct_value: Any = None
    direct_ok = False
    try:
        direct_value = json.loads(stripped)
        direct_ok = True
    except json.JSONDecodeError:
        pass
    candidates: list[tuple[dict[str, Any], str]] = []
    if direct_ok:
        candidate = canonical_candidate(family, task, direct_value)
        if candidate:
            candidates.append((candidate, "strict_outer_value"))
    if family in {"scheduling", "frequency_assignment"}:
        candidate = anchored_field_candidate(family, task, stripped)
        if candidate:
            candidates.append((candidate, "anchored_answer_and_payload"))
    for value in balanced_json_objects(stripped):
        candidate = canonical_candidate(family, task, value)
        if candidate:
            candidates.append((candidate, "unique_embedded_json"))
    if family == "bijective_matching":
        if task in {"must", "may"}:
            tokens = {token.upper() for token in re.findall(r"(?<![A-Za-z])(YES|NO)(?![A-Za-z])", stripped, re.I)}
            if len(tokens) == 1:
                candidate = canonical_candidate(family, task, next(iter(tokens)))
                if candidate:
                    candidates.append((candidate, "unique_label_token"))
        else:
            none_count = len(re.findall(r"(?<![A-Za-z])NONE(?![A-Za-z])", stripped, re.I))
            if none_count and not balanced_json_objects(stripped):
                candidates.append(({"answer": False, "construction": None}, "unique_none_claim"))
    unique: dict[str, tuple[dict[str, Any], str]] = {}
    for candidate, method in candidates:
        key = canonical_sha({"answer": candidate["answer"], "construction": candidate.get("construction")})
        unique.setdefault(key, (candidate, method))
    if len(unique) == 1:
        return next(iter(unique.values()))
    return None, "no_unique_semantic_candidate" if not unique else "conflicting_semantic_candidates"


def recover_record(detail: dict[str, Any], record: dict[str, Any]) -> tuple[dict[str, Any] | None, str, str]:
    slot = detail["slot"]
    candidate, method = recover_from_text(slot["family"], slot["task"], record.get("response_text"))
    if candidate is not None:
        strict = strict_parse_ok(detail, record.get("response_text"))
        return candidate, "strict" if strict else "conservative_recovery", method
    reasoning = record.get("reasoning_content")
    if isinstance(reasoning, str):
        markers = list(re.finditer(r"(?:FINAL\s+ANSWER|FINAL|\u6700\u7ec8\u7b54\u6848)\s*[:\uff1a]", reasoning, re.I))
        if len(markers) == 1:
            candidate, method = recover_from_text(
                slot["family"], slot["task"], reasoning[markers[0].end() :]
            )
            if candidate is not None:
                return candidate, "conservative_recovery", f"reasoning_explicit_final_marker:{method}"
    return None, "unrecoverable", method


def strict_parse_ok(detail: dict[str, Any], text: Any) -> bool:
    slot = detail["slot"]
    quartet = detail["quartet"]
    task = slot["task"]
    if slot["family"] == "scheduling":
        return score_scheduling(quartet, task, text).get("parse_ok") is True
    if slot["family"] == "frequency_assignment":
        from first_family_other_models_formal.second_family_frequency_scorer_isolated import score_one

        return score_one(quartet, detail["contract"], task, text).get("parse_ok") is True
    from first_family_other_models_formal.third_family_bijective_scorer_isolated import score_one

    return score_one(quartet, detail["contract"], task, text).get("parse_ok") is True


def gold_exists(slot: dict[str, Any]) -> bool:
    if slot["task"] == "witness":
        return bool(slot["gold_may"])
    if slot["task"] == "counterexample":
        return not bool(slot["gold_must"])
    raise ValueError("只有构造任务有目标方向存在性")


def evaluate_candidate(detail: dict[str, Any], candidate: dict[str, Any] | None) -> dict[str, Any]:
    slot = detail["slot"]
    task = slot["task"]
    base = {
        "recognizable_answer": None,
        "claim_correct": None,
        "construction_required": task in {"witness", "counterexample"} and gold_exists(slot),
        "construction_present": False,
        "construction_complete": False,
        "public_constraints_valid": None,
        "target_direction_valid": None,
        "strict_success": False,
    }
    if candidate is None:
        return base
    answer = candidate["answer"]
    base["recognizable_answer"] = answer
    if task in {"must", "may"}:
        base["claim_correct"] = answer == bool(slot[f"gold_{task}"])
        base["strict_success"] = bool(base["claim_correct"])
        return base
    expected_exists = gold_exists(slot)
    base["claim_correct"] = answer == expected_exists
    construction = candidate.get("construction")
    base["construction_present"] = construction is not None
    if answer is False:
        base["strict_success"] = not expected_exists and construction is None
        return base
    quartet = detail["quartet"]
    family = slot["family"]
    if family == "scheduling":
        profile = quartet.get("profile")
        if isinstance(profile, str):
            profiles = read_json(ROOT / "configs/profiles.json").get("profiles", {})
            profile = profiles.get(profile)
        assignment, _ = _schedule_to_assignment(construction, profile)
        base["construction_complete"] = assignment is not None
        if assignment is not None:
            public_valid, _ = check_schedule(profile, quartet["constraints"], assignment)
            holds = evaluate_proposition(quartet["proposition"], assignment, profile)
            base["public_constraints_valid"] = bool(public_valid)
            base["target_direction_valid"] = bool(holds if task == "witness" else not holds)
    elif family == "frequency_assignment":
        csp = quartet.get("family_payload")
        nodes = list((csp or {}).get("nodes", []))
        base["construction_complete"] = isinstance(construction, dict) and set(construction) == set(nodes)
        if base["construction_complete"]:
            generator = FrequencyGenerator()
            public_valid = generator.validate_assignment(csp, construction)
            holds = generator.evaluate_proposition(csp, construction, quartet["proposition"])
            base["public_constraints_valid"] = bool(public_valid)
            base["target_direction_valid"] = bool(holds if task == "witness" else not holds)
    else:
        csp = quartet.get("family_payload")
        entities = list((csp or {}).get("entities", []))
        base["construction_complete"] = isinstance(construction, dict) and set(construction) == set(entities)
        if base["construction_complete"]:
            public_valid = bijective_valid_assignment(csp, construction)
            holds = bijective_proposition_holds(csp, construction, quartet["proposition"])
            base["public_constraints_valid"] = bool(public_valid)
            base["target_direction_valid"] = bool(holds if task == "witness" else not holds)
    base["strict_success"] = bool(
        expected_exists
        and base["construction_complete"]
        and base["public_constraints_valid"]
        and base["target_direction_valid"]
    )
    return base
