# SPDX-License-Identifier: Apache-2.0
"""Candidate scorer and typed public-evidence verifier; DEV ONLY.

This module is deliberately not wired into historical policies. It does not
claim to verify arbitrary natural-language agronomic entailment. Unsupported
references fail closed. A typed verification contract is PUBLIC task data, never
gold: all branches, entities, measurements and requested fields are supplied.
"""
from __future__ import annotations

import copy
import json
import math
import re
import unicodedata

VERSION = "scorer-verifier-v2-dev-20261003"
ACTIONS = {"ANSWER", "ASK_FOR_DATA", "ABSTAIN"}
OUTPUT_KEYS = {"action", "answer", "numeric", "unit", "tool", "components", "requested_fields", "reason_code", "evidence_ids"}
PRIVATE_KEYS = {
    "expected", "expected_v2", "gold", "label", "labels", "category", "split",
    "provisional_answer", "provisional_expected_action", "human_review",
    "answer_key", "correct_answer", "correct_action", "correct_branch", "target_label",
    "hidden_answer", "scoring", "reference_answer",
}
# Orthographic aliases only. No silent conversion of dimensions or values.
UNIT_ALIASES = {
    "mm": "mm", "мм": "mm", "kPa": "kPa", "кПа": "kPa",
    "degC day": "degC day", "°C day": "degC day", "°C·day": "degC day",
    "mm/day": "mm/day", "мм/сут": "mm/day", "C": "C", "°C": "C",
    "%": "%", "m3/ha": "m3/ha", "m³/ha": "m3/ha", "m³/га": "m3/ha",
}


def normalize(text):
    """Preserve entities, negation, punctuation and conjunction; normalize spaces."""
    return " ".join(unicodedata.normalize("NFKC", text).strip().split())


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Non-finite or non-numeric value")
    return float(value)


def _reject_private(value):
    if isinstance(value, dict):
        def private(key):
            if not isinstance(key, str):
                return True
            normalized = key.casefold()
            return normalized in PRIVATE_KEYS or normalized.startswith(("expected", "gold", "provisional")) or any(part in {"expected", "gold"} for part in normalized.split("_"))
        if any(private(key) for key in value):
            raise ValueError("Private evaluation metadata in public request")
        for item in value.values():
            _reject_private(item)
    elif isinstance(value, list):
        for item in value:
            _reject_private(item)


def public_request_v2(sample):
    """Deep projection with recursive leak guard; caller must not serialize sample."""
    request = copy.deepcopy({k: sample[k] for k in ("input", "context", "inputs") if k in sample})
    _reject_private(request)
    return request


def parse_output_v2(text):
    # Strict JSON. Wrappers are reported as formatting/parsing failures, not fixed.
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    def reject_constant(value):
        raise ValueError("Invalid JSON constant " + value)
    output = json.loads(text, object_pairs_hook=pairs, parse_constant=reject_constant)
    errors = schema_errors(output)
    if errors:
        raise ValueError("; ".join(errors))
    return output


def schema_errors(output):
    if not isinstance(output, dict):
        return ["schema"]
    errors = []
    if not {"action", "answer", "numeric", "unit"} <= set(output):
        errors.append("schema")
    if set(output) - OUTPUT_KEYS:
        errors.append("schema")
    if not isinstance(output.get("action"), str) or output.get("action") not in ACTIONS:
        errors.append("action")
    if not isinstance(output.get("answer"), str) or not output.get("answer", "").strip():
        errors.append("incomplete_response")
    try:
        if output.get("numeric") is not None:
            _finite(output["numeric"])
    except ValueError:
        errors.append("schema")
    if output.get("unit") is not None and not isinstance(output["unit"], str):
        errors.append("schema")
    if isinstance(output.get("action"), str) and output.get("action") in {"ASK_FOR_DATA", "ABSTAIN"}:
        if output.get("numeric") is not None or output.get("unit") is not None:
            errors.append("unsupported_numeric_claim")
        if output.get("components"):
            errors.append("unsupported_components")
    return sorted(set(errors))


def _unit(unit):
    return UNIT_ALIASES.get(unit) if isinstance(unit, str) else None


def _match_number(output, reference):
    problems = []
    if not isinstance(reference.get("unit"), str) or not reference["unit"]:
        raise ValueError("Numeric reference must declare its unit")
    try:
        actual = _finite(output.get("numeric"))
        target = _finite(reference["numeric"])
        rel = _finite(reference.get("rel_tol", .01))
        absolute = _finite(reference.get("abs_tol", .02))
        if rel < 0 or absolute < 0:
            raise ValueError("Negative tolerance")
        if not math.isclose(actual, target, rel_tol=rel, abs_tol=absolute):
            problems.append("numeric_result")
    except (ValueError, KeyError, TypeError):
        problems.append("schema")
    # Unknown units can match exactly only if the reference explicitly declares it.
    actual_unit, target_unit = output.get("unit"), reference.get("unit")
    canonical = _unit(target_unit)
    if actual_unit != target_unit and (canonical is None or _unit(actual_unit) != canonical):
        problems.append("unit")
    # Do not accept a contradictory display field alongside a correct numeric.
    displayed = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*(.*)", output.get("answer", "") if isinstance(output.get("answer"), str) else "")
    if not displayed:
        problems.append("numeric_display_format")
    else:
        try:
            if not math.isclose(float(displayed[1]), _finite(output.get("numeric")), rel_tol=1e-5, abs_tol=1e-8):
                problems.append("contradictory_display")
            if displayed[2] and displayed[2] != actual_unit and (_unit(actual_unit) is None or _unit(displayed[2]) != _unit(actual_unit)):
                problems.append("unit_display")
        except (ValueError, TypeError):
            problems.append("schema")
    return problems


def _match_answer(output, reference):
    problems = []
    if "numeric" in reference:
        problems.extend(_match_number(output, reference))
    if "answers" in reference:
        if not isinstance(output.get("answer"), str) or normalize(output["answer"]) not in {normalize(x) for x in reference["answers"]}:
            problems.append("answer_content")
        if "numeric" not in reference and (output.get("numeric") is not None or output.get("unit") is not None):
            problems.append("unexpected_numeric_claim")
    components = output.get("components", {})
    if "components" in reference:
        if not isinstance(components, dict) or set(components) != set(reference["components"]):
            problems.append("incomplete_compound_answer")
        else:
            for key, ref in reference["components"].items():
                if not isinstance(components[key], dict):
                    problems.append("schema")
                else:
                    problems.extend(key + ":" + p for p in _match_answer(components[key], ref))
    return problems


def score_dev(sample, output):
    """Score new DEV fixtures only. Historical/home-final/review IDs are rejected."""
    if sample.get("split") != "dev" or str(sample.get("id", "")).startswith(("home_final_", "review20261002_")):
        raise ValueError("v2 accepts DEV only; historical HOME150 and review40 are frozen")
    reference = sample.get("expected_v2")
    if not isinstance(reference, dict) or not isinstance(reference.get("action"), str) or reference.get("action") not in ACTIONS:
        raise ValueError("Explicit v2 reference required")
    errors = schema_errors(output)
    if not errors:
        if output["action"] != reference["action"]:
            errors.append("action")
        elif reference["action"] == "ANSWER":
            if not any(k in reference for k in ("numeric", "answers", "components")):
                raise ValueError("ANSWER reference has no checkable content")
            errors.extend(_match_answer(output, reference))
        elif reference["action"] == "ASK_FOR_DATA":
            required = reference.get("required_fields")
            if not isinstance(required, list) or not required:
                raise ValueError("ASK reference must declare missing fields")
            supplied = output.get("requested_fields")
            if not isinstance(supplied, list) or not all(isinstance(x, str) for x in supplied) or set(supplied) != set(required):
                errors.append("missing_clarification")
            if output.get("reason_code") != "MISSING_INPUTS":
                errors.append("reason")
            if "answers" in reference:
                errors.extend(_match_answer(output, reference))
        else:
            if reference.get("reason_code") != "INSUFFICIENT_REFERENCE":
                raise ValueError("ABSTAIN reference must declare insufficiency")
            if output.get("reason_code") != reference["reason_code"]:
                errors.append("reason")
            if "answers" in reference:
                errors.extend(_match_answer(output, reference))
    return {"version": VERSION, "scope": "DEV_ONLY", "correct": not errors, "failure_types": sorted(set(errors)), "human_review": False}


def _rule(node, facts, entity, evidence):
    if not isinstance(node, dict):
        raise ValueError("Invalid rule")
    if set(node) == {"all"} or set(node) == {"any"}:
        name = next(iter(node))
        children = node[name]
        if not isinstance(children, list) or not children:
            raise ValueError("Empty conjunction/disjunction")
        values = [_rule(c, facts, entity, evidence) for c in children]
        return all(values) if name == "all" else any(values)
    if set(node) == {"not"}:
        return not _rule(node["not"], facts, entity, evidence)
    if set(node) != {"field", "op", "value", "unit"}:
        raise ValueError("Unsupported predicate")
    candidates = [f for f in facts if f.get("entity") == entity and f.get("field") == node["field"]]
    if len(candidates) != 1:
        raise ValueError("Missing or ambiguous entity fact")
    fact = candidates[0]
    if not isinstance(fact.get("id"), str) or not fact["id"]:
        raise ValueError("Fact ID required")
    evidence.add(fact["id"])
    if _unit(node["unit"]) is None or _unit(fact.get("unit")) != _unit(node["unit"]):
        raise ValueError("Unit mismatch")
    left, right = _finite(fact.get("value")), _finite(node["value"])
    op = node["op"]
    if op == ">":
        return left > right
    if op == "<":
        return left < right
    if op == ">=":
        return left >= right
    if op == "<=":
        return left <= right
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    raise ValueError("Unsupported operator")


def verify_public_dev(request, output):
    """No expected/gold argument. Accept typed entity facts and explicit full rules.

    Status ACCEPT means agreement with the public structured contract. It is not
    a claim of truth of underlying sources or general agronomic safety.
    """
    if set(request) - {"input", "context", "inputs"}:
        raise ValueError("Verifier requires a public request projection")
    _reject_private(request)
    errors = schema_errors(output)
    inputs = request.get("inputs", {})
    if not isinstance(inputs, dict):
        return {"version": VERSION, "accepted": False, "status": "UNKNOWN", "reasons": ["invalid_public_inputs"]}
    contract = inputs.get("verification")
    if not isinstance(contract, dict):
        return {"version": VERSION, "accepted": False, "status": "UNKNOWN", "reasons": errors or ["typed_reference_required"]}
    kind = contract.get("kind")
    if not isinstance(kind, str) or kind not in {"rule", "fact", "calculation"}:
        return {"version": VERSION, "accepted": False, "status": "UNKNOWN", "reasons": ["invalid_or_unsupported_reference"]}
    if kind in {"rule", "fact"} and (not isinstance(contract.get("entity"), str) or not contract["entity"] or not isinstance(contract.get("facts"), list) or not all(isinstance(f, dict) for f in contract["facts"])):
        return {"version": VERSION, "accepted": False, "status": "UNKNOWN", "reasons": ["invalid_entity_reference"]}
    if kind == "fact" and (not isinstance(contract.get("field"), str) or not contract["field"]):
        return {"version": VERSION, "accepted": False, "status": "UNKNOWN", "reasons": ["invalid_field_reference"]}
    required = contract.get("required_fields", [])
    values = inputs.get("measurements", {})
    if not isinstance(required, list) or not all(isinstance(f, str) for f in required) or not isinstance(values, dict):
        return {"version": VERSION, "accepted": False, "status": "UNKNOWN", "reasons": ["invalid_required_fields"]}
    missing = [field for field in required if values.get(field) is None]
    action = output.get("action") if isinstance(output, dict) else None
    if missing:
        requested = output.get("requested_fields") if isinstance(output, dict) else None
        if action != "ASK_FOR_DATA" or output.get("reason_code") != "MISSING_INPUTS" or not isinstance(requested, list) or not all(isinstance(f, str) for f in requested) or set(requested) != set(missing):
            errors.append("missing_clarification")
    elif contract.get("kind") == "fact" and contract.get("scope") == "closed_world_supplied_facts" and isinstance(contract.get("facts"), list) and not any(f.get("entity") == contract.get("entity") and f.get("field") == contract.get("field") for f in contract["facts"] if isinstance(f, dict)):
        if action != "ABSTAIN" or output.get("reason_code") != "INSUFFICIENT_REFERENCE":
            errors.append("insufficient_reference")
    elif action != "ANSWER":
        errors.append("action")
    else:
        try:
            if contract.get("kind") == "rule":
                evidence = set()
                truth = _rule(contract["rule"], contract["facts"], contract["entity"], evidence)
                branches = contract["branches"]
                if set(branches) != {"true", "false"} or not all(isinstance(x, str) and x for x in branches.values()):
                    raise ValueError("Both public branches required")
                if output["answer"] != branches["true" if truth else "false"]:
                    errors.append("wrong_branch")
                given_ids = output.get("evidence_ids")
                if not isinstance(given_ids, list) or not all(isinstance(x, str) for x in given_ids) or set(given_ids) != evidence:
                    errors.append("incomplete_evidence")
                if output.get("numeric") is not None or output.get("unit") is not None:
                    errors.append("unexpected_numeric_claim")
            elif contract.get("kind") == "fact":
                candidates = [f for f in contract["facts"] if f.get("entity") == contract["entity"] and f.get("field") == contract["field"]]
                if len(candidates) != 1 or not isinstance(candidates[0].get("text"), str):
                    raise ValueError("Missing or ambiguous fact")
                fact = candidates[0]
                if normalize(output["answer"]) != normalize(fact["text"]):
                    errors.append("wrong_entity_or_content")
                if output.get("evidence_ids") != [fact["id"]]:
                    errors.append("incomplete_evidence")
                if output.get("numeric") is not None or output.get("unit") is not None:
                    errors.append("unexpected_numeric_claim")
            elif contract.get("kind") == "calculation":
                # Public independent executor; no expected labels enter its input.
                from .tools import REQUIRED, execute
                tool = contract["tool"]
                if tool not in REQUIRED or set(required) != set(REQUIRED[tool]):
                    raise ValueError("Declared calculation inputs incomplete")
                numeric_reference = execute(tool, values)
                errors.extend(_match_number(output, numeric_reference))
            else:
                raise ValueError("Unsupported public contract")
        except (ValueError, KeyError, TypeError, AttributeError):
            return {"version": VERSION, "accepted": False, "status": "UNKNOWN", "reasons": ["invalid_or_unsupported_reference"]}
    return {"version": VERSION, "accepted": not errors, "status": "ACCEPT" if not errors else "REJECT", "reasons": sorted(set(errors))}
