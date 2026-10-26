"""Pure skip/boundary checks for the append-only Mercury extension."""
import importlib.util
from pathlib import Path

import pytest


def module():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("mercury_extend_test", root / "scripts/home_mercury_extend.py")
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_remaining24_excludes_all12_even_parent_timeout():
    samples = [{"id": str(i), "split": "dev"} for i in range(36)]
    parent = [{"sample": s, "cloud": {"error": {"type": "ReadTimeout"} if i == 0 else None}}
              for i, s in enumerate(samples[:12])]
    result = module().remaining_samples(samples, parent)
    assert len(result) == 24 and result[0]["id"] == "12"
    assert not set(s["id"] for s in result) & set(r["sample"]["id"] for r in parent)


def test_mismatch_and_duplicate_parent_rejected_before_calls():
    samples = [{"id": str(i), "split": "dev"} for i in range(36)]
    parent = [{"sample": s} for s in samples[:12]]
    parent[1] = parent[0]
    with pytest.raises(ValueError, match="Duplicate"):
        module().remaining_samples(samples, parent)
    parent = [{"sample": s} for s in samples[:12]]
    parent[0] = {"sample": {"id": "0", "split": "test"}}
    with pytest.raises(ValueError, match="differs"):
        module().remaining_samples(samples, parent)
