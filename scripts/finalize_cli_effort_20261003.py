# SPDX-License-Identifier: Apache-2.0
"""Compact, benchmark-text-free effort evidence from immutable product receipts."""
from __future__ import annotations
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agro_route.cli_product_20261003 import sha
from cli_product_baseline_20261003 import SAFE, RESTRICTED, write_new


def usage_from_raw(path, selected_ids):
    reports = []
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = json.loads(line)
        if raw.get("item_id") not in selected_ids:
            continue
        events = [json.loads(s) for s in raw["stdout"].splitlines() if s.strip()]
        reports.append(next(e["usage"] for e in events if e["type"] == "turn.completed"))
    def total(field):
        values = [r.get(field) for r in reports]
        return sum(values) if all(isinstance(v, int) and not isinstance(v, bool) for v in values) else None
    return {"n": len(reports), "exposed_reasoning_tokens": total("reasoning_output_tokens"),
        "cache_read_input_tokens": total("cached_input_tokens"), "cache_write_input_tokens": total("cache_write_input_tokens"),
        "reasoning_semantics": "product-reported field; zero does not prove absent hidden reasoning; output token total already includes reported reasoning"}


def main():
    analysis_path = SAFE / "cli_effort10_analysis.json"
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    plan = json.loads((SAFE / "effort10_plan_frozen.json").read_text(encoding="utf-8"))
    baseline = json.loads((SAFE / "codex_dev60_manifest.json").read_text(encoding="utf-8"))
    out = {"run_id": "20261003_cli_products_effort10", "status": "SUPPLEMENTARY", "private_test_run": False,
        "selected_model": "gpt-6-luna", "CLI_version": "0.160.0", "subscription_cost": "SUBSCRIPTION_INCLUDED",
        "new_calls": 22, "new_DEV_calls": 20, "synthetic_calls": 2, "reused_medium_calls": 10,
        "selection_method": plan["selection_method"], "profiles": {}, "paired_EM_counts": analysis["paired_em_counts"],
        "unsupported_efforts": ["instant", "none"], "benchmark_content_in_this_summary": False,
        "source_analysis": str(analysis_path.relative_to(ROOT)).replace("\\", "/"), "source_analysis_sha256": sha(analysis_path.read_bytes()),
        "plan_sha256": sha((SAFE / "effort10_plan_frozen.json").read_bytes()),
        "recommendation": {"retained_completed_DEV60_profile": "medium", "next_quality_focused_product_candidate": "high",
            "reason": "high rescued2 of9 scored cases with0 regressions vsmedium and fewer JSON failures; retain original full60 medium score, high larger-set accuracy unknown",
            "resource_caveat": "high reports substantially more output/reasoning tokens; latency dominated by fresh-process stock transport recovery",
            "limits": "single stochastic pass,n9; neither effort optimum nor causal superiority established; no full60 high extension thissession"}}
    for effort in ("low", "medium", "high"):
        s = analysis["profiles"][effort]["summary"]
        raw_path = RESTRICTED / ("codex_dev60_raw.jsonl" if effort == "medium" else "codex_effort10_" + effort + "_raw.jsonl")
        out["profiles"][effort] = {"attempted": s["n_attempted"], "completed": s["n_completed"], "n_scored": s["n_scored"],
            "EM_count": s["strict_em_count"], "EM": s["strict_set_em"], "F1": s["strict_set_f1"],
            "p50_s": s["latency_p50_s"], "p95_s": s["latency_p95_s"], "mean_s": s["latency_mean_s"],
            "invalid_option_sets": s["invalid_output"], "JSON_contract_failures": s["json_contract_failure"],
            "input_tokens": s["input_tokens"], "output_tokens": s["output_tokens"],
            "observed_tool_calls": analysis["profiles"][effort]["tool_calls_n"],
            "raw_usage_aggregate": usage_from_raw(raw_path, plan["selected_ids"])}
    target = SAFE / "effort_summary.json"
    write_new(target, out)
    columns = ["effort", "attempted", "completed", "n_scored", "EM_count", "EM", "F1", "p50_s", "p95_s", "mean_s", "input_tokens", "output_tokens", "JSON_contract_failures", "invalid_option_sets", "observed_tool_calls"]
    with (SAFE / "effort_comparison.csv").open("x", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns); writer.writeheader()
        for effort, row in out["profiles"].items():
            writer.writerow({"effort": effort, **{k: row[k] for k in columns if k != "effort"}})
    claims = []
    for effort in ("low", "medium", "high"):
        for field in ("EM", "F1", "EM_count", "n_scored", "p50_s", "p95_s", "output_tokens", "JSON_contract_failures"):
            claims.append({"claim_id": "codex_effort10_" + effort + "_" + field, "statement": "Supplementary product effort10 " + effort + ":" + field,
                "study_run_id": out["run_id"], "data_path": str(target.relative_to(ROOT)).replace("\\", "/"),
                "analysis_field": "/profiles/" + effort + "/" + field, "value": out["profiles"][effort][field],
                "data_sha256": sha(target.read_bytes()), "code_commit": baseline["code_commit_before_changes"],
                "code_identity_note": "parent commit plus exact executed adapter/runner snapshots in executed_code_effort10", "status": "SUPPLEMENTARY"})
    write_new(SAFE / "claims_effort_for_integration.json", {"claims": claims})
    table = []
    for effort, row in out["profiles"].items():
        reasoning = row["raw_usage_aggregate"]["exposed_reasoning_tokens"]
        table.append(f"| {effort} | {row['EM_count']}/{row['n_scored']} | {row['EM']:.6f} / {row['F1']:.6f} | {row['p50_s']:.3f} / {row['p95_s']:.3f} | {row['output_tokens']} / {reasoning} | {row['invalid_option_sets']} / {row['JSON_contract_failures']} |")
    report = "\n\n## Дополнительная проверка уровня reasoning: фиксированный effort10\n\n" + (
        "По уточнённому запросу авторов до low/high сохранён frozen plan: первый существующий DEV60 вопрос каждой из10 дисциплин, без gold/правильности/predictions в выборе. "
        "Из10 вопросов9 имеют разбираемый исходный reference; неопределённый десятый остаётся reference issue. Medium взят из уже выполненного DEV60 без повторения. "
        "Low и high получили по одной независимой синтетической compatibility проверке и по10 DEV calls: ровно22 новых product attempts. Все завершены, tools0, failures0. "
        "Каталог установленного Codex официально рекламирует low/medium/high/xhigh/max для Luna; instant и none отсутствуют и не запускались. Claude reasoning sweep не выполнялся: auth403 не зависит от ещё не измеренного качества модели.\n\n"
        "| Effort | EM count / scored | EM / F1 | p50 / p95, с | Output / reported reasoning tokens | Invalid sets / JSON failures |\n"
        "|---|---:|---:|---:|---:|---:|\n") + "\n".join(table) + (
        "\n\nInput tokens одинаковы:85065 на каждую десятку, включая product harness; это подтверждает совпадение измеренного объёма контекста, а не его raw-model эквивалентность. "
        "High против medium:2 дополнительных EM-correct,0 утраченных; low против medium:1/0. На всех трёх multi-answer вопросах EM0 при каждом effort; большая мыслительная нагрузка не устранила этот предел набора. "
        "Reported reasoning token field является metadata продукта;0 не доказывает отсутствие скрытого reasoning. Output уже включает reported reasoning, повторно складывать их нельзя. "
        "Latency смешивает reasoning, старт нового процесса и403 WebSocket→HTTPS fallback, а порядок medium→low→high не рандомизирован. n9, single stochastic pass и отсутствие интервалов/повторов не позволяют объявить optimum или причинное превосходство.\n\n"
        "**Автономная рекомендация:** сохранить уже выполненный полный medium DEV60 как текущую дополнительную продуктовую базовую линию; для следующего заранее замороженного quality-focused product протокола кандидат — high. "
        "Он дал2 дополнительных совпадения на scored9 и меньше JSON failures, но требует гораздо больше output/reasoning tokens; его качество на полном60 UNKNOWN. Low остаётся практичным кандидатом при более жёстком ограничении reasoning quota. "
        "Текущие числа не переносятся на TEST, дополнять high до60 ради улучшения статьи в этой сессии не стали. Mercury direct остаётся primary scientific cloud reference с прежними оговорками.\n\n"
        "Safe machine-readable: `results/20261003_cli_products/effort_summary.json`, `effort_comparison.csv`, `claims_effort_for_integration.json`. "
        "Исходные receipts и code snapshots сохранены; raw text остаётся ignored `.runtime/cli_products`.\n")
    with (ROOT / "docs/CLI_PRODUCT_BASELINES_20261003_RU.md").open("a", encoding="utf-8") as f: f.write(report)
    print(json.dumps({"effort_summary": str(target), "profiles": out["profiles"], "recommendation": out["recommendation"]}))


if __name__ == "__main__": main()
