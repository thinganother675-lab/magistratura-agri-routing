# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Antoniy Sarychev and Denis Shesternin
"""Inventory existing private research artifacts without serializing contents."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE_HEAD = "a3a33b7cf94fe2ccbca1f344c1e0ae4c27ff4af1"
FROZEN_CORE = {"src/agro_route/" + name for name in
               ("models.py", "routing.py", "evaluation.py", "benchmark.py", "tools.py", "cli.py")}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify(path):
    if path.startswith("manuscript/"):
        return "PROJECT-OWNED", "Scientific manuscript/figures; separate license NOT SELECTED; excluded from software release"
    if path.startswith("docs/WORKLOG"):
        return "DO-NOT-PUBLISH", "Private worklog; excluded regardless of original authorship"
    if path == "data/raw/agxqa/LICENSE":
        return "THIRD-PARTY-REDISTRIBUTABLE", "Preserved upstream Apache declaration; does not clear embedded source prose"
    if path.startswith("data/raw/agxqa/"):
        return "LICENSE-UNKNOWN", "Upstream Apache repository with underlying Extension text rights unresolved"
    if path.startswith("data/raw/nasa"):
        return "THIRD-PARTY-REFERENCE-ONLY", "NASA POWER snapshot/provenance; not included or relicensed"
    if path.startswith("data/") and ("benchmark" in path or "holdout" in path or "bilingual" in path):
        return "LICENSE-UNKNOWN", "Mixed imported/source-derived and synthetic corpus; per-row rights, not blanket Apache"
    if path.startswith("data/public_sample/"):
        return "PROJECT-OWNED", "Separate CC0 smoke/measurements dataset; no third-party prose"
    if path.startswith(("results/", "outputs/")):
        return "DO-NOT-PUBLISH", "Private raw/derived research archive may embed source or provider text; explicit projection only"
    if path == "scripts/build_home_holdout.py":
        return "PROJECT-OWNED", "Original implementation Apache; source-derived FACTS prose explicitly excluded, entire file excluded from candidate"
    if path.startswith(("src/", "tests/", "scripts/")):
        return "PROJECT-OWNED", "Original project implementation/test logic; no incompatible copied implementation found in inspected tree"
    return "PROJECT-OWNED", "Original project metadata/documentation; public distribution requires allowlist; manuscript/data exceptions retained"


def run(root=ROOT):
    names = subprocess.run(["git", "-C", str(root), "ls-tree", "-r", "--name-only", BASE_HEAD],
                           check=True, capture_output=True, encoding="utf-8").stdout.splitlines()
    items = []
    frozen = {}
    for name in sorted(names):
        path = root / name
        if not path.is_file():
            raise RuntimeError("Tracked baseline file missing: " + name)
        classification, rationale = classify(name)
        items.append({"path": name, "bytes": path.stat().st_size, "sha256": sha(path),
                      "classification": classification, "rationale": rationale})
        if name.startswith(("data/", "results/", "experiments/", "manuscript/")) or name in FROZEN_CORE:
            frozen[name] = sha(path)
    ignored_areas = [
        {"path": ".runtime/bitnet/BitNet", "classification": "THIRD-PARTY-REDISTRIBUTABLE", "license": "MIT top-level; nested components independent", "included": False},
        {"path": ".runtime/jev/laya-src", "classification": "THIRD-PARTY-REDISTRIBUTABLE", "license": "Apache-2.0 top-level; nested datasets independent", "included": False},
        {"path": ".runtime/bitnet/toolchain", "classification": "THIRD-PARTY-REFERENCE-ONLY", "license": "Mixed LLVM/MinGW notices; binaries excluded", "included": False},
        {"path": ".runtime/bitnet/models", "classification": "THIRD-PARTY-REFERENCE-ONLY", "license": "Per-model and quantization terms", "included": False},
        {"path": ".runtime/jev/models", "classification": "THIRD-PARTY-REFERENCE-ONLY", "license": "Per-model terms", "included": False},
        {"path": ".runtime/references/jev-agent-router", "classification": "LICENSE-UNKNOWN", "license": "Separate reference project; not copied", "included": False},
        {"path": ".runtime/20261002_170443Z_21722066_dataset_literature", "classification": "THIRD-PARTY-REFERENCE-ONLY", "license": "Per-paper and per-dataset rights; full texts/downloads excluded", "included": False},
        {"path": ".cache/jev", "classification": "THIRD-PARTY-REFERENCE-ONLY", "license": "Hugging Face cache; upstream terms", "included": False},
        {"path": ".venv", "classification": "THIRD-PARTY-REDISTRIBUTABLE", "license": "Per installed distribution; never bundled", "included": False},
        {"path": ".env", "classification": "DO-NOT-PUBLISH", "license": "Credentials: no values or hashes recorded", "included": False},
        {"path": ".git", "classification": "DO-NOT-PUBLISH", "license": "Private history excluded from candidate", "included": False},
        {"path": ".runtime and .cache disposable pytest areas", "classification": "DO-NOT-PUBLISH", "license": "Some old cache ACLs inaccessible; excluded completely", "included": False},
    ]
    dependencies = []
    for distribution in sorted(importlib.metadata.distributions(), key=lambda d: d.metadata.get("Name", "")):
        if distribution.metadata.get("Name") == "agro-route-lab":
            continue
        files = [str(p) for p in (distribution.files or []) if
                 any(part.upper().startswith(("LICENSE", "COPYING", "NOTICE")) for part in Path(str(p)).parts)]
        dependencies.append({"name": distribution.metadata.get("Name"), "version": distribution.version,
                             "declared_license": distribution.metadata.get("License-Expression") or distribution.metadata.get("License"),
                             "license_file_names": files, "bundled": False})
    report = {"audit_date": "2026-10-03", "baseline_git_head": BASE_HEAD,
              "tracked_file_count": len(items), "classification_counts": dict(Counter(r["classification"] for r in items)),
              "tracked_artifacts": items, "ignored_major_areas": ignored_areas,
              "installed_dependency_license_metadata": dependencies,
              "secret_values_or_fingerprints_recorded": False,
              "limitation": "Repository evidence audit; not proof of undisclosed external provenance or every cached third-party component"}
    targets = [(root / "docs/licensing_inventory_20261003.json", report),
               (root / "docs/historical_integrity_20261003.json",
                {"baseline_git_head": BASE_HEAD, "scope": "existing data/results/experiments/manuscript and frozen six core files", "sha256": frozen})]
    for path, content in targets:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(content, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    return {"tracked_files": len(items), "historical_protected_files": len(frozen),
            "classifications": report["classification_counts"], "dependencies": len(dependencies)}


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(run(), ensure_ascii=True))
