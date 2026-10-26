# SPDX-License-Identifier: Apache-2.0
"""Refresh public scientific metadata without changing historical literature records."""
import concurrent.futures
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "publication_sources_20261003"
OUT.mkdir(parents=True, exist_ok=True)
HISTORY = ROOT / "results/20261002_170443Z_21722066_dataset_literature/verified_references_reading_ledger.json"

class CitationParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.metadata = {}
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and a.get("name", "").startswith("citation_"):
            self.metadata.setdefault(a["name"], []).append(a.get("content", ""))

def fetch(entry):
    result = dict(entry)
    result.update(reading_status="FULL_TEXT_RELEVANT_SECTIONS_READ", reading_evidence="Prior 2026-10-02 selected-section ledger; full paper not claimed", historical_ledger=HISTORY.relative_to(ROOT).as_posix(), metadata_checked_utc=datetime.now(timezone.utc).isoformat())
    try:
        with urlopen(Request(entry["primary_url"], headers={"User-Agent": "Academic citation verification"}), timeout=30) as response:
            raw = response.read()
            result["current_http_status"] = response.status
        parser = CitationParser()
        parser.feed(raw.decode("utf-8"))
        result["current_citation_metadata"] = parser.metadata
        result["metadata_html_sha256"] = hashlib.sha256(raw).hexdigest()
        title = parser.metadata.get("citation_title", [""])[0]
        normalize = lambda x: re.sub(r"\s+", " ", x).strip().casefold()
        result["title_matches_history"] = normalize(title) == normalize(entry["title"])
        result["current_metadata_verified"] = bool(title and parser.metadata.get("citation_author"))
    except Exception as exc:
        result.update(current_metadata_verified=False, current_error=type(exc).__name__ + ": " + str(exc))
    return result

entries = json.loads(HISTORY.read_text(encoding="utf-8"))["entries"]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    refreshed = list(pool.map(fetch, entries))

# Verify the published ToolACE venue independently of the preserved arXiv ledger.
toolace = next(e for e in refreshed if e['id'] == '2409.00920')
toolace_url = 'https://proceedings.iclr.cc/paper_files/paper/2025/hash/663865ea167425c6c562cb0b6bcf76c7-Abstract-Conference.html'
try:
    with urlopen(toolace_url, timeout=30) as response:
        raw = response.read()
        published_status = response.status
    html = raw.decode('utf-8')
    if 'ToolACE: Winning the Points of LLM Function Calling' not in html or 'International Conference on Learning Representations 2025' not in html:
        raise ValueError('Proceedings title/venue did not match ToolACE')
    bibtex_url = 'https://proceedings.iclr.cc/paper_files/paper/3188-/bibtex'
    with urlopen(bibtex_url, timeout=30) as response:
        bibtex = response.read()
    toolace.update(venue='ICLR 2025', publication_year=2025, published_primary_url=toolace_url,
                   published_pages=re.search(r'pages\s*=\s*\{([^}]+)\}', bibtex.decode('utf-8')).group(1),
                   venue_verification_status='PRIMARY_PROCEEDINGS_VERIFIED', published_metadata_http_status=published_status,
                   published_metadata_html_sha256=hashlib.sha256(raw).hexdigest(),
                   published_bibtex_url=bibtex_url, published_bibtex=bibtex.decode('utf-8'),
                   published_bibtex_sha256=hashlib.sha256(bibtex).hexdigest(),
                   venue_metadata_checked_utc=datetime.now(timezone.utc).isoformat(),
                   published_reading_status='ABSTRACT_ONLY',
                   published_reading_scope='Primary proceedings abstract/metadata/BibTeX verified; prior arXiv relevant-section reading preserved')
except Exception as exc:
    toolace.update(venue_verification_status='UNVERIFIED_THIS_REFRESH', venue_verification_error=type(exc).__name__ + ': ' + str(exc))

doi = "10.1016/j.compag.2024.109349"
agx = {"id": "doi:" + doi, "primary_url": "https://doi.org/" + doi, "reading_status": "METADATA_ONLY", "reading_evidence": "Crossref primary metadata; publisher complete article not read", "metadata_checked_utc": datetime.now(timezone.utc).isoformat()}
try:
    with urlopen("https://api.crossref.org/works/" + doi, timeout=30) as response:
        message = json.load(response)["message"]
        agx.update(current_http_status=response.status)
    agx.update(title=message["title"][0], authors=[a.get("given", "") + " " + a.get("family", "") for a in message.get("author", [])], initial_year=2024, venue=message.get("container-title", [None])[0], volume=message.get("volume"), article_number=message.get("article-number"), doi=doi, published=message.get("published"), current_metadata_verified=True)
except Exception as exc:
    agx.update(current_metadata_verified=False, current_error=str(exc))
refreshed.append(agx)
document = {"verified_date_moscow": "2026-10-03", "scientific_count": len(refreshed), "current_metadata_verified_count": sum(e["current_metadata_verified"] for e in refreshed), "reading_scope": "17 prior selected full-text sections, 1 current metadata only; no full-paper or human review claim", "entries": refreshed}
(OUT / "verified_bibliography_18.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
lines = ["# Проверенная научная библиография для нового draft — 3 октября 2026", "", "18 научных источников. Метаданные обновлены по первичным страницам arXiv, Crossref и ICLR proceedings; чтение релевантных разделов 17 PDF подтверждается сохранённым ledger 02.10, а не выдаётся за новое полное чтение. AgXQA: METADATA_ONLY. Препринт не означает завершённое рецензирование. API docs, GitHub, model cards и publication rules не включены.", ""]
for i, e in enumerate(refreshed, 1):
    md = e.get("current_citation_metadata", {})
    authors = md.get("citation_author") or e.get("authors", [])
    short = "; ".join(authors[:3]) + ("; et al." if len(authors) > 3 else "")
    title = md.get("citation_title", [e.get("title", "UNVERIFIED")])[0]
    venue = e.get("venue") or "arXiv preprint; рецензируемый venue не подтверждён этой проверкой"
    if e.get('published_pages'):
        venue += ', pp. ' + e['published_pages'].replace('--', '–')
    lines += [f"{i}. {short}. **{title}**. {e.get('initial_year', 'UNKNOWN')}. {venue}. [{e['id']}]({e['primary_url']}).", f"   Reading: `{e['reading_status']}`. {e.get('sections_read', e['reading_evidence'])}. Live metadata: {'VERIFIED' if e['current_metadata_verified'] else 'UNVERIFIED'}. Full paper read: false.", ""]
    if e.get('venue_verification_status') == 'PRIMARY_PROCEEDINGS_VERIFIED':
        lines += [f"   Published version: [primary ICLR 2025 proceedings]({e['published_primary_url']}); abstract and BibTeX verified, HTTP200. Current published-version reading: `ABSTRACT_ONLY`; prior arXiv selected-section reading retained.", ""]
lines += ["Полные списки авторов, даты/version history, DOI и provenance: [verified_bibliography_18.json](../results/publication_sources_20261003/verified_bibliography_18.json). Оригинальные исторические реестры не изменены.", ""]
(ROOT / "docs/VERIFIED_BIBLIOGRAPHY_20261003_RU.md").write_text("\n".join(lines), encoding="utf-8")
print(json.dumps({"scientific_count": len(refreshed), "current_metadata_verified_count": document["current_metadata_verified_count"], "title_mismatches": [e["id"] for e in refreshed if e.get("title_matches_history") is False], "failures": [e["id"] for e in refreshed if not e["current_metadata_verified"]]}))
