"""Append-only Mercury HOME DEV pilot; no final-test or frozen-core changes.

Runs at most 12 direct Inception requests, once per existing DEV sample. Local
responses can be paired later by the exact IDs; this script uses no local GPU.
No API request is made unless --execute is supplied. Credentials are internal.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import uuid

from agro_route.evaluation import score
from agro_route.home_config import resolve_api_key
from agro_route.models import Model, SYSTEM_PROMPT, public_request

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://api.inceptionlabs.ai/v1"
MODEL = "mercury-2.5"
INPUT_PRICE = .04
OUTPUT_PRICE = .15
MAX_CALLS = 12
MAX_OUTPUT_TOKENS = 512
PLANNING_INPUT_TOKENS = 6000
MAX_BUDGET_USD = .02
PRICE_SOURCE = "https://docs.inceptionlabs.ai/get-started/models"
FROZEN_RUN = "20260930T182756Z_6703e43b"
CORE = ("models.py", "routing.py", "evaluation.py", "benchmark.py", "tools.py", "cli.py")


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_protected(root=ROOT):
    baseline = json.loads((root / "results" / FROZEN_RUN / "manifest.json").read_text(encoding="utf-8"))
    expected = {name.replace("\\", "/"): value for name, value in baseline["code_sha256"].items()}
    observed = {f"src/agro_route/{name}": sha(root / "src/agro_route" / name) for name in CORE}
    if any(expected.get(name) != value for name, value in observed.items()):
        raise RuntimeError("Protected historical core hash mismatch")
    data_hash = sha(root / "data/benchmark.jsonl")
    protocol_hash = sha(root / "data/protocol_frozen.json")
    if data_hash != baseline["dataset_sha256"] or protocol_hash != baseline["protocol_sha256"]:
        raise RuntimeError("Protected historical data/protocol hash mismatch")
    return {"core_source_sha256": observed, "historical_dataset_sha256": data_hash,
            "historical_protocol_sha256": protocol_hash, "historical_hashes_match": True}


def choose_dev_samples(n):
    # Reuse the HOME selector verbatim so LM/API and Mercury share identical IDs.
    spec = importlib.util.spec_from_file_location("home_selector", ROOT / "scripts/home_pc_benchmark.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.choose_samples(n)


def validate_samples(samples, n):
    if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= MAX_CALLS:
        raise ValueError("Mercury pilot permits 1 to 12 DEV requests")
    if len(samples) != n or any(s.get("split") != "dev" for s in samples):
        raise ValueError("Exactly n explicitly developmental samples are required")
    ids = [sample.get("id") for sample in samples]
    if any(not isinstance(sid, str) or not sid for sid in ids) or len(set(ids)) != n:
        raise ValueError("Development IDs must be present and unique")


def planning_cost(samples):
    # This is a documented planning estimate, not a guaranteed tokenizer bound.
    # Add room for provider chat framing when a supplied context is unusually long.
    inputs = [max(PLANNING_INPUT_TOKENS,
                  len(SYSTEM_PROMPT.encode("utf-8")) +
                  len(json.dumps(public_request(s), ensure_ascii=False).encode("utf-8")) + 1024)
              for s in samples]
    return sum((tokens * INPUT_PRICE + MAX_OUTPUT_TOKENS * OUTPUT_PRICE) / 1e6 for tokens in inputs)


def sanitize(value, key):
    """Fail-safe redaction if a provider unexpectedly returns the exact secret."""
    if isinstance(value, str):
        return value.replace(key, "[REDACTED_CREDENTIAL]") if key else value
    if isinstance(value, dict):
        return {sanitize(k, key): sanitize(v, key) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(item, key) for item in value]
    return value


def known_number(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def summarize(rows):
    usage = [row["cloud"].get("usage", {}) for row in rows]
    inputs = [u.get("prompt_tokens") for u in usage]
    outputs = [u.get("completion_tokens") for u in usage]
    costs = [row["cloud"].get("cost_usd") for row in rows]
    def total(values):
        known = [value for value in values if known_number(value)]
        return sum(known) if known else None
    return {"n_saved": len(rows), "cloud_calls_attempted": len(rows),
            "correct": sum(row["score"]["correct"] for row in rows),
            "quality": sum(row["score"]["correct"] for row in rows) / len(rows) if rows else None,
            "errors": sum(bool(row["cloud"].get("error")) for row in rows),
            "input_tokens_known_sum": total(inputs), "output_tokens_known_sum": total(outputs),
            "input_usage_coverage_n": sum(known_number(x) for x in inputs),
            "output_usage_coverage_n": sum(known_number(x) for x in outputs),
            "known_cost_estimate_usd": total(costs),
            "unknown_cost_calls": sum(not known_number(x) for x in costs),
            "provider_invoice_obtained": False}


def write_new(path, data):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)


def update_manifest(path, data):
    # Only the manifest in this newly created running directory is mutable.
    temporary = path.with_suffix(".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
    temporary.replace(path)


def run(n=12, *, execute=False, root=ROOT):
    if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= MAX_CALLS:
        raise ValueError("Mercury pilot permits 1 to 12 DEV requests")
    protected = verify_protected(root)
    samples = choose_dev_samples(n)
    validate_samples(samples, n)
    estimate = planning_cost(samples)
    if estimate > MAX_BUDGET_USD:
        raise RuntimeError("Mercury planning estimate exceeds $0.02 budget")
    plan = {"phase": "DEVELOPMENT_ONLY", "model": MODEL, "base_url": BASE_URL,
            "n": n, "sample_ids": [s["id"] for s in samples], "max_cloud_calls": MAX_CALLS,
            "planning_cost_estimate_usd": estimate, "budget_cap_usd": MAX_BUDGET_USD,
            "automatic_paid_retries": 0, "final_holdout_run": False}
    if not execute:
        return plan
    key, key_source = resolve_api_key("mercury", env_path=root / ".env")
    if not key:
        raise RuntimeError("Mercury credential not configured in allowed project sources")
    client = Model(BASE_URL, MODEL, key, INPUT_PRICE, OUTPUT_PRICE, timeout=60)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ") + "_" + uuid.uuid4().hex[:8] + "_mercurydev"
    directory = root / "results" / run_id
    directory.mkdir(parents=True, exist_ok=False)
    manifest = {**plan, **protected, "run_id": run_id, "state": "running", "started_utc": now(),
                "credential_source_name": key_source, "credential_value_persisted": False,
                "temperature": 0, "max_tokens": MAX_OUTPUT_TOKENS,
                "response_format": {"type": "json_object"}, "reasoning_effort": "instant",
                "prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
                "harness_sha256": sha(Path(__file__)),
                "selector_sha256": sha(ROOT / "scripts/home_pc_benchmark.py"),
                "prices_usd_per_m": {"input": INPUT_PRICE, "output": OUTPUT_PRICE,
                                      "verified_date": "2026-10-01", "source": PRICE_SOURCE,
                                      "cached_discount_applied": False},
                "cost_type": "token-based estimate; provider invoice not obtained",
                "pairing": "standalone cloud DEV; match exact saved IDs to a separately measured local run",
                "local_generation_run": False, "cloud_calls_actual": 0,
                "latency_kind": "measured direct provider HTTP wall time"}
    write_new(directory / "manifest.json", manifest)
    write_new(directory / "samples_dev.json", samples)
    with (directory / "system_prompt.txt").open("x", encoding="utf-8") as stream:
        stream.write(SYSTEM_PROMPT)
    rows = []
    try:
        with (directory / "mercury_raw.jsonl").open("x", encoding="utf-8") as journal:
            for sample in samples:
                # Increment before the call; interrupted attempts remain visible.
                manifest["cloud_calls_actual"] += 1
                update_manifest(directory / "manifest.json", manifest)
                result = sanitize(client.call(public_request(sample)), key)
                row = {"sample": sample, "cloud": result, "score": score(sample, result.get("output"))}
                journal.write(json.dumps(row, ensure_ascii=False) + "\n")
                journal.flush()
                rows.append(row)
                manifest["summary"] = summarize(rows)
                update_manifest(directory / "manifest.json", manifest)
                error = result.get("error") or {}
                print(f"MERCURY {len(rows)}/{n} id={sample['id']} correct={row['score']['correct']} error={error.get('type')} status={error.get('http_status')}", flush=True)
                status = error.get("http_status")
                if status in (401, 402, 403, 429) or (isinstance(status, int) and status >= 500):
                    manifest["stop_reason"] = {"type": "provider_http_failure", "http_status": status}
                    break
                known_cost = manifest["summary"]["known_cost_estimate_usd"]
                if known_cost is not None and known_cost > MAX_BUDGET_USD:
                    manifest["stop_reason"] = {"type": "observed_cost_budget"}
                    break
    except BaseException as exc:
        manifest["state"] = "partial_interrupted"
        manifest["interruption"] = {"type": type(exc).__name__}
        manifest["summary"] = summarize(rows)
        manifest["finished_utc"] = now()
        update_manifest(directory / "manifest.json", manifest)
        raise
    manifest["state"] = ("partial_stopped" if len(rows) < n else
                         "completed_with_errors" if manifest["summary"]["errors"] else "completed")
    manifest["finished_utc"] = now()
    update_manifest(directory / "manifest.json", manifest)
    write_new(directory / "summary.json", {"run_id": run_id, "phase": "DEVELOPMENT_ONLY", **summarize(rows)})
    verify_protected(root)
    print("RESULTS " + str(directory), flush=True)
    return directory


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=12)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    result = run(args.n, execute=args.execute)
    if isinstance(result, dict):
        print(json.dumps(result, ensure_ascii=False, indent=2))
