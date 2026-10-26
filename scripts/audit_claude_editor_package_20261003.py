# SPDX-License-Identifier: Apache-2.0
"""Read-only audit of the private editorial evidence package.

Hashes and historical Git blobs are checked independently of the manifest.
Safety content scanners are shared with the builder. No editor is started and
no package bytes are changed. Receipts expose counts and diagnostic codes only.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("editor_package_safety", ROOT / "scripts/build_claude_editor_package_20261003.py")
SAFETY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SAFETY)
ARCHIVE = "final_model_table_before_status_aliases.csv"
REQUIRED_CLI = {"results/20261003_cli_products/summary.json", "results/20261003_cli_products/effort_summary.json"}
REQUIRED_ROLES = {"manuscript": 2, "bibliography": 1, "bibliography_addendum": 1,
                  "limitations": 1, "provenance": 1, "systems_summary": 1,
                  "systems_table": 1, "study_c_summary": 1, "cli_aggregate": 2,
                  "editor_instructions": 2, "historical_provenance": 1}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def history_bytes(root: Path, revision: str, source: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), "show", revision + ":" + source],
                            capture_output=True, check=True)
    return result.stdout


def relative_safe(root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("unsafe relative path")
    part = Path(value)
    if part.is_absolute() or part.as_posix() != value:
        raise ValueError("unsafe relative path")
    path = SAFETY.safe_path(root, part)
    for segment in (root, *path.parents):
        if segment == root.parent:
            break
        if hasattr(segment, "is_junction") and segment.is_junction():
            raise ValueError("junction not allowed")
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        raise ValueError("link not allowed")
    return path


def role_allowed(row: dict) -> bool:
    source, target, role = row["source"], row["path"], row["role"]
    path = Path(source)
    if role == "manuscript":
        return source in SAFETY.MANUSCRIPTS and target == source and row["status"] == "HISTORICAL"
    if role == "bibliography":
        return source == "docs/VERIFIED_BIBLIOGRAPHY_20261003_RU.md" and target == "references/VERIFIED_BIBLIOGRAPHY_20261003_RU.md"
    if role == "bibliography_addendum":
        return source == "docs/VERIFIED_RESOURCE_BIBLIOGRAPHY_20261003_RU.md" and target == "references/VERIFIED_RESOURCE_BIBLIOGRAPHY_20261003_RU.md"
    if role == "limitations":
        return path.parent.as_posix() == "docs" and path.suffix == ".md" and target == "LIMITATIONS.md"
    if role == "provenance":
        return path.parent.as_posix() == "manuscript" and path.name.startswith("CLAIM_PROVENANCE") and path.suffix == ".json" and target == "provenance/CLAIM_PROVENANCE_SUMMARY.json"
    if role == "historical_provenance":
        return source == SAFETY.HISTORICAL_SOURCE and target == "provenance/HISTORICAL_CLAIM_PROVENANCE_SUMMARY.json" and row["status"] == "HISTORICAL"
    if role == "dev_table":
        return path.parent.as_posix() == "results/20261003_resource_analysis" and path.suffix == ".csv" and path.name != ARCHIVE and target == "tables/dev/" + path.name
    if role == "systems_summary":
        return path.parts[0] == "results" and path.name == "systems_summary.json" and target == "summaries/systems_summary.json" and row["status"] == "SYSTEMS_TELEMETRY"
    if role == "systems_table":
        return path.parts[0] == "results" and path.name == "telemetry_table.csv" and target == "tables/systems/telemetry_table.csv" and row["status"] == "SYSTEMS_TELEMETRY"
    if role == "study_c_summary":
        return path.parts[0] == "results" and path.name == "study_c_corrected_aggregate.json" and target == "summaries/study_c_summary.json" and row["status"] == "DEV"
    if role == "cli_aggregate":
        return source in REQUIRED_CLI and re.fullmatch(r"summaries/product_0[12]_" + re.escape(path.name), target) is not None and row["status"] == "SUPPLEMENTARY"
    if role == "figure":
        if path.suffix not in {".png", ".svg"}:
            return False
        if path.parent.as_posix() == "manuscript/figures":
            return path.stem == "historical_noninferiority_20261002" and target == "figures/" + path.name and row["status"] == "HISTORICAL"
        if path.parent.as_posix() == "results/20261003_resource_analysis":
            return target == "figures/dev_" + path.name and row["status"] == "DEV"
        return path.parts[0] == "results" and target == "figures/systems_" + path.name and row["status"] == "SYSTEMS_TELEMETRY"
    if role == "editor_instructions":
        return source == "scripts/build_claude_editor_package_20261003.py" and target in {"AUTHORS_AND_STYLE.md", "README.md"} and row["status"] == "SUPPLEMENTARY"
    return False


def audit_package(root: Path, package: str | Path, *, read_history=history_bytes) -> dict:
    root = root.resolve()
    failures = []
    def fail(code, index=None):
        failures.append({"code": code, **({"file_index": index} if index is not None else {})})

    try:
        directory = SAFETY.safe_path(root, package)
        if directory.relative_to(root).parts[0] != "outputs":
            raise ValueError("package must be in outputs")
        manifest_path = relative_safe(directory, "PACKAGE_MANIFEST.json")
        manifest_bytes = manifest_path.read_bytes()
        SAFETY.validate_content(manifest_path, manifest_bytes)
        manifest = json.loads(manifest_bytes)
    except (OSError, ValueError, UnicodeError, KeyError, IndexError):
        return {"schema_version": 1, "valid": False, "checked_files": 0,
                "errors": [{"code": "MANIFEST_UNREADABLE_OR_UNSAFE"}]}
    revision = manifest.get("assembly_head", "")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        fail("ASSEMBLY_SHA_INVALID")
    expected_flags = {"package_status": "PRIVATE_EDITORIAL_EVIDENCE_ONLY", "claude_editing_run": False,
                      "numbers_must_not_change": True, "historical_manuscripts_unchanged": True,
                      "latest_appendices_are_authority": True}
    if any(type(manifest.get(key)) is not type(value) or manifest.get(key) != value for key, value in expected_flags.items()):
        fail("EDITORIAL_FLAGS_INVALID")
    rows = manifest.get("files")
    if not isinstance(rows, list) or not rows:
        rows = []
        fail("EMPTY_MANIFEST")
    roles, cli_sources, declared, checked, historical, claims_count = Counter(), set(), set(), 0, 0, 0
    historical_claims_count = 0
    systems_sources = set()
    for index, row in enumerate(rows):
        try:
            if not isinstance(row, dict) or row.get("status") not in SAFETY.STATUSES or not role_allowed(row):
                fail("ROLE_ALLOWLIST_OR_STATUS_INVALID", index)
                continue
            source = relative_safe(root, row["source"])
            target = relative_safe(directory, row["path"])
            if target.suffix not in {".md", ".csv", ".json", ".png", ".svg"} or SAFETY.FORBIDDEN_NAMES.search(target.name):
                fail("UNSAFE_FILE_KIND", index)
                continue
            if row["path"] in declared:
                fail("DUPLICATE_MANIFEST_PATH", index)
            declared.add(row["path"])
            roles[row["role"]] += 1
            data = target.read_bytes()
            SAFETY.validate_content(target, data)
            if row.get("source_commit") != revision:
                fail("ASSEMBLY_SHA_MISMATCH", index)
            if type(row.get("bytes")) is not int or row["bytes"] != len(data) or row.get("copied_sha256") != sha256(data):
                fail("COPIED_HASH_OR_SIZE_MISMATCH", index)
            mode = row.get("copy_mode")
            if row["role"] == "editor_instructions":
                if mode != "GENERATED_INSTRUCTIONS" or row.get("source_sha256") is not None:
                    fail("GENERATED_INSTRUCTION_IDENTITY_INVALID", index)
            else:
                source_data = source.read_bytes()
                SAFETY.validate_content(source, source_data)
                if row.get("source_sha256") != sha256(source_data):
                    fail("SOURCE_HASH_MISMATCH", index)
                if row["role"] == "provenance":
                    source_claims = json.loads(source_data).get("claims", [])
                    projected = [{key: value for key, value in claim.items() if key in SAFETY.CLAIM_FIELDS} for claim in source_claims]
                    expected = {"schema_version": 1, "purpose": "EDITORIAL_ONLY_DO_NOT_CHANGE_NUMBERS", "claims": projected}
                    expected_bytes = (json.dumps(expected, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
                    if mode != "PROJECTION_NUMBERS_UNCHANGED" or data != expected_bytes:
                        fail("PROVENANCE_PROJECTION_CHANGED", index)
                    claims_count = len(projected)
                elif row["role"] == "historical_provenance":
                    source_json = json.loads(source_data)
                    copy_json = json.loads(data)
                    if mode != "PROJECTION_NUMBERS_UNCHANGED" or set(copy_json) != {"schema_version", "purpose", "status", "source_register", "key_claims", "derived_claims", "limitations"}:
                        fail("HISTORICAL_PROJECTION_SHAPE_CHANGED", index)
                    if copy_json.get("status") != "HISTORICAL" or copy_json.get("purpose") != "HISTORICAL_HOME150_EDITORIAL_ONLY_DO_NOT_CHANGE_NUMBERS":
                        fail("HISTORICAL_PROJECTION_STATUS_CHANGED", index)
                    expected_register = {identifier: {key: value for key, value in source_json["source_register"][identifier].items() if key in SAFETY.HISTORICAL_SOURCE_FIELDS}
                                         for identifier in sorted(SAFETY.HISTORICAL_IDS)}
                    if json.dumps(copy_json.get("source_register"), sort_keys=True) != json.dumps(expected_register, sort_keys=True):
                        fail("HISTORICAL_SOURCE_REFERENCES_CHANGED", index)
                    for group, fields in (("key_claims", SAFETY.HISTORICAL_KEY_FIELDS), ("derived_claims", SAFETY.HISTORICAL_DERIVED_FIELDS)):
                        selected = [claim for claim in source_json[group] if str(claim.get("claim_id", "")).startswith("home150_")
                                    and (group == "derived_claims" or claim.get("source_id") in {"home150", "home_manifest"})]
                        expected_rows = [{**{key: value for key, value in claim.items() if key in fields}, "status": "HISTORICAL"} for claim in selected]
                        if json.dumps(copy_json.get(group), sort_keys=True) != json.dumps(expected_rows, sort_keys=True):
                            fail("HISTORICAL_NUMBERS_OR_CLAIMS_CHANGED", index)
                        historical_claims_count += len(expected_rows)
                elif mode != "BYTE_FOR_BYTE" or data != source_data:
                    fail("BYTE_COPY_CHANGED", index)
            if row["role"] == "manuscript":
                try:
                    if data != read_history(root, revision, row["source"]):
                        fail("HISTORICAL_GIT_COPY_CHANGED", index)
                    else:
                        historical += 1
                except (OSError, subprocess.SubprocessError, ValueError):
                    fail("HISTORICAL_GIT_BLOB_UNAVAILABLE", index)
            if row["role"] in {"systems_summary", "systems_table", "study_c_summary"}:
                systems_sources.add(source.parent)
            if row["role"] == "cli_aggregate":
                cli_sources.add(row["source"])
            if row["source"].endswith("final_model_table.csv") and row["status"] != "SUPPLEMENTARY":
                fail("MIXED_FINAL_TABLE_MISCLASSIFIED", index)
            checked += 1
        except (OSError, ValueError, UnicodeError, KeyError, TypeError, IndexError, AttributeError):
            fail("FILE_UNREADABLE_OR_UNSAFE", index)
    for role, count in REQUIRED_ROLES.items():
        if roles[role] != count:
            fail("REQUIRED_ROLE_COUNT_INVALID")
    if cli_sources != REQUIRED_CLI:
        fail("CLI_SUMMARIES_INCOMPLETE")
    if len(systems_sources) != 1:
        fail("SYSTEMS_SOURCES_NOT_ONE_RUN")
    if "tables/dev/final_model_table.csv" not in declared:
        fail("FINAL_TABLE_MISSING")
    actual = set()
    try:
        for path in directory.rglob("*"):
            relative_safe(directory, path.relative_to(directory).as_posix())
            if path.is_file():
                actual.add(path.relative_to(directory).as_posix())
        if actual != declared | {"PACKAGE_MANIFEST.json"}:
            fail("UNDECLARED_OR_MISSING_PACKAGE_FILES")
        styles = (directory / "AUTHORS_AND_STYLE.md").read_text(encoding="utf-8")
        readme = (directory / "README.md").read_text(encoding="utf-8")
        if any(text not in styles for text in ("DO NOT CHANGE NUMBERS", "Antoniy Sarychev", "Denis Shesternin", "have not yet been updated")) or "DO NOT CHANGE NUMBERS" not in readme:
            fail("AUTHOR_OR_EDITOR_INSTRUCTIONS_MISSING")
    except (OSError, ValueError, UnicodeError):
        fail("PACKAGE_INVENTORY_OR_INSTRUCTIONS_UNSAFE")
    return {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
            "audit_status": "INDEPENDENT_STRUCTURE_HASH_HISTORY_QA_SHARED_SAFETY_SCANNERS",
            "valid": not failures, "assembly_head": revision if re.fullmatch(r"[0-9a-f]{40}", str(revision)) else None,
            "manifest_sha256": sha256(manifest_bytes), "declared_files": len(rows), "checked_files": checked,
            "historical_git_copies_verified": historical, "provenance_claims": claims_count,
            "historical_aggregate_claims": historical_claims_count,
            "cli_aggregate_count": roles["cli_aggregate"], "role_counts": dict(roles),
            "claude_editing_run": False, "package_mutations": 0,
            "scope_limitations": ["Structural/content safety checks do not certify every free-text sentence against all possible benchmark corpora.",
                                  "Assembly HEAD identifies packaging context; working source bytes are separately bound by SHA256."],
            "errors": failures}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--package", default="outputs/claude_paper_editor_package")
    parser.add_argument("--receipt", help="New results JSON receipt; existing files are preserved")
    args = parser.parse_args()
    receipt = audit_package(args.root, args.package)
    if args.receipt:
        try:
            target = relative_safe(args.root.resolve(), args.receipt)
            if target.relative_to(args.root.resolve()).parts[0] != "results" or target.suffix != ".json" or target.exists():
                raise ValueError("New safe results receipt required")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except (ValueError, OSError):
            print(json.dumps({"valid": False, "errors": [{"code": "UNSAFE_OR_EXISTING_RECEIPT"}]}))
            return 2
    print(json.dumps(receipt, ensure_ascii=True))
    return 0 if receipt["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
