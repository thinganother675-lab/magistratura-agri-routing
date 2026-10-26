# SPDX-License-Identifier: Apache-2.0
"""Append-only bounded subscription product probes / common public DEV60."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agro_route.cli_product_20261003 import ProductConfig, build_invocation, run_request, sha, subscription_environment
from agro_route.mera_screen_metrics_20261003 import set_score, summarize
from mera_local_screen_20261003 import DEFAULT_SOURCE, SYSTEM, validate_source

SAFE = ROOT / "results/20261003_cli_products"
RESTRICTED = ROOT / ".runtime/cli_products"
SOURCE_SHA = "be1c6da85e9c19a819656733fcb30318b79735e05068d5699a3f4142df50d150"
PROBES = [
    ("arithmetic", "Сколько будет 2+2? A:4 B:5 C:6 D:7.", "A"),
    ("multiple", "Выбери все чётные числа. A:2 B:3 C:4 D:5.", "A, C"),
    ("supplied_only", "В вымышленном справочнике сказано: сорт Луми имеет синий плод. Какой плод у сорта Луми? A:красный B:белый C:синий D:чёрный.", "C"),
    ("units", "В одном гектаре 10000 квадратных метров. Сколько квадратных метров в 2 гектарах? A:2000 B:20000 C:200 D:200000.", "B"),
]


def now():
    return datetime.now(timezone.utc).isoformat()


def write_new(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def authentication(product, executable):
    args = [executable, "auth", "status", "--json"] if product == "claude" else [executable, "login", "status"]
    p = subprocess.run(args, capture_output=True, env=subscription_environment(), timeout=30)
    if product == "claude":
        data = json.loads(p.stdout)
        safe = {k: data.get(k) for k in ("loggedIn", "authMethod", "apiProvider", "subscriptionType")}
        allowed = safe["loggedIn"] and safe["authMethod"] == "claude.ai" and safe["subscriptionType"] in {"pro", "max", "team", "enterprise"}
    else:
        allowed = b"Logged in using ChatGPT" in p.stdout + p.stderr
        safe = {"authMethod": "ChatGPT" if allowed else "UNVERIFIED"}
    if not allowed or p.returncode:
        raise RuntimeError("Subscription authentication not verified; no inference attempted")
    return safe


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", choices=["claude", "codex"], required=True)
    parser.add_argument("--stage", choices=["probe", "dev60"], required=True)
    parser.add_argument("--receipt-suffix", default="")
    parser.add_argument("--probe-parent", default="probe")
    args = parser.parse_args()
    suffix = ("_" + args.receipt_suffix) if args.receipt_suffix else ""
    if any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_" for c in args.receipt_suffix):
        raise ValueError("Unsafe receipt suffix")
    executable = shutil.which(args.product)
    if not executable:
        raise RuntimeError("CLI executable unavailable")
    auth = authentication(args.product, executable)
    version = subprocess.check_output([executable, "--version"], env=subscription_environment()).decode("utf-8").strip()
    model = "sonnet" if args.product == "claude" else "gpt-6-luna"
    effort = "medium"
    cwd = RESTRICTED / "empty"
    cwd.mkdir(parents=True, exist_ok=True)
    config = ProductConfig(args.product, executable, model, effort, cwd, SYSTEM)
    run_name = args.product + "_" + args.stage + suffix
    manifest_path = SAFE / (run_name + "_manifest.json")
    metrics_path = SAFE / (run_name + "_metrics.jsonl")
    raw_path = RESTRICTED / (run_name + "_raw.jsonl")
    if any(p.exists() for p in (manifest_path, metrics_path, raw_path)):
        raise ValueError("Append-only run exists; no automatic retry")
    manifest = {"run_id": "20261003_cli_products/" + run_name, "status": "SUPPLEMENTARY", "started_utc": now(),
        "cli_version": version, "product": args.product, "selected_model": model, "selected_effort": effort,
        "authentication": auth, "subscription_cost": "SUBSCRIPTION_INCLUDED", "new_paid_api_spend_authorized": False,
        "private_test_run": False, "MERA_submissions": 0, "concurrency": 1, "retries": 0,
        "prompt_policy": "unchanged benchmark question plus identical local SYSTEM; no gold supplied",
        "system_prompt": SYSTEM, "system_sha256": sha(SYSTEM.encode()),
        "exact_invocation_template": build_invocation(args.product, executable, cwd, SYSTEM, model, effort),
        "retry_definition": "adapter retries0; product internal transport reconnections separately captured per request",
        "code_commit_before_changes": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
        "source_hashes": {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p.read_bytes()) for p in
            (Path(__file__), ROOT / "src/agro_route/cli_product_20261003.py")},
        "tool_policy": "Claude built-ins empty, strict empty MCP, safe/restricted; Codex disabled shell/web/apps/MCP/memory/hooks/plugins/subagents; events audited",
        "codex_residual_harness_limit": "No CLI flag proves every internal tool absent; no observed tool event accepted; remains supplementary",
        "latency_definition": "wall clock per fresh CLI process, startup+authentication+inference+shutdown; not backend TTFT",
        "usage_definition": "product/harness tokens including system context; Claude cache fields separate, Codex output includes hidden reasoning if product reports it",
        "rights": "USE_WITH_RESTRICTIONS; prompts/source labels/provider output remain ignored .runtime",
        "api_billing_claim": "NONE; Claude client cost estimate is not a charge or subscription inference cost"}
    if args.stage == "probe":
        selected = [{"id": p[0], "prompt": p[1], "reference": p[2], "domain": "synthetic"} for p in PROBES]
    else:
        parent_name = args.product + "_" + args.probe_parent + "_manifest.json"
        if Path(parent_name).name != parent_name:
            raise ValueError("Unsafe probe parent")
        parent = json.loads((SAFE / parent_name).read_text(encoding="utf-8"))
        manifest["probe_parent_manifest"] = parent_name
        manifest["probe_parent_sha256"] = sha((SAFE / parent_name).read_bytes())
        if parent.get("execution_status") != "COMPLETE" or parent["summary"]["invalid_output"] or parent.get("harness_confounded"):
            raise RuntimeError("Compatibility operational gate not met")
        _, refs, items = validate_source(DEFAULT_SOURCE, SOURCE_SHA)
        manifest["dev_source_sha256"] = SOURCE_SHA
        selected = [{"id": item.item_id, "prompt": item.prompt, "reference": refs[item.item_id], "domain": item.domain,
                     "options": item.options} for item in items]
        if any(item.split != "dev" for item in items):
            raise ValueError("Only exact public DEV60 allowed")
        manifest["selection"] = "existing immutable reference-free balanced DEV60, unchanged IDs and source"
    manifest["expected_ids"] = [s["id"] for s in selected]
    # Save a frozen preflight receipt before the first inference.
    write_new(SAFE / (run_name + "_plan_frozen.json"), manifest)
    SAFE.mkdir(parents=True, exist_ok=True)
    rows = []
    with metrics_path.open("x", encoding="utf-8") as safe_f, raw_path.open("x", encoding="utf-8") as raw_f:
        for item in selected:
            started = now()
            result, raw = run_request(config, item["prompt"])
            raw.update(item_id=item["id"], request_utc=started, request_end_utc=now())
            raw_f.write(json.dumps(raw, ensure_ascii=False) + "\n"); raw_f.flush()
            response = result.pop("text")
            score = set_score(item["reference"], response if not result.get("error") else "", item.get("options", "ABCD"))
            row = {"item_id": item["id"], "split": "synthetic" if args.stage == "probe" else "dev", "domain": item["domain"],
                   "request_utc": started, "request_end_utc": raw["request_end_utc"], **score, **result}
            rows.append(row)
            safe_f.write(json.dumps(row, ensure_ascii=False) + "\n"); safe_f.flush()
            print(json.dumps({"product": args.product, "stage": args.stage, "completed_attempts": len(rows),
                "latency_s": row["latency_s"], "error": row.get("error"), "harness_confounded": row["harness_confounded"]}), flush=True)
            if row.get("error") or row["harness_confounded"]:
                manifest["stop_reason"] = "ERROR_OR_TOOL_LEAKAGE_NO_RETRY"
                break
    manifest.update(finished_utc=now(), actual_attempts=len(rows), summary=summarize(rows, manifest["expected_ids"]),
        harness_confounded=any(r["harness_confounded"] for r in rows), raw_sha256=sha(raw_path.read_bytes()),
        metrics_sha256=sha(metrics_path.read_bytes()), raw_relative_path=str(raw_path.relative_to(ROOT)).replace("\\", "/"),
        execution_status="COMPLETE" if len(rows) == len(selected) and all(not r.get("error") for r in rows) else "PARTIAL")
    write_new(manifest_path, manifest)
    print(json.dumps({"manifest": str(manifest_path), "summary": manifest["summary"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
