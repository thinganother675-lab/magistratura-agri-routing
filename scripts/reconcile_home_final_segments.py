"""Append-only validation/analysis input for an interrupted HOME final run.

No provider calls or scientific changes: finished attempts, frozen scores and
the unique sample-policy union are audited before any combined input is saved.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import uuid


ROOT = Path(__file__).resolve().parents[1]
METHODS = ("local", "cloud", "tool_cloud", "hybrid", "offline")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verified_protocol_bytes(path, expected):
    """Accept exact frozen bytes or the proven Windows CRLF serialization only."""
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() == expected:
        return raw
    normalized = raw.replace(b"\r\n", b"\n")
    if hashlib.sha256(normalized).hexdigest() != expected:
        raise ValueError("Frozen protocol copy or hash differs beyond CRLF/LF serialization")
    return normalized


def relative(path):
    path = Path(path).resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def project_path(value):
    if not isinstance(value, str) or Path(value).is_absolute():
        raise ValueError("Frozen project path must be relative")
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("Frozen project path escapes project")
    return path


def analyzer():
    spec = importlib.util.spec_from_file_location("frozen_home_segment_analysis", ROOT / "scripts/analyze_home_final.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frozen_samples(directory):
    protocol_file = directory / "protocol_copy.json"
    protocol, manifest = read(protocol_file), read(directory / "manifest.json")
    if protocol.get("status") != "FROZEN":
        raise ValueError("Frozen protocol copy or hash differs")
    verified_protocol_bytes(protocol_file, manifest.get("protocol_sha256"))
    dataset = project_path(protocol["dataset_path"])
    if sha(dataset) != protocol.get("dataset_sha256") or sha(dataset) != manifest.get("dataset_sha256"):
        raise ValueError("Frozen dataset hash differs")
    for path, expected in protocol.get("code_sha256", {}).items():
        if sha(project_path(path)) != expected:
            raise ValueError("Frozen scientific source hash differs")
    samples = jsonl(dataset)
    if protocol.get("n") != len(samples) or protocol.get("holdout_ids") != [row["id"] for row in samples]:
        raise ValueError("Frozen target IDs differ")
    return protocol, samples


def resource_summary(directory, manifest):
    rows = read(directory / "resources.json") if (directory / "resources.json").exists() else []
    persisted = manifest.get("resource_summary") or {}
    return {"vram_mib_peak_sampled_total": max((row["vram_mib_total"] for row in rows), default=None),
            "ram_gib_peak_sampled_system_used": max((row["ram_gib_system_used"] for row in rows), default=None),
            "samples": len(rows), "first_sample_utc": rows[0]["utc"] if rows else None,
            "last_sample_utc": rows[-1]["utc"] if rows else None,
            "resource_scope": "entire GPU / entire system; sampled about every 0.5s plus subprocess overhead",
            "resource_poll_errors": persisted.get("resource_poll_errors"),
            "poll_error_log_status": "KNOWN" if "resource_poll_errors" in persisted else "UNKNOWN: not persisted in interrupted manifest"}


def inspect_segment(directory):
    directory = Path(directory).resolve()
    protocol, samples = frozen_samples(directory)
    manifest = read(directory / "manifest.json")
    rows = jsonl(directory / "raw_decisions.jsonl")
    analyzer().validate_records(rows, samples)
    if any(row["result"]["status"] != "MEASURED" for row in rows):
        raise ValueError("Segment contains NOT_RUN decisions; do not claim the complete measured union")
    raw_order = [(row["sample"]["id"], row["method"]) for row in rows]
    row_keys = set(raw_order)
    schedule = read(directory / "schedule.json")
    if ([entry["sample_id"] for entry in schedule] != [sample["id"] for sample in samples]
            or any(len(entry["methods"]) != len(METHODS) or set(entry["methods"]) != set(METHODS) for entry in schedule)):
        raise ValueError("Full execution schedule differs from frozen IDs or policies")
    full_order = [(entry["sample_id"], method) for entry in schedule for method in entry["methods"]]
    first_position = full_order.index(raw_order[0]) if raw_order else 0
    if first_position % len(METHODS) or len(rows) % len(METHODS) or raw_order != full_order[first_position:first_position + len(rows)]:
        raise ValueError("Segment must contain complete cases in the original interleaved order")
    trace_counts = Counter((row["sample"]["id"], row["method"], trace["provider"])
                           for row in rows for trace in row["result"].get("trace", []))
    traces_by_key = defaultdict(list)
    for row in rows:
        for trace in row["result"].get("trace", []):
            traces_by_key[(row["sample"]["id"], row["method"], trace["provider"])].append(trace)
    started, finished = {}, {}
    for event in jsonl(directory / "attempts.jsonl"):
        if event.get("event") not in ("call_started", "call_finished"):
            raise ValueError("Unexpected attempt log event")
        key = (event.get("provider"), event.get("sample_id"), event.get("method"), event.get("attempt_number_provider"))
        if key[0] not in ("local", "cloud") or (key[1], key[2]) not in row_keys or type(key[3]) is not int or key[3] <= 0:
            raise ValueError("Attempt is outside saved unique policy decisions")
        target = started if event["event"] == "call_started" else finished
        if key in target:
            raise ValueError("Duplicate attempt log event")
        target[key] = event
    if set(started) != set(finished):
        raise ValueError("Unfinished or unstarted attempts: no safe manual union")
    attempt_counts = Counter((sid, method, provider) for provider, sid, method, number in started)
    if attempt_counts != trace_counts:
        raise ValueError("Attempt counts and raw decision provider traces differ")
    calls = Counter(key[0] for key in started)
    cumulative = manifest.get("call_counter_scope") == "cumulative_original_plus_continuation"
    baseline = manifest.get("original_call_baseline", {}) if cumulative else {"local": 0, "cloud": 0}
    for provider in ("local", "cloud"):
        if type(baseline.get(provider)) is not int or baseline[provider] < 0:
            raise ValueError("Explicit cumulative attempt baseline required")
        numbers = sorted(key[3] for key in started if key[0] == provider)
        if numbers != list(range(baseline[provider] + 1, baseline[provider] + calls[provider] + 1)):
            raise ValueError("Provider attempt numbers must form the exact unrepeated segment range")
        if manifest.get(provider + "_calls_actual") != baseline[provider] + calls[provider]:
            raise ValueError("Manifest attempt counter differs from finished HTTP attempt log")
    for key, traces in traces_by_key.items():
        sid, method, provider = key
        events = sorted((value for event_key, value in finished.items() if event_key[:3] == (provider, sid, method)),
                        key=lambda value: value["attempt_number_provider"])
        if any(trace.get("error") != event.get("error") or trace.get("cost_usd") != event.get("cost_usd")
               for trace, event in zip(traces, events)):
            raise ValueError("Finished attempt errors/costs differ from raw trace evidence")
    files = ("manifest.json", "protocol_copy.json", "raw_decisions.jsonl", "attempts.jsonl", "schedule.json", "resources.json")
    hashes = {name: sha(directory / name) for name in files if (directory / name).exists()}
    if (directory / "manifest.tmp").exists():
        hashes["manifest.tmp"] = sha(directory / "manifest.tmp")
    summary = {"run": relative(directory), "manifest_state": manifest.get("state"),
               "raw_rows": len(rows), "unique_sample_policy_pairs": len(row_keys),
               "first_sample_index": first_position // len(METHODS), "complete_sample_cases": len(rows) // len(METHODS),
               "measured_cases_by_policy": dict(Counter(row["method"] for row in rows)),
               "finished_calls": {provider: calls[provider] for provider in ("local", "cloud")},
               "attempt_baseline": baseline, "all_started_attempts_finished": True,
               "source_sha256": hashes, "resource_summary": resource_summary(directory, manifest),
               "protocol_serialization": {"raw_copy_sha256": hashes["protocol_copy.json"],
                                          "frozen_protocol_sha256": manifest["protocol_sha256"],
                                          "exact_raw_copy": hashes["protocol_copy.json"] == manifest["protocol_sha256"],
                                          "normalized_copy_sha256": hashlib.sha256(verified_protocol_bytes(directory / "protocol_copy.json", manifest["protocol_sha256"])).hexdigest(),
                                          "scope": "Only proven CRLF to LF serialization is accepted; all frozen JSON content remains byte-identical after newline normalization"},
               "cold_load_wall_s": (manifest.get("local_load_metadata") or {}).get("cold_load_wall_s"),
               "started_utc": manifest.get("started_utc"), "finished_utc": manifest.get("finished_utc"),
               "local_load_metadata": manifest.get("local_load_metadata"),
               "segment_manifest_fields": {key: value for key, value in manifest.items()
                                           if key in ("phase", "summary", "completed_sample_groups", "filesystem_only_replace_retry_deadline_s")
                                           or key.startswith(("segment_", "completed_segment_", "original_", "remaining_", "target_segment_"))},
               "manifest_tmp_is_evidence_only": "Any stale .tmp counter is excluded; only matching finished HTTP events and raw traces establish incurred calls"}
    return summary, rows, manifest, protocol, samples


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def write_audit(directory, output=None):
    summary, *_ = inspect_segment(directory)
    directory = Path(directory).resolve()
    output = Path(output).resolve() if output else directory.parent / ("reconciliation_segment_audit_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ_") + uuid.uuid4().hex[:8] + ".json")
    if output.is_relative_to(directory):
        raise ValueError("Reconciliation audit must stay outside immutable original directory")
    write_new(output, {"status": "APPEND_ONLY_SEGMENT_EVIDENCE", "created_utc": datetime.now(timezone.utc).isoformat(),
                       "helper_sha256": sha(Path(__file__)), **summary})
    print("SEGMENT_AUDIT " + str(output))
    return output


def reconcile(original, continuation, output):
    left, rows_a, manifest_a, protocol_a, samples = inspect_segment(original)
    right, rows_b, manifest_b, protocol_b, samples_b = inspect_segment(continuation)
    if manifest_a["protocol_sha256"] != manifest_b["protocol_sha256"] or protocol_a != protocol_b or samples != samples_b:
        raise ValueError("Segment frozen protocol copies differ")
    if manifest_b.get("state") not in ("completed", "completed_with_errors"):
        raise ValueError("Wait for terminal continuation state")
    if right["attempt_baseline"] != left["finished_calls"]:
        raise ValueError("Continuation attempt baseline differs from original finished calls")
    rows = rows_a + rows_b
    decisions, _ = analyzer().validate_records(rows, samples)
    if any(len(decisions[method]) != len(samples) for method in METHODS) or len(rows) != len(samples) * len(METHODS):
        raise ValueError("Union must cover each frozen sample-policy pair exactly once")
    schedule_a, schedule_b = read(Path(original) / "schedule.json"), read(Path(continuation) / "schedule.json")
    if schedule_a != schedule_b:
        raise ValueError("Frozen full execution schedules differ")
    expected_order = [(entry["sample_id"], method) for entry in schedule_a for method in entry["methods"]]
    if [(row["sample"]["id"], row["method"]) for row in rows] != expected_order:
        raise ValueError("Segment union must preserve the original interleaved execution order")
    resources = [left["resource_summary"], right["resource_summary"]]
    maxima = lambda key: max((r[key] for r in resources if r[key] is not None), default=None)
    known_poll_errors = all(r["resource_poll_errors"] is not None for r in resources)
    summary = {"vram_mib_peak_sampled_total": maxima("vram_mib_peak_sampled_total"),
               "ram_gib_peak_sampled_system_used": maxima("ram_gib_peak_sampled_system_used"),
               "samples": sum(r["samples"] for r in resources),
               "resource_scope": "sampled total peaks across two execution segments; entire GPU/system, not private allocation",
               "resource_poll_errors": [error for r in resources for error in r["resource_poll_errors"]] if known_poll_errors else None,
               "poll_error_log_status": "KNOWN" if known_poll_errors else "UNKNOWN: interrupted original error log unavailable"}
    gap = None
    if resources[0]["last_sample_utc"] and resources[1]["first_sample_utc"]:
        gap = (datetime.fromisoformat(resources[1]["first_sample_utc"]) - datetime.fromisoformat(resources[0]["last_sample_utc"])).total_seconds()
    manifest = copy.deepcopy(manifest_b)
    for key in list(manifest):
        if key in ("summary", "completed_sample_groups", "filesystem_only_replace_retry_deadline_s") or key.startswith(("segment_", "completed_segment_", "original_", "remaining_", "target_segment_")):
            del manifest[key]
    manifest.update(run_id="HOME_FINAL_MANUALLY_RECONCILED_" + uuid.uuid4().hex[:8], phase="HOME_FINAL_RECONCILED",
                    state="completed_with_errors" if any(trace.get("error") for row in rows for trace in row["result"].get("trace", [])) else "completed",
                    target_n=len(samples), holdout_ids=[s["id"] for s in samples], policies=list(METHODS),
                    total_completed_cases=len(samples), total_unique_policy_decisions=len(rows),
                    authoritative_statistics={"source": "frozen analyzer output statistics.json in the new analysis_* directory",
                                              "scope": "exact union of all frozen sample-policy decisions",
                                              "inherited_segment_summary": "omitted; segment-only summary is preserved within segment_metadata"},
                    cloud_calls_actual=left["finished_calls"]["cloud"] + right["finished_calls"]["cloud"],
                    local_calls_actual=left["finished_calls"]["local"] + right["finished_calls"]["local"],
                    call_counter_scope="reconciled_unique_all_target", resource_summary=summary,
                    started_utc=manifest_a.get("started_utc"), segment_metadata=[left, right],
                    continuation_deviation="Filesystem interruption after original decisions; explicit manual continuation of remaining cases in new segment, no policy output or HTTP call replay; original frozen protocol/data/scoring retained",
                    interruption_gap_sampled_s=gap, cold_load_count=2,
                    request_latency_scope="Actual per-decision end-to-end timers; exclude both cold loads and interruption gap, separately documented",
                    reconciliation={"helper_sha256": sha(Path(__file__)), "created_utc": datetime.now(timezone.utc).isoformat(),
                                    "original_rows": len(rows_a), "continuation_rows": len(rows_b), "union_rows": len(rows),
                                    "unique_union_pairs": len(rows), "scores_recomputed_and_matched": True,
                                    "source_files_immutable": True, "source_sha256": [left["source_sha256"], right["source_sha256"]]})
    if isinstance(manifest.get("local_load_metadata"), dict):
        manifest["local_load_metadata"]["metadata_scope"] = "continuation load only; both cold loads are preserved in segment_metadata"
    output = Path(output).resolve()
    if output.is_relative_to(Path(original).resolve()) or output.is_relative_to(Path(continuation).resolve()):
        raise ValueError("Combined analysis input must stay outside immutable source directories")
    output.mkdir(exist_ok=False)
    write_new(output / "manifest.json", manifest)
    (output / "protocol_copy.json").write_bytes(verified_protocol_bytes(Path(original) / "protocol_copy.json", manifest_a["protocol_sha256"]))
    (output / "raw_decisions.jsonl").write_bytes((Path(original) / "raw_decisions.jsonl").read_bytes().rstrip(b"\r\n") + b"\n" + (Path(continuation) / "raw_decisions.jsonl").read_bytes())
    write_new(output / "reconciliation.json", manifest["reconciliation"] | {"segment_metadata": [left, right]})
    print("RECONCILED_INPUT " + str(output))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("original", type=Path)
    parser.add_argument("continuation", type=Path, nargs="?")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.continuation:
        if not args.output:
            parser.error("--output is required for the append-only combined input")
        reconcile(args.original, args.continuation, args.output)
    else:
        write_audit(args.original, args.output)
