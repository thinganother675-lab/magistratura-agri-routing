# SPDX-License-Identifier: Apache-2.0
"""Cross-check our diagnostic scorer against exact-source execution receipts.

All labels are synthetic. Tests need no download, model backend, benchmark
questions, private TEST, or optional Transformers installation.
"""
import importlib.util
import json
from pathlib import Path

import pytest

from agro_route.mera_adapter_20261003 import official_scores

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("mera_exact_source_recheck", ROOT / "scripts/recheck_mera_scorer_20261003.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
RECEIPT = json.loads((ROOT / "results/20261003_mera_scorer_recheck_verified/scorer_recheck.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", RECEIPT["diagnostics_synthetic"][:-1], ids=lambda case: repr((case["gold"], case["prediction"])))
def test_compatibility_scorer_agrees_with_exact_published_source_execution(case):
    ours = official_scores(case["gold"], case["prediction"])
    exact = case["published_mera_exact_source"]
    assert ours == {"exact_match": exact["em"], "f1": exact["f1"]}


def test_exact_source_receipt_distinguishes_option_a_and_comma_spacing():
    cases = {(item["gold"], item["prediction"]): item["published_mera_exact_source"]
             for item in RECEIPT["diagnostics_synthetic"]}
    assert cases["A", ""] == {"em": 1, "f1": 1}
    assert cases["A, C", "C"] == {"em": 1, "f1": 1}
    assert cases["A,C", "C"] == {"em": 0, "f1": 0}
    assert cases["A, C", "A,C"] == {"em": 0, "f1": 0}
    assert cases["", "A"] == {"em": 0, "f1": 0}  # MERA missing-gold guard


def test_exact_source_receipt_cannot_claim_server_verification_or_test_execution():
    assert RECEIPT["status"] == "DEV"
    assert RECEIPT["server_metric_certainty"] == "UNKNOWN"
    assert RECEIPT["private_test_ready"] is False
    assert RECEIPT["maintainer_contacted"] is False
    assert RECEIPT["scoring_submission_sent"] is False
    assert RECEIPT["benchmark_content_downloaded"] is False
    assert RECEIPT["synthetic_only"] is True
    assert all(row["synthetic"] for row in RECEIPT["diagnostics_synthetic"])
    assert RECEIPT["fetch_failures"] == []
    assert RECEIPT["api_pagination_unread"] == []


def test_exact_source_execution_fails_closed_for_unknown_source_hash():
    with pytest.raises(ValueError, match="hash mismatch"):
        AUDIT.reproduce(b"def process_results(doc, results): return {'em': 1}", b"unknown source")


def test_function_extraction_does_not_execute_remote_module_initialization():
    source = "raise RuntimeError('must not run')\ndef wanted(value):\n    return value + 1\n"
    extracted = AUDIT.extract_functions(source, {"wanted"}, {})
    assert extracted["wanted"](2) == 3
    with pytest.raises(ValueError, match="functions missing"):
        AUDIT.extract_functions(source, {"missing"}, {})


def test_function_extraction_rejects_unexpected_decorators():
    with pytest.raises(ValueError, match="decorator"):
        AUDIT.extract_functions("@remote_side_effect\ndef wanted(): return 1", {"wanted"}, {})


def test_maintainer_drafts_remain_unsent_with_joint_authorship():
    for language in ("RU", "EN"):
        content = (ROOT / f"docs/MERA_MAINTAINER_MESSAGE_READY_{language}.md").read_text(encoding="utf-8")
        assert "NOT_SENT" in content
        assert "Antoniy Sarychev" in content and "Denis Shesternin" in content
        assert "7752f19d1658ba80f5f34144895c26dd1bf5239d" in content


def test_recheck_claims_are_hash_bound_development_evidence():
    from agro_route.mera_screen_analysis_20261003 import validate_claims
    claims = json.loads((ROOT / "results/20261003_mera_scorer_recheck_verified/claim_provenance.json").read_text(encoding="utf-8"))
    assert all(claim["status"] == "DEV" for claim in claims)
    assert validate_claims(claims, ROOT) == {"valid": True, "claim_count": 5}
