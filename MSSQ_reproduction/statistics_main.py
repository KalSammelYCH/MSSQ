"""主实验统计纯函数：输入重算逐题记录，输出分组、四联、资源和CSP区间；沿用原公式与随机种子。"""
from __future__ import annotations
import math, random, statistics
from collections import Counter, defaultdict
from typing import Any, Iterable

MODELS = [
    "Claude Opus 5",
    "Qwen3.8-Max",
    "DeepSeek-V4-Pro",
    "Grok 4.6",
    "GLM-5.2",
    "GPT-5.6 Sol",
    "Kimi-K2.6",
    "Gemini 3.8 Flash",
]


FAMILIES = ["scheduling", "frequency_assignment", "bijective_matching"]


LANGUAGES = ["zh", "en"]


TASKS = ["must", "may", "witness", "counterexample"]


MODALITIES = ["necessary", "contingent", "impossible"]


STRATA = ["sparse", "richer"]


BOOTSTRAP_REPS = 10_000


BOOTSTRAP_SEED = 27_017


BOOTSTRAP_DRAWS_PER_STRATUM = 4


BOOL_FIELDS = {
    "gold_must", "gold_may", "construction_gold_exists", "has_final_response_text",
    "semantic_recoverable", "semantic_correct", "construction_valid", "task_success",
    "format_compliant", "source_authority_conflict", "source_authority_historical_task_success",
    "recognizable_answer", "claim_correct", "construction_required", "construction_present",
    "construction_complete", "public_constraints_valid", "target_direction_valid", "strict_success",
}


INT_FIELDS = {
    "semantic_attempt_limit_k", "semantic_attempt_count_observed_until_adoption",
    "technical_attempt_count_observed_until_adoption", "raw_api_record_count_in_registered_chain",
    "post_adoption_ignored_record_count", "technical_retry_count_observed_until_adoption",
    "adopted_source_line_number", "raw_http_status", "input_tokens", "output_tokens",
    "reasoning_tokens", "cached_tokens", "total_tokens",
}


FLOAT_FIELDS = {"elapsed_seconds"}


def parse_bool(value: str) -> bool | None:
    if value == "True":
        return True
    if value == "False":
        return False
    if value == "":
        return None
    raise ValueError(f"无法解析布尔值：{value!r}")


def parse_int(value: str) -> int | None:
    if value == "":
        return None
    return int(float(value))


def parse_float(value: str) -> float | None:
    if value == "":
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"非有限数值：{value!r}")
    return result


def ratio(num: int | float, den: int | float) -> float | None:
    return None if den == 0 else num / den


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * p
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] * (hi - pos) + ordered[hi] * (pos - lo)


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    semantic = [r for r in rows if r["semantic_recoverable"] is True]
    judgment = [r for r in rows if r["task"] in {"must", "may"}]
    construction = [r for r in rows if r["task"] in {"witness", "counterexample"}]
    required = [r for r in rows if r["construction_required"] is True]
    return {
        "n": len(rows),
        "task_success_n": sum(r["task_success"] is True for r in rows),
        "task_success_rate": ratio(sum(r["task_success"] is True for r in rows), len(rows)),
        "semantic_recoverable_n": len(semantic),
        "semantic_coverage_rate": ratio(len(semantic), len(rows)),
        "semantic_correct_n": sum(r["semantic_correct"] is True for r in semantic),
        "semantic_accuracy_given_recoverable": ratio(sum(r["semantic_correct"] is True for r in semantic), len(semantic)),
        "task_success_given_recoverable": ratio(sum(r["task_success"] is True for r in semantic), len(semantic)),
        "judgment_n": len(judgment),
        "judgment_success_n": sum(r["task_success"] is True for r in judgment),
        "judgment_success_rate": ratio(sum(r["task_success"] is True for r in judgment), len(judgment)),
        "construction_task_n": len(construction),
        "construction_task_success_n": sum(r["task_success"] is True for r in construction),
        "construction_task_success_rate": ratio(sum(r["task_success"] is True for r in construction), len(construction)),
        "gold_required_construction_n": len(required),
        "gold_required_valid_construction_n": sum(r["task_success"] is True for r in required),
        "gold_required_valid_construction_rate": ratio(sum(r["task_success"] is True for r in required), len(required)),
    }


def predicted_claim(row: dict[str, Any]) -> bool | None:
    if row["semantic_recoverable"] is not True or row["claim_correct"] is None:
        return None
    if row["task"] == "must":
        gold = row["gold_must"]
    elif row["task"] == "may":
        gold = row["gold_may"]
    else:
        gold = row["construction_gold_exists"]
    if gold is None:
        raise ValueError(f"缺少Gold claim：{row['prompt_id']}")
    return gold if row["claim_correct"] else not gold


def build_quartet_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (row["model"], row["family"], row["language"], row["csp_id"], row["quartet_id"])
        grouped[key].append(row)

    records: list[dict[str, Any]] = []
    modal_from_pair = {
        (True, True): "necessary",
        (False, True): "contingent",
        (False, False): "impossible",
    }
    all_modalities = {"necessary", "contingent", "impossible"}
    for key, group in grouped.items():
        if len(group) != 4 or {r["task"] for r in group} != set(TASKS):
            raise ValueError(f"四元组不完整：{key} -> {len(group)}")
        by_task = {r["task"]: r for r in group}
        modality = group[0]["modality"]
        must_pred = predicted_claim(by_task["must"])
        may_pred = predicted_claim(by_task["may"])
        if must_pred is None or may_pred is None:
            modal_status = "indeterminate"
            inferred_modal = None
        elif (must_pred, may_pred) not in modal_from_pair:
            modal_status = "inconsistent_judgment_pair"
            inferred_modal = None
        else:
            inferred_modal = modal_from_pair[(must_pred, may_pred)]
            modal_status = "correct" if inferred_modal == modality else "wrong_modal_class"

        possible = set(all_modalities)
        unknown_component = False
        component_sets: list[set[str]] = []
        for task in TASKS:
            row = by_task[task]
            pred = predicted_claim(row)
            if pred is None:
                unknown_component = True
                continue
            if task == "must":
                component_sets.append({"necessary"} if pred else {"contingent", "impossible"})
            elif task == "may":
                component_sets.append({"necessary", "contingent"} if pred else {"impossible"})
            elif task == "witness":
                if pred is False:
                    component_sets.append({"impossible"})
                elif row["task_success"] is True:
                    component_sets.append({"necessary", "contingent"})
                else:
                    unknown_component = True
            elif task == "counterexample":
                if pred is False:
                    component_sets.append({"necessary"})
                elif row["task_success"] is True:
                    component_sets.append({"contingent", "impossible"})
                else:
                    unknown_component = True
        for component in component_sets:
            possible &= component
        if not possible:
            compatibility = "incompatible"
        elif unknown_component:
            compatibility = "indeterminate"
        else:
            compatibility = "compatible"

        records.append({
            "model": key[0],
            "family": key[1],
            "language": key[2],
            "csp_id": key[3],
            "quartet_id": key[4],
            "stratum": group[0]["stratum"],
            "gold_modality": modality,
            "inferred_modality": inferred_modal,
            "modal_recovery_status": modal_status,
            "full_quartet_success": all(r["task_success"] is True for r in group),
            "compatibility_status": compatibility,
        })
    return records


def build_contingent_direction_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    contingent = [r for r in rows if r["modality"] == "contingent"]
    grouped: dict[tuple[str, str, str, str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in contingent:
        key = (row["model"], row["family"], row["language"], row["csp_id"], row["quartet_id"])
        grouped[key][row["task"]] = row
    records: list[dict[str, Any]] = []
    for key, by_task in grouped.items():
        if set(by_task) != set(TASKS):
            raise ValueError(f"contingent quartet不完整：{key}")
        for direction, j_task, k_task in (
            ("positive", "may", "witness"),
            ("negative", "must", "counterexample"),
        ):
            j = by_task[j_task]["task_success"] is True
            k = by_task[k_task]["task_success"] is True
            records.append({
                "model": key[0], "family": key[1], "language": key[2], "csp_id": key[3],
                "quartet_id": key[4], "stratum": by_task[j_task]["stratum"], "direction": direction,
                "judgment_correct": j, "construction_valid": k,
                "pair_state": "both_success" if j and k else "judgment_only" if j else "construction_only" if k else "neither",
            })
    return records


def group_metrics(rows: list[dict[str, Any]], dimensions: list[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row[d] for d in dimensions)].append(row)
    output: list[dict[str, Any]] = []
    for key in sorted(grouped, key=lambda k: tuple(str(x) for x in k)):
        record = dict(zip(dimensions, key))
        record.update(summarize_rows(grouped[key]))
        output.append(record)
    return output


def family_balanced_rate(rows: list[dict[str, Any]], numerator, denominator) -> float | None:
    rates: list[float] = []
    for family in FAMILIES:
        family_rows = [r for r in rows if r["family"] == family]
        den = sum(1 for r in family_rows if denominator(r))
        num = sum(1 for r in family_rows if denominator(r) and numerator(r))
        if den == 0:
            return None
        rates.append(num / den)
    return statistics.mean(rates)


def quartet_summary(records: list[dict[str, Any]], model: str) -> dict[str, Any]:
    subset = [r for r in records if r["model"] == model]
    modal_counts = Counter(r["modal_recovery_status"] for r in subset)
    compatibility = Counter(r["compatibility_status"] for r in subset)
    return {
        "quartet_n": len(subset),
        "modal_recovery_correct_n": modal_counts["correct"],
        "modal_recovery_fixed_rate": ratio(modal_counts["correct"], len(subset)),
        "modal_recovery_indeterminate_n": modal_counts["indeterminate"],
        "modal_recovery_inconsistent_pair_n": modal_counts["inconsistent_judgment_pair"],
        "modal_recovery_wrong_class_n": modal_counts["wrong_modal_class"],
        "full_quartet_success_n": sum(r["full_quartet_success"] for r in subset),
        "full_quartet_success_rate": ratio(sum(r["full_quartet_success"] for r in subset), len(subset)),
        "compatible_n": compatibility["compatible"],
        "incompatible_n": compatibility["incompatible"],
        "indeterminate_n": compatibility["indeterminate"],
        "compatible_rate": ratio(compatibility["compatible"], len(subset)),
        "incompatible_rate": ratio(compatibility["incompatible"], len(subset)),
        "indeterminate_rate": ratio(compatibility["indeterminate"], len(subset)),
    }


def direction_summary(records: list[dict[str, Any]], model: str) -> dict[str, Any]:
    subset = [r for r in records if r["model"] == model]
    counts = Counter(r["pair_state"] for r in subset)
    j_correct = sum(r["judgment_correct"] for r in subset)
    hidden = sum(r["judgment_correct"] and not r["construction_valid"] for r in subset)
    return {
        "contingent_direction_n": len(subset),
        "both_success_n": counts["both_success"],
        "judgment_only_n": counts["judgment_only"],
        "construction_only_n": counts["construction_only"],
        "neither_n": counts["neither"],
        "judgment_correct_n": j_correct,
        "hidden_implementation_failure_n": hidden,
        "hidden_implementation_failure_rate": ratio(hidden, j_correct),
    }


def numeric_stats(values: Iterable[float | int | None]) -> dict[str, Any]:
    present = [float(v) for v in values if v is not None]
    if not present:
        return {"coverage_n": 0, "sum": None, "mean": None, "median": None, "p90": None}
    return {
        "coverage_n": len(present),
        "sum": sum(present),
        "mean": statistics.mean(present),
        "median": statistics.median(present),
        "p90": percentile(present, 0.9),
    }


def resource_summary(rows: list[dict[str, Any]], dimensions: list[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row[d] for d in dimensions)].append(row)
    output = []
    for key in sorted(grouped, key=lambda k: tuple(str(x) for x in k)):
        group = grouped[key]
        record = dict(zip(dimensions, key))
        record["adopted_record_n"] = len(group)
        for field in ("input_tokens", "output_tokens", "reasoning_tokens", "total_tokens", "elapsed_seconds"):
            stats = numeric_stats(r[field] for r in group)
            for stat, value in stats.items():
                record[f"{field}_{stat}"] = value
        record["elapsed_sum_hours"] = None if record["elapsed_seconds_sum"] is None else record["elapsed_seconds_sum"] / 3600
        output.append(record)
    return output


def add_metric(contrib, metric: str, model: str, family: str, csp: str, num: int, den: int) -> None:
    old_num, old_den = contrib[metric][model][(family, csp)]
    contrib[metric][model][(family, csp)] = (old_num + num, old_den + den)


def build_bootstrap(rows, quartets, directions) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    contrib = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: (0, 0))))
    for row in rows:
        m, f, c = row["model"], row["family"], row["csp_id"]
        add_metric(contrib, "fixed_task_success", m, f, c, int(row["task_success"] is True), 1)
        add_metric(contrib, "semantic_coverage", m, f, c, int(row["semantic_recoverable"] is True), 1)
        if row["task"] in {"must", "may"}:
            add_metric(contrib, "judgment_task_success", m, f, c, int(row["task_success"] is True), 1)
        if row["task"] in {"witness", "counterexample"}:
            add_metric(contrib, "construction_task_success", m, f, c, int(row["task_success"] is True), 1)
        if row["construction_required"] is True:
            add_metric(contrib, "gold_required_valid_construction", m, f, c, int(row["task_success"] is True), 1)
    for q in quartets:
        m, f, c = q["model"], q["family"], q["csp_id"]
        add_metric(contrib, "modal_recovery", m, f, c, int(q["modal_recovery_status"] == "correct"), 1)
        add_metric(contrib, "full_quartet_recovery", m, f, c, int(q["full_quartet_success"]), 1)
        add_metric(contrib, "output_compatibility", m, f, c, int(q["compatibility_status"] == "compatible"), 1)
    for d in directions:
        m, f, c = d["model"], d["family"], d["csp_id"]
        if d["judgment_correct"]:
            add_metric(contrib, "hidden_implementation_failure", m, f, c, int(not d["construction_valid"]), 1)

    csp_stratum: dict[tuple[str, str], str] = {}
    for row in rows:
        key = (row["family"], row["csp_id"])
        csp_stratum[key] = row["stratum"]
    strata_csps: dict[tuple[str, str], list[str]] = {}
    for family in FAMILIES:
        for stratum in STRATA:
            csps = sorted(c for (f, c), s in csp_stratum.items() if f == family and s == stratum)
            if len(csps) != 4:
                raise ValueError(f"{family}/{stratum} CSP数不是4：{csps}")
            strata_csps[(family, stratum)] = csps

    metric_names = list(contrib.keys())
    point: dict[str, dict[str, float | None]] = defaultdict(dict)
    for metric in metric_names:
        for model in MODELS:
            family_rates = []
            for family in FAMILIES:
                num = den = 0
                for (f, _), pair in contrib[metric][model].items():
                    if f == family:
                        num += pair[0]
                        den += pair[1]
                if den == 0:
                    family_rates = []
                    break
                family_rates.append(num / den)
            point[metric][model] = statistics.mean(family_rates) if family_rates else None

    rng = random.Random(BOOTSTRAP_SEED)
    samples: dict[str, dict[str, list[float]]] = {
        metric: {model: [] for model in MODELS} for metric in metric_names
    }
    for _ in range(BOOTSTRAP_REPS):
        weights: Counter[tuple[str, str]] = Counter()
        for family in FAMILIES:
            for stratum in STRATA:
                csps = strata_csps[(family, stratum)]
                for _draw in range(BOOTSTRAP_DRAWS_PER_STRATUM):
                    weights[(family, rng.choice(csps))] += 1
        for metric in metric_names:
            for model in MODELS:
                family_rates = []
                for family in FAMILIES:
                    num = den = 0
                    for (f, c), weight in weights.items():
                        if f != family:
                            continue
                        pair = contrib[metric][model][(f, c)]
                        num += pair[0] * weight
                        den += pair[1] * weight
                    if den == 0:
                        family_rates = []
                        break
                    family_rates.append(num / den)
                if family_rates:
                    samples[metric][model].append(statistics.mean(family_rates))

    output = []
    for metric in metric_names:
        for model in MODELS:
            vals = samples[metric][model]
            output.append({
                "model": model,
                "metric": metric,
                "family_balanced_point": point[metric][model],
                "sensitivity_interval_low": percentile(vals, 0.025),
                "sensitivity_interval_high": percentile(vals, 0.975),
                "valid_replicates": len(vals),
            })
    metadata = {
        "method": "family-balanced, family×stratum CSP-cluster percentile bootstrap sensitivity interval",
        "replicates": BOOTSTRAP_REPS,
        "seed": BOOTSTRAP_SEED,
        "draws_per_family_stratum": BOOTSTRAP_DRAWS_PER_STRATUM,
        "original_csps_per_family_stratum": 4,
        "nominal_cluster_draws_per_replicate": len(FAMILIES) * len(STRATA) * BOOTSTRAP_DRAWS_PER_STRATUM,
        "paired_structure_preserved": True,
    }
    return output, metadata
