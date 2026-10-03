# SPDX-License-Identifier: Apache-2.0
"""Build a private, allowlisted editor package; never start an editor or publish.

Historical manuscripts stay byte-for-byte unchanged. Latest appended tables and
provenance are the authority for a future separately requested revision.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
STATUSES = {"HISTORICAL", "DEV", "SYSTEMS_TELEMETRY", "SIMULATED", "SUPPLEMENTARY", "CONFIRMATORY"}
MANUSCRIPTS = ("manuscript/russian_routing_20261003.md", "manuscript/english_routing_20261003.md")
MAX_TEXT_BYTES = 1_048_576
MAX_FIGURE_BYTES = 10_485_760
FORBIDDEN_PARTS = {".git", ".runtime", ".cache", ".venv", ".aws", ".ssh", ".auth", "data", "mera_restricted", "private", "private_test", "tests", "node_modules"}
FORBIDDEN_NAMES = re.compile(r"(?:raw|gold|secret|credential|question|prompt|response|prediction|inference_metrics|scores|private_test)", re.I)
FORBIDDEN_FIELDS = {"prompt", "prompt_text", "messages", "content", "question", "question_text", "questions", "benchmark_input", "gold", "gold_answer", "correct_answer", "answer", "answers", "response", "response_text", "exact_response", "output", "output_text", "raw", "raw_response", "stdout", "stderr", "api_key", "authorization", "credential", "credentials", "password", "secret", "token", "session_token"}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"(?<![\w-])sk-(?:ant-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?<!\w)hf_[A-Za-z0-9]{20,}"),
    re.compile(r"(?<!\w)(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,})"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9_.-]{24,}"),
    re.compile(r"(?<!\d)\d{8,12}:[A-Za-z0-9_-]{30,}"),
    re.compile(r"(?<!\w)(?:AKIA|ASIA)[A-Z0-9]{16}(?!\w)"),
    re.compile(r'''(?im)^[ \t]*["']?[A-Z_]*(?:API_KEY|TOKEN|SECRET|PASSWORD)[A-Z_0-9]*["']?[ \t]*[:=][ \t]*["']?[A-Za-z0-9_.+/-]{16,}(?=['"\s,;}]|$)'''),
)
CLAIM_FIELDS = {"claim_id", "statement", "run", "run_id", "study_run_id", "data_path", "file", "field", "analysis_field", "value", "code_commit", "commit", "source_commit", "data_sha256", "status", "limitations"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_path(root: Path, value: str | Path) -> Path:
    root = root.resolve()
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise ValueError("Package path must remain inside workspace") from exc
    if ".." in relative.parts or any(part.casefold() in FORBIDDEN_PARTS for part in relative.parts):
        raise ValueError("Forbidden package path")
    for index in range(1, len(relative.parts) + 1):
        if root.joinpath(*relative.parts[:index]).is_symlink():
            raise ValueError("Package symlinks require separate review")
    if not path.resolve().is_relative_to(root):
        raise ValueError("Package path escapes workspace")
    return path


def scan_text(text: str) -> None:
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        # Never include the matched value in an exception, log, or manifest.
        raise ValueError("Potential secret pattern in package source")


def scan_fields(value) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).casefold() in FORBIDDEN_FIELDS:
                raise ValueError("Raw benchmark or credential field in package source")
            scan_fields(item)
    elif isinstance(value, list):
        for item in value:
            scan_fields(item)


def validate_content(path: Path, data: bytes) -> None:
    if path.suffix.lower() == ".png":
        if len(data) > MAX_FIGURE_BYTES or not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Invalid or oversized PNG figure")
        # PNG text metadata is scanned without changing the figure bytes.
        scan_text(data.decode("latin-1"))
        return
    if len(data) > (MAX_FIGURE_BYTES if path.suffix.lower() == ".svg" else MAX_TEXT_BYTES):
        raise ValueError("Oversized editor artifact")
    text = data.decode("utf-8-sig")
    scan_text(text)
    if path.suffix.lower() == ".json":
        scan_fields(json.loads(text))
    elif path.suffix.lower() == ".csv":
        reader = csv.DictReader(io.StringIO(text))
        if any(str(name).strip().casefold() in FORBIDDEN_FIELDS for name in reader.fieldnames or []):
            raise ValueError("Raw benchmark CSV column in package source")
    elif path.suffix.lower() == ".svg":
        if re.search(r"<script\b|\bon[a-z]+\s*=|(?:href|xlink:href)\s*=\s*[\"'](?!#)", text, re.I):
            raise ValueError("Active or external SVG content")


def provenance_projection(data: bytes) -> bytes:
    source = json.loads(data.decode("utf-8-sig"))
    claims = source.get("claims")
    if not isinstance(claims, list) or not claims:
        raise ValueError("Nonempty claim provenance required")
    result = []
    identifiers = []
    for row in claims:
        if not isinstance(row, dict) or not row.get("claim_id") or row.get("status") not in STATUSES:
            raise ValueError("Claim identifier/status missing or invalid")
        identifiers.append(row["claim_id"])
        result.append({key: value for key, value in row.items() if key in CLAIM_FIELDS})
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Duplicate claim identifier")
    summary = {"schema_version": 1, "purpose": "EDITORIAL_ONLY_DO_NOT_CHANGE_NUMBERS", "claims": result}
    return (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def build_package(root: Path, *, systems_dir: str | Path, provenance: str | Path,
                  limitations: str | Path, output: str | Path,
                  source_commit: str, cli_aggregates: tuple[str | Path, ...] = (),
                  study_c_summary: str | Path | None = None,
                  bibliography_addendum: str | Path | None = None) -> dict:
    root = root.resolve()
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("Full source commit SHA required")
    systems = safe_path(root, systems_dir)
    destination = safe_path(root, output)
    if not systems.relative_to(root).parts[0] == "results":
        raise ValueError("Systems directory must be in results")
    if destination.relative_to(root).parts[0] != "outputs" or destination.exists():
        raise ValueError("Output must be a new workspace outputs directory")
    prepared = []

    def add(source, target, role, status, transform=None):
        path = safe_path(root, source)
        rel = path.relative_to(root).as_posix()
        if FORBIDDEN_NAMES.search(path.name) or path.suffix.lower() not in {".md", ".csv", ".json", ".png", ".svg"}:
            raise ValueError("Artifact outside editor allowlist")
        if role == "manuscript" and rel not in MANUSCRIPTS:
            raise ValueError("Only current historical Markdown manuscripts allowed")
        if role == "bibliography" and rel != "docs/VERIFIED_BIBLIOGRAPHY_20261003_RU.md":
            raise ValueError("Only verified bibliography allowed")
        if role == "bibliography_addendum" and rel != "docs/VERIFIED_RESOURCE_BIBLIOGRAPHY_20261003_RU.md":
            raise ValueError("Only explicit verified resource bibliography addendum allowed")
        if role == "provenance" and not (path.parent == root / "manuscript" and path.name.startswith("CLAIM_PROVENANCE") and path.suffix == ".json"):
            raise ValueError("Claim provenance must be in manuscript directory")
        if role == "limitations" and not (path.parent == root / "docs" and path.suffix == ".md"):
            raise ValueError("Limitations must be an explicit workspace docs Markdown file")
        if role == "dev_table" and not (path.parent == root / "results/20261003_resource_analysis" and path.suffix == ".csv"):
            raise ValueError("Unexpected DEV table source")
        if role in {"systems_summary", "systems_table"} and path.parent != systems:
            raise ValueError("Unexpected systems artifact source")
        if role == "study_c_summary" and not (path.relative_to(root).parts[0] == "results" and path.name in {"study_c_summary.json", "study_c_corrected_aggregate.json"}):
            raise ValueError("Only a Study C summary is allowed")
        if role == "cli_aggregate" and not (path.relative_to(root).parts[0] == "results" and path.suffix == ".json" and re.search(r"summary|aggregate|analysis|comparison", path.stem, re.I)):
            raise ValueError("Only explicit CLI aggregate JSON allowed")
        if role == "figure" and not (path.parent in {root / "manuscript/figures", root / "results/20261003_resource_analysis", systems} and path.suffix in {".png", ".svg"}):
            raise ValueError("Unexpected figure source")
        data = path.read_bytes()
        validate_content(path, data)
        copied = transform(data) if transform else data
        prepared.append((target, copied, {"source": rel, "path": target, "role": role, "status": status,
                        "source_commit": source_commit, "source_commit_role": "ASSEMBLY_HEAD; source_sha256 binds working-tree bytes",
                        "source_sha256": digest(data), "copied_sha256": digest(copied), "bytes": len(copied),
                        "copy_mode": "PROJECTION_NUMBERS_UNCHANGED" if transform else "BYTE_FOR_BYTE"}))

    for name in MANUSCRIPTS:
        add(name, name, "manuscript", "HISTORICAL")
    add("docs/VERIFIED_BIBLIOGRAPHY_20261003_RU.md", "references/VERIFIED_BIBLIOGRAPHY_20261003_RU.md", "bibliography", "SUPPLEMENTARY")
    if bibliography_addendum is not None:
        add(bibliography_addendum, "references/VERIFIED_RESOURCE_BIBLIOGRAPHY_20261003_RU.md", "bibliography_addendum", "SUPPLEMENTARY")
    add(limitations, "LIMITATIONS.md", "limitations", "SUPPLEMENTARY")
    add(provenance, "provenance/CLAIM_PROVENANCE_SUMMARY.json", "provenance", "SUPPLEMENTARY", provenance_projection)
    for path in sorted((root / "results/20261003_resource_analysis").glob("*.csv")):
        status = "SUPPLEMENTARY" if path.name == "final_model_table.csv" else "SIMULATED" if path.name.startswith("cascade") else "DEV"
        add(path, "tables/dev/" + path.name, "dev_table", status)
    add(systems / "systems_summary.json", "summaries/systems_summary.json", "systems_summary", "SYSTEMS_TELEMETRY")
    add(systems / "telemetry_table.csv", "tables/systems/telemetry_table.csv", "systems_table", "SYSTEMS_TELEMETRY")
    add(study_c_summary or systems / "study_c_summary.json", "summaries/study_c_summary.json", "study_c_summary", "DEV")
    for index, path in enumerate(cli_aggregates, start=1):
        add(path, f"summaries/product_{index:02}_{Path(path).name}", "cli_aggregate", "SUPPLEMENTARY")
    historical = root / "manuscript/figures"
    for suffix in (".png", ".svg"):
        path = historical / ("historical_noninferiority_20261002" + suffix)
        if path.is_file():
            add(path, "figures/" + path.name, "figure", "HISTORICAL")
    for label, directory, status in (("dev", root / "results/20261003_resource_analysis", "DEV"), ("systems", systems, "SYSTEMS_TELEMETRY")):
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.suffix in {".png", ".svg"}:
                add(path, f"figures/{label}_{path.name}", "figure", status)

    instructions = """# Authors and editorial instructions

Antoniy Sarychev; Denis Shesternin.
Russian State Agrarian University – Moscow Timiryazev Agricultural Academy,
Moscow, Russia. First-year master's students in an AI-related program.
Do not invent an exact program title, CRediT contribution, consent, ORCID, email,
supervisor, author order change, or agronomic qualification.

DO NOT CHANGE NUMBERS. Preserve denominators, units, uncertainty, metric names,
run identities and evidence statuses. Do not strengthen conclusions or silently
replace historical results with new ones. Final appended tables and claim
provenance govern a future revision; unresolved discrepancies become questions.

The RU/EN manuscripts are historical, unchanged drafts whose framing and numbers
have not yet been updated for the latest systems/Study C session. Never overwrite
them. Any later authorized prose edit must create a separate version and identify
which historical passages require revision. This package does not authorize
running Claude, editing conclusions, publishing, submitting, or releasing data.

Use clear connected prose, accurate cautious scientific language and verified
bibliography only. Separate DEV from CONFIRMATORY; systems characterization from
knowledge quality; model-only arithmetic from tool selection and execution;
raw-model API baselines from subscription product/harness baselines; measured
results from SIMULATED replay. Subscription inclusion is not zero inference cost.
Retain failures, resource censoring, missing telemetry, unknown MERA server scorer,
private TEST not run, contamination and licensing limits. No agronomic advice.
"""
    readme = """# Private Claude paper editor package

Prepared evidence only. Claude prose editing has not been run. Publication and
submission have not been authorized. Both human authors retain final approval.

The unchanged historical RU/EN manuscript copies preserve prior work. Their
conclusions are not yet synchronized with the latest experiment. Use appended
tables, summaries, provenance and LIMITATIONS.md as the authority for a separately
requested next revision. DO NOT CHANGE NUMBERS.

PACKAGE_MANIFEST.json maps every artifact to source, hashes, assembly HEAD and
status. The assembly HEAD may precede uncommitted current source bytes; their
source SHA256 is the precise identity. Manifest excludes its own hash.
No benchmark prompts, gold, response texts, credentials or giant raw logs are
included. This package is private and is not a redistributable benchmark release.
"""
    for target, text in (("AUTHORS_AND_STYLE.md", instructions), ("README.md", readme)):
        data = text.encode("utf-8")
        prepared.append((target, data, {"source": "scripts/build_claude_editor_package_20261003.py", "path": target,
                         "role": "editor_instructions", "status": "SUPPLEMENTARY", "source_commit": source_commit,
                         "source_commit_role": "ASSEMBLY_HEAD", "source_sha256": None, "copied_sha256": digest(data),
                         "bytes": len(data), "copy_mode": "GENERATED_INSTRUCTIONS"}))
    if len({target for target, _, _ in prepared}) != len(prepared):
        raise ValueError("Duplicate package destination")
    manifest = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(), "assembly_head": source_commit,
                "package_status": "PRIVATE_EDITORIAL_EVIDENCE_ONLY", "claude_editing_run": False,
                "numbers_must_not_change": True, "historical_manuscripts_unchanged": True,
                "latest_appendices_are_authority": True, "files": [row for _, _, row in prepared]}
    destination.mkdir(parents=True, exist_ok=False)
    for target, data, _ in prepared:
        path = destination / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (destination / "PACKAGE_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--systems-dir", required=True)
    parser.add_argument("--provenance", required=True)
    parser.add_argument("--limitations", required=True)
    parser.add_argument("--output", default="outputs/claude_paper_editor_package")
    parser.add_argument("--source-commit")
    parser.add_argument("--study-c-summary")
    parser.add_argument("--bibliography-addendum", help="Optional explicit docs/VERIFIED_RESOURCE_BIBLIOGRAPHY_20261003_RU.md")
    parser.add_argument("--cli-aggregate", action="append", default=[])
    args = parser.parse_args()
    revision = args.source_commit or "HEAD"
    commit = subprocess.run(["git", "-C", str(args.root), "rev-parse", "--verify", revision + "^{commit}"], check=True, capture_output=True, text=True).stdout.strip()
    manifest = build_package(args.root, systems_dir=args.systems_dir, provenance=args.provenance, limitations=args.limitations,
                             output=args.output, source_commit=commit, cli_aggregates=tuple(args.cli_aggregate), study_c_summary=args.study_c_summary,
                             bibliography_addendum=args.bibliography_addendum)
    print(json.dumps({"output": args.output, "files": len(manifest["files"]), "assembly_head": commit, "claude_editing_run": False}))


if __name__ == "__main__":
    main()
