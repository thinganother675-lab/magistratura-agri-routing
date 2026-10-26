"""Mercury DEV36 extension: reuse 12 saved rows, call only remaining 24 IDs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import uuid

from agro_route.evaluation import score
from agro_route.home_config import resolve_api_key
from agro_route.models import Model, SYSTEM_PROMPT, public_request

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("home_mercury_base", ROOT / "scripts/home_cloud_pilot.py")
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)
MAX_NEW_CALLS = 24


def remaining_samples(all_samples, parent_rows):
    if len(all_samples) != 36 or len(parent_rows) != 12:
        raise ValueError("Extension requires saved DEV12 and selected DEV36")
    ids = [s["id"] for s in all_samples]
    old_ids = [r["sample"]["id"] for r in parent_rows]
    if len(set(ids)) != 36 or len(set(old_ids)) != 12 or not set(old_ids).issubset(ids):
        raise ValueError("Duplicate or unmatched development IDs")
    current = {s["id"]: s for s in all_samples}
    if any(r["sample"] != current[r["sample"]["id"]] for r in parent_rows):
        raise ValueError("Parent sample differs from current versioned DEV sample")
    if any(s.get("split") != "dev" for s in all_samples):
        raise ValueError("Only explicitly developmental samples may be extended")
    remaining = [s for s in all_samples if s["id"] not in set(old_ids)]
    if len(remaining) != MAX_NEW_CALLS:
        raise ValueError("Extension is limited to 24 new calls")
    return remaining


def load_parent(path):
    path = Path(path).resolve()
    if not path.is_relative_to((ROOT / "results").resolve()):
        raise ValueError("Parent must be an existing project results directory")
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("phase") != "DEVELOPMENT_ONLY" or manifest.get("model") != pilot.MODEL or
            manifest.get("base_url") != pilot.BASE_URL or manifest.get("temperature") != 0 or
            manifest.get("max_tokens") != 512 or manifest.get("reasoning_effort") != "instant" or
            manifest.get("response_format") != {"type": "json_object"} or
            manifest.get("state") not in ("completed", "completed_with_errors")):
        raise ValueError("Parent is not a completed compatible Mercury DEV pilot")
    rows = [json.loads(line) for line in (path / "mercury_raw.jsonl").read_text(encoding="utf-8").splitlines()]
    if manifest.get("cloud_calls_actual") != 12 or len(rows) != 12:
        raise ValueError("Parent must record exactly 12 prior attempts")
    return path, manifest, rows


def run(parent_path, *, execute=False):
    protected = pilot.verify_protected(ROOT)
    parent, old_manifest, old_rows = load_parent(parent_path)
    samples = pilot.choose_dev_samples(36)
    remaining = remaining_samples(samples, old_rows)
    estimated = pilot.planning_cost(remaining)
    if estimated > pilot.MAX_BUDGET_USD:
        raise RuntimeError("Extension planning estimate exceeds $0.02 budget")
    parent_hashes = {name: pilot.sha(parent / name) for name in ("manifest.json", "mercury_raw.jsonl", "samples_dev.json")}
    plan = {"phase": "DEVELOPMENT_ONLY", "model": pilot.MODEL, "base_url": pilot.BASE_URL,
            "n_new_planned": len(remaining), "n_reused": 12, "n_combined_planned": 36,
            "new_sample_ids": [s["id"] for s in remaining], "reused_sample_ids": [r["sample"]["id"] for r in old_rows],
            "parent_run": str(parent.relative_to(ROOT)), "parent_file_sha256": parent_hashes,
            "max_new_cloud_calls": MAX_NEW_CALLS, "planning_cost_estimate_usd_new": estimated,
            "budget_cap_usd_new": pilot.MAX_BUDGET_USD, "automatic_paid_retries": 0,
            "final_holdout_run": False, "parent_timeout_not_retried": True}
    if not execute:
        return plan
    key, source = resolve_api_key("mercury", env_path=ROOT / ".env")
    if not key:
        raise RuntimeError("Mercury credential not configured")
    client = Model(pilot.BASE_URL, pilot.MODEL, key, pilot.INPUT_PRICE, pilot.OUTPUT_PRICE, timeout=60)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ") + "_" + uuid.uuid4().hex[:8] + "_mercurydev36"
    directory = ROOT / "results" / run_id
    directory.mkdir(exist_ok=False)
    manifest = {**plan, **protected, "run_id": run_id, "state": "running", "started_utc": pilot.now(),
                "credential_source_name": source, "credential_value_persisted": False,
                "temperature": 0, "max_tokens": 512, "response_format": {"type": "json_object"},
                "reasoning_effort": "instant", "prompt_sha256": old_manifest["prompt_sha256"],
                "prices_usd_per_m": old_manifest["prices_usd_per_m"],
                "harness_sha256": pilot.sha(Path(__file__)),
                "selector_sha256": pilot.sha(ROOT / "scripts/home_pc_benchmark.py"),
                "cloud_calls_actual_new": 0, "new_summary": pilot.summarize([]),
                "combined_summary": pilot.summarize(old_rows),
                "latency_kind": "measured direct provider HTTP wall time; combined includes parent timeout",
                "pairing": "same versioned DEV36 IDs; local responses measured separately"}
    pilot.write_new(directory / "manifest.json", manifest)
    pilot.write_new(directory / "samples_dev.json", samples)
    with (directory / "system_prompt.txt").open("x", encoding="utf-8") as f:
        f.write(SYSTEM_PROMPT)
    rows = []
    try:
        with (directory / "mercury_raw.jsonl").open("x", encoding="utf-8") as journal:
            for sample in remaining:
                manifest["cloud_calls_actual_new"] += 1
                pilot.update_manifest(directory / "manifest.json", manifest)
                result = pilot.sanitize(client.call(public_request(sample)), key)
                row = {"sample": sample, "cloud": result, "score": score(sample, result.get("output"))}
                journal.write(json.dumps(row, ensure_ascii=False) + "\n")
                journal.flush()
                rows.append(row)
                manifest["new_summary"] = pilot.summarize(rows)
                manifest["combined_summary"] = pilot.summarize(old_rows + rows)
                pilot.update_manifest(directory / "manifest.json", manifest)
                error = result.get("error") or {}
                print(f"MERCURY NEW {len(rows)}/24 id={sample['id']} correct={row['score']['correct']} error={error.get('type')} status={error.get('http_status')}", flush=True)
                status = error.get("http_status")
                if status in (401, 402, 403, 429) or (isinstance(status, int) and status >= 500):
                    manifest["stop_reason"] = {"type": "provider_http_failure", "http_status": status}
                    break
                known_cost = manifest["new_summary"]["known_cost_estimate_usd"]
                if known_cost is not None and known_cost > pilot.MAX_BUDGET_USD:
                    manifest["stop_reason"] = {"type": "observed_cost_budget"}
                    break
    except BaseException as exc:
        manifest["state"] = "partial_interrupted"
        manifest["interruption"] = {"type": type(exc).__name__}
        manifest["finished_utc"] = pilot.now()
        pilot.update_manifest(directory / "manifest.json", manifest)
        raise
    manifest["state"] = "partial_stopped" if len(rows) != MAX_NEW_CALLS else "completed_with_errors" if manifest["new_summary"]["errors"] else "completed"
    manifest["combined_state"] = "partial" if len(old_rows + rows) != 36 else "completed_with_errors" if manifest["combined_summary"]["errors"] else "completed"
    manifest["finished_utc"] = pilot.now()
    pilot.update_manifest(directory / "manifest.json", manifest)
    current_order = {s["id"]: i for i, s in enumerate(samples)}
    combined = sorted(old_rows + rows, key=lambda row: current_order[row["sample"]["id"]])
    with (directory / "combined_mercury_raw.jsonl").open("x", encoding="utf-8") as journal:
        for row in combined:
            journal.write(json.dumps(row, ensure_ascii=False) + "\n")
    pilot.write_new(directory / "summary.json", {"run_id": run_id, "phase": "DEVELOPMENT_ONLY",
                                                 "new": manifest["new_summary"], "combined": manifest["combined_summary"]})
    pilot.verify_protected(ROOT)
    if any(pilot.sha(parent / name) != value for name, value in parent_hashes.items()):
        raise RuntimeError("Parent snapshot changed during extension")
    print("RESULTS " + str(directory), flush=True)
    return directory


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-run", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    result = run(args.parent_run, execute=args.execute)
    if isinstance(result, dict):
        print(json.dumps(result, ensure_ascii=False, indent=2))
