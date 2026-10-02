"""Analyze a saved frozen HOME final journal, without inference or API calls.

Missing/NOT_RUN decisions do not enter accuracy. Full frozen-ID coverage is
required for criterion conclusions. Whole source/family bootstrap is primary;
Wilson and McNemar are descriptive under correlated variants.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import uuid

import numpy as np
from agro_route.evaluation import score
from agro_route.home_stats import cluster_bootstrap_interval, paired_cluster_bootstrap, wilson_interval, mcnemar_exact
from agro_route.models import public_request
from agro_route.routing import hard_gate

ROOT = Path(__file__).resolve().parents[1]
METHODS = ("local", "cloud", "tool_cloud", "hybrid", "offline")
REPEATS = 5000
SEED = 20261001
CRITERIA = {"quality_margin": .05, "cloud_call_reduction_pp": .10,
            "critical_error_increase_max": 0, "p95_max_s": 10}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def total_known(values):
    values = [value for value in values if finite(value)]
    return sum(values) if values else None


def latency(values):
    known = [value / 1000 for value in values if finite(value)]
    return {"known_n": len(known), "mean_s": float(np.mean(known)) if known else None,
            "p50_s": float(np.quantile(known, .5)) if known else None,
            "p95_s": float(np.quantile(known, .95)) if known else None}


def validate_records(records, samples, methods=METHODS):
    indexed = {sample["id"]: sample for sample in samples}
    if len(indexed) != len(samples) or any(not sample.get("group") for sample in samples):
        raise ValueError("Frozen sample IDs must be unique and have source/family groups")
    decisions = {method: {} for method in methods}
    normalized = []
    for row in records:
        sample, method, result = row["sample"], row["method"], row["result"]
        sid = sample["id"]
        if sid not in indexed or sample != indexed[sid]:
            raise ValueError("Journal sample differs from frozen dataset")
        if method not in decisions or sid in decisions[method]:
            raise ValueError("Unknown policy or duplicate ID-policy decision")
        status = result.get("status")
        if status not in ("MEASURED", "NOT_RUN"):
            raise ValueError("Decision status must explicitly be MEASURED or NOT_RUN")
        kind = (result.get("latency_kind") or "").lower()
        if status == "MEASURED" and any(word in kind for word in ("cli", "reconstruct", "cached")):
            raise ValueError("Final measured decisions cannot mix replay or CLI latency")
        traces = result.get("trace", [])
        if not isinstance(traces, list) or any(not isinstance(trace, dict) for trace in traces):
            raise ValueError("Decision traces must be a list of provider call records")
        providers = Counter(trace.get("provider") for trace in traces)
        if set(providers) - {"local", "cloud"}:
            raise ValueError("Every trace requires an explicit local/cloud provider")
        if traces or status == "MEASURED" or any(field in result for field in ("local_calls", "cloud_calls")):
            if providers["local"] != result.get("local_calls") or providers["cloud"] != result.get("cloud_calls"):
                raise ValueError("Trace and decision provider counters differ")
        if any(field in result and not count(result[field]) for field in ("local_calls", "cloud_calls", "tool_calls")):
            raise ValueError("Call counters must be nonnegative integers when recorded")
        if status == "MEASURED":
            calculated = score(sample, result.get("output"))
            if row.get("score") != calculated:
                raise ValueError("Journal score differs from immutable scoring contract")
            for field in ("cloud_calls", "local_calls", "tool_calls"):
                if not count(result.get(field)):
                    raise ValueError("Measured call counters must be nonnegative integers")
            if result.get("latency_ms") is not None and not finite(result["latency_ms"]):
                raise ValueError("Measured latency must be finite and nonnegative")
        else:
            if row.get("score") is not None:
                raise ValueError("NOT_RUN decisions must not contain accuracy scores")
            calculated = None
        decisions[method][sid] = {**row, "score": calculated}
    for sample in samples:
        for method in methods:
            row = decisions[method].get(sample["id"])
            result = row["result"] if row else {}
            calculated = row["score"] if row else None
            normalized.append({"id": sample["id"], "group": sample["group"], "category": sample["category"],
                               "language": sample["language"], "method": method,
                               "status": result.get("status", "MISSING"), "route": result.get("route"),
                               "correct": calculated["correct"] if calculated else None,
                               "critical_error": calculated["critical_error"] if calculated else None,
                               "qa_f1": calculated["qa_f1"] if calculated else None,
                               "numeric_error": calculated["numeric_error"] if calculated else None,
                               "cloud_calls": result.get("cloud_calls"), "local_calls": result.get("local_calls"),
                               "tool_calls": result.get("tool_calls"), "latency_ms": result.get("latency_ms"),
                               "cost_usd": result.get("cost_usd"), "blocked_reason": result.get("blocked_reason"),
                               "output": result.get("output"), "error": result.get("error"),
                               "call_errors": sum(bool(trace.get("error")) for trace in result.get("trace", [])),
                               "degraded_provider": result.get("degraded_provider")})
    return decisions, normalized


def provider_metrics(traces):
    report = {}
    for provider in ("local", "cloud"):
        calls = [trace for trace in traces if trace["provider"] == provider]
        usage = [trace.get("usage") or {} for trace in calls]
        inputs = [value.get("prompt_tokens") for value in usage]
        outputs = [value.get("completion_tokens") for value in usage]
        totals = [value.get("total_tokens") for value in usage]
        reasoning = [(value.get("completion_tokens_details") or {}).get("reasoning_tokens") for value in usage]
        costs = [trace.get("cost_usd") for trace in calls]
        errors = [trace.get("error") for trace in calls if trace.get("error")]
        error_types = Counter(error.get("type", "UNKNOWN") if isinstance(error, dict) else "UNKNOWN" for error in errors)
        timing = [trace.get("timing") or {} for trace in calls]
        ttft = [t.get("first_nonempty_delta_s_client", t.get("ttft_s", t.get("client_ttft_s", t.get("time_to_first_token_seconds")))) for t in timing]
        answer_ttft = [t.get("first_answer_delta_s_client") for t in timing]
        speeds = [t.get("completion_tokens_per_second_client_approx", t.get("approx_output_tokens_per_second", t.get("approx_tps", t.get("tokens_per_second")))) for t in timing]
        report[provider] = {"calls": len(calls), "input_tokens_known_sum": total_known(inputs),
                            "output_tokens_known_sum": total_known(outputs),
                            "total_tokens_reported_known_sum": total_known(totals),
                            "reasoning_tokens_reported_known_sum": total_known(reasoning),
                            "input_usage_coverage_n": sum(finite(v) for v in inputs),
                            "output_usage_coverage_n": sum(finite(v) for v in outputs),
                            "total_usage_coverage_n": sum(finite(v) for v in totals),
                            "reasoning_usage_coverage_n": sum(finite(v) for v in reasoning),
                            "reasoning_observed_calls": sum(bool((trace.get("raw") or {}).get("reasoning_content")) for trace in calls),
                            "reasoning_token_limitation": "reasoning is a reported subset of completion tokens; never added again to output or total tokens; missing reasoning usage is UNKNOWN",
                            "usage_complete": all(finite(a) and finite(b) for a, b in zip(inputs, outputs)),
                            "known_cost_estimate_usd": total_known(costs) if calls else 0.,
                            "known_cost_coverage_n": sum(finite(v) for v in costs),
                            "unknown_cost_calls": sum(not finite(v) for v in costs),
                            "errors": len(errors), "error_types": dict(error_types),
                            "malformed_calls": sum(error_types[k] for k in ("ValueError", "JSONDecodeError", "KeyError", "IndexError", "TypeError")),
                            "timeout_calls": sum(v for k, v in error_types.items() if "Timeout" in k),
                            "incomplete_calls": error_types["IncompleteCompletion"],
                            "transport_calls": sum(v for k, v in error_types.items() if k in ("ConnectError", "ReadError", "WriteError", "RemoteProtocolError", "HTTPStatusError")),
                            "client_ttft_median_s": float(np.median([v for v in ttft if finite(v)])) if any(finite(v) for v in ttft) else None,
                            "client_ttft_coverage_n": sum(finite(v) for v in ttft),
                            "client_first_answer_delta_median_s": float(np.median([v for v in answer_ttft if finite(v)])) if any(finite(v) for v in answer_ttft) else None,
                            "approx_tps_median": float(np.median([v for v in speeds if finite(v)])) if any(finite(v) for v in speeds) else None,
                            "timing_limitation": "client streaming approximation; cloud backend TTFT/TPS UNKNOWN"}
    return report


def policy_summary(rows, target_n):
    measured = [row for row in rows if row["result"]["status"] == "MEASURED"]
    correct = [int(row["score"]["correct"]) for row in measured]
    groups = [row["sample"]["group"] for row in measured]
    # A NOT_RUN policy may already have incurred a local call before its cloud
    # provider was blocked. Preserve all attempted calls and their usage/cost.
    traces = [trace for row in rows for trace in row["result"].get("trace", [])]
    providers = provider_metrics(traces)
    n = len(measured)
    outputs = [row["result"].get("output") or {} for row in measured]
    actions = Counter(output.get("action", "NO_OUTPUT") for output in outputs)
    answered = [row for row in measured if (row["result"].get("output") or {}).get("action") == "ANSWER"]
    qa = [row for row in measured if row["sample"]["scoring"] == "span_em_f1"]
    abstain_gold = [row for row in measured if row["sample"]["expected"]["action"] == "ABSTAIN"]
    cloud = providers["cloud"]
    cost_complete = cloud["usage_complete"] and cloud["unknown_cost_calls"] == 0
    costs = cloud["known_cost_estimate_usd"]
    report = {"target_n": target_n, "measured_n": n, "recorded_not_run_n": len(rows) - n,
              "missing_n": target_n - len(rows), "measurement_coverage": n / target_n,
              "correct": sum(correct), "quality": sum(correct) / n if n else None,
              "quality_cluster": cluster_bootstrap_interval(correct, groups) if n else None,
              "wilson_descriptive_ci95": wilson_interval(sum(correct), n) if n else None,
              "critical_errors": sum(row["score"]["critical_error"] for row in measured),
              "critical_error_rate": sum(row["score"]["critical_error"] for row in measured) / n if n else None,
              "error_decisions": sum(bool(row["result"].get("error")) for row in measured),
              "error_decision_rate": sum(bool(row["result"].get("error")) for row in measured) / n if n else None,
              "call_errors": sum(bool(trace.get("error")) for trace in traces),
              "degraded_provider_decisions": sum(bool(row["result"].get("degraded_provider")) for row in measured),
              "qa_measured_n": len(qa), "qa_em_correct": sum(row["score"]["correct"] for row in qa),
              "qa_em": sum(row["score"]["correct"] for row in qa) / len(qa) if qa else None,
              "qa_f1_mean": float(np.mean([row["score"]["qa_f1"] for row in measured if row["score"]["qa_f1"] is not None])) if any(row["score"]["qa_f1"] is not None for row in measured) else None,
              "route_counts": dict(Counter(row["result"].get("route", "UNKNOWN") for row in measured)),
              "action_counts": dict(actions), "answer_coverage": actions["ANSWER"] / n if n else None,
              "ask_coverage": actions["ASK"] / n if n else None,
              "abstention_rate": actions["ABSTAIN"] / n if n else None,
              "action_coverage_denominator": "measured decisions; missing and NOT_RUN remain separately reported",
              "selective_error_rate": sum(not row["score"]["correct"] for row in answered) / len(answered) if answered else None,
              "gold_abstain_measured_n": len(abstain_gold),
              "correct_abstention_rate": sum(row["score"]["correct"] for row in abstain_gold) / len(abstain_gold) if abstain_gold else None,
              "correct_abstention_status": "MEASURED" if abstain_gold else "UNKNOWN: no measured gold ABSTAIN",
              "cloud_calls": providers["cloud"]["calls"],
              "local_calls": providers["local"]["calls"],
              "tool_calls": sum(row["result"]["tool_calls"] for row in rows if count(row["result"].get("tool_calls"))),
              "cloud_call_rate_measured": sum(row["result"]["cloud_calls"] for row in measured) / n if n else None,
              "latency_measured_end_to_end": latency([row["result"].get("latency_ms") for row in measured]),
              "providers": providers, "cloud_cost_known_total_usd": costs,
              "cloud_cost_usage_complete": cost_complete,
              "cloud_cost_per_1000_measured_usd": costs / target_n * 1000 if n == target_n and cost_complete else None,
              "cloud_cost_per_1000_known_lower_bound_usd": costs / target_n * 1000 if costs is not None and (n != target_n or not cost_complete) else None,
              "cost_rate_denominator": "all frozen target cases; includes any attempted calls in NOT_RUN decisions",
              "cost_limitation": "provider token estimate; unknown usage is not zero; invoice and electricity/depreciation costs unavailable"}
    return report


def paired(decisions, samples, a, b):
    left, right = decisions[a], decisions[b]
    ids = [s["id"] for s in samples if s["id"] in left and s["id"] in right and
           left[s["id"]]["result"]["status"] == right[s["id"]]["result"]["status"] == "MEASURED"]
    if not ids:
        return {"paired_n": 0, "target_n": len(samples), "status": "NOT_RUN"}
    av = [int(left[sid]["score"]["correct"]) for sid in ids]
    bv = [int(right[sid]["score"]["correct"]) for sid in ids]
    groups = [left[sid]["sample"]["group"] for sid in ids]
    critical_a = [int(left[sid]["score"]["critical_error"]) for sid in ids]
    critical_b = [int(right[sid]["score"]["critical_error"]) for sid in ids]
    calls_a = [left[sid]["result"]["cloud_calls"] for sid in ids]
    calls_b = [right[sid]["result"]["cloud_calls"] for sid in ids]
    latency_ids = [sid for sid in ids if finite(left[sid]["result"].get("latency_ms")) and finite(right[sid]["result"].get("latency_ms"))]
    latency_diff = paired_cluster_bootstrap(
        [left[sid]["result"]["latency_ms"] / 1000 for sid in latency_ids],
        [right[sid]["result"]["latency_ms"] / 1000 for sid in latency_ids],
        [left[sid]["sample"]["group"] for sid in latency_ids]) if latency_ids else None
    return {"a": a, "b": b, "paired_n": len(ids), "target_n": len(samples),
            "status": "COMPLETE" if len(ids) == len(samples) else "PARTIAL",
            "quality_a_minus_b": paired_cluster_bootstrap(av, bv, groups),
            "critical_error_a_minus_b": paired_cluster_bootstrap(critical_a, critical_b, groups),
            "cloud_call_reduction_b_minus_a": paired_cluster_bootstrap(calls_b, calls_a, groups),
            "cloud_call_reduction_all_target": sum(vb - va for va, vb in zip(calls_a, calls_b)) / len(samples) if len(ids) == len(samples) else None,
            "latency_a_minus_b_seconds": latency_diff,
            "mcnemar_descriptive": mcnemar_exact(av, bv),
            "critical_interval_limitation": "zero observed discordances can yield degenerate bootstrap CI; does not prove absent population risk" if len(set(np.asarray(critical_a) - np.asarray(critical_b))) == 1 else None}


def hypothesis(primary, hybrid, criteria, full_complete):
    complete_pair = primary.get("status") == "COMPLETE"
    measurements = {
        "quality_noninferiority": primary.get("quality_a_minus_b", {}).get("ci95", [None, None])[0],
        "additional_cloud_call_reduction": primary.get("cloud_call_reduction_all_target"),
        "critical_error_difference": primary.get("critical_error_a_minus_b", {}).get("ci95", [None, None])[1],
        "hybrid_p95_latency": hybrid["latency_measured_end_to_end"]["p95_s"],
    }
    thresholds = {"quality_noninferiority": -criteria["quality_margin"],
                  "additional_cloud_call_reduction": criteria["cloud_call_reduction_pp"],
                  "critical_error_difference": criteria["critical_error_increase_max"],
                  "hybrid_p95_latency": criteria["p95_max_s"]}
    checks = {}
    for name, value in measurements.items():
        available = full_complete and complete_pair and value is not None
        if name == "hybrid_p95_latency":
            available &= hybrid["latency_measured_end_to_end"]["known_n"] == hybrid["target_n"]
        passes = None if value is None else value >= thresholds[name] if name in ("quality_noninferiority", "additional_cloud_call_reduction") else value <= thresholds[name]
        checks[name] = {"value": value, "threshold": thresholds[name],
                        "operator": ">=" if name in ("quality_noninferiority", "additional_cloud_call_reduction") else "<=",
                        "status": "PASS" if available and passes else "FAIL" if available else "UNCERTAIN"}
    evaluable = full_complete and all(check["status"] != "UNCERTAIN" for check in checks.values())
    supported = all(check["status"] == "PASS" for check in checks.values()) if evaluable else None
    return {"primary_contrast": "hybrid minus tool_cloud", "criteria": checks,
            "supported_on_frozen_controlled_sample": supported,
            "status": "EVALUATED" if evaluable else "UNCERTAIN: incomplete measurement or metadata",
            "interpretation": "Failure to demonstrate noninferiority is not proof of inferiority; no agronomic/generalization claim."}


def compute_statistics(records, samples, manifest, protocol):
    target = manifest["target_n"]
    methods = tuple(manifest.get("policies", METHODS))
    if (type(target) is not int or target <= 0 or target != len(samples)
            or len(methods) != len(METHODS) or set(methods) != set(METHODS)
            or manifest["holdout_ids"] != [s["id"] for s in samples]):
        raise ValueError("Dataset, frozen IDs, target count or policies differ")
    if protocol.get("status") != "FROZEN":
        raise ValueError("Analysis requires an explicit FROZEN protocol copy")
    statistic = protocol.get("statistic", {})
    if statistic != {"bootstrap_seed": SEED, "repeats": REPEATS, "unit": "sample.group"}:
        raise ValueError("Frozen bootstrap specification differs from supported contract")
    if protocol.get("criteria") != CRITERIA:
        raise ValueError("Frozen criteria differ from supported final contract")
    decisions, normalized = validate_records(records, samples, methods)
    summaries = {method: policy_summary([decisions[method][s["id"]] for s in samples if s["id"] in decisions[method]], target)
                 for method in methods}
    gold_abstain_target = sum(s["expected"]["action"] == "ABSTAIN" for s in samples)
    for summary in summaries.values():
        summary["gold_abstain_target_n"] = gold_abstain_target
        summary["gold_abstain_measurement_coverage"] = summary["gold_abstain_measured_n"] / gold_abstain_target if gold_abstain_target else None
    complete = all(summary["measured_n"] == target for summary in summaries.values()) and manifest.get("state") in ("completed", "completed_with_errors")
    primary = paired(decisions, samples, "hybrid", "tool_cloud")
    contrasts = {f"{a}_minus_{b}": paired(decisions, samples, a, b) for a, b in
                 (("hybrid", "tool_cloud"), ("local", "cloud"), ("hybrid", "cloud"), ("tool_cloud", "cloud"), ("offline", "hybrid"))}
    categories, languages = [], []
    for method in methods:
        measured = [row for row in decisions[method].values() if row["result"]["status"] == "MEASURED"]
        for key, destination in (("category", categories), ("language", languages)):
            for value in sorted({s[key] for s in samples}):
                sub = [row for row in measured if row["sample"][key] == value]
                target_sub = sum(s[key] == value for s in samples)
                recorded = [row for row in decisions[method].values() if row["sample"][key] == value]
                sub_traces = [trace for row in recorded for trace in row["result"].get("trace", [])]
                sub_qa = [row for row in sub if row["sample"]["scoring"] == "span_em_f1"]
                destination.append({"method": method, key: value, "target_n": target_sub,
                                    "measured_n": len(sub), "measurement_coverage": len(sub) / target_sub,
                                    "not_run_n": len(recorded) - len(sub), "missing_n": target_sub - len(recorded),
                                    "correct": sum(row["score"]["correct"] for row in sub),
                                    "quality": sum(row["score"]["correct"] for row in sub) / len(sub) if sub else None,
                                    "critical_errors": sum(row["score"]["critical_error"] for row in sub),
                                    "error_decisions": sum(bool(row["result"].get("error")) for row in sub),
                                    "call_errors": sum(bool(trace.get("error")) for trace in sub_traces),
                                    "cloud_calls": sum(trace["provider"] == "cloud" for trace in sub_traces),
                                    "local_calls": sum(trace["provider"] == "local" for trace in sub_traces),
                                    "route_counts": dict(Counter(row["result"].get("route", "UNKNOWN") for row in sub)),
                                    "action_counts": dict(Counter((row["result"].get("output") or {}).get("action", "NO_OUTPUT") for row in sub)),
                                    "qa_measured_n": len(sub_qa),
                                    "qa_em": sum(row["score"]["correct"] for row in sub_qa) / len(sub_qa) if sub_qa else None,
                                    "qa_f1_mean": float(np.mean([row["score"]["qa_f1"] for row in sub_qa])) if sub_qa else None,
                                    "latency_mean_s": latency([row["result"].get("latency_ms") for row in sub])["mean_s"]})
    traced_cloud = sum(summary["providers"]["cloud"]["calls"] for summary in summaries.values())
    actual_cloud = manifest.get("cloud_calls_actual")
    if count(actual_cloud) and actual_cloud < traced_cloud:
        raise ValueError("Manifest cloud attempts below journal trace count")
    pending = actual_cloud - traced_cloud if count(actual_cloud) else None
    traced_local = sum(summary["providers"]["local"]["calls"] for summary in summaries.values())
    actual_local = manifest.get("local_calls_actual")
    if count(actual_local) and actual_local < traced_local:
        raise ValueError("Manifest local attempts below journal trace count")
    report = {"status": "COMPLETE_FROZEN_CONTROLLED_RUN" if complete else "PARTIAL_NOT_CONFIRMATORY",
              "target_n": target, "source_groups": len({s["group"] for s in samples}),
              "statistics": {"bootstrap_seed": SEED, "repeats": REPEATS, "unit": "sample.group", "estimand": "per-row mean"},
              "summary": summaries, "paired": contrasts, "category": categories, "language": languages,
              "hypothesis": hypothesis(primary, summaries["hybrid"], protocol["criteria"], complete),
              "actual_cloud_attempts_manifest": actual_cloud, "cloud_traces_journaled": traced_cloud,
              "unjournaled_cloud_attempts_unknown_usage_cost": pending,
              "actual_local_attempts_manifest": actual_local, "local_traces_journaled": traced_local,
              "unjournaled_local_attempts_unknown_usage": actual_local - traced_local if count(actual_local) else None,
              "resource_peak_total_scope": manifest.get("resource_summary"),
              "resource_limitation": "sampled total GPU/system memory, not per-policy private allocations",
              "model_load_metadata": manifest.get("local_load_metadata"),
              "prices_and_provider": manifest.get("cloud"), "provider_invoice_obtained": False,
              "scientific_limitations": ["AI-assisted QA translations: human validation PENDING", "Manual audit PENDING",
                                          "Wilson/McNemar descriptive under correlated source/family variants",
                                          "Substring grounding is neither calibrated confidence nor factual correctness"]}
    pending_local = actual_local - traced_local if count(actual_local) else None
    if pending or pending_local:
        report["status"] = "PARTIAL_NOT_CONFIRMATORY"
        report["hypothesis"] = hypothesis(primary, summaries["hybrid"], protocol["criteria"], False)
        if pending:
            for row in summaries.values():
                row["cloud_cost_per_1000_measured_usd"] = None
                row["cloud_cost_per_1000_known_lower_bound_usd"] = row["cloud_cost_known_total_usd"] / target * 1000 if row["cloud_cost_known_total_usd"] is not None else None
                row["billing_status"] = "UNKNOWN: unjournaled cloud attempts cannot be attributed to a policy without attempts log"
    return report, normalized, decisions


def eligibility(sample):
    request = public_request(sample)
    gate = hard_gate(request)
    if gate:
        return "hard_gate:" + gate["route"]
    return "context_reader_eligible" if request.get("context", "").strip() else "direct_cloud_eligible; offline_abstain_eligible"


def manual_rows(samples, decisions):
    selected = [sample for category in sorted({s["category"] for s in samples})
                for sample in [s for s in samples if s["category"] == category][:5]]
    result = []
    for sample in selected:
        row = {"id": sample["id"], "group": sample["group"], "category": sample["category"],
               "source": sample.get("source", sample.get("provenance")), "language": sample["language"],
               "question": sample["input"], "context": sample.get("context", ""), "inputs": sample.get("inputs", {}),
               "expected": sample["expected"], "expected_eligibility_from_public_inputs": eligibility(sample)}
        for method in ("local", "cloud", "hybrid"):
            decision = decisions[method].get(sample["id"])
            measured = decision and decision["result"]["status"] == "MEASURED"
            row[method + "_actual_output"] = decision["result"].get("output") if measured else "NOT_RUN"
            row[method + "_correct"] = decision["score"]["correct"] if measured else None
            row[method + "_score"] = decision["score"] if measured else None
        row["notes"] = "human audit PENDING; eligibility uses public request only, no gold label oracle; AI translation validation PENDING"
        result.append(row)
    return result


def write_json_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def write_csv_new(path, rows):
    if not rows:
        return
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else
                         "UNKNOWN" if value is None else value for key, value in row.items()} for row in rows)


def plots(directory, report):
    os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.5))
    for method, row in report["summary"].items():
        if row["quality"] is None:
            continue
        x, y = row["cloud_call_rate_measured"] * 100, row["quality"] * 100
        ci = row["quality_cluster"]["ci95"]
        axes[0].errorbar(x, y, yerr=[[max(0., y - ci[0] * 100)], [max(0., ci[1] * 100 - y)]], fmt="o", capsize=3)
        axes[0].annotate(f"{method} ({row['measured_n']}/{row['target_n']})", (x, y), xytext=(4, 4), textcoords="offset points", fontsize=8)
    axes[0].set(xlabel="Actual cloud calls / measured cases (%)", ylabel="Correctness + cluster 95% CI (%)", xlim=(-5, 105), ylim=(-5, 105))
    methods = list(report["summary"])
    x = np.arange(len(methods))
    for offset, field, label in ((-.18, "p50_s", "p50"), (.18, "p95_s", "p95")):
        values = [report["summary"][m]["latency_measured_end_to_end"][field] for m in methods]
        axes[1].bar(x + offset, [v if v is not None else np.nan for v in values], width=.36, label=label)
    axes[1].set(xticks=x, xticklabels=methods, ylabel="Measured end-to-end latency (s)")
    axes[1].tick_params(axis="x", rotation=25)
    axes[1].legend()
    fig.suptitle("Frozen HOME controlled run — " + report["status"])
    fig.tight_layout()
    fig.savefig(directory / "quality_calls_latency.png", dpi=180)
    fig.savefig(directory / "quality_calls_latency.svg")
    plt.close(fig)


def analyze(directory, dataset=None):
    directory = Path(directory).resolve()
    manifest = read_json(directory / "manifest.json")
    if manifest.get("state") == "running":
        raise RuntimeError("Wait for completed or explicitly stopped final journal")
    protocol_path = directory / "protocol_copy.json"
    protocol = read_json(protocol_path)
    if sha(protocol_path) != manifest["protocol_sha256"]:
        raise ValueError("Frozen protocol-copy hash mismatch")
    if dataset is None:
        dataset = protocol.get("dataset_path")
        if not dataset:
            raise ValueError("Supply --dataset pointing to the frozen dataset")
    dataset = Path(dataset)
    if not dataset.is_absolute():
        dataset = ROOT / dataset
    if sha(dataset) != manifest["dataset_sha256"]:
        raise ValueError("Frozen dataset hash mismatch")
    if protocol.get("dataset_sha256") != manifest["dataset_sha256"]:
        raise ValueError("Protocol and manifest dataset versions differ")
    if protocol.get("n") != manifest["target_n"] or protocol.get("holdout_ids") != manifest["holdout_ids"]:
        raise ValueError("Frozen protocol and manifest target IDs differ")
    for relative, expected in manifest.get("code_sha256", {}).items():
        normalized_path = relative.replace("\\", "/")
        if normalized_path in {f"src/agro_route/{name}" for name in ("models.py", "routing.py", "evaluation.py", "tools.py", "benchmark.py", "cli.py")}:
            if sha(ROOT / normalized_path) != expected:
                raise ValueError("Protected current scoring/tool/core differs from final run")
    samples = read_jsonl(dataset)
    source = directory / "raw_decisions.jsonl"
    report, normalized, decisions = compute_statistics(read_jsonl(source), samples, manifest, protocol)
    report["provenance"] = {"run": str(directory.relative_to(ROOT)) if directory.is_relative_to(ROOT) else directory.name,
                            "raw_sha256": sha(source), "manifest_sha256": sha(directory / "manifest.json"),
                            "dataset_sha256": sha(dataset), "protocol_sha256": sha(protocol_path),
                            "analyzer_sha256": sha(Path(__file__)), "analysis_created_utc": datetime.now(timezone.utc).isoformat()}
    report["provenance"]["home_stats_sha256"] = sha(ROOT / "src/agro_route/home_stats.py")
    output = directory / ("analysis_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ") + "_" + uuid.uuid4().hex[:8])
    output.mkdir(exist_ok=False)
    write_json_new(output / "statistics.json", report)
    write_csv_new(output / "normalized.csv", normalized)
    write_csv_new(output / "category.csv", report["category"])
    write_csv_new(output / "language.csv", report["language"])
    write_csv_new(output / "manual30.csv", manual_rows(samples, decisions))
    summary_rows = [{"method": method, "measured_n": row["measured_n"], "target_n": row["target_n"],
                     "recorded_not_run_n": row["recorded_not_run_n"], "missing_n": row["missing_n"],
                     "measurement_coverage": row["measurement_coverage"],
                     "correct": row["correct"], "quality": row["quality"],
                     "quality_ci95": row["quality_cluster"]["ci95"] if row["quality_cluster"] else None,
                     "critical_errors": row["critical_errors"], "critical_error_rate": row["critical_error_rate"],
                     "error_decisions": row["error_decisions"], "call_errors": row["call_errors"],
                     "qa_measured_n": row["qa_measured_n"], "qa_em": row["qa_em"], "qa_f1_mean": row["qa_f1_mean"],
                     "answer_coverage": row["answer_coverage"], "ask_coverage": row["ask_coverage"],
                     "abstention_rate": row["abstention_rate"], "correct_abstention_rate": row["correct_abstention_rate"],
                     "cloud_calls": row["cloud_calls"], "local_calls": row["local_calls"], "tool_calls": row["tool_calls"],
                     "latency_known_n": row["latency_measured_end_to_end"]["known_n"],
                     "latency_mean_s": row["latency_measured_end_to_end"]["mean_s"],
                     "latency_p50_s": row["latency_measured_end_to_end"]["p50_s"],
                     "latency_p95_s": row["latency_measured_end_to_end"]["p95_s"],
                     "cloud_cost_known_usd": row["cloud_cost_known_total_usd"],
                     "cost_per1000_complete_usd": row["cloud_cost_per_1000_measured_usd"],
                     "cost_per1000_known_lower_bound_usd": row["cloud_cost_per_1000_known_lower_bound_usd"]}
                    | {f"{provider}_{field}": row["providers"][provider][field]
                       for provider in ("local", "cloud") for field in
                       ("input_tokens_known_sum", "output_tokens_known_sum", "total_tokens_reported_known_sum",
                        "reasoning_tokens_reported_known_sum", "input_usage_coverage_n", "output_usage_coverage_n",
                        "total_usage_coverage_n", "reasoning_usage_coverage_n", "usage_complete", "errors",
                        "known_cost_coverage_n", "unknown_cost_calls")}
                    for method, row in report["summary"].items()]
    write_csv_new(output / "summary.csv", summary_rows)
    paired_rows = [{"contrast": name, "status": value["status"], "paired_n": value["paired_n"],
                    "target_n": value["target_n"], "metric": metric,
                    "estimate": (value.get(metric) or {}).get("estimate"),
                    "ci95": (value.get(metric) or {}).get("ci95"),
                    "n_groups": (value.get(metric) or {}).get("n_groups"),
                    "cloud_call_reduction_all_target": value.get("cloud_call_reduction_all_target")}
                   for name, value in report["paired"].items() for metric in
                   ("quality_a_minus_b", "critical_error_a_minus_b", "cloud_call_reduction_b_minus_a", "latency_a_minus_b_seconds")]
    write_csv_new(output / "paired.csv", paired_rows)
    write_csv_new(output / "hypothesis.csv", [{"criterion": name, **value} for name, value in report["hypothesis"]["criteria"].items()])
    plots(output, report)
    print("ANALYSIS " + str(output))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--dataset", type=Path)
    arguments = parser.parse_args()
    analyze(arguments.run_directory, arguments.dataset)
