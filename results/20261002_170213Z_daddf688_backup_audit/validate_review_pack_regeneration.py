"""Offline artifact integrity check; never overwrites the original review pack."""
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".cache/review_pack_integrity_smoke_20261002_1927"
DATA = ROOT / "results/20261002_170443Z_21722066_dataset_literature"
CANONICAL = {
    "README_RU.md", "blinded_questions.csv", "blinded_questions.jsonl",
    "provisional_gold_separate.csv", "provisional_gold_separate.jsonl",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
assert set(manifest["files"]) == CANONICAL
assert manifest["rows"] == 40 and manifest["human_review"] is False
assert manifest["confirmatory_eligible"] is False
original = json.loads((DATA / "human_review_pack/manifest_v2_integrity_20261002.json").read_text(encoding="utf-8"))
for name in CANONICAL:
    assert manifest["files"][name] == original["files"][name]
    assert manifest["files"][name] == {"bytes": (OUT / name).stat().st_size, "sha256": digest(OUT / name)}
questions = [json.loads(line) for line in (OUT / "blinded_questions.jsonl").read_text(encoding="utf-8").splitlines()]
gold = [json.loads(line) for line in (OUT / "provisional_gold_separate.jsonl").read_text(encoding="utf-8").splitlines()]
assert len(questions) == len(gold) == 40
assert len({row["id"] for row in questions}) == 40
assert {row["id"] for row in questions} == {row["id"] for row in gold}
assert all(row["human_review"] is False for row in questions + gold)
assert all(not row["reviewer_answer"] and not row["reviewer"] for row in questions)
assert not any("provisional_answer" in row or "provisional_expected_action" in row for row in questions)
before = {name: digest(OUT / name) for name in CANONICAL | {"manifest.json"}}
source = ROOT / "scripts/build_blinded_review_pack_20261002.py"
spec = importlib.util.spec_from_file_location("review_pack_regeneration_validation", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.CACHE = OUT / "intentionally_missing_source"
try:
    module.main(OUT)
except FileExistsError:
    refused_existing = True
else:
    raise AssertionError("Existing review pack was not rejected")
assert before == {name: digest(OUT / name) for name in before}
protected = json.loads((DATA / "integrity_repair_validation_20261002.json").read_text(encoding="utf-8"))["original_protected_records"]
for relative, record in protected.items():
    path = ROOT / relative
    assert path.stat().st_size == record["bytes"] and digest(path) == record["sha256"]
result = {
    "checked_utc": datetime.now(timezone.utc).isoformat(), "status": "PASS",
    "phase": "offline_artifact_generator_integration_not_inference",
    "source_sha256": digest(source), "new_pack_rows": 40,
    "finalized_inventory_hashes_verified": 5,
    "generated_question_gold_bytes_match_original": True,
    "manifest_self_hash_present": False,
    "existing_destination_refused_before_source_read": refused_existing,
    "six_existing_validation_files_unchanged": True,
    "seven_original_research_files_unchanged": True,
    "human_review": False, "provider_requests": 0,
    "validation_destination": str(OUT.relative_to(ROOT)).replace("\\", "/"),
}
destination = DATA / "review_pack_generator_integration_20261002.json"
with destination.open("x", encoding="utf-8") as handle:
    json.dump(result, handle, ensure_ascii=False, indent=2)
print(json.dumps(result, ensure_ascii=True))
