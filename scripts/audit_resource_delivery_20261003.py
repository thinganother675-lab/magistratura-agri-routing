"""Audit only this session's owned files and preserve pre-existing outputs.

No Git mutation, credential values, question text, network or model invocation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from scan_public_artifacts import configured_secret_values, inspect_file

BASE = "6c496744107001d523c2311f236a61a5e14b93c2"
EXCLUDED = {"scripts/convert_review_xlsx_to_csv_20261003.py"}


def historical_changes(root, baseline):
    protected = ["manuscript/russian_routing_20261003.md", "manuscript/english_routing_20261003.md",
                 "experiments/mera_private_test_protocol_draft_20261003.json"]
    # New result files remain A relative to the original baseline even after
    # an intermediate commit. They are additions, not historical rewrites.
    return subprocess.check_output(["git", "diff", "--name-only", "--diff-filter=DMRT", baseline,
                                    "--", "results", "data", *protected], cwd=root).decode("utf-8").splitlines()


def owned_files():
    changed = subprocess.check_output(["git", "diff", "--name-only", "-z", BASE], cwd=ROOT).decode().split("\0")
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=ROOT).decode().split("\0")
    files = []
    for name in sorted(set(changed + untracked)):
        if not name or name in EXCLUDED:
            continue
        if name.startswith("outputs/") and not name.startswith("outputs/claude_paper_editor_package/"):
            continue
        if (ROOT / name).is_file():
            files.append(name)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    if not args.label.isidentifier() or not args.label.isascii():
        raise ValueError("Safe audit label required")
    target = ROOT / "results/20261003_resource_session" / ("delivery_audit_" + args.label + ".json")
    if target.exists():
        raise ValueError("Audit is append-only")
    files = owned_files()
    secrets = configured_secret_values(ROOT)
    findings = [finding for name in files for finding in inspect_file(ROOT, ROOT / name, secrets)]
    changed_old = historical_changes(ROOT, BASE)
    ignored = subprocess.run(["git", "check-ignore", ".runtime/mera/20261003_systems_checkpoint0_v2/raw.jsonl",
                              ".runtime/cli_products/codex_dev60_raw.jsonl", ".env"], cwd=ROOT, capture_output=True, text=True)
    receipt = {"status": "SAFE_PRIVATE_DELIVERY_AUDIT", "baseline_commit": BASE,
               "owned_file_count": len(files), "findings": findings,
               "historical_results_inputs_manuscripts_private_protocol_changed": changed_old,
               "raw_and_credentials_ignored": ignored.returncode == 0 and len(ignored.stdout.splitlines()) == 3,
               "file_hashes": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files},
               "excluded_preexisting_outputs": ["outputs/01a1000f-1760-7353-b09f-1f0aed9a4e34/", "outputs/denis_research_review_20261003/", *sorted(EXCLUDED)],
               "safe": not findings and not changed_old and ignored.returncode == 0,
               "historical_diff_filter": "DMRT; additions A are new evidence, including after intermediate commits",
               "historical_filter_correction": "Earlier final audit counted new committed additions as historical changes; preserve earlier receipt, this filter checks modifications/deletions/renames/type changes only"}
    target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"receipt": target.relative_to(ROOT).as_posix(), "safe": receipt["safe"],
                      "owned_file_count": len(files), "findings": findings, "protected_change_count": len(changed_old)}))
    raise SystemExit(0 if receipt["safe"] else 1)


if __name__ == "__main__":
    main()
