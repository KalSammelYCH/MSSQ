"""排程纯验证函数：输入约束、命题和赋值，返回合法性；沿用原实现。"""
from __future__ import annotations

PERSON_NAMES = [chr(code) for code in range(ord("A"), ord("Z") + 1)]


def get_day_for_slot(slot_idx: int, profile: dict) -> int:
    """返回零基场次所属的一基天编号。"""
    return slot_idx // len(profile["periods"]) + 1


def get_period_for_slot(slot_idx: int, profile: dict) -> int:
    """返回零基场次所属的零基时段类型。"""
    return slot_idx % len(profile["periods"])


def get_day_slots(day: int, profile: dict) -> list[int]:
    """返回一基天编号对应的全部零基场次。"""
    period_count = len(profile["periods"])
    start = (day - 1) * period_count
    return list(range(start, start + period_count))


def get_period_slots(period_idx: int, profile: dict) -> list[int]:
    """返回某零基时段类型跨所有天对应的场次。"""
    period_count = len(profile["periods"])
    slot_count = profile["days"] * period_count
    return [slot for slot in range(slot_count) if slot % period_count == period_idx]


def _expected_people(profile: dict) -> list[str]:
    people_count = profile["people_count"]
    if not isinstance(people_count, int) or people_count < 1 or people_count > len(PERSON_NAMES):
        raise ValueError("people_count 必须是 1 到 26 之间的整数")
    return PERSON_NAMES[:people_count]


def _schedule_structure_is_safe(profile: dict, assignment: dict[str, int]) -> bool:
    """检查约束求值所需的人员键和场次值是否完整、安全。"""
    expected_people = _expected_people(profile)
    if set(assignment) != set(expected_people):
        return False

    slot_count = profile["days"] * len(profile["periods"])
    return not any(
        not isinstance(slot, int) or isinstance(slot, bool) or not 0 <= slot < slot_count
        for slot in assignment.values()
    )


def _base_capacity_is_valid(profile: dict, assignment: dict[str, int]) -> bool:
    """在结构安全的前提下检查固定或可变场次容量。"""
    slot_count = profile["days"] * len(profile["periods"])

    slot_counts = [0] * slot_count
    for slot in assignment.values():
        slot_counts[slot] += 1

    capacity = profile.get("slot_capacity")
    if not isinstance(capacity, dict):
        return False
    if capacity.get("mode") == "fixed":
        return all(count == capacity.get("value") for count in slot_counts)
    if capacity.get("mode") == "variable":
        minimum = capacity.get("min")
        maximum = capacity.get("max")
        return all(minimum <= count <= maximum for count in slot_counts)
    return False


def check_schedule(
    profile: dict,
    constraints: list[dict],
    assignment: dict[str, int],
) -> tuple[bool, list[int]]:
    """返回整体有效性以及未满足约束的零基索引。"""
    if not _schedule_structure_is_safe(profile, assignment):
        return False, []
    base_capacity_valid = _base_capacity_is_valid(profile, assignment)
    violated = [
        index
        for index, constraint in enumerate(constraints)
        if not check_constraint(constraint, assignment, profile)
    ]
    return base_capacity_valid and not violated, violated


def check_constraint(
    constraint: dict,
    assignment: dict[str, int],
    profile: dict,
) -> bool:
    """用纯 Python 语义验证五类排程约束，不调用 MILPBuilder。"""
    template_type = constraint["template_type"]
    params = constraint["params"]

    if template_type == "count_day_tod":
        if "day" in params:
            target_slots = set(get_day_slots(params["day"], profile))
        else:
            target_slots = set(get_period_slots(params["period_idx"], profile))
        actual = sum(assignment[person] in target_slots for person in params["set"])
        return actual == params["k_value"]

    if template_type == "count_order":
        members = params["set"]
        subtype = params["subtype"]
        pivot_x_slot = assignment[params["pivot_x"]]
        if subtype == "between":
            pivot_y_slot = assignment[params["pivot_y"]]
            actual = sum(
                pivot_x_slot < assignment[person] < pivot_y_slot
                for person in members
            )
        elif subtype == "earlier":
            actual = sum(assignment[person] < pivot_x_slot for person in members)
        elif subtype == "later":
            actual = sum(assignment[person] > pivot_x_slot for person in members)
        elif subtype == "not_earlier":
            actual = sum(assignment[person] >= pivot_x_slot for person in members)
        elif subtype == "not_later":
            actual = sum(assignment[person] <= pivot_x_slot for person in members)
        else:
            raise ValueError(f"不支持的 count_order 子类型: {subtype}")
        return actual == params["k_value"]

    if template_type == "simple_relation":
        slot_x = assignment[params["person_x"]]
        slot_y = assignment[params["person_y"]]
        subtype = params["subtype"]
        if subtype == "before":
            return slot_x < slot_y
        if subtype == "not_adjacent":
            return abs(slot_x - slot_y) >= 2
        if subtype == "separated":
            return abs(slot_x - slot_y) - 1 >= params.get("gap", 1)
        if subtype == "not_same_day":
            return get_day_for_slot(slot_x, profile) != get_day_for_slot(slot_y, profile)
        if subtype == "adjacent_day":
            return abs(
                get_day_for_slot(slot_x, profile) - get_day_for_slot(slot_y, profile)
            ) == 1
        if subtype == "not_same_period":
            return get_period_for_slot(slot_x, profile) != get_period_for_slot(slot_y, profile)
        raise ValueError(f"不支持的 simple_relation 子类型: {subtype}")

    if template_type == "direct_same_session":
        return assignment[params["person_x"]] == assignment[params["person_y"]]

    if template_type == "conditional":
        condition_type = params["cond_type"]
        if condition_type == "on_day":
            condition_true = (
                get_day_for_slot(assignment[params["person"]], profile) == params["day"]
            )
        elif condition_type == "on_period":
            condition_true = (
                get_period_for_slot(assignment[params["person"]], profile)
                == params["period_idx"]
            )
        elif condition_type == "before_y":
            condition_true = (
                assignment[params["person_x"]] < assignment[params["person_y"]]
            )
        else:
            raise ValueError(f"不支持的 conditional 条件类型: {condition_type}")

        if not condition_true:
            return True

        consequence_type = params["cons_cons_type"]
        if consequence_type == "not_adjacent":
            slot_y = assignment[params["cons_person_y"]]
            slot_z = assignment[params["cons_person_z"]]
            return abs(slot_y - slot_z) >= 2
        if consequence_type == "not_same_day":
            slot_y = assignment[params["cons_person_y"]]
            slot_z = assignment[params["cons_person_z"]]
            return get_day_for_slot(slot_y, profile) != get_day_for_slot(slot_z, profile)
        if consequence_type == "same_period_count":
            target_slots = set(get_period_slots(params["cons_period_idx"], profile))
            actual = sum(
                assignment[person] in target_slots for person in params["cons_set"]
            )
            return actual == params["cons_k_value"]
        raise ValueError(f"不支持的 conditional 后件类型: {consequence_type}")

    raise ValueError(f"不支持的约束模板: {template_type}")


def evaluate_proposition(
    proposition: dict,
    assignment: dict[str, int],
    profile: dict,
) -> bool:
    """用纯 Python 判断一个完整赋值是否满足首阶段原子命题。"""
    proposition_type = proposition["type"]
    if proposition_type == "person_in_slot":
        return assignment[proposition["person"]] == proposition["slot"]
    if proposition_type == "person_in_day":
        return (
            get_day_for_slot(assignment[proposition["person"]], profile)
            == proposition["day"]
        )
    if proposition_type == "person_in_period":
        return (
            get_period_for_slot(assignment[proposition["person"]], profile)
            == proposition["period_idx"]
        )

    if proposition_type in {
        "same_session",
        "same_day",
        "same_period",
        "before",
        "adjacent",
        "not_adjacent",
        "minimum_gap",
    }:
        slot_x = assignment[proposition["person_x"]]
        slot_y = assignment[proposition["person_y"]]
        if proposition_type == "same_session":
            return slot_x == slot_y
        if proposition_type == "same_day":
            return get_day_for_slot(slot_x, profile) == get_day_for_slot(
                slot_y,
                profile,
            )
        if proposition_type == "same_period":
            return get_period_for_slot(slot_x, profile) == get_period_for_slot(
                slot_y,
                profile,
            )
        if proposition_type == "before":
            return slot_x < slot_y
        if proposition_type == "adjacent":
            return abs(slot_x - slot_y) == 1
        if proposition_type == "not_adjacent":
            return abs(slot_x - slot_y) >= 2
        return abs(slot_x - slot_y) - 1 >= proposition["gap"]

    raise ValueError(f"Unsupported proposition type: {proposition_type}")
