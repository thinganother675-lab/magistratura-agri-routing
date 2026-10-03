# SPDX-License-Identifier: Apache-2.0
"""Offline development reporting, frozen shortlist and claim provenance.

Never infers a model or reads hidden TEST answers. Restricted source text is
read only by the explicit bounded-cloud diagnostic correction command.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agro_route.mera_screen_analysis_20261003 import (
    confidence_diagnostic, digest, domain_and_cardinality, replay_cascade,
    select_shortlist, summarize_measurements, validate_claims,
    validate_comparable,
    select_dev_routing_rule,
)
from agro_route.mera_screen_metrics_20261003 import summarize


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_new(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2); f.write("\n")


def canonical_hash(obj):
    return digest(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode())


def normalize_rows(rows):
    return [{**row, "em": row.get("strict_set_em"), "f1": row.get("strict_set_f1"),
             "pred_valid": row.get("prediction_valid")} for row in rows]


def load_protocol(safe):
    path = safe / "protocol_frozen.json"; original = read(path); effective = dict(original)
    original_sha, previous = digest(path.read_bytes()), None
    hashes = {path.name: original_sha}
    for amendment_path in sorted(safe.glob("protocol_amendment_*.json")):
        amendment = read(amendment_path)
        if amendment.get("original_protocol_sha256") != original_sha or amendment.get("before_any_inference") is not True:
            raise ValueError("Protocol amendment provenance invalid")
        if amendment.get("previous_amendment_sha256") != previous:
            raise ValueError("Protocol amendment chain broken")
        effective.update(amendment["replacement_fields"])
        previous = digest(amendment_path.read_bytes()); hashes[amendment_path.name] = previous
    return effective, hashes


def validate_manifest_protocol(manifest, protocol, original_protocol_sha, expected_n=None):
    if manifest.get("source_sha256") != protocol["source_sha256"] or manifest.get("protocol_sha256") != original_protocol_sha:
        raise ValueError("Model manifest source/protocol provenance mismatch")
    if manifest.get("private_test_run") is not False or manifest.get("classification") != "DEV":
        raise ValueError("Private TEST or non-DEV manifest rejected")
    if manifest.get("uncommitted_source_hashes") != protocol["uncommitted_source_hashes"]:
        raise ValueError("Model manifest runner source hash mismatch")
    for load in manifest.get("loads", []):
        config = load.get("load_config")
        if config and any(config.get(k) != protocol[k] for k in ("context_length", "parallel", "speculative_draft_mtp")):
            raise ValueError("Actual model load configuration differs from common protocol")
    if manifest.get("status") == "COMPLETE":
        loads = manifest.get("loads", [])
        if expected_n is not None and [x.get("chunk_offset") for x in loads] != list(range(0, expected_n, protocol["fixed_reload_every_n"])):
            raise ValueError("Complete model lacks expected fixed reload provenance")
        if any(not x.get("load_config") or x.get("warmup_latency_s") is None for x in loads):
            raise ValueError("Complete model lacks actual load configuration/warmup provenance")


def load_profiles(safe, stage):
    safe = Path(safe).resolve()
    protocol, protocol_hashes = load_protocol(safe)
    expected_ids = protocol["dev60_ids" if stage == "dev60" else "dev293_ids"]
    profiles, rows_by_model, hashes = [], {}, {}
    amendment_paths = sorted(safe.glob("protocol_amendment_*.json"))
    snapshots_name = "source_snapshots_" + amendment_paths[-1].stem.replace("protocol_", "") if amendment_paths else "source_snapshots"
    for name, expected_sha in protocol["uncommitted_source_hashes"].items():
        snapshot = ROOT / ".runtime/mera" / safe.name / snapshots_name / Path(name).name
        if not snapshot.exists() or digest(snapshot.read_bytes()) != expected_sha:
            raise ValueError("Effective executed-source snapshot missing or changed")
        hashes[str(snapshot.relative_to(ROOT)).replace("\\", "/")] = expected_sha
    for path in sorted((safe / stage).glob("*_manifest.json")):
        manifest = read(path); metrics = path.parent / manifest["safe_rows"]
        validate_manifest_protocol(manifest, protocol, protocol_hashes["protocol_frozen.json"], len(expected_ids))
        if not metrics.exists() or digest(metrics.read_bytes()) != manifest["safe_rows_sha256"]:
            raise ValueError("Safe measurement source hash mismatch")
        rows = normalize_rows([json.loads(x) for x in metrics.read_text(encoding="utf-8").splitlines() if x])
        summary = {**manifest["summary"], **summarize_measurements(rows, expected_ids)}
        summary["complete_coverage"] = summary["complete"]
        summary.update(peak_gpu_mib=manifest["resource_metrics"].get("vram_mib_peak_sampled_total"),
                       peak_ram_used_gib=manifest["resource_metrics"].get("ram_gib_peak_sampled_system_used"))
        profile = {"model_key": manifest["model_key"], "stage": stage, "split": "dev",
                   "status": manifest["status"], "summary": summary, "ids": [r["item_id"] for r in rows],
                   "dataset_revision": protocol["source_revision"], "source_sha256": protocol["source_sha256"],
                   "selection_sha256": canonical_hash(expected_ids), "system_sha256": digest(protocol["system_prompt"].encode()),
                   "output_contract": "JSON choices array; Latin option letters; presentation normalization only",
                   "score_policy": protocol["strict_gold_policy"],
                   "common_parameters_sha256": canonical_hash(protocol["request_parameters"]),
                   "common_load_policy_sha256": canonical_hash({k: protocol[k] for k in ("context_length", "parallel", "speculative_draft_mtp", "fixed_reload_every_n", "synthetic_warmup_per_load")}),
                   "reasoning_policy_sha256": canonical_hash(protocol["reasoning_policy"]),
                   "quantization": manifest.get("quantization"), "architecture": manifest.get("architecture"),
                   "gpu_requested": manifest["gpu_requested"], "actual_gpu_layers": manifest.get("actual_gpu_layers"),
                   "reasoning_effort_requested": manifest.get("reasoning_effort_requested"),
                   "stop_reason": manifest.get("stop_reason"), "model_load_failure": manifest.get("model_load_failure"),
                   "loads_n": manifest.get("loads_n"), "total_load_latency_s": manifest.get("total_load_latency_s"),
                   "total_warmup_latency_s": manifest.get("total_warmup_latency_s"),
                   "confidence": confidence_diagnostic(rows), "breakdown": domain_and_cardinality(rows),
                   "published_compatible_em_diagnostic": sum(r["published_compatible_em"] for r in rows) / len(rows) if rows else None,
                   "published_compatible_f1_diagnostic": sum(r["published_compatible_f1"] for r in rows) / len(rows) if rows else None,
                   "manifest_path": str(path.relative_to(ROOT)).replace("\\", "/"),
                   "source_rows_path": str(metrics.relative_to(ROOT)).replace("\\", "/")}
        profiles.append(profile); rows_by_model[profile["model_key"]] = rows
        hashes[str(path.relative_to(ROOT)).replace("\\", "/")] = digest(path.read_bytes())
        hashes[str(metrics.relative_to(ROOT)).replace("\\", "/")] = digest(metrics.read_bytes())
    return profiles, rows_by_model, protocol, protocol_hashes, hashes


def correct_cloud(safe):
    """Append-only correction of truncated cloud completions, preserving raw."""
    plan = read(safe / "plan_frozen.json")
    profiles = {}
    changes = []
    for name in plan["profiles"]:
        path = safe / (name + "_probe12_metrics.jsonl")
        manifest_path = safe / (name + "_probe12_manifest.json")
        if not path.exists():
            continue
        original = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]
        manifest = read(manifest_path)
        if digest(path.read_bytes()) != manifest["safe_rows_sha256"]:
            raise ValueError("Cloud diagnostic parent changed")
        corrected = []
        for row in original:
            new = dict(row)
            if row.get("response_received") and row.get("finish_reason") != "stop":
                new.update(error={"type": "IncompleteCompletion", "finish_reason": row["finish_reason"]},
                           prediction_valid=False, prediction_cardinality=0, prediction_status="incomplete_completion", json_contract=False,
                           strict_set_em=0 if row["gold_valid"] else None, strict_set_f1=0. if row["gold_valid"] else None)
                changes.append({"profile": name, "item_id": row["item_id"], "reason": "truncated completion scores zero even when partial JSON parses"})
            corrected.append(new)
        summary = summarize(corrected, plan["probe12_ids"])
        profiles[name] = {"rows": corrected, "summary": summary, "operational_gate_passed": summary["complete_coverage"] and len(corrected) == 12 and sum(r["prediction_valid"] for r in corrected) >= 10 and all(r["cost_usd_estimate"] is not None for r in corrected),
                          "known_cost_usd_estimate": sum(r["cost_usd_estimate"] or 0 for r in corrected),
                          "unknown_cost_calls": sum(r["cost_usd_estimate"] is None for r in corrected),
                          "original_manifest_sha256": digest(manifest_path.read_bytes()), "original_rows_sha256": digest(path.read_bytes())}
    result = {"run_id": safe.name, "status": "DEV", "created_utc": now(),
              "correction": "Completion truncation and successful-completion accounting only; original source/output/gold and manifests preserved",
              "source_plan_sha256": digest((safe / "plan_frozen.json").read_bytes()),
              "analysis_code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "analysis_source_sha256": digest(Path(__file__).read_bytes()), "changes": changes, "profiles": profiles,
              "actual_attempts": sum(p["summary"]["n_attempted"] for p in profiles.values()),
              "actual_response_received": sum(p["summary"]["n_response_received"] for p in profiles.values()),
              "known_cost_usd_estimate": sum(p["known_cost_usd_estimate"] for p in profiles.values()),
              "unknown_cost_calls": sum(p["unknown_cost_calls"] for p in profiles.values()),
              "primary_cloud_selection": "NOT_FROZEN_OPERATIONAL_GATES_FAILED", "private_test_run": False}
    write_new(safe / "diagnostic_corrected.json", result)
    print(json.dumps({k: result[k] for k in ("actual_attempts", "actual_response_received", "known_cost_usd_estimate", "unknown_cost_calls", "primary_cloud_selection")}))


def freeze_shortlist(safe):
    profiles, rows, protocol, protocol_hashes, hashes = load_profiles(safe, "dev60")
    if {p["model_key"] for p in profiles} != {p["model_key"] for p in protocol["candidate_configs"]}:
        raise ValueError("Every predeclared Stage1 candidate must have an explicit terminal manifest")
    if (safe / "dev293").exists() and any((safe / "dev293").iterdir()):
        raise ValueError("Shortlist must be frozen before Stage2")
    shortlist = select_shortlist(profiles, protocol["dev60_ids"], maximum=5)
    diagnostic = dict(shortlist)
    amendment_path = safe / "dev_selection_amendment.json"
    if amendment_path.exists():
        amendment = read(amendment_path)
        if amendment.get("status") != "DEV" or amendment.get("before_dev293") is not True or amendment.get("human_review") is not False:
            raise ValueError("DEV selection amendment role/timing invalid")
        selected = amendment["model_keys"]
        if not 3 <= len(selected) <= 5 or len(selected) != len(set(selected)) or not set(selected).issubset(shortlist["pareto_models"]):
            raise ValueError("Practical selection must retain3-5 complete Pareto candidates")
        if amendment.get("stage1_source_hashes") != hashes:
            raise ValueError("Selection amendment does not bind exact Stage1 sources")
        shortlist.update(selected=selected, roles=amendment["roles"],
                         selection_method="EXPLICIT_POST_DEV60_PRE_DEV293_PRACTICAL_SELECTION",
                         selection_amendment_sha256=digest(amendment_path.read_bytes()),
                         selection_amendment_path=str(amendment_path.relative_to(ROOT)).replace("\\", "/"),
                         original_algorithm_diagnostic=diagnostic,
                         practical_rationale=amendment["rationale"])
    shortlist.update(model_keys=shortlist["selected"], created_utc=now(), stage1_only=True,
                     source_hashes=hashes, protocol_hashes=protocol_hashes,
                     analysis_code_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                     analysis_source_sha256=digest(Path(__file__).read_bytes()),
                     module_source_sha256=digest((ROOT / "src/agro_route/mera_screen_analysis_20261003.py").read_bytes()),
                     resource_scope="sampled whole GPU and whole system RAM; ordinary apps not isolated; no per-model allocation claim",
                     reasoning_exceptions={p["model_key"]: p["reasoning_effort_requested"] for p in profiles}, private_test_run=False)
    write_new(safe / "shortlist_frozen.json", shortlist)
    write_new(safe / "automated_shortlist_diagnostic.json", diagnostic)
    write_new(safe / "stage1_analysis.json", {"run_id": safe.name, "status": "DEV", "profiles": profiles,
              "shortlist": shortlist, "primary_metric": "STRICT_SET_EM/F1 on original parseable references",
              "lower_bound_companion_is_not_known_correctness": True, "source_hashes": hashes})
    print(json.dumps({"selected": shortlist["model_keys"], "roles": shortlist["roles"], "excluded": shortlist["excluded"]}, ensure_ascii=False))


def csv_profiles(path, profiles):
    fields = ["model_key", "status", "quantization", "architecture", "gpu_requested", "actual_gpu_layers",
              "n_expected", "n_attempted", "n_completed", "n_response_received", "n_scored", "reference_issues",
              "strict_em_count", "strict_set_em", "strict_set_f1", "conservative_all_n_em", "invalid_output", "errors", "timeouts",
              "latency_p50_s", "latency_p95_s", "latency_mean_s", "ttft_p50_s", "client_tps_p50", "backend_tps_p50",
              "input_tokens", "output_tokens", "peak_gpu_mib", "peak_ram_used_gib", "loads_n", "total_load_latency_s", "total_warmup_latency_s", "stop_reason"]
    with path.open("x", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader()
        for profile in profiles:
            row = {**profile, **profile["summary"]}
            writer.writerow({k: json.dumps(row[k], ensure_ascii=False) if isinstance(row.get(k), (dict, list)) else row.get(k) for k in fields})


def table(profiles):
    lines = ["| Модель / квант | Статус; попытки / завершено | EM (correct/N) | F1 | invalid / errors | p50 / p95, с | GPU / RAM peak |",
             "|---|---|---:|---:|---:|---:|---:|"]
    for p in profiles:
        s = p["summary"]
        pct = lambda value: "UNKNOWN" if value is None else f"{value*100:.2f}%"
        num = lambda value: "UNKNOWN" if value is None else f"{value:.3f}"
        lines.append(f"| `{p['model_key']}` / {p['quantization']} | {p['status']}; {s['n_attempted']}/{s['n_completed']} | {s['strict_em_count']}/{s['n_scored']} = {pct(s['strict_set_em'])} | {num(s['strict_set_f1'])} | {s['invalid_output']}/{s['errors']} | {num(s['latency_p50_s'])} / {num(s['latency_p95_s'])} | {num(s['peak_gpu_mib'])} MiB / {num(s['peak_ram_used_gib'])} GiB |")
    return "\n".join(lines)


def finalize(safe, cloud_path):
    stage1 = read(safe / "stage1_analysis.json"); shortlist_path = safe / "shortlist_frozen.json"; shortlist = read(shortlist_path)
    stage2, rows2, protocol, protocol_hashes, hashes2 = load_profiles(safe, "dev293")
    if {p["model_key"] for p in stage2} != set(shortlist["model_keys"]):
        raise ValueError("Every frozen shortlist model must have Stage2 terminal manifest")
    complete, stage2_excluded = validate_comparable(stage2, protocol["dev293_ids"], expected_stage="dev293")
    primary = min(complete, key=lambda p: (-p["summary"]["strict_set_em"], -p["summary"]["strict_set_f1"], p["summary"]["latency_p95_s"], p["model_key"]))["model_key"] if complete else None
    fast_balanced = min([p for p in complete if p["summary"]["strict_set_em"] >= max(q["summary"]["strict_set_em"] for q in complete) - .10], key=lambda p: (p["summary"]["latency_p95_s"], p["model_key"]))["model_key"] if complete else None
    _, rows1, _, _, _ = load_profiles(safe, "dev60")
    cascade = {}
    cloud_info = None
    if cloud_path:
        cloud_info = read(cloud_path)
        cloud_rows = normalize_rows(cloud_info["rows"])
        for p in stage1["profiles"]:
            if p["status"] == "COMPLETE" and p["summary"]["complete_coverage"]:
                cascade[p["model_key"]] = select_dev_routing_rule(rows1[p["model_key"]], cloud_rows, protocol["dev60_ids"])
    result = {"run_id": safe.name, "created_utc": now(), "status": "DEV",
              "analysis_code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "analysis_source_sha256": digest(Path(__file__).read_bytes()),
              "module_source_sha256": digest((ROOT / "src/agro_route/mera_screen_analysis_20261003.py").read_bytes()),
              "stage1": stage1["profiles"], "stage2": stage2, "shortlist": shortlist,
              "stage2_excluded_from_primary_selection": stage2_excluded,
              "shortlist_sha256": digest(shortlist_path.read_bytes()), "protocol_hashes": protocol_hashes,
              "source_hashes": {**stage1["source_hashes"], **hashes2},
              "primary_local": primary, "best_latency_quality": fast_balanced,
              "cascade_dev60": cascade, "cascade_status": "SIMULATED" if cascade else "UNAVAILABLE_NO_COMPLETE_COMMON_CLOUD",
              "cloud_source_sha256": digest(cloud_path.read_bytes()) if cloud_path else None,
              "private_test_run": False, "MERA_PRIVATE_TEST_READY": "NO",
              "confirmatory_validation": False, "metric_server_status": "UNKNOWN",
              "routing_rule": "invalid format/transport/abstain -> cloud; no probability threshold selected",
              "paper_recommendation": "B_AS_NEXT_PRIMARY_DESIGN_AFTER_VALID_TEST; CURRENT_EMPIRICAL_CLAIMS_DEV_ONLY",
              "actual_cloud_calls_saved_by_replay": 0,
              "blockers": ["MERA production scorer/server version unknown", "rights remain USE_WITH_RESTRICTIONS", "official submission acceptance and per-item results unverified", "authors must approve frozen primary local/cloud/rule/protocol and separate TEST submission"]}
    output = safe / "final_analysis.json"; write_new(output, result)
    csv_profiles(safe / "stage1_models.csv", result["stage1"]); csv_profiles(safe / "stage2_models.csv", stage2)
    domains = []
    for p in stage2:
        for domain, s in p["breakdown"]["domains"].items():
            domains.append({"model_key": p["model_key"], "domain": domain, "n": s["n_expected"], "n_scored": s["n_scored"], "EM": s["strict_set_em"], "F1": s["strict_set_f1"], "reference_issues": s["reference_issues"]})
    with (safe / "stage2_domains.csv").open("x", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(domains[0]) if domains else ["model_key", "domain", "n", "n_scored", "EM", "F1", "reference_issues"]); writer.writeheader(); writer.writerows(domains)
    source_rel = str(output.relative_to(ROOT)).replace("\\", "/")
    claims = []
    def claim(id_, statement, pointer, value, status="DEV"):
        claims.append({"claim_id": id_, "statement": statement, "study_run_id": safe.name + "_dev", "data_path": source_rel,
                       "analysis_field": pointer, "value": value, "code_commit": result["analysis_code_commit"],
                       "data_sha256": digest(output.read_bytes()), "status": status})
    for stage in ("stage1", "stage2"):
        for i, p in enumerate(result[stage]):
            for name in ("n_attempted", "n_completed", "n_scored", "strict_set_em", "strict_set_f1", "latency_p50_s", "latency_p95_s", "peak_gpu_mib", "peak_ram_used_gib"):
                claim(f"{stage}_{p['model_key'].replace('/', '_')}_{name}", f"{p['model_key']} {stage} {name}; public DEV development only", f"/{stage}/{i}/summary/{name}", p["summary"][name])
            for name in ("n_expected", "n_response_received", "reference_issues", "invalid_output", "errors", "timeouts", "strict_em_count", "input_tokens", "output_tokens", "conservative_all_n_em"):
                claim(f"{stage}_{p['model_key'].replace('/', '_')}_{name}", f"{p['model_key']} {stage} {name}; public DEV development only", f"/{stage}/{i}/summary/{name}", p["summary"][name])
            for name in ("auc_correctness", "n_observed", "n_total"):
                claim(f"{stage}_{p['model_key'].replace('/', '_')}_confidence_{name}", "Actual emitted-option lexical-confidence DEV diagnostic: " + name, f"/{stage}/{i}/confidence/{name}", p["confidence"][name])
            if stage == "stage2":
                for group_name in ("domains", "answer_cardinality"):
                    for group, metrics in p["breakdown"][group_name].items():
                        escaped_group = group.replace("~", "~0").replace("/", "~1")
                        for name in ("n_expected", "n_scored", "reference_issues", "strict_set_em", "strict_set_f1"):
                            claim(f"{stage}_{p['model_key'].replace('/', '_')}_{group_name}_{group}_{name}", "DEV293 original-label breakdown: " + name, f"/{stage}/{i}/breakdown/{group_name}/{escaped_group}/{name}", metrics[name])
    claim("primary_local_dev_selection", "Primary local development recommendation, not independent validation", "/primary_local", primary)
    claim("best_latency_quality_dev_selection", "Latency-quality development recommendation within exploratory .10EM tolerance", "/best_latency_quality", fast_balanced)
    claim("actual_practical_shortlist", "Explicit practical selection afterDEV60 beforeDEV293", "/shortlist/model_keys", shortlist["model_keys"])
    for key, replay in cascade.items():
        escaped = key.replace("~", "~0").replace("/", "~1")
        if replay["selected"]:
            for name in ("strict_set_em", "strict_set_f1", "cloud_calls_if_deployed", "relative_cloud_call_reduction_if_deployed", "threshold"):
                claim(f"cascade_{key.replace('/', '_')}_{name}", "Saved commonDEV60 output replay: " + name, "/cascade_dev60/" + escaped + "/selected/" + name, replay["selected"][name], "SIMULATED")
            for name in ("confidence_benefit_established", "trivial_local_resolution_suffices_on_dev"):
                claim(f"cascade_{key.replace('/', '_')}_{name}", "Saved commonDEV60 output replay limitation: " + name, "/cascade_dev60/" + escaped + "/" + name, replay[name], "SIMULATED")
    provenance = {"run_id": safe.name, "created_utc": now(), "claims": claims,
                  "validation": validate_claims(claims, ROOT), "human_confirmation": "PENDING"}
    write_new(ROOT / "manuscript/CLAIM_PROVENANCE_LOCAL_SCREEN_20261003.json", provenance)
    text = f"""# Локальный screen ruTXTAgroBench DEV: 3 октября 2026

Статус: **DEV / DEVELOPMENT_ONLY**. Исторический HOME150 и исходные рукописи сохранены. Частный TEST не запускался, официальная серверная оценка отсутствует. Серия `{safe.name}`.

Все десять кандидатов получили одну и ту же фиксированную выборку DEV60 по историческому selector: по шесть задач десяти исходных дисциплин, распределённых по ID без обращения к gold. System/JSON контракт, исходный prompt, контекст2048, reload каждые10 задач и синтетический warmup одинаковы; запрос temperature0, top_p1, seed42, max_tokens512. Off/low reasoning и GPU ratio по модели записаны как явные поддерживаемые исключения. Результаты полного DEV293 используются для разработки выбора, а не независимого подтверждения.

STRICT_SET_EM — точное совпадение множества; STRICT_SET_F1 — среднее per-question multilabel F1=2|intersection|/(|gold|+|prediction|). Только presentation normalization, латинский A сохраняется. Кириллические gold не исправлялись: знаменатель59/60 на screen и289/293 на полном DEV; original referenceissues видны. Conservative all-N — нижняя граница покрытия при нулевом вкладе unresolved, не известная истинная неправильность gold. Ошибки/незавершённые outputs дают0.

## Stage1: одинаковый DEV60

{table(result['stage1'])}

`n_attempted` включает ошибки; `n_completed` — полученные error-free завершённые responses. Partial проценты только описательны, не входят в основной ranking. Invalid обозначает непригодный набор/формат; ошибки исполнения отдельны. Published-compatible scorer сохраняется исключительно диагностически и не называется official MERA score.

## Замороженный shortlist

Модели: {', '.join('`'+m+'`' for m in shortlist['model_keys'])}. Роли: `{json.dumps(shortlist['roles'], ensure_ascii=False)}`. Файл `shortlist_frozen.json` создан до DEV293, с hashes всех Stage1 manifests/rows и protocol amendments. Pareto: maximize EM/F1, minimize p95/invalid/errors/измеренные peaks. Исходный automated selector сохранён в `automated_shortlist_diagnostic.json`; он включал MiniCPM1B как fastest/lowestresource несмотря на0/59 EM. Практические пять выбраны явно **после DEV60 и до DEV293**: `{json.dumps(shortlist.get('practical_rationale'), ensure_ascii=False)}`. Это объявленная разработческая поправка, а не заранее автоматический выбор и не человеческая научная валидация. Partial не добавлялись; zero-EM low-end reference сохранён в Stage1 без полного повторного293.

## Stage2: весь публичный DEV293

{table(stage2)}

Предварительный primary local: **`{primary}`**. Лучший latency/quality: **`{fast_balanced}`**. Самая малая ресурсная роль screen: `{shortlist['roles'].get('LOW_RESOURCE', 'UNKNOWN')}`; пригодный небольшой вариант нужно оценивать совместно с качеством, MiniCPM1B остаётся low-end reference. Числа выше не доказывают перенос на private TEST. Full293 per-domain N/EM/F1 и single/multiple/unresolved находятся в `final_analysis.json` и `stage2_domains.csv`; названия дисциплин взяты буквально из meta.domain, категории не придуманы.

Ресурсы — sampled peak всей GPU и всей системной RAM на обычном хосте, не allocation отдельной модели. Request latency исключает reload/warmup: их отдельные amounts доступны в CSV/JSON. Requested GPU ratio не подтверждает actualoffload layers, если native API их не раскрывает. BackendTPS и TTFT публикуются только при фактическом измерении. Token logprobs, если есть, — lexicalconfidence; AUC по DEV диагностичен, калиброванной вероятности правильности и выбранного threshold нет.

## Cascade DEV replay

Статус **{result['cascade_status']}**. Неразбираемый набор вариантов/transport/abstain → cloud; presentation-normalized plain Latin list может быть допустим даже без исходного JSON, поэтому это не проверка полной strict JSONschema. Дополнительный порог реальной lexicalconfidence выбирается только на DEV из объявленной сетки [None,.5,.7,.8,.9,.95,.98,.99,1]. Цель — минимальная доля cloud при EM не ниже cloud−5 п.п.; ties higherF1/lowerthreshold.5 п.п. — exploratory design choice, требующая подтверждения авторами для TEST; это не доказанное неухудшение и не агрономический норматив. Каждое routing decision использует только local observable signal, не gold. Результат primary: `{json.dumps(cascade.get(primary, {}).get('selected'), ensure_ascii=False)}`. Confidence benefit: `{cascade.get(primary, {}).get('confidence_benefit_established', False)}`; local-only suffices: `{cascade.get(primary, {}).get('trivial_local_resolution_suffices_on_dev', False)}`.

Replay не вызывает моделей: фактически сэкономленных в этом screen запросов0. Возможное сокращение по сохранённым ответам относится только к общему DEV60; full293 cloud не выполнялся, full293 cascade качество неизвестно. Live cascade latency/cost savings не измерены.

## Следующий этап статьи

Рекомендуется **OPTION B как основной следующий дизайн**: MERA для аграрных знаний; HOME150 и StudyC поддерживают технические части. Нынешнее расширение materially усиливает выбор локальной модели и методику, но DEV нельзя назвать final scientific validation. OPTIONC не обоснован числом публикаций.

**MERA_PRIVATE_TEST_READY=NO; server metric UNKNOWN**. Нужны ответ сопровождающих о production scorer/optionA и правах, приёмка official submissionworkflow, согласованная cloudidentity, утверждение авторами замороженных local/cloud/rule/protocol и отдельное разрешение TEST. Maintainermessage подготовлен отдельно, не отправлен. Антоний: проверить рекомендации и вместе с Денисом утвердить небольшой следующий protocol. Денис: независимо проверить denominator/partial/metrics/счёт обращений и согласовать вопросы к MERA; review40 не требуется заполнять.

Агрегаты/CSV: `{str(safe.relative_to(ROOT)).replace(chr(92), '/')}`. Новая provenance: `manuscript/CLAIM_PROVENANCE_LOCAL_SCREEN_20261003.json`. Source questions/gold/raw remain ignored `.runtime/mera`; datasetrights USE_WITH_RESTRICTIONS.
"""
    document = ROOT / "docs/MERA_LOCAL_MODEL_SCREEN_20261003_RU.md"
    with document.open("x", encoding="utf-8") as f: f.write(text)
    print(json.dumps({"primary_local": primary, "best_latency_quality": fast_balanced, "stage2_complete": len(complete), "claim_count": len(claims)}))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["correct-cloud", "freeze-shortlist", "finalize"], required=True)
    parser.add_argument("--study-dir", required=True, type=Path)
    parser.add_argument("--cloud-combined", type=Path)
    args = parser.parse_args(); safe = (ROOT / args.study_dir).resolve()
    if not safe.is_relative_to(ROOT / "results"): raise ValueError("Private research results path required")
    if args.stage == "correct-cloud": correct_cloud(safe)
    elif args.stage == "freeze-shortlist": freeze_shortlist(safe)
    else: finalize(safe, (ROOT / args.cloud_combined).resolve() if args.cloud_combined else None)
