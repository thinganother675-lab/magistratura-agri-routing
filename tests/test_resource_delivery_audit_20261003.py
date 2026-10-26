"""Real Git regression for additions versus protected historical changes."""
import importlib.util
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("delivery_audit", ROOT / "scripts/audit_resource_delivery_20261003.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def git(root, *args):
    return subprocess.check_output(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                                    "-c", "commit.gpgsign=false", *args], cwd=root).decode("utf-8").strip()


@pytest.fixture
def repository(tmp_path):
    git(tmp_path, "init", "-q")
    for name in ("results/historical/summary.json", "manuscript/russian_routing_20261003.md",
                 "experiments/mera_private_test_protocol_draft_20261003.json"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"original":true}\n', encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "fixture baseline")
    return tmp_path, git(tmp_path, "rev-parse", "HEAD")


def test_committed_new_results_are_additions_not_historical_modifications(repository):
    root, baseline = repository
    path = root / "results/new_run/summary.json"
    path.parent.mkdir()
    path.write_text('{"new":true}\n', encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-qm", "new evidence")
    assert module.historical_changes(root, baseline) == []


def test_existing_historical_result_modification_is_detected(repository):
    root, baseline = repository
    (root / "results/historical/summary.json").write_text('{"original":false}\n', encoding="utf-8")
    assert module.historical_changes(root, baseline) == ["results/historical/summary.json"]


def test_private_protocol_deletion_is_detected(repository):
    root, baseline = repository
    (root / "experiments/mera_private_test_protocol_draft_20261003.json").unlink()
    assert module.historical_changes(root, baseline) == ["experiments/mera_private_test_protocol_draft_20261003.json"]


def test_historical_manuscript_rename_is_detected(repository):
    root, baseline = repository
    git(root, "mv", "manuscript/russian_routing_20261003.md", "manuscript/moved.md")
    assert module.historical_changes(root, baseline)
