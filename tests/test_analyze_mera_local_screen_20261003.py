# SPDX-License-Identifier: Apache-2.0
import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from analyze_mera_local_screen_20261003 import load_protocol, normalize_rows, validate_manifest_protocol
from agro_route.mera_screen_analysis_20261003 import digest


def protocol_fixture():
    protocol = {"source_sha256": "synthetic_data", "uncommitted_source_hashes": {"runner": "synthetic_code"},
                "context_length": 2048, "parallel": 1, "speculative_draft_mtp": False}
    manifest = {"source_sha256": "synthetic_data", "protocol_sha256": "synthetic_protocol", "classification": "DEV",
                "private_test_run": False, "uncommitted_source_hashes": {"runner": "synthetic_code"},
                "loads": [{"load_config": {"context_length": 2048, "parallel": 1, "speculative_draft_mtp": False}}]}
    return protocol, manifest


@pytest.mark.parametrize("field,value", [("source_sha256", "changed_data"), ("protocol_sha256", "changed_protocol"),
                                        ("uncommitted_source_hashes", {"runner": "changed_code"})])
def test_loader_rejects_manifest_not_bound_to_effective_protocol(field, value):
    protocol, manifest = protocol_fixture(); manifest[field] = value
    with pytest.raises(ValueError, match="provenance mismatch|runner source hash mismatch"):
        validate_manifest_protocol(manifest, protocol, "synthetic_protocol")


def test_loader_rejects_context_mismatch_or_private_test():
    protocol, manifest = protocol_fixture()
    manifest["loads"][0]["load_config"]["context_length"] = 8192
    with pytest.raises(ValueError, match="configuration differs"):
        validate_manifest_protocol(manifest, protocol, "synthetic_protocol")


def test_loader_rejects_missing_source_hash_and_missing_complete_load_metadata():
    protocol, manifest = protocol_fixture(); del manifest["uncommitted_source_hashes"]
    with pytest.raises(ValueError, match="runner source hash mismatch"):
        validate_manifest_protocol(manifest, protocol, "synthetic_protocol")
    protocol, manifest = protocol_fixture(); manifest["status"] = "COMPLETE"
    manifest["loads"][0] = {"chunk_offset": 0}
    protocol["fixed_reload_every_n"] = 10
    with pytest.raises(ValueError, match="configuration/warmup"):
        validate_manifest_protocol(manifest, protocol, "synthetic_protocol", 1)
    manifest["loads"] = []
    with pytest.raises(ValueError, match="fixed reload provenance"):
        validate_manifest_protocol(manifest, protocol, "synthetic_protocol", 60)
    protocol, manifest = protocol_fixture(); manifest["private_test_run"] = True
    with pytest.raises(ValueError, match="Private TEST"):
        validate_manifest_protocol(manifest, protocol, "synthetic_protocol")


def test_protocol_first_amendment_cannot_claim_unknown_parent(tmp_path):
    path = tmp_path / "protocol_frozen.json"; path.write_text('{"synthetic":true}', encoding="utf-8")
    amendment = {"original_protocol_sha256": digest(path.read_bytes()), "previous_amendment_sha256": "orphan",
                 "before_any_inference": True, "replacement_fields": {}}
    (tmp_path / "protocol_amendment_01.json").write_text(json.dumps(amendment), encoding="utf-8")
    with pytest.raises(ValueError, match="chain broken"):
        load_protocol(tmp_path)


def test_safe_schema_bridge_preserves_unresolved_reference_and_zero_error():
    rows = [{"item_id": 1, "gold_valid": False, "strict_set_em": None, "strict_set_f1": None, "prediction_valid": False}]
    normalized = normalize_rows(rows)
    assert normalized[0]["em"] is None and normalized[0]["f1"] is None and normalized[0]["pred_valid"] is False
    assert rows[0] == {"item_id": 1, "gold_valid": False, "strict_set_em": None, "strict_set_f1": None, "prediction_valid": False}
