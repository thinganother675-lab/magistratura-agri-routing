# SPDX-License-Identifier: Apache-2.0
"""Fetch public official publication rules; no account actions or credentials."""
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen
from datetime import datetime, timezone
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "publication_sources_20261003"
CACHE = ROOT / ".cache" / "publication_sources_20261003"
OUT.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)
sources = {
    "rgau_conference": "https://www.timacad.ru/legacy-uploads/files/20260727/1785149428_info-pismo-18.pdf",
    "rgau_contest": "https://www.timacad.ru/legacy-uploads/files/20260727/1785149423_pologen-k-18.pdf",
}
records = []
for name, url in sources.items():
    record = {"id": name, "url": url, "retrieved_utc": datetime.now(timezone.utc).isoformat()}
    try:
        with urlopen(Request(url, headers={"User-Agent": "Research publication rules verification"}), timeout=30) as response:
            data = response.read()
            record.update(http_status=response.status, content_type=response.headers.get("Content-Type"))
        if not data.startswith(b"%PDF"):
            raise ValueError("Not PDF")
        local = CACHE / (name + ".pdf")
        local.write_bytes(data)
        reader = PdfReader(local)
        record.update(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data), page_count=len(reader.pages), cache_path=local.relative_to(ROOT).as_posix(), redistribution="REFERENCE_ONLY_NOT_RELEASED")
        text = "\n\n".join(f"PAGE {i + 1}\n{page.extract_text()}" for i, page in enumerate(reader.pages))
        (CACHE / (name + ".txt")).write_text(text, encoding="utf-8")
        print(name, record["http_status"], record["page_count"], record["sha256"])
    except Exception as exc:
        record["error"] = str(exc)
        print(name, "FAILED", type(exc).__name__)
    records.append(record)
(OUT / "acquisition.json").write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
