# SPDX-License-Identifier: Apache-2.0
"""Small, sequential MERA DEV screen. No TEST fetch, no service submission.

Uses existing LM Studio and Inception credentials internally. Source questions,
references and provider text stay under ignored .runtime/mera. Safe summaries
are written separately. Never calls the historical agricultural JSON scorer.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agro_route.home_config import resolve_api_key
from agro_route.mera_adapter_20261003 import (
    HF_REVISION, MERA_REVISION, diagnostic_set_scores, ensure_restricted_path,
    isolate_dev_references, normalize_options, official_scores, route_local,
    sha256_bytes,
)
import home_pc_benchmark as guards
import home_lm_api_benchmark as native

LOCAL_MODELS = {"gemma-4-26b-a4b-it": "0.70", "qwen3.8-27b": "0.75"}


def now():
    return datetime.now(timezone.utc).isoformat()


def write_new(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as h:
        json.dump(obj, h, ensure_ascii=False, indent=2); h.write("\n")


def select_balanced(items, per_domain=6):
    groups = defaultdict(list)
    for item in items:
        groups[item.domain].append(item)
    selected = []
    for domain in sorted(groups):
        rows = sorted(groups[domain], key=lambda x: x.item_id)
        # Fixed before calls: spread over each DEV domain; no reference selection.
        if len(rows) < per_domain:
            raise ValueError("Insufficient public DEV examples in a domain")
        selected.extend(rows[(i * len(rows)) // per_domain] for i in range(per_domain))
    return selected


def token_confidence(logprobs):
    values = []
    for row in (logprobs if isinstance(logprobs, dict) else {}).get("content", []) or []:
        token, value = row.get("token", "").strip().strip(",;"), row.get("logprob")
        if token in tuple("ABCDEFGH") and isinstance(value, (int, float)) and math.isfinite(value) and value <= 0:
            values.append(value)
    return math.exp(sum(values) / len(values)) if values else None


def call_model(client, url, key, model, item, *, local, prices, cloud_profile="default-medium-128"):
    body = {"model": model, "messages": [{"role": "user", "content": item.prompt}],
            "temperature": 0, "max_tokens": 128, "top_p": 1}
    if local:
        body.update(seed=42, reasoning_effort="none", logprobs=True, top_logprobs=1,
                    chat_template_kwargs={"enable_thinking": False})
    elif cloud_profile == "instant-256":
        body.pop("max_tokens")
        body.update(temperature=.75, reasoning_effort="instant", max_completion_tokens=256)
    elif cloud_profile != "default-medium-128":
        raise ValueError("Unknown cloud development profile")
    started = time.perf_counter()
    raw, error = None, None
    try:
        response = client.post(url, json=body, headers={"Authorization": "Bearer " + key} if key else {})
        response.raise_for_status()
        raw = response.json()
        # Remove a credential if an upstream response ever reflects it.
        raw = native.redact(raw, key)
        choice = raw["choices"][0]
        text = choice["message"].get("content") or ""
        if not isinstance(text, str):
            raise ValueError("Expected textual model content, not content parts")
        normalized = normalize_options(text, item.options)
        confidence = (token_confidence(choice.get("logprobs"))
                      if local and normalized.status == "format_only" and normalized.choices else None)
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        error = {"type": type(exc).__name__, "http_status": getattr(getattr(exc, "response", None), "status_code", None)}
        text, confidence = "", None
        normalized = normalize_options(text, item.options)
    usage = (raw or {}).get("usage") or {}
    if not isinstance(usage, dict):
        usage = {}
    has_usage = all(isinstance(usage.get(k), int) and not isinstance(usage[k], bool) and usage[k] >= 0
                    for k in ("prompt_tokens", "completion_tokens"))
    cost = ((usage["prompt_tokens"] * prices[0] + usage["completion_tokens"] * prices[1]) / 1e6
            if has_usage else None)
    return {"item_id": item.item_id, "split": "dev", "domain": item.domain,
            "prompt_sha256": sha256_bytes(item.prompt.encode()), "requested_model": model,
            "returned_model": (raw or {}).get("model"), "prediction_raw": text,
            "prediction": normalized.canonical if normalized.choices else text.lstrip(),
            "normalization_status": normalized.status, "strict_format": normalized.strict_format,
            "valid_options": bool(normalized.choices), "option_token_confidence": confidence,
            "usage": usage, "cost_usd_estimate": cost, "latency_ms": (time.perf_counter() - started) * 1000,
            "error": error, "raw": raw, "request_parameters": {k: v for k, v in body.items() if k != "messages"}}


def summarize(rows, references, items):
    by_id = {x.item_id: x for x in items}
    official_raw, official_canonical, strict = [], [], []
    domains = defaultdict(list)
    for row in rows:
        reference, options = references[row["item_id"]], by_id[row["item_id"]].options
        a = official_scores(reference, row["prediction_raw"].lstrip())
        b = official_scores(reference, row["prediction"])
        c = diagnostic_set_scores(reference, row["prediction"], options)
        official_raw.append(a); official_canonical.append(b); strict.append(c)
        domains[row["domain"]].append(c)
    mean = lambda xs: statistics.mean(xs) if xs else None
    costs = [r["cost_usd_estimate"] for r in rows if r["cost_usd_estimate"] is not None]
    return {"n": len(rows), "official_compatible_raw_exact_match": mean([x["exact_match"] for x in official_raw]),
            "official_compatible_raw_f1": mean([x["f1"] for x in official_raw]),
            "official_compatible_normalized_exact_match": mean([x["exact_match"] for x in official_canonical]),
            "official_compatible_normalized_f1": mean([x["f1"] for x in official_canonical]),
            "diagnostic_set_exact_match": mean([x["set_exact_match"] for x in strict if x["set_exact_match"] is not None]),
            "diagnostic_set_f1": mean([x["set_f1"] for x in strict if x["set_f1"] is not None]),
            "reference_script_or_format_issues": sum(x["reference_issue"] for x in strict),
            "invalid_options": sum(not r["valid_options"] for r in rows),
            "strict_format_failures": sum(not r["strict_format"] for r in rows),
            "errors": sum(bool(r["error"]) for r in rows),
            "logprob_confidence_available": sum(r["option_token_confidence"] is not None for r in rows),
            "mean_latency_ms": mean([r["latency_ms"] for r in rows]),
            "median_latency_ms": statistics.median([r["latency_ms"] for r in rows]) if rows else None,
            "known_cost_usd_estimate": sum(costs), "unknown_usage_n": len(rows) - len(costs),
            "prompt_tokens_known": sum(r["usage"].get("prompt_tokens", 0) for r in rows),
            "completion_tokens_known": sum(r["usage"].get("completion_tokens", 0) for r in rows),
            "domain_diagnostic_exact_match": {d: mean([x["set_exact_match"] for x in v if x["set_exact_match"] is not None]) for d, v in domains.items()},
            "status": "DEV_ONLY_EXPLORATORY_NOT_OFFICIAL_REMOTE_SCORE"}


def run(args):
    safe = (ROOT / args.study_dir).resolve()
    if not safe.is_relative_to(ROOT / "results"):
        raise ValueError("Study directory must be within results")
    restricted = ensure_restricted_path(ROOT / ".runtime/mera" / safe.name, ROOT)
    restricted.mkdir(parents=True, exist_ok=True)
    dataset_path = ensure_restricted_path(args.dev_rows, ROOT)
    rows = json.loads(dataset_path.read_text(encoding="utf-8"))
    items, refs = isolate_dev_references(rows)
    selected = select_balanced(items)
    ledger = safe / "dev_use_ledger.jsonl"
    # Register each use before processing. No TEST input is ever fetched here.
    profile_suffix = "" if args.provider == "local" or args.cloud_profile == "default-medium-128" else "_" + args.cloud_profile
    event = {"utc": now(), "purpose": "fixed_60_compatibility_and_model_screen", "provider": args.provider,
             "model_key": args.model, "dataset_revision": HF_REVISION, "source_sha256": sha256_bytes(dataset_path.read_bytes()),
             "ids": [x.item_id for x in selected], "n": len(selected), "classification": "DEVELOPMENT_ONLY",
             "cloud_profile": args.cloud_profile if args.provider != "local" else None}
    with ledger.open("a", encoding="utf-8") as f: f.write(json.dumps(event, ensure_ascii=False) + "\n")
    raw_path = restricted / (args.model + profile_suffix + "_raw.jsonl")
    if raw_path.exists():
        raise ValueError("Existing inference journal: no automatic repeat")
    key, source = resolve_api_key(args.provider)
    if not key:
        raise RuntimeError("Existing provider credential missing; no key printed")
    local = args.provider == "local"
    if local and args.model not in LOCAL_MODELS:
        raise ValueError("Reuse only the two measured local candidates")
    if not local and args.model != "mercury-2":
        raise ValueError("One stable cloud identifier only")
    manifest = {**event, "started_utc": now(), "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "uncommitted_source_hashes": {p: sha256_bytes((ROOT / p).read_bytes()) for p in
                 ("scripts/mera_dev_20261003.py", "src/agro_route/mera_adapter_20261003.py")},
                "credential_source_name": source, "mera_revision": MERA_REVISION, "actual_calls": 0,
                "dataset_or_provider_text_in_git": False, "private_test_run": False,
                "input_price_usd_per_m": 0 if local else .25, "output_price_usd_per_m": 0 if local else .75,
                "cloud_spend_cap_usd_estimate": .15 if not local else 0,
                "restrictions": "MERA terms testing only; no model training; no redistribution"}
    snapshot = restricted / "source_snapshots" / (args.model + profile_suffix)
    snapshot.mkdir(parents=True, exist_ok=True)
    for name in manifest["uncommitted_source_hashes"]:
        with (snapshot / Path(name).name).open("xb") as f:
            f.write((ROOT / name).read_bytes())
    measured = []
    identifier = f"mera-dev-{safe.name[-8:]}-{args.model}"
    own_load_attempted = False
    attempted_calls = 0
    url = "http://127.0.0.1:1234/v1/chat/completions" if local else "https://api.inceptionlabs.ai/v1/chat/completions"
    client = httpx.Client(timeout=60, trust_env=not local)
    try:
        if local:
            state = native.native_models(client, key)
            if any(m.get("loaded_instances") for m in state):
                raise RuntimeError("Existing loaded models: retain state, do not unload them")
            load_args = [guards.LMS, "load", args.model, "--context-length", "4096", "--parallel", "1",
                         "--gpu", LOCAL_MODELS[args.model], "--identifier", identifier, "--yes"]
            meta = {}
            estimate = guards.command([*load_args, "--estimate-only"])
            if estimate.returncode:
                raise RuntimeError("Resource estimate failed")
            own_load_attempted = True
            load = guards.guarded_load(load_args, restricted / (args.model + "_load.txt"), meta)
            manifest["load_guard"] = meta
            if load.returncode:
                raise RuntimeError("Guarded load failed")
            matches = [(m, i) for m in native.native_models(client, key) for i in m.get("loaded_instances", []) if i.get("id") == identifier]
            if len(matches) != 1:
                raise RuntimeError("Own instance not confirmed")
            model_meta, instance = matches[0]
            manifest.update(native_model_metadata=native.redact(model_meta, key), load_config=instance.get("config"),
                            quantization=model_meta.get("quantization"), own_instance_id=identifier)
            if (instance.get("config") or {}).get("context_length") != 4096:
                raise RuntimeError("Context length was not confirmed")
        with raw_path.open("x", encoding="utf-8") as handle, (restricted / (args.model + profile_suffix + "_requests_started.jsonl")).open("x", encoding="utf-8") as starts:
            for index, item in enumerate(selected):
                if local:
                    headroom = guards.resource_headroom()
                    if headroom["ram_available_gib"] < 2 or headroom["gpu_free_mib"] < 512:
                        manifest["resource_stop"] = headroom
                        break
                # Conservative byte-based upper bound, before any paid request.
                if not local:
                    output_cap = 256 if args.cloud_profile == "instant-256" else 128
                    upper = (len(item.prompt.encode()) * .25 + output_cap * .75) / 1e6
                    if sum(r["cost_usd_estimate"] or 0 for r in measured) + upper > .15:
                        manifest["budget_stop"] = True; break
                attempted_calls += 1
                starts.write(json.dumps({"item_id": item.item_id, "started_utc": now(),
                             "prompt_sha256": sha256_bytes(item.prompt.encode())}) + "\n"); starts.flush()
                result = call_model(client, url, key, identifier if local else args.model, item,
                                    local=local, prices=(0, 0) if local else (.25, .75), cloud_profile=args.cloud_profile)
                handle.write(json.dumps(result, ensure_ascii=False) + "\n"); handle.flush()
                measured.append(result)
                print(json.dumps({"model": args.model, "dev_progress": f"{index + 1}/{len(selected)}",
                                  "latency_ms": round(result["latency_ms"]), "valid_options": result["valid_options"],
                                  "confidence_available": result["option_token_confidence"] is not None,
                                  "error": result["error"]}), flush=True)
                if result["error"] or (not local and result["cost_usd_estimate"] is None):
                    manifest["stop_reason"] = "No automatic retry after error or missing paid usage"
                    break
                if not local and args.cloud_profile == "instant-256" and len(measured) <= 6 and sum(not r["valid_options"] for r in measured) >= 3:
                    manifest["stop_reason"] = "Three invalid answers during revised cloud compatibility pilot"
                    break
        manifest["actual_calls"] = len(measured)
        manifest["summary"] = summarize(measured, refs, selected)
        manifest["raw_sha256"] = sha256_bytes(raw_path.read_bytes()) if raw_path.exists() else None
    finally:
        manifest["actual_calls"] = len(measured)
        manifest["attempted_calls"] = attempted_calls
        if raw_path.exists():
            manifest["raw_sha256"] = sha256_bytes(raw_path.read_bytes())
        if own_load_attempted:
            try:
                cleanup = guards.command([guards.LMS, "unload", identifier])
                manifest["own_instance_cleanup_success"] = cleanup.returncode == 0 and not any(
                    i.get("id") == identifier for m in native.native_models(client, key) for i in m.get("loaded_instances", []))
            except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, httpx.HTTPError) as exc:
                manifest["own_instance_cleanup_success"] = False
                manifest["cleanup_error_type"] = type(exc).__name__
        client.close()
        manifest["finished_utc"] = now()
        write_new(safe / (args.model + profile_suffix + "_dev_manifest.json"), manifest)
    print(json.dumps({"summary": manifest.get("summary"), "study": safe.name}), flush=True)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-dir", required=True, type=Path)
    parser.add_argument("--dev-rows", required=True, type=Path)
    parser.add_argument("--provider", choices=["local", "mercury"], required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--cloud-profile", choices=["default-medium-128", "instant-256"], default="default-medium-128")
    run(parser.parse_args())
