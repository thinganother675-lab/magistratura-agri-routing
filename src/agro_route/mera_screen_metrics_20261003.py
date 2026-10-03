"""Presentation-only multiple-choice scoring for public MERA development data."""
from __future__ import annotations

import json
import math
import re
import statistics


def choice_set(text, allowed):
    """Never translate letters, extract prose, consult gold, or repair meaning."""
    if not isinstance(text, str):
        return (), "invalid_type", False
    candidate = text.strip()
    if candidate.startswith("```json") and candidate.endswith("```"):
        candidate = candidate[7:-3].strip()
    elif candidate.startswith("```") and candidate.endswith("```"):
        candidate = candidate[3:-3].strip()
    contract = False
    try:
        obj = json.loads(candidate)
    except ValueError:
        obj = None
    if isinstance(obj, dict):
        if set(obj) != {"choices"} or not isinstance(obj["choices"], list):
            return (), "invalid_json_contract", False
        if any(not isinstance(x, str) or not re.fullmatch(r"[A-Ha-h]", x.strip()) for x in obj["choices"]):
            return (), "invalid_option", False
        letters = tuple(sorted(set(x.strip().upper() for x in obj["choices"])))
        contract = True
    else:
        candidate = candidate.rstrip(".")
        if not re.fullmatch(r"[A-Ha-h](?:\s*[,;\s]\s*[A-Ha-h])*", candidate):
            return (), "invalid_format", False
        letters = tuple(sorted(set(re.findall(r"[A-H]", candidate.upper()))))
    if not letters:
        return (), "empty_choices", contract
    if not set(letters).issubset(allowed):
        return (), "option_out_of_range", contract
    return letters, "format_only", contract


def set_score(reference, prediction, options):
    gold, issue, _ = choice_set(reference, options)
    pred, pred_status, contract = choice_set(prediction, options)
    valid = bool(gold)
    return {
        "gold_valid": valid, "gold_cardinality": len(gold) if valid else None,
        "gold_issue": issue if not valid else None,
        "prediction_valid": bool(pred), "prediction_cardinality": len(pred),
        "prediction_status": pred_status, "json_contract": contract,
        "strict_set_em": int(gold == pred) if valid else None,
        "strict_set_f1": (2 * len(set(gold) & set(pred)) / (len(gold) + len(pred)) if pred else 0.0) if valid else None,
    }


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def quantile(values, q):
    vals = sorted(x for x in values if finite(x))
    if not vals:
        return None
    point = (len(vals) - 1) * q
    low = int(point)
    return vals[low] + (vals[min(low + 1, len(vals) - 1)] - vals[low]) * (point - low)


def summarize(rows, expected_ids):
    ids = [r["item_id"] for r in rows]
    if len(ids) != len(set(ids)) or not set(ids).issubset(expected_ids):
        raise ValueError("Duplicate or unexpected model result ids")
    scored = [r for r in rows if r["gold_valid"]]
    latencies = [r["latency_s"] for r in rows]
    count = sum(r["strict_set_em"] for r in scored)
    f1_sum = sum(r["strict_set_f1"] for r in scored)
    mean = lambda xs: statistics.mean(xs) if xs else None
    completed_n = sum(bool(r.get("response_received")) and not r.get("error") for r in rows)
    result = {"n_expected": len(expected_ids), "n_attempted": len(rows), "n_completed": completed_n,
        "n_response_received": sum(r.get("response_received", False) for r in rows),
        "n_scored": len(scored), "attempted_coverage": set(ids) == set(expected_ids),
        "complete_coverage": set(ids) == set(expected_ids) and completed_n == len(expected_ids),
        "strict_em_count": count, "strict_f1_sum": f1_sum,
        "strict_set_em": count / len(scored) if scored else None,
        "strict_set_f1": f1_sum / len(scored) if scored else None,
        "conservative_all_n_em": count / len(expected_ids),
        "reference_issues": len(rows) - len(scored),
        "invalid_output": sum(not r["prediction_valid"] for r in rows),
        "json_contract_failure": sum(not r["json_contract"] for r in rows),
        "errors": sum(bool(r.get("error")) for r in rows),
        "timeouts": sum((r.get("error") or {}).get("type", "").endswith("Timeout") for r in rows),
        "latency_p50_s": quantile(latencies, .5), "latency_p95_s": quantile(latencies, .95),
        "latency_mean_s": mean(latencies),
        "ttft_p50_s": quantile([r.get("ttft_s") for r in rows], .5),
        "first_answer_p50_s": quantile([r.get("first_answer_s") for r in rows], .5),
        "client_tps_p50": quantile([r.get("client_tps") for r in rows], .5),
        "backend_tps_p50": quantile([r.get("backend_tps") for r in rows], .5),
        "input_tokens": sum(r.get("input_tokens") or 0 for r in rows),
        "output_tokens": sum(r.get("output_tokens") or 0 for r in rows),
        "usage_coverage": sum(r.get("input_tokens") is not None and r.get("output_tokens") is not None for r in rows),
        "confidence_coverage": sum(r.get("option_token_confidence") is not None for r in rows),
    }
    result["by_domain"] = {}
    for domain in sorted({r["domain"] for r in rows}):
        sub = [r for r in rows if r["domain"] == domain]
        eligible = [r for r in sub if r["gold_valid"]]
        result["by_domain"][domain] = {"n": len(sub), "n_scored": len(eligible),
            "reference_issues": len(sub) - len(eligible),
            "strict_set_em": mean([r["strict_set_em"] for r in eligible]),
            "strict_set_f1": mean([r["strict_set_f1"] for r in eligible])}
    result["by_answer_cardinality"] = {}
    for label, condition in [("single", lambda r: r["gold_cardinality"] == 1),
                              ("multiple", lambda r: r["gold_cardinality"] > 1)]:
        sub = [r for r in scored if condition(r)]
        result["by_answer_cardinality"][label] = {"n": len(sub),
            "strict_set_em": mean([r["strict_set_em"] for r in sub]),
            "strict_set_f1": mean([r["strict_set_f1"] for r in sub]),
            "predicted_single_n": sum(r["prediction_cardinality"] == 1 for r in sub)}
    return result
