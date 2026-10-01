import collections
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import time
import uuid
from .evaluation import score
from .models import configured_models, public_request, SYSTEM_PROMPT
from .routing import decide

ROOT = Path(__file__).resolve().parents[2]
METHODS = ["local", "cloud", "rule", "cascade", "tool_cloud", "offline"]

def load_samples(split):
    all_samples = [json.loads(line) for line in (ROOT / "data/benchmark.jsonl").read_text(encoding="utf-8").splitlines()]
    return [s for s in all_samples if s["split"] == split]

def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def run(split="dev", limit=None):
    samples = load_samples(split)
    if limit:
        # Round robin categories for pilot rather than the first N QA items.
        by_cat = collections.defaultdict(list)
        for s in samples:
            by_cat[s["category"]].append(s)
        samples = [row for group in zip(*[v for v in by_cat.values()]) for row in group][:limit]
    local, cloud = configured_models()
    if not cloud.key:
        raise RuntimeError("CLOUD_API_KEY required for paired local/cloud run")
    if split == "test" and not (ROOT / "data/protocol_frozen.json").exists():
        raise RuntimeError("Freeze pilot-informed protocol before final test")
    if split == 'test':
        frozen = json.loads((ROOT / 'data/protocol_frozen.json').read_text())
        if frozen['local_model'] != local.model or frozen['cloud_model'] != cloud.model or frozen['dataset_sha256'] != hashlib.sha256((ROOT/'data/benchmark.jsonl').read_bytes()).hexdigest():
            raise RuntimeError('Model/dataset differs from frozen development protocol')
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    directory = ROOT / "results" / run_id
    directory.mkdir(parents=True, exist_ok=False)
    # At most 6000 input tokens (UTF-8 bytes conservative upper bound) + 512 output per request.
    estimated = sum((len(SYSTEM_PROMPT.encode()) + len(json.dumps(public_request(s), ensure_ascii=False).encode())) * cloud.input_price / 1e6 + 512 * cloud.output_price / 1e6 for s in samples)
    if estimated > 1:
        raise RuntimeError(f"Budget guard: upper estimate ${estimated:.3f} exceeds $1 per paired run")
    print(f"RUN {run_id}; {len(samples)} pairs; conservative cloud upper estimate ${estimated:.4f}", flush=True)
    code_hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / "src/agro_route").glob("*.py")}
    manifest = {"run_id": run_id, "split": split, "n": len(samples), "state": "running", "started_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(), "os": platform.platform(), "cpu_logical": os.cpu_count(), "processor_identifier": os.getenv("PROCESSOR_IDENTIFIER"), "hardware": {"ram_gib_observed": 7.73, "gpu": "UNKNOWN", "inference": "CPU, 4 threads, llama.cpp b11292, context 4096, parallel slots 1"}, "local_model": local.model, "cloud_model": cloud.model, "temperature": 0, "local_seed": 42, "max_tokens": 512, "reasoning": "disabled local / instant cloud", "prices_usd_per_m": {"input": cloud.input_price, "output": cloud.output_price, "date": "2026-09-30", "source": "https://docs.inceptionlabs.ai/get-started/models", "cached_discount": "not_applied"}, "estimated_upper_cloud_usd": estimated, "dataset_sha256": hashlib.sha256((ROOT / "data/benchmark.jsonl").read_bytes()).hexdigest(), "code_sha256": code_hashes, "prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(), "cost_type": "token-based conservative estimate; invoice not obtained", "latency": "HTTP end-to-end measured pairs; hybrid reconstructed by trace replay, not live deployment", "selection": "full split" if not limit else "round_robin_pilot"}
    write_json(directory / "manifest.json", manifest)
    asset = ROOT / f"data/model_assets_{'2B' if '2B-' in local.model else '0.8B'}.json"
    if asset.exists():
        manifest["local_assets"] = json.loads(asset.read_text(encoding="utf-8"))
    protocol_path = ROOT / "data/protocol_frozen.json"
    if protocol_path.exists():
        manifest["protocol_sha256"] = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    write_json(directory / "manifest.json", manifest)
    (directory / "system_prompt.txt").write_text(SYSTEM_PROMPT, encoding="utf-8")
    pairs = []
    with (directory / "pairs.jsonl").open("x", encoding="utf-8") as f:
        for i, sample in enumerate(samples):
            # Alternate pair order, no parallel CPU requests, no paid retries.
            results = {}
            for name, model in (("local", local), ("cloud", cloud)) if i % 2 == 0 else (("cloud", cloud), ("local", local)):
                results[name] = model.call(public_request(sample))
            row = {"sample": sample, **results}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            pairs.append(row)
            print(f"{i+1}/{len(samples)} {sample['id']} local={score(sample,results['local']['output'])['correct']} cloud={score(sample,results['cloud']['output'])['correct']} errors={bool(results['local']['error'])}/{bool(results['cloud']['error'])}", flush=True)
    manifest["state"] = "completed"
    manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["api_cost_estimate_usd"] = sum(r["cloud"]["cost_usd"] or 0 for r in pairs)
    manifest["unknown_cost_calls"] = sum(r["cloud"]["cost_usd"] is None for r in pairs)
    write_json(directory / "manifest.json", manifest)
    replay(directory)
    return directory

def replay(directory, threshold=None):
    directory = Path(directory)
    if (directory / "normalized.jsonl").exists():
        raise RuntimeError("Refuse overwriting normalized results; use a new analysis directory")
    if threshold is None:
        frozen = ROOT / "data/protocol_frozen.json"
        threshold = json.loads(frozen.read_text())["rule_threshold_chars"] if frozen.exists() else 900
    rows = []
    for pair in [json.loads(l) for l in (directory / "pairs.jsonl").read_text(encoding="utf-8").splitlines()]:
        sample = pair["sample"]
        for method in METHODS:
            result = decide(public_request(sample), method, lambda r: pair["local"], lambda r: pair["cloud"], method != "offline", threshold)
            if result["trace"]:
                result["latency_ms"] += sum(t["latency_ms"] for t in result["trace"])
                result["latency_kind"] = "reconstructed_trace_replay"
            result.pop("trace", None)
            rows.append({"id": sample["id"], "group": sample["group"], "category": sample["category"], "language": sample["language"], "method": method, **result, **score(sample, result["output"])})
    with (directory / "normalized.jsonl").open("x", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return rows

def freeze(pilot):
    pairs = [json.loads(l) for l in (Path(pilot) / "pairs.jsonl").read_text(encoding="utf-8").splitlines()]
    if json.loads((Path(pilot) / "manifest.json").read_text())["split"] != "dev":
        raise ValueError("Only development data may set protocol")
    # A fixed grid predeclared in experiment design. Select best quality, then lower cost.
    candidates = []
    for threshold in (400, 900, 1600):
        pred = [decide(public_request(p["sample"]), "rule", lambda r:p["local"], lambda r:p["cloud"], True, threshold) for p in pairs]
        quality = sum(score(p["sample"],r["output"])["correct"] for p,r in zip(pairs,pred))/len(pred)
        cost = sum(r["cost_usd"] or 0 for r in pred)
        candidates.append({"threshold":threshold,"pilot_quality":quality,"pilot_cost_usd":cost})
    best = sorted(candidates, key=lambda x:(-x["pilot_quality"],x["pilot_cost_usd"],x["threshold"]))[0]
    cloud_quality = sum(score(p['sample'], p['cloud']['output'])['correct'] for p in pairs)/len(pairs)
    local_quality = sum(score(p['sample'], p['local']['output'])['correct'] for p in pairs)/len(pairs)
    cascade = [decide(public_request(p['sample']), 'cascade', lambda r:p['local'], lambda r:p['cloud']) for p in pairs]
    observed_reduction = 1-sum(r['cloud_calls'] for r in cascade)/len(pairs)
    # Exploratory utility margins: a pilot-derived planning rule, not clinical/agronomic validation.
    quality_margin = min(.05, max(1/len(pairs), abs(cloud_quality-local_quality)/2))
    reduction_target = observed_reduction/2
    protocol = {"frozen_utc": datetime.now(timezone.utc).isoformat(), "pilot_run": Path(pilot).name, "rule_threshold_chars": best["threshold"], "grid": candidates, "primary_method": "cascade", "comparator": "cloud", "quality_margin_absolute": quality_margin, "min_cloud_call_reduction": reduction_target, "critical_error_margin_absolute": 0., "pilot_margins": {"cloud_quality":cloud_quality,"local_quality":local_quality,"observed_cascade_cloud_reduction":observed_reduction,"quality_rule":"min(0.05,max(1/n,abs(cloud-local)/2))", "reduction_rule":"half observed pilot reduction", "critical_rule":"no increase in wrong numerical ANSWER/missing-input ANSWER"}, "criterion_status": "exploratory pilot-derived utility target; NOT an agronomic standard or confirmatory preregistration", "decision": "support H1 on controlled sample only if lower paired quality CI >= -margin, call reduction >= target and upper critical-error difference CI <=0; H2 additionally requires benefit over tool_cloud", "local_model":json.loads((Path(pilot)/'manifest.json').read_text())['local_model'], "cloud_model":json.loads((Path(pilot)/'manifest.json').read_text())['cloud_model'], "dataset_sha256":hashlib.sha256((ROOT/'data/benchmark.jsonl').read_bytes()).hexdigest(), "bootstrap_cluster": "sample.group", "bootstrap_seed":42,"bootstrap_repeats":2000,"final_split":"test", "small_sample":"failure to prove noninferiority is not proof of inferiority"}
    path = ROOT / "data/protocol_frozen.json"
    with path.open("x", encoding="utf-8") as f:
        json.dump(protocol, f, ensure_ascii=False, indent=2)
    return protocol
