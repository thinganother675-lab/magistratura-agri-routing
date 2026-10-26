"""Append-only tables from completed LM Studio API journals; never calls a model."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def valid_tokens(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def token_measure(rows, field):
    values = [(row["local"].get("usage") or {}).get(field) for row in rows]
    known = [value for value in values if valid_tokens(value)]
    return {"total": sum(known) if known else None, "coverage": len(known), "n": len(rows)}


def reasoning_measure(rows):
    values = [((row["local"].get("usage") or {}).get("completion_tokens_details") or {}).get("reasoning_tokens") for row in rows]
    known = [value for value in values if valid_tokens(value)]
    return {"total": sum(known) if known else None, "coverage": len(known), "n": len(rows)}


def table_row(run, manifest, model, meta, rows):
    summary = meta.get("summary") or {}
    if summary.get("n", 0) != len(rows):
        raise ValueError("Manifest/journal count mismatch; do not report a partially written run")
    if summary.get("correct", 0) != sum(bool(row["score"]["correct"]) for row in rows):
        raise ValueError("Manifest/journal correctness mismatch")
    input_usage = token_measure(rows, "prompt_tokens")
    output_usage = token_measure(rows, "completion_tokens")
    reasoning_usage = reasoning_measure(rows)
    native = meta.get("native_model_metadata") or {}
    quant = native.get("quantization") or {}
    return {"run": run.name, "model": model, "split": manifest["dataset_split"],
            "reasoning_profile": manifest.get("reasoning_profile"),
            "reasoning_effort_requested": meta.get("reasoning_effort_requested"),
            "state": "RESOURCE_STOP" if meta.get("resource_guard_stop") else "EARLY_STOP" if meta.get("early_stop") else meta.get("state"), "n": len(rows), "correct": summary.get("correct") if rows else None,
            "quality": summary.get("quality"), "errors": summary.get("errors") if rows else None,
            "latency_mean_s": summary.get("latency_mean_s"), "p50_s": summary.get("latency_p50_s"),
            "p95_s": summary.get("latency_p95_s"), "first_delta_p50_s": summary.get("client_first_delta_p50_s"),
            "client_tps_approx_p50": summary.get("client_completion_tps_approx_p50"),
            "input_tokens_known": input_usage["total"], "input_coverage": input_usage["coverage"],
            "output_tokens_known": output_usage["total"], "output_coverage": output_usage["coverage"],
            "reasoning_tokens_known": reasoning_usage["total"], "reasoning_coverage": reasoning_usage["coverage"],
            "reasoning_observed_n": summary.get("reasoning_observed_n"),
            "vram_mib_total_peak": meta.get("vram_mib_peak_sampled_total"),
            "ram_gib_system_peak": meta.get("ram_gib_peak_sampled_system_used"),
            "gpu_offload_requested": meta.get("requested_offload_ratio"),
            "actual_offloaded_layers": meta.get("actual_offloaded_layers"),
            "quantization": quant.get("name"),
            "file_gib": native.get("size_bytes", 0) / 2**30 if native.get("size_bytes") is not None else None,
            "cold_load_s": meta.get("cold_load_wall_s"),
            "resource_guard_stop": json.dumps(meta.get("resource_guard_stop")) if meta.get("resource_guard_stop") else None,
            "early_stop": meta.get("early_stop"), "phase_error": json.dumps(meta.get("phase_error")) if meta.get("phase_error") else None}


def collect(root=ROOT):
    records, details = [], {}
    for run in sorted((root / "results").glob("20261001*_lm_api")):
        path = run / "manifest.json"
        if not path.exists():
            continue
        manifest = read(path)
        # A running journal is never an immutable data source.
        if manifest.get("state") == "running":
            continue
        catalog_path = run / "catalog_before.json"
        catalog = {model["key"]: model for model in read(catalog_path)} if catalog_path.exists() else {}
        for model, meta in manifest.get("models", {}).items():
            if not meta.get("native_model_metadata") and model in catalog:
                meta = {**meta, "native_model_metadata": catalog[model]}
            journal = run / (model + "_raw.jsonl")
            rows = load_rows(journal) if journal.exists() else []
            record = table_row(run, manifest, model, meta, rows)
            records.append(record)
            details[run.name + "/" + model] = {"record": record, "summary": meta.get("summary"),
                "sample_ids": [row["sample"]["id"] for row in rows],
                "raw_sha256": hashlib.sha256(journal.read_bytes()).hexdigest() if journal.exists() else None,
                "actual_load_config": meta.get("actual_load_config"),
                "requested_parameters": manifest.get("requested_parameters"),
                "source_manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return records, details


def representative(records):
    selected = {}
    for row in records:
        if row["split"] != "old_dev" or row["reasoning_profile"] != "off-or-low":
            continue
        current = selected.get(row["model"])
        # Prefer the largest saved set, then the latest run, without selecting by score.
        if current is None or (row["n"], row["run"]) > (current["n"], current["run"]):
            selected[row["model"]] = row
    return list(selected.values())


def write_csv(path, records):
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def report():
    records, details = collect()
    if not records:
        raise RuntimeError("No completed modern API journals available")
    run_id = "20261001_api_tables_" + uuid.uuid4().hex[:8]
    directory = ROOT / "results" / run_id
    directory.mkdir(exist_ok=False)
    selected = representative(records)
    write_csv(directory / "all_api_runs.csv", records)
    write_csv(directory / "representative_local_models.csv", selected)
    totals = {"requests": sum(row["n"] for row in records),
              "input_tokens_known": sum(row["input_tokens_known"] or 0 for row in records),
              "output_tokens_known": sum(row["output_tokens_known"] or 0 for row in records),
              "reasoning_tokens_known": sum(row["reasoning_tokens_known"] or 0 for row in records),
              "input_usage_coverage_n": sum(row["input_coverage"] for row in records),
              "output_usage_coverage_n": sum(row["output_coverage"] for row in records),
              "reasoning_usage_coverage_n": sum(row["reasoning_coverage"] for row in records)}
    payload = {"created_utc": datetime.now(timezone.utc).isoformat(), "phase": "DEVELOPMENT ONLY",
               "selection_rule": "largest completed off-or-low old_dev set, latest run tie-break, never highest score",
               "all_runs": records, "representative": selected, "details": details, "usage": totals,
               "limitations": ["Different N is not an equal quality comparison", "Client approximate TPS includes provider counted reasoning; not native decode speed",
                   "First delta can be reasoning or answer; client HTTP wall time", "VRAM device total / RAM whole system sampled, other apps included",
                   "Requested offload ratio is not a measured layer count", "Historical CLI and modern API are distinct measurement series",
                   "No independent holdout in these tables"]}
    with (directory / "summary.json").open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
    def fmt(value, digits=2):
        return "UNKNOWN" if value is None else f"{value:.{digits}f}" if isinstance(value, (int, float)) else str(value)
    lines = ["# LM Studio: токены и ресурсы контролируемых API-серий", "", "01.10.2026. Развивающий набор; подтверждающий holdout здесь не запускался.", "",
             f"Сводка: `results/{run_id}/summary.json`. Все серии, включая режим reasoning по умолчанию и двуязычные повторы, — в all_api_runs.csv.", "",
             "| Модель | Correct/N | p50 / p95, с | Input / output tokens | Reasoning tokens | TTFT client, с | Client approx tok/s | VRAM MiB total | RAM GiB system | Offload requested | Quant | Ошибки |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|"]
    for row in selected:
        outcome = f"{row['correct']}/{row['n']}" if row['n'] else "NOT RUN"
        lines.append(f"| {row['model']} | {outcome} | {fmt(row['p50_s'],3)} / {fmt(row['p95_s'],3)} | {fmt(row['input_tokens_known'],0)} / {fmt(row['output_tokens_known'],0)} | {fmt(row['reasoning_tokens_known'],0)} ({row['reasoning_coverage']}/{row['n']}) | {fmt(row['first_delta_p50_s'],3)} | {fmt(row['client_tps_approx_p50'])} | {fmt(row['vram_mib_total_peak'],0)} | {fmt(row['ram_gib_system_peak'])} | {row['gpu_offload_requested']} | {row['quantization']} | {fmt(row['errors'],0)} |")
    lines += ["", f"Все API-серии: {totals['requests']} запросов, известно {totals['input_tokens_known']} входных и {totals['output_tokens_known']} выходных токенов; coverage {totals['input_usage_coverage_n']}/{totals['requests']} и {totals['output_usage_coverage_n']}/{totals['requests']}. Reasoning входит в output; его нельзя повторно прибавлять к расходу.", "",
              "Temperature=0, top_p=1, seed=42, max_tokens=512, strict JSON schema; context=4096, parallel=1. off-or-low использует экспериментальное поле reasoning_effort=none либо low для GPT-OSS; фактические reasoning deltas/usage сохранены. Нулевая reasoning coverage не доказывает отсутствие reasoning.", "",
              "Выбор представительной серии сделан по размеру, затем дате, без отбора лучшего результата. Ранние остановки и NOT RUN сохранены. Для сравнений качества используйте одинаковые ID и N; категории и языки доступны в summary.json.", "",
              "TTFT и скорость измерены клиентом по SSE. Client TPS приблизителен и исключает первый межтокенный интервал; он не равен старому backend decode tok/s. VRAM/RAM включают другие процессы. Число фактически выгруженных на GPU слоёв UNKNOWN; requested ratio приведён явно."]
    (ROOT / "docs/HOME_API_TOKEN_RESOURCE_TABLE_RU.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(directory)
    return directory


if __name__ == "__main__":
    report()
