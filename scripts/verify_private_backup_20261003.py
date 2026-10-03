# SPDX-License-Identifier: Apache-2.0
"""Verify authorized private Git backup through existing GCM, never print credentials."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess

import httpx

ROOT = Path(__file__).resolve().parents[1]
TARGET = "Apartman36/magistratura-agri-routing"
BASELINE = "a3a33b7cf94fe2ccbca1f344c1e0ae4c27ff4af1"


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args]).decode().strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include", action="append", default=[])
    args = parser.parse_args()
    destination = (ROOT / args.output).resolve()
    assert destination.is_relative_to(ROOT) and not destination.exists(), "Use a new workspace report path."
    assert git("remote", "get-url", "apartman") == "https://github.com/" + TARGET + ".git"
    assert git("remote", "get-url", "origin") == "https://github.com/thinganother675-lab/magistratura-agri-routing.git"
    assert subprocess.run(["git", "merge-base", "--is-ancestor", BASELINE, args.sha], cwd=ROOT).returncode == 0
    env = os.environ.copy()
    env.update(GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
    credential = subprocess.run(
        ["git", "-c", "credential.interactive=never", "credential", "fill"],
        input="protocol=https\nhost=github.com\nusername=Apartman36\n\n",
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=25,
    )
    if credential.returncode:
        raise SystemExit("Credential lookup blocked; no credential printed.")
    values = dict(line.split("=", 1) for line in credential.stdout.splitlines() if "=" in line)
    token = values.get("password")
    if not token:
        raise SystemExit("No credential returned; no credential printed.")
    headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    with httpx.Client(timeout=30, trust_env=True, headers=headers) as client:
        user = client.get("https://api.github.com/user")
        user.raise_for_status()
        assert user.json()["login"] == "Apartman36", "Unexpected authenticated identity"
        repo = client.get("https://api.github.com/repos/" + TARGET)
        repo.raise_for_status()
        assert repo.json()["private"] is True, "Destination is not PRIVATE"
        reference = client.get("https://api.github.com/repos/" + TARGET + "/git/ref/heads/main")
        reference.raise_for_status()
        remote_sha = reference.json()["object"]["sha"]
        assert remote_sha == args.sha, "Remote main differs from expected SHA"
        tree = client.get("https://api.github.com/repos/" + TARGET + "/git/trees/" + args.sha, params={"recursive": 1})
        tree.raise_for_status()
        assert not tree.json().get("truncated"), "Remote tree truncated"
        blobs = {item["path"]: item for item in tree.json()["tree"] if item["type"] == "blob"}
        checks = {}
        for path in args.include:
            local_blob = git("rev-parse", args.sha + ":" + path)
            assert path in blobs and blobs[path]["sha"] == local_blob, "Research blob mismatch: " + path
            checks[path] = {"blob_sha": local_blob, "size_bytes": blobs[path].get("size"), "match": True}
    report = {
        "utc": datetime.now(timezone.utc).isoformat(), "status": "PASS", "identity": "Apartman36",
        "destination": "https://github.com/" + TARGET, "private": True,
        "remote_main_sha": remote_sha, "remote_tree_blob_count": len(blobs), "important_artifacts": checks,
        "baseline_ancestor": BASELINE, "origin_preserved": True, "force_push": False,
        "credential_values_or_fingerprints_persisted": False, "public_release": "NOT_RUN",
        "transport": "Existing Git Credential Manager, credential internal to Python only",
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("status", "identity", "destination", "private", "remote_main_sha", "remote_tree_blob_count")}))


if __name__ == "__main__":
    main()
