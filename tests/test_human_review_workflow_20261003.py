# SPDX-License-Identifier: Apache-2.0
"""Synthetic temporary review fixtures; no real human annotations are authored."""
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/human_review_workflow_20261003.py"
spec = importlib.util.spec_from_file_location("review_workflow_v2_test", SCRIPT)
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


@pytest.fixture
def pack(tmp_path):
    source = tmp_path / "fake_source"
    source.mkdir()
    rows = [{"id": f"fixture_{i}", "language": "en", "question": "SYNTHETIC TEST FIXTURE, not a human-reviewed question", "context": '{"fixture":true}', "source_url": "https://example.invalid/fixture", "human_review": False, "category": "abstention"} for i in range(40)]
    (source / "blinded_questions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    (source / "provisional_gold_separate.jsonl").write_text('SECRET_FIXTURE_GOLD\n', encoding="utf-8")
    destination = tmp_path / "pack"
    manifest = review.prepare(destination, source)
    return destination, manifest


def returned(pack, tmp_path, letter, complete=True, judgment="CORRECT"):
    directory, manifest = pack
    rows = review.read_csv(directory / manifest["forms"][letter]["path"])
    if complete:
        for row in rows:
            row.update(judgment=judgment, expected_action="ABSTAIN", reference_answer="Synthetic unit test answer only")
    file = tmp_path / (letter + "_returned.csv")
    review._write_csv(file, rows)
    attestation = tmp_path / (letter + "_attestation.json")
    attestation.write_text(json.dumps({"reviewer": review.REVIEWERS[letter], "completed_by_human": True, "completed_utc": datetime.now(timezone.utc).isoformat(), "form_sha256": review.sha(file), "fixture_only": True}), encoding="utf-8")
    return file, attestation


def test_prepared_forms_are_blind_blank_and_unreviewed(pack):
    directory, manifest = pack
    assert manifest["human_review"] is False and manifest["confirmatory_eligible"] is False
    assert manifest["classification_target"] == "QUESTION_AND_REFERENCE_VALIDITY_NOT_MODEL_ACCURACY"
    for letter in "AB":
        file = directory / manifest["forms"][letter]["path"]
        rows = review.read_csv(file)
        assert len(rows) == 40 and all(not r["judgment"] for r in rows)
        text = file.read_text(encoding="utf-8-sig")
        assert "SECRET_FIXTURE_GOLD" not in text and "abstention" not in text and "model" not in text


def test_blank_form_rejected_even_with_attestation(pack, tmp_path):
    file, attestation = returned(pack, tmp_path, "A", complete=False)
    with pytest.raises(ValueError, match="Blank/incomplete"):
        review.validate_return(pack[0], "A", file, attestation)


def test_both_reviews_required_before_any_output(pack, tmp_path):
    a, att_a = returned(pack, tmp_path, "A")
    b, att_b = returned(pack, tmp_path, "B", complete=False)
    destination = tmp_path / "adjudication"
    with pytest.raises(ValueError, match="Blank/incomplete"):
        review.adjudicate(pack[0], a, att_a, b, att_b, destination)
    assert not destination.exists()


def test_attestation_must_match_identity_and_bytes(pack, tmp_path):
    file, attestation = returned(pack, tmp_path, "A")
    info = json.loads(attestation.read_text())
    info["reviewer"] = review.REVIEWERS["B"]
    attestation.write_text(json.dumps(info))
    with pytest.raises(ValueError, match="attestation"):
        review.validate_return(pack[0], "A", file, attestation)


def test_original_reference_integrity_prevents_adjudication(pack, tmp_path):
    file, attestation = returned(pack, tmp_path, "A")
    (pack[0] / "reviewer_A/reference_weather.json").write_text("changed")
    with pytest.raises(ValueError, match="reference bytes changed"):
        review.validate_return(pack[0], "A", file, attestation)


def test_expert_needed_never_becomes_gold(pack, tmp_path):
    a, att_a = returned(pack, tmp_path, "A")
    b, att_b = returned(pack, tmp_path, "B", judgment="DOMAIN_EXPERT_NEEDED")
    dest = tmp_path / "fixture_only_adjudication"
    receipt = review.adjudicate(pack[0], a, att_a, b, att_b, dest)
    assert receipt["agreed_gold_candidates"] == 0 and receipt["final_gold_frozen"] is False
    rows = json.loads((dest / "adjudication_candidates.json").read_text(encoding="utf-8"))
    assert all(r["gold_candidate"] is None and r["adjudication_status"] == "DOMAIN_EXPERT_NEEDED" for r in rows)


def test_prepare_never_overwrites_existing_pack(pack):
    original = (pack[0] / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        review.prepare(pack[0])
    assert (pack[0] / "manifest.json").read_bytes() == original


def test_synthetic_complete_forms_preserve_provenance_without_freezing_gold(pack, tmp_path):
    a, att_a = returned(pack, tmp_path, "A")
    b, att_b = returned(pack, tmp_path, "B")
    dest = tmp_path / "fixture_only_adjudication"
    input_hashes = {p: review.sha(p) for p in (a, att_a, b, att_b)}
    receipt = review.adjudicate(pack[0], a, att_a, b, att_b, dest)
    assert receipt["agreed_gold_candidates"] == 40
    assert receipt["confirmatory_eligible"] is False and receipt["final_gold_frozen"] is False
    assert {p: review.sha(p) for p in input_hashes} == input_hashes
    assert json.loads((pack[0] / "manifest.json").read_text(encoding="utf-8"))["human_review"] is False
