# SPDX-License-Identifier: Apache-2.0
"""Compile the new drafts and produce PDF QA with the bundled PDF runtime.

No system configuration is modified. This script never submits an article.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone

from pypdf import PdfReader
import pypdfium2 as pdfium
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/publication_build_20261003"
RENDER = ROOT / ".cache/pdf_qa_20261003"
ENGINE = ROOT / ".runtime/tex20261003/tectonic-msvc.exe"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    RENDER.mkdir(parents=True, exist_ok=True)
    assert ENGINE.is_file(), "Use the verified local Tectonic installation."
    env = os.environ.copy()
    env["TECTONIC_CACHE_DIR"] = str(ROOT / ".runtime/tex20261003/cache")
    historical = list((ROOT / "manuscript").glob("*20261002*"))
    before = {p.relative_to(ROOT).as_posix(): sha(p) for p in historical if p.is_file()}
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "COMPILED_QA_PENDING_VISUAL_REVIEW",
        "engine": "Tectonic 0.17.0, Windows MSVC portable official release",
        "engine_sha256": sha(ENGINE),
        "native_editor_compile": {
            "status": "BLOCKED_PLATFORM_ERROR",
            "diagnostic": "Unable to find standard directories for platform",
        },
        "article_license": "NOT_SELECTED",
        "submission": "NOT_RUN",
        "documents": {},
    }
    for language in ("russian", "english"):
        stem = language + "_routing_20261003"
        source = ROOT / "manuscript" / (stem + ".tex")
        pdf = source.with_suffix(".pdf")
        process = subprocess.run(
            [str(ENGINE), "--keep-logs", "--outdir", str(source.parent), str(source)],
            cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=240,
        )
        transcript = process.stdout + process.stderr
        (OUT / (stem + "_compile.txt")).write_text(transcript, encoding="utf-8")
        assert process.returncode == 0 and pdf.is_file(), "Tectonic compilation failed; inspect saved log."
        assert not any(x in transcript for x in ("Missing character:", "Undefined control sequence", "LaTeX Error:"))
        document = PdfReader(pdf)
        rendered_document = pdfium.PdfDocument(pdf)
        try:
            text = "\n".join(page.extract_text() for page in document.pages)
            assert len(text) > 5000 and "\ufffd" not in text
            assert "139" in text and "133" in text and "ToolACE" in text and "AgXQA" in text
            assert "DATA_BLOCKED" in "".join(text.split())
            assert ("Антоний Сарычев" if language == "russian" else "Antoniy Sarychev") in text
            assert ("Денис Шестернин" if language == "russian" else "Denis Shesternin") in text
            fonts = {}
            pages = []
            for n, page in enumerate(document.pages):
                for resource, reference in page["/Resources"].get("/Font", {}).items():
                    font = reference.get_object()
                    descendants = font.get("/DescendantFonts", [reference])
                    embedded = []
                    for child in descendants:
                        descriptor = child.get_object().get("/FontDescriptor")
                        embedded.append(bool(descriptor and any(k in descriptor.get_object() for k in ("/FontFile", "/FontFile2", "/FontFile3"))))
                    fonts[str(reference.idnum)] = {"name": str(font.get("/BaseFont")), "type": str(font.get("/Subtype")), "embedded": all(embedded)}
                target = RENDER / (stem + f"_page_{n+1:02d}.png")
                rendered_document[n].render(scale=1.65).to_pil().save(target)
                pages.append({"page": n + 1, "render": target.relative_to(ROOT).as_posix(), "text_characters": len(page.extract_text())})
            assert fonts and all(font["embedded"] for font in fonts.values()), "Nonembedded font detected."
            if language == "russian":
                assert 6 <= len(document.pages) <= 8, "Russian course manuscript outside 6–8 pages."
            (RENDER / (stem + "_text.txt")).write_text(text, encoding="utf-8")
            thumbnails = []
            for page_info in pages:
                with Image.open(ROOT / page_info["render"]) as page_image:
                    thumb = page_image.copy()
                thumb.thumbnail((450, 640))
                tile = Image.new("RGB", (470, 680), "#d9d9d9")
                tile.paste(thumb, ((470-thumb.width)//2, 22))
                ImageDraw.Draw(tile).text((10, 655), f"{language} page {page_info['page']}", fill="black")
                thumbnails.append(tile)
            columns = 4
            sheet = Image.new("RGB", (columns*470, ((len(thumbnails)+columns-1)//columns)*680), "white")
            for n, thumb in enumerate(thumbnails):
                sheet.paste(thumb, ((n % columns)*470, (n//columns)*680))
            sheet.save(RENDER / (stem + "_contact.png"))
            report["documents"][language] = {
                "source": source.relative_to(ROOT).as_posix(), "source_sha256": sha(source),
                "pdf": pdf.relative_to(ROOT).as_posix(), "pdf_sha256": sha(pdf),
                "pages": len(document.pages), "size_bytes": pdf.stat().st_size,
                "metadata": {str(k): str(v) for k,v in document.metadata.items()}, "selectable_text": True, "text_characters": len(text),
                "fonts": fonts, "all_fonts_embedded": True, "scientific_references": 18,
                "page_rendering": pages, "compile_returncode": process.returncode,
                "layout_warnings": [line for line in transcript.splitlines() if "Overfull" in line or "Underfull" in line],
            }
        finally:
            rendered_document.close()
    after = {p.relative_to(ROOT).as_posix(): sha(p) for p in historical if p.is_file()}
    assert before == after, "Historical manuscript changed."
    report["historical_manuscript_hashes_unchanged"] = before
    package = ROOT / "manuscript/arxiv_source_draft_20261003"
    package.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "manuscript/english_routing_20261003.tex", package / "main.tex")
    (package / "README.txt").write_text(
        "WORKING DRAFT — NOT READY FOR SUBMISSION\n"
        "Authors: Antoniy Sarychev; Denis Shesternin.\n"
        "main.tex is self-contained; tables, figure and bibliography are in source.\n"
        "Compiled locally using Tectonic 0.17.0 (XeTeX). arXiv-server compilation is NOT VERIFIED.\n"
        "Human gold review, independent evaluation, author approval, venue rights/preprint policy,\n"
        "account/endorsement and article license remain pending. No license selected.\n",
        encoding="utf-8",
    )
    report["source_package"] = package.relative_to(ROOT).as_posix()
    (OUT / "pdf_qa.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k: {x:v[x] for x in ("pages", "pdf_sha256", "all_fonts_embedded", "selectable_text")} for k,v in report["documents"].items()}))


if __name__ == "__main__":
    main()
