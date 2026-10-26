"""Explicit manual continuation after a storage failure; never automatic resume.

Original source, protocol, results and once-claim remain byte-for-byte intact.
Only the frozen decision/API/scorer are reused. The one infrastructure override
is bounded retry of filesystem replacement, never a model/provider request.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import uuid

import httpx
import run_home_final as final

ROOT = final.ROOT


def atomic_update(path, value, *, deadline_s=5., clock=time.monotonic, sleeper=time.sleep):
    """Write once to an exclusive temp, retry only Windows file replacement."""
    path = Path(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    final.write_new(temporary, value)
    deadline = clock() + deadline_s
    delay = .05
    while True:
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if clock() >= deadline:
                raise
            sleeper(min(delay, max(0., deadline - clock())))
            delay = min(.25, delay * 2)


def original_inventory(directory):
    directory = Path(directory)
    return {p.name: final.sha(p) for p in sorted(directory.iterdir()) if p.is_file()}


def verify_original(directory, authorized_hashes):
    if original_inventory(directory) != authorized_hashes:
        raise ValueError("Original interruption artifacts changed or file set differs")


def validate_recovery(protocol_path, original, authorization_path, *, root=ROOT):
    """Plan validation has no key, network, model load or claim side effect."""
    root, original = Path(root).resolve(), Path(original).resolve()
    if not original.is_relative_to(root / "results") or not original.is_dir():
        raise ValueError("Original run must be an existing workspace results directory")
    protocol, samples, plan = final.validate_protocol(protocol_path, root)
    authorization = json.loads(Path(authorization_path).read_text(encoding="utf-8"))
    if (authorization.get("status") != "MANUAL_RECOVERY_AUTHORIZED"
            or authorization.get("interruption_reason") != "windows_manifest_replace_failure"
            or authorization.get("original_run_id") != original.name
            or authorization.get("protocol_sha256") != plan["protocol_sha256"]
            or authorization.get("recovery_driver_sha256") != final.sha(__file__)
            or not isinstance(authorization.get("authorized_utc"), str)):
        raise ValueError("Require the exact root-authorized manual recovery annex and code hash")
    hashes = authorization.get("original_files_sha256")
    if not isinstance(hashes, dict):
        raise ValueError("Require byte hashes of every original result file")
    verify_original(original, hashes)
    required = {"manifest.json", "manifest.tmp", "attempts.jsonl", "raw_decisions.jsonl", "protocol_copy.json",
                "harness_source.py", "samples_home_final.json", "schedule.json", "resources.json", "summary.json"}
    if not required.issubset(hashes):
        raise ValueError("Incomplete original interruption evidence")
    if (final.canonical(json.loads((original / "protocol_copy.json").read_text(encoding="utf-8"))) != final.canonical(protocol)
            or final.sha(original / "harness_source.py") != protocol["code_sha256"]["scripts/run_home_final.py"]
            or final.canonical(json.loads((original / "samples_home_final.json").read_text(encoding="utf-8"))) != final.canonical(samples)):
        raise ValueError("Original frozen source, protocol or full sample copy mismatch")
    ordering = json.loads((original / "schedule.json").read_text(encoding="utf-8"))
    if ordering != final.schedule(samples):
        raise ValueError("Original full frozen policy schedule mismatch")
    rows = [json.loads(line) for line in (original / "raw_decisions.jsonl").read_text(encoding="utf-8").splitlines()]
    events = [json.loads(line) for line in (original / "attempts.jsonl").read_text(encoding="utf-8").splitlines()]
    prefix = authorization.get("resume_after_completed_cases")
    if type(prefix) is not int or prefix != 6 or len(rows) != prefix * 5:
        raise ValueError("Require the authorized six complete original cases only")
    expected_pairs = [(entry["sample_id"], method) for entry in ordering[:prefix] for method in entry["methods"]]
    if [(r["sample"]["id"], r["method"]) for r in rows] != expected_pairs:
        raise ValueError("Original decisions are not the exact completed schedule prefix")
    by_id = {s["id"]: s for s in samples}
    for row in rows:
        sample = by_id[row["sample"]["id"]]
        if final.canonical(row["sample"]) != final.canonical(sample):
            raise ValueError("Original sample/gold differs from the frozen dataset")
        expected_score = final.score(sample, row["result"]["output"]) if row["result"]["status"] == "MEASURED" else None
        if final.canonical(row["score"]) != final.canonical(expected_score):
            raise ValueError("Original immutable score recomputation mismatch")
    def key(event):
        return (event["provider"], event["sample_id"], event["method"], event["attempt_number_provider"])
    started = [key(e) for e in events if e["event"] == "call_started"]
    finished = [key(e) for e in events if e["event"] == "call_finished"]
    if (len(events) != len(started) + len(finished) or len(set(started)) != len(started)
            or len(set(finished)) != len(finished) or set(started) != set(finished)):
        raise ValueError("Pending, duplicate or unknown original provider attempt; unsafe to continue")
    counts = dict(Counter(k[0] for k in started))
    if counts != {"local": 10, "cloud": 12} or authorization.get("original_calls") != counts:
        raise ValueError("Require the verified original ten local and twelve cloud attempts")
    for provider, n in counts.items():
        if sorted(k[3] for k in started if k[0] == provider) != list(range(1, n + 1)):
            raise ValueError("Original provider attempt sequence is discontinuous")
    traces = [t for row in rows for t in row["result"]["trace"]]
    if Counter(t["provider"] for t in traces) != counts:
        raise ValueError("Original responses and provider attempt journal disagree")
    attempt_by_decision = Counter((k[0], k[1], k[2]) for k in started)
    trace_by_decision = Counter((t["provider"], row["sample"]["id"], row["method"]) for row in rows for t in row["result"]["trace"])
    if attempt_by_decision != trace_by_decision:
        raise ValueError("Original attempt/sample/policy alignment mismatch")
    cloud = [t for t in traces if t["provider"] == "cloud"]
    known = sum(t["cost_usd"] for t in cloud if final.api.finite_nonnegative(t.get("cost_usd")))
    unknown = sum(not final.api.finite_nonnegative(t.get("cost_usd")) for t in cloud)
    old_manifest = json.loads((original / "manifest.json").read_text(encoding="utf-8"))
    if (old_manifest.get("protocol_sha256") != plan["protocol_sha256"]
            or old_manifest.get("completed_sample_groups") != prefix
            or old_manifest.get("local_calls_actual") != counts["local"]
            or old_manifest.get("cloud_calls_actual") != counts["cloud"]
            or old_manifest.get("cloud_unknown_cost_calls") != unknown
            or abs(old_manifest.get("cloud_known_cost_estimate_usd", -1) - known) > 1e-12
            or old_manifest.get("local_stop_reason") or old_manifest.get("cloud_stop_reason")):
        raise ValueError("Original cumulative accounting or provider state mismatch")
    claim = root / "results" / (".home_final_" + protocol["dataset_sha256"] + "_claim.json")
    existing = json.loads(claim.read_text(encoding="utf-8"))
    if existing.get("run_id") != original.name or existing.get("protocol_sha256") != plan["protocol_sha256"]:
        raise ValueError("Original once-only claim identity mismatch")
    recovery = {"target_n": 150, "segment_start": prefix, "remaining_n": 150 - prefix,
                "target_segment_decisions": (150 - prefix) * 5, "original_run_id": original.name,
                "original_files_sha256": hashes, "original_claim_sha256": final.sha(claim),
                "authorization_sha256": final.sha(authorization_path), "recovery_driver_sha256": final.sha(__file__),
                "original_call_baseline": counts, "original_known_cloud_cost_usd": known,
                "original_unknown_cost_calls": unknown, "automatic_resume_allowed": False,
                "original_attempts_repeated": 0, "filesystem_only_replace_retry_deadline_s": 5.}
    return protocol, samples, plan, ordering, rows, recovery


def run(protocol_path, original, authorization_path, *, execute=False, root=ROOT):
    root, original = Path(root), Path(original)
    protocol, samples, plan, ordering, original_rows, recovery = validate_recovery(protocol_path, original, authorization_path, root=root)
    if not execute:
        return recovery
    local_key, local_source = final.resolve_api_key("local", env_path=root / ".env")
    cloud_key, cloud_source = final.resolve_api_key("mercury", env_path=root / ".env")
    if not local_key or not cloud_key:
        raise RuntimeError("Both frozen-provider credentials must be configured")
    secrets = (local_key, cloud_key)
    claim = root / "results" / (".home_final_recovery_" + protocol["dataset_sha256"] + "_" + original.name + "_claim.json")
    if claim.exists():
        raise RuntimeError("This original run already has a manual continuation claim")
    client = httpx.Client(timeout=60, trust_env=False)
    try:
        before, weight, pre_headroom, estimate = final.preflight_local(protocol, client, local_key)
        device = final.hardware()
    except BaseException:
        client.close()
        raise
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ") + "_" + uuid.uuid4().hex[:8] + "_final_continuation"
    directory = root / "results" / run_id
    final.write_new(claim, {"run_id": run_id, "claimed_utc": final.now(), **recovery})
    directory.mkdir(exist_ok=False)
    for name, value in (("protocol_copy.json", protocol), ("samples_home_final.json", samples), ("schedule.json", ordering),
                        ("authorization_copy.json", json.loads(Path(authorization_path).read_text(encoding="utf-8"))),
                        ("hardware.json", device), ("weight_metadata.json", weight), ("catalog_before.json", final.sanitize(before, secrets))):
        final.write_new(directory / name, value)
    (directory / "harness_source.py").write_bytes(Path(__file__).read_bytes())
    (directory / "system_prompt.txt").write_text(final.SYSTEM_PROMPT, encoding="utf-8")
    estimate_text = final.home.ANSI.sub("", estimate.stdout + "\n" + estimate.stderr)
    for homepath in (str(Path.home()), str(Path.home()).replace("\\", "/")):
        estimate_text = estimate_text.replace(homepath, "[USER_HOME]")
    (directory / "load_estimate.txt").write_text(final.sanitize(estimate_text, secrets), encoding="utf-8")
    manifest = {**plan, **recovery, "run_id": run_id, "phase": "HOME_FINAL_CONTINUATION", "state": "running",
                "started_utc": final.now(), "sample_ids": protocol["holdout_ids"], "local": protocol["local"],
                "cloud": final.CLOUD, "policies": final.METHODS, "execution_seed": 20261001,
                "code_sha256": protocol["code_sha256"], "credential_sources": {"local": local_source, "cloud": cloud_source},
                "credential_values_persisted": False, "call_counter_scope": "cumulative_original_plus_continuation",
                "cloud_calls_actual": recovery["original_call_baseline"]["cloud"], "local_calls_actual": recovery["original_call_baseline"]["local"],
                "cloud_known_cost_estimate_usd": recovery["original_known_cloud_cost_usd"],
                "cloud_unknown_cost_calls": recovery["original_unknown_cost_calls"],
                "cloud_reserved_cost_estimate_usd": recovery["original_unknown_cost_calls"] * plan["max_planning_cost_per_call_usd"],
                "completed_segment_cases": 0, "completed_sample_groups": recovery["segment_start"],
                "local_energy_cost": "N/A; not measured", "provider_invoice_obtained": False,
                "cost_type": "Uncached token-price estimate; missing usage retains unknown cost and planning reserve",
                "execution_context": "Sequential GPU/provider calls; infrastructure interruption and second cold load declared; host not isolated",
                "infrastructure_override": "Runtime final.update replaced by bounded filesystem-only atomic replacement retry; no provider retries or scientific changes",
                "no_other_benchmark_gpu_activity": True,
                "local_load_metadata": {"actual_offloaded_layers": "UNKNOWN", "preflight_headroom": pre_headroom}}
    final.write_new(directory / "manifest.json", manifest)
    print("RESULTS_START " + directory.name, flush=True)
    identifier = "home-final-recovery-" + uuid.uuid4().hex[:8] + "-gemma26"
    meta, rows, load_attempted = manifest["local_load_metadata"], [], False
    logs = root / ".runtime/home_final_logs" / run_id
    logs.mkdir(parents=True, exist_ok=False)
    monitor = final.home.Monitor()
    original_update = final.update
    final.update = atomic_update
    try:
        with monitor:
            try:
                args = [final.home.LMS, "load", final.LOCAL["model"], "--context-length", "4096", "--parallel", "1",
                        "--gpu", "0.70", "--identifier", identifier, "--yes"]
                load_attempted = True
                began = time.perf_counter()
                loaded = final.home.guarded_load(args, logs / "load.txt", meta)
                meta.update(cold_load_wall_s=time.perf_counter() - began, load_success=loaded.returncode == 0)
                if loaded.returncode:
                    raise RuntimeError("Guarded continuation local load failed")
                catalog = final.api.native_models(client, local_key)
                matches = [(m, inst) for m in catalog for inst in m.get("loaded_instances", []) if inst.get("id") == identifier]
                if len(matches) != 1:
                    raise RuntimeError("Own continuation local instance not verified")
                native, instance = matches[0]
                allowed = ((native.get("capabilities") or {}).get("reasoning") or {}).get("allowed_options", [])
                if (native.get("quantization", {}).get("name") != final.LOCAL["quantization"] or "off" not in allowed
                        or instance.get("config", {}).get("context_length") != 4096 or instance.get("config", {}).get("parallel") != 1):
                    raise RuntimeError("Frozen continuation local capability/configuration mismatch")
                meta.update(own_instance_id=identifier, native_model_metadata=final.sanitize(native, secrets), actual_load_config=instance["config"])
                local_fn = lambda req: {**final.api.api_call(client, local_key, identifier, req, "none"), "provider": "local", "model": final.LOCAL["model"]}
                local_failure = None
            except (RuntimeError, ValueError, OSError, final.home.subprocess.TimeoutExpired, httpx.HTTPError) as exc:
                meta["load_error"] = {"type": type(exc).__name__}
                local_fn = lambda req: None
                local_failure = {"type": "local_load_failure", "error_type": type(exc).__name__}
                if load_attempted:
                    unloaded = final.home.command([final.home.LMS, "unload", identifier])
                    meta["unload_after_failure_success"] = unloaded.returncode == 0 and not any(p["identifier"] == identifier for p in final.home.cli_json("ps", "--json"))
                    if not meta["unload_after_failure_success"]:
                        raise RuntimeError("Uncertain continuation cleanup; stop before paid calls")
                    load_attempted = False
            model = final.Model(final.CLOUD["base_url"], final.CLOUD["model"], cloud_key, .04, .15, timeout=60)
            def stop_local():
                nonlocal load_attempted
                if load_attempted:
                    unloaded = final.home.command([final.home.LMS, "unload", identifier])
                    meta["unload_on_local_stop_success"] = unloaded.returncode == 0 and not any(p["identifier"] == identifier for p in final.home.cli_json("ps", "--json"))
                    if not meta["unload_on_local_stop_success"]:
                        raise RuntimeError("Continuation local stop cleanup failed")
                    load_attempted = False
            calls = final.Calls(local_fn, lambda req: final.strict_cloud_record(model.call(req)), manifest, directory, secrets,
                                plan["max_planning_cost_per_call_usd"], headroom=final.home.resource_headroom, on_local_stop=stop_local)
            calls.known_cost = recovery["original_known_cloud_cost_usd"]
            calls.unknown_cost_calls = recovery["original_unknown_cost_calls"]
            calls.local_stop = local_failure
            with (directory / "attempts.jsonl").open("x", encoding="utf-8"):
                pass
            atomic_update(directory / "manifest.json", final.sanitize(manifest, secrets))
            ordered = {entry["sample_id"]: entry["methods"] for entry in ordering}
            with (directory / "raw_decisions.jsonl").open("x", encoding="utf-8") as journal:
                for index, sample in enumerate(samples[recovery["segment_start"]:]):
                    for method in ordered[sample["id"]]:
                        calls.sample_id, calls.method = sample["id"], method
                        result = final.measured_decision(final.public_request(sample), method, calls.local, calls.cloud)
                        row = {"sample": sample, "method": method, "result": result,
                               "score": final.score(sample, result["output"]) if result["status"] == "MEASURED" else None}
                        row = final.sanitize(row, secrets)
                        journal.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                        journal.flush(); os.fsync(journal.fileno()); rows.append(row)
                    manifest.update(completed_segment_cases=index + 1, completed_sample_groups=recovery["segment_start"] + index + 1)
                    atomic_update(directory / "manifest.json", final.sanitize(manifest, secrets))
                    print(json.dumps({"case": recovery["segment_start"] + index + 1, "target_n": 150,
                                      "segment_completed": index + 1, "local_calls_cumulative": manifest["local_calls_actual"],
                                      "cloud_calls_cumulative": manifest["cloud_calls_actual"], "known_cloud_cost_usd": calls.known_cost,
                                      "unknown_cost_calls": calls.unknown_cost_calls, "local_stopped": bool(calls.local_stop),
                                      "cloud_stopped": bool(calls.cloud_stop)}), flush=True)
        combined = original_rows + rows
        manifest["state"] = "partial_stopped" if any(r["result"]["status"] == "NOT_RUN" for r in combined) else "completed_with_errors" if any(r["result"]["call_errors"] for r in combined) else "completed"
    except BaseException as exc:
        manifest.update(state="partial_interrupted", interruption={"type": type(exc).__name__})
        raise
    finally:
        if load_attempted:
            try:
                unloaded = final.home.command([final.home.LMS, "unload", identifier])
                meta["unload_success"] = unloaded.returncode == 0 and not any(p["identifier"] == identifier for p in final.home.cli_json("ps", "--json"))
            except (RuntimeError, OSError, final.home.subprocess.TimeoutExpired) as exc:
                meta.update(unload_success=False, unload_error={"type": type(exc).__name__})
            if not meta.get("unload_success"):
                manifest.update(state="partial_cleanup_failed", cleanup_error={"type": "OwnInstanceUnloadFailure"})
        try:
            manifest["catalog_after"] = final.sanitize(final.api.native_models(client, local_key), secrets)
            manifest["headroom_after"] = final.home.resource_headroom()
        except (httpx.HTTPError, RuntimeError, ValueError, OSError) as exc:
            manifest["cleanup_verification_error"] = {"type": type(exc).__name__}
        if (logs / "load.txt").exists():
            original_log = (logs / "load.txt").read_bytes()
            text = original_log.decode("utf-8")
            for homepath in (str(Path.home()), str(Path.home()).replace("\\", "/")):
                text = text.replace(homepath, "[USER_HOME]")
            (directory / "load_public.txt").write_text(final.sanitize(text, secrets), encoding="utf-8")
            meta.update(load_original_sha256=final.hashlib.sha256(original_log).hexdigest(), load_public_sha256=final.sha(directory / "load_public.txt"))
        manifest.update(finished_utc=final.now(), summary=final.summarize(rows, samples), resource_summary=monitor.summary(),
                        segment_call_counts={p: manifest[p + "_calls_actual"] - recovery["original_call_baseline"][p] for p in ("local", "cloud")})
        final.write_new(directory / "resources.json", monitor.rows)
        final.write_new(directory / "summary.json", {"run_id": run_id, "phase": "HOME_FINAL_CONTINUATION", "segment_start": recovery["segment_start"], "policies": manifest["summary"]})
        atomic_update(directory / "manifest.json", final.sanitize(manifest, secrets))
        final.update = original_update
        client.close()
    final.validate_protocol(protocol_path, root)
    verify_original(original, recovery["original_files_sha256"])
    original_claim = root / "results" / (".home_final_" + protocol["dataset_sha256"] + "_claim.json")
    if final.sha(original_claim) != recovery["original_claim_sha256"]:
        raise RuntimeError("Original once-only claim changed during continuation")
    print("RESULTS " + directory.name, flush=True)
    return directory


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--resume-after", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    options = parser.parse_args()
    outcome = run(options.protocol, options.resume_after, options.authorization, execute=options.execute)
    if isinstance(outcome, dict):
        print(json.dumps(outcome, ensure_ascii=False, indent=2))
