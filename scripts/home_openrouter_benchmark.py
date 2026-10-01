"""Explicit zero-price :free OpenRouter DEV pilot. No paid/dynamic fallback."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import time
import uuid

import httpx

from agro_route.evaluation import score
from agro_route.home_config import resolve_api_key
from agro_route.models import SYSTEM_PROMPT, parse_output, public_request

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://openrouter.ai/api/v1"
ENDPOINT = BASE + "/chat/completions"
DEFAULT_MODELS = ["nvidia/nemotron-3-super-120b-a12b:free", "google/gemma-4-26b-a4b-it:free", "qwen/qwen3.8-27b:free"]
SCHEMA = {"type": "object", "additionalProperties": False,
          "required": ["action", "answer", "numeric", "unit", "tool"],
          "properties": {"action": {"type": "string", "enum": ["ANSWER", "ASK_FOR_DATA", "ABSTAIN"]},
                         "answer": {"type": "string"}, "numeric": {"type": ["number", "null"]},
                         "unit": {"type": ["string", "null"]}, "tool": {"type": ["string", "null"]}}}


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def redact(value, key):
    if isinstance(value, str):
        return value.replace(key, "[REDACTED]") if key else value
    if isinstance(value, dict):
        return {redact(k, key): redact(v, key) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, key) for v in value]
    return value


def zero_price(value):
    try:
        price = Decimal(str(value))
        return price.is_finite() and price == 0
    except InvalidOperation:
        return False


def validate_model(model_id, catalog):
    if not model_id.endswith(":free") or model_id not in catalog:
        raise ValueError("Only exact catalog :free model identifiers allowed")
    model = catalog[model_id]
    price = model.get("pricing", {})
    if not all(zero_price(price.get(k)) for k in ("prompt", "completion")):
        raise ValueError("Model input/output pricing must be explicitly zero")
    if "request" in price and not zero_price(price["request"]):
        raise ValueError("Nonzero per-request pricing rejected")
    if "text" not in model.get("architecture", {}).get("output_modalities", []):
        raise ValueError("Text output model required")
    params = model.get("supported_parameters", [])
    if not all(k in params for k in ("temperature", "max_tokens")):
        raise ValueError("Required controls unsupported")
    return model


def request_payload(model, sample):
    params = model.get("supported_parameters", [])
    body = {"model": model["id"], "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(public_request(sample), ensure_ascii=False)}],
            "temperature": 0, "max_tokens": 512, "stream": False,
            "provider": {"allow_fallbacks": False, "require_parameters": True,
                         "max_price": {"prompt": 0, "completion": 0, "request": 0}}}
    if "reasoning" in params:
        body["reasoning"] = {"enabled": False}
    if "response_format" in params and "structured_outputs" in params:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "agricultural_response", "strict": True, "schema": SCHEMA}}
    if "seed" in params:
        body["seed"] = 0
    return body


def safe_quota(client, key):
    try:
        response = client.get(BASE + "/key", headers={"Authorization": "Bearer " + key})
        if response.status_code != 200:
            return {"http_status": response.status_code, "retrieved_utc": now()}
        data = response.json().get("data", {})
        return redact({"http_status": 200, "retrieved_utc": now(), **{k: data.get(k) for k in
                       ("limit", "limit_remaining", "usage", "usage_daily", "is_free_tier", "free_model_daily_requests")}}, key)
    except Exception as exc:
        return {"error": type(exc).__name__, "retrieved_utc": now()}


def normalize(model, sample, raw):
    if "error" in raw:
        raise ValueError("API error inside successful HTTP response")
    choices = raw.get("choices", [])
    text = choices[0].get("message", {}).get("content") if choices else None
    answer = None
    parse_error = None
    try:
        if not isinstance(text, str):
            raise ValueError("No text answer")
        answer = parse_output(text)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        parse_error = type(exc).__name__
    usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
    cost = usage.get("cost")
    if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost):
        cost = None
    if cost is not None and cost != 0:
        raise ValueError("Unexpected nonzero reported cost; stop immediately")
    return {"model_requested": model["id"], "model_reported": raw.get("model"), "provider_reported": raw.get("provider"),
            "answer_text": text, "normalized_answer": answer, "parse_error": parse_error,
            "scoring": score(sample, answer), "usage": usage, "reported_actual_cost_usd": cost,
            "catalog_estimated_cost_usd": 0.0, "ttft_seconds": None, "tokens_per_second": None,
            "metrics_note": "UNKNOWN: nonstream response does not provide server TTFT or generation TPS",
            "resource_vram_ram_gpu_offload": "N/A: remote service",
            "grammar": "requested_strict_json_schema" if "response_format" in request_payload(model, sample) else "NONE: prompt-only JSON",
            "finish_reason": choices[0].get("finish_reason") if choices else None}


def execute_model(model, samples, *, client, key, output, progress, min_interval=3.1):
    rows, stop_reason = [], None
    for sample in samples:
        remaining = min_interval - (time.monotonic() - progress[0])
        if remaining > 0:
            time.sleep(remaining)
        progress[0] = time.monotonic()
        row = {"id": sample["id"], "language": sample.get("language"), "category": sample["category"],
               "group_id": sample.get("group_id"), "model_requested": model["id"], "error": None}
        started = time.perf_counter()
        try:
            response = client.post(ENDPOINT, headers={"Authorization": "Bearer " + key}, json=request_payload(model, sample))
            row["latency_ms"] = (time.perf_counter()-started)*1000
            row["http_status"] = response.status_code
            if response.status_code != 200:
                row["error"] = "HTTP_" + str(response.status_code)
                row["rate_limit"] = {k: response.headers.get(k) for k in ("x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset", "retry-after") if response.headers.get(k) is not None}
                # No body logging on HTTP failures; no automatic paid/free retries.
                stop_reason = row["error"]
            else:
                raw = response.json()
                row["raw"] = redact(raw, key)
                row.update(normalize(model, sample, raw))
        except Exception as exc:
            row["latency_ms"] = (time.perf_counter()-started)*1000
            row["error"] = type(exc).__name__
            stop_reason = row["error"]
        safe_row = redact(row, key)
        rows.append(safe_row)
        with (output / "raw.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(safe_row, ensure_ascii=False) + "\n")
        print(json.dumps({k: safe_row.get(k) for k in ("model_requested", "id", "http_status", "scoring", "latency_ms", "parse_error", "error", "reported_actual_cost_usd")}, ensure_ascii=True), flush=True)
        if stop_reason:
            break
    return rows, stop_reason


def summarize(model_id, rows):
    completed = [r for r in rows if r.get("http_status") == 200 and "scoring" in r]
    latencies = sorted(r["latency_ms"] for r in completed)
    def percentile(q):
        if not latencies:
            return None
        pos = (len(latencies)-1)*q
        lo, hi = int(pos), min(int(pos)+1, len(latencies)-1)
        return latencies[lo] + (latencies[hi]-latencies[lo])*(pos-lo)
    return {"model": model_id, "cases": len(rows), "correct": sum(r.get("scoring", {}).get("correct") is True for r in rows),
            "successful_generations": len(completed),
            "quality_accuracy": sum(r.get("scoring", {}).get("correct") is True for r in completed)/len(completed) if completed else None,
            "errors": sum(r.get("error") is not None for r in rows), "structured_failures": sum(r.get("parse_error") is not None for r in rows),
            "p50_latency_ms": statistics.median(latencies) if latencies else None, "p95_latency_ms": percentile(.95),
            "reported_actual_cost_usd": sum(r["reported_actual_cost_usd"] for r in rows) if rows and all(r.get("reported_actual_cost_usd") is not None for r in rows) else None,
            "catalog_estimated_cost_usd": 0.0, "providers_reported": sorted({r["provider_reported"] for r in rows if r.get("provider_reported")}),
            "input_tokens": sum(r.get("usage", {}).get("prompt_tokens") or 0 for r in rows),
            "output_tokens": sum(r.get("usage", {}).get("completion_tokens") or 0 for r in rows),
            "ttft_seconds": None, "tokens_per_second": None, "resource_vram_ram": "N/A: remote service",
            "by_language": {lang: {"cases": sum(r["language"] == lang for r in rows), "correct": sum(r["language"] == lang and r.get("scoring", {}).get("correct") is True for r in rows)} for lang in ("en", "ru")},
            "by_category": {cat: {"cases": sum(r["category"] == cat for r in rows), "correct": sum(r["category"] == cat and r.get("scoring", {}).get("correct") is True for r in rows)} for cat in sorted({r["category"] for r in rows})}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pilot-only", action="store_true", help="Only three already-selected DEV cases per model")
    args = parser.parse_args()
    if not 1 <= len(args.models) <= 3 or len(set(args.models)) != len(args.models):
        raise SystemExit("One to three distinct explicit model IDs required")
    key, source = resolve_api_key("openrouter", env_path=ROOT/".env")
    if not key:
        raise SystemExit("OpenRouter credential missing; no calls made")
    spec = importlib.util.spec_from_file_location("_home_pc_benchmark_samples", ROOT/"scripts/home_pc_benchmark.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    samples = helper.choose_samples(12)
    # Three category/language checks first; later requests use remaining same DEV12.
    pilot = [samples[i] for i in (1, 2, 9)]
    remaining = [sample for sample in samples if sample not in pilot]
    output = args.output or ROOT/"results"/("20261001_"+datetime.now(timezone.utc).strftime("%H%M%SZ")+"_"+uuid.uuid4().hex[:8]+"_openrouter_free")
    output.mkdir(parents=True, exist_ok=False)
    with httpx.Client(timeout=60, follow_redirects=False) as client:
        response = client.get(BASE+"/models")
        if response.status_code != 200:
            write(output/"failure.json", {"stage": "public_catalog", "http_status": response.status_code})
            raise SystemExit("Catalog unavailable; no inference made")
        catalog_raw = response.json()
        write(output/"catalog.json", {"retrieved_utc": now(), "url": BASE+"/models", "catalog": catalog_raw})
        catalog = {m["id"]: m for m in catalog_raw["data"]}
        models = [validate_model(model_id, catalog) for model_id in args.models]
        write(output/"samples_dev.json", samples)
        write(output/"config.json", {"status": "DEVELOPMENT_ONLY", "created_utc": now(), "endpoint": ENDPOINT,
              "credential_source": source, "models": models, "temperature": 0, "max_tokens": 512,
              "system_prompt": SYSTEM_PROMPT, "pilot_ids": [s["id"] for s in pilot], "sample_ids": [s["id"] for s in samples],
              "minimum_interval_seconds": 3.1, "paid_fallback": False, "dynamic_router": False, "automatic_retries": 0,
              "benchmark_sha256": hashlib.sha256((ROOT/"data/benchmark.jsonl").read_bytes()).hexdigest(),
              "requests": {model["id"]: request_payload(model, samples[0]) for model in models},
              "privacy": "Only already-public benchmark text; account/provider privacy policy preserved; no data collection setting changed"})
        quota_before = safe_quota(client, key)
        write(output/"quota_before.json", quota_before)
        print(str(output.relative_to(ROOT)), flush=True)
        if quota_before.get("http_status") in (401, 403, 429):
            write(output/"summary.json", {"status": "NOT_RUN", "reason": "Credential/quota preflight rejected", "http_status": quota_before["http_status"], "successful_generations": 0})
            raise SystemExit("Credential/quota preflight rejected; no inference made")
        quota_left = (quota_before.get("free_model_daily_requests") or {}).get("remaining")
        planned = len(models)*(3 if args.pilot_only else 12)
        if isinstance(quota_left, int) and quota_left < planned:
            write(output/"summary.json", {"status": "NOT_RUN", "reason": "Insufficient reported free quota", "remaining": quota_left, "planned": planned})
            raise SystemExit("Insufficient free quota; no inference made")
        summaries, stop_reason = [], None
        progress = [0.0]
        for model in models:
            rows, stop_reason = execute_model(model, pilot, client=client, key=key, output=output, progress=progress)
            pilot_success = len(rows) == 3 and all(r["error"] is None and r.get("parse_error") is None for r in rows)
            if pilot_success and not args.pilot_only:
                extra, stop_reason = execute_model(model, remaining, client=client, key=key, output=output, progress=progress)
                rows.extend(extra)
            summaries.append(summarize(model["id"], rows))
            write(output/"summary.json", {"status": "DEVELOPMENT_ONLY", "models": summaries, "stop_reason": stop_reason, "final_holdout": "NOT RUN"})
            if stop_reason:
                break
        write(output/"quota_after.json", safe_quota(client, key))
    print(json.dumps({"models": summaries, "stop_reason": stop_reason}, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
