# SPDX-License-Identifier: Apache-2.0
"""Recompute safe historical DEV quality/resource diagnostics without inference.

Restricted raw journals are hash-checked and reduced to timing scalars only.
Questions, answer letters, gold strings, headers and environment never leave
ignored .runtime. Existing measured outputs are not changed or rerun.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agro_route.mera_screen_analysis_20261003 import paired_correctness
from agro_route.resource_analysis_20261003 import (
    ROW_FIELDS, confidence_analysis, distribution, fixed_threshold_replay, grouped_pairs,
    paired_bootstrap, validate_rows,
)

MODEL_KEYS = ("qwen3.5-9b", "qwen3.8-27b", "gemma-4-26b-a4b-it")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def csv_write(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def source_loader():
    path = ROOT / "scripts/analyze_mera_local_screen_20261003.py"
    spec = importlib.util.spec_from_file_location("historical_source_loader", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def safe_raw_timing(rows, manifest, raw_path):
    if sha(raw_path) != manifest["raw_sha256"]:
        raise ValueError("Historical raw journal hash mismatch")
    raw = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines() if line]
    benchmark = [r for r in raw if r["kind"] == "benchmark"]
    if len(benchmark) != len(rows):
        raise ValueError("Raw benchmark coverage differs from safe measurements")
    augmented = []
    for row, record in zip(rows, benchmark):
        if row["latency_s"] != record["latency_s"] or row["output_tokens"] != record["usage"]["completion_tokens"]:
            raise ValueError("Raw and safe request ordering differ")
        timing = record["timing"]
        first, last = timing.get("first_nonempty_delta_s_client"), timing.get("last_nonempty_delta_s_client")
        span = last - first if isinstance(first, (int, float)) and isinstance(last, (int, float)) and last >= first else None
        augmented.append({**row, "generation_span_s": span, "finish_reason": record["raw"].get("finish_reason")})
    return augmented


def resource_summary(manifest, weight):
    loads = manifest["loads"]
    headroom = {}
    for phase in ("headroom_before", "headroom_before_load", "headroom_after", "headroom_latest"):
        headroom[phase] = {
            "ram_available": distribution([x.get(phase, {}).get("ram_available_gib") for x in loads], unit="GiB"),
            "gpu_free": distribution([x.get(phase, {}).get("gpu_free_mib") for x in loads], unit="MiB")}
    return {
        "exact_gguf_path": weight["relative_model_path"], "exact_gguf_sha256": weight["sha256"],
        "exact_gguf_bytes": weight["bytes"], "exact_gguf_gib": weight["bytes"] / 2**30,
        "backend_metadata_size_bytes": manifest["model_size_bytes"],
        "backend_size_is_not_exact_gguf_bytes": True,
        "quantization": weight["quantization"]["name"],
        "parameter_count_backend_label": manifest["native_model_metadata"].get("params_string"),
        "parameter_count_official_documentation_verified_here": False,
        "context_length": manifest["load_config"]["context_length"],
        "concurrency": manifest["load_config"]["parallel"],
        "reasoning_requested": manifest["reasoning_effort_requested"],
        "gpu_offload_requested": manifest["gpu_requested"], "actual_gpu_layers": manifest["actual_gpu_layers"],
        "whole_gpu_peak_mib": manifest["resource_metrics"]["vram_mib_peak_sampled_total"],
        "whole_system_ram_peak_gib": manifest["resource_metrics"]["ram_gib_peak_sampled_system_used"],
        "resource_scope": manifest["resource_metrics"]["resource_scope"],
        "resource_sample_count": manifest["resource_metrics"]["samples"],
        "resource_poll_error_count": len(manifest["resource_metrics"]["resource_poll_errors"]),
        "request_memory_distributions": None,
        "request_memory_distribution_status": "HISTORICAL_PEAKS_AND_LOAD_HEADROOM_ONLY_NO_SAVED_SAMPLE_SERIES",
        "per_process_vram_mib": None, "per_process_rss_gib": None, "energy_joules": None,
        "loads_n": len(loads), "first_load_s": loads[0]["load_latency_s"],
        "load_time": distribution([x["load_latency_s"] for x in loads], unit="s"),
        "warmup_time": distribution([x["warmup_latency_s"] for x in loads], unit="s"),
        "headroom_distributions_over_load_events": headroom,
        "load_failure": manifest["model_load_failure"], "cleanup_success": manifest["cleanup_success"],
        "background_machine_state_controlled": False,
    }


def figures(out, models, rows_by_model, confidence):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    labels = {MODEL_KEYS[0]: "Qwen3.5 9B (Q8_0)", MODEL_KEYS[1]: "Qwen3.8 27B (Q4_K_M)", MODEL_KEYS[2]: "Gemma4 26B-A4B (IQ4_NL_XL)"}
    point_labels = dict(zip(MODEL_KEYS, ("Qwen9", "Qwen27", "Gemma26")))
    colors = {MODEL_KEYS[0]: "#1976a3", MODEL_KEYS[1]: "#c54a35", MODEL_KEYS[2]: "#488640"}
    plt.rcParams.update({"font.size": 10, "figure.dpi": 130, "savefig.dpi": 200})
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.1), layout="constrained")
    for key, m in models.items():
        xs = [m["latency"]["p50"], m["resources"]["whole_gpu_peak_mib"] / 1024, m["resources"]["whole_system_ram_peak_gib"]]
        for ax, x in zip(axes, xs):
            ax.scatter(x, 100 * m["quality"]["strict_set_em"], color=colors[key], s=70, label=labels[key])
        axes[0].annotate(point_labels[key], (xs[0],100 * m["quality"]["strict_set_em"]), xytext=(-5,7) if key==MODEL_KEYS[1] else (5,7), ha="right" if key==MODEL_KEYS[1] else "left", textcoords="offset points", fontsize=8)
    for ax, name in zip(axes, ("Median request latency (s)", "Sampled whole-GPU peak (GiB)", "Sampled whole-system RAM peak (GiB)")):
        ax.set_xlabel(name); ax.set_ylabel("STRICT_SET_EM (%)"); ax.grid(alpha=.25); ax.set_ylim(46,54)
    fig.suptitle("Historical DEV293: tradeoffs, no scalar winner; 289 valid references")
    handles, legend_labels = axes[0].get_legend_handles_labels();fig.legend(handles, legend_labels, loc="outside lower center", ncol=3, fontsize=8)
    fig.savefig(out / "historical_quality_resource_pareto.png");fig.savefig(out / "historical_quality_resource_pareto.svg");plt.close(fig)
    fig, ax = plt.subplots(figsize=(7,4), layout="constrained")
    for key, rows in rows_by_model.items():
        values=np.sort([r["latency_s"] for r in rows]);ax.step(values,np.arange(1,len(values)+1)/len(values), where="post",label=labels[key],color=colors[key])
    ax.set(xlabel="End-to-end request latency (s)",ylabel="Empirical cumulative fraction",title="Historical DEV293 latency; load/warmup excluded");ax.grid(alpha=.25);ax.legend(fontsize=8)
    fig.savefig(out / "historical_latency_ecdf.png");fig.savefig(out / "historical_latency_ecdf.svg");plt.close(fig)
    fig, ax = plt.subplots(figsize=(6.5,4), layout="constrained")
    for key in MODEL_KEYS[:2]:
        bins=[b for b in confidence[key]["confidence_bins"] if b["n"]]
        ax.plot([b["mean_lexical_confidence"] for b in bins],[b["observed_accuracy"] for b in bins],"o-",label=labels[key],color=colors[key])
        for b in bins: ax.annotate(str(b["n"]),(b["mean_lexical_confidence"],b["observed_accuracy"]),xytext=(-4,4 if key==MODEL_KEYS[0] else -10) if b["mean_lexical_confidence"]>.9 else (3,4 if key==MODEL_KEYS[0] else -10),ha="right" if b["mean_lexical_confidence"]>.9 else "left",textcoords="offset points",fontsize=7)
    ax.set(xlabel="Mean emitted-choice-token geometric probability",ylabel="Observed strict accuracy in bin",title="DEV lexical confidence bins (labels = bin counts)",xlim=(0,1),ylim=(0,1));ax.grid(alpha=.25);ax.legend(fontsize=8)
    fig.savefig(out / "historical_confidence_bins.png");fig.savefig(out / "historical_confidence_bins.svg");plt.close(fig)


def report(result, path):
    m=result["models"];pair=result["paired_qwen9_minus_qwen27"];unc=result["paired_bootstrap"]
    lines=["# Qwen9 и Qwen27: парный анализ существующего DEV293", "",
           "3 октября 2026. **DEV / HISTORICAL / SIMULATED**. Новых model/API calls нет; private TEST не читался и не выполнялся. Для качества использованы те же 293 задания, 289 исходных разбираемых references и 4 unresolved references. `STRICT_SET_EM/F1` — локальные метрики, не официальный MERA production scorer. DEV293 включает прежний DEV60 и использовался для выбора моделей; независимым holdout он не является.","",
           "Гипотеза H1: Qwen9 сохраняет большую часть наблюдаемого качества Qwen27, существенно снижая задержку и спрос на память. Анализ не задаёт порог победителя и не пытается доказать превосходство Qwen9. Сравниваются установленные конфигурации с разными квантами и offload, а не изолированное влияние числа параметров.","",
           "| Конфигурация | EM | F1 | mean/p50/p90/p95/p99, с | TTFT p50, с | client tok/s p50 | whole GPU peak, MiB | whole RAM peak, GiB | exact GGUF, GiB |","|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for k,v in m.items():
        q,l,r=v["quality"],v["latency"],v["resources"]
        lines.append(f"| {k} / {r['quantization']} | {q['strict_em_count']}/{q['n_scored']} = {100*q['strict_set_em']:.2f}% | {q['strict_set_f1']:.6f} | {'/'.join(f'{l[x]:.3f}' for x in ('mean','p50','p90','p95','p99'))} | {v['ttft']['p50']:.3f} | {v['client_tps']['p50']:.3f} | {r['whole_gpu_peak_mib']:.0f} | {r['whole_system_ram_peak_gib']:.3f} | {r['exact_gguf_gib']:.3f} |")
    ratio=result["ratios_qwen9_vs_qwen27"]
    lines += ["",f"EM9−EM27 = **{100*unc['em_left_minus_right']:.3f} п.п.**; F1 difference {unc['f1_left_minus_right']:.6f}. Quality retention EM9/EM27 = **{100*ratio['em_retention']:.2f}%**, F1 retention {100*ratio['f1_retention']:.2f}%. Median latency27/9 = **{ratio['median_latency_27_over_9']:.3f}×**, p95 ratio {ratio['p95_latency_27_over_9']:.3f}×. Наблюдаемая разница whole-device peak27−9 = {ratio['whole_gpu_peak_27_minus_9_mib']:.0f} MiB; whole-system RAM peak27−9 = {ratio['whole_system_ram_peak_27_minus_9_gib']:.3f} GiB. Это не доказанный per-model allocation.","",
              f"Парные ответы: обе верны **{pair['both_correct']}**, только Qwen9 **{pair['left_only_correct']}**, только Qwen27 **{pair['right_only_correct']}**, обе неверны **{pair['both_incorrect']}**. Qwen27 имеет на 9 strict-correct больше; расхождения гораздо шире, чем итоговая разница. Domain-stratified paired bootstrap (10 000, seed 20261003): descriptive95% EM difference [{100*unc['em_interval'][0]:.3f}; {100*unc['em_interval'][1]:.3f}] п.п.; F1 [{unc['f1_interval'][0]:.6f}; {unc['f1_interval'][1]:.6f}]. Интервал отражает чувствительность имеющегося DEV к resampling; не является confirmatory significance, equivalence или noninferiority доказательством.","",
              "Qwen9 занимает благоприятную область качества и ресурсов в этих измеренных конфигурациях; Qwen27 сохраняет наибольший EM из трёх. Gemma26 даёт наибольший F1 и промежуточную задержку, поэтому универсального победителя нет. Предпочтение зависит от допустимого времени и памяти; бюджеты должны быть зафиксированы авторами до независимого теста.","",
              "## Дисциплины и кратность ответа","","| Дисциплина | N | EM9 | EM27 | difference9−27, п.п. | F1 difference |","|---|---:|---:|---:|---:|---:|"]
    for group,v in result["by_domain"].items():
        lines.append(f"| {group} | {v['n']} | {v['left_em_count']}/{v['n']} | {v['right_em_count']}/{v['n']} | {100*v['em_left_minus_right']:.2f} | {v['f1_left_minus_right']:.6f} |")
    lines += ["","| Кратность | N | EM9 | EM27 | F1 9/27 |","|---|---:|---:|---:|---:|"]
    for group,v in result["by_answer_cardinality"].items():
        lines.append(f"| {group} | {v['n']} | {v['left_em_count']}/{v['n']} | {v['right_em_count']}/{v['n']} | {v['left_f1']:.6f}/{v['right_f1']:.6f} |")
    lines += ["","Кратность исходного reference используется только для post-hoc анализа; inference/router не получает gold cardinality. Дисциплины доступны как observable metadata, но их accuracies здесь уже DEV fit. Их неоднородность — основание для будущей простой заранее замороженной проверки, а не готовая policy с доказанной пользой.","",
              "## Исторические ресурсы, загрузка и ограничения","",
              "Доступны 30 load/warmup событий на модель (reload через 10 заданий), peak и headroom before/after. Полный исторический ряд ресурсных samples не сохранён; поэтому request-level memory distributions, process RSS/VRAM и energy остаются UNKNOWN. Whole-GPU/RAM включают обычные приложения, sampling около0.5с плюс subprocess overhead; p99 из293 запросов опирается лишь на несколько tail observations. Новая отдельная TELEMETRY выборка нужна для контролируемой systems характеристики.","",
              "TTFT — измеренный client first nonempty streamed delta; backend TTFT не раскрыт. Client tok/s ≈ reported completion tokens/(last−first nonempty delta), включает counted reasoning и пропускает интервал первого токена; ответы короткие, поэтому это не чистая аппаратная generation speed. Prompt processing tok/s UNKNOWN. Load timing включает CLI overhead; первая загрузка не гарантированно cold, следующие reload могут использовать OS cache.","",
              "| Конфигурация | loads | first load / median reload, с | warmup median, с | context / concurrency | requested offload | actual layers | invalid/error/load failure |","|---|---:|---:|---:|---:|---|---|---:|"]
    for k,v in m.items():
        r,q=v["resources"],v["quality"]
        lines.append(f"| {k} | {r['loads_n']} | {r['first_load_s']:.3f}/{r['load_time']['p50']:.3f} | {r['warmup_time']['p50']:.3f} | {r['context_length']}/{r['concurrency']} | {r['gpu_offload_requested']} | UNKNOWN | {q['invalid_output']}/{q['errors']}/{int(r['load_failure'])} |")
    lines += ["","Все293 benchmark responses трёх моделей имеют finish_reason stop; crashes/load/transport failures в этой завершённой серии0. Это не оценка долговременной надёжности и не отменяет failures других screen-конфигураций. Exact GGUF SHA256+bytes берутся из checksummed file receipt, не native `size_bytes`, который содержит больше байт; официальное число параметров в этом анализе отдельно не проверялось. Quant label означает mixed GGUF types, не одинаковую битность всех tensor elements.","",
              "## Qwen9 confidence и saved-output routing","",
              "Lexical confidence — geometric mean вероятностей выпущенных Latin option tokens, не P(верный ответ). Поэтому ECE/Brier не вычисляются; график показывает empirical accuracy по confidence bins без утверждения calibration.","",
              "| Модель | N scored confidence | AUC | descriptive95% interval | single AUC | multiple AUC |","|---|---:|---:|---:|---:|---:|"]
    for key in MODEL_KEYS[:2]:
        c=result["confidence"][key];sub=result["confidence_by_cardinality"][key]
        lines.append(f"| {key} | {c['n_observed_scored']} | {c['auc_correctness']:.6f} | [{c['auc_interval'][0]:.6f}; {c['auc_interval'][1]:.6f}] | {sub['single']['auc_correctness']:.6f} | {sub['multiple']['auc_correctness']:.6f} |")
    replay=result["qwen9_mercury_dev60_replay"]
    lines += ["","Это exploratory correctness ranking на том же DEV. Уверенный формат не является уверенным знанием. Fixed-grid replay использует сохранённый Qwen9 **Stage1 DEV60** и Mercury2.5 instant512/.5 на тех же prompt hashes; повторный Qwen9 Stage2 subset не подменяет Stage1. Gold используется только offline scoring, не routing. Все thresholds сохранены, новый router не обучался.","",
              "| threshold | cloud calls/60 (simulated) | EM correct/59 | F1 | invalid/error |","|---|---:|---:|---:|---:|"]
    for v in replay["grid"]:
        lines.append(f"| {v['threshold']} | {v['cloud_calls_if_deployed']} | {v['strict_em_count']}/59 | {v['strict_set_f1']:.6f} | {v['invalid_output']}/{v['errors']} |")
    lines += ["","**Confidence сигнал существует, но польза делегирования текущему Mercury не установлена**: local-only37/59; ни один ненулевой fixed threshold не улучшает этот EM, лучший даёт35/59. Mercury-only31/59 включает4 length failures. Формат-only fallback вызывает0cloud на этих данных. Live cascade latency/cost не измерялись; actual requests saved0. Нет full293 cloud comparator, и нет независимой проверки threshold/domain routing. Не следует обучать learned router или называть replay экономией платных запросов.","",
              "## Связь с уже имеющейся статьёй","",
              "HOME150 — искусственный технический holdout от тех же авторов, не внешняя агрономическая expertise. Его composite score нельзя сравнивать с MERA strict EM/F1. Прежний OpenRouter — supplementary provider/harness screen с собственной identity/eligibility/неполным coverage; это не равная raw-local конфигурация. Mercury2.5 — direct provisional scientific cloud reference, operational TEST readiness не установлена из-за4/60 length. Новых cloud API calls и затрат этот анализ не делает. Publication plan и authorship требуют совместного human approval; рукописи здесь не переписаны и ничего не опубликовано.","",
              "Машиночитаемые результаты: `results/20261003_resource_analysis/analysis.json`, `models.csv`, `domains.csv`, `cardinality.csv`, `confidence_thresholds.csv`, `cascade_dev60.csv`. Рисунки: Pareto tradeoff, latency ECDF, confidence bins. Reproduction: `.venv/Scripts/python.exe scripts/analyze_resource_efficiency_20261003.py`; hashes всех прочитанных данных и кода входят в analysis.json. DEV evidence status сохраняется."]
    path.write_text("\n".join(lines)+"\n",encoding="utf-8")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-dir",type=Path,default=ROOT/"results/20261003_local_screen_571682f5")
    parser.add_argument("--output-dir",type=Path,default=ROOT/"results/20261003_resource_analysis")
    args=parser.parse_args();safe=args.study_dir.resolve();out=args.output_dir.resolve()
    if not safe.is_relative_to(ROOT/"results") or not out.is_relative_to(ROOT/"results"):
        raise ValueError("Safe private-repository results directories required")
    out.mkdir(parents=True,exist_ok=True)
    loader=source_loader();profiles,rows2,protocol,_,hashes=loader.load_profiles(safe,"dev293")
    _,rows1,_,_,hashes1=loader.load_profiles(safe,"dev60")
    profiles={p["model_key"]:p for p in profiles};models={};all_rows={}
    weights={m["model_key"]:m for m in read(safe/"installed_weight_checksums.json")["models"]}
    hashes[str((safe/"installed_weight_checksums.json").relative_to(ROOT)).replace("\\","/")]=sha(safe/"installed_weight_checksums.json")
    confidence={};by_cardinality={}
    for key in MODEL_KEYS:
        profile=profiles[key]
        if profile["status"] != "COMPLETE": raise ValueError("Historical complete configuration required")
        manifest=read(ROOT/profile["manifest_path"])
        raw_path=ROOT/".runtime/mera"/safe.name/"dev293"/f"{key}_raw.jsonl"
        rows=safe_raw_timing(rows2[key],manifest,raw_path);all_rows[key]=rows
        hashes[raw_path.relative_to(ROOT).as_posix()]=sha(raw_path)
        quality=validate_rows(rows,protocol["dev293_ids"])
        models[key]={"status":"DEV_HISTORICAL", "quality":quality,
                     "latency":distribution([r["latency_s"] for r in rows],unit="s"),
                     "ttft":distribution([r["ttft_s"] for r in rows],unit="s"),
                     "generation_span":distribution([r["generation_span_s"] for r in rows],unit="s"),
                     "client_tps":distribution([r["client_tps"] for r in rows],unit="tokens/s"),
                     "backend_tps":distribution([r["backend_tps"] for r in rows],unit="tokens/s"),
                     "prompt_processing_tokens_per_second":None,
                     "input_tokens":sum(r["input_tokens"] for r in rows),"output_tokens":sum(r["output_tokens"] for r in rows),
                     "finish_reason_stop_n":sum(r["finish_reason"]=="stop" for r in rows),
                     "resources":resource_summary(manifest,weights[key])}
        confidence[key]=confidence_analysis(rows,protocol["dev293_ids"])
        by_cardinality[key]={}
        for group,card in (("single",1),("multiple",None)):
            subgroup=[r for r in rows if r["gold_valid"] and (r["gold_cardinality"]==1 if card==1 else r["gold_cardinality"]>1)]
            by_cardinality[key][group]=confidence_analysis(subgroup,[r["item_id"] for r in subgroup])
    q9,q27=MODEL_KEYS[:2];a,b=models[q9],models[q27]
    cloud_path=ROOT/"results/20261003_cloud_budget_only_c1184a27/mercury25_instant512_t05_dev60_combined.json"
    cloud=[{k:v for k,v in r.items() if k in ROW_FIELDS}
           for r in loader.normalize_rows(read(cloud_path)["rows"])]
    hashes[cloud_path.relative_to(ROOT).as_posix()]=sha(cloud_path)
    hashes.update(hashes1)
    for p in (Path(__file__),ROOT/"src/agro_route/resource_analysis_20261003.py",ROOT/"src/agro_route/mera_screen_analysis_20261003.py",ROOT/"scripts/analyze_mera_local_screen_20261003.py"):
        hashes[p.relative_to(ROOT).as_posix()]=sha(p)
    result={"run_id":out.name,"status":"DEV","created_utc":datetime.now(timezone.utc).isoformat(),
            "analysis_code_commit":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
            "uncommitted_analysis_source_hashes_recorded":True,"historical_run_id":safe.name,
            "source_hashes":hashes,"private_test_run":False,"new_inference_calls":0,"new_paid_api_spend_usd":0,
            "independent_holdout":False,"models":models,
            "paired_qwen9_minus_qwen27":paired_correctness(rows2[q9],rows2[q27],protocol["dev293_ids"]),
            "paired_bootstrap":paired_bootstrap(rows2[q9],rows2[q27],protocol["dev293_ids"]),
            "by_domain":grouped_pairs(rows2[q9],rows2[q27],protocol["dev293_ids"],field="domain"),
            "by_answer_cardinality":grouped_pairs(rows2[q9],rows2[q27],protocol["dev293_ids"],field="answer_cardinality"),
            "confidence":confidence,"confidence_by_cardinality":by_cardinality,
            "qwen9_mercury_dev60_replay":fixed_threshold_replay(rows1[q9],cloud,protocol["dev60_ids"]),
            "ratios_qwen9_vs_qwen27":{"em_retention":a["quality"]["strict_set_em"]/b["quality"]["strict_set_em"],
                "f1_retention":a["quality"]["strict_set_f1"]/b["quality"]["strict_set_f1"],
                "median_latency_27_over_9":b["latency"]["p50"]/a["latency"]["p50"],
                "p95_latency_27_over_9":b["latency"]["p95"]/a["latency"]["p95"],
                "whole_gpu_peak_27_minus_9_mib":b["resources"]["whole_gpu_peak_mib"]-a["resources"]["whole_gpu_peak_mib"],
                "whole_system_ram_peak_27_minus_9_gib":b["resources"]["whole_system_ram_peak_gib"]-a["resources"]["whole_system_ram_peak_gib"],
                "exact_gguf_size_27_minus_9_bytes":b["resources"]["exact_gguf_bytes"]-a["resources"]["exact_gguf_bytes"]}}
    write(out/"analysis.json",result)
    model_csv=[]
    for key,v in models.items():
        q,r=v["quality"],v["resources"]
        row={"model_key":key,"status":"DEV_HISTORICAL","n_attempted":q["n_attempted"],"n_scored":q["n_scored"],"em_count":q["strict_em_count"],"strict_set_em":q["strict_set_em"],"strict_set_f1":q["strict_set_f1"]}
        row.update({"latency_"+k+"_s":v["latency"][k] for k in ("mean","p50","p90","p95","p99")})
        row.update(ttft_p50_s=v["ttft"]["p50"],client_tps_p50=v["client_tps"]["p50"],backend_tps_p50=v["backend_tps"]["p50"],
                   exact_gguf_bytes=r["exact_gguf_bytes"],exact_gguf_sha256=r["exact_gguf_sha256"],quantization=r["quantization"],whole_gpu_peak_mib=r["whole_gpu_peak_mib"],whole_ram_peak_gib=r["whole_system_ram_peak_gib"],first_load_s=r["first_load_s"],load_p50_s=r["load_time"]["p50"],warmup_p50_s=r["warmup_time"]["p50"],invalid=q["invalid_output"],errors=q["errors"])
        model_csv.append(row)
    csv_write(out/"models.csv",model_csv)
    for name,values in (("domains",result["by_domain"]),("cardinality",result["by_answer_cardinality"])):
        csv_write(out/(name+".csv"),[{"group":g,**{k:v for k,v in value.items() if k!="discordance"}} for g,value in values.items()])
    csv_write(out/"confidence_thresholds.csv",[{"model_key":key,**row} for key,c in confidence.items() for row in c["selective_thresholds"]])
    csv_write(out/"cascade_dev60.csv",result["qwen9_mercury_dev60_replay"]["grid"])
    figures(out,models,all_rows,confidence)
    write(out/"figure_provenance.json",{"status":"DEV_HISTORICAL","source":"analysis.json","source_sha256":sha(out/"analysis.json"),
          "files":{p.name:sha(p) for p in sorted(out.glob("historical_*"))},"restricted_source_content_included":False})
    report(result,ROOT/"docs/QWEN9_VS_QWEN27_DEV_ANALYSIS_20261003_RU.md")
    print(json.dumps({"result":str(out/"analysis.json"),"paired":result["paired_qwen9_minus_qwen27"],"bootstrap":result["paired_bootstrap"],"qwen9_auc":confidence[q9]["auc_correctness"],"qwen27_auc":confidence[q27]["auc_correctness"]},ensure_ascii=False))


if __name__=="__main__":
    if hasattr(sys.stdout,"reconfigure"):sys.stdout.reconfigure(encoding="utf-8",errors="replace")
    main()
