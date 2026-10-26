# SPDX-License-Identifier: Apache-2.0
"""Versioned free-only supplementary DEV screen; never modifies account settings."""
from __future__ import annotations
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import time
import uuid
from datetime import datetime, timezone
import httpx

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("or_previous", ROOT / "scripts/openrouter_screen_20261002.py")
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)


def scrub(value, secrets):
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[REDACTED]")
        value = re.sub(r"sk-or-v1-[A-Za-z0-9_-]+", "[REDACTED]", value)
        return re.sub(r"(https://openrouter\.ai/[^\s\"']*/keys/)[a-f0-9]{32,}", r"\1[REDACTED_ACCOUNT_KEY_ID]", value)
    if isinstance(value, dict):
        return {scrub(k, secrets): scrub(v, secrets) for k, v in value.items() if k.lower() not in {"authorization", "key", "hash", "label", "creator_user_id"}}
    if isinstance(value, list):
        return [scrub(v, secrets) for v in value]
    return value


def authorized_key(name):
    if name not in {"openrouter_api_key_2", "OPENROUTER_INFERENCE_KEY_ZERO_20261002"}:
        raise ValueError("Unapproved credential source")
    return os.environ.get(name) or old.read_key(source_name=name)[0]


def validate_current(row, model, endpoints):
    if model.get("id") != row["resolved_model_id"] or old.ancillary_charge(model) or not old.all_prices_zero(model.get("pricing")):
        raise ValueError("Current model price/identity rejected")
    if "text" not in model.get("architecture", {}).get("output_modalities", []):
        raise ValueError("Text output required")
    matching = [ep for ep in endpoints if old.endpoint_slug(ep) == old.endpoint_slug(row["selected_endpoint"]) and old.eligible_endpoint(ep, model)]
    if len(matching) != 1:
        raise ValueError("Pinned free endpoint missing, changed or ambiguous")
    return {**row, "model": model, "selected_endpoint": matching[0]}


def confirmed_cost(raw):
    cost = (raw.get("usage") or {}).get("cost")
    if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
        return None
    return cost


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--free-suffix-screen", action="store_true", help="New declared DEV screen after zero-limit reservation diagnosis; exclude non-free aliases")
    parser.add_argument("--shared-models", nargs="+", help="Explicit predeclared shared DEV9 on already-free eligible models; no selection by gold")
    args = parser.parse_args()
    out = ROOT / "results" / (datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ") + "_" + uuid.uuid4().hex[:8] + "_openrouter_retry")
    out.mkdir(exist_ok=False)
    keys = {name: authorized_key(name) for name in ("openrouter_api_key_2", "OPENROUTER_INFERENCE_KEY_ZERO_20261002")}
    secrets = list(keys.values())
    def write(name, obj):
        old.write(out / name, scrub(obj, secrets))
    external = 0
    with httpx.Client(timeout=40, follow_redirects=False) as client:
        def get(path, key=None):
            nonlocal external
            external += 1
            return client.get(old.BASE + path, headers={"Authorization": "Bearer " + key} if key else {})
        snapshots = {}
        for name, key in keys.items():
            if key:
                snapshots[name] = old.key_snapshot(client, key)
                external += 1
        write("key_metadata_before.json", snapshots)
        primary = snapshots.get("openrouter_api_key_2", {})
        source = "OPENROUTER_INFERENCE_KEY_ZERO_20261002" if primary.get("is_management_key") or primary.get("is_provisioning_key") else "openrouter_api_key_2"
        key = keys[source]
        quota = snapshots.get(source, {})
        write("credential_selection.json", {"source_name": source, "reason": "Use existing same-account ordinary zero-cap child if key2 is management; no key creation/rotation", "privacy_settings_changed_by_runner": False})
        manifest, _ = old.metadata(client, key, out, source)
        external += manifest["metadata_requests_n"]
        user = get("/models/user", key)
        filtered_ids = {m["id"] for m in user.json().get("data", [])} if user.status_code == 200 else None
        write("filtered_catalog.json", {"http_status": user.status_code, "model_ids": sorted(filtered_ids) if filtered_ids is not None else None, "note": "Filtered by account provider preferences/privacy/guardrails; exact private toggle values not exposed"})
        matrix = []
        for row in manifest["rows"]:
            row["privacy_eligibility"] = "ELIGIBLE_FILTERED_CATALOG" if filtered_ids is not None and row["resolved_model_id"] in filtered_ids else "EXCLUDED_FILTERED_CATALOG" if filtered_ids is not None else "UNKNOWN"
            matrix.append(row)
        write("catalogue_matrix.json", matrix)
        attempts = []
        stop = None
        if not key or quota.get("http_status") != 200 or quota.get("is_management_key") or quota.get("is_provisioning_key"):
            stop = "AUTH_BLOCKED_PREFLIGHT"
        elif quota.get("limit") != 0 or quota.get("include_byok_in_limit") is not True:
            stop = "ZERO_PAID_LIMIT_NOT_VERIFIED"
        remaining = (quota.get("free_model_daily_requests") or {}).get("remaining")
        if not isinstance(remaining, int) or remaining < 2:
            stop = stop or "FREE_QUOTA_NOT_VERIFIED"
        cap = min(40, max(0, remaining - 1)) if isinstance(remaining, int) else 0
        candidates = [r for r in matrix if r.get("eligible") and (filtered_ids is None or r["resolved_model_id"] in filtered_ids)]
        if args.free_suffix_screen:
            candidates = [r for r in candidates if r["resolved_model_id"].endswith(":free")]
        if args.shared_models:
            if len(args.shared_models) > 3 or any(not m.endswith(":free") for m in args.shared_models):
                raise ValueError("One to three explicit free IDs only")
            candidates = [r for r in candidates if r["resolved_model_id"] in args.shared_models]
            if {r["resolved_model_id"] for r in candidates} != set(args.shared_models):
                stop = stop or "SHARED_MODEL_NOT_CURRENTLY_ELIGIBLE"
        candidates.sort(key=lambda r: ("lfm" not in r["resolved_model_id"].lower(), "ling" not in r["resolved_model_id"].lower(), r["resolved_model_id"]))
        samples = old.read_dev_samples()
        selected_samples = [samples[i] for i in (1, 2, 0, 3, 4, 5, 6, 9, 11)]
        write("samples_dev9.json", selected_samples)
        fixed_shortlist = args.shared_models or ["google/gemma-4-26b-a4b-it:free", "google/gemma-4-31b-it:free", "qwen/qwen3.8-27b:free"]
        write("plan.json", {"created_utc": old.now(), "status": "DEVELOPMENT_ONLY", "generation_cap": cap, "initial_minimal_probe": candidates[0]["resolved_model_id"] if candidates else None, "shared_sample_ids": [s["id"] for s in selected_samples], "concurrency": 1, "retries": 0, "paid_cap_usd": 0, "fallback": False, "privacy_override": False, "final_holdout": "NOT_RUN", "prior_diagnostic": "20261003_044632Z_cba2c92c_openrouter_retry" if args.free_suffix_screen else None, "shortlist_rule": "Explicit shared-model list, transport/schema gate only, no quality selection" if args.shared_models else "Predeclared Gemma26/Gemma31/Qwen27, extend only if transport and structured probe complete" if args.free_suffix_screen else "Two stable general models with complete structured correct first probe, lexicographic fixed identity order; exploratory only", "fixed_shortlist": fixed_shortlist if args.free_suffix_screen or args.shared_models else None})
        last = 0
        def attempt(row, sample, stage):
            nonlocal external, last, stop
            if stop or len(attempts) >= cap:
                return
            current = get("/models").json()
            model = next((m for m in current.get("data", []) if m["id"] == row["resolved_model_id"]), {})
            eps = get("/models/" + row["resolved_model_id"] + "/endpoints")
            try:
                fresh = validate_current(row, model, eps.json().get("data", {}).get("endpoints", []) if eps.status_code == 200 else [])
            except ValueError:
                stop = "PRICE_OR_PIN_REVALIDATION_FAILED"
                return
            delay = 3.1 - (time.monotonic() - last)
            if delay > 0:
                time.sleep(delay)
            last = time.monotonic()
            body = old.payload(fresh, sample)
            rec = {"sample_id": sample["id"], "language": sample.get("language"), "category": sample.get("category"), "group_id": sample.get("group"), "model_requested": row["resolved_model_id"], "provider_pinned": old.endpoint_slug(fresh["selected_endpoint"]), "stage": stage, "request": body, "started_utc": old.now(), "score": {"correct": False}, "error": None, "reported_cost_usd": None, "usage": {}}
            old.append(out / "attempts_started.jsonl", scrub(rec, secrets))
            started = time.perf_counter()
            external += 1
            try:
                resp = client.post(old.BASE + "/chat/completions", headers={"Authorization": "Bearer " + key}, json=body)
                rec["http_status"] = resp.status_code
                rec["rate_limit_headers"] = {k: resp.headers[k] for k in ("retry-after", "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset") if k in resp.headers}
                try:
                    raw = scrub(resp.json(), secrets)
                except ValueError:
                    raw = {"non_json_response": True}
                rec["raw"] = raw
                if resp.status_code != 200 or "error" in raw:
                    rec["error"] = "HTTP_" + str(resp.status_code)
                    if resp.status_code in (401, 402, 403, 429):
                        stop = rec["error"]
                else:
                    rec.update(usage=raw.get("usage") or {}, provider_reported=raw.get("provider"), reported_cost_usd=confirmed_cost(raw), model_reported=raw.get("model"))
                    if rec["reported_cost_usd"] != 0:
                        stop = "NONZERO_OR_UNKNOWN_REPORTED_COST"
                    choices = raw.get("choices") or []
                    content = (choices[0].get("message") or {}).get("content") if choices else None
                    rec["schema_error"] = old.schema_failure(content)
                    try:
                        parsed = old.parse_output(content)
                        rec.update(normalized_answer=parsed, score=old.score(sample, parsed))
                    except (ValueError, TypeError, KeyError):
                        rec["parse_error"] = "InvalidStructuredAnswer"
            except httpx.HTTPError as exc:
                rec["error"] = type(exc).__name__
                stop = rec["error"]
            rec["latency_seconds"] = time.perf_counter() - started
            attempts.append(rec)
            old.append(out / "raw.jsonl", scrub(rec, secrets))
            print(json.dumps({k: rec.get(k) for k in ("sample_id", "model_requested", "http_status", "error", "latency_seconds", "reported_cost_usd")}), flush=True)
        for row in candidates:
            attempt(row, selected_samples[0], "MINIMAL_CONNECTIVITY_THEN_SHARED_PROBE")
            if stop:
                break
        shortlist = [r for r in candidates if (args.shared_models or old.stable_general(r)) and any(a["model_requested"] == r["resolved_model_id"] and not a.get("error") and not a.get("schema_error") and (r["resolved_model_id"] in fixed_shortlist if args.free_suffix_screen or args.shared_models else a["score"]["correct"]) for a in attempts)][:3 if args.free_suffix_screen or args.shared_models else 2] if not stop else []
        for sample in selected_samples[1:]:
            for row in shortlist:
                attempt(row, sample, "SHARED_DEV9")
            if stop:
                break
        external += 1
        after = old.key_snapshot(client, key) if key else {}
        write("quota_after.json", after)
        summaries = []
        for row in matrix:
            records = [a for a in attempts if a["model_requested"] == row["resolved_model_id"]]
            summaries.append({**{k: row.get(k) for k in ("requested_display_name", "resolved_model_id", "status", "reason", "eligible", "privacy_eligibility", "context_length", "modalities", "pricing")}, **old.rows_summary(records), "test_status": "TESTED" if records else "NOT_RUN", "http_results": [a.get("http_status") for a in records], "blocked": bool(records and any(a.get("error") for a in records))})
        result = {"completed_utc": old.now(), "status": "BLOCKED" if stop else "DONE_EXPLORATORY", "stop_reason": stop, "rows": summaries, "found_n": sum(r["resolved_model_id"] is not None for r in matrix), "tested_n": sum(r["test_status"] == "TESTED" for r in summaries), "blocked_tested_n": sum(r["blocked"] for r in summaries), "skipped_ineligible_n": sum(not r["eligible"] for r in matrix), "generation_attempts": len(attempts), "successful_generations": sum(a.get("http_status") == 200 and not a.get("error") for a in attempts), "total_external_requests": external, "retries": 0, "user_billed_cost_usd": 0 if attempts and all(a["reported_cost_usd"] == 0 for a in attempts) and after.get("usage") == quota.get("usage") else None, "paid_cap_usd": 0, "privacy_settings_changed": False, "final_confirmatory_run": False}
        write("summary.json", result)
        print(json.dumps({"output": out.relative_to(ROOT).as_posix(), **{k: result[k] for k in ("status", "stop_reason", "found_n", "tested_n", "generation_attempts", "successful_generations", "total_external_requests")}}), flush=True)


if __name__ == "__main__":
    main()
