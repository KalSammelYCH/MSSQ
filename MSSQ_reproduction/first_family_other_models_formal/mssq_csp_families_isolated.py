"""
MSSQ 新增 CSP 家族的规则化 Generator 与主流水线 Oracle。

本文件只处理列表频率分配和 Exact Cover 两个新增家族，不修改冻结的 v8 排程数据。
输入是 JSON 参数档、确定性 development seed，或已经结构化的单个 CSP；输出是候选 CSP
的完整解集、可判定派生命题、中文 development Prompt、主 Oracle 报告和 SHA-256 清单。
主要流程为：按家族规则生成候选 → 使用手写回溯完整枚举 → 过滤平凡/直接复述命题 →
选择有正反支持的 contingent 命题 → 对频率题测量目标条件下的单值传播、分支与回溯负担 →
用“存在／不存在＋条件性 assignment”渲染频率 WITNESS → 形成可验证工件 → Oracle
重新枚举并按版本核对解集、Gold与公开题面。频率新记录使用v4存在性封装；已弃用的
Exact Cover原型及v2/v3历史工件保留旧Prompt合同。程序不调用任何模型或API；所有已展示
development题都应永久排除于正式集。

公共角色名称刻意与 v8 对齐为 ``Generator`` 和 ``Oracle``。两个家族共享工件合同，
但保留各自的约束字段和求解逻辑，避免为了表面统一引入空壳适配层。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
from typing import Any, Iterable


SCHEMA_VERSION = "mssq_csp_development_v1"
GENERATOR_VERSION = "mssq_csp_generator_v4"
PROMPT_CONTRACT = "v8_layout_existence_wrapper_no_rationale_v2"
LEGACY_PROMPT_CONTRACT = "v8_layout_unaided_no_rationale_v1"
LEGACY_GENERATOR_VERSIONS = {
    "mssq_csp_generator_v1",
    "mssq_csp_generator_v2",
    "mssq_csp_generator_v3",
}
DIFFICULTY_PARAMETER_KEYS = {
    "min_target_residual_variables",
    "min_search_branch_decisions",
    "min_search_backtracks",
    "min_search_nodes",
}
FAMILIES = ("frequency_assignment", "exact_cover")


def _current_record_contract(family: str) -> tuple[str, str]:
    if family == "frequency_assignment":
        return GENERATOR_VERSION, PROMPT_CONTRACT
    return "mssq_csp_generator_v2", LEGACY_PROMPT_CONTRACT


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalise_edge(node_a: str, node_b: str) -> tuple[str, str]:
    return tuple(sorted((node_a, node_b)))


def _solution_key(csp: dict[str, Any], assignment: dict[str, Any]) -> tuple[Any, ...]:
    if csp["family"] == "frequency_assignment":
        return tuple(assignment[node] for node in csp["nodes"])
    return tuple(assignment[set_id] for set_id in csp["candidate_sets"])


def _normalise_solutions(
    csp: dict[str, Any], solutions: Iterable[dict[str, Any]]
) -> list[dict[str, Any]]:
    return sorted((dict(row) for row in solutions), key=lambda row: _solution_key(csp, row))


class Generator:
    """规则化生成候选并用主实现完整枚举、构造 Gold。"""

    def enumerate_solutions(
        self, csp: dict[str, Any], limit: int | None = None
    ) -> list[dict[str, Any]]:
        self.validate_csp(csp)
        if csp["family"] == "frequency_assignment":
            return self._enumerate_frequency(csp, limit)
        if csp["family"] == "exact_cover":
            return self._enumerate_exact_cover(csp, limit)
        raise ValueError(f"unsupported family: {csp.get('family')}")

    def _enumerate_frequency(
        self, csp: dict[str, Any], limit: int | None
    ) -> list[dict[str, str]]:
        nodes = list(csp["nodes"])
        allowed = csp["allowed_frequencies"]
        neighbours = {node: set() for node in nodes}
        for node_a, node_b in csp["conflict_edges"]:
            neighbours[node_a].add(node_b)
            neighbours[node_b].add(node_a)

        # 固定 MRV/度数顺序；这是一套主实现的回溯编码，不依赖 CP-SAT。
        order = sorted(nodes, key=lambda node: (len(allowed[node]), -len(neighbours[node]), node))
        partial: dict[str, str] = {}
        rows: list[dict[str, str]] = []

        def visit(index: int) -> bool:
            if index == len(order):
                assignment = {node: partial[node] for node in nodes}
                if not self._heterogeneous_frequency_constraints_hold(csp, assignment):
                    return False
                rows.append(assignment)
                return limit is not None and len(rows) >= limit
            node = order[index]
            for frequency in allowed[node]:
                if any(partial.get(other) == frequency for other in neighbours[node]):
                    continue
                partial[node] = frequency
                if not self._heterogeneous_frequency_constraints_hold(
                    csp, partial, partial_assignment=True
                ):
                    del partial[node]
                    continue
                if visit(index + 1):
                    return True
                del partial[node]
            return False

        visit(0)
        return _normalise_solutions(csp, rows)

    def _enumerate_exact_cover(
        self, csp: dict[str, Any], limit: int | None
    ) -> list[dict[str, str]]:
        elements = list(csp["elements"])
        candidate_sets = csp["candidate_sets"]
        set_ids = list(candidate_sets)
        set_elements = {set_id: set(values) for set_id, values in candidate_sets.items()}
        containing = {
            element: [set_id for set_id in set_ids if element in set_elements[set_id]]
            for element in elements
        }
        rows: list[dict[str, str]] = []

        def visit(uncovered: set[str], selected: set[str]) -> bool:
            if not uncovered:
                rows.append(
                    {
                        set_id: "SELECTED" if set_id in selected else "NOT_SELECTED"
                        for set_id in set_ids
                    }
                )
                return limit is not None and len(rows) >= limit
            element = min(
                uncovered,
                key=lambda item: (
                    sum(set_elements[set_id] <= uncovered for set_id in containing[item]),
                    item,
                ),
            )
            for set_id in containing[element]:
                covered = set_elements[set_id]
                if not covered <= uncovered:
                    continue
                if visit(uncovered - covered, selected | {set_id}):
                    return True
            return False

        visit(set(elements), set())
        return _normalise_solutions(csp, rows)

    def validate_csp(self, csp: dict[str, Any]) -> None:
        family = csp.get("family")
        if family not in FAMILIES:
            raise ValueError(f"family must be one of {FAMILIES}")
        if family == "frequency_assignment":
            nodes = csp.get("nodes")
            frequencies = csp.get("frequencies")
            allowed = csp.get("allowed_frequencies")
            edges = csp.get("conflict_edges")
            if not isinstance(nodes, list) or not nodes or len(nodes) != len(set(nodes)):
                raise ValueError("frequency nodes must be a non-empty unique list")
            if not isinstance(frequencies, list) or len(frequencies) < 2:
                raise ValueError("frequency list must contain at least two values")
            if not isinstance(allowed, dict) or set(allowed) != set(nodes):
                raise ValueError("allowed_frequencies must cover every node exactly once")
            for node in nodes:
                values = allowed[node]
                if not values or len(values) != len(set(values)) or not set(values) <= set(frequencies):
                    raise ValueError(f"invalid frequency list for {node}")
            seen_edges: set[tuple[str, str]] = set()
            for edge in edges:
                if not isinstance(edge, list) or len(edge) != 2 or edge[0] == edge[1]:
                    raise ValueError("each conflict edge must contain two distinct nodes")
                if not set(edge) <= set(nodes):
                    raise ValueError("conflict edge references an unknown node")
                normalised = _normalise_edge(*edge)
                if normalised in seen_edges:
                    raise ValueError("duplicate conflict edge")
                seen_edges.add(normalised)
            constraints = csp.get("heterogeneous_constraints", [])
            if not isinstance(constraints, list):
                raise ValueError("heterogeneous_constraints must be a list")
            for constraint in constraints:
                self._validate_heterogeneous_frequency_constraint(
                    constraint, set(nodes), set(frequencies), allowed
                )
            return

        elements = csp.get("elements")
        candidate_sets = csp.get("candidate_sets")
        if not isinstance(elements, list) or not elements or len(elements) != len(set(elements)):
            raise ValueError("exact-cover elements must be a non-empty unique list")
        if not isinstance(candidate_sets, dict) or not candidate_sets:
            raise ValueError("candidate_sets must be a non-empty mapping")
        element_set = set(elements)
        seen_contents: set[tuple[str, ...]] = set()
        for set_id, values in candidate_sets.items():
            if not values or len(values) != len(set(values)) or not set(values) <= element_set:
                raise ValueError(f"invalid candidate set {set_id}")
            key = tuple(sorted(values))
            if key in seen_contents:
                raise ValueError("duplicate exact-cover candidate contents")
            seen_contents.add(key)
        if any(not any(e in values for values in candidate_sets.values()) for e in elements):
            raise ValueError("every element must occur in at least one candidate set")

    def validate_assignment(self, csp: dict[str, Any], assignment: dict[str, Any]) -> bool:
        try:
            self.validate_csp(csp)
        except (KeyError, TypeError, ValueError):
            return False
        if csp["family"] == "frequency_assignment":
            if set(assignment) != set(csp["nodes"]):
                return False
            if any(
                assignment[node] not in csp["allowed_frequencies"][node]
                for node in csp["nodes"]
            ):
                return False
            if not all(
                assignment[node_a] != assignment[node_b]
                for node_a, node_b in csp["conflict_edges"]
            ):
                return False
            return self._heterogeneous_frequency_constraints_hold(csp, assignment)

        if set(assignment) != set(csp["candidate_sets"]):
            return False
        if any(value not in ("SELECTED", "NOT_SELECTED") for value in assignment.values()):
            return False
        for element in csp["elements"]:
            count = sum(
                assignment[set_id] == "SELECTED" and element in values
                for set_id, values in csp["candidate_sets"].items()
            )
            if count != 1:
                return False
        return True

    def _validate_heterogeneous_frequency_constraint(
        self,
        constraint: dict[str, Any],
        nodes: set[str],
        frequencies: set[str],
        allowed: dict[str, list[str]],
    ) -> None:
        if not isinstance(constraint, dict):
            raise ValueError("each heterogeneous constraint must be an object")
        kind = constraint.get("kind")
        if kind == "forbidden_frequency_pair":
            node_a = constraint.get("node_a")
            node_b = constraint.get("node_b")
            frequency_a = constraint.get("frequency_a")
            frequency_b = constraint.get("frequency_b")
            if node_a not in nodes or node_b not in nodes or node_a == node_b:
                raise ValueError("invalid forbidden-frequency node pair")
            if frequency_a not in frequencies or frequency_b not in frequencies:
                raise ValueError("invalid forbidden-frequency value")
            if frequency_a not in allowed[node_a] or frequency_b not in allowed[node_b]:
                raise ValueError("forbidden-frequency value is outside an allowed list")
            return
        if kind == "conditional_allowed_frequencies":
            trigger_node = constraint.get("trigger_node")
            trigger_frequency = constraint.get("trigger_frequency")
            target_node = constraint.get("target_node")
            target_frequencies = constraint.get("target_frequencies")
            if (
                trigger_node not in nodes
                or target_node not in nodes
                or trigger_node == target_node
            ):
                raise ValueError("invalid conditional-frequency node pair")
            if trigger_frequency not in allowed[trigger_node]:
                raise ValueError("conditional trigger is outside its allowed list")
            if (
                not isinstance(target_frequencies, list)
                or not target_frequencies
                or len(target_frequencies) != len(set(target_frequencies))
                or not set(target_frequencies) < set(allowed[target_node])
            ):
                raise ValueError("conditional target must be a non-empty proper allowed subset")
            return
        if kind == "group_frequency_count":
            group_nodes = constraint.get("nodes")
            frequency = constraint.get("frequency")
            minimum = constraint.get("minimum")
            maximum = constraint.get("maximum")
            if (
                not isinstance(group_nodes, list)
                or len(group_nodes) < 2
                or len(group_nodes) != len(set(group_nodes))
                or not set(group_nodes) <= nodes
            ):
                raise ValueError("invalid group-frequency node list")
            if frequency not in frequencies:
                raise ValueError("invalid group-frequency value")
            if (
                not isinstance(minimum, int)
                or not isinstance(maximum, int)
                or not 0 <= minimum <= maximum <= len(group_nodes)
            ):
                raise ValueError("invalid group-frequency bounds")
            if minimum == 0 and maximum == len(group_nodes):
                raise ValueError("group-frequency count constraint is vacuous")
            return
        if kind == "pair_channel_distance":
            node_a = constraint.get("node_a")
            node_b = constraint.get("node_b")
            minimum = constraint.get("minimum")
            maximum = constraint.get("maximum")
            largest_distance = len(frequencies) - 1
            if node_a not in nodes or node_b not in nodes or node_a == node_b:
                raise ValueError("invalid channel-distance node pair")
            if (
                not isinstance(minimum, int)
                or not isinstance(maximum, int)
                or not 0 <= minimum <= maximum <= largest_distance
                or (minimum == 0 and maximum == largest_distance)
            ):
                raise ValueError("invalid or vacuous channel-distance bounds")
            return
        if kind == "group_band_count":
            self._validate_group_band_count(
                constraint,
                nodes,
                frequencies,
                node_key="nodes",
                frequency_key="frequencies",
                minimum_key="minimum",
                maximum_key="maximum",
            )
            return
        if kind == "conditional_group_band_count":
            self._validate_group_band_count(
                constraint,
                nodes,
                frequencies,
                node_key="trigger_nodes",
                frequency_key="trigger_frequencies",
                minimum_key="trigger_minimum",
                maximum_key="trigger_maximum",
            )
            self._validate_group_band_count(
                constraint,
                nodes,
                frequencies,
                node_key="target_nodes",
                frequency_key="target_frequencies",
                minimum_key="target_minimum",
                maximum_key="target_maximum",
            )
            return
        raise ValueError(f"unsupported heterogeneous frequency constraint: {kind}")

    def _validate_group_band_count(
        self,
        constraint: dict[str, Any],
        nodes: set[str],
        frequencies: set[str],
        *,
        node_key: str,
        frequency_key: str,
        minimum_key: str,
        maximum_key: str,
    ) -> None:
        group_nodes = constraint.get(node_key)
        band = constraint.get(frequency_key)
        minimum = constraint.get(minimum_key)
        maximum = constraint.get(maximum_key)
        if (
            not isinstance(group_nodes, list)
            or len(group_nodes) < 2
            or len(group_nodes) != len(set(group_nodes))
            or not set(group_nodes) <= nodes
        ):
            raise ValueError(f"invalid {node_key}")
        if (
            not isinstance(band, list)
            or not band
            or len(band) != len(set(band))
            or not set(band) < frequencies
        ):
            raise ValueError(f"invalid {frequency_key}")
        if (
            not isinstance(minimum, int)
            or not isinstance(maximum, int)
            or not 0 <= minimum <= maximum <= len(group_nodes)
            or (minimum == 0 and maximum == len(group_nodes))
        ):
            raise ValueError(f"invalid or vacuous {minimum_key}/{maximum_key}")

    def _heterogeneous_frequency_constraints_hold(
        self,
        csp: dict[str, Any],
        assignment: dict[str, str],
        *,
        partial_assignment: bool = False,
    ) -> bool:
        for constraint in csp.get("heterogeneous_constraints", []):
            kind = constraint["kind"]
            if kind == "forbidden_frequency_pair":
                node_a = constraint["node_a"]
                node_b = constraint["node_b"]
                if (
                    assignment.get(node_a) == constraint["frequency_a"]
                    and assignment.get(node_b) == constraint["frequency_b"]
                ):
                    return False
            elif kind == "conditional_allowed_frequencies":
                trigger_node = constraint["trigger_node"]
                target_node = constraint["target_node"]
                if assignment.get(trigger_node) == constraint["trigger_frequency"]:
                    if target_node in assignment and assignment[target_node] not in set(
                        constraint["target_frequencies"]
                    ):
                        return False
            elif kind == "group_frequency_count":
                group_nodes = constraint["nodes"]
                frequency = constraint["frequency"]
                count = sum(assignment.get(node) == frequency for node in group_nodes)
                unresolved = sum(node not in assignment for node in group_nodes)
                if count > constraint["maximum"]:
                    return False
                if count + unresolved < constraint["minimum"]:
                    return False
            elif kind == "pair_channel_distance":
                node_a = constraint["node_a"]
                node_b = constraint["node_b"]
                if node_a in assignment and node_b in assignment:
                    frequency_index = {
                        value: index for index, value in enumerate(csp["frequencies"])
                    }
                    distance = abs(
                        frequency_index[assignment[node_a]]
                        - frequency_index[assignment[node_b]]
                    )
                    if not constraint["minimum"] <= distance <= constraint["maximum"]:
                        return False
            elif kind == "group_band_count":
                if not self._group_band_count_possible(
                    assignment,
                    constraint["nodes"],
                    set(constraint["frequencies"]),
                    constraint["minimum"],
                    constraint["maximum"],
                ):
                    return False
            elif kind == "conditional_group_band_count":
                trigger_count, trigger_unresolved = self._group_band_count_state(
                    assignment,
                    constraint["trigger_nodes"],
                    set(constraint["trigger_frequencies"]),
                )
                trigger_possible = range(
                    trigger_count, trigger_count + trigger_unresolved + 1
                )
                trigger_values = [
                    value
                    for value in trigger_possible
                    if constraint["trigger_minimum"]
                    <= value
                    <= constraint["trigger_maximum"]
                ]
                if trigger_values and trigger_unresolved == 0:
                    if not self._group_band_count_possible(
                        assignment,
                        constraint["target_nodes"],
                        set(constraint["target_frequencies"]),
                        constraint["target_minimum"],
                        constraint["target_maximum"],
                    ):
                        return False
        if partial_assignment:
            return True
        return all(node in assignment for node in csp["nodes"])

    def _group_band_count_state(
        self,
        assignment: dict[str, str],
        group_nodes: list[str],
        band: set[str],
    ) -> tuple[int, int]:
        count = sum(assignment.get(node) in band for node in group_nodes if node in assignment)
        unresolved = sum(node not in assignment for node in group_nodes)
        return count, unresolved

    def _group_band_count_possible(
        self,
        assignment: dict[str, str],
        group_nodes: list[str],
        band: set[str],
        minimum: int,
        maximum: int,
    ) -> bool:
        count, unresolved = self._group_band_count_state(
            assignment, group_nodes, band
        )
        return count <= maximum and count + unresolved >= minimum

    def evaluate_proposition(
        self,
        csp: dict[str, Any],
        assignment: dict[str, Any],
        proposition: dict[str, Any],
    ) -> bool:
        kind = proposition["kind"]
        args = proposition["args"]
        if kind == "node_uses_frequency":
            return assignment[args["node"]] == args["frequency"]
        if kind == "nodes_same_frequency":
            return assignment[args["node_a"]] == assignment[args["node_b"]]
        if kind == "nodes_different_frequency":
            return assignment[args["node_a"]] != assignment[args["node_b"]]
        if kind == "set_selected":
            return assignment[args["set"]] == "SELECTED"
        if kind == "sets_co_selected":
            return (
                assignment[args["set_a"]] == "SELECTED"
                and assignment[args["set_b"]] == "SELECTED"
            )
        if kind == "exactly_one_selected":
            return sum(
                assignment[set_id] == "SELECTED"
                for set_id in (args["set_a"], args["set_b"])
            ) == 1
        raise ValueError(f"unsupported proposition kind: {kind}")

    def proposition_is_derived(
        self,
        csp: dict[str, Any],
        solutions: list[dict[str, Any]],
        proposition: dict[str, Any],
    ) -> bool:
        """排除显式局部约束的直接改写，保留可由完整约束系统判定的命题。"""
        kind = proposition["kind"]
        args = proposition["args"]
        if csp["family"] == "frequency_assignment":
            edges = {_normalise_edge(*edge) for edge in csp["conflict_edges"]}
            if kind in ("nodes_same_frequency", "nodes_different_frequency"):
                pair = _normalise_edge(args["node_a"], args["node_b"])
                if pair in edges:
                    return False
                allowed = csp["allowed_frequencies"]
                if not (
                    set(allowed[args["node_a"]]) & set(allowed[args["node_b"]])
                ):
                    return False
            if kind == "node_uses_frequency" and args["frequency"] not in csp[
                "allowed_frequencies"
            ][args["node"]]:
                return False
            if kind == "node_uses_frequency" and len(
                csp["allowed_frequencies"][args["node"]]
            ) == 1:
                return False
        else:
            sets = csp["candidate_sets"]
            if kind == "set_selected":
                selected_set = args["set"]
                for element in sets[selected_set]:
                    containing = [
                        set_id for set_id, values in sets.items() if element in values
                    ]
                    if containing == [selected_set]:
                        return False
            if kind == "sets_co_selected" and set(sets[args["set_a"]]) & set(
                sets[args["set_b"]]
            ):
                return False
            if kind == "exactly_one_selected":
                target_pair = {args["set_a"], args["set_b"]}
                for element in csp["elements"]:
                    containing = {
                        set_id for set_id, values in sets.items() if element in values
                    }
                    if containing == target_pair:
                        return False

        return bool(solutions)

    def classify_proposition(
        self,
        csp: dict[str, Any],
        solutions: list[dict[str, Any]],
        proposition: dict[str, Any],
    ) -> dict[str, Any]:
        if not solutions:
            raise ValueError("modal classification requires a non-empty complete solution set")
        support = sum(self.evaluate_proposition(csp, row, proposition) for row in solutions)
        modal_class = (
            "necessary"
            if support == len(solutions)
            else "impossible"
            if support == 0
            else "contingent"
        )
        return {
            "support_count": support,
            "complement_support_count": len(solutions) - support,
            "modal_class": modal_class,
        }

    def frequency_witness_search_metrics(
        self,
        csp: dict[str, Any],
        proposition: dict[str, Any],
    ) -> dict[str, Any]:
        """测量频率 WITNESS 在目标条件下是否仍需实质分支与回溯。"""
        if csp.get("family") != "frequency_assignment":
            raise ValueError("frequency search metrics require a frequency CSP")

        domains = {
            node: set(csp["allowed_frequencies"][node]) for node in csp["nodes"]
        }
        unequal_pairs = {
            _normalise_edge(*edge) for edge in csp["conflict_edges"]
        }
        equal_pairs: set[tuple[str, str]] = set()
        kind = proposition["kind"]
        args = proposition["args"]
        if kind == "node_uses_frequency":
            domains[args["node"]] &= {args["frequency"]}
        elif kind == "nodes_same_frequency":
            equal_pairs.add(_normalise_edge(args["node_a"], args["node_b"]))
        elif kind == "nodes_different_frequency":
            unequal_pairs.add(_normalise_edge(args["node_a"], args["node_b"]))
        else:
            raise ValueError(f"unsupported frequency proposition kind: {kind}")

        def propagate(current: dict[str, set[str]]) -> bool:
            changed = True
            while changed:
                changed = False
                if any(not values for values in current.values()):
                    return False
                for node_a, node_b in equal_pairs:
                    common = current[node_a] & current[node_b]
                    if not common:
                        return False
                    if common != current[node_a]:
                        current[node_a] = set(common)
                        changed = True
                    if common != current[node_b]:
                        current[node_b] = set(common)
                        changed = True
                for node_a, node_b in unequal_pairs:
                    if len(current[node_a]) == 1:
                        frequency = next(iter(current[node_a]))
                        if frequency in current[node_b]:
                            current[node_b].remove(frequency)
                            changed = True
                    if len(current[node_b]) == 1:
                        frequency = next(iter(current[node_b]))
                        if frequency in current[node_a]:
                            current[node_a].remove(frequency)
                            changed = True
            return all(current.values())

        target_consistent = propagate(domains)
        residual_variables = sum(len(values) > 1 for values in domains.values())
        counters = {"branch_decisions": 0, "backtracks": 0, "search_nodes": 0}

        def visit(current: dict[str, set[str]]) -> bool:
            if not propagate(current):
                return False
            unresolved = [node for node, values in current.items() if len(values) > 1]
            if not unresolved:
                assignment = {node: next(iter(current[node])) for node in csp["nodes"]}
                return self.validate_assignment(csp, assignment) and self.evaluate_proposition(
                    csp, assignment, proposition
                )
            node = min(unresolved, key=lambda item: (len(current[item]), item))
            counters["branch_decisions"] += 1
            for frequency in sorted(current[node]):
                counters["search_nodes"] += 1
                child = {item: set(values) for item, values in current.items()}
                child[node] = {frequency}
                if visit(child):
                    return True
                counters["backtracks"] += 1
            return False

        found = target_consistent and visit(
            {node: set(values) for node, values in domains.items()}
        )
        return {
            "target_consistent": target_consistent,
            "target_residual_variables": residual_variables,
            "target_forced_variables": len(csp["nodes"]) - residual_variables,
            "target_residual_domain_size": sum(len(values) for values in domains.values()),
            "search_branch_decisions": counters["branch_decisions"],
            "search_backtracks": counters["backtracks"],
            "search_nodes": counters["search_nodes"],
            "first_witness_found": found,
        }

    def proposition_pool(
        self, csp: dict[str, Any], solutions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        pool: list[dict[str, Any]] = []
        if csp["family"] == "frequency_assignment":
            for node in csp["nodes"]:
                for frequency in csp["allowed_frequencies"][node]:
                    pool.append(
                        {
                            "kind": "node_uses_frequency",
                            "args": {"node": node, "frequency": frequency},
                        }
                    )
            for index, node_a in enumerate(csp["nodes"]):
                for node_b in csp["nodes"][index + 1 :]:
                    for kind in ("nodes_same_frequency", "nodes_different_frequency"):
                        pool.append(
                            {"kind": kind, "args": {"node_a": node_a, "node_b": node_b}}
                        )
        else:
            set_ids = list(csp["candidate_sets"])
            for set_id in set_ids:
                pool.append({"kind": "set_selected", "args": {"set": set_id}})
            for index, set_a in enumerate(set_ids):
                for set_b in set_ids[index + 1 :]:
                    for kind in ("sets_co_selected", "exactly_one_selected"):
                        pool.append(
                            {"kind": kind, "args": {"set_a": set_a, "set_b": set_b}}
                        )
        return [item for item in pool if self.proposition_is_derived(csp, solutions, item)]

    def select_proposition(
        self, csp: dict[str, Any], solutions: list[dict[str, Any]]
    ) -> dict[str, Any]:
        pool = self.proposition_pool(csp, solutions)
        pool = [
            item
            for item in pool
            if self.classify_proposition(csp, solutions, item)["modal_class"]
            == "contingent"
        ]
        if not pool:
            raise ValueError("no non-trivial contingent proposition survived the derived gate")

        def rank(item: dict[str, Any]) -> tuple[Any, ...]:
            support = sum(self.evaluate_proposition(csp, row, item) for row in solutions)
            return (abs(2 * support - len(solutions)), _canonical_json(item))

        selected = min(pool, key=rank)
        selected = json.loads(json.dumps(selected, ensure_ascii=False))
        selected["text_zh"] = self.proposition_text_zh(selected)
        return selected

    def proposition_text_zh(self, proposition: dict[str, Any]) -> str:
        kind = proposition["kind"]
        args = proposition["args"]
        templates = {
            "node_uses_frequency": f"设备 {args.get('node')} 使用频率 {args.get('frequency')}",
            "nodes_same_frequency": f"设备 {args.get('node_a')} 与 {args.get('node_b')} 使用相同频率",
            "nodes_different_frequency": f"设备 {args.get('node_a')} 与 {args.get('node_b')} 使用不同频率",
            "set_selected": f"候选集合 {args.get('set')} 被选中",
            "sets_co_selected": f"候选集合 {args.get('set_a')} 与 {args.get('set_b')} 同时被选中",
            "exactly_one_selected": f"候选集合 {args.get('set_a')} 与 {args.get('set_b')} 中恰好一个被选中",
        }
        if kind not in templates:
            raise ValueError(f"unsupported proposition kind: {kind}")
        return templates[kind]

    def _frequency_count_text(
        self, minimum: int, maximum: int, group_size: int
    ) -> str:
        if minimum == maximum:
            return f"恰好为 {minimum} 台"
        if minimum == 0:
            return f"至多为 {maximum} 台"
        if maximum == group_size:
            return f"至少为 {minimum} 台"
        return f"必须在 {minimum} 至 {maximum} 台之间（含端点）"

    def render_prompt(
        self,
        csp: dict[str, Any],
        proposition: dict[str, Any],
        prompt_contract: str | None = None,
    ) -> str:
        effective_contract = prompt_contract or _current_record_contract(csp["family"])[1]
        if csp["family"] == "frequency_assignment":
            lines = [
                "# WITNESS 任务",
                "",
                "## 场景",
                f"可用频率：{', '.join(csp['frequencies'])}",
                "每台设备必须从自己的允许列表中选择且只选择一个频率。",
                "",
                "设备及允许频率：",
            ]
            lines.extend(
                f"- {node}: {', '.join(csp['allowed_frequencies'][node])}"
                for node in csp["nodes"]
            )
            lines.extend(["", "## 公开约束"])
            lines.extend(
                f"[C{index}] 设备 {node_a} 与 {node_b} 不得使用相同频率。"
                for index, (node_a, node_b) in enumerate(csp["conflict_edges"], start=1)
            )
            next_index = len(csp["conflict_edges"]) + 1
            for offset, constraint in enumerate(
                csp.get("heterogeneous_constraints", [])
            ):
                index = next_index + offset
                kind = constraint["kind"]
                if kind == "forbidden_frequency_pair":
                    text = (
                        f"设备 {constraint['node_a']} 使用 {constraint['frequency_a']} 与设备 "
                        f"{constraint['node_b']} 使用 {constraint['frequency_b']} 不得同时成立。"
                    )
                elif kind == "conditional_allowed_frequencies":
                    values = "、".join(constraint["target_frequencies"])
                    if len(constraint["target_frequencies"]) == 1:
                        required_text = f"必须使用 {values}。"
                    else:
                        required_text = f"必须使用 {values} 中的一个频率。"
                    text = (
                        f"如果设备 {constraint['trigger_node']} 使用 "
                        f"{constraint['trigger_frequency']}，则设备 {constraint['target_node']} "
                        f"{required_text}"
                    )
                elif kind == "group_frequency_count":
                    values = "、".join(constraint["nodes"])
                    minimum = constraint["minimum"]
                    maximum = constraint["maximum"]
                    count_text = self._frequency_count_text(
                        minimum, maximum, len(constraint["nodes"])
                    )
                    text = (
                        f"在设备 {values} 中，使用 {constraint['frequency']} 的设备数量"
                        f"{count_text}。"
                    )
                elif kind == "pair_channel_distance":
                    minimum = constraint["minimum"]
                    maximum = constraint["maximum"]
                    if minimum == maximum:
                        relation = f"恰好相差 {minimum}"
                    elif minimum == 0:
                        relation = f"最多相差 {maximum}"
                    elif maximum == len(csp["frequencies"]) - 1:
                        relation = f"至少相差 {minimum}"
                    else:
                        relation = f"相差 {minimum} 至 {maximum}（含端点）"
                    text = (
                        f"频率按 F1 至 F{len(csp['frequencies'])} 的顺序编号；设备 "
                        f"{constraint['node_a']} 与 {constraint['node_b']} 的频率编号"
                        f"{relation}。"
                    )
                elif kind == "group_band_count":
                    values = "、".join(constraint["nodes"])
                    band = "、".join(constraint["frequencies"])
                    count_text = self._frequency_count_text(
                        constraint["minimum"],
                        constraint["maximum"],
                        len(constraint["nodes"]),
                    )
                    text = (
                        f"在设备 {values} 中，使用频段 {{{band}}} 内频率的"
                        f"设备数量{count_text}。"
                    )
                else:
                    trigger_nodes = "、".join(constraint["trigger_nodes"])
                    trigger_band = "、".join(constraint["trigger_frequencies"])
                    target_nodes = "、".join(constraint["target_nodes"])
                    target_band = "、".join(constraint["target_frequencies"])
                    trigger_count = self._frequency_count_text(
                        constraint["trigger_minimum"],
                        constraint["trigger_maximum"],
                        len(constraint["trigger_nodes"]),
                    )
                    target_count = self._frequency_count_text(
                        constraint["target_minimum"],
                        constraint["target_maximum"],
                        len(constraint["target_nodes"]),
                    )
                    text = (
                        f"如果在设备 {trigger_nodes} 中，使用频段 "
                        f"{{{trigger_band}}} 内频率的设备数量{trigger_count}，"
                        f"那么在设备 {target_nodes} 中，使用频段 "
                        f"{{{target_band}}} 内频率的设备数量{target_count}。"
                    )
                lines.append(f"[C{index}] {text}")
            schema = {node: "频率编号" for node in csp["nodes"]}
            if effective_contract == PROMPT_CONTRACT:
                requirement_lines = [
                    "若存在满足全部公开约束且目标命题成立的完整赋值，给出一份完整赋值；否则回答不存在。",
                    "回答不存在时，assignment 必须为 null。",
                    "不得调用或借助代码执行环境、程序、网页搜索或外部求解器。可以自行使用分支、反证、回溯或搜索。",
                    "",
                    "只输出一个 JSON 对象。回答存在时，assignment 的键必须恰好是全部设备编号，值必须是频率编号。",
                ]
                response_schema: dict[str, Any] = {
                    "answer": "存在或不存在",
                    "assignment": schema,
                }
            elif effective_contract == LEGACY_PROMPT_CONTRACT:
                requirement_lines = [
                    "请给出一个满足全部约束且使目标命题成立的完整赋值。",
                    "不得调用或借助代码执行环境、程序、网页搜索或外部求解器。可以自行使用分支、反证、回溯或搜索。",
                    "",
                    "只输出一个 JSON 对象，键必须恰好是全部设备编号，值必须是频率编号。",
                ]
                response_schema = schema
            else:
                raise ValueError(f"unsupported prompt contract: {effective_contract}")
            lines.extend(
                [
                    "",
                    "## 目标命题",
                    proposition["text_zh"],
                    "",
                    "## 要求",
                    *requirement_lines,
                    "回复的第一个字符必须是 {，最后一个字符必须是 }。不得添加 Markdown 代码块、json 代码围栏、解释、rationale 或其他前后缀。",
                    "JSON 结构示例（只说明字段结构）：",
                    json.dumps(response_schema, ensure_ascii=False),
                ]
            )
            return "\n".join(lines) + "\n"

        if effective_contract != LEGACY_PROMPT_CONTRACT:
            raise ValueError(f"unsupported exact-cover prompt contract: {effective_contract}")

        lines = [
            "# WITNESS 任务",
            "",
            "## 场景",
            "请为每个候选集合决定是否选中。",
            "",
            f"底层元素：{', '.join(csp['elements'])}",
            "",
            "## 公开约束",
            "[C1] 每个底层元素都必须恰好被一个被选中的候选集合覆盖。",
        ]
        lines.extend(
            f"[C{index}] 候选集合 {set_id} 包含元素 {{{', '.join(values)}}}。"
            for index, (set_id, values) in enumerate(
                csp["candidate_sets"].items(), start=2
            )
        )
        schema = {set_id: "SELECTED 或 NOT_SELECTED" for set_id in csp["candidate_sets"]}
        lines.extend(
            [
                "",
                "## 目标命题",
                proposition["text_zh"],
                "",
                "## 要求",
                "请给出一个满足全部约束且使目标命题成立的完整赋值。",
                "不得调用或借助代码执行环境、程序、网页搜索或外部求解器。可以自行使用分支、反证、回溯或搜索。",
                "",
                "只输出一个 JSON 对象，键必须恰好是全部候选集合编号，值只能是 SELECTED 或 NOT_SELECTED。",
                "回复的第一个字符必须是 {，最后一个字符必须是 }。不得添加 Markdown 代码块、json 代码围栏、解释、rationale 或其他前后缀。",
                "JSON 结构示例（只说明字段结构）：",
                json.dumps(schema, ensure_ascii=False),
            ]
        )
        return "\n".join(lines) + "\n"

    def build_record(
        self,
        *,
        csp_id: str,
        stratum: str,
        seed: int,
        csp: dict[str, Any],
        generation_parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        solutions = self.enumerate_solutions(csp)
        if not solutions:
            raise ValueError("a dataset CSP must have a non-empty complete solution set")
        proposition = self.select_proposition(csp, solutions)
        support = sum(self.evaluate_proposition(csp, row, proposition) for row in solutions)
        difficulty_metrics: dict[str, Any] = {}
        parameters = generation_parameters or {}
        if csp["family"] == "frequency_assignment":
            difficulty_metrics = self.frequency_witness_search_metrics(csp, proposition)
            thresholds = {
                "target_residual_variables": int(
                    parameters.get("min_target_residual_variables", 0)
                ),
                "search_branch_decisions": int(
                    parameters.get("min_search_branch_decisions", 0)
                ),
                "search_backtracks": int(parameters.get("min_search_backtracks", 0)),
                "search_nodes": int(parameters.get("min_search_nodes", 0)),
            }
            if not difficulty_metrics["first_witness_found"] or any(
                difficulty_metrics[field] < minimum
                for field, minimum in thresholds.items()
            ):
                raise ValueError(
                    "target-conditioned propagation/search hardness gate failed: "
                    + _canonical_json(
                        {"metrics": difficulty_metrics, "minimums": thresholds}
                    )
                )
        generator_version, prompt_contract = _current_record_contract(csp["family"])
        prompt = self.render_prompt(csp, proposition, prompt_contract)
        record = {
            "schema_version": SCHEMA_VERSION,
            "generator_version": generator_version,
            "prompt_contract": prompt_contract,
            "development_only": True,
            "formal_exclusion_reason": "displayed_or_generated_during_development",
            "csp_id": csp_id,
            "family": csp["family"],
            "stratum": stratum,
            "seed": seed,
            "generation_parameters": parameters,
            "csp": csp,
            "solutions": solutions,
            "solution_count": len(solutions),
            "proposition": proposition,
            "support_count": support,
            "complement_support_count": len(solutions) - support,
            "modal_class": "contingent",
            "development_task": "WITNESS",
            "prompt_zh": prompt,
        }
        if difficulty_metrics:
            record["difficulty_metrics"] = difficulty_metrics
        return record

    def generate_candidate(
        self,
        *,
        family: str,
        stratum: str,
        seed: int,
        parameters: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        if family not in FAMILIES:
            raise ValueError(f"unsupported family: {family}")
        rng = random.Random(seed)
        scans: list[dict[str, Any]] = []
        maximum = int(parameters.get("max_attempts", 5000))
        minimum_solutions = int(parameters["solution_count_min"])
        maximum_solutions = int(parameters["solution_count_max"])
        for attempt in range(1, maximum + 1):
            candidate_seed = rng.randrange(1, 2**63)
            if family == "frequency_assignment":
                csp = self._generate_frequency_candidate(candidate_seed, parameters)
            else:
                csp = self._generate_exact_cover_candidate(candidate_seed, parameters)
            if csp is None:
                scans.append({"attempt": attempt, "candidate_seed": candidate_seed, "status": "structural_reject"})
                continue
            bounded = self.enumerate_solutions(csp, limit=maximum_solutions + 1)
            solution_count = len(bounded)
            if solution_count < minimum_solutions or solution_count > maximum_solutions:
                scans.append(
                    {
                        "attempt": attempt,
                        "candidate_seed": candidate_seed,
                        "status": "solution_count_reject",
                        "bounded_solution_count": solution_count,
                    }
                )
                continue
            # 接纳前必须无上限地重新完整枚举，并确认派生命题池非空。
            complete = self.enumerate_solutions(csp)
            try:
                record = self.build_record(
                    csp_id=f"dev_{family}_{stratum}_{seed}",
                    stratum=stratum,
                    seed=candidate_seed,
                    csp=csp,
                    generation_parameters=parameters,
                )
            except ValueError as exc:
                status = (
                    "difficulty_reject"
                    if "hardness gate failed" in str(exc)
                    else "proposition_reject"
                )
                scans.append(
                    {
                        "attempt": attempt,
                        "candidate_seed": candidate_seed,
                        "status": status,
                    }
                )
                continue
            scans.append(
                {
                    "attempt": attempt,
                    "candidate_seed": candidate_seed,
                    "status": "accepted",
                    "complete_solution_count": len(complete),
                    "difficulty_metrics": record.get("difficulty_metrics", {}),
                }
            )
            return record, scans
        raise RuntimeError(f"no acceptable {family}/{stratum} candidate after {maximum} attempts")

    def _generate_frequency_candidate(
        self, seed: int, parameters: dict[str, Any]
    ) -> dict[str, Any] | None:
        rng = random.Random(seed)
        node_count = int(parameters["node_count"])
        frequency_count = int(parameters["frequency_count"])
        edge_probability = float(parameters["edge_probability"])
        list_size_min = int(parameters.get("list_size_min", 2))
        list_size_max = int(parameters.get("list_size_max", min(3, frequency_count)))
        nodes = [f"D{index:02d}" for index in range(1, node_count + 1)]
        frequencies = [f"F{index}" for index in range(1, frequency_count + 1)]
        planted = {node: rng.choice(frequencies) for node in nodes}
        if len(set(planted.values())) < min(3, frequency_count):
            return None
        allowed: dict[str, list[str]] = {}
        for node in nodes:
            size = rng.randint(list_size_min, list_size_max)
            others = [value for value in frequencies if value != planted[node]]
            chosen = [planted[node], *rng.sample(others, size - 1)]
            allowed[node] = sorted(chosen)

        edges: set[tuple[str, str]] = set()
        connected = [nodes[0]]
        remaining = nodes[1:]
        rng.shuffle(remaining)
        for node in remaining:
            choices = [other for other in connected if planted[other] != planted[node]]
            if not choices:
                return None
            edges.add(_normalise_edge(node, rng.choice(choices)))
            connected.append(node)
        for index, node_a in enumerate(nodes):
            for node_b in nodes[index + 1 :]:
                if planted[node_a] != planted[node_b] and rng.random() < edge_probability:
                    edges.add(_normalise_edge(node_a, node_b))
        return {
            "family": "frequency_assignment",
            "nodes": nodes,
            "frequencies": frequencies,
            "allowed_frequencies": allowed,
            "conflict_edges": [list(edge) for edge in sorted(edges)],
        }

    def _generate_exact_cover_candidate(
        self, seed: int, parameters: dict[str, Any]
    ) -> dict[str, Any] | None:
        rng = random.Random(seed)
        element_count = int(parameters["element_count"])
        block_size = int(parameters["block_size"])
        partition_count = int(parameters["partition_count"])
        if element_count % block_size:
            raise ValueError("element_count must be divisible by block_size")
        elements = [f"E{index:02d}" for index in range(1, element_count + 1)]
        content_rows: list[tuple[str, ...]] = []
        seen: set[tuple[str, ...]] = set()
        for _ in range(partition_count):
            shuffled = elements[:]
            rng.shuffle(shuffled)
            partition: list[tuple[str, ...]] = []
            for start in range(0, element_count, block_size):
                block = tuple(sorted(shuffled[start : start + block_size]))
                if block in seen:
                    return None
                partition.append(block)
            seen.update(partition)
            content_rows.extend(partition)
        candidate_sets = {
            f"S{index:02d}": list(values)
            for index, values in enumerate(content_rows, start=1)
        }
        if not self._exact_cover_incidence_connected(elements, candidate_sets):
            return None
        return {
            "family": "exact_cover",
            "elements": elements,
            "candidate_sets": candidate_sets,
        }

    def _exact_cover_incidence_connected(
        self, elements: list[str], candidate_sets: dict[str, list[str]]
    ) -> bool:
        graph: dict[str, set[str]] = {element: set() for element in elements}
        graph.update({set_id: set() for set_id in candidate_sets})
        for set_id, values in candidate_sets.items():
            for element in values:
                graph[set_id].add(element)
                graph[element].add(set_id)
        start = elements[0]
        reached = {start}
        stack = [start]
        while stack:
            node = stack.pop()
            for other in graph[node] - reached:
                reached.add(other)
                stack.append(other)
        return len(reached) == len(graph)


class Oracle:
    """主流水线末端的全量一致性检查；独立第二实现由 GoldAuditor 承担。"""

    def __init__(self) -> None:
        self.generator = Generator()

    def audit_record(self, record: dict[str, Any]) -> dict[str, Any]:
        errors: list[str] = []
        generator_version = record.get("generator_version")
        generation_parameters = record.get("generation_parameters", {})
        if not isinstance(generation_parameters, dict):
            generation_parameters = {}
            errors.append("invalid_generation_parameters")
        if generator_version not in LEGACY_GENERATOR_VERSIONS | {GENERATOR_VERSION}:
            errors.append("unsupported_generator_version")
        elif generator_version == "mssq_csp_generator_v1":
            if "prompt_contract" in record or "difficulty_metrics" in record:
                errors.append("generator_version_shape_mismatch")
        elif generator_version == "mssq_csp_generator_v2":
            if record.get("prompt_contract") != LEGACY_PROMPT_CONTRACT:
                errors.append("prompt_contract_mismatch")
            if "difficulty_metrics" in record or any(
                key in generation_parameters for key in DIFFICULTY_PARAMETER_KEYS
            ):
                errors.append("generator_version_shape_mismatch")
        elif generator_version == "mssq_csp_generator_v3":
            if record.get("prompt_contract") != LEGACY_PROMPT_CONTRACT:
                errors.append("prompt_contract_mismatch")
        else:
            if record.get("prompt_contract") != PROMPT_CONTRACT:
                errors.append("prompt_contract_mismatch")
        csp = record.get("csp")
        if not isinstance(csp, dict):
            return {"passed": False, "errors": ["missing_csp"]}
        if generator_version in {"mssq_csp_generator_v3", GENERATOR_VERSION} and csp.get(
            "family"
        ) != "frequency_assignment":
            errors.append("generator_version_shape_mismatch")
        try:
            actual = self.generator.enumerate_solutions(csp)
        except (KeyError, TypeError, ValueError) as exc:
            return {"passed": False, "errors": [f"invalid_csp:{exc}"]}
        stored = record.get("solutions")
        try:
            stored_normalised = (
                _normalise_solutions(csp, stored) if isinstance(stored, list) else None
            )
        except (KeyError, TypeError):
            stored_normalised = None
        if stored_normalised is None or _canonical_json(stored_normalised) != _canonical_json(actual):
            errors.append("solution_set_mismatch")
        if record.get("solution_count") != len(actual):
            errors.append("solution_count_mismatch")
        if not all(self.generator.validate_assignment(csp, row) for row in actual):
            errors.append("invalid_enumerated_assignment")
        proposition = record.get("proposition")
        if not isinstance(proposition, dict):
            errors.append("missing_proposition")
        else:
            try:
                expected_text = self.generator.proposition_text_zh(proposition)
            except (KeyError, TypeError, ValueError):
                expected_text = None
            if proposition.get("text_zh") != expected_text:
                errors.append("proposition_text_mismatch")
            support = sum(
                self.generator.evaluate_proposition(csp, row, proposition) for row in actual
            )
            if support != record.get("support_count"):
                errors.append("support_count_mismatch")
            if len(actual) - support != record.get("complement_support_count"):
                errors.append("complement_support_count_mismatch")
            if not 0 < support < len(actual) or record.get("modal_class") != "contingent":
                errors.append("modal_class_mismatch")
            if not self.generator.proposition_is_derived(csp, actual, proposition):
                errors.append("derived_gate_failed")
            if (
                csp["family"] == "frequency_assignment"
                and record.get("generator_version")
                in {"mssq_csp_generator_v3", GENERATOR_VERSION}
            ):
                expected_metrics = self.generator.frequency_witness_search_metrics(
                    csp, proposition
                )
                if _canonical_json(record.get("difficulty_metrics")) != _canonical_json(
                    expected_metrics
                ):
                    errors.append("difficulty_metrics_mismatch")
                parameters = generation_parameters
                thresholds = {
                    "target_residual_variables": int(
                        parameters.get("min_target_residual_variables", 0)
                    ),
                    "search_branch_decisions": int(
                        parameters.get("min_search_branch_decisions", 0)
                    ),
                    "search_backtracks": int(parameters.get("min_search_backtracks", 0)),
                    "search_nodes": int(parameters.get("min_search_nodes", 0)),
                }
                if not expected_metrics["first_witness_found"] or any(
                    expected_metrics[field] < minimum
                    for field, minimum in thresholds.items()
                ):
                    errors.append("difficulty_gate_failed")
            canonical_proposition = dict(proposition)
            if expected_text is not None:
                canonical_proposition["text_zh"] = expected_text
            expected_contract = (
                PROMPT_CONTRACT
                if generator_version == GENERATOR_VERSION
                and csp["family"] == "frequency_assignment"
                else LEGACY_PROMPT_CONTRACT
            )
            expected_prompt = self.generator.render_prompt(
                csp, canonical_proposition, expected_contract
            )
            if record.get("prompt_zh") != expected_prompt:
                errors.append("prompt_mismatch")
        prompt = str(record.get("prompt_zh", ""))
        forbidden = ("support_count", "complement_support_count", "正确答案", "Gold")
        if any(token in prompt for token in forbidden):
            errors.append("public_prompt_leakage")
        return {
            "passed": not errors,
            "errors": errors,
            "audited_solution_count": len(actual),
            "audited_csp_id": record.get("csp_id"),
        }


def _write_generation_output(
    output_dir: Path,
    record: dict[str, Any],
    scans: list[dict[str, Any]],
) -> None:
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output_dir}")
    output_dir.mkdir(parents=True)
    record_path = output_dir / "dataset.json"
    scan_path = output_dir / "candidate_scans.json"
    prompt_path = output_dir / "prompt_zh.md"
    oracle_path = output_dir / "oracle_report.json"
    _write_json(record_path, record)
    _write_json(scan_path, scans)
    prompt_path.write_text(record["prompt_zh"], encoding="utf-8", newline="\n")
    oracle_report = Oracle().audit_record(record)
    _write_json(oracle_path, oracle_report)
    if not oracle_report["passed"]:
        raise RuntimeError(f"Oracle rejected generated record: {oracle_report['errors']}")
    files = [record_path, scan_path, prompt_path, oracle_path]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generator_version": record["generator_version"],
        "prompt_contract": record["prompt_contract"],
        "development_only": True,
        "files": {path.name: _sha256(path) for path in files},
    }
    _write_json(output_dir / "manifest.sha256.json", manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--family", choices=FAMILIES, required=True)
    parser.add_argument("--stratum", choices=("sparse", "richer", "development"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--confirm-development-generation", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    parameters = config["families"][args.family][args.stratum]
    seed = int(config["development_seed"]) + int(parameters.get("seed_offset", 0))
    if not args.confirm_development_generation:
        print(
            json.dumps(
                {
                    "preflight": True,
                    "family": args.family,
                    "stratum": args.stratum,
                    "seed": seed,
                    "parameters": parameters,
                    "output_dir": str(args.output_dir),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    record, scans = Generator().generate_candidate(
        family=args.family,
        stratum=args.stratum,
        seed=seed,
        parameters=parameters,
    )
    _write_generation_output(args.output_dir, record, scans)
    print(_canonical_json({"status": "completed", "output_dir": str(args.output_dir)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
