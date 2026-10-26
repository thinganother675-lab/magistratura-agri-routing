# SPDX-License-Identifier: Apache-2.0
"""Separate MERA integration; no historical scorer, gold lookup, or upload.

The official text metric is SQuAD-style. Its removal of the article 'a'
also removes option A. Keep that behavior visible, never silently correct it.
All test fixtures in this project's tests are independently invented.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import string
import zipfile

DATASET = "MERA-evaluation/ruTXTAgroBench"
HF_REVISION = "b00011342a8f5f1e7968edaa2f6d50545a1e8f79"
MERA_REVISION = "7752f19d1658ba80f5f34144895c26dd1bf5239d"
TASK_NAME = "ruTXTAgroBench"
OPTION_KEYS = tuple("option_" + c.lower() for c in "ABCDEFGH")
GOLD_KEYS = frozenset({"outputs", "gold", "expected", "answer", "reference_answer", "label", "labels"})


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def forbid_gold(value):
    """Reject references recursively at inference/router and packaging boundaries."""
    if isinstance(value, dict):
        if GOLD_KEYS.intersection(value):
            raise ValueError("Reference/gold fields are forbidden at inference boundary")
        for child in value.values():
            forbid_gold(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            forbid_gold(child)


@dataclass(frozen=True)
class InferenceItem:
    item_id: int
    split: str
    prompt: str
    options: tuple[str, ...]
    domain: str

    def public(self):
        result = asdict(self)
        forbid_gold(result)
        return result


def adapt_row(row, split):
    """HF train is public DEV. Test references must all be blank, never consumed."""
    if split not in {"dev", "test"}:
        raise ValueError("Use explicit dev/test roles, not HF train as training permission")
    if split == "test" and row.get("outputs") not in (None, ""):
        raise ValueError("Private TEST reference unexpectedly present: stop")
    inputs, meta = row["inputs"], row["meta"]
    if not isinstance(meta.get("id"), int) or isinstance(meta["id"], bool):
        raise ValueError("Dataset item id must be an integer")
    options = tuple(letter for letter, key in zip("ABCDEFGH", OPTION_KEYS)
                    if isinstance(inputs.get(key), str) and inputs[key].strip())
    if not 4 <= len(options) <= 8:
        raise ValueError("Expected 4-8 supplied choices")
    # Explicit whitelist: never interpolate outputs or arbitrary reference fields.
    fields = {"question": inputs["question"], **{key: inputs.get(key) for key in OPTION_KEYS},
              "domain": meta["domain"], "id": meta["id"]}
    prompt = row["instruction"].format(**fields)
    return InferenceItem(meta["id"], split, prompt, options, meta["domain"])


def isolate_dev_references(rows):
    items, references = [], {}
    for row in rows:
        item = adapt_row(row, "dev")
        if item.item_id in references:
            raise ValueError("Duplicate development id")
        if not isinstance(row.get("outputs"), str) or not row["outputs"].strip():
            raise ValueError("DEV reference missing")
        items.append(item)
        references[item.item_id] = row["outputs"]
    return items, references


def official_normalize(text):
    # Compatible with transformers.data.metrics.squad_metrics.normalize_answer.
    lowered = str(text).lower()
    without_punctuation = "".join(c for c in lowered if c not in string.punctuation)
    return " ".join(re.sub(r"\b(a|an|the)\b", " ", without_punctuation).split())


def official_scores(reference, prediction):
    gold, pred = official_normalize(reference), official_normalize(prediction)
    gold_tokens, pred_tokens = gold.split(), pred.split()
    overlap = sum((Counter(gold_tokens) & Counter(pred_tokens)).values())
    if not gold_tokens or not pred_tokens:
        f1 = float(gold_tokens == pred_tokens)
    elif not overlap:
        f1 = 0.0
    else:
        precision, recall = overlap / len(pred_tokens), overlap / len(gold_tokens)
        f1 = 2 * precision * recall / (precision + recall)
    return {"exact_match": int(gold == pred), "f1": f1}


@dataclass(frozen=True)
class NormalizedAnswer:
    canonical: str
    choices: tuple[str, ...]
    status: str
    strict_format: bool


def normalize_options(text, allowed, *, reference=False):
    """Parse letter sets, never inspect correctness or infer an option from prose.

    Only an unambiguous leading 'Ответ:'/'Answer:' clause may be extracted
    from prose. Rejected ambiguous prose does not acquire a guessed answer.
    Cyrillic lookalikes are allowed only for diagnostic public reference parsing;
    the official original reference string remains intact for official scores.
    """
    if not isinstance(text, str):
        return NormalizedAnswer("", (), "invalid_type", False)
    cleaned = text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = re.sub(r"^```(?:text)?\s*", "", cleaned[:-3]).strip()
    if reference:
        cleaned = cleaned.translate(str.maketrans({"А": "A", "В": "B", "С": "C", "Е": "E", "Н": "H"}))
    strict = bool(re.fullmatch(r"[A-H](?:, [A-H])*", text))
    candidate, mode = cleaned, "format_only"
    labelled = re.match(r"^(?:ответ|answer)\s*:\s*([A-Ha-h](?:\s*[,;]\s*[A-Ha-h])*)\s*(?:[.!]|$)", cleaned, re.I)
    if labelled:
        candidate, mode = labelled[1], "explicit_answer_clause"
        # Another explicit answer clause or subsequent option list is ambiguous.
        remainder = cleaned[labelled.end():]
        if re.search(r"(?:ответ|answer)\s*:|(?<!\w)[A-H](?:\s*[,;]\s*[A-H])+(?!\w)", remainder, re.I):
            return NormalizedAnswer("", (), "ambiguous_prose", False)
    if not re.fullmatch(r"[A-Ha-h](?:\s*[,;\s]\s*[A-Ha-h])*", candidate):
        return NormalizedAnswer("", (), "invalid_format", False)
    letters = tuple(sorted(set(re.findall(r"[A-H]", candidate.upper()))))
    if not letters or not set(letters).issubset(allowed):
        return NormalizedAnswer("", (), "option_out_of_range", False)
    return NormalizedAnswer(", ".join(letters), letters, mode, strict and text == ", ".join(letters))


def diagnostic_set_scores(reference, prediction, options):
    gold = normalize_options(reference, options, reference=True)
    pred = normalize_options(prediction, options)
    if not gold.choices:
        return {"set_exact_match": None, "set_f1": None, "reference_issue": True}
    overlap = len(set(gold.choices) & set(pred.choices))
    f1 = 2 * overlap / (len(gold.choices) + len(pred.choices)) if pred.choices else 0.0
    return {"set_exact_match": int(gold.choices == pred.choices), "set_f1": f1,
            "reference_issue": gold.canonical != reference}


def route_local(result, *, threshold=None):
    """Reference-free rule. Confidence is lexical certainty, not truth probability."""
    forbid_gold(result)
    if result.get("error") or not result.get("valid_options"):
        return "cloud"
    if threshold is not None:
        value = result.get("option_token_confidence")
        if value is None or not math.isfinite(value) or value < threshold:
            return "cloud"
    return "local"


def ensure_restricted_path(path, root):
    path, root = Path(path).resolve(), Path(root).resolve()
    if not path.is_relative_to(root / ".runtime" / "mera"):
        raise ValueError("Benchmark source/output/submission artifacts must stay in ignored .runtime/mera")
    return path


def submission_object(predictions, expected_ids):
    """Official data/test/id/outputs schema. No sources, reference labels or scores."""
    expected_ids = list(expected_ids)
    if any(isinstance(i, bool) or not isinstance(i, int) for i in expected_ids):
        raise ValueError("Official dataset IDs must be integers, never booleans")
    if len(set(expected_ids)) != len(expected_ids) or not expected_ids:
        raise ValueError("Expected IDs must be nonempty and unique")
    ids = []
    records = []
    for prediction in predictions:
        forbid_gold(prediction)
        if set(prediction) != {"item_id", "prediction", "split"} or prediction["split"] != "test":
            raise ValueError("Package only explicit TEST inference records")
        if not isinstance(prediction["prediction"], str):
            raise ValueError("Prediction must be a string; failed generation remains empty")
        if isinstance(prediction["item_id"], bool) or not isinstance(prediction["item_id"], int):
            raise ValueError("Prediction ID must be an integer, never a boolean")
        ids.append(prediction["item_id"])
        records.append({"outputs": prediction["prediction"], "meta": {"id": prediction["item_id"]}})
    if len(ids) != len(set(ids)) or set(ids) != set(expected_ids):
        raise ValueError("Submission must have exactly one output for every official TEST ID")
    by_id = {r["meta"]["id"]: r for r in records}
    return {"data": {"test": [by_id[i] for i in expected_ids]}}


def package_submission(predictions, expected_ids, logs_public_zip, destination, *, root, manifest):
    """Local packaging only. Requires original official logs, never fabricates them.

    Structure reproduced from official log_to_submission.py. Online acceptance
    remains unverified until an authorized actual official service submission.
    """
    destination = ensure_restricted_path(destination, root)
    logs_public_zip = ensure_restricted_path(logs_public_zip, root)
    forbid_gold(manifest)
    obj = submission_object(predictions, expected_ids)
    if destination.exists() or not logs_public_zip.is_file():
        raise ValueError("Use a new path and existing official logs_public.zip")
    if not zipfile.is_zipfile(logs_public_zip):
        raise ValueError("Official logs archive is not a ZIP")
    required = {"code_commit", "model_id", "quantization", "prompt_sha256", "runtime",
                "mera_revision", "dataset_revision", "policy", "protocol_sha256"}
    if not required.issubset(manifest) or any(not manifest[k] for k in required):
        raise ValueError("Incomplete reproducibility manifest")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(TASK_NAME + ".json", canonical_json(obj))
        archive.write(logs_public_zip, "logs_public.zip")
    return {**manifest, "archive_sha256": sha256_bytes(destination.read_bytes()),
            "archive_bytes": destination.stat().st_size, "submission_status": "NOT_SUBMITTED",
            "service_acceptance": "UNVERIFIED", "redistribution": "DO_NOT_REDISTRIBUTE"}


def ingest_remote_score(record, *, expected_archive_sha256):
    """Validate a human-imported response; no guessed scores or invented per-item CI."""
    forbid_gold(record)
    required = {"submission_id", "submission_timestamp", "archive_sha256", "source_url", "metrics"}
    if set(record) != required or record["archive_sha256"] != expected_archive_sha256:
        raise ValueError("Remote score provenance mismatch")
    if not all(isinstance(record[k], str) and record[k].strip() for k in required - {"metrics"}):
        raise ValueError("Missing official response provenance")
    metrics = record["metrics"]
    if set(metrics) != {"exact_match", "f1"}:
        raise ValueError("Import explicitly identified official aggregate metrics")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
           or not 0 <= v <= 1 for v in metrics.values()):
        raise ValueError("Metric scale must be explicitly converted to 0..1")
    return {**record, "status": "IMPORTED_AGGREGATE_ONLY", "paired_ci_available": False,
            "gold_available": False, "per_item_correctness_available": False}
