# SPDX-License-Identifier: Apache-2.0
"""Sequential, append-only public MERA DEV60/DEV293 local screen; never TEST.

One controller owns LM Studio. Fixed context2048, no speculative MTP, reload
every10 questions and identical synthetic warmup bound accumulated cache state.
Source questions, references and provider text remain in ignored .runtime/mera.
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agro_route.home_config import resolve_api_key
from agro_route.mera_adapter_20261003 import (
    HF_REVISION, MERA_REVISION, ensure_restricted_path, forbid_gold,
    isolate_dev_references, official_scores, sha256_bytes,
)
from agro_route.mera_screen_metrics_20261003 import choice_set, set_score, summarize
import home_pc_benchmark as guards
import home_lm_api_benchmark as native
from mera_dev_20261003 import select_balanced

BASE = "http://127.0.0.1:1234"
OLD_STUDY = ROOT / "results/20261003_mera_agro_routing_3de88b82"
DEFAULT_SOURCE = ROOT / ".runtime/mera" / ("dev_rows_" + HF_REVISION + ".json")
SYSTEM = ('Ты отвечаешь на тестовые вопросы по сельскому хозяйству. Выбери все правильные варианты. '
          'Вопрос может иметь один или несколько правильных вариантов. Верни только JSON вида '
          '{"choices":["A","C"]}, без пояснений. Используй только латинские буквы вариантов, '
          'которые присутствуют в вопросе. Не добавляй поля.')
WARMUP = 'Синтетический вопрос для прогрева: сколько будет 2+2? A:4 B:5 C:6 D:7. Верни JSON choices.'
SCHEMA = {"type": "object", "properties": {"choices": {"type": "array", "items": {
    "type": "string", "enum": list("ABCDEFGH")}, "minItems": 1, "maxItems": 8}},
    "required": ["choices"], "additionalProperties": False}
CANDIDATES = [
    ("gemma-4-12b-it", "max"), ("gemma-4-26b-a4b-it", "0.70"),
    ("unsloth/qwen3.5-4b", "max"), ("qwen3.5-9b", "max"),
    ("qwen3.8-27b", "0.75"), ("qwen3.5-35b-a3b", "0.55"),
    ("phi-4-mini-instruct", "max"), ("gpt-oss-20b", "max"),
    ("granite-4.1-8b", "max"), ("minicpm5-1b", "max"),
]
PARAMETERS = {"temperature": 0, "top_p": 1, "seed": 42, "max_tokens": 512,
              "stream": True, "stream_options": {"include_usage": True},
              "logprobs": True, "top_logprobs": 1,
              "response_format": {"type": "json_schema", "json_schema": {
                  "name": "mera_choices", "strict": True, "schema": SCHEMA}}}
PROTOCOL = {"context_length": 2048, "parallel": 1, "speculative_draft_mtp": False,
            "fixed_reload_every_n": 10, "synthetic_warmup_per_load": True,
            "preload_min_ram_gib": 3, "inference_min_ram_gib": 2,
            "preload_min_gpu_free_mib": 1024, "inference_min_gpu_free_mib": 512,
            "timeout_s": 60, "load_timeout_s": 240,
            "reasoning_policy": "off where native off supported; GPT-OSS low (off unsupported); default otherwise",
            "strict_gold_policy": "presentation only; no Cyrillic transliteration; unresolved references retained and conservative all-N score reported",
            "claim_status": "DEV", "private_test_run": False,
            "primary_metric": "STRICT_SET_EM/F1 on parseable original references; conservative_all_n_em LOWER_BOUND companion"}


def now():
    return datetime.now(timezone.utc).isoformat()


def slug(name):
    return name.replace("/", "__")


def write_new(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def append(handle, obj):
    handle.write(json.dumps(obj, ensure_ascii=False) + "\n")
    handle.flush()


def validate_source(path, expected_sha):
    path = ensure_restricted_path(path, ROOT)
    data = path.read_bytes()
    if sha256_bytes(data) != expected_sha:
        raise ValueError("Benchmark source immutability check failed")
    # Deliberately no TEST path, split adapter, gold lookup or service upload.
    rows = json.loads(data)
    items, refs = isolate_dev_references(rows)
    if len(items) != 293:
        raise ValueError("Only exact public293 DEV source accepted")
    selected = select_balanced(items)
    ledger = [json.loads(line) for line in (OLD_STUDY / "dev_use_ledger.jsonl").read_text(encoding="utf-8").splitlines()]
    events = [x for x in ledger if x.get("purpose") == "fixed_60_compatibility_and_model_screen"]
    if not events or any(x.get("ids") != [i.item_id for i in selected] for x in events):
        raise ValueError("Historical DEV60 ids differ from reference-free selector")
    if any(x.get("source_sha256") != expected_sha for x in events):
        raise ValueError("Historical DEV60 source hash mismatch")
    return items, refs, selected


def payload(identifier, prompt, reasoning):
    body = {"model": identifier, **PARAMETERS, "messages": [
        {"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]}
    if reasoning is not None:
        body["reasoning_effort"] = reasoning
    if reasoning == "none":
        body["chat_template_kwargs"] = {"enable_thinking": False}
    return body


def reasoning_config(meta):
    options = ((meta.get("capabilities") or {}).get("reasoning") or {}).get("allowed_options", [])
    if "off" in options:
        return "none"
    if meta.get("architecture") == "gpt-oss":
        return "low"
    return None


def confidence_from_events(events):
    logp = []
    for event in events:
        for choice in (event.get("data") or {}).get("choices", []):
            for row in (choice.get("logprobs") or {}).get("content", []) or []:
                token = str(row.get("token", "")).strip().strip(' ,;[]{}"')
                value = row.get("logprob")
                if token in list("ABCDEFGH") and isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value <= 0:
                    logp.append(value)
    return {"option_token_confidence": math.exp(sum(logp) / len(logp)) if logp else None,
            "option_logprob_token_n": len(logp),
            "confidence_method": "geometric mean of emitted Latin-choice-token probability; not probability of correctness"}


class ResourceMonitor(guards.Monitor):
    """Same thresholds as historical guards; checks throughout streaming."""
    def __init__(self):
        super().__init__()
        self.tripped = threading.Event()
        self.trip = None
    def sample(self):
        super().sample()
        try:
            # WDDM memory.total - memory.used differs from reported memory.free.
            # Use actual measured free, never derive it by subtraction.
            headroom = guards.resource_headroom()
            if headroom["ram_available_gib"] < 2 or headroom["gpu_free_mib"] < 512:
                self.trip = {"utc": now(), **headroom}
                self.tripped.set()
        except (OSError, ValueError, IndexError, RuntimeError, subprocess.TimeoutExpired) as exc:
            self.trip = {"utc": now(), "measurement_error_type": type(exc).__name__}
            self.tripped.set()


def call_model(client, key, identifier, prompt, reasoning, monitor):
    start = time.perf_counter()
    request = payload(identifier, prompt, reasoning)
    record = {"request": request, "error": None, "response_received": False,
              "usage": {}, "timing": {}, "raw": None, "prediction_raw": ""}
    try:
        with client.stream("POST", BASE + "/v1/chat/completions", json=request,
                           headers={"Authorization": "Bearer " + key}) as response:
            response.raise_for_status()
            def guarded_lines():
                for line in response.iter_lines():
                    if monitor.tripped.is_set():
                        raise RuntimeError("RESOURCE_GUARD")
                    yield line
            raw = native.consume_sse(guarded_lines(), start)
        record.update(raw=raw, usage=raw["usage"], timing=raw["timing"],
                      prediction_raw=raw["final_content"], response_received=True,
                      **confidence_from_events(raw["events"]))
        if raw["event_error"] or not raw["stream_done"] or raw["finish_reason"] != "stop":
            record["error"] = {"type": "IncompleteCompletion", "finish_reason": raw["finish_reason"], "stream_done": raw["stream_done"]}
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, RuntimeError) as exc:
        record["error"] = {"type": type(exc).__name__,
                           "resource_guard": monitor.tripped.is_set(),
                           "http_status": getattr(getattr(exc, "response", None), "status_code", None)}
    record["latency_s"] = time.perf_counter() - start
    # Secret remains inside this process, never request body, argument, files or output.
    return native.redact(record, key)


def safe_row(item, reference, raw):
    score = set_score(reference, raw["prediction_raw"] if not raw["error"] else "", item.options)
    time_fields = raw["timing"]
    row = {"item_id": item.item_id, "split": "dev", "domain": item.domain,
           "prompt_sha256": sha256_bytes(item.prompt.encode()), **score,
           "error": raw["error"], "response_received": raw["response_received"],
           "latency_s": raw["latency_s"], "ttft_s": time_fields.get("first_nonempty_delta_s_client"),
           "first_answer_s": time_fields.get("first_answer_delta_s_client"),
           "client_tps": time_fields.get("completion_tokens_per_second_client_approx"),
           "backend_tps": time_fields.get("backend_tokens_per_second"),
           "input_tokens": raw["usage"].get("prompt_tokens"),
           "output_tokens": raw["usage"].get("completion_tokens"),
           "reasoning_observed": bool((raw.get("raw") or {}).get("reasoning_content")),
           "option_token_confidence": raw.get("option_token_confidence") if score["prediction_valid"] else None,
           "option_logprob_token_n": raw.get("option_logprob_token_n", 0)}
    # Production compatibility purely diagnostic, never fed to local selection.
    prediction, _, _ = choice_set(raw["prediction_raw"], item.options)
    official = official_scores(reference, ", ".join(prediction))
    row.update(published_compatible_em=official["exact_match"], published_compatible_f1=official["f1"])
    return row


def idle(client, key):
    state = native.native_models(client, key)
    if any(m.get("loaded_instances") for m in state):
        raise RuntimeError("Another model is loaded: exclusive controller requirement")


def inventory(args):
    safe = (ROOT / args.study_dir).resolve() if args.study_dir else ROOT / "results" / ("20261003_local_screen_" + uuid.uuid4().hex[:8])
    if not safe.is_relative_to(ROOT / "results") or safe.exists():
        raise ValueError("Fresh result directory required")
    safe.mkdir(parents=True)
    restricted = ensure_restricted_path(ROOT / ".runtime/mera" / safe.name, ROOT)
    restricted.mkdir(parents=True)
    key, source = resolve_api_key("local")
    if not key:
        raise RuntimeError("Existing LM Studio credential unavailable")
    models = guards.cli_json("ls", "--json")
    with httpx.Client(timeout=10, trust_env=False) as client:
        api_models = native.native_models(client, key)
        idle(client, key)
    mem = guards.Memory(); mem.length = ctypes.sizeof(mem)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
    gpu = guards.command(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free", "--format=csv,noheader,nounits"], 10)
    hardware = {"ram_total_gib": mem.total / 2**30, "headroom": guards.resource_headroom(),
                "gpu": gpu.stdout.strip(), "cpu": "AMD Ryzen 7 8700F 8-Core Processor (Windows registry verified)",
                "lm_studio_version": "0.4.25+1", "cli": guards.command([guards.LMS, "--version"]).stdout.strip()}
    file_root = Path.home() / ".lmstudio/models"
    duplicates = [m for m in models if m["modelKey"] in {"unsloth/qwen3.5-4b", "magistratura/qwen3.5-4b"}]
    duplicate_hashes = {}
    for m in duplicates:
        path = file_root / m["path"]
        with path.open("rb") as f:
            duplicate_hashes[m["modelKey"]] = hashlib.file_digest(f, "sha256").hexdigest()
    source_path = args.dev_rows or DEFAULT_SOURCE
    expected_sha = "be1c6da85e9c19a819656733fcb30318b79735e05068d5699a3f4142df50d150"
    items, refs, selected = validate_source(source_path, expected_sha)
    protocol = {**PROTOCOL, "created_utc": now(), "run_id": safe.name,
        "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=ROOT).strip(),
        "source_sha256": expected_sha, "source_revision": HF_REVISION, "mera_revision": MERA_REVISION,
        "dev60_ids": [i.item_id for i in selected], "dev293_ids": [i.item_id for i in items],
        "dev60_selection": "exact historical domain-stratified ID-spread selector, no answer input; all historical ledgers verified",
        "system_prompt": SYSTEM, "request_parameters": PARAMETERS,
        "candidate_configs": [{"model_key": key_, "gpu_requested": ratio} for key_, ratio in CANDIDATES],
        "max_prompt_utf8_bytes": max(len(i.prompt.encode()) for i in items),
        "reference_format_issue_ids": [i.item_id for i in items if not choice_set(refs[i.item_id], i.options)[0]],
        "uncommitted_source_hashes": {p: sha256_bytes((ROOT / p).read_bytes()) for p in (
            "scripts/mera_local_screen_20261003.py", "src/agro_route/mera_screen_metrics_20261003.py")},
        "license_status": "USE_WITH_RESTRICTIONS", "source_or_output_text_committed": False}
    write_new(safe / "protocol_frozen.json", protocol)
    write_new(safe / "inventory.json", {"utc": now(), "api_endpoint": BASE,
              "credential_source_name": source, "hardware": hardware, "cli_models": models,
              "native_models": native.redact(api_models, key), "installed_entry_count": len(models),
              "duplicate_qwen4_sha256": duplicate_hashes,
              "duplicate_qwen4_byte_identical": len(set(duplicate_hashes.values())) == 1,
              "candidate_keys": [k for k, _ in CANDIDATES],
              "exclusions": {m["modelKey"]: ("byte-identical Qwen4 duplicate" if m["modelKey"] == "magistratura/qwen3.5-4b" else
                "not part of ten normal general-text candidates: image/audio/embedding/coder/aggressive or specialized/multimodal-only")
                for m in models if m["modelKey"] not in [k for k, _ in CANDIDATES]}})
    for p in protocol["uncommitted_source_hashes"]:
        path = restricted / "source_snapshots" / Path(p).name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / p).read_bytes())
    write_new(restricted / "source_manifest.json", {"local_source_path": str(source_path), "sha256": expected_sha})
    print(json.dumps({"study_dir": str(safe.relative_to(ROOT)), "inventory_n": len(models),
                      "candidate_n": len(CANDIDATES), "max_prompt_utf8_bytes": protocol["max_prompt_utf8_bytes"],
                      "gold_format_issue_n": len(protocol["reference_format_issue_ids"]), "no_inference": True}), flush=True)


def run_one(client, key, safe, restricted, stage, model_key, ratio, items, refs, protocol):
    stem = slug(model_key)
    target = safe / stage / (stem + "_manifest.json")
    if target.exists() or (restricted / stage / (stem + "_raw.jsonl")).exists():
        raise ValueError("Append-only run already exists; no automatic rerun")
    target.parent.mkdir(parents=True, exist_ok=True)
    raw_dir = restricted / stage
    raw_dir.mkdir(parents=True, exist_ok=True)
    identifier = "mera-screen-" + safe.name[-8:] + "-" + stem
    manifest = {"run_id": safe.name + "_" + stage + "_" + stem, "stage": stage,
                "classification": "DEV", "model_key": model_key, "gpu_requested": ratio,
                "actual_gpu_layers": None, "source_sha256": protocol["source_sha256"],
                "protocol_sha256": sha256_bytes((safe / "protocol_frozen.json").read_bytes()),
                "started_utc": now(), "loads": [], "status": "PARTIAL", "private_test_run": False,
                "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=ROOT).strip(),
                "uncommitted_source_hashes": protocol["uncommitted_source_hashes"],
                "timeout_count": 0, "model_load_failure": False, "safe_rows": stem + "_metrics.jsonl"}
    rows, own_load_attempted = [], False
    monitor = ResourceMonitor()
    try:
        idle(client, key)
        with (raw_dir / (stem + "_raw.jsonl")).open("x", encoding="utf-8") as raw_handle, \
             (target.parent / (stem + "_metrics.jsonl")).open("x", encoding="utf-8") as metrics_handle, \
             (raw_dir / (stem + "_started.jsonl")).open("x", encoding="utf-8") as started_handle, monitor:
            for offset in range(0, len(items), PROTOCOL["fixed_reload_every_n"]):
                if own_load_attempted:
                    cleanup = guards.command([guards.LMS, "unload", identifier])
                    if cleanup.returncode:
                        raise RuntimeError("Own instance unload failed")
                    own_load_attempted = False
                    idle(client, key)
                    time.sleep(2)
                if monitor.tripped.is_set():
                    manifest.update(status="PARTIAL_RESOURCE_GUARD", stop_reason=monitor.trip)
                    break
                meta = {"chunk_offset": offset, "headroom_before": guards.resource_headroom(), "started_utc": now()}
                manifest["loads"].append(meta)
                args = [guards.LMS, "load", model_key, "--context-length", "2048", "--parallel", "1", "--gpu", ratio,
                        "--no-speculative-draft-mtp", "--identifier", identifier, "--yes"]
                estimate = guards.command([*args, "--estimate-only"])
                # Load output is restricted because it can contain local command hints.
                (raw_dir / (stem + f"_estimate_{offset:03d}.txt")).write_text(estimate.stdout + estimate.stderr, encoding="utf-8")
                if estimate.returncode:
                    manifest.update(status="FAILED_LOAD", model_load_failure=True, stop_reason="resource_estimate_failed")
                    break
                own_load_attempted = True
                load_start = time.perf_counter()
                load = guards.guarded_load(args, raw_dir / (stem + f"_load_{offset:03d}.txt"), meta)
                meta["load_latency_s"] = time.perf_counter() - load_start
                if load.returncode:
                    manifest.update(status="FAILED_LOAD", model_load_failure=True, stop_reason="guarded_load_nonzero")
                    break
                matches = [(m, i) for m in native.native_models(client, key) for i in m.get("loaded_instances", []) if i["id"] == identifier]
                if len(matches) != 1:
                    raise RuntimeError("Own exact instance not found")
                model_meta, instance = matches[0]
                config = instance.get("config") or {}
                if config.get("context_length") != 2048 or config.get("parallel") != 1 or config.get("speculative_draft_mtp") is not False:
                    raise RuntimeError("Common load settings not confirmed")
                meta.update(load_config=config, headroom_after=guards.resource_headroom())
                manifest.update(quantization=model_meta.get("quantization"), model_size_bytes=model_meta.get("size_bytes"),
                                architecture=model_meta.get("architecture"), native_model_metadata=model_meta,
                                load_config=config, reasoning_effort_requested=reasoning_config(model_meta))
                warm = call_model(client, key, identifier, WARMUP, reasoning_config(model_meta), monitor)
                append(raw_handle, {"kind": "synthetic_warmup", "chunk_offset": offset, **warm})
                meta["warmup_latency_s"] = warm["latency_s"]
                if warm["error"] or not choice_set(warm["prediction_raw"], tuple("ABCD"))[0]:
                    manifest.update(status="FORMAT_INCOMPATIBLE", stop_reason=warm["error"] or "synthetic_warmup_invalid")
                    break
                for item in items[offset: offset + PROTOCOL["fixed_reload_every_n"]]:
                    if item.split != "dev":
                        raise ValueError("Private TEST is forbidden by this runner")
                    forbid_gold(item.public())
                    headroom = guards.resource_headroom()
                    if monitor.tripped.is_set() or headroom["ram_available_gib"] < 2 or headroom["gpu_free_mib"] < 512:
                        manifest.update(status="PARTIAL_RESOURCE_GUARD", stop_reason=monitor.trip or headroom)
                        break
                    append(started_handle, {"item_id": item.item_id, "started_utc": now(), "prompt_sha256": sha256_bytes(item.prompt.encode())})
                    raw = call_model(client, key, identifier, item.prompt, reasoning_config(model_meta), monitor)
                    append(raw_handle, {"kind": "benchmark", "item_id": item.item_id, "split": "dev", **raw})
                    row = safe_row(item, refs[item.item_id], raw)
                    rows.append(row)
                    append(metrics_handle, row)
                    print(json.dumps({"stage": stage, "model": model_key, "progress": f"{len(rows)}/{len(items)}",
                                      "latency_s": round(raw["latency_s"], 3), "invalid": not row["prediction_valid"], "error": row["error"]}), flush=True)
                    if raw["error"]:
                        manifest.update(status="PARTIAL_RESOURCE_GUARD" if monitor.tripped.is_set() else "PARTIAL",
                                        stop_reason=raw["error"])
                        break
                    if len(rows) >= 6 and sum(not r["prediction_valid"] for r in rows[-6:]) >= 3:
                        manifest.update(status="FORMAT_INCOMPATIBLE", stop_reason="three invalid outputs in last six responses")
                        break
                if manifest.get("stop_reason"):
                    break
            if len(rows) == len(items):
                manifest["status"] = "COMPLETE"
    except (RuntimeError, ValueError, OSError, httpx.HTTPError, subprocess.TimeoutExpired) as exc:
        manifest.update(status="PARTIAL_RESOURCE_GUARD" if monitor.tripped.is_set() or "guard" in str(exc).lower() else "FAILED_LOAD" if not rows else "PARTIAL",
                        stop_reason={"type": type(exc).__name__, "resource_guard": monitor.trip}, model_load_failure=not rows)
    finally:
        if own_load_attempted:
            try:
                cleanup = guards.command([guards.LMS, "unload", identifier])
                manifest["cleanup_success"] = cleanup.returncode == 0
                idle(client, key)
            except (RuntimeError, OSError, ValueError, httpx.HTTPError, subprocess.TimeoutExpired):
                manifest["cleanup_success"] = False
        manifest.update(finished_utc=now(), summary=summarize(rows, [i.item_id for i in items]),
                        resource_metrics=monitor.summary(),
                        actual_calls=len(rows), loads_n=len(manifest["loads"]),
                        total_load_latency_s=sum(x.get("load_latency_s", 0) for x in manifest["loads"]),
                        total_warmup_latency_s=sum(x.get("warmup_latency_s", 0) for x in manifest["loads"]))
        manifest["raw_sha256"] = sha256_bytes((raw_dir / (stem + "_raw.jsonl")).read_bytes()) if (raw_dir / (stem + "_raw.jsonl")).exists() else None
        manifest["safe_rows_sha256"] = sha256_bytes((target.parent / (stem + "_metrics.jsonl")).read_bytes()) if (target.parent / (stem + "_metrics.jsonl")).exists() else None
        write_new(target, native.redact(manifest, key))
    print(json.dumps({"stage": stage, "model": model_key, "status": manifest["status"], "summary": manifest["summary"], "memory": manifest["resource_metrics"]}), flush=True)
    if manifest.get("cleanup_success") is False:
        raise RuntimeError("Cleanup not confirmed; subsequent models blocked")
    time.sleep(2)
    return manifest


def run(args):
    if args.stage == "inventory":
        return inventory(args)
    safe = (ROOT / args.study_dir).resolve()
    if not safe.is_relative_to(ROOT / "results"):
        raise ValueError("Result directory must stay in results")
    restricted = ensure_restricted_path(ROOT / ".runtime/mera" / safe.name, ROOT)
    protocol = json.loads((safe / "protocol_frozen.json").read_text(encoding="utf-8"))
    amendment = safe / "protocol_amendment_01.json"
    if amendment.exists():
        amendment_data = json.loads(amendment.read_text(encoding="utf-8"))
        if amendment_data["original_protocol_sha256"] != sha256_bytes((safe / "protocol_frozen.json").read_bytes()):
            raise ValueError("Protocol amendment parent mismatch")
        protocol.update(amendment_data["replacement_fields"])
    for name, expected in protocol["uncommitted_source_hashes"].items():
        if sha256_bytes((ROOT / name).read_bytes()) != expected:
            raise ValueError("Frozen runner source changed: no inference permitted")
    items, refs, dev60 = validate_source(args.dev_rows or DEFAULT_SOURCE, protocol["source_sha256"])
    candidates = CANDIDATES
    if args.models:
        chosen = set(args.models)
        candidates = [(k, r) for k, r in candidates if k in chosen]
        if chosen != {k for k, _ in candidates}:
            raise ValueError("Candidate absent from frozen protocol")
    if args.stage == "dev60":
        items = dev60
    elif args.stage == "dev293":
        shortlist_path = safe / "shortlist_frozen.json"
        shortlist = json.loads(shortlist_path.read_text(encoding="utf-8"))
        selected_keys = shortlist["model_keys"]
        if not selected_keys or any(key not in {k for k, _ in CANDIDATES} for key in selected_keys):
            raise ValueError("Invalid pre-frozen shortlist")
        candidates = [(k, r) for k, r in candidates if k in selected_keys]
    else:
        raise ValueError("Only public DEV stages accepted")
    key, _ = resolve_api_key("local")
    if not key:
        raise RuntimeError("Existing LM Studio credential unavailable")
    with httpx.Client(timeout=PROTOCOL["timeout_s"], trust_env=False) as client:
        for model_key, ratio in candidates:
            run_one(client, key, safe, restricted, args.stage, model_key, ratio, items, refs, protocol)
    if sha256_bytes((args.dev_rows or DEFAULT_SOURCE).read_bytes()) != protocol["source_sha256"]:
        raise RuntimeError("Source changed during run")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["inventory", "dev60", "dev293"], required=True)
    parser.add_argument("--study-dir", type=Path)
    parser.add_argument("--dev-rows", type=Path)
    parser.add_argument("--models", nargs="*")
    run(parser.parse_args())
