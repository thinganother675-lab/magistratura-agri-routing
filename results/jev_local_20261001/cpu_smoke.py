"""Reproducible local CPU smoke of a pinned non-generative decision model.

Diagnostic development cases; never an independent final holdout or Jev-parity
evaluation. Uses only local weights and blocks Hub/network downloads at inference.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
import statistics
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "results/jev_local_20261001/cpu_smoke"
MODEL_SHA = "9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204"
TOKENIZER_SHA = "609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f"
CRITERIA = {
    "gdd": "Growing degree days from daily minimum and maximum temperature and a base temperature.",
    "vpd": "Vapor pressure deficit from air temperature and relative humidity.",
    "et0": "Reference evapotranspiration using radiation, temperature, humidity, wind and location.",
    "precipitation": "Sum rainfall or calculate rainfall minus specified water demand.",
    "abstain": "Ask for missing essential measurements; do not infer or fabricate missing inputs.",
    "qa": "Agricultural conceptual explanation which needs no numerical weather calculation.",
}
CASES = [
    ("gdd_en", "en", "Calculate growing degree days. Tmin=12 C, Tmax=24 C, base temperature=10 C.", "gdd", False),
    ("gdd_ru", "ru", "Рассчитать сумму эффективных температур за день. Минимум 12 °C, максимум 24 °C, базовая температура 10 °C.", "gdd", False),
    ("vpd_en", "en", "Calculate vapor pressure deficit. Air temperature=25 C, relative humidity=60 percent.", "vpd", False),
    ("vpd_ru", "ru", "Рассчитайте дефицит давления водяного пара: температура воздуха 25 °C, относительная влажность 60 процентов.", "vpd", False),
    ("et0_en", "en", "Find FAO56 reference evapotranspiration: air temperature=20 C, net radiation=12 MJ/m2/day, ground heat=0, wind at2m=2 m/s, pressure=100 kPa, actual vapor pressure=1.4 kPa, saturation vapor pressure=2.34 kPa, slope=0.145 kPa/C, psychrometric constant=0.066 kPa/C.", "et0", False),
    ("et0_ru", "ru", "Рассчитайте эталонную эвапотранспирацию FAO56: температура 20 °C, чистая радиация 12 МДж/м2/сутки, поток тепла почвы 0, ветер на2м 2 м/с, давление 100 кПа, фактическое давление пара 1.4 кПа, давление насыщения 2.34 кПа, наклон кривой 0.145 кПа/°C, психрометрическая постоянная 0.066 кПа/°C.", "et0", False),
    ("rain_en", "en", "Total rainfall over three days was 4,7,2 mm. Sum rainfall and compare with stated crop water demand of20 mm.", "precipitation", False),
    ("rain_ru", "ru", "За три дня выпало 4, 7 и 2 мм осадков. Найдите общую сумму и разницу относительно заданной потребности культуры 20 мм.", "precipitation", False),
    ("missing_en", "en", "Calculate vapor pressure deficit. Air temperature=25 C; relative humidity is not available. Do not assume missing data.", "abstain", True),
    ("missing_ru", "ru", "Рассчитайте дефицит давления водяного пара. Температура 25 °C; относительная влажность неизвестна. Не подставляйте предположения.", "abstain", True),
    ("qa_en", "en", "Explain why crop rotation can reduce the spread of some soil-borne crop diseases.", "qa", False),
    ("qa_ru", "ru", "Объясните, почему севооборот способен уменьшить распространение некоторых почвенных болезней сельскохозяйственных культур.", "qa", False),
]

def percentile(values, q):
    values = sorted(values)
    pos = (len(values) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(values)-1)
    return values[lo] + (values[hi] - values[lo]) * (pos-lo)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="Fresh directory only; default generates timestamp plus UUID")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--state", help="Optional single text instead of diagnostic set; outputs typed routing decision")
    args = parser.parse_args()
    out = args.output or DEFAULT_OUT / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8])
    out.mkdir(parents=True, exist_ok=False)
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "USE_TF": "0", "CUDA_VISIBLE_DEVICES": "", "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1"})
    import torch
    import psutil
    import laya
    torch.set_num_threads(args.threads)
    torch.manual_seed(0)
    model_path = ROOT / ".runtime/jev/models/laya-multilingual"
    tokenizer_config_before = hashlib.sha256((model_path / "tokenizer/tokenizer_config.json").read_bytes()).hexdigest()
    hashes = {}
    for filename, expected in {"model.safetensors": MODEL_SHA, "tokenizer/tokenizer.json": TOKENIZER_SHA}.items():
        h = hashlib.sha256()
        with (model_path / filename).open("rb") as handle:
            for chunk in iter(lambda: handle.read(8*1024*1024), b""):
                h.update(chunk)
        actual = h.hexdigest()
        if actual != expected:
            raise RuntimeError("Pinned model/tokenizer checksum mismatch")
        hashes[filename] = actual
    process = psutil.Process()
    peak_rss = [process.memory_info().rss]
    stop = threading.Event()
    def monitor():
        while not stop.wait(0.025):
            peak_rss[0] = max(peak_rss[0], process.memory_info().rss)
    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()
    load_start = time.perf_counter()
    agent = laya.load(str(model_path), device="cpu", fast=False, compile=False,
                      expected_sha256=hashes)
    load_ms = (time.perf_counter() - load_start)*1000
    questions = {
        "route": {"type": "choice", "instructions": "Select the appropriate deterministic agricultural calculator. If essential numerical inputs are missing, choose abstain. For conceptual nonnumeric agriculture questions choose qa.", "criteria": CRITERIA},
        "missing_data": {"type": "noul", "instructions": "Is this request for a numerical weather calculation missing an essential input? Conceptual explanations do not require weather measurements."},
    }
    warm_start = time.perf_counter()
    agent.predict("Air temperature=25 C; relative humidity=60 percent. Calculate vapor pressure deficit.", questions)
    warm_ms = (time.perf_counter()-warm_start)*1000
    cases = [("custom", "unspecified", args.state, None, None)] if args.state else CASES
    rows = []
    for case_id, language, state, gold, missing in cases:
        started = time.perf_counter()
        try:
            raw = agent.predict(state, questions)
            ms = (time.perf_counter()-started)*1000
            answer = raw["answers"]["route"]
            noul = raw["answers"]["missing_data"]["noul"]
            row = {"id": case_id, "language": language, "state": state, "gold_route": gold, "gold_missing_data": missing,
                   "route": answer["choice"], "correct_route": answer["choice"]==gold if gold else None,
                   "predicted_missing_data": noul>=0.5, "correct_missing_data": (noul>=0.5)==missing if missing is not None else None,
                   "latency_ms": ms, "raw": raw, "error": None}
        except Exception as exc:
            row = {"id": case_id, "language": language, "state": state, "gold_route": gold, "latency_ms": (time.perf_counter()-started)*1000, "error": type(exc).__name__, "correct_route": False}
        rows.append(row)
        print(json.dumps({"id": case_id, "route": row.get("route"), "correct_route": row.get("correct_route"), "latency_ms": round(row["latency_ms"],2), "error": row["error"]}, ensure_ascii=False), flush=True)
    stop.set()
    monitor_thread.join()
    latencies = [r["latency_ms"] for r in rows]
    summary = {"status": "measured_cpu_smoke", "model_id": "convaiinnovations/laya-multilingual", "model_revision": "e4e9ddf21a7b1903b7acffd8814ad4307bf63a67",
               "source_revision": "4aa6761be8173de4ce6d92c31b3e40b6eaf59a7c", "device": str(agent.device), "dtype": str(agent.dtype), "threads": args.threads,
               "cases": len(rows), "route_correct": sum(r.get("correct_route") is True for r in rows), "errors": sum(r["error"] is not None for r in rows),
               "missing_data_correct": sum(r.get("correct_missing_data") is True for r in rows), "load_ms": load_ms, "warmup_ms": warm_ms,
               "latency_p50_ms": statistics.median(latencies), "latency_p95_ms": percentile(latencies,0.95), "latency_mean_ms": statistics.mean(latencies),
               "peak_process_rss_bytes": peak_rss[0], "temperature": agent.temperature_raw, "calibration": "uncalibrated on this domain; probabilities are preferences, not validated risk",
               "dataset_kind": "custom demonstration" if args.state else "synthetic controlled development cases, manually authored EN/RU pairs; not an external benchmark",
               "cpu_environment": {"platform": platform.system(), "python": platform.python_version(), "logical_cpus": psutil.cpu_count(), "physical_cpus": psutil.cpu_count(logical=False), "total_ram_bytes": psutil.virtual_memory().total},
               "tokenizer_config_sha256": {"before_load": tokenizer_config_before, "after_load": hashlib.sha256((model_path / "tokenizer/tokenizer_config.json").read_bytes()).hexdigest()},
               "output_tokens_per_second": None, "output_tokens_per_second_reason": "N/A: non-autoregressive typed decision output",
               "noul_threshold": 0.5,
               "model_file_sha256": hashes, "packages": {p: importlib.metadata.version(p) for p in ["torch","transformers","huggingface_hub","safetensors","laya","psutil"]},
               "by_language": {lang: {"cases": sum(r["language"]==lang for r in rows), "route_correct": sum(r["language"]==lang and r.get("correct_route") is True for r in rows)} for lang in sorted({r["language"] for r in rows})},
               "limits": ["12 controlled development scenarios, not final holdout", "No cloud/Jev API used", "Decision accuracy is not LLM answer quality", "No parity or calibration claim", "CPU-only timings exclude model loading and warmup"]}
    (out / "raw.jsonl").write_text("\n".join(json.dumps(r,ensure_ascii=False) for r in rows)+"\n",encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    (out / "questions.json").write_text(json.dumps(questions,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__ == "__main__":
    main()
