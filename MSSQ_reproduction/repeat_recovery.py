"""重复采样恢复函数：输入固定采用记录和题目，输出候选；沿用现有规则。"""
from __future__ import annotations
import json,re
from typing import Any
import scoring as phase

def recover_adopted_candidate(
    adopted: dict[str, str],
    detail: dict[str, Any],
    record: dict[str, Any],
) -> tuple[dict[str, Any] | None, str, str]:
    """保留严格解析优先，并处理S-01已观察到的明确最终片段。"""

    text = record.get("response_text")
    if isinstance(text, str) and "</think>" in text:
        final_segment = text.rsplit("</think>", 1)[1]
        candidate, method = phase.recover_from_text(
            adopted["family"], adopted["task"], final_segment
        )
        if candidate is not None:
            return candidate, "conservative_recovery", f"post_think_final_segment:{method}"
    candidate, parse_status, recovery_method = phase.recover_record(detail, record)
    if candidate is not None and parse_status == "strict":
        return candidate, parse_status, recovery_method
    if (
        adopted["family"] == "bijective_matching"
        and isinstance(text, str)
    ):
        if adopted["task"] in {"must", "may"}:
            terminal = re.search(r"(?<![A-Za-z])(YES|NO)[.!。]?\s*$", text.strip(), re.I)
        else:
            terminal = re.search(r"(?<![A-Za-z])(NONE)[.!。]?\s*$", text.strip(), re.I)
        if terminal is not None:
            candidate = phase.canonical_candidate(
                adopted["family"], adopted["task"], terminal.group(1)
            )
            if candidate is not None:
                return candidate, "conservative_recovery", "explicit_terminal_label_suffix"
    if candidate is not None:
        return candidate, parse_status, recovery_method
    if (
        adopted["family"] == "frequency_assignment"
        and adopted["task"] in {"witness", "counterexample"}
        and isinstance(text, str)
    ):
        repaired = text.strip().replace('\\"', '"')
        match = re.fullmatch(r"\{\\assignment:\s*(\{.*\})\s*\}", repaired, re.S)
        if match is not None:
            try:
                assignment = json.loads(match.group(1))
            except json.JSONDecodeError:
                assignment = None
            if isinstance(assignment, dict):
                return (
                    {"answer": True, "construction": assignment},
                    "conservative_recovery",
                    "mechanically_unescaped_bare_assignment",
                )
    if adopted["terminal_category"] == "reasoning_only_recovery":
        candidate, method = phase.recover_from_text(
            adopted["family"], adopted["task"], record.get("reasoning_content")
        )
        if candidate is not None:
            return (
                candidate,
                "conservative_recovery",
                f"registered_reasoning_unique_semantic_candidate:{method}",
            )
    return None, parse_status, recovery_method
