# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Antoniy Sarychev and Denis Shesternin
"""Build or verify an explicit-allowlist public candidate without publication."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PARTS = {".git", ".venv", ".runtime", ".cache", "__pycache__", "models", "node_modules"}
FORBIDDEN_SUFFIXES = {".gguf", ".safetensors", ".onnx", ".pt", ".pth", ".pdf", ".xlsx", ".pem", ".key", ".p12", ".pfx", ".log"}
PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "provider_token": re.compile(r"(?<![\w-])sk-(?:ant-)?[A-Za-z0-9_-]{20,}"),
    "huggingface_token": re.compile(r"(?<!\w)hf_[A-Za-z0-9]{20,}"),
    "github_token": re.compile(r"(?<!\w)(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,})"),
    "bearer_literal": re.compile(r"(?i)Bearer\s+[A-Za-z0-9_.-]{24,}"),
    "telegram_token": re.compile(r"(?<!\d)\d{8,12}:[A-Za-z0-9_-]{30,}"),
    "aws_id": re.compile(r"(?<!\w)(?:AKIA|ASIA)[A-Z0-9]{16}(?!\w)"),
    "personal_path": re.compile(r"(?i)[A-Z]:[\\/]Users[\\/][A-Za-z0-9_.-]+"),
}
KEY_NAME = re.compile(r"(?i)(api[_-]?key|token|secret|password|credential)")
ASSIGNMENT = re.compile(r'''(?im)^[ \t]*["']?[A-Z_]*?(?:API_KEY|TOKEN|SECRET|PASSWORD)[A-Z_0-9]*["']?[ \t]*[:=][ \t]*["']?([A-Za-z0-9_.+/-]{16,})(?=['"\s,;}]|$)''')
OFFICIAL_APACHE_SHA256 = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_path(root, relative):
    path = PurePosixPath(relative)
    if not relative or path.is_absolute() or ".." in path.parts or "\\" in relative or ":" in relative:
        raise ValueError("Unsafe release path")
    target = root / path
    if any((root / Path(*path.parts[:i])).is_symlink() for i in range(1, len(path.parts) + 1)):
        raise ValueError("Symlink requires separate review")
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("Release path escapes root")
    return target


def configured_secrets(root):
    # Never return these values in reports, fingerprints or exceptions.
    values = {value for name, value in os.environ.items() if KEY_NAME.search(name) and len(value) >= 8}
    dotenv = root / ".env"
    if dotenv.is_file():
        for line in dotenv.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                name, value = line.split("=", 1)
                if KEY_NAME.search(name):
                    value = value.strip().strip("\"'")
                    if len(value) >= 8:
                        values.add(value)
    return values


def inspect(relative, data, secrets=()):
    path = PurePosixPath(relative)
    name = path.name.lower()
    findings = []
    if any(part.lower() in FORBIDDEN_PARTS for part in path.parts) or path.suffix.lower() in FORBIDDEN_SUFFIXES:
        findings.append("forbidden_artifact")
    if (name == ".env" or name.startswith(".env.") and name != ".env.example" or
            "worklog" in name or name.startswith(("credentials", "id_rsa", "id_ed25519")) or
            name in {"auth.json", "cookies.json", "cookies.txt", "storage_state.json", "storage-state.json"}):
        findings.append("sensitive_filename")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return findings + ["binary_or_non_utf8_requires_review"]
    for rule, pattern in PATTERNS.items():
        if pattern.search(text):
            findings.append(rule)
    if ASSIGNMENT.search(text):
        findings.append("credential_assignment")
    if any(value in text for value in secrets):
        findings.append("configured_secret_match")
    return sorted(set(findings))


def approved_provenance(item, data):
    if item["classification"] == "PROJECT-OWNED":
        return item["license"] in {"Apache-2.0", "CC0-1.0"}
    # The only third-party bytes in this source-only distribution are the
    # unchanged official license text. No blanket allowance for external code.
    return (item["classification"] == "THIRD-PARTY-REDISTRIBUTABLE" and item["path"] == "LICENSE" and
            item["license"] == "Apache-2.0" and hashlib.sha256(data).hexdigest() == OFFICIAL_APACHE_SHA256)


def check_historical(root):
    baseline = json.loads((root / "docs/historical_integrity_20261003.json").read_text(encoding="utf-8"))
    mismatches = [name for name, digest in baseline["sha256"].items()
                  if not safe_path(root, name).is_file() or sha(safe_path(root, name)) != digest]
    if mismatches:
        raise RuntimeError("Historical artifacts changed: " + ", ".join(mismatches))
    return {"baseline_git_head": baseline["baseline_git_head"],
            "protected_files": len(baseline["sha256"]), "all_sha256_match": True}


def verify(directory, *, secrets=()):
    manifest = json.loads((directory / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
    listed = {item["path"] for item in manifest["files"]}
    if len(listed) != len(manifest["files"]):
        raise RuntimeError("Duplicate candidate manifest path")
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()}
    actual = {name for name in actual if "__pycache__" not in PurePosixPath(name).parts and
              not any(part in {".pytest_cache", ".venv", ".cache"} for part in PurePosixPath(name).parts) and
              not name.startswith("reproduction_output/") and ".egg-info/" not in name}
    expected = listed | {"RELEASE_MANIFEST.json"}
    if actual != expected:
        raise RuntimeError("Candidate file set differs from manifest")
    findings = []
    for item in manifest["files"]:
        path = safe_path(directory, item["path"])
        if sha(path) != item["sha256"]:
            findings.append({"path": item["path"], "rule": "sha256_mismatch"})
        if not approved_provenance(item, path.read_bytes()):
            findings.append({"path": item["path"], "rule": "unapproved_provenance"})
        findings.extend({"path": item["path"], "rule": rule} for rule in inspect(item["path"], path.read_bytes(), secrets))
    findings.extend({"path": "RELEASE_MANIFEST.json", "rule": rule} for rule in
                    inspect("RELEASE_MANIFEST.json", (directory / "RELEASE_MANIFEST.json").read_bytes(), secrets))
    if findings:
        # Paths/rules only: never print matched content or credential values.
        raise RuntimeError("Candidate verification failed: " + json.dumps(findings, ensure_ascii=True))
    return {"files": len(listed), "hashes_match": True, "provenance_pass": True,
            "secret_scan_pass": True, "no_secrets_or_fingerprints_printed": True}


def archive(directory, destination):
    verify(directory)
    manifest = json.loads((directory / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
    names = sorted([item["path"] for item in manifest["files"]] + ["RELEASE_MANIFEST.json"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as handle:
        for name in names:
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 3, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            handle.writestr(info, (directory / name).read_bytes(), compresslevel=9)
    return {"archive_sha256": sha(destination), "archive_members": len(names)}


def build(root, destination):
    if destination.exists():
        raise FileExistsError("Refuse overwriting an existing candidate; use a new directory")
    plan = json.loads((root / "release/allowlist.json").read_text(encoding="utf-8"))
    historical = check_historical(root)
    secrets = configured_secrets(root)
    payload = []
    seen = set()
    for item in plan["files"]:
        source, target = safe_path(root, item["source"]), safe_path(destination, item["path"])
        if item["path"] in seen or item["path"] == "RELEASE_MANIFEST.json":
            raise ValueError("Duplicate or reserved candidate path")
        seen.add(item["path"])
        data = source.read_bytes()
        if not approved_provenance(item, data):
            raise ValueError("Unknown/unapproved release provenance")
        findings = inspect(item["path"], data, secrets)
        if findings:
            raise RuntimeError("Rejected candidate file " + item["path"] + ": " + ",".join(findings))
        payload.append((item, target, data))
    # Verify every input before any candidate file is written.
    source_head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True,
                                 capture_output=True, encoding="utf-8").stdout.strip()
    destination.mkdir(parents=True, exist_ok=False)
    files = []
    for item, target, data in payload:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files.append({key: item[key] for key in ("path", "classification", "license", "provenance")})
        files[-1].update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    manifest = {"candidate_version": "v0.1.0-research", "date": "2026-10-03",
                "publicly_published": False, "source_git_head": source_head,
                "source_working_tree_sha256": "individual file hashes below include new uncommitted session work",
                "historical_integrity": historical, "files": files,
                "excluded_scope": ["manuscripts", "third-party paragraphs/datasets/papers", "model weights/runtimes",
                                   "provider output text/raw logs", "credentials", "private worklog", "private Git history"],
                "scan_limitation": "Patterns and exact configured values; not proof against arbitrary undisclosed secrets"}
    (destination / "RELEASE_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return verify(destination, secrets=secrets)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--build", type=Path)
    group.add_argument("--verify", type=Path)
    group.add_argument("--archive-tree", type=Path)
    parser.add_argument("--archive-output", type=Path)
    args = parser.parse_args()
    if args.build:
        result = build(ROOT, args.build.resolve())
    elif args.verify:
        result = verify(args.verify.resolve(), secrets=configured_secrets(ROOT))
    else:
        if not args.archive_output:
            parser.error("--archive-output is required")
        result = archive(args.archive_tree.resolve(), args.archive_output.resolve())
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
