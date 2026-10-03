# SPDX-License-Identifier: Apache-2.0
"""Anonymous metadata/document audit. Never acquire benchmark rows or use keys."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "bbk_metadata": "https://huggingface.co/api/datasets/bharatgenai/BhashaBench-Krishi",
    "bbk_card": "https://huggingface.co/datasets/bharatgenai/BhashaBench-Krishi/raw/main/README.md",
    "bbk_code_tree": "https://api.github.com/repos/kundeshwar-BharatGen/BhashaBench/git/trees/main?recursive=1",
    "bbk_task_template": "https://raw.githubusercontent.com/kundeshwar-BharatGen/BhashaBench/babd1e1d97d5361da53fe1f11b941400399206e0/lm_eval/tasks/bbk/_default_template_yaml",
    "bbk_task_english": "https://raw.githubusercontent.com/kundeshwar-BharatGen/BhashaBench/babd1e1d97d5361da53fe1f11b941400399206e0/lm_eval/tasks/bbk/bbk_English.yaml",
    "bbk_task_utils": "https://raw.githubusercontent.com/kundeshwar-BharatGen/BhashaBench/babd1e1d97d5361da53fe1f11b941400399206e0/lm_eval/tasks/bbk/utils_bbk.py",
    "agrieval_community_terms": "https://raw.githubusercontent.com/YanPioneer/AgriEval/46f92806e3af884aa62423a8561cd86cbbff748d/AgriBench%20%E6%95%B0%E6%8D%AE%E9%9B%86%E7%A4%BE%E5%8C%BA%E8%AE%B8%E5%8F%AF%E5%8D%8F%E8%AE%AE.md",
    "agrieval_evaluator": "https://raw.githubusercontent.com/YanPioneer/AgriEval/46f92806e3af884aa62423a8561cd86cbbff748d/eval/run_multi_choice_base.py",
    "agrieval_code_tree": "https://api.github.com/repos/YanPioneer/AgriEval/git/trees/main?recursive=1",
    "agrieval_metadata": "https://huggingface.co/api/datasets/PaperHarvester/AgriEval",
    "agmmu_metadata": "https://huggingface.co/api/datasets/AgMMU/AgMMU_v1",
    "agrotools_metadata": "https://huggingface.co/api/datasets/AgroTools/AgroTools",
    "agrotools_card": "https://huggingface.co/datasets/AgroTools/AgroTools/raw/main/README.md",
    "dew_logiq_metadata": "https://huggingface.co/api/datasets/msu-ceco/dew-logiq",
    "dew_mathq_metadata": "https://huggingface.co/api/datasets/msu-ceco/dew-mathq-ncb",
    "farmpro_metadata": "https://huggingface.co/api/datasets/msu-ceco/farmpro-qa-600",
}


def metadata_projection(data: dict) -> dict:
    """Keep identity/schema declarations, never dataset examples or environment."""
    result = {key: data.get(key) for key in ("id", "sha", "gated", "private", "lastModified") if key in data}
    if "cardData" in data:
        card = data.get("cardData") or {}
        result["cardData"] = {key: card[key] for key in ("license", "language", "dataset_info", "configs") if key in card}
    if "siblings" in data:
        result["files"] = [row["rfilename"] for row in data["siblings"]]
    if "tree" in data:
        result["relevant_files"] = [row["path"] for row in data["tree"] if row["path"].lower().startswith("lm_eval/tasks/bbk") or row["path"].lower() in {"license.md", "license.txt", "eval/run_multi_choice_base.py"}]
        result["tree_truncated"] = data.get("truncated")
    return result


def main() -> None:
    raw = ROOT / ".runtime/backup_benchmark_20261003"
    out = ROOT / "results/20261003_backup_benchmark"
    raw.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    receipts = []
    with httpx.Client(timeout=35, follow_redirects=True, trust_env=False, headers={"User-Agent": "agro-route-lab-metadata-audit"}) as client:
        for source_id, url in SOURCES.items():
            receipt = {"source_id": source_id, "url": url, "requested_utc": datetime.now(timezone.utc).isoformat(), "authentication": "ANONYMOUS", "purpose": "METADATA_OR_DOCUMENT_ONLY"}
            try:
                response = client.get(url)
                body = response.content
                receipt.update(http_status=response.status_code, bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), final_url=str(response.url))
                (raw / f"{source_id}.source").write_bytes(body)
                if response.is_success and "json" in response.headers.get("content-type", ""):
                    receipt["metadata"] = metadata_projection(response.json())
            except httpx.HTTPError as exc:
                receipt.update(error_type=type(exc).__name__)
            receipts.append(receipt)
            print(source_id, receipt.get("http_status", receipt.get("error_type")))
    result = {"schema_version": 1, "audit_date_moscow": "2026-10-03", "benchmark_rows_downloaded": 0, "model_requests": 0, "paid_api_spend_usd": 0, "credentials_read": False, "gates_accepted": False, "receipts": receipts}
    (out / "source_receipts.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
