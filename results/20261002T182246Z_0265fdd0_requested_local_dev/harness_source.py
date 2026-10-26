"""Versioned exploratory Q8 development baseline; old protocols stay immutable.

Imports the historical controlled DEV API payload/scorer and memory guards.
Only this controller may load/unload LM Studio. Downloads/builds must finish
before --run. The 150-item historical holdout is never read by this script.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

import httpx
import home_lm_api_benchmark as api
import home_pc_benchmark as old
from agro_route.evaluation import score
from agro_route.home_config import resolve_api_key
from agro_route.models import SYSTEM_PROMPT

ROOT = Path(__file__).resolve().parents[1]
BASELINES = {
    "qwen": {"repo": "unsloth/Qwen3.5-4B-GGUF", "revision": "e87f176479d0855a907a41277aca2f8ee7a09523",
             "base_model": "Qwen/Qwen3.5-4B", "base_revision": "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a",
             "filename": "Qwen3.5-4B-Q8_0.gguf", "size": 4482403488,
             "sha256": "10cc391b403021dd11c614679d2fd92f611c3681d29e29651b717316965d61e1",
             "license": "apache-2.0", "model_key": "qwen3.5-4b", "gpu": "max"},
    "phi": {"repo": "unsloth/Phi-4-mini-instruct-GGUF", "revision": "78eb92a46fc37e6b524df991ed9aca9bc6aa7b80",
            "base_model": "microsoft/Phi-4-mini-instruct", "base_revision": "cfbefacb99257ffa30c83adab238a50856ac3083",
            "filename": "Phi-4-mini-instruct.Q8_0.gguf", "size": 4084611040,
            "sha256": "26188c6050d525376a88b04514c236c5e28a36730f1e936f2a00314212b7ba42",
            "license": "mit", "model_key": "phi-4-mini-instruct", "gpu": "max"},
}
BITNET = {"repo": "microsoft/bitnet-b1.58-2B-4T-gguf",
          "revision": "a1f2f1c765812aa8af3f6eda4a313707064bba15",
          "filename": "ggml-model-i2_s.gguf", "size": 1187801280,
          "sha256": "4221b252fdd5fd25e15847adfeb5ee88886506ba50b8a34548374492884c2162",
          "license": "mit", "quantization": "I2_S native ternary W1.58A8"}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    """Atomic reporting checkpoints; never rewrite raw requests."""
    path = Path(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    for attempt in range(20):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(.25)


def process_snapshot():
    """Backend process working sets, separate from whole-system RAM.

    Runtime PID to model association is UNKNOWN unless subsequently confirmed.
    Only allowlisted local runtime process names are returned; no command lines.
    """
    command = ("Get-Process -ErrorAction SilentlyContinue | Where-Object { "
               "$_.ProcessName -match '^(llama-server|llama-worker|lms|LM Studio|lmstudio.*)$' } | "
               "Select-Object Id,ProcessName,WorkingSet64,PeakWorkingSet64 | ConvertTo-Json -Compress")
    result = old.command(["powershell.exe", "-NoProfile", "-Command", command], timeout=20)
    if result.returncode:
        return {"status": "UNKNOWN", "error_type": "ProcessSnapshotFailed"}
    rows = json.loads(result.stdout or "[]")
    return {"status": "MEASURED", "rows": rows if isinstance(rows, list) else [rows],
            "model_process_association": "UNKNOWN", "scope": "OS process working sets; no command lines"}


def fingerprint(spec, inventory, model_root):
    matches = [m for m in inventory if m.get("path", "").endswith("/" + spec["filename"])]
    if len(matches) != 1:
        raise RuntimeError("Exact requested GGUF missing or ambiguous in LM Studio inventory")
    item = matches[0]
    if (item.get("quantization") or {}).get("name") != "Q8_0":
        raise RuntimeError("Requested ordinary faithful Q8_0 not confirmed")
    path = Path(model_root) / item["path"]
    actual_size, actual_hash = path.stat().st_size, digest(path)
    if actual_size != spec["size"] or actual_hash != spec["sha256"]:
        raise RuntimeError("GGUF checksum or size mismatch; no inference permitted")
    return {**spec, "local_path": str(path), "measured_size": actual_size,
            "measured_sha256": actual_hash, "inventory": item,
            "measured_utc": old.now(), "status": "CHECKSUM_VERIFIED"}


def eligible_extension(rows):
    # Predeclared compact-baseline screen, not a claim of matching larger models.
    return (len(rows) == 12 and sum(r["score"]["correct"] for r in rows) >= 6
            and sum(bool(r["local"]["error"]) for r in rows) <= 2)


def bitnet_request(client, identifier, sample):
    """Same public DEV payload/schema via dedicated native bitnet.cpp server."""
    started = time.perf_counter()
    result = {"output": None, "error": None, "raw": None, "usage": {}, "timing": {}, "cost_usd": 0.0}
    try:
        with client.stream("POST", "http://127.0.0.1:1235/v1/chat/completions", json=api.payload(identifier, sample)) as response:
            response.raise_for_status()
            raw = api.consume_sse(response.iter_lines(), started)
        result.update(raw=raw, usage=raw["usage"], timing=raw["timing"])
        # llama.cpp may expose timings in the same response rather than stats.
        timings = [e["data"].get("timings") for e in raw["events"] if isinstance(e["data"].get("timings"), dict)]
        if timings:
            result["timing"]["native_llama_timings"] = timings[-1]
            result["timing"]["backend_tokens_per_second"] = timings[-1].get("predicted_per_second")
        if raw["event_error"] or not raw["stream_done"] or raw["finish_reason"] != "stop":
            result["error"] = {"type": "IncompleteCompletion", "finish_reason": raw["finish_reason"]}
        else:
            answer = api.parse_output(raw["final_content"])
            if set(answer) != set(api.SCHEMA["required"]):
                raise ValueError("Structured schema mismatch")
            result["output"] = answer
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, RuntimeError) as exc:
        result["error"] = {"type": type(exc).__name__, "http_status": getattr(getattr(exc, "response", None), "status_code", None)}
    result["latency_ms"] = (time.perf_counter() - started) * 1000
    return result


def run_bitnet(server_path, model_path, n=36):
    if n not in (12, 36):
        raise ValueError("Only DEV12/DEV36 allowed")
    if not Path(server_path).is_file() or not Path(model_path).is_file():
        raise RuntimeError("Build native server and download exact I2_S weights first")
    if Path(model_path).stat().st_size != BITNET["size"] or digest(model_path) != BITNET["sha256"]:
        raise RuntimeError("Native BitNet checksum mismatch")
    # Require no LM Studio model and no occupied own server port.
    key, _ = resolve_api_key("local", env_path=ROOT / ".env")
    with httpx.Client(timeout=10, trust_env=False) as local_client:
        if any(m.get("loaded_instances") for m in api.native_models(local_client, key)):
            raise RuntimeError("LM Studio instance present; CPU baseline waits for a quiet window")
        try:
            local_client.get("http://127.0.0.1:1235/health")
        except httpx.ConnectError:
            pass
        else:
            raise RuntimeError("Native baseline port already occupied; do not stop another server")
    headroom = old.resource_headroom()
    if headroom["ram_available_gib"] < 3:
        raise RuntimeError("Insufficient CPU baseline RAM")
    directory = ROOT / "results" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8] + "_bitnet_native_dev")
    directory.mkdir(exist_ok=False)
    samples = old.choose_samples(n)
    identifier = "bitnet-native-i2s"
    args = [str(Path(server_path).resolve()), "-m", str(Path(model_path).resolve()), "--alias", identifier,
            "--host", "127.0.0.1", "--port", "1235", "-c", "4096", "-t", "4", "-tb", "4", "-np", "1", "-ngl", "0"]
    manifest = {"started_utc": old.now(), "run_id": directory.name, "state": "running", "phase": "exploratory_development_only",
                "model": BITNET, "server_sha256": digest(server_path), "harness_sha256": digest(__file__),
                "sample_ids": [s["id"] for s in samples], "n_planned": n, "cloud_calls": 0,
                "runtime": "official microsoft/BitNet bitnet.cpp; isolated LLVM-MinGW Windows build",
                "runtime_commit": "0b341e582afbf9e1011f24744b554c96a3477eb5",
                "llama_submodule_commit": "390c307752ab78fd8189f359d6954c9ba1be74af",
                "cpu_threads": 4, "threads_batch": 4, "context": 4096, "parallel": 1,
                "gpu_offload_requested_layers": 0, "actual_offload": "Confirm from own runtime startup log; CPU native baseline",
                "backend_server_args": args, "hidden_warmups": 0, "request_retries": 0,
                "extension_rule": "DEV12 correct>=6 and completion errors<=2, then remaining24 without repeats",
                "request_parameters": {k: v for k, v in api.payload(identifier, samples[0]).items() if k != "messages"},
                "data_sha256": digest(ROOT / "data/benchmark.jsonl"), "prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
                "latency_scope": "Measured streaming HTTP wall time; model loads and resource snapshots excluded",
                "limitations": ["Native CPU runtime differs from LM Studio GPU runtime", "Exploratory DEV, not independent final test", "No concurrent downloads/builds/model inference permitted"]}
    write(directory / "manifest.json", manifest)
    write(directory / "samples_dev.json", samples)
    rows, monitor, process = [], old.Monitor(), None
    env = os.environ.copy()
    env["PATH"] = str(Path(server_path).resolve().parent) + os.pathsep + env.get("PATH", "")
    # Only this new server's PID is terminated in cleanup.
    try:
        with (directory / "native_server_log.txt").open("x", encoding="utf-8") as log, monitor:
            loaded_started = time.perf_counter()
            process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, env=env)
            manifest["own_server_pid"] = process.pid
            with httpx.Client(timeout=120, trust_env=False) as client:
                while True:
                    if process.poll() is not None:
                        raise RuntimeError("Native server stopped before health readiness")
                    if time.perf_counter() - loaded_started > 180:
                        raise RuntimeError("Native server readiness timeout")
                    try:
                        ready = client.get("http://127.0.0.1:1235/health", timeout=2)
                        if ready.status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(.5)
                manifest["cold_load_wall_s"] = time.perf_counter() - loaded_started
                with (directory / "bitnet_raw.jsonl").open("x", encoding="utf-8") as raw_handle:
                    for i, sample in enumerate(samples):
                        if i == 12 and not eligible_extension(rows):
                            manifest["state"] = "PARTIAL_SCREEN_REJECTED"
                            break
                        headroom = old.resource_headroom()
                        if headroom["ram_available_gib"] < 2:
                            raise RuntimeError("Native CPU RAM guard")
                        result = bitnet_request(client, identifier, sample)
                        item = {"run_id": directory.name, "sample": sample, "sample_index": i, "utc": old.now(),
                                "model": identifier, "local": result, "score": score(sample, result.get("output")),
                                "headroom_before_request": headroom}
                        rows.append(item)
                        raw_handle.write(json.dumps(item, ensure_ascii=False) + "\n")
                        raw_handle.flush()
                        print(json.dumps({"model": "bitnet", "completed": len(rows), "planned": n}), flush=True)
                    else:
                        manifest["state"] = "DONE"
                result = old.command(["powershell.exe", "-NoProfile", "-Command", f"Get-Process -Id {process.pid} | Select-Object Id,ProcessName,WorkingSet64,PeakWorkingSet64 | ConvertTo-Json -Compress"], 20)
                manifest["own_process_memory"] = json.loads(result.stdout) if result.returncode == 0 else {"status": "UNKNOWN"}
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired, httpx.HTTPError) as exc:
        manifest.update(state="BLOCKED" if not rows else "PARTIAL", error_type=type(exc).__name__)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        manifest["own_server_cleanup_confirmed"] = process is None or process.poll() is not None
        manifest["resources"] = monitor.summary()
        manifest["summary"] = api.summarize(rows)
        manifest["finished_utc"] = old.now()
        write(directory / "resources.json", monitor.rows)
        write(directory / "manifest.json", manifest)
    print(json.dumps({"run_directory": str(directory), "state": manifest["state"], "summary": manifest["summary"]}), flush=True)
    return directory


def run(names, model_root, development_n=36):
    if development_n not in (12, 36) or not names or set(names) - set(BASELINES):
        raise ValueError("Only the requested Qwen/Phi names and DEV12/DEV36 are allowed")
    key, source = resolve_api_key("local", env_path=ROOT / ".env")
    if not key:
        raise RuntimeError("LOCAL_API_KEY missing in legitimate project environment")
    client = httpx.Client(timeout=120, trust_env=False)
    catalog = api.native_models(client, key)
    if any(m.get("loaded_instances") for m in catalog):
        raise RuntimeError("Another model is loaded; this controller will not unload it")
    inventory = old.cli_json("ls", "--json")
    fingerprints = {name: fingerprint(BASELINES[name], inventory, model_root) for name in names}
    samples = old.choose_samples(development_n)
    directory = ROOT / "results" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8] + "_requested_local_dev")
    directory.mkdir(exist_ok=False)
    manifest = {"run_id": directory.name, "started_utc": old.now(), "state": "running",
                "phase": "exploratory_development_only", "n_planned_per_model": development_n,
                "sample_ids": [s["id"] for s in samples], "dataset_split": "old_dev",
                "data_sha256": digest(ROOT / "data/benchmark.jsonl"),
                "prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
                "harness_sha256": digest(__file__), "historical_api_sha256": digest(api.__file__),
                "core_source_sha256": {n: digest(ROOT / "src/agro_route" / n) for n in ("models.py", "routing.py", "evaluation.py", "tools.py")},
                "credential_source": source, "fingerprints": fingerprints, "models": {},
                "parameters": api.payload("unused", samples[0]), "context_length": 4096, "parallel": 1,
                "warmups": 0, "request_retries": 0, "response_cache": False,
                "extension_rule": "After fixed DEV12, append remaining 24 once only if correct>=6/12, completion errors<=2/12, and guards remain safe. Earlier requests are never repeated.",
                "latency_scope": "Measured streaming HTTP wall time. Model load and resource/process polling are outside request latency.",
                "execution_context": "Sequential GPU inference; no downloads, builds, CPU-heavy local inference or other GPU inference permitted during measurement.",
                "limitations": ["Development screening, not confirmatory holdout", "Original DEV agricultural extractive QA English-only", "Client TPS approximate", "Sampled whole-device VRAM and whole-system RAM", "Process RSS association UNKNOWN unless separately proven"]}
    manifest["parameters"]["messages"] = "SYSTEM_PROMPT + public_request(sample); no gold/category/expected route"
    write(directory / "manifest.json", api.redact(manifest, key))
    write(directory / "samples_dev.json", samples)
    (directory / "system_prompt.txt").write_text(SYSTEM_PROMPT, encoding="utf-8")
    (directory / "harness_source.py").write_bytes(Path(__file__).read_bytes())
    print(json.dumps({"run_directory": str(directory)}), flush=True)
    try:
        for name in names:
            info = fingerprints[name]
            model_key = info["inventory"]["modelKey"]
            identifier = "requested-local-" + uuid.uuid4().hex[:8] + "-" + name
            meta = {"status": "NOT_RUN", "own_instance_id": identifier,
                    "requested_offload": info["gpu"], "actual_offloaded_layers": "UNKNOWN", "load_success": False}
            manifest["models"][name] = meta
            rows, monitor = [], old.Monitor()
            try:
                with monitor:
                    meta["processes_before_load"] = process_snapshot()
                    args = [old.LMS, "load", model_key, "--context-length", "4096", "--parallel", "1", "--gpu", info["gpu"], "--identifier", identifier, "--yes"]
                    estimate = old.command([*args, "--estimate-only"])
                    meta["estimate_returncode"] = estimate.returncode
                    (directory / (name + "_estimate.txt")).write_text(old.ANSI.sub("", estimate.stdout + estimate.stderr), encoding="utf-8")
                    if estimate.returncode:
                        raise RuntimeError("Resource estimate failed")
                    started = time.perf_counter()
                    loaded = old.guarded_load(args, directory / (name + "_load.txt"), meta)
                    meta["cold_load_wall_s"] = time.perf_counter() - started
                    meta["load_success"] = loaded.returncode == 0
                    if loaded.returncode:
                        raise RuntimeError("Guarded load failed")
                    current = api.native_models(client, key)
                    matches = [(m, instance) for m in current for instance in m.get("loaded_instances", []) if instance.get("id") == identifier]
                    if len(matches) != 1:
                        raise RuntimeError("Own instance not confirmed")
                    native, instance = matches[0]
                    meta.update(native_model_metadata=native, actual_load_config=instance.get("config"))
                    config = instance.get("config") or {}
                    if config.get("context_length") != 4096 or config.get("parallel") != 1:
                        raise RuntimeError("Controlled load configuration not confirmed")
                    allowed = ((native.get("capabilities") or {}).get("reasoning") or {}).get("allowed_options", [])
                    effort = "none" if "off" in allowed else None
                    meta["reasoning_effort_requested"] = effort
                    meta["processes_after_load"] = process_snapshot()
                    with (directory / (name + "_raw.jsonl")).open("x", encoding="utf-8") as handle:
                        for i, sample in enumerate(samples):
                            if i == 12 and not eligible_extension(rows):
                                meta["status"] = "PARTIAL_SCREEN_REJECTED"
                                break
                            headroom = old.resource_headroom()
                            if headroom["ram_available_gib"] < 2 or headroom["gpu_free_mib"] < 512:
                                meta["resource_guard_stop"] = headroom
                                raise RuntimeError("Resource guard before inference")
                            result = api.api_call(client, key, identifier, sample, effort)
                            item = {"run_id": directory.name, "sample": sample, "model": model_key,
                                    "sample_index": i, "utc": old.now(), "local": result,
                                    "score": score(sample, result.get("output")), "headroom_before_request": headroom}
                            rows.append(item)
                            handle.write(json.dumps(api.redact(item, key), ensure_ascii=False) + "\n")
                            handle.flush()
                            print(json.dumps({"model": name, "completed": len(rows), "planned": development_n}), flush=True)
                        else:
                            meta["status"] = "DONE"
                    meta["processes_after_inference"] = process_snapshot()
            except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired, httpx.HTTPError) as exc:
                meta.update(status="BLOCKED" if not rows else "PARTIAL", error_type=type(exc).__name__)
            finally:
                meta["resources"] = monitor.summary()
                meta["summary"] = api.summarize(rows)
                write(directory / (name + "_resources.json"), monitor.rows)
                current = api.native_models(client, key)
                if any(instance.get("id") == identifier for m in current for instance in m.get("loaded_instances", [])):
                    unloaded = old.command([old.LMS, "unload", identifier])
                    meta["unload_returncode"] = unloaded.returncode
                meta["own_cleanup_confirmed"] = not any(instance.get("id") == identifier for m in api.native_models(client, key) for instance in m.get("loaded_instances", []))
                write(directory / "manifest.json", api.redact(manifest, key))
                if not meta["own_cleanup_confirmed"]:
                    raise RuntimeError("Own instance cleanup failed; no later model permitted")
        manifest["state"] = "completed"
    finally:
        manifest["finished_utc"] = old.now()
        if manifest["state"] == "running":
            manifest["state"] = "interrupted"
        write(directory / "manifest.json", api.redact(manifest, key))
        client.close()
    print(json.dumps({"run_directory": str(directory), "state": manifest["state"], "models": {n: m.get("summary") for n, m in manifest["models"].items()}}), flush=True)
    return directory


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Must be scheduled by the lead after downloads/builds stop")
    parser.add_argument("--models", nargs="+", choices=list(BASELINES), default=list(BASELINES))
    parser.add_argument("--n", type=int, choices=[12, 36], default=36)
    parser.add_argument("--model-root", type=Path, default=Path.home() / ".lmstudio/models")
    parser.add_argument("--bitnet-server", type=Path)
    parser.add_argument("--bitnet-model", type=Path)
    args = parser.parse_args()
    if args.bitnet_server or args.bitnet_model:
        if not args.run or not args.bitnet_server or not args.bitnet_model:
            parser.error("Native BitNet requires --run, --bitnet-server and --bitnet-model")
        run_bitnet(args.bitnet_server, args.bitnet_model, args.n)
    elif args.run:
        run(args.models, args.model_root, args.n)
    else:
        inventory = old.cli_json("ls", "--json")
        print(json.dumps({name: fingerprint(BASELINES[name], inventory, args.model_root) for name in args.models}, ensure_ascii=False, indent=2))
