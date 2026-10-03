# SPDX-License-Identifier: Apache-2.0
"""Bounded sequential Mercury DEV diagnostic and one fixed DEV60 baseline.

No LM Studio control, TEST fetch, service upload, retries, credential output, or
public source text. Paid attempts are journaled before requests. A profile may
extend from its fixed12 probe to fixed60 without repeating the12 IDs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agro_route.home_config import resolve_api_key
from agro_route.mera_adapter_20261003 import official_scores, sha256_bytes
from agro_route.mera_screen_metrics_20261003 import choice_set, set_score, summarize
from mera_local_screen_20261003 import DEFAULT_SOURCE, SCHEMA, SYSTEM, validate_source
from home_lm_api_benchmark import redact

BASE = "https://api.inceptionlabs.ai/v1"
PROFILES = {
    "mercury25_instant256_t05": {"model": "mercury-2.5", "reasoning_effort": "instant", "max_completion_tokens": 256, "temperature": .5, "prices": [.04, .15]},
    "mercury2_medium1024_t05": {"model": "mercury-2", "reasoning_effort": "medium", "max_completion_tokens": 1024, "temperature": .5, "prices": [.25, .75]},
    "mercury25_instant512_t05": {"model": "mercury-2.5", "reasoning_effort": "instant", "max_completion_tokens": 512, "temperature": .5, "prices": [.04, .15]},
}
SOURCE_SHA = "be1c6da85e9c19a819656733fcb30318b79735e05068d5699a3f4142df50d150"


def now():
    return datetime.now(timezone.utc).isoformat()


def write_new(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2); f.write("\n")


def append(handle, obj):
    handle.write(json.dumps(obj, ensure_ascii=False) + "\n"); handle.flush()


def selected_probe(dev60):
    if len(dev60) != 60:
        raise ValueError("Exact common DEV60 required")
    return [dev60[(i * len(dev60)) // 12] for i in range(12)]


def request(profile, prompt):
    if profile not in PROFILES:
        raise ValueError("Unfrozen cloud profile")
    params = {k: v for k, v in PROFILES[profile].items() if k != "prices"}
    params["messages"] = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    params["response_format"] = {"type": "json_schema", "json_schema": {"name": "mera_choices", "strict": True, "schema": SCHEMA}}
    return params


def reserve_usd(profile, prompt):
    p = PROFILES[profile]
    # Byte upper bound reserves conservatively; it is not provider tokenization.
    return ((len(SYSTEM.encode()) + len(prompt.encode())) * p["prices"][0] + p["max_completion_tokens"] * p["prices"][1]) / 1e6


def source_snapshot(safe, restricted):
    names = ["scripts/mera_cloud_baseline_20261003.py", "scripts/mera_local_screen_20261003.py",
             "src/agro_route/mera_screen_metrics_20261003.py", "src/agro_route/mera_adapter_20261003.py"]
    hashes = {}
    for name in names:
        data = (ROOT / name).read_bytes(); hashes[name] = sha256_bytes(data)
        dest = restricted / "source_snapshots" / Path(name).name
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("xb") as f: f.write(data)
    return hashes


def plan(args):
    safe = (ROOT / args.study_dir).resolve()
    if not safe.is_relative_to(ROOT / "results") or safe.exists():
        raise ValueError("Fresh results directory required")
    restricted = ROOT / ".runtime/mera" / safe.name
    restricted.mkdir(parents=True)
    _, _, dev60 = validate_source(DEFAULT_SOURCE, SOURCE_SHA)
    probe = selected_probe(dev60)
    profiles = args.profiles or ["mercury25_instant256_t05", "mercury2_medium1024_t05"]
    bounds = {profile: sum(reserve_usd(profile, item.prompt) for item in probe) for profile in profiles}
    body = {"run_id": safe.name, "created_utc": now(), "status": "DEV", "source_sha256": SOURCE_SHA,
            "dev60_ids": [i.item_id for i in dev60], "probe12_ids": [i.item_id for i in probe],
            "selection_provenance": "deterministic evenly-spread indexes of immutable historical DEV60; no gold input",
            "profiles": {p: PROFILES[p] for p in profiles}, "diagnostic_max_calls": 12 * len(profiles), "diagnostic_cap_usd": .02,
            "diagnostic_conservative_reserve_usd": bounds, "baseline_total_cap_usd": .1,
            "baseline_max_calls": 60, "baseline_extension_rule": "one profile only, operational validity gate; extend remaining48 without repeating initial12; no tuning on DEV293",
            "operational_gate": "all12 transport success, all12 usage known, at least10/12 valid sets; no selection by probe accuracy",
            "temperature_supported_floor": .5, "local_temperature": 0,
            "parameter_differences": ["Mercury temperature.5 vs local0 because provider allows.5-1", "Mercury instant/medium vs native local off/low", "Mercury nonstream TTFT/tok/s unavailable", "Mercury no seed/top_p/logprobs requested because not documented in current API"],
            "system_prompt": SYSTEM, "response_schema": SCHEMA,
            "source_hashes": source_snapshot(safe, restricted),
            "budget_only_diagnostic_parent": "20261003_cloud_baseline_7c019d4a mercury25_instant256_t05; onlymax_completion_tokens256to512changed" if profiles == ["mercury25_instant512_t05"] else None,
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "private_test_run": False, "mera_submission_calls": 0,
            "data_rights": "USE_WITH_RESTRICTIONS; benchmark/provider text restricted"}
    if sum(bounds.values()) > .02:
        raise ValueError("Predeclared diagnostic reserve exceeds budget")
    write_new(safe / "plan_frozen.json", body)
    print(json.dumps({"plan": str(safe.relative_to(ROOT)), "diagnostic_reserved_usd": sum(bounds.values()), "max_calls": 12 * len(profiles), "no_inference": True}))


def safe_measurement(item, reference, body, result, elapsed, error, raw):
    finish = ((raw or {}).get("choices") or [{}])[0].get("finish_reason")
    if raw is not None and finish != "stop" and not error:
        error = {"type": "IncompleteCompletion", "finish_reason": finish}
    score = set_score(reference, result if not error else "", item.options)
    normalized, _, _ = choice_set(result if not error else "", item.options)
    compatible = official_scores(reference, ", ".join(normalized))
    usage = (raw or {}).get("usage") or {}
    fields = {"item_id": item.item_id, "split": "dev", "domain": item.domain, **score,
              "prompt_sha256": sha256_bytes(item.prompt.encode()), "error": error,
              "response_received": raw is not None, "latency_s": elapsed,
              "input_tokens": usage.get("prompt_tokens"), "output_tokens": usage.get("completion_tokens"),
              "reasoning_tokens": usage.get("reasoning_tokens", usage.get("completion_tokens_details", {}).get("reasoning_tokens")),
              "returned_model": (raw or {}).get("model"), "warning": (raw or {}).get("warning"),
              "published_compatible_em": compatible["exact_match"], "published_compatible_f1": compatible["f1"],
              "finish_reason": finish,
              "option_token_confidence": None, "ttft_s": None, "backend_tps": None}
    p = next(x for x in PROFILES.values() if x["model"] == body["model"])
    known = all(isinstance(fields.get(k), int) and not isinstance(fields[k], bool) and fields[k] >= 0 for k in ("input_tokens", "output_tokens"))
    fields["cost_usd_estimate"] = (fields["input_tokens"] * p["prices"][0] + fields["output_tokens"] * p["prices"][1]) / 1e6 if known else None
    return fields


def run(args):
    safe = (ROOT / args.study_dir).resolve()
    if not safe.is_relative_to(ROOT / "results"):
        raise ValueError("Results must be private research workspace")
    frozen_path = safe / "plan_frozen.json"
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    for name, sha in frozen["source_hashes"].items():
        if sha256_bytes((ROOT / name).read_bytes()) != sha:
            raise ValueError("Frozen executed source changed")
    _, refs, dev60 = validate_source(DEFAULT_SOURCE, SOURCE_SHA)
    if [i.item_id for i in dev60] != frozen["dev60_ids"]:
        raise ValueError("Common subset changed")
    restricted = ROOT / ".runtime/mera" / safe.name
    profile = args.profile
    if profile not in frozen["profiles"]:
        raise ValueError("Cloud profile not declared in this frozen plan")
    parent_rows = []
    if args.stage == "probe12":
        selected = selected_probe(dev60)
    elif args.stage == "dev60":
        manifest_path = safe / (profile + "_probe12_manifest.json")
        parent = json.loads(manifest_path.read_text(encoding="utf-8"))
        metrics_path = safe / (profile + "_probe12_metrics.jsonl")
        if sha256_bytes(metrics_path.read_bytes()) != parent["safe_rows_sha256"]:
            raise ValueError("Parent probe immutable hash mismatch")
        parent_rows = [json.loads(line) for line in metrics_path.read_text(encoding="utf-8").splitlines()]
        if len(parent_rows) != 12 or any(r.get("error") or r.get("cost_usd_estimate") is None for r in parent_rows) or sum(r["prediction_valid"] for r in parent_rows) < 10:
            raise ValueError("Operational gate for cloud baseline not met")
        selection = safe / "cloud_primary_frozen.json"
        if selection.exists():
            chosen = json.loads(selection.read_text(encoding="utf-8"))
            if chosen["profile"] != profile:
                raise ValueError("Only one cloud baseline may be fixed")
        else:
            write_new(selection, {"created_utc": now(), "profile": profile,
                                 "status": "DEV_PROVISIONAL_PRIMARY_BEFORE_DEV60_EXTENSION",
                                 "reason": "direct legitimate stable model ID; operational12 gate; no selection by gold accuracy", "private_test_run": False})
        seen = {r["item_id"] for r in parent_rows}
        selected = [item for item in dev60 if item.item_id not in seen]
    else:
        raise ValueError("Only public DEV stages allowed")
    target = safe / (profile + "_" + args.stage + "_manifest.json")
    raw_path = restricted / (profile + "_" + args.stage + "_raw.jsonl")
    metrics = safe / (profile + "_" + args.stage + "_metrics.jsonl")
    if target.exists() or raw_path.exists() or metrics.exists():
        raise ValueError("Append-only artifact already exists; no retries or overwrite")
    key, source = resolve_api_key("mercury")
    if not key:
        raise RuntimeError("Existing Mercury credential unavailable")
    reserved = sum(r.get("cost_usd_estimate") or 0 for r in parent_rows)
    cap = .02 if args.stage == "probe12" else .1
    manifest = {"run_id": safe.name, "profile": profile, "stage": args.stage, "status": "DEV",
                "started_utc": now(), "credential_source_name": source, "code_commit": frozen["code_commit"],
                "plan_sha256": sha256_bytes(frozen_path.read_bytes()), "actual_attempts": 0,
                "prior_probe_calls": len(parent_rows), "private_test_run": False, "retries": 0,
                "MERA_submissions": 0, "cap_usd": cap, "n_expected": len(selected),
                "parameter_differences": frozen["parameter_differences"]}
    rows = []
    try:
        with httpx.Client(timeout=60, trust_env=True) as client, raw_path.open("x", encoding="utf-8") as raw_handle, metrics.open("x", encoding="utf-8") as safe_handle, (restricted / (profile + "_" + args.stage + "_started.jsonl")).open("x", encoding="utf-8") as starts:
            for item in selected:
                if item.split != "dev":
                    raise ValueError("Private TEST forbidden")
                upper = reserve_usd(profile, item.prompt)
                if reserved + upper > cap:
                    manifest["stop_reason"] = "BUDGET_GUARD"; break
                reserved += upper
                body = request(profile, item.prompt)
                append(starts, {"item_id": item.item_id, "started_utc": now(), "reserved_usd": upper, "prompt_sha256": sha256_bytes(item.prompt.encode())})
                manifest["actual_attempts"] += 1
                raw, text, error = None, "", None
                start = time.perf_counter()
                try:
                    response = client.post(BASE + "/chat/completions", json=body, headers={"Authorization": "Bearer " + key})
                    response.raise_for_status(); raw = redact(response.json(), key)
                    text = raw["choices"][0]["message"].get("content") or ""
                    if not isinstance(text, str):
                        raise ValueError("Nont text output")
                    if raw.get("model") != PROFILES[profile]["model"]:
                        raise ValueError("Returned model identity changed")
                except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as exc:
                    error = {"type": type(exc).__name__, "http_status": getattr(getattr(exc, "response", None), "status_code", None)}
                elapsed = time.perf_counter() - start
                row = safe_measurement(item, refs[item.item_id], body, text, elapsed, error, raw)
                rows.append(row); append(safe_handle, row)
                append(raw_handle, {"item_id": item.item_id, "split": "dev", "request_parameters": {k: v for k, v in body.items() if k != "messages"}, "prompt_sha256": row["prompt_sha256"], "system_sha256": sha256_bytes(SYSTEM.encode()), "response": raw, "prediction_raw": text, "error": error, "elapsed_s": elapsed})
                print(json.dumps({"profile": profile, "stage": args.stage, "progress": f"{len(rows)}/{len(selected)}", "valid": row["prediction_valid"], "finish_reason": row["finish_reason"], "error": error}), flush=True)
                if error or row["cost_usd_estimate"] is None:
                    manifest["stop_reason"] = "ERROR_OR_UNKNOWN_USAGE_NO_RETRY"; break
                if len(rows) >= 6 and sum(not r["prediction_valid"] for r in rows[-6:]) >= 3:
                    manifest["stop_reason"] = "THREE_INVALID_LAST_SIX"; break
    finally:
        manifest.update(finished_utc=now(), status="COMPLETE" if len(rows) == len(selected) else "PARTIAL",
                        actual_calls=len(rows), reserved_usd=reserved, known_cost_usd_estimate=sum(r["cost_usd_estimate"] or 0 for r in rows),
                        unknown_cost_calls=sum(r["cost_usd_estimate"] is None for r in rows), summary=summarize(rows, [i.item_id for i in selected]),
                        raw_sha256=sha256_bytes(raw_path.read_bytes()) if raw_path.exists() else None,
                        safe_rows_sha256=sha256_bytes(metrics.read_bytes()) if metrics.exists() else None)
        write_new(target, manifest)
        if args.stage == "dev60":
            complete = parent_rows + rows
            complete.sort(key=lambda r: frozen["dev60_ids"].index(r["item_id"]))
            write_new(safe / (profile + "_dev60_combined.json"), {"status": "DEV", "rows": complete,
                "summary": summarize(complete, frozen["dev60_ids"]), "parent_probe_sha256": sha256_bytes((safe / (profile + "_probe12_manifest.json")).read_bytes()),
                "extension_manifest_sha256": sha256_bytes(target.read_bytes()), "no_repeated_probe_ids": True})
    print(json.dumps({"profile": profile, "stage": args.stage, "summary": manifest["summary"], "known_cost_usd_estimate": manifest["known_cost_usd_estimate"]}), flush=True)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["plan", "probe12", "dev60"], required=True)
    parser.add_argument("--study-dir", type=Path, required=True)
    parser.add_argument("--profile", choices=list(PROFILES))
    parser.add_argument("--profiles", choices=list(PROFILES), nargs="+", help="Explicit profiles for a fresh plan only")
    args = parser.parse_args()
    if args.stage == "plan": plan(args)
    elif not args.profile: parser.error("profile required for execution")
    else: run(args)
