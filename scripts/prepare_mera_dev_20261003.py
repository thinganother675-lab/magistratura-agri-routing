# SPDX-License-Identifier: Apache-2.0
"""Fetch pinned public DEV only into ignored storage; never fetch TEST.

Optional parquet reader is confined to .runtime/mera/reader; the project
environment and dependency lock are not modified. No training permission implied.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import zipfile
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agro_route.mera_adapter_20261003 import DATASET, HF_REVISION, isolate_dev_references

TRAIN_SHA256 = "688046d5b25adbec713856df0ebce00784498e919b4b235692f6262b03678f8d"


def main():
    if sys.version_info[:2] != (3, 12) or sys.platform != "win32":
        raise RuntimeError("This confined optional reader path was verified for Windows CPython 3.12 only")
    target = ROOT / ".runtime/mera"; target.mkdir(parents=True, exist_ok=True)
    reader = target / "reader"
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        # Published package metadata supplies the wheel checksum, never executes code.
        meta = client.get("https://pypi.org/pypi/pyarrow/19.0.1/json")
        meta.raise_for_status()
        matches = [x for x in meta.json()["urls"] if "cp312-cp312-win_amd64.whl" in x["filename"]]
        if len(matches) != 1:
            raise RuntimeError("Unambiguous CPython wheel not found")
        wheel = matches[0]; path = target / "reader_wheels" / wheel["filename"]
        path.parent.mkdir(exist_ok=True)
        if not path.exists():
            response = client.get(wheel["url"]); response.raise_for_status()
            with path.open("xb") as f: f.write(response.content)
        if hashlib.sha256(path.read_bytes()).hexdigest() != wheel["digests"]["sha256"]:
            raise RuntimeError("Optional reader wheel checksum mismatch")
        if not reader.exists():
            reader.mkdir()
            with zipfile.ZipFile(path) as archive:
                for entry in archive.infolist():
                    if not (reader / entry.filename).resolve().is_relative_to(reader.resolve()):
                        raise RuntimeError("Wheel path escaped isolated reader directory")
                archive.extractall(reader)
        source = target / f"dev_train_{HF_REVISION}.parquet"
        if not source.exists():
            url = f"https://huggingface.co/datasets/{DATASET}/resolve/{HF_REVISION}/data/train-00000-of-00001.parquet"
            response = client.get(url); response.raise_for_status()
            with source.open("xb") as f: f.write(response.content)
        if hashlib.sha256(source.read_bytes()).hexdigest() != TRAIN_SHA256:
            raise RuntimeError("Pinned public DEV content differs from official LFS SHA256")
    sys.path.insert(0, str(reader))
    import pyarrow.parquet as parquet
    rows = parquet.read_table(source).to_pylist()
    items, refs = isolate_dev_references(rows)
    if len(items) != 293:
        raise RuntimeError("Expected exactly 293 public DEV rows")
    out = target / f"dev_rows_{HF_REVISION}.json"
    if not out.exists():
        with out.open("x", encoding="utf-8") as f: json.dump(rows, f, ensure_ascii=False)
    report = {"source_revision": HF_REVISION, "source_parquet_sha256": TRAIN_SHA256,
              "derived_local_json_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
              "n": len(items), "domains": dict(Counter(x.domain for x in items)),
              "reader": {"name": "pyarrow", "version": "19.0.1", "wheel_sha256": wheel["digests"]["sha256"]},
              "test_fetched": False, "source_redistribution": "DO_NOT_REDISTRIBUTE", "model_training": "PROHIBITED"}
    report_path = target / "dev_extraction_manifest.json"
    if not report_path.exists():
        with report_path.open("x", encoding="utf-8") as f: json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps({"local_dev_rows_path": str(out), **report}, ensure_ascii=False))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
