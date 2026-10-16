"""Joint恢复函数：输入原响应和封装流内容，沿用原候选唯一性规则；路径由本地adapter提供。"""
from __future__ import annotations
import hashlib,json,re
from dataclasses import dataclass
from pathlib import Path
from typing import Any,Iterable
from joint_parse import DuplicateKeyError,_object_no_duplicates
import joint_adapter as base
def _source_run_dir(record,fallback):return None
def _reconstruct_stream_payload(record,source):return record["_bundled_stream_payload"]

RECOVERY_RULE_ID = "joint_d355_deterministic_recovery_v1"


_FINAL_MARKER = re.compile(
    r"(?:FINAL\s+(?:ANSWER|SUBMISSION)|最终答案|最终提交)\s*[:：]",
    flags=re.IGNORECASE,
)


_MISSING = object()


@dataclass(frozen=True)
class RecoveryResult:
    parsed: dict[str, Any] | None
    strict_schema_pass: bool
    recovery_applied: bool
    recovery_source: str | None
    recovery_rule_id: str | None
    recovered_structure_sha256: str | None
    recovered_structure: dict[str, Any] | None
    payload_reconstructed_from_stream: bool
    stream_transcript_sha256: str | None
    strict_failure_reason: str | None
    failure_reason: str | None


def _canonical_sha256(value: dict[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _balanced_json_objects(text: str) -> list[str]:
    """提取正文中所有顶层花括号对象；引号内花括号不参与配平。"""

    results: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text):
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
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                results.append(text[start : index + 1])
                start = None
    return results


def _parse_object(text: str) -> dict[str, Any] | None:
    try:
        value = json.loads(text, object_pairs_hook=_object_no_duplicates)
    except (json.JSONDecodeError, DuplicateKeyError):
        return None
    return value if isinstance(value, dict) else None


def _top_level_prefix_objects(text: str) -> list[dict[str, Any]]:
    """读取未闭合外层JSON中已经完整形成的顶层字段，不补括号或字段值。"""

    decoder = json.JSONDecoder(object_pairs_hook=_object_no_duplicates)
    results: list[dict[str, Any]] = []
    for start, char in enumerate(text):
        if char != "{":
            continue
        index = start + 1
        fields: dict[str, Any] = {}
        invalid_candidate = False
        while index < len(text):
            while index < len(text) and text[index] in " \t\r\n,":
                index += 1
            if index >= len(text) or text[index] == "}":
                break
            try:
                key, after_key = decoder.raw_decode(text, index)
            except (json.JSONDecodeError, DuplicateKeyError):
                tail = text[index:].strip()
                if tail and not '"reasoning_summary"'.startswith(tail):
                    invalid_candidate = True
                break
            if not isinstance(key, str):
                break
            if key in fields:
                invalid_candidate = True
                break
            index = after_key
            while index < len(text) and text[index].isspace():
                index += 1
            if index >= len(text) or text[index] != ":":
                if key in {"judgment", "answer", "assignment", "schedule"}:
                    invalid_candidate = True
                break
            index += 1
            while index < len(text) and text[index].isspace():
                index += 1
            try:
                value, index = decoder.raw_decode(text, index)
            except (json.JSONDecodeError, DuplicateKeyError):
                if key != "reasoning_summary":
                    invalid_candidate = True
                break
            fields[key] = value
        if fields and not invalid_candidate:
            results.append(fields)
    return results


def _nested_semantic_objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if "judgment" in value or "answer" in value:
            yield value
        for nested in value.values():
            yield from _nested_semantic_objects(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _nested_semantic_objects(nested)


def _normalize_judgment(value: Any, labels: list[str]) -> str | None:
    if not isinstance(value, (str, bool)):
        return None
    if isinstance(value, bool):
        return labels[0] if value else labels[1]
    stripped = value.strip()
    if stripped in labels:
        return stripped
    folded = stripped.casefold()
    positive = {"yes", "true", "是"}
    negative = {"no", "false", "否"}
    if folded in positive:
        return labels[0]
    if folded in negative:
        return labels[1]
    return None


def _expected_variable_names(dataset_dir: Path, manifest: dict[str, Any]) -> set[str]:
    for gold in base.read_jsonl(dataset_dir / "gold.jsonl"):
        if gold.get("prompt_id") == manifest["prompt_id"]:
            construction = gold.get("canonical_construction")
            if isinstance(construction, dict):
                return set(construction)
            break
    raise ValueError(f"Gold缺少canonical构造：{manifest['prompt_id']}")


def _construction_is_complete(
    dataset_dir: Path,
    manifest: dict[str, Any],
    construction: Any,
) -> bool:
    expected = _expected_variable_names(dataset_dir, manifest)
    if manifest["family"] == "scheduling":
        assignment = base._schedule_to_assignment(construction)
        return assignment is not None and set(assignment) == expected
    return isinstance(construction, dict) and set(construction) == expected


def _semantic_candidate(
    dataset_dir: Path,
    manifest: dict[str, Any],
    value: dict[str, Any],
) -> dict[str, Any] | None:
    labels = manifest["response_contract"]["judgment_labels"]
    raw_judgments = [value[key] for key in ("judgment", "answer") if key in value]
    normalized = {_normalize_judgment(item, labels) for item in raw_judgments}
    normalized.discard(None)
    if len(normalized) != 1:
        return None
    judgment = next(iter(normalized))
    if any(_normalize_judgment(item, labels) != judgment for item in raw_judgments):
        return None
    field = "schedule" if manifest["family"] == "scheduling" else "assignment"
    construction = value.get(field, _MISSING)
    requires = base._expected_requires_construction(
        manifest["joint_direction"], judgment, labels
    )
    if requires:
        if construction is _MISSING or not _construction_is_complete(
            dataset_dir, manifest, construction
        ):
            return None
    elif construction is _MISSING:
        construction = None
    return {"judgment": judgment, field: construction}


def _candidates_from_text(
    dataset_dir: Path,
    manifest: dict[str, Any],
    text: str,
    source: str,
) -> list[tuple[dict[str, Any], str]]:
    candidates: list[tuple[dict[str, Any], str]] = []
    for fragment in _balanced_json_objects(text):
        value = _parse_object(fragment)
        if value is None:
            continue
        for semantic_object in _nested_semantic_objects(value):
            candidate = _semantic_candidate(dataset_dir, manifest, semantic_object)
            if candidate is not None:
                candidates.append((candidate, source))
    for value in _top_level_prefix_objects(text):
        candidate = _semantic_candidate(dataset_dir, manifest, value)
        if candidate is not None:
            candidates.append((candidate, source.replace("json", "json_prefix")))
    stripped = text.strip()
    labels = manifest["response_contract"]["judgment_labels"]
    judgment = _normalize_judgment(stripped, labels)
    if judgment is not None:
        field = "schedule" if manifest["family"] == "scheduling" else "assignment"
        candidate = _semantic_candidate(dataset_dir, manifest, {"judgment": judgment})
        if candidate is not None:
            candidates.append((candidate, source.replace("json", "label")))
    return candidates


def recover_joint_response(
    dataset_dir: str | Path,
    manifest: dict[str, Any],
    record: dict[str, Any],
    *,
    source_run_dir: str | Path | None = None,
) -> RecoveryResult:
    """严格优先；严格失败后只返回唯一且完整的显式语义对象。"""

    dataset_dir = Path(dataset_dir)
    fallback = Path(source_run_dir) if source_run_dir is not None else None
    record_source = _source_run_dir(record, fallback)
    stream_text, stream_reasoning, stream_sha = _reconstruct_stream_payload(
        record, record_source
    )
    text = record.get("response_text")
    parsed, strict_reason = base.parse_joint_response(
        text, manifest["response_contract"]
    )
    if parsed is not None:
        ids_valid = base._reasoning_ids_valid(dataset_dir, manifest, parsed)
        return RecoveryResult(
            parsed=parsed,
            strict_schema_pass=bool(ids_valid),
            recovery_applied=False,
            recovery_source=None,
            recovery_rule_id=None,
            recovered_structure_sha256=None,
            recovered_structure=None,
            payload_reconstructed_from_stream=False,
            stream_transcript_sha256=stream_sha,
            strict_failure_reason=None if ids_valid else "invalid_reasoning_constraint_ids",
            failure_reason=None,
        )

    if isinstance(stream_text, str) and stream_text:
        stream_parsed, stream_strict_reason = base.parse_joint_response(
            stream_text, manifest["response_contract"]
        )
        if stream_parsed is not None:
            ids_valid = base._reasoning_ids_valid(dataset_dir, manifest, stream_parsed)
            return RecoveryResult(
                parsed=stream_parsed,
                strict_schema_pass=bool(ids_valid),
                recovery_applied=True,
                recovery_source="stream_transcript_content_strict",
                recovery_rule_id=RECOVERY_RULE_ID,
                recovered_structure_sha256=_canonical_sha256(stream_parsed),
                recovered_structure=stream_parsed,
                payload_reconstructed_from_stream=True,
                stream_transcript_sha256=stream_sha,
                strict_failure_reason=(
                    None if ids_valid else "invalid_reasoning_constraint_ids"
                ),
                failure_reason=None,
            )
        if strict_reason in {None, "missing_response_text"}:
            strict_reason = stream_strict_reason

    candidates: list[tuple[dict[str, Any], str]] = []
    if isinstance(text, str) and text.strip():
        candidates.extend(
            _candidates_from_text(dataset_dir, manifest, text, "response_text_json")
        )
    if isinstance(stream_text, str) and stream_text:
        candidates.extend(
            _candidates_from_text(
                dataset_dir, manifest, stream_text, "stream_transcript_content_json"
            )
        )
    reasoning = record.get("reasoning_content")
    reasoning_sources = []
    if isinstance(reasoning, str):
        reasoning_sources.append((reasoning, "reasoning_explicit_final_json"))
    if isinstance(stream_reasoning, str):
        reasoning_sources.append(
            (stream_reasoning, "stream_transcript_reasoning_explicit_final_json")
        )
    invalid_final_section = False
    for reasoning_text, reasoning_source in reasoning_sources:
        markers = list(_FINAL_MARKER.finditer(reasoning_text))
        for index, marker in enumerate(markers):
            end = markers[index + 1].start() if index + 1 < len(markers) else len(reasoning_text)
            section_candidates = _candidates_from_text(
                dataset_dir,
                manifest,
                reasoning_text[marker.end() : end],
                reasoning_source,
            )
            section_unique: dict[str, tuple[dict[str, Any], str]] = {}
            for candidate, source in section_candidates:
                section_unique.setdefault(
                    _canonical_sha256(candidate), (candidate, source)
                )
            if len(section_unique) != 1:
                invalid_final_section = True
                continue
            candidates.append(next(iter(section_unique.values())))
    unique: dict[str, tuple[dict[str, Any], str]] = {}
    for candidate, source in candidates:
        unique.setdefault(_canonical_sha256(candidate), (candidate, source))
    if invalid_final_section or len(unique) != 1:
        return RecoveryResult(
            parsed=None,
            strict_schema_pass=False,
            recovery_applied=False,
            recovery_source=None,
            recovery_rule_id=None,
            recovered_structure_sha256=None,
            recovered_structure=None,
            payload_reconstructed_from_stream=False,
            stream_transcript_sha256=stream_sha,
            strict_failure_reason=strict_reason,
            failure_reason="irrecoverably_unparseable",
        )
    structure_hash, (candidate, source) = next(iter(unique.items()))
    return RecoveryResult(
        parsed=candidate,
        strict_schema_pass=False,
        recovery_applied=True,
        recovery_source=source,
        recovery_rule_id=RECOVERY_RULE_ID,
        recovered_structure_sha256=structure_hash,
        recovered_structure=candidate,
        payload_reconstructed_from_stream=bool(
            source.startswith("stream_transcript")
        ),
        stream_transcript_sha256=stream_sha,
        strict_failure_reason=strict_reason,
        failure_reason=None,
    )
