"""Public HTTPS fallback after HF CLI read timeouts; pinned revision + hashes.

Only model artifacts are downloaded. No credentials, paid inference, or TLS
exceptions. Range boundaries are verified and partial downloads remain resumable.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
META_PATH = ROOT / "results/jev_local_20261001/metadata.json"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for data in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()


def fetch_range(resolved_url, name, size, offset, end):
    for attempt in range(4):
        try:
            # Reuse the public redirect only in process memory. Its signed query
            # is never printed or persisted; every range is independently checked.
            request = urllib.request.Request(resolved_url, headers={"Range": f"bytes={offset}-{end}"})
            with urllib.request.urlopen(request, timeout=25) as response:
                if response.status != 206:
                    raise RuntimeError(f"Expected HTTP 206, got {response.status}")
                if response.headers.get("Content-Range") != f"bytes {offset}-{end}/{size}":
                    raise RuntimeError("Content-Range did not match requested pinned range")
                data = response.read(end - offset + 2)
            if len(data) != end - offset + 1:
                raise RuntimeError("Range body length mismatch")
            return data
        except Exception as exc:
            print(json.dumps({"file": name, "offset": offset, "retry": attempt + 1, "error_type": type(exc).__name__}), flush=True)
            if attempt == 3:
                raise RuntimeError(f"Public artifact transport failed: {type(exc).__name__}") from None
            time.sleep(min(attempt + 1, 3))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunk-mib", type=int, default=4)
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=4)
    args = parser.parse_args()
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    destination = ROOT / meta["model_path"]
    verified = []
    for entry in meta["files"]:
        name, size, expected = entry["path"], entry["size"], entry["lfs_sha256"]
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            actual = sha256(path)
            if path.stat().st_size != size or (expected and actual != expected):
                raise RuntimeError(f"Existing file does not match pinned metadata: {name}")
            print(json.dumps({"file": name, "status": "already_verified", "bytes": size}), flush=True)
        else:
            partial = path.with_name(path.name + ".part")
            offset = partial.stat().st_size if partial.exists() else 0
            if offset > size:
                raise RuntimeError("Partial exceeds pinned file size")
            base_url = f"https://huggingface.co/{meta['model_id']}/resolve/{meta['model_revision']}/{name}"
            began = time.perf_counter()
            request = urllib.request.Request(base_url, headers={"Range": f"bytes={offset}-{min(offset, size-1)}"})
            with urllib.request.urlopen(request, timeout=25) as response:
                resolved_url = response.url
            with partial.open("ab") as handle, ThreadPoolExecutor(max_workers=args.workers) as pool:
                while offset < size:
                    pending = []
                    scheduled = offset
                    for _ in range(args.workers):
                        if scheduled >= size:
                            break
                        end = min(scheduled + args.chunk_mib * 1024 * 1024, size) - 1
                        pending.append(pool.submit(fetch_range, resolved_url, name, size, scheduled, end))
                        scheduled = end + 1
                    for future in pending:
                        data = future.result()
                        handle.write(data)
                        handle.flush()
                        offset += len(data)
                        elapsed = time.perf_counter() - began
                        print(json.dumps({"file": name, "bytes": offset, "total": size, "percent": round(offset / size * 100, 2), "elapsed_seconds": round(elapsed, 2)}), flush=True)
            actual = sha256(partial)
            if expected and actual != expected:
                raise RuntimeError("Completed artifact SHA256 did not match pinned public metadata")
            partial.rename(path)
        verified.append({"file": name, "bytes": size, "sha256": sha256(path), "expected_lfs_sha256": expected})
    report = {"model_id": meta["model_id"], "revision": meta["model_revision"], "status": "all_selected_artifacts_size_and_lfs_sha256_verified", "transport": "HF CLI small files; standard verified HTTPS Range fallback for binary read timeouts", "artifacts": verified}
    report_path = META_PATH.parent / "download_verification.json"
    if report_path.exists():
        if json.loads(report_path.read_text(encoding="utf-8")) != report:
            raise RuntimeError("Existing verification report differs; preserve it and review artifacts")
    else:
        with report_path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(report, indent=2))
    print(json.dumps({"status": report["status"], "files": len(verified)}), flush=True)


if __name__ == "__main__":
    main()
