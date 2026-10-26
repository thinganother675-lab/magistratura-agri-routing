"""Paired HOME development pilot: Jev typed decisions vs immutable Laya CPU run.

No autoretries, no generative QA, no credential values in artifacts. Only the
fixed official TypeSafe URL is used. Baseline prompts/questions are unchanged.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import time
import uuid

import httpx

from agro_route.home_config import resolve_api_key
from agro_route.home_stats import mcnemar_exact

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "results/jev_local_20261001/cpu_smoke/20261001T191143Z_562a73b3"
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"
INPUT_USD_PER_MILLION = 0.042


def write(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def redact(value, key: str):
    """Remove exact credential occurrence from all persisted response strings."""
    if isinstance(value, str):
        return value.replace(key, "[REDACTED]") if key else value
    if isinstance(value, dict):
        return {redact(k, key): redact(v, key) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, key) for v in value]
    return value


def load_baseline():
    rows = [json.loads(line) for line in (BASELINE / "raw.jsonl").read_text(encoding="utf-8").splitlines() if line]
    questions = json.loads((BASELINE / "questions.json").read_text(encoding="utf-8"))
    if len(rows) != 12 or len({r["id"] for r in rows}) != 12:
        raise ValueError("Expected exact immutable 12-case baseline")
    return rows, questions


def public_payload(case, questions):
    return {"state": case["state"], "model": MODEL, "questions": questions}


def normalize(case, raw):
    if raw.get("model") != MODEL:
        raise ValueError("Pinned model mismatch")
    route = raw["answers"]["route"]["choice"]
    noul = raw["answers"]["missing_data"]["noul"]
    if route not in {"gdd", "vpd", "et0", "precipitation", "abstain", "qa"}:
        raise ValueError("Invalid typed route")
    if isinstance(noul, bool) or not isinstance(noul, (int, float)) or not math.isfinite(noul) or not 0 <= noul <= 1:
        raise ValueError("Invalid noul probability")
    usage = raw.get("usage", {})
    inp, out = usage.get("input_tokens"), usage.get("output_tokens")
    for token_count in (inp, out):
        if token_count is not None and (isinstance(token_count, bool) or not isinstance(token_count, int) or token_count < 0):
            raise ValueError("Invalid token usage")
    return {"route": route, "noul": noul, "predicted_missing_data": noul >= 0.5,
            "correct_route": route == case["gold_route"],
            "correct_missing_data": (noul >= 0.5) == case["gold_missing_data"],
            "model_reported": raw.get("model"), "input_tokens": inp, "output_tokens": out,
            "estimated_cost_usd": inp * INPUT_USD_PER_MILLION / 1_000_000 if inp is not None else None}


def execute(cases, questions, *, client, key, output: Path):
    rows = []
    stop_reason = None
    spend = 0.0
    for case in cases:
        # Official 64k input ceiling bounds one request by USD0.002688.
        if spend + 64_000 * INPUT_USD_PER_MILLION / 1_000_000 > 0.01:
            stop_reason = "PRE_CALL_SPEND_CAP"
            break
        row = {k: case[k] for k in ("id", "language", "state", "gold_route", "gold_missing_data")}
        row.update({"local_route": case.get("route"), "local_correct_route": case.get("correct_route"),
                    "local_correct_missing_data": case.get("correct_missing_data"),
                    "error": None, "correct_route": False, "correct_missing_data": False})
        started = time.perf_counter()
        try:
            response = client.post(ENDPOINT, headers={"Authorization": "Bearer " + key}, json=public_payload(case, questions))
            row["latency_ms"] = (time.perf_counter() - started) * 1000
            row["http_status"] = response.status_code
            if response.status_code != 200:
                row["error"] = "HTTP_" + str(response.status_code)
                stop_reason = row["error"]
            else:
                raw = response.json()
                row["raw"] = redact(raw, key)
                row.update(normalize(case, raw))
                if row["estimated_cost_usd"] is None:
                    stop_reason = "USAGE_UNKNOWN_SPEND_CAP"
                else:
                    spend += row["estimated_cost_usd"]
        except Exception as exc:
            row["latency_ms"] = (time.perf_counter() - started) * 1000
            row["error"] = type(exc).__name__
            stop_reason = row["error"]
        rows.append(redact(row, key))
        with (output / "raw.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(rows[-1], ensure_ascii=False) + "\n")
        print(json.dumps({k: row.get(k) for k in ("id", "route", "correct_route", "correct_missing_data", "latency_ms", "error")}, ensure_ascii=True), flush=True)
        if stop_reason:
            break
    return rows, stop_reason


def percentile(values, q):
    values = sorted(values)
    pos = (len(values) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(values)-1)
    return values[lo] + (values[hi] - values[lo]) * (pos-lo)


def summarize(rows, stop_reason, baseline_summary):
    latencies = [r["latency_ms"] for r in rows]
    only_jev = sum(r["correct_route"] and not r["local_correct_route"] for r in rows)
    only_laya = sum(r["local_correct_route"] and not r["correct_route"] for r in rows)
    complete_usage = all(r.get("input_tokens") is not None for r in rows)
    return {"status": "DEVELOPMENT_ONLY", "planned_cases": 12, "attempted_cases": len(rows),
            "complete": len(rows) == 12 and stop_reason is None, "model_requested": MODEL,
            "models_reported": sorted({r["model_reported"] for r in rows if r.get("model_reported")}),
            "route_correct": sum(r["correct_route"] for r in rows),
            "missing_data_correct": sum(r["correct_missing_data"] for r in rows), "noul_threshold": 0.5,
            "errors": sum(r["error"] is not None for r in rows), "stop_reason": stop_reason,
            "latency_p50_ms": statistics.median(latencies) if latencies else None,
            "latency_p95_ms": percentile(latencies, 0.95) if latencies else None,
            "latency_mean_ms": statistics.mean(latencies) if latencies else None,
            "input_tokens": sum(r.get("input_tokens") or 0 for r in rows),
            "output_tokens": sum(r.get("output_tokens") or 0 for r in rows),
            "estimated_cost_usd": sum(r.get("estimated_cost_usd") or 0 for r in rows) if complete_usage else None,
            "actual_invoice_cost_usd": None, "cost_source": "Official 2026-10-01 models page: USD0.042/M input, output free; not invoice",
            "price_url": "https://docs.typesafe.ai/models", "ttft_seconds": None, "tokens_per_second": None,
            "resource_vram_ram_gpu_offload": "N/A: remote typed decision service", "temperature_seed": "Not exposed by documented typed API",
            "baseline": baseline_summary, "paired_route": {"jev_only_correct": only_jev, "laya_only_correct": only_laya,
                    "difference_proportion": (only_jev-only_laya)/len(rows) if rows else None,
                    "exact_mcnemar": mcnemar_exact([r["correct_route"] for r in rows], [bool(r["local_correct_route"]) for r in rows])},
            "by_language": {lang: {"cases": sum(r["language"] == lang for r in rows),
                                    "route_correct": sum(r["language"] == lang and r["correct_route"] for r in rows),
                                    "missing_data_correct": sum(r["language"] == lang and r["correct_missing_data"] for r in rows)} for lang in ("en", "ru")},
            "limits": ["12 synthetic bilingual development cases; no independent holdout", "Typed routing and missing-data decisions only, not agricultural QA answers", "Probabilities not calibrated on this domain", "Cloud HTTP wall latency includes network; Laya timing excludes loading and warmup", "No retries or architecture integration"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cases, questions = load_baseline()
    key, source = resolve_api_key("jev", env_path=ROOT / ".env")
    if not key:
        raise SystemExit("Jev credential missing; no calls made")
    output = args.output or ROOT / "results" / ("20261001_" + datetime.now(timezone.utc).strftime("%H%M%SZ") + "_" + uuid.uuid4().hex[:8] + "_jevdev")
    output.mkdir(parents=True, exist_ok=False)
    config = {"created_utc": datetime.now(timezone.utc).isoformat(), "endpoint": ENDPOINT,
              "model": MODEL, "credential_source": source, "questions": questions, "cases": 12,
              "maximum_planned_spend_usd": 0.01, "rough_planning_estimate_usd": 0.003024,
              "no_retries": True, "stop_on_any_http_error": True, "split": "dev",
              "baseline_directory": str(BASELINE.relative_to(ROOT)),
              "baseline_sha256": {name: hashlib.sha256((BASELINE / name).read_bytes()).hexdigest() for name in ("raw.jsonl", "summary.json", "questions.json")}}
    write(output / "config.json", config)
    write(output / "questions.json", questions)
    print(str(output.relative_to(ROOT)), flush=True)
    with httpx.Client(timeout=60, follow_redirects=False) as client:
        rows, stop_reason = execute(cases, questions, client=client, key=key, output=output)
    baseline_summary = json.loads((BASELINE / "summary.json").read_text(encoding="utf-8"))
    summary = summarize(rows, stop_reason, baseline_summary)
    write(output / "summary.json", summary)
    import csv
    with (output / "manual_paired_validation.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        columns = ["id", "language", "state", "gold_route", "gold_missing_data", "local_route", "route", "noul", "local_correct_route", "correct_route", "local_correct_missing_data", "correct_missing_data", "latency_ms", "input_tokens", "estimated_cost_usd", "error"]
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({k: summary[k] for k in ("complete", "attempted_cases", "route_correct", "missing_data_correct", "errors", "latency_p50_ms", "input_tokens", "estimated_cost_usd", "by_language")}, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
