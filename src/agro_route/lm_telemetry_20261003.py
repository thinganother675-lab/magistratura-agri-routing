"""Native LM Studio streaming telemetry. No credentials or headers in records.

Client event spans are observations, not backend execution timers. Whole-device
memory and LM Studio process-group RSS must never be called per-model allocation.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
import math
import os
import subprocess
import threading
import time
from typing import Iterable

VERSION = "lm_telemetry_20261003_v1"
STAT_FIELDS = ("input_tokens", "total_output_tokens", "reasoning_output_tokens",
               "tokens_per_second", "time_to_first_token_seconds", "model_load_time_seconds")
RESOURCE_FIELDS = ("gpu_memory_used_mib", "gpu_memory_free_mib", "gpu_utilization_pct",
                   "gpu_temperature_c", "gpu_power_w", "system_ram_used_gib",
                   "system_ram_available_gib", "lmstudio_process_group_rss_mib")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def normalized_stats(stats):
    stats = stats if isinstance(stats, dict) else {}
    return {field: stats.get(field) if finite(stats.get(field)) else None for field in STAT_FIELDS}


def redact(value, secret):
    if isinstance(value, str):
        return value.replace(secret, "[REDACTED]") if secret else value
    if isinstance(value, list):
        return [redact(v, secret) for v in value]
    if isinstance(value, dict):
        return {k: redact(v, secret) for k, v in value.items()}
    return value


def native_payload(identifier, system, prompt, max_output=512):
    if not isinstance(prompt, str) or not isinstance(system, str):
        raise ValueError("Text-only prompt required")
    if isinstance(max_output, bool) or not isinstance(max_output, int) or max_output <= 0:
        raise ValueError("Invalid output budget")
    return {"model": identifier, "input": prompt, "system_prompt": system,
            "stream": True, "store": False, "integrations": [],
            "temperature": 0, "top_p": 1, "max_output_tokens": max_output,
            "reasoning": "off", "context_length": 2048}


def parse_native_sse(lines: Iterable[str], started: float, clock=time.perf_counter):
    events, first_any, first_answer, last_any = [], None, None, None
    prompt_start = prompt_end = None
    result, error = None, None
    previous = -1.0
    for line in lines:
        if not line.startswith("data:"):
            continue
        elapsed = clock() - started
        if not finite(elapsed) or elapsed < previous:
            raise ValueError("Nonmonotonic stream timing")
        previous = elapsed
        try:
            body = json.loads(line[5:].strip())
        except ValueError:
            error = "MalformedSSE"
            break
        if not isinstance(body, dict) or not isinstance(body.get("type"), str):
            error = "MalformedSSE"
            break
        kind = body["type"]
        events.append({"elapsed_s": elapsed, "data": body})
        if kind == "prompt_processing.start":
            prompt_start = elapsed
        elif kind == "prompt_processing.end":
            prompt_end = elapsed
        elif kind in {"message.delta", "reasoning.delta"} and body.get("content"):
            if first_any is None:
                first_any = elapsed
            if kind == "message.delta" and first_answer is None:
                first_answer = elapsed
            last_any = elapsed
        elif kind.startswith("tool_call."):
            error = "UnexpectedToolCall"
        elif kind == "error":
            error = "ProviderStreamError"
        elif kind == "chat.end":
            result = body.get("result")
            break
    output = result.get("output", []) if isinstance(result, dict) else []
    if not isinstance(output, list) or any(not isinstance(part, dict) for part in output):
        error = "MalformedOutput"
        output = []
    if any(part.get("type") in {"tool_call", "invalid_tool_call"} for part in output):
        error = "UnexpectedToolCall"
    stats = normalized_stats(result.get("stats") if isinstance(result, dict) else None)
    prompt_span = prompt_end - prompt_start if prompt_start is not None and prompt_end is not None else None
    decode_span = last_any - first_any if first_any is not None and last_any is not None else None
    return {"stream_complete": isinstance(result, dict), "error": error or (None if result else "MissingChatEnd"),
            "events": events, "result": result,
            "response_text": "".join(str(p.get("content", "")) for p in output if p.get("type") == "message"),
            "reasoning_text": "".join(str(p.get("content", "")) for p in output if p.get("type") == "reasoning"),
            "stats": stats, "timing": {"client_ttft_any_s": first_any, "client_ttft_answer_s": first_answer,
            "client_generation_span_s": decode_span, "client_prompt_processing_span_s": prompt_span,
            "client_prompt_token_equivalent_tps": stats["input_tokens"] / prompt_span if prompt_span and prompt_span > 0 and stats["input_tokens"] is not None else None}}


def parse_json_presentation(text):
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if lines[0] not in {"```", "```json", "```JSON"}:
            raise ValueError("Invalid fence")
        text = "\n".join(lines[1:-1])
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("JSON object required")
    return obj


def windows_ram():
    class Memory(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD),
                    *[(name, ctypes.c_ulonglong) for name in ("total", "available", "total_page", "available_page", "total_virtual", "available_virtual", "extended")]]
    memory = Memory()
    memory.length = ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise RuntimeError("RAM observation unavailable")
    return {"system_ram_used_gib": (memory.total - memory.available) / 2**30,
            "system_ram_available_gib": memory.available / 2**30}


def lmstudio_process_rss():
    """Read basename and working set only; never process command lines/env."""
    kernel, psapi = ctypes.WinDLL("kernel32", use_last_error=True), ctypes.WinDLL("psapi", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD),
                    *[(name, ctypes.c_size_t) for name in ("peak", "rss", "paged_peak", "paged", "nonpaged_peak", "nonpaged", "pagefile", "pagefile_peak")]]
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    ids, needed = (wintypes.DWORD * 4096)(), wintypes.DWORD()
    if not psapi.EnumProcesses(ids, ctypes.sizeof(ids), ctypes.byref(needed)):
        return {"lmstudio_process_group_rss_mib": None, "lmstudio_process_count": None}
    total, count = 0, 0
    for pid in ids[:needed.value // ctypes.sizeof(wintypes.DWORD)]:
        handle = kernel.OpenProcess(0x1000 | 0x0010, False, pid)
        if not handle:
            continue
        try:
            name, length = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
            if not kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(length)):
                continue
            basename = os.path.basename(name.value).casefold()
            if basename not in {"lm studio.exe", "llama-server.exe", "llmster.exe", "lms.exe"}:
                continue
            counters = Counters()
            counters.cb = ctypes.sizeof(counters)
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                total += counters.rss
                count += 1
        finally:
            kernel.CloseHandle(handle)
    return {"lmstudio_process_group_rss_mib": total / 2**20 if count else None, "lmstudio_process_count": count}


def number_or_none(text):
    try:
        value = float(text.strip())
        return value if finite(value) else None
    except ValueError:
        return None


def device_snapshot():
    begin = time.perf_counter()
    process = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.free,utilization.gpu,temperature.gpu,power.draw", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10)
    if process.returncode:
        raise RuntimeError("GPU observation unavailable")
    values = process.stdout.strip().splitlines()
    if len(values) != 1:
        raise RuntimeError("Single-GPU observation required")
    parts = values[0].split(",")
    if len(parts) != 5:
        raise RuntimeError("Malformed GPU observation")
    row = dict(zip(RESOURCE_FIELDS[:5], map(number_or_none, parts)))
    if row["gpu_memory_used_mib"] is None or row["gpu_memory_free_mib"] is None:
        raise RuntimeError("GPU memory observation unavailable")
    return {"utc": utc_now(), "monotonic_s": time.perf_counter(),
            "sample_acquisition_s": time.perf_counter() - begin, **row, **windows_ram(), **lmstudio_process_rss()}


def summarize_resources(rows):
    out = {"n_samples": len(rows), "scope": "whole_GPU / whole_system_RAM / LM_Studio_named_process_group_RSS; NOT per-model allocation",
           "energy_j": None, "energy_status": "NOT_ESTIMATED_SHORT_REQUESTS_AND_WHOLE_DEVICE_SAMPLING"}
    for field in RESOURCE_FIELDS:
        values = [r[field] for r in rows if finite(r.get(field))]
        out[field + "_peak_sampled"] = max(values) if values else None
        out[field + "_min_sampled"] = min(values) if values else None
    return out


class ResourceSampler:
    def __init__(self, interval_s=.15, sample=device_snapshot):
        self.interval_s, self.sample_fn = interval_s, sample
        self.rows, self.errors = [], []
        self.done, self.tripped = threading.Event(), threading.Event()

    def sample(self):
        try:
            row = self.sample_fn()
            self.rows.append(row)
            if row.get("system_ram_available_gib", 0) < 2 or row.get("gpu_memory_free_mib", 0) < 512:
                self.tripped.set()
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            self.errors.append({"utc": utc_now(), "type": type(exc).__name__})
            self.tripped.set()

    def _loop(self):
        while not self.done.is_set():
            self.sample()
            self.done.wait(self.interval_s)

    def __enter__(self):
        self.sample()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.done.set()
        self.thread.join(timeout=12)
        self.sample()


def safe_record(record):
    """Allowlist prevents exact responses, prompts, headers and event text export."""
    fields = ("task_id", "domain", "kind", "model_key", "block", "request_utc", "end_utc", "latency_s",
              "prompt_sha256", "prompt_bytes", "request_sha256", "stats", "timing", "error",
              "finish_reason", "finish_reason_source", "parse_success", "stream_complete", "resources", "resource_before", "resource_after")
    return {field: record.get(field) for field in fields}
