# SPDX-License-Identifier: Apache-2.0
"""Prepare blind forms; validate two real returned forms before adjudication.

Never completes review itself. Every write creates a new directory. Old review40,
question/gold files and returned reviewer files are immutable input evidence.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results/20261002_170443Z_21722066_dataset_literature/human_review_pack"
JUDGMENTS = {"CORRECT", "INCORRECT", "AMBIGUOUS", "INSUFFICIENT_REFERENCE", "TRANSLATION_PROBLEM", "DOMAIN_EXPERT_NEEDED"}
ACTIONS = {"ANSWER", "ASK_FOR_DATA", "ABSTAIN"}
REVIEWERS = {"A": "Antoniy Sarychev", "B": "Denis Shesternin"}
STATIC_FIELDS = ("review_id", "reviewer", "language", "question", "reference_file")
FIELDS = (*STATIC_FIELDS, "judgment", "expected_action", "reference_answer", "numeric", "unit", "note")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(FIELDS):
            raise ValueError("Unexpected reviewer form columns")
        rows = list(reader)
        if any(set(row) != set(FIELDS) or not all(isinstance(value, str) for value in row.values()) for row in rows):
            raise ValueError("Malformed CSV row")
        return rows


def _write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def prepare(destination, source=SOURCE):
    if destination.exists():
        raise FileExistsError("Reviewer pack exists; choose a new directory")
    source_files = sorted(p for p in source.iterdir() if p.is_file())
    before = {p.name: sha(p) for p in source_files}
    questions = [json.loads(line) for line in (source / "blinded_questions.jsonl").read_text(encoding="utf-8").splitlines()]
    if len(questions) != 40 or len({q["id"] for q in questions}) != 40 or any(q.get("human_review") is not False for q in questions):
        raise ValueError("Expected the original 40 unreviewed questions")
    if len({q["context"] for q in questions}) != 1:
        raise ValueError("Prepare explicit per-reference files for a new pack")
    reference = json.loads(questions[0]["context"])
    pack_id = destination.name
    mapping = {"R" + hashlib.sha256((pack_id + q["id"]).encode()).hexdigest()[:12]: q["id"] for q in questions}
    inverse = {original: review_id for review_id, original in mapping.items()}
    destination.mkdir(parents=True, exist_ok=False)
    public_rows = []
    for q in questions:
        public_rows.append({"review_id": inverse[q["id"]], "language": q["language"], "question": q["question"],
                            "reference_file": "reference_weather.json", "judgment": "", "expected_action": "", "reference_answer": "", "numeric": "", "unit": "", "note": ""})
    forms = {}
    for letter, reviewer in REVIEWERS.items():
        folder = destination / ("reviewer_" + letter)
        folder.mkdir()
        rows = [{**q, "reviewer": reviewer} for q in public_rows]
        random.Random(20261003 + ord(letter)).shuffle(rows)
        filename = "reviewer_" + letter + "_" + ("antoniy" if letter == "A" else "denis") + ".csv"
        _write_csv(folder / filename, rows)
        (folder / "reference_weather.json").write_text(json.dumps(reference, ensure_ascii=False, indent=2), encoding="utf-8")
        (folder / "instructions_RU.md").write_text(
            "# Независимая слепая проверка задач и опорных данных\n\n"
            f"Рецензент {letter}: {reviewer}. human_review=false до реального возврата заполненной формы.\n\n"
            "Это 40 НЕЗАПУЩЕННЫХ задач (20 RU/EN пар), а не ответы моделей. Judgment оценивает корректность и проверяемость постановки по источнику; CORRECT не означает измеренную точность модели. Для CORRECT самостоятельно заполните expected_action (ANSWER / ASK_FOR_DATA / ABSTAIN) и reference_answer, при численном ответе также numeric и unit. Сначала работайте независимо от второго рецензента и не открывайте старый provisional gold.\n\n"
            "Judgment для каждой строки: CORRECT; INCORRECT; AMBIGUOUS; INSUFFICIENT_REFERENCE; TRANSLATION_PROBLEM; DOMAIN_EXPERT_NEEDED. Последний используйте для агрономического факта вне вашей компетенции; не изображайте экспертизу агронома. Note необязателен. Не меняйте review_id, reviewer, language, question, reference_file. Все 40 judgments обязательны; проблемный gold не нужно угадывать.\n\n"
            "ASK_FOR_DATA означает, что конечный расчёт может стать определённым после конкретных измерений; ABSTAIN — материал не поддерживает запрошенный фактический вывод. Объясните недостающую опору в reference_answer. ANSWER относится к полностью заданной авторской экспериментальной формуле или правилу, а не к агрономической рекомендации.\n\n"
            "Сохраните заполненную форму в новом файле, не поверх шаблона. Создайте отдельный attestation JSON: reviewer — ваше полное имя выше; completed_by_human=true; completed_utc — фактическое время ISO 8601 с часовым поясом; form_sha256 — SHA256 заполненного CSV. Передайте оба файла исследователю для нового запуска adjudication. Никаких учётных данных не требуется.\n\n"
            "Источник: Open-Meteo archive API, ECMWF/Copernicus ERA5, CC BY 4.0; сеточный реанализ, не измерения на ферме. URL источника: " + questions[0]["source_url"] + "\n",
            encoding="utf-8")
        forms[letter] = {"path": (folder / filename).relative_to(destination).as_posix(), "reviewer": reviewer, "sha256": sha(folder / filename)}
    private = destination / "private_provenance"
    private.mkdir()
    (private / "id_mapping.json").write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    manifest = {"pack_id": pack_id, "actual_created_utc": datetime.now(timezone.utc).isoformat(), "human_review": False,
                "inference_run": False, "scientific_status": "AWAITING_TWO_INDEPENDENT_HUMAN_FORMS", "rows_per_reviewer": 40,
                "source_scenario_groups": 20, "source_blocks": 1, "confirmatory_eligible": False,
                "classification_target": "QUESTION_AND_REFERENCE_VALIDITY_NOT_MODEL_ACCURACY", "forms": forms,
                "source_directory": source.relative_to(ROOT).as_posix() if source.is_relative_to(ROOT) else str(source),
                "original_pack_hashes": before, "private_mapping_sha256": sha(private / "id_mapping.json"),
                "limitations": ["One ERA5 block; translated pairs are dependent", "No model answers exist for review40", "Candidate gold must be authored by the humans", "Agronomic expertise not established"]}
    manifest["public_files"] = {p.relative_to(destination).as_posix(): sha(p) for p in destination.rglob("*") if p.is_file() and "private_provenance" not in p.parts}
    (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if before != {p.name: sha(p) for p in source_files}:
        raise RuntimeError("Original review pack changed")
    return manifest


def validate_return(pack, letter, returned, attestation):
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    for relative, expected_hash in manifest["public_files"].items():
        if sha(pack / relative) != expected_hash:
            raise ValueError("Original blind template/reference bytes changed")
    template = pack / manifest["forms"][letter]["path"]
    if sha(template) != manifest["forms"][letter]["sha256"]:
        raise ValueError("Original blind template bytes changed")
    info = json.loads(attestation.read_text(encoding="utf-8"))
    if info.get("completed_by_human") is not True or info.get("reviewer") != REVIEWERS[letter] or info.get("form_sha256") != sha(returned):
        raise ValueError("A matching human attestation is required")
    try:
        timestamp = datetime.fromisoformat(info["completed_utc"].replace("Z", "+00:00"))
        created = datetime.fromisoformat(manifest["actual_created_utc"])
        if timestamp.tzinfo is None or timestamp > datetime.now(timezone.utc) or timestamp < created:
            raise ValueError("Invalid completion timestamp")
    except (KeyError, ValueError, TypeError):
        raise ValueError("Actual timezone-aware completion time required") from None
    original, rows = read_csv(template), read_csv(returned)
    originals = {r["review_id"]: r for r in original}
    if len(rows) != len(original) or len({r["review_id"] for r in rows}) != len(rows) or {r["review_id"] for r in rows} != set(originals):
        raise ValueError("Both humans must return every original row, exactly once")
    result = {}
    for row in rows:
        if any(row[field] != originals[row["review_id"]][field] for field in STATIC_FIELDS):
            raise ValueError("Blind task identity or reference was edited")
        if row["judgment"] not in JUDGMENTS:
            raise ValueError("Blank/incomplete or invalid judgment; no human review may be claimed")
        if row["judgment"] == "CORRECT" and (row["expected_action"] not in ACTIONS or not row["reference_answer"].strip()):
            raise ValueError("CORRECT requires independently authored action and answer")
        if row["expected_action"] and row["expected_action"] not in ACTIONS:
            raise ValueError("Invalid action")
        if row["numeric"]:
            try:
                value = Decimal(row["numeric"])
                if not value.is_finite() or not row["unit"] or row["expected_action"] != "ANSWER":
                    raise InvalidOperation
            except InvalidOperation:
                raise ValueError("Numeric gold needs a finite value, unit and ANSWER action") from None
        result[row["review_id"]] = row
    return result, info


def adjudicate(pack, form_a, attestation_a, form_b, attestation_b, destination):
    if destination.exists():
        raise FileExistsError("Adjudication output exists; choose a new directory")
    # Validate BOTH first; no partial output and no promotion of a blank form.
    a, info_a = validate_return(pack, "A", form_a, attestation_a)
    b, info_b = validate_return(pack, "B", form_b, attestation_b)
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    mapping_path = pack / "private_provenance/id_mapping.json"
    if sha(mapping_path) != manifest["private_mapping_sha256"]:
        raise ValueError("Private task mapping changed")
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    rows = []
    def value_tuple(row):
        number = str(Decimal(row["numeric"]).normalize()) if row["numeric"] else ""
        return row["expected_action"], " ".join(row["reference_answer"].split()), number, row["unit"]
    for review_id in sorted(a):
        left, right = a[review_id], b[review_id]
        agreed = left["judgment"] == right["judgment"] == "CORRECT" and value_tuple(left) == value_tuple(right)
        status = "AGREED_GOLD_CANDIDATE" if agreed else "DOMAIN_EXPERT_NEEDED" if "DOMAIN_EXPERT_NEEDED" in {left["judgment"], right["judgment"]} else "UNRESOLVED_AUTHOR_ADJUDICATION"
        rows.append({"id": mapping[review_id], "review_id": review_id, "reviewer_A": left, "reviewer_B": right,
                     "human_review": True, "adjudication_status": status,
                     "gold_candidate": {"action": left["expected_action"], "answer": left["reference_answer"], "numeric": left["numeric"], "unit": left["unit"]} if agreed else None,
                     "final_gold_frozen": False})
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "adjudication_candidates.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    receipt = {"human_review": True, "independent_reviews_attested": 2, "actual_utc": datetime.now(timezone.utc).isoformat(),
               "final_gold_frozen": False, "confirmatory_eligible": False, "semantic_disagreements_not_auto_resolved": True,
               "attestations": {"A": info_a, "B": info_b},
               "input_provenance": {str(p): sha(p) for p in (pack / "manifest.json", form_a, attestation_a, form_b, attestation_b)},
               "rows": len(rows), "agreed_gold_candidates": sum(r["adjudication_status"] == "AGREED_GOLD_CANDIDATE" for r in rows)}
    (destination / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("prepare")
    build.add_argument("--output", type=Path, required=True)
    review = sub.add_parser("adjudicate")
    for name in ("pack", "form-a", "attestation-a", "form-b", "attestation-b", "output"):
        review.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        report = prepare(args.output)
    else:
        report = adjudicate(args.pack, args.form_a, args.attestation_a, args.form_b, args.attestation_b, args.output)
    print(json.dumps({k: report[k] for k in ("human_review", "confirmatory_eligible")}, ensure_ascii=False))
