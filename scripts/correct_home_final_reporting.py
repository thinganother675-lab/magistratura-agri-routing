"""Nonfrozen reporting correction, with no inference and no source mutation.

The frozen analyzer's ask_coverage counts the shorthand ASK, while the original
model/output contract uses ASK_FOR_DATA. Preserve statistics.json byte-for-byte,
change only summary.<policy>.ask_coverage, and save separate provenance/diff.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


METHODS = {"local", "cloud", "tool_cloud", "hybrid", "offline"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def correct_ask_reporting(report):
    """Return a copy and exact field diff; criterion/scoring fields are untouched."""
    summaries = report.get("summary")
    if not isinstance(summaries, dict) or set(summaries) != METHODS:
        raise ValueError("Expected the five frozen policy summaries")
    corrected, changes = copy.deepcopy(report), []
    for method, row in summaries.items():
        n = row.get("measured_n")
        actions = row.get("action_counts")
        if type(n) is not int or n < 0 or not isinstance(actions, dict):
            raise ValueError("Measured count and action counts must be explicit")
        if any(type(value) is not int or value < 0 for value in actions.values()) or sum(actions.values()) != n:
            raise ValueError("Action counts must cover exactly the measured decisions")
        if "ask_coverage" not in row:
            raise ValueError("Expected the frozen ask_coverage field")
        value = actions.get("ASK_FOR_DATA", 0) / n if n else None
        corrected["summary"][method]["ask_coverage"] = value
        if value != row["ask_coverage"]:
            changes.append({"path": "summary." + method + ".ask_coverage",
                            "before": row["ask_coverage"], "after": value})
    return corrected, changes


def save_correction(source, output=None):
    source = Path(source).resolve()
    output = Path(output).resolve() if output else source.with_name("statistics_reporting_corrected.json")
    report = json.loads(source.read_text(encoding="utf-8-sig"))
    if "reporting_correction" in report:
        raise ValueError("Source already contains a reporting correction")
    corrected, changes = correct_ask_reporting(report)
    corrected["reporting_correction"] = {
        "status": "NONFROZEN_REPORTING_LABEL_CORRECTION",
        "reason": "Frozen analyzer used ASK; unchanged output contract uses ASK_FOR_DATA",
        "source_filename": source.name, "source_sha256": sha(source),
        "helper_sha256": sha(Path(__file__)), "created_utc": datetime.now(timezone.utc).isoformat(),
        "changed_fields": changes,
        "correction_rule": "action_counts.ASK_FOR_DATA / measured_n; no measured decisions => null",
        "preservation": "All preexisting fields except summary.<policy>.ask_coverage are unchanged; original statistics.json is immutable; no model reruns, scoring or criterion changes",
    }
    with output.open("x", encoding="utf-8") as stream:
        json.dump(corrected, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print("REPORTING_CORRECTION " + str(output))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("statistics", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    save_correction(arguments.statistics, arguments.output)
