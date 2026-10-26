# SPDX-License-Identifier: Apache-2.0
"""Gold-independent, bounded Codex product low/medium/high sensitivity."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agro_route.cli_product_20261003 import ProductConfig, build_invocation, run_request, sha
from agro_route.mera_screen_metrics_20261003 import set_score, summarize
from cli_product_baseline_20261003 import SAFE, RESTRICTED, SOURCE_SHA, PROBES, authentication, write_new
from mera_local_screen_20261003 import DEFAULT_SOURCE, SYSTEM, validate_source

PLAN = SAFE / "effort10_plan_frozen.json"


def now():
    return datetime.now(timezone.utc).isoformat()


def select_effort_subset(items):
    first = {}
    for item in items:
        if item.split != "dev":
            raise ValueError("DEV only")
        first.setdefault(item.domain, item)
    if len(first) != 10:
        raise ValueError("Expected frozen DEV60 with exactly10 disciplines")
    return list(first.values())


def freeze():
    _, _, items = validate_source(DEFAULT_SOURCE, SOURCE_SHA)
    selected = select_effort_subset(items)
    cache_path = Path.home() / ".codex/models_cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    model = next(m for m in cache["models"] if m["slug"] == "gpt-6-luna" and m["visibility"] == "list")
    available = [r["effort"] for r in model["supported_reasoning_levels"]]
    if not {"low", "medium", "high"}.issubset(available):
        raise ValueError("Requested sensitivity efforts not officially advertised")
    write_new(PLAN, {"run_id": "20261003_cli_products_effort10", "status": "SUPPLEMENTARY",
        "created_utc": now(), "source_sha256": SOURCE_SHA, "private_test_run": False,
        "selected_ids": [i.item_id for i in selected], "selected_domains": [i.domain for i in selected],
        "selection_method": "first existing DEV60 item per discipline in immutable DEV60 order; exactly10 disciplines; no correctness, labels or output used",
        "model": "gpt-6-luna", "advertised_efforts": available, "not_supported": ["instant", "none"],
        "catalog_client_version": cache.get("client_version"), "catalog_fetched_at": cache.get("fetched_at"),
        "catalog_sha256": sha(cache_path.read_bytes()), "profiles": ["low", "medium", "high"],
        "medium_source": "reuse saved commonDEV60 medium, no repeat", "new_calls_limit": 22,
        "profile_order": ["low", "high"], "operational_gate": "one synthetic each; no tool events, error-free, valid output; no gate on DEV accuracy",
        "product_tools": "same constrained configuration as main product baseline", "subscription_cost": "SUBSCRIPTION_INCLUDED",
        "new_paid_api_spend": False, "retries": 0, "concurrency": 1,
        "uncertainty": "n10 descriptive product sensitivity; stochastic single pass; startup/transport overhead and time order confounded"})
    print(json.dumps({"frozen_plan": str(PLAN), "selected_ids": [i.item_id for i in selected], "new_calls_limit": 22}))


def run(effort):
    if effort not in {"low", "high"}:
        raise ValueError("Only extra officially advertised low/high; medium reused")
    if not (SAFE / "codex_dev60_manifest.json").exists():
        raise ValueError("Medium must finish before extra effort profiles; concurrency1")
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    _, refs, items = validate_source(DEFAULT_SOURCE, SOURCE_SHA)
    selected = select_effort_subset(items)
    if [i.item_id for i in selected] != plan["selected_ids"]:
        raise ValueError("Frozen subset changed")
    executable = shutil.which("codex")
    auth = authentication("codex", executable)
    config = ProductConfig("codex", executable, plan["model"], effort, RESTRICTED / "empty", SYSTEM)
    run_name = "codex_effort10_" + effort
    manifest_path = SAFE / (run_name + "_manifest.json")
    metrics = SAFE / (run_name + "_metrics.jsonl")
    raw_path = RESTRICTED / (run_name + "_raw.jsonl")
    if any(p.exists() for p in (manifest_path, metrics, raw_path)):
        raise ValueError("Append-only effort profile already attempted")
    manifest = {"run_id": run_name, "status": "SUPPLEMENTARY", "started_utc": now(), "model": plan["model"],
        "selected_effort": effort, "authentication": auth, "plan_sha256": sha(PLAN.read_bytes()),
        "exact_invocation_template": build_invocation("codex", executable, config.cwd, SYSTEM, plan["model"], effort),
        "source_hashes": {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p.read_bytes()) for p in
            (Path(__file__), ROOT / "src/agro_route/cli_product_20261003.py")},
        "subscription_cost": "SUBSCRIPTION_INCLUDED", "private_test_run": False, "adapter_retries": 0}
    rows = []
    with raw_path.open("x", encoding="utf-8") as raw_f, metrics.open("x", encoding="utf-8") as safe_f:
        # Compatibility uses independent synthetic content, not benchmark gold.
        probe_id, probe_text, probe_ref = PROBES[0]
        probe_result, probe_raw = run_request(config, probe_text)
        raw_f.write(json.dumps({"stage": "synthetic", **probe_raw}, ensure_ascii=False) + "\n"); raw_f.flush()
        probe_score = set_score(probe_ref, probe_result.pop("text"), "ABCD")
        manifest["synthetic_compatibility"] = {**probe_result, **probe_score}
        if probe_result.get("error") or probe_result["harness_confounded"] or not probe_score["prediction_valid"]:
            manifest["stop_reason"] = "SYNTHETIC_OPERATIONAL_GATE_FAILED"
        else:
            for item in selected:
                started = now()
                result, raw = run_request(config, item.prompt)
                raw.update(item_id=item.item_id, request_utc=started, request_end_utc=now())
                raw_f.write(json.dumps(raw, ensure_ascii=False) + "\n"); raw_f.flush()
                text = result.pop("text")
                score = set_score(refs[item.item_id], text if not result.get("error") else "", item.options)
                row = {"item_id": item.item_id, "domain": item.domain, "split": "dev", "request_utc": started,
                    "request_end_utc": raw["request_end_utc"], **result, **score}
                rows.append(row); safe_f.write(json.dumps(row, ensure_ascii=False) + "\n"); safe_f.flush()
                print(json.dumps({"effort": effort, "attempts": len(rows), "latency_s": row["latency_s"],
                    "error": row.get("error"), "harness_confounded": row["harness_confounded"]}), flush=True)
                if row.get("error") or row["harness_confounded"]:
                    manifest["stop_reason"] = "ERROR_OR_TOOL_EVENT_NO_RETRY"; break
    manifest.update(finished_utc=now(), expected_n=10, actual_dev_attempts=len(rows), total_new_attempts=len(rows) + 1,
        execution_status="COMPLETE" if len(rows) == 10 and all(not r.get("error") for r in rows) else "PARTIAL",
        summary=summarize(rows, plan["selected_ids"]), raw_sha256=sha(raw_path.read_bytes()), metrics_sha256=sha(metrics.read_bytes()))
    write_new(manifest_path, manifest)
    print(json.dumps({"manifest": str(manifest_path), "summary": manifest["summary"]}))


def analyze():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    medium_all = [json.loads(s) for s in (SAFE / "codex_dev60_metrics.jsonl").read_text(encoding="utf-8").splitlines()]
    medium = [r for r in medium_all if r["item_id"] in plan["selected_ids"]]
    out = {"status": "SUPPLEMENTARY", "plan_sha256": sha(PLAN.read_bytes()), "n": 10, "profiles": {},
        "interpretation": "descriptive effort sensitivity on10 gold-independent DEV items; do not promote selected profile to confirmatory or raw-model superiority",
        "unsupported_efforts": ["instant", "none"], "new_paid_api_spend": False, "private_test_run": False}
    all_rows = {"medium": medium}
    for effort in ("low", "high"):
        all_rows[effort] = [json.loads(s) for s in (SAFE / ("codex_effort10_" + effort + "_metrics.jsonl")).read_text(encoding="utf-8").splitlines()]
    for effort, rows in all_rows.items():
        out["profiles"][effort] = {"summary": summarize(rows, plan["selected_ids"]),
            "tool_calls_n": sum(r["tool_calls_n"] for r in rows),
            "internal_reconnect_events_n": sum(r.get("product_internal_reconnect_events_n", 0) for r in rows)}
    out["paired_em_counts"] = {}
    for effort in ("low", "high"):
        joined = {r["item_id"]: r for r in all_rows[effort]}
        pairs = [(r, joined[r["item_id"]]) for r in medium if r["item_id"] in joined and r["gold_valid"] and joined[r["item_id"]]["gold_valid"]]
        out["paired_em_counts"][effort + "_vs_medium"] = {
            "n": len(pairs), "both_correct": sum(a["strict_set_em"] and b["strict_set_em"] for a,b in pairs),
            "medium_only_correct": sum(a["strict_set_em"] and not b["strict_set_em"] for a,b in pairs),
            "extra_effort_only_correct": sum(not a["strict_set_em"] and b["strict_set_em"] for a,b in pairs),
            "both_wrong": sum(not a["strict_set_em"] and not b["strict_set_em"] for a,b in pairs)}
    write_new(SAFE / "cli_effort10_analysis.json", out)
    print(json.dumps(out))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["freeze", "run", "analyze"], required=True)
    parser.add_argument("--effort", choices=["low", "high"])
    args = parser.parse_args()
    if args.stage == "freeze": freeze()
    elif args.stage == "run": run(args.effort)
    else: analyze()
