"""Fetch public, unauthenticated pinned model metadata; no credential access."""
import json
import shutil
import urllib.request
from pathlib import Path

REPO = "convaiinnovations/laya-multilingual"
REVISION = "e4e9ddf21a7b1903b7acffd8814ad4307bf63a67"
SOURCE_REVISION = "4aa6761be8173de4ce6d92c31b3e40b6eaf59a7c"
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]

def main():
    url = f"https://huggingface.co/api/models/{REPO}/revision/{REVISION}?blobs=true"
    with urllib.request.urlopen(url, timeout=30) as response:
        public = json.load(response)
    free = shutil.disk_usage(ROOT).free
    files = [{"path": f["rfilename"], "size": f.get("size"), "lfs_sha256": (f.get("lfs") or {}).get("sha256")} for f in public["siblings"]]
    selected_bytes = sum(f["size"] or 0 for f in files)
    data = {"model_id": REPO, "model_revision": REVISION, "source_repo": "https://github.com/NandhaKishorM/laya", "source_revision": SOURCE_REVISION,
            "source_version": "0.3.23", "license": public["cardData"]["license"], "language_tags": public["cardData"].get("language", []),
            "safetensors_metadata": public.get("safetensors"), "files": files, "selected_download_bytes": selected_bytes,
            "free_disk_bytes_before_model_download": free, "reason": "Small multilingual non-autoregressive typed decision baseline; Russian routing experiment supplementary control",
            "device_plan": "CPU only; torch CPU build; no concurrent GPU inference", "expected_weight_ram_bytes_fp32_lower_bound": 321908998 * 4,
            "model_path": ".runtime/jev/models/laya-multilingual", "venv_path": ".runtime/jev/.venv", "status": "download_preflight_verified",
            "calibration_status": "uncalibrated; no fitted temperature on our agricultural data", "jev_parity_claim": False,
            "paid_jev_api_used": False, "auth": "Public unauthenticated metadata/download; isolated HF_HOME"}
    (OUT / "metadata.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"revision": REVISION, "license": data["license"], "download_bytes": selected_bytes, "free_disk_bytes": free}))

if __name__ == "__main__":
    main()
