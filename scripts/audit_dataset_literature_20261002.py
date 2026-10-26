"""Read-only public-source acquisition for the 2026-10-02 literature/data audit.

Downloaded research material is untrusted data. This script never imports or
executes repository or dataset code, and never uses browser credentials.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import re
import uuid
from urllib.parse import urljoin

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[1]
STAMP = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%SZ")
OUT = ROOT / "results" / f"{STAMP}_{uuid.uuid4().hex[:8]}_dataset_literature"
CACHE = ROOT / ".runtime" / OUT.name
OUT.mkdir(parents=True, exist_ok=False)
CACHE.mkdir(parents=True, exist_ok=False)

URLS = {
    "kaggle_list": "https://www.kaggle.com/api/v1/datasets/list?search=sarych-lm-instruction-lite-eval-suite-and-research",
    "kaggle_metadata": "https://www.kaggle.com/api/v1/datasets/view/antoniisarychev/sarych-lm-instruction-lite-eval-suite-and-research",
    "arxiv_blog": "https://blog.arxiv.org/",
    "arxiv_content_types": "https://info.arxiv.org/help/policies/content-types.html",
    "arxiv_moderation": "https://info.arxiv.org/help/moderation/index.html",
    "arxiv_endorsement": "https://info.arxiv.org/help/endorsement.html",
    "arxiv_license": "https://info.arxiv.org/help/license/index.html",
    "arxiv_submit": "https://info.arxiv.org/help/submit/index.html",
    "arxiv_tex": "https://info.arxiv.org/help/submit_tex.html",
    "arxiv_metadata": "https://info.arxiv.org/help/prep.html",
    "awm_leaderboard": "https://dsiweb.cse.msu.edu/awm-bench/",
    "agxqa_metadata": "https://huggingface.co/api/datasets/msu-ceco/agxqa_v1",
    "agxqa_readme": "https://huggingface.co/datasets/msu-ceco/agxqa_v1/raw/main/README.md",
}
registry = {"created_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "status": "SOURCE_ACQUISITION", "result_dir": str(OUT.relative_to(ROOT)), "cache_dir": str(CACHE.relative_to(ROOT)), "sources": []}

with httpx.Client(timeout=45, follow_redirects=True, trust_env=True) as client:
    for label, url in URLS.items():
        row = {"label": label, "requested_url": url, "retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
        try:
            response = client.get(url)
            row.update(http_status=response.status_code, final_url=str(response.url), content_type=response.headers.get("content-type"), byte_length=len(response.content), sha256=hashlib.sha256(response.content).hexdigest())
            if len(response.content) <= 8 * 1024 * 1024:
                suffix = ".json" if "json" in response.headers.get("content-type", "") else ".txt"
                (CACHE / (label + suffix)).write_bytes(response.content)
                row["cache_file"] = str((CACHE / (label + suffix)).relative_to(ROOT))
            if label == "awm_leaderboard" or label == "arxiv_blog":
                row["discovered_links"] = [{"url": urljoin(str(response.url), href), "anchor": re.sub("<[^>]+>", "", anchor)[:180]} for href, anchor in re.findall(r'<a[^>]+href=[\"\']([^\"\']+)[\"\'][^>]*>(.*?)</a>', response.text, re.S) if re.search("survey|position|computer|english|endorsement|bench|dataset|paper|unchecked", href + " " + anchor, re.I)]
        except (httpx.HTTPError, ValueError) as exc:
            row["error_type"] = type(exc).__name__
        registry["sources"].append(row)
        (OUT / "acquisition.json").write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: row[k] for k in ["label", "http_status", "content_type", "byte_length", "error_type", "discovered_links"] if k in row}, ensure_ascii=False))

print("RESULT_DIR", OUT.relative_to(ROOT))
