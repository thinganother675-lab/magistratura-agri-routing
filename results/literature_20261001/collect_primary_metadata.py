"""Fetch public bibliography metadata only; never downloads models or PDFs.

ArXiv records are candidates, not automatically peer-reviewed publications.
The current HTML may contain revisions after the review cutoff; first-submission
date is retained, and version-sensitive findings require manual confirmation.
"""
import concurrent.futures
import datetime
import html
import json
import re
import urllib.request
from pathlib import Path

GROUPS = {
    "routing_cascades": "2305.05176 2406.18665 2404.14618 2410.10347 2403.12031 2309.15789 2310.12963 2410.03834 2502.08773 2502.18482 2407.10834 2506.03880 2602.03478 2503.10657 2601.07206 2603.04445 2605.18796 2606.27457 2608.20316 2608.06867 2502.02743 2506.16655",
    "uncertainty_abstention": "2303.08896 2306.13063 2406.15927 2404.03163 2407.18418 2410.24029 2404.10960 2507.16199 2510.01152 2609.27822",
    "tools_rag": "2302.04761 2307.16789 2305.15334 2304.08244 2409.00920 2406.12045 2506.07982 2309.15817 2305.11554 2303.09014 2310.11511 2401.15884 2309.15217 2312.10997",
    "agriculture": "2407.04721 2508.08632 2503.04788 2410.08405 2512.10624 2601.08308 2605.22366 2401.01600 2412.02158 2510.04002",
    "practical_local_inference": "2309.06180 2306.00978 2210.17323 2211.10438 2307.08691 2407.08608 2302.01318 2402.17764 2505.09388 2412.15115 2503.19786 2501.12948 2407.21783",
}

def clean(value):
    return re.sub(r"\s+", " ", html.unescape(value)).strip()

def fetch(item):
    group, arxiv_id = item
    url = "https://arxiv.org/abs/" + arxiv_id
    entry = {"id": "arxiv:" + arxiv_id, "group": group, "primary_url": url,
             "retrieved_for_cutoff": "2026-10-01", "scientific_candidate": True,
             "verification_level": "primary_metadata_only", "peer_review_status": "not_verified",
             "full_text_reviewed": False}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Research bibliography metadata audit"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            source = resp.read().decode("utf-8", errors="replace")
        metadata = {}
        for name, value in re.findall(r'<meta\s+name="([^"]+)"\s+content="([^"]*)"', source):
            metadata.setdefault(name, []).append(clean(value))
        entry["title"] = metadata["citation_title"][0]
        entry["authors"] = metadata.get("citation_author", [])
        entry["submission_date"] = metadata.get("citation_date", [None])[0]
        entry["arxiv_version"] = metadata.get("citation_arxiv_id", [arxiv_id])[0]
        entry["doi"] = metadata.get("citation_doi", [None])[0]
        entry["journal_reference"] = metadata.get("citation_journal_title", [None])[0]
        dates = re.findall(r'\[v\d+\].*?([A-Z][a-z]{2},?\s+\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4})', source)
        entry["version_date_strings"] = dates
        first = entry["submission_date"]
        entry["within_cutoff"] = bool(first and first.replace("/", "-")[:10] <= "2026-10-01")
        entry["fetch_status"] = "verified_primary_record"
    except Exception as exc:
        entry["fetch_status"] = "unverified_fetch_failed"
        entry["error_type"] = type(exc).__name__
    return entry

def main():
    items = [(group, paper) for group, ids in GROUPS.items() for paper in ids.split()]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        entries = list(pool.map(fetch, items))
    Path(__file__).with_name("papers.json").write_text(json.dumps({
        "cutoff_date": "2026-10-01", "method": "Primary arXiv HTML citation metadata; thematic discovery, not systematic review",
        "entries": entries}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"attempted": len(entries), "verified_primary_records": sum(e["fetch_status"] == "verified_primary_record" for e in entries),
                      "failed": [e["id"] for e in entries if e["fetch_status"] != "verified_primary_record"]}))

if __name__ == "__main__":
    main()
