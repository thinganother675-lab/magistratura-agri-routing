# SPDX-License-Identifier: Apache-2.0
"""DEV-only model selection and saved-output replay, independent of source text.

This module accepts measurements, never questions, answer choices, gold letters,
or private TEST data. Completeness and a common protocol are prerequisites for
ranking. Missing resource/probability measurements remain unknown.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics


PRIVATE_TEXT_KEYS = frozenset({"question", "prompt", "outputs", "gold", "prediction",
                              "prediction_raw", "raw", "reference", "choices"})
CLAIM_STATUSES = frozenset({"DEV", "HISTORICAL", "CONFIRMATORY", "SIMULATED"})
PROFILE_COMMON_FIELDS = ("dataset_revision", "source_sha256", "selection_sha256",
                         "system_sha256", "output_contract", "score_policy",
                         "common_parameters_sha256", "common_load_policy_sha256",
                         "reasoning_policy_sha256")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_safe_measurements(value):
    if isinstance(value, dict):
        forbidden = PRIVATE_TEXT_KEYS.intersection(value)
        if forbidden:
            raise ValueError("Restricted content cannot enter safe analysis: " + ",".join(sorted(forbidden)))
        if value.get("split", "dev") != "dev":
            raise ValueError("Only public DEV measurements are accepted")
        for child in value.values():
            assert_safe_measurements(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            assert_safe_measurements(child)


def percentile(values, fraction):
    values = sorted(v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v))
    if not values:
        return None
    position = (len(values) - 1) * fraction
    low, high = math.floor(position), math.ceil(position)
    return values[low] + (position - low) * (values[high] - values[low])


def wilson_em_interval(successes, n):
    """Descriptive95% binomial interval; DEV selection/dependence is not removed."""
    if isinstance(n, bool) or not isinstance(n, int) or n < 0 or isinstance(successes, bool) or not isinstance(successes, int) or not 0 <= successes <= n:
        raise ValueError("Wilson interval requires bounded integer counts")
    if not n:
        return {"n": 0, "successes": 0, "lower": None, "upper": None,
                "method": "WILSON_95_DESCRIPTIVE", "independent_confirmatory_inference": False}
    z = 1.959963984540054
    p, z2 = successes / n, z * z
    denominator = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denominator
    radius = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denominator
    return {"n": n, "successes": successes, "lower": max(0., center - radius),
            "upper": min(1., center + radius), "method": "WILSON_95_DESCRIPTIVE",
            "independent_confirmatory_inference": False}


def paired_correctness(left_rows, right_rows, expected_ids):
    """Paired correctness discordance on the same DEV, without a p-value."""
    assert_safe_measurements(left_rows); assert_safe_measurements(right_rows)
    expected = list(expected_ids)
    left, right = {r["item_id"]: r for r in left_rows}, {r["item_id"]: r for r in right_rows}
    if not expected or len(expected) != len(set(expected)) or len(left) != len(left_rows) or len(right) != len(right_rows) or set(left) != set(expected) or set(right) != set(expected):
        raise ValueError("Paired correctness requires full common DEV coverage")
    counts = {"both_correct": 0, "left_only_correct": 0, "right_only_correct": 0, "both_incorrect": 0}
    unresolved = 0
    for item in expected:
        a, b = left[item], right[item]
        if (a["domain"], a.get("gold_valid"), a.get("gold_cardinality")) != (b["domain"], b.get("gold_valid"), b.get("gold_cardinality")):
            raise ValueError("Paired DEV source annotations differ")
        if not a.get("gold_valid"):
            unresolved += 1
            continue
        # Use the same guards as the metric summary, including zero credit
        # for any failed/invalid response; no recovered gold or output text.
        summarize_measurements([a], [item]); summarize_measurements([b], [item])
        key = "both_correct" if a["em"] and b["em"] else "left_only_correct" if a["em"] else "right_only_correct" if b["em"] else "both_incorrect"
        counts[key] += 1
    n = len(expected) - unresolved
    return {"status": "DEV", "n_expected": len(expected), "n_scored": n,
            "reference_issues": unresolved, **counts,
            "em_difference_left_minus_right": (counts["left_only_correct"] - counts["right_only_correct"]) / n if n else None,
            "independent_holdout": False, "confirmatory_p_value": None}


def summarize_measurements(rows, expected_ids):
    """Invalid/error predictions score zero; unparseable gold stays unresolved."""
    assert_safe_measurements(rows)
    expected = list(expected_ids)
    ids = [r["item_id"] for r in rows]
    if len(expected) != len(set(expected)) or len(ids) != len(set(ids)):
        raise ValueError("Duplicate DEV id")
    if not set(ids).issubset(expected):
        raise ValueError("Unexpected DEV id")
    scored = [r for r in rows if r.get("gold_valid") is True]
    for r in scored:
        if r.get("em") not in (0, 1) or isinstance(r.get("f1"), bool) or not isinstance(r.get("f1"), (int, float)) or not 0 <= r["f1"] <= 1:
            raise ValueError("Valid gold requires bounded EM/F1 measurement")
        if (r.get("error") or r.get("pred_valid") is False) and (r["em"] != 0 or r["f1"] != 0):
            raise ValueError("Invalid/error output cannot score positively")
    em = sum(r["em"] for r in scored)
    f1 = sum(r["f1"] for r in scored)
    latency = [r.get("latency_s") for r in rows]
    finite_latency = [x for x in latency if isinstance(x, (float, int)) and not isinstance(x, bool) and math.isfinite(x) and x >= 0]
    responses = sum(r.get("response_received", False) is True for r in rows)
    completed = sum(r.get("response_received", False) is True and not r.get("error") for r in rows)
    return {"n_expected": len(expected), "n_attempted": len(rows), "n_completed": completed,
            "n_response_received": responses, "n_scored": len(scored),
            "missing_ids": sorted(set(expected) - set(ids)), "attempted_coverage": set(ids) == set(expected),
            "complete": set(ids) == set(expected) and completed == len(expected),
            "strict_em_count": em, "strict_f1_sum": f1,
            "strict_set_em": em / len(scored) if scored else None,
            "strict_set_f1": f1 / len(scored) if scored else None,
            "conservative_all_n_em": em / len(expected) if expected else None,
            "conservative_all_n_f1": f1 / len(expected) if expected else None,
            "reference_issues": len(rows) - len(scored),
            "invalid_output": sum(r.get("pred_valid") is False for r in rows),
            "errors": sum(bool(r.get("error")) for r in rows),
            "latency_p50_s": percentile(finite_latency, .5), "latency_p95_s": percentile(finite_latency, .95),
            "latency_mean_s": statistics.mean(finite_latency) if finite_latency else None,
            "latency_coverage": len(finite_latency)}


def validate_comparable(profiles, expected_ids, *, expected_stage="dev60"):
    """Return complete common-protocol candidates; partial percentages cannot rank."""
    expected = set(expected_ids)
    if not expected or len(expected) != len(list(expected_ids)):
        raise ValueError("Expected IDs must be unique and nonempty")
    accepted, rejected = [], {}
    common = None
    for profile in profiles:
        key = profile["model_key"]
        if key in rejected or any(p["model_key"] == key for p in accepted):
            raise ValueError("Duplicate model profile key")
        summary = profile["summary"]
        reasons = []
        if profile.get("stage") != expected_stage or profile.get("split", "dev") != "dev":
            reasons.append("NOT_COMMON_" + expected_stage.upper())
        if profile.get("status") != "COMPLETE" or summary.get("complete_coverage") is not True or summary.get("n_completed") != len(expected) or set(profile.get("ids", [])) != expected or len(profile.get("ids", [])) != len(expected):
            reasons.append("INCOMPLETE_COVERAGE")
        fingerprint = tuple(profile.get(k) for k in PROFILE_COMMON_FIELDS)
        if any(x is None for x in fingerprint):
            reasons.append("MISSING_PROTOCOL_PROVENANCE")
        elif common is not None and fingerprint != common:
            reasons.append("INCOMPARABLE_PROTOCOL")
        for name in ("strict_set_em", "strict_set_f1", "latency_p50_s", "latency_p95_s"):
            x = summary.get(name)
            if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0 or (name.startswith("strict") and x > 1):
                reasons.append("MISSING_OR_INVALID_" + name.upper())
        if summary.get("n_scored", 0) + summary.get("reference_issues", 0) != len(expected):
            reasons.append("SCORING_COVERAGE_MISMATCH")
        if reasons:
            rejected[key] = reasons
        else:
            common = fingerprint if common is None else common
            accepted.append(profile)
    if accepted and len({(p["summary"]["n_scored"], p["summary"]["reference_issues"]) for p in accepted}) != 1:
        raise ValueError("Candidates differ in gold score denominator")
    return accepted, rejected


def _objectives(profile, *, resources=True):
    s = profile["summary"]
    values = [-s["strict_set_em"], -s["strict_set_f1"], s["latency_p95_s"], s.get("invalid_output", 0), s.get("errors", 0)]
    if resources:
        for name in ("peak_gpu_mib", "peak_ram_used_gib"):
            x = s.get(name)
            if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0:
                return None
            values.append(x)
    return values


def pareto_front(profiles):
    """Use resources only when measured for every candidate; do not invent them."""
    resource_complete = all(_objectives(p) is not None for p in profiles)
    obj = {p["model_key"]: _objectives(p, resources=resource_complete) for p in profiles}
    front = []
    for p in profiles:
        candidate = obj[p["model_key"]]
        dominated = any(all(a <= b for a, b in zip(other, candidate)) and any(a < b for a, b in zip(other, candidate))
                        for key, other in obj.items() if key != p["model_key"])
        if not dominated:
            front.append(p)
    return front, resource_complete


def select_shortlist(profiles, expected_ids, maximum=5):
    if not 3 <= maximum <= 5:
        raise ValueError("Shortlist ceiling must be 3-5")
    eligible, rejected = validate_comparable(profiles, expected_ids)
    front, resources = pareto_front(eligible)
    roles, selected = {}, []
    def add(role, profile):
        key = profile["model_key"]
        roles[role] = key
        if key not in selected and len(selected) < maximum:
            selected.append(key)
    if front:
        quality = sorted(front, key=lambda p: (-p["summary"]["strict_set_em"], -p["summary"]["strict_set_f1"], p["summary"]["errors"], p["summary"]["latency_p95_s"], p["model_key"]))
        add("HIGH_QUALITY", quality[0])
        add("FAST", min(front, key=lambda p: (p["summary"]["latency_p50_s"], -p["summary"]["strict_set_em"], p["model_key"])))
        if resources:
            add("LOW_RESOURCE", min(front, key=lambda p: (p["summary"]["peak_gpu_mib"], p["summary"]["peak_ram_used_gib"], -p["summary"]["strict_set_em"], p["model_key"])))
        # A bounded DEV tolerance, declared in code before the screen: retain
        # quality within ten percentage points of the observed best, then speed.
        near_best = [p for p in front if p["summary"]["strict_set_em"] >= quality[0]["summary"]["strict_set_em"] - .10]
        add("BALANCED", min(near_best, key=lambda p: (p["summary"]["latency_p95_s"], p["summary"]["invalid_output"], -p["summary"]["strict_set_f1"], p["model_key"])))
        # Fill only from the actual non-dominated front; never pad with partial
        # or dominated candidates merely to reach a requested count.
        for p in quality:
            if len(selected) >= maximum:
                break
            if p["model_key"] not in selected:
                selected.append(p["model_key"])
    return {"status": "DEV_SHORTLIST_FROZEN_BEFORE_DEV293", "selected": selected,
            "roles": roles, "pareto_models": sorted(p["model_key"] for p in front),
            "eligible_complete_models": sorted(p["model_key"] for p in eligible), "excluded": rejected,
            "resource_objectives_available": resources, "balanced_em_tolerance": .10,
            "selection_is_confirmatory": False, "minimum_not_forced": len(selected) < 3}


def grouped_metrics(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    return {str(group): summarize_measurements(values, [r["item_id"] for r in values]) for group, values in sorted(groups.items(), key=lambda kv: str(kv[0]))}


def domain_and_cardinality(rows):
    assert_safe_measurements(rows)
    return {"domains": grouped_metrics(rows, lambda r: r["domain"]),
            "answer_cardinality": grouped_metrics(rows, lambda r: "unresolved_reference" if not r.get("gold_valid") else "single" if r["gold_cardinality"] == 1 else "multi")}


def route_signal(row, *, threshold=None):
    """Only observable local-format/error/abstain/probability fields are allowed."""
    allowed = {"pred_valid", "error", "abstain", "option_token_confidence"}
    if set(row) - allowed:
        raise ValueError("Routing accepts observable signals only, no references")
    if row.get("error") or row.get("pred_valid") is not True or row.get("abstain"):
        return "cloud"
    if threshold is not None:
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
            raise ValueError("Invalid threshold")
        confidence = row.get("option_token_confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or not 0 <= confidence <= 1 or confidence < threshold:
            return "cloud"
    return "local"


def replay_cascade(local, cloud, expected_ids, *, threshold=None):
    assert_safe_measurements(local); assert_safe_measurements(cloud)
    expected = set(expected_ids)
    left, right = {r["item_id"]: r for r in local}, {r["item_id"]: r for r in cloud}
    if not expected or len(left) != len(local) or len(right) != len(cloud) or set(left) != expected or set(right) != expected:
        raise ValueError("Saved paired full common DEV coverage is required")
    chosen, remote = [], 0
    for item in expected_ids:
        a, b = left[item], right[item]
        if (a["domain"], a.get("gold_valid"), a.get("gold_cardinality")) != (b["domain"], b.get("gold_valid"), b.get("gold_cardinality")):
            raise ValueError("Paired DEV source annotations differ")
        signal = {k: a.get(k) for k in ("pred_valid", "error", "abstain", "option_token_confidence")}
        take_cloud = route_signal(signal, threshold=threshold) == "cloud"
        remote += take_cloud
        chosen.append(dict(b if take_cloud else a))
    result = summarize_measurements(chosen, expected_ids)
    result.update(status="SIMULATED", replay_type="SAVED_DEV_OUTPUTS_ONLY", cloud_calls_if_deployed=remote,
                  cloud_fraction_if_deployed=remote / len(expected), local_resolution_fraction_if_deployed=1 - remote / len(expected),
                  relative_cloud_call_reduction_if_deployed=1 - remote / len(expected), actual_requests_saved=0,
                  threshold=threshold, live_latency_or_cost_savings_established=False)
    # The copied latency fields describe selected saved outputs, not measured
    # cascade latency; expose separately and do not mislabel as live savings.
    result["selected_output_latency_summary_is_live_cascade"] = False
    return result


def select_dev_routing_rule(local, cloud, expected_ids):
    """A predeclared DEV objective; its5pp margin requires human confirmation.

    Each deployed routing decision remains reference-free. Open DEV scores
    select a threshold from the fixed grid, never hidden TEST data.
    """
    thresholds = [None, .5, .7, .8, .9, .95, .98, .99, 1.]
    cloud_summary = summarize_measurements(cloud, expected_ids)
    local_summary = summarize_measurements(local, expected_ids)
    if cloud_summary["strict_set_em"] is None:
        raise ValueError("A scored commonDEV cloud baseline is required")
    grid = [replay_cascade(local, cloud, expected_ids, threshold=t) for t in thresholds]
    eligible = [(i, r) for i, r in enumerate(grid) if r["strict_set_em"] >= cloud_summary["strict_set_em"] - .05]
    chosen = min(eligible, key=lambda pair: (pair[1]["cloud_fraction_if_deployed"], -pair[1]["strict_set_f1"], -1 if pair[1]["threshold"] is None else pair[1]["threshold"])) if eligible else None
    return {"status": "SIMULATED", "selection_data": "PUBLIC_COMMON_DEV60_ONLY", "grid": grid,
            "objective": "smallest cloud fraction with STRICT_SET_EM >= cloud EM minus .05; tie higherF1 then lowerthreshold",
            "exploratory_em_margin": .05, "margin_human_confirmation": "PENDING",
            "cloud_only": cloud_summary, "local_only": local_summary,
            "selected_index": chosen[0] if chosen else None, "selected": chosen[1] if chosen else None,
            "dev_observed_em_improvement_with_confidence": bool(chosen and chosen[1]["threshold"] is not None and chosen[1]["cloud_fraction_if_deployed"] < 1 and chosen[1]["strict_set_em"] > grid[0]["strict_set_em"]),
            "confidence_benefit_established": False,
            "trivial_local_resolution_suffices_on_dev": bool(chosen and chosen[1]["cloud_calls_if_deployed"] == 0),
            "confirmatory_noninferiority_established": False, "private_test_run": False,
            "actual_requests_saved": 0}


def confidence_diagnostic(rows):
    assert_safe_measurements(rows)
    pairs = [(r["option_token_confidence"], r["em"]) for r in rows if r.get("gold_valid") and r.get("pred_valid") and not r.get("error") and isinstance(r.get("option_token_confidence"), (float, int)) and not isinstance(r.get("option_token_confidence"), bool) and math.isfinite(r["option_token_confidence"]) and 0 <= r["option_token_confidence"] <= 1]
    correct = [x for x, y in pairs if y == 1]
    incorrect = [x for x, y in pairs if y == 0]
    auc = (sum(float(a > b) + .5 * float(a == b) for a in correct for b in incorrect) / (len(correct) * len(incorrect)) if correct and incorrect else None)
    return {"status": "DEV_LEXICAL_CONFIDENCE_DIAGNOSTIC" if pairs else "UNAVAILABLE",
            "n_observed": len(pairs), "n_total": len(rows), "auc_correctness": auc,
            "mean_if_correct": statistics.mean(correct) if correct else None,
            "mean_if_incorrect": statistics.mean(incorrect) if incorrect else None,
            "calibrated_probability_of_correctness": False,
            "primary_threshold_selected": False}


def json_pointer(document, pointer):
    value = document
    if pointer == "":
        return value
    if not pointer.startswith("/"):
        raise ValueError("Analysis field must be a JSON pointer")
    for piece in pointer[1:].split("/"):
        piece = piece.replace("~1", "/").replace("~0", "~")
        value = value[int(piece)] if isinstance(value, list) else value[piece]
    return value


def validate_claims(claims, root):
    seen = set()
    for c in claims:
        if not c.get("claim_id") or c["claim_id"] in seen:
            raise ValueError("Missing or duplicate claim id")
        seen.add(c["claim_id"])
        if not all(c.get(k) for k in ("statement", "study_run_id", "data_path", "analysis_field", "code_commit", "status", "data_sha256")):
            raise ValueError("Incomplete claim provenance")
        if c["status"] not in CLAIM_STATUSES:
            raise ValueError("Unknown evidence status")
        path = (Path(root) / c["data_path"]).resolve()
        if not path.is_relative_to(Path(root).resolve()) or not path.is_file() or digest(path.read_bytes()) != c["data_sha256"]:
            raise ValueError("Claim data missing, outside workspace, or changed")
        document = json.loads(path.read_text(encoding="utf-8"))
        actual = json_pointer(document, c["analysis_field"])
        if actual != c.get("value"):
            raise ValueError("Claim value does not match source")
        if c["status"] == "CONFIRMATORY" and "dev" in c["study_run_id"].lower():
            raise ValueError("DEV evidence cannot be promoted to confirmatory")
        if c["status"] == "CONFIRMATORY" and c.get("private_test_authorized") is not True:
            raise ValueError("Confirmatory claim lacks explicit authorization evidence")
        if c["status"] == "CONFIRMATORY":
            source_roles = [str(document.get(k, "")).upper() for k in
                            ("status", "classification", "evidence_status", "source_dataset_role", "dataset_role", "split")]
            if any("DEV" in role or "SIMULAT" in role or "HISTORICAL" in role for role in source_roles) or document.get("private_test_run") is False:
                raise ValueError("DEV/SIMULATED/HISTORICAL source evidence cannot be promoted to confirmatory")
            if "CONFIRMATORY" not in source_roles or document.get("private_test_run") is not True:
                raise ValueError("Source document lacks confirmatory evidence classification")
    return {"valid": True, "claim_count": len(claims)}
