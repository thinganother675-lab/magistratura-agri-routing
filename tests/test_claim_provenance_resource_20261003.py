# SPDX-License-Identifier: Apache-2.0
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from agro_route.claim_provenance_resource_20261003 import (
    ProvenanceError,
    exact_value,
    git_commit_exists,
    resolve_pointer,
    safe_source_path,
    strict_json_loads,
    validate_provenance,
)

ROOT = Path(__file__).resolve().parents[1]
HEAD = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()


def fixture(tmp_path, source=None):
    path = tmp_path / "results/synthetic_fixture/summary.json"
    path.parent.mkdir(parents=True)
    document = source or {"run_id": "synthetic_run", "classification": "DEV", "private_test_run": False,
                          "metrics": {"em": 0.5, "n": 2}, "a/b": {"~key": [{"": 3}]}}
    path.write_text(json.dumps(document, ensure_ascii=False) + "\n", encoding="utf-8")
    claim = {"claim_id": "fixture_em", "statement": "Synthetic metric fixture only", "run_id": "synthetic_run",
             "file": path.relative_to(tmp_path).as_posix(), "field": "/metrics/em", "value": 0.5,
             "code_commit": HEAD, "status": "DEV", "data_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
             "limitations": "Synthetic fixture, never an experimental result"}
    return {"claims": [claim], "source_commit": HEAD, "run_code_commits": {"synthetic_run": HEAD}}, path


def check(document, root):
    # Real current repository commit checks; temporary fixture content is not
    # represented as committed measurement data.
    return validate_provenance(document, root, commit_checker=lambda commit: git_commit_exists(ROOT, commit))


def codes(receipt):
    return {row["code"] for row in receipt["errors"]}


def test_actual_existing_commit_hash_pointer_and_value_agree(tmp_path):
    document, _ = fixture(tmp_path)
    receipt = check(document, tmp_path)
    assert receipt["valid"] and receipt["claims_verified"] == receipt["claims_total"] == 1
    assert receipt["status_counts"]["DEV"] == 1
    assert "Fixture metric" not in json.dumps(receipt)
    assert git_commit_exists(ROOT, HEAD)
    assert not git_commit_exists(ROOT, "0" * 40)


def test_changed_source_hash_fails_even_when_selected_metric_is_same(tmp_path):
    document, path = fixture(tmp_path)
    path.write_text(path.read_text() + " ", encoding="utf-8")
    receipt = check(document, tmp_path)
    assert not receipt["valid"] and "source_sha256_mismatch" in codes(receipt)


def test_claim_value_and_boolean_type_cannot_be_rewritten(tmp_path):
    document, _ = fixture(tmp_path)
    document["claims"][0].update(field="/private_test_run", value=0)
    assert "source_value_mismatch" in codes(check(document, tmp_path))
    document["claims"][0].update(field="/metrics/em", value=0.6)
    assert "source_value_mismatch" in codes(check(document, tmp_path))
    assert not exact_value(1, True) and not exact_value(1, 1.0)
    assert exact_value({"v": [1, 1.0, True]}, {"v": [1, 1.0, True]})


def test_duplicate_claim_identifier_is_rejected(tmp_path):
    document, _ = fixture(tmp_path)
    document["claims"].append(copy.deepcopy(document["claims"][0]))
    assert "invalid_or_duplicate_claim_id" in codes(check(document, tmp_path))


def test_rfc6901_escaping_empty_keys_and_root_are_resolved():
    source = {"a/b": {"~key": [{"": 3}]}}
    assert resolve_pointer(source, "/a~1b/~0key/0/") == 3
    assert resolve_pointer(source, "") is source


@pytest.mark.parametrize("pointer", ["metric", "/a~2b", "/a/b~", "/a~1b/~0key/00", "/a~1b/~0key/-", "/a~1b/~0key/" + "9" * 5000])
def test_invalid_or_out_of_range_pointers_fail_closed(pointer):
    with pytest.raises(ProvenanceError):
        resolve_pointer({"a/b": {"~key": [3]}}, pointer)


@pytest.mark.parametrize("path", [".runtime/summary.json", "data/summary.json", "results/mera_restricted/summary.json", "results/run/gold.json", "experiments/mera_private_test_protocol.json", "../results/summary.json", "results\\summary.json", "C:/secret.json", "docs/summary.md"])
def test_forbidden_sources_cannot_be_bound_to_claims(tmp_path, path):
    with pytest.raises(ProvenanceError):
        safe_source_path(tmp_path, path)


def test_nonexistent_or_wrong_recorded_commit_is_rejected(tmp_path):
    document, _ = fixture(tmp_path)
    document["claims"][0]["code_commit"] = "0" * 40
    result = check(document, tmp_path)
    assert {"code_commit_missing_or_invalid", "recorded_run_commit_mismatch"} <= codes(result)


def test_source_run_identity_mismatch_is_rejected(tmp_path):
    document, _ = fixture(tmp_path)
    document["claims"][0]["run_id"] = "another_synthetic_run"
    assert "source_run_id_mismatch" in codes(check(document, tmp_path))


def test_confirmatory_flags_cannot_promote_dev_data(tmp_path):
    document, _ = fixture(tmp_path)
    document.update(independent_holdout=True, authorized_protocol=True)
    document["claims"][0]["status"] = "CONFIRMATORY"
    assert "confirmatory_not_authorized_independent_source" in codes(check(document, tmp_path))


def test_confirmatory_requires_explicit_top_and_source_gates(tmp_path):
    source = {"run_id": "synthetic_run", "classification": "CONFIRMATORY", "private_test_run": False,
              "independent_holdout": True, "metrics": {"em": 0.5}}
    document, _ = fixture(tmp_path, source)
    document["claims"][0]["status"] = "CONFIRMATORY"
    assert not check(document, tmp_path)["valid"]
    document.update(independent_holdout=True, authorized_protocol=True)
    assert check(document, tmp_path)["valid"]  # Structural synthetic fixture only.
    document["authorized_protocol"] = 1
    assert not check(document, tmp_path)["valid"]


def test_private_test_source_is_not_authorized_by_confirmatory_flags(tmp_path):
    document, _ = fixture(tmp_path, {"run_id": "synthetic_run", "classification": "CONFIRMATORY", "private_test_run": True,
                                   "independent_holdout": True, "metrics": {"em": 0.5}})
    document.update(independent_holdout=True, authorized_protocol=True)
    document["claims"][0]["status"] = "CONFIRMATORY"
    assert "confirmatory_not_authorized_independent_source" in codes(check(document, tmp_path))


def test_secret_in_source_or_claim_never_reaches_receipt(tmp_path):
    marker = "SYNTHETIC_SECRET_DO_NOT_EXPOSE"
    document, _ = fixture(tmp_path, {"metrics": {"em": 0.5}, "api_key": marker})
    result = check(document, tmp_path)
    assert "secret_like_source" in codes(result) and marker not in json.dumps(result)
    document["claims"][0]["statement"] = "sk-" + "SYNTHETICSECRET" * 3
    result = check(document, tmp_path)
    assert "secret_like_provenance" in codes(result)
    assert "SYNTHETICSECRET" not in json.dumps(result)


def test_nested_private_source_and_provider_key_fields_are_rejected(tmp_path):
    nested = tmp_path / "results/synthetic_private_run/summary.json"
    nested.parent.mkdir(parents=True)
    nested.write_text('{"em":0.5}', encoding="utf-8")
    with pytest.raises(ProvenanceError, match="forbidden_source_path"):
        safe_source_path(tmp_path, nested.relative_to(tmp_path).as_posix())
    document, _ = fixture(tmp_path, {"metrics": {"em": 0.5}, "OPENAI_API_KEY": "SYNTHETIC" + "_MARKER"})
    result = check(document, tmp_path)
    assert "secret_like_source" in codes(result) and "SYNTHETIC_MARKER" not in json.dumps(result)


@pytest.mark.parametrize("text", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'])
def test_ambiguous_or_nonfinite_json_is_not_accepted(text):
    with pytest.raises(ProvenanceError):
        strict_json_loads(text)


def test_malformed_identity_types_produce_receipt_instead_of_exception(tmp_path):
    document, _ = fixture(tmp_path)
    document["claims"][0].update(run_id=[], claim_id={}, field=None, value={})
    result = check(document, tmp_path)
    assert not result["valid"] and "claim_text_identity_missing" in codes(result)


def test_cli_emits_only_safe_receipt_and_refuses_overwrite(tmp_path, monkeypatch, capsys):
    document, _ = fixture(tmp_path)
    path = tmp_path / "manuscript/CLAIM_PROVENANCE_RESOURCE_FIXTURE.json"
    path.parent.mkdir()
    path.write_text(json.dumps(document), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("resource_provenance_cli_test", ROOT / "scripts/verify_resource_provenance_20261003.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    monkeypatch.setattr(cli, "validate_provenance", lambda doc, root: check(doc, root))
    argv = [str(ROOT / "scripts/verify_resource_provenance_20261003.py"), "--root", str(tmp_path),
            "--provenance", path.relative_to(tmp_path).as_posix(), "--receipt", "results/validation.json"]
    monkeypatch.setattr(sys, "argv", argv)
    assert cli.main() == 0
    output = capsys.readouterr().out
    assert "fixture_em" not in output and "Synthetic metric fixture" not in output and '"valid": true' in output
    before = (tmp_path / "results/validation.json").read_bytes()
    assert cli.main() == 2
    assert (tmp_path / "results/validation.json").read_bytes() == before
