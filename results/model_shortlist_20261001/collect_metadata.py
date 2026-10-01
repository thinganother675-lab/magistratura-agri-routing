"""Fetch public HF metadata/config only; never model weights or credentials."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
REPOS = [
    "Qwen/Qwen3.5-4B", "bartowski/Qwen_Qwen3.5-4B-GGUF",
    "microsoft/Phi-4-mini-instruct", "bartowski/microsoft_Phi-4-mini-instruct-GGUF",
    "microsoft/bitnet-b1.58-2B-4T", "microsoft/bitnet-b1.58-2B-4T-gguf",
    "microsoft/bitnet-b1.58-2B-4T-bf16",
    "google/gemma-4-E4B-it", "unsloth/gemma-4-E4B-it-GGUF",
    "CohereLabs/tiny-aya-global", "CohereLabs/tiny-aya-global-GGUF",
    "HuggingFaceTB/SmolLM3-3B", "bartowski/HuggingFaceTB_SmolLM3-3B-GGUF",
    "ibm-granite/granite-4.0-h-tiny", "ibm-granite/granite-4.0-h-tiny-GGUF",
    "Qwen/Qwen3.5-35B-A3B", "unsloth/Qwen3.5-35B-A3B-GGUF",
    "Qwen/Qwen3-4B-Instruct-2507", "bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF",
    "Qwen/Qwen3-30B-A3B-Instruct-2507", "unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF",
    "Xianjun/PLLaMa-7b-instruct",
]


def get_json(url):
    for attempt in range(3):
        try:
            req = Request(url, headers={"User-Agent": "agro-route-public-metadata-audit/1.0"})
            with urlopen(req, timeout=25) as response:
                return json.load(response)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(0.5)


def collect(repo):
    url = f"https://huggingface.co/api/models/{repo}?blobs=true"
    result = {"repo": repo, "api_url": url, "retrieved_utc": datetime.now(timezone.utc).isoformat(),
              "weights_downloaded": False}
    try:
        metadata = get_json(url)
        result["metadata"] = metadata
        sha = metadata.get("sha")
        if any(s.get("rfilename") == "config.json" for s in metadata.get("siblings", [])):
            config_url = f"https://huggingface.co/{repo}/resolve/{sha}/config.json"
            result["config_url"] = config_url
            try:
                result["config"] = get_json(config_url)
            except Exception as exc:
                result["config_error"] = type(exc).__name__
    except Exception as exc:
        result["error"] = type(exc).__name__
    path = ROOT / "metadata" / (repo.replace("/", "__") + ".json")
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    (ROOT / "metadata").mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as executor:
        records = list(executor.map(collect, REPOS))
    for record in records:
        m = record.get("metadata", {})
        gguf = [s for s in m.get("siblings", []) if s["rfilename"].endswith(".gguf") and
                any(tag in s["rfilename"].lower() for tag in ("q8_0", "iq1", "i2_s", "tl1", "tl2"))]
        print(json.dumps({"repo": record["repo"], "sha": m.get("sha"), "created": m.get("createdAt"),
                          "modified": m.get("lastModified"), "license": m.get("cardData", {}).get("license"),
                          "params": m.get("safetensors", {}), "files": gguf,
                          "error": record.get("error")}, ensure_ascii=True))
