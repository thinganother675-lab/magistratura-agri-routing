"""Once-only live HOME final driver. Plan-only never reads keys or calls HTTP.

All controls, data and scientific code must match the root-authored FROZEN
protocol. Independent policy calls are interleaved; responses are never reused.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import statistics
import time
import uuid

import httpx
import home_lm_api_benchmark as api
import home_pc_benchmark as home
from agro_route.evaluation import score
from agro_route.home_config import resolve_api_key
from agro_route.models import Model, SYSTEM_PROMPT, public_request
from agro_route.routing import hard_gate, grounded

ROOT = Path(__file__).resolve().parents[1]
METHODS = ["local", "cloud", "tool_cloud", "hybrid", "offline"]
LOCAL = {"model": "gemma-4-26b-a4b-it", "quantization": "IQ4_NL_XL", "gpu": "0.70",
         "context": 4096, "parallel": 1, "reasoning_effort": "none", "temperature": 0,
         "top_p": 1, "seed": 42, "max_tokens": 512, "response_format": "strict_json_schema_5fields"}
CLOUD = {"model": "mercury-2.5", "base_url": "https://api.inceptionlabs.ai/v1", "temperature": 0,
         "max_tokens": 512, "reasoning_effort": "instant", "response_format": "json_object",
         "timeout_s": 60, "input_usd_per_m": .04, "output_usd_per_m": .15, "price_date": "2026-10-01"}
CRITERIA = {"quality_margin": .05, "cloud_call_reduction_pp": .10,
            "critical_error_increase_max": 0, "p95_max_s": 10}
STATISTIC = {"bootstrap_seed": 20261001, "repeats": 5000, "unit": "sample.group"}
CATEGORIES = {"extractive_qa": 40, "numeric": 30, "missing_data": 20,
              "tool_selection": 20, "rule_interpretation": 20, "compound_reasoning": 20}
DEPENDENCIES = {f"src/agro_route/{name}.py" for name in
                ("models", "routing", "evaluation", "benchmark", "tools", "cli", "home_policy", "home_config")}
DEPENDENCIES |= {"scripts/home_pc_benchmark.py", "scripts/home_lm_api_benchmark.py", "scripts/run_home_final.py"}


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def update(path, value):
    temporary = Path(path).with_suffix(".tmp")
    write_new(temporary, value)
    temporary.replace(path)


def sanitize(value, secrets):
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[REDACTED_CREDENTIAL]")
        return value
    if isinstance(value, dict):
        return {sanitize(k, secrets): sanitize(v, secrets) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(v, secrets) for v in value]
    return value


def project_path(root, relative):
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ValueError("Frozen project paths must be relative strings")
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise ValueError("Frozen path escapes project")
    return candidate


def validate_protocol(path, root=ROOT):
    path, root = Path(path), Path(root)
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "FROZEN" or type(protocol.get("n")) is not int or protocol["n"] != 150:
        raise ValueError("Require an explicitly FROZEN 150-case protocol")
    local_settings = protocol.get("local", {})
    if not isinstance(local_settings, dict):
        raise ValueError("Frozen local controls must be an object")
    optional_weight = {k: local_settings[k] for k in ("gguf_sha256", "file_size_bytes") if k in local_settings}
    local_controls = {k: v for k, v in local_settings.items() if k not in optional_weight}
    if canonical(local_controls) != canonical(LOCAL):
        raise ValueError("Frozen local control differs from supported final protocol")
    if ("file_size_bytes" in optional_weight and (type(optional_weight["file_size_bytes"]) is not int or optional_weight["file_size_bytes"] <= 0)
            or "gguf_sha256" in optional_weight and (not isinstance(optional_weight["gguf_sha256"], str) or len(optional_weight["gguf_sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in optional_weight["gguf_sha256"]))):
        raise ValueError("Invalid optional frozen weight metadata")
    fixed = {"cloud": CLOUD, "policies": METHODS, "execution_seed": 20261001,
             "budget_cap_usd": .25, "planning_input_tokens_per_call": 6000,
             "criteria": CRITERIA, "statistic": STATISTIC}
    if any(canonical(protocol.get(field)) != canonical(expected) for field, expected in fixed.items()):
        raise ValueError("Frozen control differs from supported final protocol")
    hashes = protocol.get("code_sha256", {})
    if not isinstance(hashes, dict) or not DEPENDENCIES.issubset(hashes):
        raise ValueError("Frozen imported-code hashes are incomplete")
    for relative, expected in hashes.items():
        file = project_path(root, relative)
        if file.suffix != ".py" or sha(file) != expected:
            raise ValueError("Frozen scientific/driver code hash mismatch")
    if protocol.get("prompt_sha256") != hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest():
        raise ValueError("Frozen system prompt hash mismatch")
    dataset = project_path(root, protocol["dataset_path"])
    if sha(dataset) != protocol.get("dataset_sha256"):
        raise ValueError("Frozen dataset hash mismatch")
    samples = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines()]
    ids = [sample.get("id") for sample in samples]
    if (len(samples) != 150 or len(set(ids)) != 150 or any(not isinstance(sid, str) or not sid for sid in ids)
            or ids != protocol.get("holdout_ids") or any(s.get("split") != "home_final" for s in samples)):
        raise ValueError("Require the same 150 unique frozen HOME final IDs and order")
    if Counter(s.get("category") for s in samples) != CATEGORIES or Counter(s.get("language") for s in samples) != {"en": 75, "ru": 75}:
        raise ValueError("Frozen category/language balance mismatch")
    if any(not isinstance(s.get("group"), str) or not s["group"] or not isinstance(s.get("expected"), dict)
           or not isinstance(s.get("input"), str) or not isinstance(s.get("scoring"), str) for s in samples):
        raise ValueError("Incomplete frozen holdout schema")
    planned_inputs = [max(6000, len(SYSTEM_PROMPT.encode()) + len(canonical(public_request(s)).encode()) + 1024) for s in samples]
    per_call = [(tokens * CLOUD["input_usd_per_m"] + 512 * CLOUD["output_usd_per_m"]) / 1e6 for tokens in planned_inputs]
    estimate = 3 * sum(per_call)  # at most one cloud call/policy for cloud, tool_cloud and hybrid
    if estimate > protocol["budget_cap_usd"]:
        raise ValueError("Planning estimate exceeds frozen paid-call cap")
    plan = {"phase": "HOME_FINAL", "target_n": 150, "holdout_ids": ids,
            "protocol_sha256": sha(path), "dataset_sha256": sha(dataset), "prompt_sha256": protocol["prompt_sha256"],
            "max_cloud_calls": 450, "planning_cost_estimate_usd": estimate,
            "max_planning_cost_per_call_usd": max(per_call), "budget_cap_usd": .25,
            "planning_method": "3 independent cloud-using policies; max(6000, UTF8 request+prompt bytes+1024) input estimate and512 output; estimate, not invoice or guaranteed tokenizer bound",
            "automatic_paid_retries": 0, "hidden_warmups": 0, "result_cache_reuse": False}
    return protocol, samples, plan


def schedule(samples, methods=METHODS, seed=20261001):
    rng = random.Random(seed)
    order = []
    for sample in samples:
        shuffled = list(methods)
        rng.shuffle(shuffled)
        order.append({"sample_id": sample["id"], "methods": shuffled})
    return order


class ProviderBlocked(RuntimeError):
    def __init__(self, provider, reason):
        self.provider, self.reason = provider, reason
        super().__init__(provider + " unavailable")


def strict_cloud_record(record):
    """Preserve frozen Model.call parsing, but reject interrupted completions."""
    record = dict(record)
    raw = record.get("raw") or {}
    choices = raw.get("choices") or []
    finish = choices[0].get("finish_reason") if choices and isinstance(choices[0], dict) else None
    record["finish_reason"] = finish
    if not record.get("error") and finish != "stop":
        record.update(output=None, error={"type": "IncompleteCompletion", "finish_reason": finish})
    usage = record.get("usage") or {}
    if all(api.finite_nonnegative(usage.get(k)) for k in ("prompt_tokens", "completion_tokens")):
        record["cost_usd"] = (usage["prompt_tokens"] * .04 + usage["completion_tokens"] * .15) / 1e6
    else:
        record["cost_usd"] = None
    record.update(provider="cloud", timing={"backend_ttft_s": None, "backend_tokens_per_second": None,
                                             "reason": "Frozen nonstream Model.call; no client TTFT/decode TPS measured"})
    return record


def measured_decision(request, method, local, cloud, clock=time.perf_counter):
    """Policies receive only public request, never category, split or gold."""
    began, traces = clock(), []
    output, route, error, blocked, degraded = None, None, None, None, None
    tool_calls = 0
    try:
        gate = hard_gate(request) if method in ("tool_cloud", "hybrid", "offline") else None
        if gate:
            output, route, tool_calls = gate["output"], gate["route"], gate["tool_calls"]
        elif method in ("local", "cloud", "tool_cloud"):
            provider = local if method == "local" else cloud
            result = provider(request)
            traces.append(result)
            output, error = result.get("output"), result.get("error")
            route = "LOCAL_MODEL" if method == "local" else "CLOUD_MODEL"
        elif method in ("hybrid", "offline"):
            has_context = bool(request.get("context", "").strip())
            if has_context:
                try:
                    first = local(request)
                    traces.append(first)
                    if not first.get("error") and grounded(request, first):
                        output, route = first["output"], "LOCAL_MODEL"
                except ProviderBlocked as exc:
                    degraded = {"provider": exc.provider, "reason": exc.reason}
            if output is None:
                if method == "hybrid":
                    final = cloud(request)
                    traces.append(final)
                    output, error = final.get("output"), final.get("error")
                    route = "LOCAL_TO_CLOUD" if has_context and traces[:-1] else "CLOUD_MODEL"
                else:
                    route = "ABSTAIN"
                    output = {"action": "ABSTAIN", "answer": "Нет проверяемой локальной опоры; облако недоступно", "numeric": None}
        else:
            raise ValueError("Unsupported final policy")
    except ProviderBlocked as exc:
        blocked = {"provider": exc.provider, "reason": exc.reason}
        route, output = "NOT_RUN", None
    costs = [r.get("cost_usd") for r in traces]
    return {"status": "NOT_RUN" if blocked else "MEASURED", "route": route, "output": output, "trace": traces,
            "local_calls": sum(r.get("provider") == "local" for r in traces),
            "cloud_calls": sum(r.get("provider") == "cloud" for r in traces), "tool_calls": tool_calls,
            "cost_usd": sum(costs) if all(api.finite_nonnegative(c) for c in costs) else None,
            "latency_ms": (clock() - began) * 1000, "latency_kind": "measured_end_to_end_live",
            "error": error, "blocked_reason": blocked,
            "degraded_provider": degraded,
            "call_errors": sum(bool(r.get("error")) for r in traces)}


def fatal_status(error):
    status = (error or {}).get("http_status")
    return status in (401, 402, 403, 429) or (type(status) is int and status >= 500)


class Calls:
    """Independent providers, paid budget accounting and durable attempt log."""
    def __init__(self, local_fn, cloud_fn, manifest, directory, secrets=(), reserve=.0003168,
                 headroom=home.resource_headroom, on_local_stop=lambda: None):
        self.local_fn, self.cloud_fn = local_fn, cloud_fn
        self.manifest, self.directory, self.secrets = manifest, Path(directory), secrets
        self.reserve, self.headroom = reserve, headroom
        self.on_local_stop = on_local_stop
        self.local_stop = self.cloud_stop = None
        self.known_cost, self.unknown_cost_calls = 0.0, 0
        self.sample_id = self.method = None

    def event(self, event):
        with (self.directory / "attempts.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(sanitize({"utc": now(), **event}, self.secrets), ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def call(self, provider, request):
        stopped = self.local_stop if provider == "local" else self.cloud_stop
        if stopped:
            raise ProviderBlocked(provider, stopped)
        if provider == "local":
            available = self.headroom()
            if available["ram_available_gib"] < 2 or available["gpu_free_mib"] < 512:
                self.local_stop = {"type": "resource_guard", **available}
                self.manifest["local_stop_reason"] = self.local_stop
                update(self.directory / "manifest.json", sanitize(self.manifest, self.secrets))
                self.on_local_stop()
                raise ProviderBlocked(provider, self.local_stop)
        elif (self.manifest["cloud_calls_actual"] >= 450 or
              self.known_cost + self.unknown_cost_calls * self.reserve + self.reserve > .25):
            self.cloud_stop = {"type": "budget_guard"}
            self.manifest["cloud_stop_reason"] = self.cloud_stop
            update(self.directory / "manifest.json", sanitize(self.manifest, self.secrets))
            raise ProviderBlocked(provider, self.cloud_stop)
        counter = provider + "_calls_actual"
        self.manifest[counter] += 1  # before HTTP; interrupted attempts remain visible
        if provider == "cloud":
            self.unknown_cost_calls += 1  # pending attempt has unknown possible charge
            self.manifest.update(cloud_unknown_cost_calls=self.unknown_cost_calls,
                                 cloud_reserved_cost_estimate_usd=self.unknown_cost_calls * self.reserve)
        update(self.directory / "manifest.json", sanitize(self.manifest, self.secrets))
        attempt = {"provider": provider, "sample_id": self.sample_id, "method": self.method,
                   "attempt_number_provider": self.manifest[counter]}
        self.event({"event": "call_started", **attempt})
        began = time.perf_counter()
        try:
            result = (self.local_fn if provider == "local" else self.cloud_fn)(request)
        except (httpx.HTTPError, ValueError, KeyError, TypeError, OSError, RuntimeError) as exc:
            result = {"output": None, "error": {"type": type(exc).__name__, "http_status": getattr(getattr(exc, "response", None), "status_code", None)},
                      "usage": {}, "raw": None, "timing": {}, "cost_usd": None if provider == "cloud" else 0.,
                      "latency_ms": (time.perf_counter() - began) * 1000}
        result = sanitize({**result, "provider": provider}, self.secrets)
        if provider == "cloud":
            cost = result.get("cost_usd")
            if api.finite_nonnegative(cost):
                self.known_cost += cost
                self.unknown_cost_calls -= 1
            if self.known_cost + self.unknown_cost_calls * self.reserve >= .25:
                self.cloud_stop = {"type": "observed_or_reserved_budget"}
        if fatal_status(result.get("error")):
            stop = {"type": "provider_http_failure", "http_status": result["error"]["http_status"]}
            if provider == "cloud":
                self.cloud_stop = stop
            else:
                self.local_stop = stop
                self.on_local_stop()
        if provider == "local" and (result.get("raw") or {}).get("reasoning_content"):
            result.update(output=None, error={"type": "UnexpectedReasoning", "requested": "none"})
            self.local_stop = {"type": "frozen_reasoning_control_failed"}
            self.on_local_stop()
        self.manifest.update(cloud_known_cost_estimate_usd=self.known_cost,
                             cloud_unknown_cost_calls=self.unknown_cost_calls,
                             cloud_reserved_cost_estimate_usd=self.unknown_cost_calls * self.reserve,
                             cloud_stop_reason=self.cloud_stop, local_stop_reason=self.local_stop)
        self.event({"event": "call_finished", **attempt, "error": result.get("error"), "cost_usd": result.get("cost_usd")})
        update(self.directory / "manifest.json", sanitize(self.manifest, self.secrets))
        return result

    def local(self, request):
        return self.call("local", request)

    def cloud(self, request):
        return self.call("cloud", request)


def summarize(rows, samples):
    out = {}
    for method in METHODS:
        records = [r for r in rows if r["method"] == method]
        measured = [r for r in records if r["result"]["status"] == "MEASURED"]
        values = [r["result"]["latency_ms"] / 1000 for r in measured]
        traces = [trace for r in records for trace in r["result"]["trace"]]
        def numeric_total(items):
            known = [v for v in items if api.finite_nonnegative(v)]
            return {"total": sum(known) if known else None, "coverage": len(known)}
        done = {r["sample"]["id"] for r in measured}
        timings = {field: [t.get("timing", {}).get(field) for t in traces] for field in
                   ("first_nonempty_delta_s_client", "first_answer_delta_s_client", "completion_tokens_per_second_client_approx")}
        out[method] = {"target_n": 150, "n": len(measured), "n_records": len(records),
                       "not_run": 150 - len(measured), "correct": sum(r["score"]["correct"] for r in measured),
                       "quality": sum(r["score"]["correct"] for r in measured) / len(measured) if measured else None,
                       "critical_errors": sum(r["score"]["critical_error"] for r in measured),
                       "error_decisions": sum(bool(r["result"]["error"]) for r in measured),
                       "call_errors": sum(r["result"]["call_errors"] for r in records),
                       "latency_mean_s": statistics.mean(values) if values else None,
                       "latency_p50_s": statistics.median(values) if values else None,
                       "latency_p95_s": float(home.np.quantile(values, .95)) if values else None,
                       "routes": dict(Counter(r["result"]["route"] for r in records)),
                       "calls": {kind: sum(r["result"][kind + "_calls"] for r in records) for kind in ("cloud", "local", "tool")},
                       "abstentions": sum((r["result"]["output"] or {}).get("action") == "ABSTAIN" for r in measured),
                       "cost_usd": numeric_total([t.get("cost_usd") for t in traces if t.get("provider") == "cloud"]),
                       "cloud_unknown_cost_calls": sum(not api.finite_nonnegative(t.get("cost_usd")) for t in traces if t.get("provider") == "cloud"),
                       "usage": {provider: {key: numeric_total([t.get("usage", {}).get(key) for t in traces if t.get("provider") == provider])
                                            for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
                                 for provider in ("local", "cloud")},
                       "client_timing": {field: {"p50": statistics.median(known) if known else None, "coverage": len(known)}
                                         for field, vals in timings.items() if (known := [v for v in vals if api.finite_nonnegative(v)]) or True},
                       "by_category": {k: {"n": len(sub), "correct": sum(r["score"]["correct"] for r in sub)}
                                       for k in CATEGORIES if (sub := [r for r in measured if r["sample"]["category"] == k])},
                       "by_language": {k: {"n": len(sub), "correct": sum(r["score"]["correct"] for r in sub)}
                                       for k in ("en", "ru") if (sub := [r for r in measured if r["sample"]["language"] == k])},
                       "unattempted_ids": [s["id"] for s in samples if s["id"] not in done]}
    return out


def hardware():
    memory = home.Memory(); memory.length = home.ctypes.sizeof(memory)
    home.ctypes.windll.kernel32.GlobalMemoryStatusEx(home.ctypes.byref(memory))
    gpu = home.command(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"], 10)
    return {"os": platform.system(), "os_release": platform.release(), "os_version": platform.version(),
            "python": platform.python_version(), "logical_cpu_count": os.cpu_count(), "ram_total_gib": memory.total / 2**30,
            "gpu_inventory": gpu.stdout.strip() if gpu.returncode == 0 else "UNKNOWN",
            "hostname_and_user_saved": False}


def preflight_local(protocol, client, key):
    catalog = api.native_models(client, key)
    if any(m.get("loaded_instances") for m in catalog):
        raise RuntimeError("Existing local model instance; do not alter another task's model")
    matches = [m for m in catalog if m.get("key") == LOCAL["model"]]
    if len(matches) != 1 or matches[0].get("quantization", {}).get("name") != LOCAL["quantization"]:
        raise RuntimeError("Frozen installed weight identity mismatch")
    native = matches[0]
    if native.get("size_bytes") != 16847892149:
        raise RuntimeError("Frozen total catalog artifact size mismatch")
    weight = {"model_key": native["key"], "quantization": native["quantization"], "size_bytes": native["size_bytes"]}
    if protocol["local"].get("gguf_sha256"):
        listing = home.cli_json("ls", "--json")
        paths = [m.get("path") for m in listing if m.get("modelKey") == LOCAL["model"]]
        if len(paths) != 1 or not isinstance(paths[0], str):
            raise RuntimeError("Cannot locate frozen weight for required checksum")
        actual = Path(paths[0])
        if not actual.is_absolute():
            actual = Path.home() / ".lmstudio" / "models" / actual
        if not actual.is_file() or actual.stat().st_size != protocol["local"].get("file_size_bytes", 14556687680):
            raise RuntimeError("Cannot verify required frozen weight file")
        weight["gguf_sha256"] = sha(actual)
        weight["gguf_file_size_bytes"] = actual.stat().st_size
        weight["catalog_size_bytes"] = native["size_bytes"]
        if weight["gguf_sha256"] != protocol["local"]["gguf_sha256"]:
            raise RuntimeError("Frozen weight checksum mismatch")
    headroom = home.resource_headroom()
    if headroom["ram_available_gib"] < 3 or headroom["gpu_free_mib"] < 1024:
        raise RuntimeError("Insufficient baseline headroom before claiming final")
    args = [home.LMS, "load", LOCAL["model"], "--context-length", "4096", "--parallel", "1", "--gpu", "0.70", "--yes", "--estimate-only"]
    estimate = home.command(args)
    if estimate.returncode:
        raise RuntimeError("Local estimate failed before claiming final")
    return catalog, weight, headroom, estimate


def run(protocol_path, *, execute=False, root=ROOT):
    root = Path(root)
    protocol, samples, plan = validate_protocol(protocol_path, root)
    if not execute:
        return plan
    local_key, local_source = resolve_api_key("local", env_path=root / ".env")
    cloud_key, cloud_source = resolve_api_key("mercury", env_path=root / ".env")
    if not local_key or not cloud_key:
        raise RuntimeError("Both frozen-provider credentials must be configured")
    secrets = (local_key, cloud_key)
    claim = root / "results" / (".home_final_" + protocol["dataset_sha256"] + "_claim.json")
    if claim.exists():
        raise RuntimeError("This frozen dataset already has a final execution claim; no automatic repeat or resume")
    client = httpx.Client(timeout=60, trust_env=False)
    try:
        before, weight_metadata, pre_headroom, estimate = preflight_local(protocol, client, local_key)
        device = hardware()
    except BaseException:
        client.close()
        raise
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ") + "_" + uuid.uuid4().hex[:8] + "_final"
    directory = root / "results" / run_id
    try:
        write_new(claim, {"run_id": run_id, "protocol_sha256": plan["protocol_sha256"], "claimed_utc": now(),
                          "automatic_resume_allowed": False, "preflight_passed": True})
        directory.mkdir(exist_ok=False)
    except BaseException:
        client.close()
        raise
    write_new(directory / "protocol_copy.json", protocol)
    write_new(directory / "samples_home_final.json", samples)
    write_new(directory / "schedule.json", schedule(samples))
    (directory / "harness_source.py").write_bytes(Path(__file__).read_bytes())
    (directory / "system_prompt.txt").write_text(SYSTEM_PROMPT, encoding="utf-8")
    write_new(directory / "hardware.json", device)
    write_new(directory / "weight_metadata.json", weight_metadata)
    write_new(directory / "catalog_before.json", sanitize(before, secrets))
    estimate_text = home.ANSI.sub("", estimate.stdout + "\n" + estimate.stderr)
    for homepath in (str(Path.home()), str(Path.home()).replace("\\", "/")):
        estimate_text = estimate_text.replace(homepath, "[USER_HOME]")
    (directory / "load_estimate.txt").write_text(sanitize(estimate_text, secrets), encoding="utf-8")
    manifest = {**plan, "run_id": run_id, "state": "running", "started_utc": now(), "sample_ids": protocol["holdout_ids"],
                "local": protocol["local"], "cloud": CLOUD, "policies": METHODS, "execution_seed": 20261001,
                "code_sha256": protocol["code_sha256"], "credential_sources": {"local": local_source, "cloud": cloud_source},
                "credential_values_persisted": False, "cloud_calls_actual": 0, "local_calls_actual": 0,
                "cloud_known_cost_estimate_usd": 0., "cloud_unknown_cost_calls": 0, "cloud_reserved_cost_estimate_usd": 0.,
                "local_energy_cost": "N/A; not measured", "provider_invoice_obtained": False,
                "cost_type": "uncached token price estimate; missingusage calls retain unknowncost and conservative planningreserve",
                "execution_context": "Sequential GPU and sequential policy HTTP calls; whole-system RAM/device VRAM includes other applications, host not isolated",
                "no_other_benchmark_gpu_activity": True, "local_load_metadata": {"actual_offloaded_layers": "UNKNOWN", "preflight_headroom": pre_headroom}}
    write_new(directory / "manifest.json", manifest)
    print("RESULTS_START " + directory.name, flush=True)
    identifier = "home-final-" + uuid.uuid4().hex[:8] + "-gemma26"
    meta = manifest["local_load_metadata"]
    rows, load_attempted = [], False
    local_logdir = root / ".runtime" / "home_final_logs" / run_id
    local_logdir.mkdir(parents=True, exist_ok=False)
    monitor = home.Monitor()
    calls = None
    try:
        with monitor:
            try:
                args = [home.LMS, "load", LOCAL["model"], "--context-length", "4096", "--parallel", "1",
                        "--gpu", "0.70", "--identifier", identifier, "--yes"]
                load_attempted = True
                began = time.perf_counter()
                loaded = home.guarded_load(args, local_logdir / "load.txt", meta)
                meta.update(cold_load_wall_s=time.perf_counter() - began, load_success=loaded.returncode == 0)
                if loaded.returncode:
                    raise RuntimeError("Guarded local load failed")
                catalog = api.native_models(client, local_key)
                matches = [(m, inst) for m in catalog for inst in m.get("loaded_instances", []) if inst.get("id") == identifier]
                if len(matches) != 1:
                    raise RuntimeError("Own local instance not verified")
                native, instance = matches[0]
                allowed = ((native.get("capabilities") or {}).get("reasoning") or {}).get("allowed_options", [])
                if (native.get("quantization", {}).get("name") != LOCAL["quantization"] or "off" not in allowed
                        or instance.get("config", {}).get("context_length") != 4096 or instance.get("config", {}).get("parallel") != 1):
                    raise RuntimeError("Frozen local capability/configuration mismatch")
                meta.update(own_instance_id=identifier, native_model_metadata=sanitize(native, secrets), actual_load_config=instance["config"])
                local_fn = lambda req: {**api.api_call(client, local_key, identifier, req, "none"), "provider": "local", "model": LOCAL["model"]}
                local_failure = None
            except (RuntimeError, ValueError, OSError, home.subprocess.TimeoutExpired, httpx.HTTPError) as exc:
                meta["load_error"] = {"type": type(exc).__name__}
                local_fn = lambda req: None
                local_failure = {"type": "local_load_failure", "error_type": type(exc).__name__}
                if load_attempted:
                    unloaded = home.command([home.LMS, "unload", identifier])
                    meta["unload_after_failure_success"] = unloaded.returncode == 0 and not any(p["identifier"] == identifier for p in home.cli_json("ps", "--json"))
                    if not meta["unload_after_failure_success"]:
                        raise RuntimeError("Uncertain local load cleanup; stop entire final before paidcalls")
                    load_attempted = False
            model = Model(CLOUD["base_url"], CLOUD["model"], cloud_key, .04, .15, timeout=60)
            def stop_local():
                nonlocal load_attempted
                if load_attempted:
                    unloaded = home.command([home.LMS, "unload", identifier])
                    meta["unload_on_local_stop_success"] = unloaded.returncode == 0 and not any(p["identifier"] == identifier for p in home.cli_json("ps", "--json"))
                    if not meta["unload_on_local_stop_success"]:
                        raise RuntimeError("Local stop cleanup failed; stop entire final")
                    load_attempted = False
            calls = Calls(local_fn, lambda req: strict_cloud_record(model.call(req)), manifest, directory, secrets,
                          plan["max_planning_cost_per_call_usd"], headroom=home.resource_headroom, on_local_stop=stop_local)
            calls.local_stop = local_failure
            with (directory / "attempts.jsonl").open("x", encoding="utf-8"):
                pass
            update(directory / "manifest.json", sanitize(manifest, secrets))
            ordered = {entry["sample_id"]: entry["methods"] for entry in schedule(samples)}
            with (directory / "raw_decisions.jsonl").open("x", encoding="utf-8") as journal:
                for index, sample in enumerate(samples):
                    for method in ordered[sample["id"]]:
                        calls.sample_id, calls.method = sample["id"], method
                        result = measured_decision(public_request(sample), method, calls.local, calls.cloud)
                        row = {"sample": sample, "method": method, "result": result,
                               "score": score(sample, result["output"]) if result["status"] == "MEASURED" else None}
                        row = sanitize(row, secrets)
                        journal.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                        journal.flush(); os.fsync(journal.fileno()); rows.append(row)
                    manifest["completed_sample_groups"] = index + 1
                    update(directory / "manifest.json", sanitize(manifest, secrets))
                    print(json.dumps({"case": index + 1, "target_n": 150, "local_calls": manifest["local_calls_actual"],
                                      "cloud_calls": manifest["cloud_calls_actual"], "known_cloud_cost_usd": calls.known_cost,
                                      "unknown_cost_calls": calls.unknown_cost_calls, "local_stopped": bool(calls.local_stop),
                                      "cloud_stopped": bool(calls.cloud_stop)}), flush=True)
        manifest["state"] = "partial_stopped" if any(r["result"]["status"] == "NOT_RUN" for r in rows) else "completed_with_errors" if any(r["result"]["call_errors"] for r in rows) else "completed"
    except BaseException as exc:
        manifest.update(state="partial_interrupted", interruption={"type": type(exc).__name__})
        raise
    finally:
        if load_attempted:
            try:
                unloaded = home.command([home.LMS, "unload", identifier])
                meta["unload_success"] = unloaded.returncode == 0 and not any(p["identifier"] == identifier for p in home.cli_json("ps", "--json"))
            except (RuntimeError, OSError, home.subprocess.TimeoutExpired) as exc:
                meta.update(unload_success=False, unload_error={"type": type(exc).__name__})
            if not meta.get("unload_success"):
                manifest.update(state="partial_cleanup_failed", cleanup_error={"type": "OwnInstanceUnloadFailure"})
        try:
            after = api.native_models(client, local_key)
            manifest["catalog_after"] = sanitize(after, secrets)
            manifest["headroom_after"] = home.resource_headroom()
        except (httpx.HTTPError, RuntimeError, ValueError, OSError) as exc:
            manifest["cleanup_verification_error"] = {"type": type(exc).__name__}
        local_log = local_logdir / "load.txt"
        if local_log.exists():
            original = local_log.read_bytes()
            text = original.decode("utf-8")
            for homepath in (str(Path.home()), str(Path.home()).replace("\\", "/")):
                text = text.replace(homepath, "[USER_HOME]")
            text = sanitize(text, secrets)
            (directory / "load_public.txt").write_text(text, encoding="utf-8")
            meta.update(load_original_sha256=hashlib.sha256(original).hexdigest(), load_public_sha256=sha(directory / "load_public.txt"),
                        load_log_sanitization="Only userhome path and any exactcredentialecho replaced; original remains local in ignored.runtime")
        manifest.update(finished_utc=now(), summary=summarize(rows, samples), resource_summary=monitor.summary())
        write_new(directory / "resources.json", monitor.rows)
        write_new(directory / "summary.json", {"run_id": run_id, "phase": "HOME_FINAL", "policies": manifest["summary"]})
        update(directory / "manifest.json", sanitize(manifest, secrets))
        client.close()
    validate_protocol(protocol_path, root)
    print("RESULTS " + directory.name, flush=True)
    return directory


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    flags = parser.add_mutually_exclusive_group()
    flags.add_argument("--execute", action="store_true")
    flags.add_argument("--plan-only", action="store_true")
    options = parser.parse_args()
    outcome = run(options.protocol, execute=options.execute)
    if isinstance(outcome, dict):
        print(json.dumps(outcome, ensure_ascii=False, indent=2))
