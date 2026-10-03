# SPDX-License-Identifier: Apache-2.0
import io
import math
import zipfile
import pytest

from agro_route.mera_adapter_20261003 import (
    adapt_row, diagnostic_set_scores, ensure_restricted_path, forbid_gold,
    ingest_remote_score, isolate_dev_references, normalize_options,
    official_scores, package_submission, route_local, submission_object,
)


def invented_row(label="A"):
    return {"instruction": "{domain}: {question}\nA. {option_a}\nB. {option_b}\nC. {option_c}\nD. {option_d}",
            "inputs": {"question": "Сколько будет 1 + 1?", "option_a": "2", "option_b": "3",
                       "option_c": "4", "option_d": "5"},
            "outputs": label, "meta": {"id": 7, "domain": "Придуманный пример программы"}}


def test_prompt_never_includes_reference_and_dev_gold_is_separate():
    items, refs = isolate_dev_references([invented_row("UNIQUE_REFERENCE_SENTINEL")])
    assert "UNIQUE_REFERENCE_SENTINEL" not in items[0].prompt
    assert refs[7] == "UNIQUE_REFERENCE_SENTINEL"
    forbid_gold(items[0].public())


@pytest.mark.parametrize("gold", ["A", " ", ["A"], 1])
def test_private_reference_is_rejected(gold):
    with pytest.raises(ValueError): adapt_row(invented_row(gold), "test")


def test_split_roles_and_duplicate_ids():
    assert adapt_row(invented_row(""), "test").split == "test"
    with pytest.raises(ValueError): adapt_row(invented_row(), "train")
    with pytest.raises(ValueError): isolate_dev_references([invented_row(), invented_row()])


@pytest.mark.parametrize("text,expected", [("A", "A"), ("A, C", "A, C"), ("C,A", "A, C"),
    ("  c , a  ", "A, C"), ("A A C", "A, C"), ("Ответ: C, A. Объяснение.", "A, C"),
    ("```text\nA, C\n```", "A, C")])
def test_normalization_without_reference(text, expected):
    assert normalize_options(text, "ABCD").canonical == expected


@pytest.mark.parametrize("text", ["AC", "1", "A или B", "Можно выбрать A, но лучше B", "E", "", "Ответ: A. Ответ: B."])
def test_ambiguous_or_nonexistent_choices_fail(text):
    assert not normalize_options(text, "ABCD").choices


def test_official_metric_quirk_is_preserved_and_visible():
    assert official_scores("A, C", "C") == {"exact_match": 1, "f1": 1.0}
    assert official_scores("A", "") == {"exact_match": 1, "f1": 1.0}
    assert diagnostic_set_scores("A, C", "C", "ABCD")["set_exact_match"] == 0
    assert diagnostic_set_scores("A", "", "ABCD")["set_f1"] == 0
    assert official_scores("B, C", "C, B")["exact_match"] == 0
    assert official_scores("B, C", "C, B")["f1"] == 1


def test_public_reference_script_issue_not_silently_changed():
    assert diagnostic_set_scores("А, В", "A, B", "ABCD")["reference_issue"]
    assert official_scores("А, В", "A, B")["exact_match"] == 0


def test_router_is_reference_free_and_missing_confidence_routes_cloud():
    result = {"valid_options": True, "option_token_confidence": .8, "error": None}
    assert route_local(result, threshold=.7) == "local"
    assert route_local({**result, "option_token_confidence": None}, threshold=.7) == "cloud"
    with pytest.raises(ValueError): route_local({**result, "nested": {"gold": "A"}})


def test_submission_schema_is_exact_and_requires_complete_test():
    p = [{"item_id": 7, "prediction": "B", "split": "test"}]
    assert submission_object(p, [7]) == {"data": {"test": [{"outputs": "B", "meta": {"id": 7}}]}}
    for bad in [p * 2, [{**p[0], "split": "dev"}], [{**p[0], "gold": "A"}], []]:
        with pytest.raises(ValueError): submission_object(bad, [7])
    with pytest.raises(ValueError): submission_object([{**p[0], "item_id": True}], [1])
    with pytest.raises(ValueError): submission_object(p, [True])


def test_packaging_restricted_and_contains_original_logs(tmp_path):
    root = tmp_path
    d = root / ".runtime/mera"; d.mkdir(parents=True)
    logs = d / "logs_public.zip"
    with zipfile.ZipFile(logs, "w") as z: z.writestr("invented_fixture.txt", "Synthetic fixture, no dataset")
    manifest = {k: "fixture" for k in ("code_commit", "model_id", "quantization", "prompt_sha256", "runtime",
                "mera_revision", "dataset_revision", "policy", "protocol_sha256")}
    predictions = [{"item_id": 7, "prediction": "B", "split": "test"}]
    out = d / "submission.zip"
    report = package_submission(predictions, [7], logs, out, root=root, manifest=manifest)
    assert report["submission_status"] == "NOT_SUBMITTED"
    with zipfile.ZipFile(out) as z:
        assert set(z.namelist()) == {"ruTXTAgroBench.json", "logs_public.zip"}
        assert z.read("logs_public.zip") == logs.read_bytes()
    with pytest.raises(ValueError): ensure_restricted_path(root / "release/data.json", root)
    with pytest.raises(ValueError): package_submission(predictions, [7], logs, out, root=root, manifest=manifest)


def test_remote_aggregate_ingestion_never_creates_per_item_evidence():
    r = {"submission_id": "synthetic-unit-fixture", "submission_timestamp": "2026-10-03T00:00:00Z",
         "archive_sha256": "a" * 64, "source_url": "https://mera.a-ai.ru/", "metrics": {"exact_match": .5, "f1": .6}}
    assert not ingest_remote_score(r, expected_archive_sha256="a" * 64)["paired_ci_available"]
    with pytest.raises(ValueError): ingest_remote_score(r, expected_archive_sha256="b" * 64)
    with pytest.raises(ValueError): ingest_remote_score({**r, "metrics": {"exact_match": math.nan, "f1": .6}}, expected_archive_sha256="a" * 64)
    with pytest.raises(ValueError): ingest_remote_score({**r, "gold": "A"}, expected_archive_sha256="a" * 64)
    with pytest.raises(ValueError): ingest_remote_score({**r, "per_item_correctness": [True]}, expected_archive_sha256="a" * 64)
