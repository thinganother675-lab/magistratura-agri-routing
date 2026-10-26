# SPDX-License-Identifier: Apache-2.0
"""Check source-bound claims without promoting DEV or revealing source values.

This validates recorded file/hash/value/commit consistency. It does not certify
scientific conclusions, consent, actual execution provenance, or agronomic gold.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Callable

STATUSES = {"HISTORICAL", "DEV", "SYSTEMS_TELEMETRY", "SIMULATED", "SUPPLEMENTARY", "CONFIRMATORY"}
REQUIRED_FIELDS = {"claim_id", "statement", "run_id", "file", "field", "value", "code_commit", "status", "data_sha256", "limitations"}
SOURCE_ROOTS = {"results", "docs", "manuscript", "experiments"}
FORBIDDEN_PARTS = {".git", ".runtime", ".cache", ".venv", ".aws", ".ssh", ".auth", "data", "private", "gold", "mera_restricted", "private_test"}
FORBIDDEN_FILENAME = re.compile(r"(?:private|gold|raw|question|prompt|response|prediction|credentials|secret)", re.I)
SECRET_FIELDS = {"api_key", "api-key", "authorization", "password", "secret", "credentials", "credential", "access_token", "refresh_token", "session_token", "bearer_token", "token"}
SECRET_FIELD_SUFFIX = re.compile(r"(?:^|[_-])(?:api[_-]?key|secret|password|credentials?|access_token|refresh_token|session_token|bearer_token)$", re.I)
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"(?<![\w-])sk-(?:ant-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?<!\w)hf_[A-Za-z0-9]{20,}"),
    re.compile(r"(?<!\w)(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,})"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9_.-]{24,}"),
    re.compile(r"(?<!\d)\d{8,12}:[A-Za-z0-9_-]{30,}"),
    re.compile(r"(?<!\w)(?:AKIA|ASIA)[A-Z0-9]{16}(?!\w)"),
)
MAX_SOURCE_BYTES = 4_194_304


class ProvenanceError(ValueError):
    """Diagnostic code only: no values, matched secrets, or source excerpts."""


def secret_like(value) -> bool:
    if isinstance(value, dict):
        return any(str(key).casefold() in SECRET_FIELDS or SECRET_FIELD_SUFFIX.search(str(key)) or secret_like(key) or secret_like(item) for key, item in value.items())
    if isinstance(value, list):
        return any(secret_like(item) for item in value)
    return isinstance(value, str) and any(pattern.search(value) for pattern in SECRET_PATTERNS)


def strict_json_loads(text: str):
    def invalid_constant(_):
        raise ProvenanceError("nonfinite_json")
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ProvenanceError("duplicate_json_key")
            result[key] = value
        return result
    try:
        return json.loads(text, parse_constant=invalid_constant, object_pairs_hook=unique_object)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ProvenanceError("invalid_json") from exc


def resolve_pointer(document, pointer: str):
    """Resolve RFC6901; malformed escapes and noncanonical indices fail closed."""
    if not isinstance(pointer, str) or (pointer and not pointer.startswith("/")):
        raise ProvenanceError("invalid_json_pointer")
    if pointer == "":
        return document
    value = document
    for encoded in pointer[1:].split("/"):
        if re.search(r"~(?![01])", encoded):
            raise ProvenanceError("invalid_pointer_escape")
        token = encoded.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict):
            if token not in value:
                raise ProvenanceError("pointer_not_found")
            value = value[token]
        elif isinstance(value, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", token):
                raise ProvenanceError("invalid_array_index")
            if len(token) > len(str(len(value))):
                raise ProvenanceError("pointer_not_found")
            index = int(token)
            if index >= len(value):
                raise ProvenanceError("pointer_not_found")
            value = value[index]
        else:
            raise ProvenanceError("pointer_scalar_traversal")
    return value


def exact_value(left, right) -> bool:
    """JSON type and value agree; True is not 1 and integers are not floats."""
    if type(left) is not type(right):
        return False
    if isinstance(left, float) and (not math.isfinite(left) or not math.isfinite(right)):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(exact_value(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(exact_value(a, b) for a, b in zip(left, right))
    return left == right


def safe_source_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        raise ProvenanceError("unsafe_source_path")
    parts = PurePosixPath(relative)
    if parts.is_absolute() or ".." in parts.parts or not parts.parts or parts.parts[0].casefold() not in SOURCE_ROOTS:
        raise ProvenanceError("unsafe_source_path")
    if any(part.casefold() in FORBIDDEN_PARTS or part.startswith(".") or FORBIDDEN_FILENAME.search(part) for part in parts.parts):
        raise ProvenanceError("forbidden_source_path")
    if parts.suffix.lower() != ".json":
        raise ProvenanceError("json_pointer_requires_json_source")
    root = root.resolve()
    path = root.joinpath(*parts.parts)
    for index in range(1, len(parts.parts) + 1):
        parent = root.joinpath(*parts.parts[:index])
        if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
            raise ProvenanceError("source_link_requires_review")
    if not path.resolve().is_relative_to(root):
        raise ProvenanceError("source_escapes_workspace")
    if not path.is_file():
        raise ProvenanceError("source_missing")
    return path


def git_commit_exists(root: Path, commit: str) -> bool:
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        return False
    try:
        result = subprocess.run(["git", "-C", str(root), "cat-file", "-e", commit + "^{commit}"], capture_output=True, timeout=10)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def confirmatory_authorized(document: dict, source) -> bool:
    return (document.get("independent_holdout") is True and document.get("authorized_protocol") is True
            and isinstance(source, dict) and source.get("independent_holdout") is True
            and source.get("private_test_run") is False
            and source.get("classification", source.get("status")) == "CONFIRMATORY")


def validate_provenance(document, root: Path, *, commit_checker: Callable[[str], bool] | None = None) -> dict:
    """Return safe counts and indexed diagnostic codes, never source/claim values."""
    receipt = {"valid": False, "claims_total": 0, "claims_verified": 0,
               "status_counts": {status: 0 for status in sorted(STATUSES)}, "errors": [],
               "scope": "FILE_HASH_POINTER_VALUE_COMMIT_CONSISTENCY_NOT_SCIENTIFIC_OR_CONSENT_CERTIFICATION"}

    def error(index, code):
        receipt["errors"].append({"claim_index": index, "code": code})

    if not isinstance(document, dict) or not isinstance(document.get("claims"), list) or not document["claims"]:
        error(None, "nonempty_claims_required")
        return receipt
    receipt["claims_total"] = len(document["claims"])
    if secret_like(document):
        error(None, "secret_like_provenance")
        return receipt
    checker = commit_checker or (lambda commit: git_commit_exists(root, commit))
    commits = {}
    cache = {}
    identifiers = set()
    bindings = document.get("run_code_commits", {})
    if not isinstance(bindings, dict):
        error(None, "invalid_run_code_commits")
        return receipt

    def existing(commit):
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
            return False
        if commit not in commits:
            commits[commit] = bool(checker(commit))
        return commits[commit]

    if "source_commit" in document and not existing(document["source_commit"]):
        error(None, "assembly_source_commit_invalid")
    if any(not isinstance(run, str) or not run or not existing(commit) for run, commit in bindings.items()):
        error(None, "recorded_run_commit_invalid")
    for index, claim in enumerate(document["claims"]):
        before = len(receipt["errors"])
        if not isinstance(claim, dict) or REQUIRED_FIELDS - claim.keys():
            error(index, "claim_fields_missing")
            continue
        identifier = claim["claim_id"]
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            error(index, "invalid_or_duplicate_claim_id")
        else:
            identifiers.add(identifier)
        for field in ("statement", "run_id"):
            if not isinstance(claim[field], str) or not claim[field].strip():
                error(index, "claim_text_identity_missing")
        limits = claim["limitations"]
        if not (isinstance(limits, str) or isinstance(limits, list) and all(isinstance(item, str) for item in limits)):
            error(index, "limitations_invalid")
        status = claim["status"]
        if not isinstance(status, str) or status not in STATUSES:
            error(index, "evidence_status_invalid")
        else:
            receipt["status_counts"][status] += 1
        if not existing(claim["code_commit"]):
            error(index, "code_commit_missing_or_invalid")
        if isinstance(claim["run_id"], str) and claim["run_id"] in bindings and bindings[claim["run_id"]] != claim["code_commit"]:
            error(index, "recorded_run_commit_mismatch")
        try:
            path = safe_source_path(root, claim["file"])
            if path not in cache:
                if path.stat().st_size > MAX_SOURCE_BYTES:
                    raise ProvenanceError("source_too_large")
                raw = path.read_bytes()
                source = strict_json_loads(raw.decode("utf-8-sig"))
                if secret_like(source):
                    raise ProvenanceError("secret_like_source")
                cache[path] = (hashlib.sha256(raw).hexdigest(), source)
            actual_sha, source = cache[path]
            if not isinstance(claim["data_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", claim["data_sha256"]):
                error(index, "data_sha256_invalid")
            elif claim["data_sha256"] != actual_sha:
                error(index, "source_sha256_mismatch")
            actual = resolve_pointer(source, claim["field"])
            if not exact_value(actual, claim["value"]):
                error(index, "source_value_mismatch")
            if isinstance(source, dict) and isinstance(source.get("run_id"), str) and source["run_id"] != claim["run_id"]:
                error(index, "source_run_id_mismatch")
            if isinstance(source, dict) and "code_commit" in source and source["code_commit"] != claim["code_commit"]:
                error(index, "source_recorded_commit_mismatch")
            if status == "CONFIRMATORY" and not confirmatory_authorized(document, source):
                error(index, "confirmatory_not_authorized_independent_source")
        except ProvenanceError as exc:
            error(index, str(exc))
        except (OSError, UnicodeError, TypeError, KeyError):
            error(index, "source_or_pointer_unreadable")
        if len(receipt["errors"]) == before:
            receipt["claims_verified"] += 1
    receipt["valid"] = not receipt["errors"] and receipt["claims_verified"] == receipt["claims_total"]
    return receipt
