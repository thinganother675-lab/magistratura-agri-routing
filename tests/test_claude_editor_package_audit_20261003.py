# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


AUDIT = module("editor_independent_audit", "scripts/audit_claude_editor_package_20261003.py")
BUILDER = AUDIT.SAFETY
FIXTURES = module("editor_audit_builder_fixture", "tests/test_claude_editor_package_20261003.py")


def prepared(root):
    config = FIXTURES.fixture(root)
    FIXTURES.historical_fixture(root)
    config["cli_aggregates"] = tuple(sorted(AUDIT.REQUIRED_CLI))
    for source in config["cli_aggregates"]:
        FIXTURES.write(root, source, '{"status":"SUPPLEMENTARY","n":60,"private_test_run":false}\n')
    config["bibliography_addendum"] = "docs/VERIFIED_RESOURCE_BIBLIOGRAPHY_20261003_RU.md"
    FIXTURES.write(root, config["bibliography_addendum"], "Verified synthetic resource references.\n")
    config["study_c_summary"] = "results/20261003_systems_fixture/study_c_corrected_aggregate.json"
    FIXTURES.write(root, config["study_c_summary"], '{"classification":"DEV","numeric_correct":6,"corrected":true}\n')
    FIXTURES.write(root, "results/20261003_resource_analysis/final_model_table.csv",
                   "model,quality_status,latency_status\nsynthetic,DEV,SYSTEMS_TELEMETRY\n")
    BUILDER.build_package(root, **config)
    return root / config["output"]


def read_history(root, revision, source):
    assert revision == "a" * 40
    return (root / source).read_bytes()


def receipt(root, package):
    return AUDIT.audit_package(root, package, read_history=read_history)


def change_manifest(package, update):
    target = package / "PACKAGE_MANIFEST.json"
    manifest = json.loads(target.read_text(encoding="utf-8"))
    update(manifest)
    target.write_text(json.dumps(manifest), encoding="utf-8")


def test_complete_package_has_verified_hashes_historical_copies_and_both_cli_summaries(tmp_path):
    package = prepared(tmp_path)
    result = receipt(tmp_path, package)
    assert result["valid"] and result["errors"] == []
    assert result["historical_git_copies_verified"] == 2
    assert result["provenance_claims"] == 1 and result["cli_aggregate_count"] == 2
    assert result["historical_aggregate_claims"] == 2
    assert result["checked_files"] == result["declared_files"]
    assert result["package_mutations"] == 0


def test_changed_copy_fails_hash_and_byte_comparison(tmp_path):
    package = prepared(tmp_path)
    (package / "tables/dev/final_model_table.csv").write_text("model,latency_s\nsynthetic,999\n")
    result = receipt(tmp_path, package)
    codes = {item["code"] for item in result["errors"]}
    assert not result["valid"] and {"COPIED_HASH_OR_SIZE_MISMATCH", "BYTE_COPY_CHANGED"} <= codes


def test_archive_added_to_manifest_is_rejected_even_with_correct_hash(tmp_path):
    package = prepared(tmp_path)
    source = FIXTURES.write(tmp_path, "results/20261003_resource_analysis/" + AUDIT.ARCHIVE, "model,EM\nsynthetic,0.5\n")
    target = "tables/dev/" + AUDIT.ARCHIVE
    (package / target).write_bytes(source.read_bytes())
    def update(manifest):
        row = next(row for row in manifest["files"] if row["role"] == "dev_table").copy()
        row.update(source=source.relative_to(tmp_path).as_posix(), path=target,
                   bytes=len(source.read_bytes()), source_sha256=AUDIT.sha256(source.read_bytes()),
                   copied_sha256=AUDIT.sha256(source.read_bytes()))
        manifest["files"].append(row)
    change_manifest(package, update)
    assert any(error["code"] == "ROLE_ALLOWLIST_OR_STATUS_INVALID" for error in receipt(tmp_path, package)["errors"])


def test_undeclared_raw_file_cannot_hide_outside_manifest(tmp_path):
    package = prepared(tmp_path)
    (package / "raw.jsonl").write_text('{"question":"synthetic only"}\n')
    assert any(error["code"] == "UNDECLARED_OR_MISSING_PACKAGE_FILES" for error in receipt(tmp_path, package)["errors"])


def test_changed_historical_git_blob_detected(tmp_path):
    package = prepared(tmp_path)
    result = AUDIT.audit_package(tmp_path, package, read_history=lambda *args: b"original historical synthetic bytes")
    assert not result["valid"] and result["historical_git_copies_verified"] == 0
    assert sum(error["code"] == "HISTORICAL_GIT_COPY_CHANGED" for error in result["errors"]) == 2


def test_provenance_number_tamper_detected_even_when_copied_hash_updated(tmp_path):
    package = prepared(tmp_path)
    path = package / "provenance/CLAIM_PROVENANCE_SUMMARY.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["claims"][0]["value"] = 123
    path.write_text(json.dumps(data), encoding="utf-8")
    def update(manifest):
        row = next(row for row in manifest["files"] if row["role"] == "provenance")
        row.update(bytes=len(path.read_bytes()), copied_sha256=AUDIT.sha256(path.read_bytes()))
    change_manifest(package, update)
    assert any(error["code"] == "PROVENANCE_PROJECTION_CHANGED" for error in receipt(tmp_path, package)["errors"])


def test_historical_number_tamper_detected_even_with_manifest_hash_updated(tmp_path):
    package = prepared(tmp_path)
    path = package / "provenance/HISTORICAL_CLAIM_PROVENANCE_SUMMARY.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["key_claims"][0]["value"] = 999
    path.write_text(json.dumps(data), encoding="utf-8")
    def update(manifest):
        row = next(row for row in manifest["files"] if row["role"] == "historical_provenance")
        row.update(bytes=len(path.read_bytes()), copied_sha256=AUDIT.sha256(path.read_bytes()))
    change_manifest(package, update)
    assert any(error["code"] == "HISTORICAL_NUMBERS_OR_CLAIMS_CHANGED" for error in receipt(tmp_path, package)["errors"])


@pytest.mark.parametrize("key", ["question", "correct_answer", "response_text", "api_key"])
def test_sensitive_package_field_is_blocked_without_value_in_receipt(tmp_path, key):
    package = prepared(tmp_path)
    sentinel = "SYNTHETIC_PRIVATE_SENTINEL"
    path = package / "summaries/product_01_effort_summary.json"
    path.write_text(json.dumps({key: sentinel}), encoding="utf-8")
    result = receipt(tmp_path, package)
    assert not result["valid"] and sentinel not in json.dumps(result)


def test_uncorrected_study_c_source_rejected(tmp_path):
    package = prepared(tmp_path)
    def update(manifest):
        row = next(row for row in manifest["files"] if row["role"] == "study_c_summary")
        row["source"] = row["source"].replace("study_c_corrected_aggregate.json", "study_c_summary.json")
    change_manifest(package, update)
    assert not receipt(tmp_path, package)["valid"]


def test_missing_product_summary_is_not_a_complete_evidence_package(tmp_path):
    package = prepared(tmp_path)
    def update(manifest):
        manifest["files"] = [row for row in manifest["files"] if row["source"] != "results/20261003_cli_products/summary.json"]
    change_manifest(package, update)
    assert any(error["code"] == "CLI_SUMMARIES_INCOMPLETE" for error in receipt(tmp_path, package)["errors"])


def test_traversal_is_rejected_without_reading_external_file(tmp_path):
    package = prepared(tmp_path)
    def update(manifest):
        manifest["files"][0]["path"] = "../OUTSIDE.md"
    change_manifest(package, update)
    assert not receipt(tmp_path, package)["valid"]
