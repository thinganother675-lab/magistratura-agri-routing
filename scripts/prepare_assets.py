"""Download pinned public assets. Does not inspect credentials."""
import hashlib
import json
from pathlib import Path
import zipfile
import time
import argparse
import httpx

ROOT = Path(__file__).resolve().parents[1]

def download(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        tmp = path.with_suffix(path.suffix + ".part")
        for attempt in range(20):
            offset = tmp.stat().st_size if tmp.exists() else 0
            try:
                with httpx.stream("GET", url, headers={"Range": f"bytes={offset}-"} if offset else {}, follow_redirects=True, timeout=45) as r:
                    r.raise_for_status()
                    if r.status_code == 206:
                        if not r.headers.get("content-range", "").startswith(f"bytes {offset}-"):
                            raise ValueError("Unexpected Content-Range")
                    elif offset:
                        offset = 0
                    with tmp.open("ab" if offset else "wb") as f:
                        for chunk in r.iter_bytes(1024 * 1024):
                            f.write(chunk)
                    total = offset + int(r.headers["content-length"]) if "content-length" in r.headers else tmp.stat().st_size
                    if tmp.stat().st_size != total:
                        raise ValueError("Incomplete download")
                tmp.replace(path)
                break
            except (httpx.HTTPError, ValueError) as exc:
                print(f"download attempt {attempt + 1}: {type(exc).__name__}; retained {tmp.stat().st_size if tmp.exists() else 0} bytes", flush=True)
                time.sleep(2)
        else:
            raise RuntimeError("Download failed after bounded retries; partial retained")
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    print(json.dumps({"file": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": h.hexdigest()}), flush=True)
    return {"url": url, "file": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": h.hexdigest()}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", choices=["0.8B", "2B"], default="0.8B")
    size = parser.parse_args().size
    manifest = []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        info = client.get(f"https://huggingface.co/api/models/unsloth/Qwen3.5-{size}-GGUF", params={"blobs": "true"}).json()
    revision = info["sha"]
    filename = f"Qwen3.5-{size}-Q4_K_M.gguf"
    spec = next(f for f in info["siblings"] if f["rfilename"] == filename)
    model_asset = download(f"https://huggingface.co/unsloth/Qwen3.5-{size}-GGUF/resolve/{revision}/{filename}", ROOT / "models" / filename)
    if model_asset["sha256"] != spec["lfs"]["sha256"]:
        raise ValueError("Model SHA-256 differs from upstream LFS metadata")
    model_asset["upstream_sha256_verified"] = True
    manifest.append(model_asset)
    tag = "b11292"
    archive = ROOT / ".runtime/llama.zip"
    manifest.append(download(f"https://github.com/ggml-org/llama.cpp/releases/download/{tag}/llama-{tag}-bin-win-cpu-x64.zip", archive))
    with zipfile.ZipFile(archive) as z:
        target = (ROOT / ".runtime/llama").resolve()
        for name in z.namelist():
            if not (target / name).resolve().is_relative_to(target):
                raise ValueError("Archive path escapes target")
        # Preserve running DLLs when resuming an interrupted setup. Verify bytes
        # before skipping, so a stale runtime is not silently accepted.
        for member in z.infolist():
            destination = target / member.filename
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            content = z.read(member)
            if destination.exists() and hashlib.sha256(destination.read_bytes()).digest() == hashlib.sha256(content).digest():
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
    metadata = {"access_date": "2026-09-30", "model_revision": revision, "runtime_tag": tag, "assets": manifest}
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / f"data/model_assets_{size}.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
