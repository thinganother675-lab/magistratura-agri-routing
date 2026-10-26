# SPDX-License-Identifier: Apache-2.0
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("claude_editor_builder", ROOT / "scripts/build_claude_editor_package_20261003.py")
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


def write(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")
    return path


def fixture(root):
    for name in BUILDER.MANUSCRIPTS:
        write(root, name, "Unchanged historical synthetic manuscript, EM 0.4879.\n")
    write(root, "docs/VERIFIED_BIBLIOGRAPHY_20261003_RU.md", "Verified synthetic bibliography.\n")
    write(root, "docs/RESOURCE_SESSION_LIMITATIONS_20261003_RU.md", "Synthetic limitation: DEV is exploratory.\n")
    write(root, "manuscript/CLAIM_PROVENANCE_RESOURCE_SESSION_20261003.json", json.dumps({"claims": [
        {"claim_id": "synthetic_delta", "statement": "Fixture only", "value": -0.03114186851211076,
         "analysis_field": "/quality/delta", "code_commit": "b" * 40, "status": "DEV"}]}))
    write(root, "results/20261003_resource_analysis/domains.csv", "group,n,left_em_count,right_em_count\nsynthetic,2,1,2\n")
    write(root, "results/20261003_resource_analysis/cascade_dev60.csv", "policy,cloud_calls\nsynthetic,1\n")
    write(root, "results/20261003_systems_fixture/systems_summary.json", json.dumps({"classification": "SYSTEMS_TELEMETRY", "p50": 0.33, "private_test_run": False}))
    write(root, "results/20261003_systems_fixture/study_c_summary.json", json.dumps({"classification": "DEV", "n": 27, "correct": 7}))
    write(root, "results/20261003_systems_fixture/telemetry_table.csv", "model_key,task_id,latency_s,output_tokens\nsynthetic,0,0.33,12\n")
    write(root, "results/20261003_cli_fixture/dev60_summary.json", json.dumps({"classification": "SUPPLEMENTARY", "n": 60, "correct": 33, "cost_label": "SUBSCRIPTION_INCLUDED"}))
    return {"systems_dir": "results/20261003_systems_fixture",
            "provenance": "manuscript/CLAIM_PROVENANCE_RESOURCE_SESSION_20261003.json",
            "limitations": "docs/RESOURCE_SESSION_LIMITATIONS_20261003_RU.md",
            "output": "outputs/claude_paper_editor_package", "source_commit": "a" * 40,
            "cli_aggregates": ("results/20261003_cli_fixture/dev60_summary.json",)}


def historical_fixture(root):
    register = {name: {"analysis_file": "results/synthetic_history/summary.json", "run_id": "synthetic_home150",
                       "sha256": "c" * 64, "code_commit": "b" * 40, "scope": "SYNTHETIC_HISTORY"}
                for name in ("home150", "home_manifest")}
    data = {"source_register": register,
            "key_claims": [{"claim_id": "home150_n", "source_id": "home150", "value": 150,
                            "json_pointer": "/target_n", "run_id": "synthetic_home150"},
                           {"claim_id": "dev_count", "source_id": "study_c", "value": 27}],
            "derived_claims": [{"claim_id": "home150_policy_count", "value": 5,
                                "derivation": {"operation": "length", "operands": [{"source_id": "home_manifest", "json_pointer": "/policies"}]}}],
            "numeric_claim_catalogs": {"synthetic_excluded": [123456789]}}
    return write(root, BUILDER.HISTORICAL_SOURCE, json.dumps(data))


def test_package_preserves_manuscripts_numbers_hashes_and_statuses(tmp_path):
    config = fixture(tmp_path)
    manifest = BUILDER.build_package(tmp_path, **config)
    output = tmp_path / config["output"]
    assert manifest["claude_editing_run"] is False
    assert manifest["historical_manuscripts_unchanged"]
    assert manifest["latest_appendices_are_authority"]
    for name in BUILDER.MANUSCRIPTS:
        assert (tmp_path / name).read_bytes() == (output / name).read_bytes()
    for row in manifest["files"]:
        assert row["status"] in BUILDER.STATUSES
        assert row["source_commit"] == "a" * 40
        assert hashlib.sha256((output / row["path"]).read_bytes()).hexdigest() == row["copied_sha256"]
        if row["copy_mode"] == "BYTE_FOR_BYTE":
            assert row["source_sha256"] == row["copied_sha256"]
    claims = json.loads((output / "provenance/CLAIM_PROVENANCE_SUMMARY.json").read_text())["claims"]
    assert claims[0]["value"] == -0.03114186851211076
    assert next(row for row in manifest["files"] if row["source"].endswith("cascade_dev60.csv"))["status"] == "SIMULATED"
    styles = (output / "AUTHORS_AND_STYLE.md").read_text(encoding="utf-8")
    assert "DO NOT CHANGE NUMBERS" in styles and "Antoniy Sarychev" in styles and "Denis Shesternin" in styles
    assert "historical" in (output / "README.md").read_text().lower()


def test_unlisted_raw_artifacts_are_never_copied(tmp_path):
    config = fixture(tmp_path)
    write(tmp_path, "results/20261003_systems_fixture/inference_metrics.jsonl", '{"exact_response":"SYNTHETIC_RAW_TEXT"}\n')
    write(tmp_path, "results/20261003_systems_fixture/study_c_scores.jsonl", '{"gold":"SYNTHETIC_GOLD"}\n')
    write(tmp_path, ".runtime/synthetic_private/question.json", '{"question":"SYNTHETIC_QUESTION"}\n')
    write(tmp_path, "results/20261003_resource_analysis/private_summary.json", '{"gold":"SYNTHETIC_GOLD"}\n')
    manifest = BUILDER.build_package(tmp_path, **config)
    assert all(not row["path"].endswith(".jsonl") for row in manifest["files"])
    contents = "\n".join(path.read_text(encoding="utf-8") for path in (tmp_path / config["output"]).rglob("*") if path.is_file())
    assert "SYNTHETIC_RAW_TEXT" not in contents and "SYNTHETIC_GOLD" not in contents and "SYNTHETIC_QUESTION" not in contents


@pytest.mark.parametrize("field", ["question", "correct_answer", "response_text", "output_text", "api_key", "authorization"])
def test_forbidden_summary_content_fails_before_output_creation(tmp_path, field):
    config = fixture(tmp_path)
    write(tmp_path, "results/20261003_systems_fixture/systems_summary.json", json.dumps({field: "synthetic sensitive field"}))
    with pytest.raises(ValueError, match="Raw benchmark or credential field"):
        BUILDER.build_package(tmp_path, **config)
    assert not (tmp_path / config["output"]).exists()


def test_gold_csv_column_is_blocked(tmp_path):
    config = fixture(tmp_path)
    write(tmp_path, "results/20261003_resource_analysis/domains.csv", "domain,correct_answer\nsynthetic,A\n")
    with pytest.raises(ValueError, match="Raw benchmark CSV"):
        BUILDER.build_package(tmp_path, **config)
    assert not (tmp_path / config["output"]).exists()


def test_secret_error_never_contains_matched_value(tmp_path):
    config = fixture(tmp_path)
    secret = "sk-" + "SYNTHETICSECRET" * 3
    write(tmp_path, config["limitations"], secret)
    with pytest.raises(ValueError) as error:
        BUILDER.build_package(tmp_path, **config)
    assert secret not in str(error.value)
    assert not (tmp_path / config["output"]).exists()


@pytest.mark.parametrize("source", [".runtime/summary.json", "data/summary.json", "results/mera_restricted/summary.json", "../outside.json"])
def test_source_paths_cannot_capture_private_or_external_files(tmp_path, source):
    config = fixture(tmp_path)
    config["cli_aggregates"] = (source,)
    with pytest.raises(ValueError):
        BUILDER.build_package(tmp_path, **config)
    assert not (tmp_path / config["output"]).exists()


def test_non_summary_cli_json_is_rejected(tmp_path):
    config = fixture(tmp_path)
    config["cli_aggregates"] = ("results/20261003_cli_fixture/manifest.json",)
    write(tmp_path, config["cli_aggregates"][0], '{"n":60}')
    with pytest.raises(ValueError, match="aggregate JSON"):
        BUILDER.build_package(tmp_path, **config)


def test_existing_output_is_preserved(tmp_path):
    config = fixture(tmp_path)
    sentinel = write(tmp_path, config["output"] + "/KEEP.md", "preserve this synthetic existing file")
    with pytest.raises(ValueError, match="new workspace outputs"):
        BUILDER.build_package(tmp_path, **config)
    assert sentinel.read_text() == "preserve this synthetic existing file"


def test_active_svg_is_blocked(tmp_path):
    config = fixture(tmp_path)
    write(tmp_path, "results/20261003_systems_fixture/figure.svg", '<svg><script>synthetic()</script></svg>')
    with pytest.raises(ValueError, match="Active or external SVG"):
        BUILDER.build_package(tmp_path, **config)


def test_unknown_claim_status_is_not_promoted_to_confirmatory(tmp_path):
    config = fixture(tmp_path)
    write(tmp_path, config["provenance"], json.dumps({"claims": [{"claim_id": "fixture", "status": "READY", "value": 0.5}]}))
    with pytest.raises(ValueError, match="status missing or invalid"):
        BUILDER.build_package(tmp_path, **config)


def test_corrected_study_c_and_verified_bibliography_addendum_are_preserved(tmp_path):
    config = fixture(tmp_path)
    config["study_c_summary"] = "results/20261003_corrected/study_c_corrected_aggregate.json"
    corrected = write(tmp_path, config["study_c_summary"], '{"classification":"DEV","numeric_correct":6,"corrected":true}\n')
    config["bibliography_addendum"] = "docs/VERIFIED_RESOURCE_BIBLIOGRAPHY_20261003_RU.md"
    bibliography = write(tmp_path, config["bibliography_addendum"], "Verified synthetic resource addendum.\n")
    final_table = write(tmp_path, "results/20261003_resource_analysis/final_model_table.csv", "model,quality_status,latency_status\nsynthetic,DEV,SYSTEMS_TELEMETRY\n")
    manifest = BUILDER.build_package(tmp_path, **config)
    output = tmp_path / config["output"]
    assert (output / "summaries/study_c_summary.json").read_bytes() == corrected.read_bytes()
    assert (output / "references/VERIFIED_RESOURCE_BIBLIOGRAPHY_20261003_RU.md").read_bytes() == bibliography.read_bytes()
    assert (output / "tables/dev/final_model_table.csv").read_bytes() == final_table.read_bytes()
    assert next(row for row in manifest["files"] if row["source"].endswith("final_model_table.csv"))["status"] == "SUPPLEMENTARY"


def test_unverified_bibliography_addendum_is_not_allowlisted(tmp_path):
    config = fixture(tmp_path)
    config["bibliography_addendum"] = "docs/UNVERIFIED_RESOURCE_REFERENCES.md"
    write(tmp_path, config["bibliography_addendum"], "synthetic unverified references")
    with pytest.raises(ValueError, match="verified resource bibliography"):
        BUILDER.build_package(tmp_path, **config)
    assert not (tmp_path / config["output"]).exists()


def test_preserved_pre_alias_archive_is_excluded_while_final_table_is_copied(tmp_path):
    config = fixture(tmp_path)
    archive = write(tmp_path, "results/20261003_resource_analysis/final_model_table_before_status_aliases.csv",
                    "model,quality_status\nsynthetic,OLD_CLASSIFICATION\n")
    archive_bytes = archive.read_bytes()
    final = write(tmp_path, "results/20261003_resource_analysis/final_model_table.csv",
                  "model,quality_status,latency_status\nsynthetic,DEV,SYSTEMS_TELEMETRY\n")
    manifest = BUILDER.build_package(tmp_path, **config)
    output = tmp_path / config["output"]
    assert archive.read_bytes() == archive_bytes
    assert not (output / "tables/dev" / archive.name).exists()
    assert all(row["source"] != archive.relative_to(tmp_path).as_posix() for row in manifest["files"])
    assert (output / "tables/dev/final_model_table.csv").read_bytes() == final.read_bytes()
    assert (output / "tables/dev/domains.csv").is_file()


def test_historical_home150_projection_preserves_scalars_and_excludes_catalogs(tmp_path):
    config = fixture(tmp_path)
    original = historical_fixture(tmp_path)
    original_bytes = original.read_bytes()
    manifest = BUILDER.build_package(tmp_path, **config)
    row = next(row for row in manifest["files"] if row["role"] == "historical_provenance")
    copied = (tmp_path / config["output"] / row["path"]).read_bytes()
    summary = json.loads(copied)
    assert row["status"] == "HISTORICAL" and row["copy_mode"] == "PROJECTION_NUMBERS_UNCHANGED"
    assert summary["key_claims"][0]["value"] == 150
    assert summary["derived_claims"][0]["value"] == 5
    assert all(claim["status"] == "HISTORICAL" for claim in summary["key_claims"] + summary["derived_claims"])
    assert set(summary["source_register"]) == {"home150", "home_manifest"}
    assert b"numeric_claim_catalogs" not in copied and b"dev_count" not in copied and b"123456789" not in copied
    assert original.read_bytes() == original_bytes


def test_alternative_historical_source_cannot_capture_unlisted_provenance(tmp_path):
    config = fixture(tmp_path)
    config["historical_provenance"] = "manuscript/CLAIM_PROVENANCE_UNLISTED.json"
    write(tmp_path, config["historical_provenance"], '{"synthetic":true}')
    with pytest.raises(ValueError, match="frozen historical HOME150"):
        BUILDER.build_package(tmp_path, **config)
    assert not (tmp_path / config["output"]).exists()


def test_denis_sheet_contains_eight_unanswered_decisions_on_one_page():
    text = (ROOT / "docs/DENIS_DECISION_SHEET_20261003_RU.md").read_text(encoding="utf-8")
    assert len(text.split()) <= 450
    assert text.count("☐") == 8 and "☑" not in text and "[x]" not in text.lower()
    assert text.count("Комментарий:") == 8
    assert "Antoniy Sarychev" in text and "Denis Shesternin" in text
