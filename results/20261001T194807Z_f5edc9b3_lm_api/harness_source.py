"""Append-only, sequential HOME-PC LM Studio structured-output DEV comparison.

Modern OpenAI chat API controls schema/temperature/seed/budget. Native v1 model
listing provides actual load configuration. Streaming timing is client measured;
backend timings remain unknown unless returned by this same completion.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time
import uuid

import httpx
import home_pc_benchmark as old
from agro_route.evaluation import score
from agro_route.home_config import resolve_api_key
from agro_route.models import SYSTEM_PROMPT, parse_output, public_request

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:1234"
SCHEMA = {"type": "object", "properties": {
    "action": {"type": "string", "enum": ["ANSWER", "ASK_FOR_DATA", "ABSTAIN"]},
    "answer": {"type": "string"}, "numeric": {"type": ["number", "null"]},
    "unit": {"type": ["string", "null"]}, "tool": {"type": ["string", "null"]}},
    "required": ["action", "answer", "numeric", "unit", "tool"], "additionalProperties": False}
SKIP_UNSAFE = {"qwen3-coder-next": "Prior two guarded CLI loads failed; no new lower-memory configuration justified",
               "qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive": "Prior CLI load triggered resource guard; no new lower-memory configuration justified"}


def redact(value, secret):
    if isinstance(value, str):
        return value.replace(secret, "[REDACTED]") if secret else value
    if isinstance(value, list):
        return [redact(v, secret) for v in value]
    if isinstance(value, dict):
        return {k: redact(v, secret) for k, v in value.items()}
    return value


def native_models(client, key):
    response = client.get(BASE + "/api/v1/models", headers={"Authorization": "Bearer " + key})
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict) or not isinstance(body.get("models"), list):
        raise ValueError("Malformed native model listing")
    # Do not persist response headers or arbitrary provider errors.
    return body["models"]


def payload(identifier, sample, reasoning_effort=None):
    body = {"model": identifier, "messages": [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content": json.dumps(public_request(sample), ensure_ascii=False)}],
            "temperature": 0, "top_p": 1, "seed": 42, "max_tokens": 512,
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "agro_route_answer", "strict": True, "schema": SCHEMA}},
            "stream": True, "stream_options": {"include_usage": True}}
    if reasoning_effort is not None:
        body["reasoning_effort"] = reasoning_effort
    return body


def finite_nonnegative(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def consume_sse(lines, started, clock=time.perf_counter):
    events, content, reasoning = [], [], []
    first_any = first_answer = first_reasoning = last_any = None
    usage, backend_stats, finish = {}, {}, None
    done, event_error = False, None
    for line in lines:
        if not line or line.startswith(":") or not line.startswith("data:"):
            continue
        received = clock() - started
        data = line[5:].strip()
        if data == "[DONE]":
            done = True
            break
        try:
            envelope = json.loads(data)
        except ValueError:
            events.append({"elapsed_s": received, "unparsed_data": data})
            event_error = "MalformedSSE"
            break
        if not isinstance(envelope, dict):
            raise ValueError("Malformed streaming envelope")
        events.append({"elapsed_s": received, "data": envelope})
        if "error" in envelope:
            event_error = "StreamingProviderError"
        if isinstance(envelope.get("usage"), dict):
            usage = envelope["usage"]
        if isinstance(envelope.get("stats"), dict):
            backend_stats = envelope["stats"]
        for choice in envelope.get("choices", []):
            if not isinstance(choice, dict):
                raise ValueError("Malformed streaming choice")
            delta = choice.get("delta") or {}
            if not isinstance(delta, dict):
                raise ValueError("Malformed streaming delta")
            answer = delta.get("content")
            thought = delta.get("reasoning") or delta.get("reasoning_content")
            if isinstance(answer, str) and answer:
                if first_answer is None:
                    first_answer = received
                content.append(answer)
            if isinstance(thought, str) and thought:
                if first_reasoning is None:
                    first_reasoning = received
                reasoning.append(thought)
            if (isinstance(answer, str) and answer) or (isinstance(thought, str) and thought):
                if first_any is None:
                    first_any = received
                last_any = received
            if choice.get("finish_reason") is not None:
                finish = choice["finish_reason"]
    completion = usage.get("completion_tokens")
    span = last_any - first_any if last_any is not None and first_any is not None else None
    client_tps = completion / span if finite_nonnegative(completion) and span and span > 0 else None
    timing = {"first_nonempty_delta_s_client": first_any, "first_answer_delta_s_client": first_answer,
              "first_reasoning_delta_s_client": first_reasoning, "last_nonempty_delta_s_client": last_any,
              "completion_tokens_per_second_client_approx": client_tps,
              "client_tps_method": "reported completion_tokens / (last nonempty delta - first nonempty delta); includes reasoning if counted by server; approximate, first token interval omitted",
              "backend_stats": backend_stats, "backend_ttft_s": backend_stats.get("time_to_first_token_seconds"),
              "backend_tokens_per_second": backend_stats.get("tokens_per_second")}
    return {"events": events, "final_content": "".join(content), "reasoning_content": "".join(reasoning),
            "usage": usage, "finish_reason": finish, "stream_done": done, "event_error": event_error, "timing": timing}


def api_call(client, key, identifier, sample, reasoning_effort=None):
    began = time.perf_counter()
    record = {"output": None, "error": None, "raw": None, "usage": {}, "timing": {}, "cost_usd": 0.0}
    try:
        with client.stream("POST", BASE + "/v1/chat/completions", json=payload(identifier, sample, reasoning_effort),
                           headers={"Authorization": "Bearer " + key}) as response:
            response.raise_for_status()
            raw = consume_sse(response.iter_lines(), began)
        record.update(raw=redact(raw, key), usage=raw["usage"], timing=raw["timing"])
        if raw["event_error"]:
            raise RuntimeError("StreamingProviderError")
        if not raw["stream_done"] or raw["finish_reason"] != "stop":
            record["error"] = {"type": "IncompleteCompletion", "finish_reason": raw["finish_reason"], "stream_done": raw["stream_done"]}
        else:
            answer = parse_output(raw["final_content"])
            if set(answer) != set(SCHEMA["required"]) or any(answer[k] is not None and not isinstance(answer[k], str) for k in ("unit", "tool")):
                raise ValueError("Structured schema mismatch")
            record["output"] = answer
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, RuntimeError) as exc:
        record["error"] = {"type": type(exc).__name__, "http_status": getattr(getattr(exc, "response", None), "status_code", None)}
    record["latency_ms"] = (time.perf_counter() - began) * 1000
    return redact(record, key)


def summarize(rows):
    latencies = [r["local"]["latency_ms"] / 1000 for r in rows]
    first = [r["local"]["timing"].get("first_nonempty_delta_s_client") for r in rows]
    speeds = [r["local"]["timing"].get("completion_tokens_per_second_client_approx") for r in rows]
    first = [x for x in first if finite_nonnegative(x)]
    speeds = [x for x in speeds if finite_nonnegative(x)]
    answer_first = [r["local"]["timing"].get("first_answer_delta_s_client") for r in rows]
    answer_first = [x for x in answer_first if finite_nonnegative(x)]
    reasoning_tokens = [(r["local"]["usage"].get("completion_tokens_details") or {}).get("reasoning_tokens") for r in rows]
    reasoning_tokens = [x for x in reasoning_tokens if finite_nonnegative(x)]
    token_totals = {field: {"total": sum(values), "coverage": len(values)} for field in ("prompt_tokens", "completion_tokens", "total_tokens")
                    if (values := [r["local"]["usage"][field] for r in rows if finite_nonnegative(r["local"]["usage"].get(field))])}
    return {"n": len(rows), "correct": sum(r["score"]["correct"] for r in rows),
            "quality": sum(r["score"]["correct"] for r in rows) / len(rows) if rows else None,
            "errors": sum(bool(r["local"]["error"]) for r in rows),
            "latency_mean_s": statistics.mean(latencies) if rows else None,
            "latency_p50_s": statistics.median(latencies) if rows else None,
            "latency_p95_s": float(old.np.quantile(latencies, .95)) if rows else None,
            "client_first_delta_p50_s": statistics.median(first) if first else None,
            "client_first_answer_delta_p50_s": statistics.median(answer_first) if answer_first else None,
            "client_completion_tps_approx_p50": statistics.median(speeds) if speeds else None,
            "client_timing_coverage": {"first_delta": len(first), "first_answer_delta": len(answer_first), "approx_tps": len(speeds)},
            "reasoning_tokens_reported": {"total": sum(reasoning_tokens), "coverage": len(reasoning_tokens)},
            "token_totals": token_totals, "usage_coverage_n": sum(bool(r["local"]["usage"]) for r in rows),
            "reasoning_observed_n": sum(bool((r["local"].get("raw") or {}).get("reasoning_content")) for r in rows),
            "by_category": {cat: {"n": len(sub), "correct": sum(r["score"]["correct"] for r in sub)} for cat in sorted({r["sample"]["category"] for r in rows}) if (sub := [r for r in rows if r["sample"]["category"] == cat])},
            "by_language": {lang: {"n": len(sub), "correct": sum(r["score"]["correct"] for r in sub)} for lang in sorted({r["sample"]["language"] for r in rows}) if (sub := [r for r in rows if r["sample"]["language"] == lang])}}


def run(n, models, reasoning_profile="default"):
    unknown = set(models) - {key for key, _ in old.CANDIDATES}
    if unknown:
        raise ValueError("Unknown installed text model selection")
    key, source = resolve_api_key("local", env_path=ROOT / ".env")
    if not key:
        raise RuntimeError("Configure LOCAL_API_KEY in project .env")
    directory = ROOT / "results" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8] + "_lm_api")
    directory.mkdir(exist_ok=False)
    samples = old.choose_samples(n)
    client = httpx.Client(timeout=120, trust_env=False)
    catalog = native_models(client, key)
    if any(m.get("loaded_instances") for m in catalog):
        client.close()
        raise RuntimeError("An existing model instance is loaded; do not alter another task's model")
    inventory = old.cli_json("ls", "--json")
    manifest = {"run_id": directory.name, "started_utc": old.now(), "state": "running", "phase": "development_only",
                "transport": "modern_openai_chat_stream", "endpoint": "/v1/chat/completions", "credential_source": source,
                "dataset_split": "old_dev", "sample_ids": [s["id"] for s in samples],
                "dataset_sha256": hashlib.sha256((ROOT / "data/benchmark.jsonl").read_bytes()).hexdigest(),
                "prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(), "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "historical_harness_sha256": hashlib.sha256(Path(old.__file__).read_bytes()).hexdigest(),
                "core_source_sha256": {name: hashlib.sha256((ROOT / "src/agro_route" / name).read_bytes()).hexdigest() for name in ("models.py", "routing.py", "evaluation.py", "tools.py")},
                "requested_parameters": {"temperature": 0, "top_p": 1, "seed": 42, "max_tokens": 512, "stream": True, "stream_options": {"include_usage": True}, "response_format": payload("unused", samples[0])["response_format"]},
                "reasoning_profile": reasoning_profile,
                "reasoning_control": "default: no field; off-or-low: experimental chat reasoning_effort=none when native off allowed, low for GPT-OSS; not listed in public chat parameter docs, effects evaluated from returned reasoning deltas/usage",
                "context": 4096, "parallel": 1, "hidden_warmups": 0, "cloud_calls": 0, "models": {},
                "execution_context": "Local GPU inference sequential; separate Mercury/OpenRouter HTTP experiments may run concurrently in CPU processes. Whole-system RAM/device VRAM includes other applications; host is not isolated.",
                "limits": ["DEV only; no final holdout", "Client first delta includes input processing and HTTP wall time", "Client TPS approximate, not native backend decode speed", "Whole-device/system resources sampled, not per-model allocation", "Native offloaded layer count UNKNOWN unless explicitly exposed"]}
    old.write(directory / "samples_dev.json", samples)
    old.write(directory / "catalog_before.json", redact(catalog, key))
    old.write(directory / "cli_inventory.json", inventory)
    old.write(directory / "manifest.json", manifest)
    (directory / "system_prompt.txt").write_text(SYSTEM_PROMPT, encoding="utf-8")
    (directory / "harness_source.py").write_bytes(Path(__file__).read_bytes())
    try:
        for model_key, gpu in old.CANDIDATES:
            if model_key not in models:
                continue
            meta = {"requested_offload_ratio": gpu, "actual_offloaded_layers": "UNKNOWN", "load_attempted": False, "load_success": False}
            manifest["models"][model_key] = meta
            if model_key in SKIP_UNSAFE:
                meta.update(state="NOT_RUN_PRIOR_RESOURCE_GUARD", reason=SKIP_UNSAFE[model_key])
                old.write(directory / "manifest.json", manifest)
                print(json.dumps({"model": model_key, "state": meta["state"]}), flush=True)
                continue
            identifier = "home-api-" + uuid.uuid4().hex[:8] + "-" + model_key
            monitor, rows = old.Monitor(), []
            try:
                with monitor:
                    args = [old.LMS, "load", model_key, "--context-length", "4096", "--parallel", "1", "--gpu", gpu, "--identifier", identifier, "--yes"]
                    estimate = old.command([*args, "--estimate-only"])
                    meta["estimate_returncode"] = estimate.returncode
                    (directory / (model_key + "_estimate.txt")).write_text(old.ANSI.sub("", estimate.stdout + "\n" + estimate.stderr), encoding="utf-8")
                    if estimate.returncode:
                        raise RuntimeError("Resource estimate failed")
                    meta["load_attempted"] = True
                    started = time.perf_counter()
                    load = old.guarded_load(args, directory / (model_key + "_load.txt"), meta)
                    meta.update(cold_load_wall_s=time.perf_counter() - started, load_success=load.returncode == 0)
                    if load.returncode:
                        raise RuntimeError("Guarded load returned nonzero")
                    state = native_models(client, key)
                    matches = [(m, instance) for m in state for instance in m.get("loaded_instances", []) if instance.get("id") == identifier]
                    if len(matches) != 1:
                        raise RuntimeError("Own loaded instance not confirmed by native API")
                    native, instance = matches[0]
                    meta.update(native_model_metadata=redact(native, key), actual_load_config=instance.get("config"), own_instance_id=identifier)
                    allowed = ((native.get("capabilities") or {}).get("reasoning") or {}).get("allowed_options", [])
                    effort = ("none" if "off" in allowed else "low" if native.get("architecture") == "gpt-oss" else None) if reasoning_profile == "off-or-low" else None
                    meta["reasoning_effort_requested"] = effort
                    meta["reasoning_effort_documentation"] = "Experimental chat mapping; validate actual channels/usage, not a documented native request"
                    if instance.get("config", {}).get("context_length") != 4096 or instance.get("config", {}).get("parallel") != 1:
                        raise RuntimeError("Requested controlled load configuration not confirmed")
                    with (directory / (model_key + "_raw.jsonl")).open("x", encoding="utf-8") as handle:
                        for i, sample in enumerate(samples):
                            headroom = old.resource_headroom()
                            if headroom["ram_available_gib"] < 2 or headroom["gpu_free_mib"] < 512:
                                meta["resource_guard_stop"] = headroom
                                raise RuntimeError("Resource headroom too low before inference")
                            result = api_call(client, key, identifier, sample, effort)
                            row = {"sample": sample, "local": result, "score": score(sample, result["output"])}
                            handle.write(json.dumps(row, ensure_ascii=False) + "\n"); handle.flush(); rows.append(row)
                            print(json.dumps({"model": model_key, "case": i + 1, "n": n, "correct": row["score"]["correct"], "latency_s": round(result["latency_ms"] / 1000, 3), "error": result["error"], "usage": result["usage"]}), flush=True)
                            if effort == "none" and (result.get("raw") or {}).get("reasoning_content"):
                                meta["early_stop"] = "Experimental reasoning-off request still returned reasoning; preserve diagnostic without more inference"
                                meta["experimental_reasoning_control_failed"] = True
                                break
                            if sum(bool(r["local"]["error"]) for r in rows) >= 4:
                                meta["early_stop"] = "four errors; no automatic per-sample retries"
                                break
            except (RuntimeError, ValueError, OSError, old.subprocess.TimeoutExpired, httpx.HTTPError) as exc:
                meta["phase_error"] = {"type": type(exc).__name__}
            finally:
                meta.update(monitor.summary()); meta["summary"] = summarize(rows)
                old.write(directory / (model_key + "_resources.json"), monitor.rows)
                if meta["load_attempted"]:
                    unloaded = old.command([old.LMS, "unload", identifier])
                    meta["unload_success"] = unloaded.returncode == 0 and not any(p["identifier"] == identifier for p in old.cli_json("ps", "--json"))
                    if not meta["unload_success"]:
                        manifest["state"] = "stopped_cleanup_failed"
                        old.write(directory / "manifest.json", redact(manifest, key))
                        raise RuntimeError("Own model cleanup failed; no further model load")
                meta["state"] = "measured" if rows else "NOT_RUN_LOAD_FAILURE"
                old.write(directory / "manifest.json", redact(manifest, key))
                if meta.get("resource_guard_stop") or (meta["load_attempted"] and not meta["load_success"]):
                    manifest["state"] = "stopped_after_uncertain_load"
                    old.write(directory / "manifest.json", redact(manifest, key))
                    raise RuntimeError("Inspect uncertain backend loading before any subsequent model")
            print("MODEL SUMMARY " + json.dumps({"model": model_key, **meta["summary"], **monitor.summary()}), flush=True)
        manifest.update(state="completed", finished_utc=old.now(), catalog_after=redact(native_models(client, key), key))
        old.write(directory / "manifest.json", redact(manifest, key))
    finally:
        client.close()
    print("RESULTS " + directory.name, flush=True)
    return directory


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=12)
    parser.add_argument("--models", nargs="+", default=["gemma-4-26b-a4b-it"])
    parser.add_argument("--all-text-models", action="store_true")
    parser.add_argument("--reasoning-profile", choices=["default", "off-or-low"], default="default")
    args = parser.parse_args()
    run(args.n, [m[0] for m in old.CANDIDATES] if args.all_text_models else args.models, args.reasoning_profile)
