"""Review a fixed safe Git scope, including text inside editable/ZIP/TAR artifacts."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
from zipfile import ZipFile
from scan_public_artifacts import configured_secret_values, inspect_file, PATTERNS, ASSIGNMENT, PLACEHOLDERS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/20261004_session"
GIT = Path("C:/Users/hustlePC/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected_paths():
    paths = {ROOT / "README.md", ROOT / "tests/test_study_c_live_20261004.py", ROOT / "experiments/STUDY_C_LIVE_PROTOCOL_20261004.json"}
    for name in ("CURRENT_STUDY", "EVIDENCE_AUDIT", "PUBLICATION_METADATA", "STUDY_C_LIVE"):
        paths.add(ROOT / f"docs/{name}_20261004_RU.md")
    for prefix in ("english", "russian"):
        for ext in ("md", "tex", "pdf"):
            paths.add(ROOT / f"manuscript/{prefix}_resource_20261004.{ext}")
    paths.add(ROOT / "manuscript/russian_resource_20261004.docx")
    for p in (ROOT / "scripts").glob("*20261004*"):
        if p.is_file():
            paths.add(p)
    for folder in ("results/20261004_evidence_audit", "results/20261004_article_build", "results/20261004_study_c_live", "results/20261004_session", "outputs/claude_article_editor_20261004"):
        paths.update(p for p in (ROOT / folder).rglob("*") if p.is_file())
    paths.add(ROOT / "outputs/claude_article_editor_20261004.zip")
    for name in ("compact_bibliography_19.json", "references_19.bib", "refs_ready.md", "VERIFIED_BIBLIOGRAPHY_19_RU.md", "official_qwen_registry.json", "mera_methodological_source.md", "direct_retrieval_receipts.json", "build_compact_bibliography.py"):
        paths.add(ROOT / "results/20261004_publication_sources" / name)
    generated = {"delivery_scope_manifest.json", "delivery_secret_scan.json", "safe_stage_paths.json"}
    paths = {p for p in paths if not (p.parent == OUT and p.name in generated)}
    assert all(p.is_file() for p in paths)
    assert not any(p.name == "den_text.docx" or "20261003" in p.name and p.parent.name == "scripts" or p.name.endswith("_README.md") or p.suffix == ".html" for p in paths)
    return sorted(paths)


def scan_bytes(data, label, secrets):
    if b"\0" in data[:4096]:
        return []
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return []
    findings = []
    for rule, pattern in PATTERNS.items():
        for m in pattern.finditer(text):
            findings.append({"path": label, "rule": rule, "line": text.count("\n", 0, m.start()) + 1})
    for m in ASSIGNMENT.finditer(text):
        if m[1].lower() not in PLACEHOLDERS:
            findings.append({"path": label, "rule": "literal_credential_assignment", "line": text.count("\n", 0, m.start()) + 1})
    for secret in secrets:
        if secret in text:
            findings.append({"path": label, "rule": "configured_secret_exact_match", "line": None})
    return findings


def main():
    paths = selected_paths()
    secrets = configured_secret_values(ROOT)
    findings = []
    nested = 0
    for p in paths:
        findings += inspect_file(ROOT, p, secrets)
        label = p.relative_to(ROOT).as_posix()
        if p.suffix in (".zip", ".docx"):
            with ZipFile(p) as z:
                for info in z.infolist():
                    if not info.is_dir():
                        nested += 1
                        findings += scan_bytes(z.read(info), label + "::" + info.filename, secrets)
        elif p.name.endswith(".tar.gz"):
            with tarfile.open(p) as tar:
                for member in tar.getmembers():
                    if member.isfile():
                        nested += 1
                        findings += scan_bytes(tar.extractfile(member).read(), label + "::" + member.name, secrets)
    changed = subprocess.run([str(GIT), "diff", "--name-only", "af5742e7c294cd5f93155a3deb438f6d667351fe"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    original = set(subprocess.run([str(GIT), "ls-tree", "-r", "--name-only", "af5742e7c294cd5f93155a3deb438f6d667351fe"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines())
    changed_old = sorted(set(changed) & original)
    assert set(changed_old) <= {"README.md"}, changed_old
    native = json.loads((ROOT / "results/20261004_study_c_live/postrun_revision_receipt.json").read_text(encoding="utf-8"))
    current_sha = sha(ROOT / "scripts/study_c_live_20261004.py")
    assert current_sha in json.dumps(native)
    excluded = [p for p in (ROOT / "results/20261004_publication_sources").iterdir() if p.is_file() and p not in paths]
    scope = {"created_utc": datetime.now(timezone.utc).isoformat(), "baseline_head": "af5742e7c294cd5f93155a3deb438f6d667351fe", "only_changed_preexisting_tracked_file": changed_old, "historical_data_protocol_results_source_unchanged": True, "current_live_runner_sha256": current_sha, "selected_files": [{"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)} for p in paths], "excluded_third_party_local_snapshots": [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p)} for p in sorted(excluded)], "preserved_user_untracked": ["den_text.docx", "outputs/01a1000f-1760-7353-b09f-1f0aed9a4e34/", "outputs/denis_research_review_20261003/", "scripts/convert_review_xlsx_to_csv_20261003.py"], "restricted_raw_state": "local only, original hashes retained in evidence audit and live protocol; not backed up by this Git delivery"}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "delivery_scope_manifest.json").write_text(json.dumps(scope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {"checked_utc": datetime.now(timezone.utc).isoformat(), "scope": "fixed selected safe new work plus README; inherited/unrelated untracked files excluded", "files_checked": len(paths), "archive_members_checked": nested, "findings": findings, "configured_secret_values_printed_or_persisted": False, "copyright": "Full third-party pages/cards and restricted benchmark records excluded; factual bibliography/metadata and original drafts included", "limitation": "Pattern and configured-secret checks cannot prove absence of every possible secret"}
    (OUT / "delivery_secret_scan.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Exact paths for subsequent Git add; JSON parsed as argument array by PS.
    names = [p.relative_to(ROOT).as_posix() for p in paths]
    names += ["results/20261004_session/delivery_scope_manifest.json", "results/20261004_session/delivery_secret_scan.json", "results/20261004_session/safe_stage_paths.json"]
    (OUT / "safe_stage_paths.json").write_text(json.dumps(sorted(set(names)), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"files": len(paths), "archive_members": nested, "findings": findings, "historical_unchanged": True}))
    raise SystemExit(1 if findings else 0)


if __name__ == "__main__":
    main()
