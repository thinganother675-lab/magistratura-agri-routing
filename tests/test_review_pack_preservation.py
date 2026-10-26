"""A future artifact regeneration must not erase human annotations or gold."""
import importlib.util
from pathlib import Path

import pytest


def test_existing_review_pack_is_rejected_before_source_read(tmp_path):
    source = Path(__file__).resolve().parents[1] / "scripts/build_blinded_review_pack_20261002.py"
    spec = importlib.util.spec_from_file_location("review_pack_preservation_test", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.CACHE = tmp_path / "source_is_deliberately_absent"
    destination = tmp_path / "existing_review"
    destination.mkdir()
    annotations = destination / "blinded_questions.csv"
    annotations.write_text("reviewer=human; reviewed=true\n", encoding="utf-8")
    original = annotations.read_bytes()

    with pytest.raises(FileExistsError, match="Existing reviewer inputs and gold are immutable"):
        module.main(destination)

    assert annotations.read_bytes() == original
    assert list(destination.iterdir()) == [annotations]
