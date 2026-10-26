# SPDX-License-Identifier: Apache-2.0
"""Append-only, offline audit of saved development evidence; no inference.

Restricted questions, references and model answer letters never leave .runtime.
The new tables contain aggregate scores, task IDs, configuration and hashes.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agro_route.mera_adapter_20261003 import isolate_dev_references
from agro_route.mera_screen_metrics_20261003 import choice_set, set_score
from agro_route.resource_analysis_20261003 import paired_bootstrap

OUT = ROOT / "results/20261004_evidence_audit"
MODELS = ("qwen3.5-9b", "qwen3.8-27b")
SCREEN = "results/20261003_local_screen_571682f5"
TELE = "results/20261003_systems_checkpoint0_v2"
SOURCES = {}


def read(name):
    path = ROOT / name
    data = path.read_bytes()
    SOURCES[name] = hashlib.sha256(data).hexdigest()
    return json.loads(data.decode("utf-8-sig"))


def journal(name):
    path = ROOT / name
    data = path.read_bytes()
    SOURCES[name] = hashlib.sha256(data).hexdigest()
    return [json.loads(x) for x in data.decode("utf-8-sig").splitlines() if x]


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write(name, value):
    with (OUT / name).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def csv_write(name, rows):
    with (OUT / name).open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def quality(rows):
    eligible = [r for r in rows if r["gold_valid"]]
    return {"n_attempted": len(rows), "n_scored": len(eligible),
            "unresolved_references": len(rows)-len(eligible),
            "em_count": sum(r["strict_set_em"] for r in eligible),
            "em": statistics.mean(r["strict_set_em"] for r in eligible),
            "set_f1": statistics.mean(r["strict_set_f1"] for r in eligible),
            "conservative_all_n_em": sum(r["strict_set_em"] for r in eligible)/len(rows),
            "invalid_predictions": sum(not r["prediction_valid"] for r in rows),
            "json_contract_failures": sum(not r["json_contract"] for r in rows),
            "transport_errors": sum(bool(r.get("error")) for r in rows)}


def paired(left, right):
    a = {r["item_id"]: r for r in left if r["gold_valid"]}
    b = {r["item_id"]: r for r in right if r["gold_valid"]}
    assert set(a) == set(b)
    counts = Counter((a[i]["strict_set_em"], b[i]["strict_set_em"]) for i in a)
    return {"both_correct": counts[1, 1], "left_only": counts[1, 0],
            "right_only": counts[0, 1], "both_wrong": counts[0, 0], "n": len(a)}


def main():
    started = datetime.now(timezone.utc).isoformat()
    if OUT.exists() and any(OUT.iterdir()):
        raise FileExistsError("Audit outputs already exist; preserve them")
    OUT.mkdir(exist_ok=True)
    source = ".runtime/mera/dev_rows_b00011342a8f5f1e7968edaa2f6d50545a1e8f79.json"
    items, refs = isolate_dev_references(read(source))
    by_id = {i.item_id: i for i in items}
    historical, safe, manifests, raw_history = {}, {}, {}, {}
    for model in MODELS:
        manifest_name = f"{SCREEN}/dev293/{model}_manifest.json"
        manifests[model] = read(manifest_name)
        raw_name = f".runtime/mera/20261003_local_screen_571682f5/dev293/{model}_raw.jsonl"
        raw = journal(raw_name)
        assert SOURCES[raw_name] == manifests[model]["raw_sha256"]
        assert Counter(r["kind"] for r in raw) == {"benchmark": 293, "synthetic_warmup": 30}
        raw_history[model] = {r["item_id"]: r for r in raw if r["kind"] == "benchmark"}
        assert set(raw_history[model]) == set(by_id)
        historical[model] = [dict(item_id=i, domain=by_id[i].domain, error=r["error"],
                                 **set_score(refs[i], r["prediction_raw"], by_id[i].options))
                             for i, r in raw_history[model].items()]
        safe[model] = journal(f"{SCREEN}/dev293/{model}_metrics.jsonl")
        s = {r["item_id"]: r for r in safe[model]}
        for record in historical[model]:
            for key, value in record.items():
                assert s[record["item_id"]][key] == value, (model, key)
        assert SOURCES[source] == manifests[model]["source_sha256"]
    unresolved = sorted(r["item_id"] for r in historical[MODELS[0]] if not r["gold_valid"])
    assert unresolved == [222, 300, 317, 374]
    hquality = {m: quality(historical[m]) for m in MODELS}
    assert [hquality[m]["em_count"] for m in MODELS] == [141, 150]
    hpairs = paired(*[historical[m] for m in MODELS])
    assert hpairs == {"both_correct": 113, "left_only": 28, "right_only": 37, "both_wrong": 111, "n": 289}
    old_analysis = read("results/20261003_resource_analysis/analysis.json")
    bootstrap_rows = {m: [{**r, "em": r["strict_set_em"], "f1": r["strict_set_f1"],
                           "pred_valid": r["prediction_valid"]} for r in safe[m]] for m in MODELS}
    bootstrap = paired_bootstrap(bootstrap_rows[MODELS[0]], bootstrap_rows[MODELS[1]], list(by_id), samples=10000, seed=20261003)
    assert bootstrap == old_analysis["paired_bootstrap"]
    dev60 = {m: journal(f"{SCREEN}/dev60/{m}_metrics.jsonl") for m in MODELS}
    selected = {r["item_id"] for r in dev60[MODELS[0]]}
    assert len(selected) == 60 and selected < set(by_id)
    assert selected == {r["item_id"] for r in dev60[MODELS[1]]}

    plan = read(f"{TELE}/protocol_frozen.json")
    receipt = read(f"{TELE}/completion_receipt.json")
    raw_name = ".runtime/mera/20261003_systems_checkpoint0_v2/raw.jsonl"
    native = journal(raw_name)
    assert SOURCES[raw_name] == receipt["raw_sha256"]
    telemetry = {m: [r for r in native if r["model_key"] == m and r["kind"] == "telemetry"] for m in MODELS}
    weights = {w["model_key"]: w for w in read(f"{SCREEN}/installed_weight_checksums.json")["models"]}
    identities = {w["model_key"]: w for w in plan["identities"]}
    assert all(identities[m] == weights[m] for m in MODELS)
    loads = read(f"{TELE}/load_receipts.json")
    assert all(r["config"]["context_checkpoints"] == 0 and r["config"]["parallel"] == 1 for r in loads)
    compatibility, trows, flat = {}, {}, []
    changes = []
    for model in MODELS:
        old_by_id = {r["item_id"]: r for r in historical[model]}
        rows = telemetry[model]
        assert len(rows) == 40 and {r["task_id"] for r in rows} == set(plan["telemetry_item_ids"])
        trows[model] = []
        exact_same = parsed_same = 0
        for row in rows:
            i = row["task_id"]
            old_raw = raw_history[model][i]
            request = old_raw["request"]
            messages = request["messages"]
            old_system = next(x["content"] for x in messages if x["role"] == "system")
            old_user = next(x["content"] for x in messages if x["role"] == "user")
            assert old_user.encode("utf-8") == row["request"]["input"].encode("utf-8")
            assert old_system.encode("utf-8") == row["request"]["system_prompt"].encode("utf-8")
            assert sha(old_user) == row["prompt_sha256"]
            assert old_user == by_id[i].prompt
            new = dict(item_id=i, domain=by_id[i].domain, error=row["error"],
                       **set_score(refs[i], row["response_text"], by_id[i].options))
            trows[model].append(new)
            same = choice_set(old_raw["prediction_raw"], by_id[i].options)[0] == choice_set(row["response_text"], by_id[i].options)[0]
            parsed_same += same
            exact_same += old_raw["prediction_raw"].encode("utf-8") == row["response_text"].encode("utf-8")
            changes.append({"model": model, "item_id": i, "gold_valid": new["gold_valid"],
                            "historical_em": old_by_id[i]["strict_set_em"], "telemetry_em": new["strict_set_em"],
                            "historical_f1": old_by_id[i]["strict_set_f1"], "telemetry_f1": new["strict_set_f1"],
                            "parsed_choices_identical": same})
        old_subset = [old_by_id[r["task_id"]] for r in rows]
        tq, hq = quality(trows[model]), quality(old_subset)
        transitions = paired(old_subset, trows[model])
        compatibility[model] = {"historical_same40": hq, "retrospective_native40": tq,
            "same_prompt_and_system_bytes_n": 40, "identical_response_bytes_n": exact_same,
            "identical_parsed_choice_sets_n": parsed_same, "changed_choice_sets_n": 40-parsed_same,
            "paired_old_vs_native": transitions, "prompt_hashes_match": True,
            "weight_identity_receipt_matches": True,
            "recorded_weight_sha256": weights[model]["sha256"],
            "weight_bytes": weights[model]["bytes"],
            "weight_scope": "Saved file-hash receipts; installed files not rehashed in this offline audit",
            "native_loads": sum(r["model_key"] == model for r in loads)}
        for mode, q in [("historical_same40", hq), ("retrospective_native40", tq)]:
            flat.append({"model": model, "protocol": mode, **q})
    cpairs = paired(*[trows[m] for m in MODELS])
    config_rows = []
    for m in MODELS:
        hr = next(iter(raw_history[m].values()))["request"]
        nr = telemetry[m][0]["request"]
        config_rows.append({"model": m, "historical_transport": "OpenAI-compatible /v1/chat/completions",
            "telemetry_transport": "Native /api/v1/chat", "same_system_user_bytes": True,
            "historical_seed": hr.get("seed"), "telemetry_seed": nr.get("seed"),
            "historical_reasoning": hr.get("reasoning_effort"), "telemetry_reasoning": nr.get("reasoning"),
            "historical_temperature": hr["temperature"], "telemetry_temperature": nr["temperature"],
            "historical_top_p": hr["top_p"], "telemetry_top_p": nr["top_p"],
            "historical_max_tokens": hr["max_tokens"], "telemetry_max_tokens": nr["max_output_tokens"],
            "historical_schema_enforced": hr["response_format"]["json_schema"]["strict"],
            "telemetry_schema_enforced": False, "context_both": 2048,
            "historical_context_checkpoints": manifests[m]["load_config"].get("context_checkpoints"),
            "telemetry_context_checkpoints": 0, "historical_requested_gpu": manifests[m]["gpu_requested"],
            "telemetry_gpu": "AUTOMATIC_UNKNOWN", "actual_gpu_layers_both": "UNKNOWN",
            "historical_loads": 30, "telemetry_loads": 2, "historical_reload_every_n": 10,
            "telemetry_order": "ABBA; 2 blocks of20/model; warmup per load; load/warmup excluded",
            "same_declared_scorer": "choice_set/set_score; presentation only; no transliteration"})
    systems = read(f"{TELE}/systems_corrected_aggregate.json")
    study = read(f"{TELE}/study_c_corrected_aggregate.json")
    cloud = read("results/20261003_cloud_budget_only_c1184a27/mercury25_instant512_t05_dev60_combined.json")
    cloud_manifest = read("results/20261003_cloud_budget_only_c1184a27/mercury25_instant512_t05_dev60_manifest.json")
    cli = read("results/20261003_cli_products/cli_products_analysis.json")
    router = read("results/openrouter_integrated_20261003/summary.json")
    coverage = []
    def cov(model, access, data, n, config, status, metric, live, role, evidence):
        coverage.append(dict(model_checkpoint=model, access=access, dataset_split=data,
            sample_count=n, configuration=config, status=status, metric=metric,
            live_vs_replay=live, paper_role=role, primary_evidence=evidence))
    for m in MODELS:
        cov(m, "local GGUF / LM Studio", "MERA public DEV60", 60,
            "ctx2048;512;temperature0;top_p1;seed42;schema;off reasoning; reload10",
            "COMPLETED_DEV_MODEL_SELECTION", f"EM {sum(r['strict_set_em'] or 0 for r in dev60[m])}/59",
            "historical live calls", "selection; nested within DEV293", f"{SCREEN}/dev60/{m}_metrics.jsonl")
        cov(m, "local GGUF / LM Studio", "MERA public DEV293", 293,
            "ctx2048;512;temperature0;top_p1;seed42;schema;off reasoning; reload10",
            "COMPLETED_DEV", f"EM {hquality[m]['em_count']}/289; F1 {hquality[m]['set_f1']:.9f}",
            "historical live calls; rescored offline20261004", "primary historical practical configuration comparison", f"{SCREEN}/dev293/{m}_metrics.jsonl")
        cov(m, "local GGUF / LM Studio native", "MERA TELEMETRY40 subset of public DEV293", 40,
            "ctx2048;512;temperature0;top_p1;no seed/schema;checkpoint0;ABBA;autoGPU",
            "COMPLETED_SYSTEMS_RETROSPECTIVE_QUALITY", f"EM {compatibility[m]['retrospective_native40']['em_count']}/39; F1 {compatibility[m]['retrospective_native40']['set_f1']:.9f}",
            "historical live calls; retrospective scoring20261004", "supporting measured systems; not independent validation", f"{TELE}/inference_metrics.jsonl")
    for row in router["shared_dev"]:
        if row.get("attempts"):
            cov(row["resolved_model_id"], "OpenRouter API hosted checkpoint", "HOME public DEV9", row["attempts"],
                "provider profile; remote weights/revision unknown", row.get("test_status", "TESTED"),
                f"correct {row.get('correct')}/{row['attempts']}; errors {row.get('errors')}",
                "historical live API", "supplementary provider/harness coverage", "results/openrouter_integrated_20261003/summary.json")
    cov("mercury-2.5", "direct API", "MERA public DEV60", 60,
        "instant;512;temperature0.5; reused12+new48;4length failures",
        "ATTEMPTED60_COMPLETED56", f"EM {cloud['summary']['strict_em_count']}/59; F1 {cloud['summary']['strict_set_f1']:.9f}",
        "saved real API requests; combined historical probe+extension", "supplementary cloud reference; no new paid calls", "results/20261003_cloud_budget_only_c1184a27/mercury25_instant512_t05_dev60_combined.json")
    c = cli["codex"]["summary"]
    cov("gpt-6-luna (backend revision unknown)", "Codex CLI subscription product", "MERA public DEV60", 60,
        "medium; tool disabled; product startup/system overhead;46JSON violations",
        "COMPLETED_SUPPLEMENTARY", f"EM {c['strict_em_count']}/59; F1 {c['strict_set_f1']:.9f}",
        "historical live CLI", "product/harness supplementary", "results/20261003_cli_products/cli_products_analysis.json")
    cov(cli["claude"]["displayed_model"], "Claude Code subscription product", "synthetic authentication probes; MERA DEV0", 2,
        "medium; two403; no DEV calls", "BLOCKED_AUTHENTICATION_403", "no task quality measured",
        "historical live auth probes", "access coverage only", "results/20261003_cli_products/cli_products_analysis.json")
    cov("Gemma26/Mercury2.5 + Jev1.13/Laya/rules (6 arms)", "local + direct API + hosted router", "HOME development36 x6 methods", 216,
        "Gemma ctx4096/.70GPU; Laya CPU4threads1024/256; shared guards; provider timeout imbalance",
        "COMPLETED_EXPLORATORY", "Jev30/36;rules31/36;Laya23/36; actual calls and failures retained",
        "historical live routing216; separate series", "supplementary; not MERA result", "results/20261002_180119Z_76283d02_prerouting_dev/raw_decisions.jsonl")
    csv_write("quality_telemetry_same40.csv", flat)
    csv_write("retrospective_quality_transitions.csv", changes)
    csv_write("configuration_comparison.csv", config_rows)
    csv_write("model_coverage.csv", coverage)
    result = {"audit_started_utc": started, "audit_completed_utc": datetime.now(timezone.utc).isoformat(),
        "status": "OFFLINE_APPEND_ONLY_RETROSPECTIVE_DEV_AUDIT", "new_inference_calls": 0,
        "new_paid_api_calls": 0, "private_test_read_or_run": False,
        "historical_quality": hquality, "unresolved_original_reference_ids": unresolved,
        "paired_qwen9_qwen27_dev293": hpairs, "recomputed_bootstrap_matches_saved": True,
        "paired_bootstrap": bootstrap, "dev60_is_subset_of_dev293": True,
        "dev60_n": len(selected), "dev60_dev293_overlap_n": len(selected & set(by_id)),
        "telemetry_dev60_overlap_n": len(selected & set(plan["telemetry_item_ids"])),
        "retrospective_telemetry_compatibility": compatibility, "native40_model_paired": cpairs,
        "configuration_comparison": config_rows, "historical_study_c": study,
        "telemetry_measurements": {m: {k:systems["models"][m][k] for k in ["latency_s", "client_ttft_s", "backend_ttft_s", "backend_tokens_per_second", "resources", "load_samples_s", "warmup_samples_s"]} for m in MODELS},
        "mercury_extension_counts": {k: cloud_manifest[k] for k in ["prior_probe_calls", "actual_attempts", "actual_calls"]},
        "openrouter_stale_status_note": "shared_dev.status NOT_RUN is stale where test_status TESTED and nine actual outcomes are retained; old file preserved",
        "joint_claim": "Same40 prompts/weight receipts match, but answers and runtime profiles differ. Native40 retrospectively scored quality and contemporaneous native40 timing may be reported together for this subset; historical DEV293 accuracy must not be presented as simultaneously measured native40 quality. No independent validation or equivalence.",
        "source_sha256": SOURCES,
        "restrictions": ["No restricted questions/gold/answer letters exported", "Dataset rights are separate from software Apache-2.0", "Public DEV reuse/model selection disclosed", "Historical scores retained unchanged", "Native EOS/truncation reason unknown; stream completion not EOS proof", "Memory remains whole-device/whole-system or basename process-group RSS scope"]}
    SOURCES["scripts/audit_evidence_20261004.py"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    write("analysis.json", result)
    print(json.dumps({"historical": hquality, "retrospective": compatibility, "native_pairs": cpairs,
                      "new_inference_calls": 0, "output": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
