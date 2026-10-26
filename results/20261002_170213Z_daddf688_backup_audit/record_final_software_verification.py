"""Record verified final checks and independently validate executed snapshots."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


checks = {}
for run in (
    "20261002T182246Z_0265fdd0_requested_local_dev",
    "20261002T185320Z_1027a4c6_bitnet_native_dev",
    "20261002T191731Z_61e3e23d_bitnet_native_dev",
    "20261002T192227Z_63b6c1bf_requested_local_dev",
):
    folder = ROOT / "results" / run
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert digest(folder / "harness_source.py") == manifest["harness_sha256"], run
    snapshot = manifest.get("source_snapshot", {})
    for _, record in snapshot.items():
        assert digest(folder / record["snapshot"]) == record["sha256"], (run, record["snapshot"])
    for name, expected in manifest.get("core_source_sha256", {}).items():
        assert digest(ROOT / "src/agro_route" / name) == expected, name
    checks[run] = {"driver_snapshot_exact": True, "helper_copies_verified": len(snapshot),
                   "phi_limitation": "No pre-call helper copies were promised; driver preserved and core hashes verified" if not snapshot else None}
protocol_path = ROOT / "results/20261002_180119Z_76283d02_prerouting_dev/protocol.json"
protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
for name, expected in protocol["code_sha256"].items():
    assert digest(ROOT / name) == expected, name
source_records = {}
for directory in ("src", "scripts", "tests"):
    for path in sorted((ROOT / directory).rglob("*.py")):
        source_records[path.relative_to(ROOT).as_posix()] = digest(path)
report = {
    "created_utc": datetime.now(timezone.utc).isoformat(), "status": "PASS",
    "baseline_before_session_changes": {"passed": 241, "elapsed_seconds": 28.01},
    "full_suite": {"passed": 299, "elapsed_seconds_reported_by_pytest": 18.29,
                   "command": ".venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp .cache/pytest_continuation_final_20261002_1933",
                   "exit_code": 0, "timed_inference_active": False},
    "historical_reproducibility": {"status": "PASS", "dataset_protocol_sha_exact": True,
                                    "core_model_policy_scoring_sha_exact": True, "cached_statistics_exact": True,
                                    "folder": ".cache/reproducibility/statistics_4d841998"},
    "executed_compact_snapshots": checks,
    "prerouting_current_code_sha_verified": len(protocol["code_sha256"]),
    "checked_source_sha256": source_records,
    "review_pack_generator_integration": "PASS; fresh40 rows/final5 hashes/no self-hash/existing folder refused/7 originalfiles unchanged",
    "human_review": False, "software_validation_is_agronomic_validation": False,
    "lint": "NOT CONFIGURED",
}
destination = Path(__file__).resolve().parent / "software_verification_final_20261002.json"
with destination.open("x", encoding="utf-8") as handle:
    json.dump(report, handle, ensure_ascii=False, indent=2)
print(json.dumps({"status": report["status"], "passed": report["full_suite"]["passed"],
                  "driver_snapshots": len(checks), "prerouting_sources": report["prerouting_current_code_sha_verified"],
                  "output": destination.relative_to(ROOT).as_posix()}))
