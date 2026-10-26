# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Antoniy Sarychev and Denis Shesternin
"""Release boundaries, quantitative replay and protected history checks."""
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


def helper(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_original_smoke_has_no_network_or_label_leakage():
    report = helper("public_smoke").run(ROOT / "data/public_sample/benchmark.jsonl")
    assert report["cases"] == report["correct"] == 8
    assert report["external_requests"] == report["local_model_requests"] == 0
    assert {row["route"] for row in report["decisions"]} == {"DETERMINISTIC_TOOL", "ASK_FOR_DATA", "ABSTAIN"}


def test_measurements_projection_reproduces_frozen_aggregates():
    module = helper("reproduce_public_aggregates")
    path = ROOT / "data/public_sample/home150_measurements.jsonl"
    report = module.reproduce(path)
    expected = json.loads((ROOT / "data/public_sample/home150_expected_aggregates.json").read_text())
    module.compare(report, expected)
    assert sum(row["measured_n"] for row in report.values()) == 750
    assert {name: row["correct"] for name, row in report.items()} == {
        "local": 102, "cloud": 130, "tool_cloud": 139, "hybrid": 133, "offline": 114}
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert all(set(row) == module.FIELDS for row in rows)
    assert len({row["id"] for row in rows}) == 150
    assert len({row["group"] for row in rows}) == 25


@pytest.mark.parametrize("path", ["../outside", "/absolute", "x/../../outside", "x\\file", "C:/outside"])
def test_release_rejects_path_escape(tmp_path, path):
    with pytest.raises(ValueError):
        helper("build_public_release").safe_path(tmp_path, path)


@pytest.mark.parametrize("path", [".env", ".env.private", "models/weights.gguf", "private_WORKLOG.md", "downloaded.pdf", "runtime.log", ".git/config"])
def test_release_rejects_private_or_nonredistributable_artifacts(path):
    assert helper("build_public_release").inspect(path, b"innocent content")


def test_release_detects_pattern_and_exact_secret_without_logging_value():
    module = helper("build_public_release")
    synthetic = "sk-" + "A" * 32
    assert module.inspect("file.txt", synthetic.encode()) == ["provider_token"]
    custom = "fixture_" + "nonprovider_" + "value"
    assert module.inspect("file.txt", custom.encode(), {custom}) == ["configured_secret_match"]
    assert module.inspect(".env.example", b"CLOUD_API_KEY=\nCLOUD_INPUT_USD_PER_M=0.04\nCLOUD_AVAILABLE=false\n") == []


def test_manifest_requires_all_files_unchanged_and_known_provenance(tmp_path):
    module = helper("build_public_release")
    file = tmp_path / "original.txt"
    file.write_text("original software documentation\n")
    item = {"path": file.name, "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
            "classification": "PROJECT-OWNED", "license": "Apache-2.0", "provenance": "original"}
    manifest = tmp_path / "RELEASE_MANIFEST.json"
    manifest.write_text(json.dumps({"files": [item]}))
    assert module.verify(tmp_path)["provenance_pass"]
    file.write_text("modified payload\n")
    with pytest.raises(RuntimeError, match="sha256_mismatch"):
        module.verify(tmp_path)
    item["sha256"] = hashlib.sha256(file.read_bytes()).hexdigest()
    item["classification"] = "LICENSE-UNKNOWN"
    manifest.write_text(json.dumps({"files": [item]}))
    with pytest.raises(RuntimeError, match="unapproved_provenance"):
        module.verify(tmp_path)


def test_unlisted_file_is_not_silently_exported(tmp_path):
    module = helper("build_public_release")
    (tmp_path / "RELEASE_MANIFEST.json").write_text(json.dumps({"files": []}))
    (tmp_path / "unapproved.txt").write_text("extra")
    with pytest.raises(RuntimeError, match="file set"):
        module.verify(tmp_path)


def test_external_code_cannot_claim_a_blanket_apache_provenance():
    module = helper("build_public_release")
    assert not module.approved_provenance({"path": "vendor.py", "classification": "THIRD-PARTY-REDISTRIBUTABLE", "license": "Apache-2.0"}, b"copied code")
    assert module.approved_provenance({"path": "LICENSE", "classification": "THIRD-PARTY-REDISTRIBUTABLE", "license": "Apache-2.0"}, (ROOT / "LICENSE").read_bytes())


def test_symlink_ancestor_is_rejected_before_read(tmp_path, monkeypatch):
    module = helper("build_public_release")
    linked = tmp_path / "linked"
    monkeypatch.setattr(Path, "is_symlink", lambda self: self == linked)
    with pytest.raises(ValueError, match="Symlink"):
        module.safe_path(tmp_path, "linked/file.py")


def test_unknown_provenance_blocks_build_before_any_candidate_write(tmp_path):
    module = helper("build_public_release")
    (tmp_path / "release").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/historical_integrity_20261003.json").write_text(json.dumps({"baseline_git_head": "fixture", "sha256": {}}))
    (tmp_path / "file.py").write_text("original fixture")
    (tmp_path / "release/allowlist.json").write_text(json.dumps({"files": [{"source": "file.py", "path": "file.py", "classification": "LICENSE-UNKNOWN", "license": "Apache-2.0"}]}))
    destination = tmp_path / "output"
    with pytest.raises(ValueError, match="provenance"):
        module.build(tmp_path, destination)
    assert not destination.exists()


def test_historical_mutation_is_rejected_before_export(tmp_path):
    module = helper("build_public_release")
    (tmp_path / "docs").mkdir()
    source = tmp_path / "frozen.json"
    source.write_text('{"historical":true}')
    baseline = {"baseline_git_head": "fixture", "sha256": {"frozen.json": hashlib.sha256(source.read_bytes()).hexdigest()}}
    (tmp_path / "docs/historical_integrity_20261003.json").write_text(json.dumps(baseline))
    assert module.check_historical(tmp_path)["all_sha256_match"]
    source.write_text('{"historical":false}')
    with pytest.raises(RuntimeError, match="Historical artifacts changed"):
        module.check_historical(tmp_path)


def test_archive_is_deterministic_and_does_not_include_generated_output(tmp_path):
    module = helper("build_public_release")
    tree = tmp_path / "candidate"
    tree.mkdir()
    file = tree / "README.md"
    file.write_text("original software documentation\n")
    item = {"path": file.name, "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
            "classification": "PROJECT-OWNED", "license": "Apache-2.0", "provenance": "original"}
    (tree / "RELEASE_MANIFEST.json").write_text(json.dumps({"files": [item]}))
    (tree / "reproduction_output").mkdir()
    (tree / "reproduction_output/generated.json").write_text("{}")
    left, right = tmp_path / "left.zip", tmp_path / "right.zip"
    a, b = module.archive(tree, left), module.archive(tree, right)
    assert a == b
    assert left.read_bytes() == right.read_bytes()
    with zipfile.ZipFile(left) as handle:
        assert handle.namelist() == ["README.md", "RELEASE_MANIFEST.json"]
        assert handle.testzip() is None


def test_historical_data_results_protocol_and_frozen_core_unchanged():
    # Public tree has a release manifest instead of the private history inventory.
    if (ROOT / "docs/historical_integrity_20261003.json").exists():
        assert helper("build_public_release").check_historical(ROOT)["all_sha256_match"]
    else:
        metadata = json.loads((ROOT / "RELEASE_MANIFEST.json").read_text())
        assert metadata["historical_integrity"]["all_sha256_match"] is True
        assert metadata["historical_integrity"]["protected_files"] == 796


def test_official_license_is_unmodified_and_software_authors_are_correct():
    assert hashlib.sha256((ROOT / "LICENSE").read_bytes()).hexdigest() == "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"
    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert "given-names: Antoniy" in citation and "given-names: Denis" in citation
    assert "family-names: Sarychev" in citation and "family-names: Shesternin" in citation
    assert "license: Apache-2.0" in citation
    assert "doi:" not in citation.lower() and "orcid:" not in citation.lower()
