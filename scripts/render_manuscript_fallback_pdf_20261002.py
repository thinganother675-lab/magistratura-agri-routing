"""Explicit ReportLab fallback; never claims native/terminal TeX compilation.

Run with the bundled document runtime after the timed inference window. It
creates a PDF from the same Markdown and renders every page for visual review.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "manuscript/english_routing_20261002.md"
TARGET = ROOT / "manuscript/english_routing_20261002_reportlab_draft.pdf"
RUN = ROOT / "results/20261002_170443Z_21722066_dataset_literature"
NATIVE_DIAGNOSTIC = "Unable to find standard directories for platform"


def rich(text: str) -> str:
    tokens = []
    def store(value: str) -> str:
        tokens.append(value)
        return f"PLACEHOLDER{len(tokens)-1}FINISH"
    text = re.sub(r"`([^`]+)`", lambda m: store('<font name="Courier" size="8.1">' + escape(m.group(1)) + '</font>'), text)
    text = re.sub(r"\*\*([^*]+)\*\*", lambda m: store('<b>'+rich(m.group(1))+'</b>'), text)
    text = re.sub(r"\*([^*]+)\*", lambda m: store('<i>'+rich(m.group(1))+'</i>'), text)
    text = re.sub(r"https?://[^\s]+", lambda m: store('<link href="'+escape(m.group(0))+'" color="#1F4F80">'+escape(m.group(0))+'</link>'), text)
    text = escape(text)
    for i, value in enumerate(tokens): text = text.replace(f"PLACEHOLDER{i}FINISH", value)
    return text


def main() -> None:
    # Windows font embedding uses the installed system fonts; no fonts are distributed separately.
    fonts = Path("C:/Windows/Fonts")
    for name, file in [("Research", "arial.ttf"), ("Research-Bold", "arialbd.ttf"), ("Research-Italic", "ariali.ttf"), ("Research-BoldItalic", "arialbi.ttf")]:
        pdfmetrics.registerFont(TTFont(name, str(fonts/file)))
    pdfmetrics.registerFontFamily("Research", normal="Research", bold="Research-Bold", italic="Research-Italic", boldItalic="Research-BoldItalic")
    styles = getSampleStyleSheet()
    body = ParagraphStyle("BodyResearch", fontName="Research", fontSize=9.35, leading=12.7,
                          alignment=TA_JUSTIFY, spaceAfter=5.5, splitLongWords=True)
    heading = ParagraphStyle("ResearchHeading", parent=body, fontName="Research-Bold", fontSize=12.5,
                             leading=16, spaceBefore=11, spaceAfter=6, alignment=TA_LEFT, keepWithNext=True)
    subheading = ParagraphStyle("ResearchSubheading", parent=body, fontName="Research-Bold", fontSize=10.1,
                                leading=13, spaceBefore=8, spaceAfter=5, alignment=TA_LEFT, keepWithNext=True)
    title = ParagraphStyle("ResearchTitle", parent=body, fontName="Research-Bold", fontSize=16.1,
                           leading=20, alignment=TA_CENTER, spaceAfter=9)
    center = ParagraphStyle("CenterResearch", parent=body, fontSize=9.2, leading=12.3, alignment=TA_CENTER)
    note = ParagraphStyle("NoteResearch", parent=body, fontSize=8.2, leading=11, alignment=TA_LEFT,
                          textColor=colors.HexColor("#614628"), spaceAfter=8)
    cell = ParagraphStyle("CellResearch", parent=body, fontSize=7.7, leading=10.0, alignment=TA_LEFT, spaceAfter=0)
    citation = ParagraphStyle("CitationResearch", parent=body, fontSize=8.15, leading=10.9,
                              alignment=TA_LEFT, spaceAfter=6)
    provenance = ParagraphStyle("ProvenanceResearch", parent=body, alignment=TA_LEFT)
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    story = [Paragraph(rich(lines[0].removeprefix("# ")), title),
             Paragraph("Antonii Sarychev and Denis Shesternin", center),
             Paragraph("Russian State Agrarian University – Moscow Timiryazev Agricultural Academy, Moscow, Russia", center),
             Paragraph("Working draft · 2 October 2026 · author approval and human validation pending · not submitted", center),
             Spacer(1, 6),
             Paragraph("<b>Renderer: ReportLab from Markdown; TeX compilation UNVERIFIED.</b> Native Codex compilation failed with: <i>"+NATIVE_DIAGNOSTIC+"</i>. This PDF is a reading artifact, not proof of TeX compilation or arXiv submission readiness.", note)]
    index = lines.index("## Abstract")
    tables = 0
    captions = ["Table 1. Frozen-run quality, actual cloud calls and request latency (150 cases per policy).",
                "Table 2. Correct decisions by category; related source/scenario variants are correlated.",
                "Table 3. Reported token usage by policy/provider; unknown usage is not zero.",
                "Table 4. Supplementary observed DEV36 comparison; known cost in USD plus count of unknown charge events. Not confirmatory; provider timeout tails confound latency."]
    references = False
    width = A4[0] - 36*mm
    while index < len(lines):
        line = lines[index].strip()
        if not line: index += 1; continue
        if line.startswith("!["):
            match = re.match(r"!\[[^\]]*\]\(([^)]+)\)", line)
            if not match: raise ValueError("Malformed manuscript figure reference")
            figure = Image(str(SOURCE.parent/match.group(1)))
            figure.drawHeight *= width/figure.drawWidth; figure.drawWidth = width
            next_caption = lines[index+2] if index+2 < len(lines) and lines[index+2].startswith("Figure 1.") else "Figure 1. Frozen historical quality difference."
            story.append(KeepTogether([figure, Paragraph(rich(next_caption), note), Spacer(1, 5)]))
            index += 3 if next_caption.startswith("Figure 1.") else 1; continue
        if line.startswith("### "):
            story.append(Paragraph(rich(line[4:]), subheading)); index += 1; continue
        if line.startswith("## "):
            references = line == "## References"
            story.append(Paragraph(rich(line[3:]), heading)); index += 1; continue
        if line.startswith("|"):
            data = []
            while index < len(lines) and lines[index].startswith("|"):
                row = [v.strip() for v in lines[index].strip("|").split("|")]
                if not all(re.fullmatch(r"[:\-]+", v) for v in row): data.append(row)
                index += 1
            columns = len(data[0]); first_width = 143 if columns == 7 else 148 if columns == 6 else 146
            if columns == 8:
                weights = [94, 44, 45, 48, 55, 40, 40, 128]
                colwidths = [value * width/sum(weights) for value in weights]
            else:
                colwidths = [first_width]+[(width-first_width)/(columns-1)]*(columns-1)
            cells = [[Paragraph(rich(v), cell) for v in row] for row in data]
            table = Table(cells, colWidths=colwidths, repeatRows=1, hAlign="LEFT")
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6EDF2")),
                ("LINEABOVE", (0, 0), (-1, 0), 0.65, colors.HexColor("#486077")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.55, colors.HexColor("#486077")),
                ("LINEBELOW", (0, -1), (-1, -1), 0.65, colors.HexColor("#486077")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7F9")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(KeepTogether([Paragraph(rich(captions[tables]), note), table, Spacer(1, 9)])); tables += 1; continue
        paragraph_style = citation if references else provenance if re.search(r"`(?:[0-9a-f]{64}|results/)", line) else body
        story.append(Paragraph(rich(line), paragraph_style)); index += 1

    def page(canvas, document):
        canvas.saveState()
        canvas.setFont("Research", 7.3); canvas.setFillColor(colors.HexColor("#445464"))
        canvas.drawString(18*mm, A4[1]-12*mm, "Agricultural routing · Working draft · 2 October 2026")
        canvas.drawRightString(A4[0]-18*mm, A4[1]-12*mm, str(document.page))
        canvas.setStrokeColor(colors.HexColor("#D9E0E7")); canvas.line(18*mm, A4[1]-14*mm, A4[0]-18*mm, A4[1]-14*mm)
        canvas.setFont("Research", 7.1)
        canvas.drawString(18*mm, 11*mm, "ReportLab rendering from Markdown; native TeX compiler blocked; human review pending.")
        canvas.restoreState()

    document = SimpleDocTemplate(str(TARGET), pagesize=A4, rightMargin=18*mm, leftMargin=18*mm,
                                 topMargin=19*mm, bottomMargin=18*mm,
                                 title=lines[0].removeprefix("# "), author="Antonii Sarychev; Denis Shesternin")
    document.build(story, onFirstPage=page, onLaterPages=page)
    image_dir = ROOT / ".runtime/20261002_170443Z_21722066_dataset_literature/manuscript_pdf_pages"
    image_dir.mkdir(exist_ok=True)
    pdf = pdfium.PdfDocument(str(TARGET))
    pages = []
    for index in range(len(pdf)):
        page_object = pdf[index]
        image_path = image_dir/f"page_{index+1:02d}.png"
        page_object.render(scale=1.25).to_pil().save(image_path)
        pages.append({"page": index+1, "png": str(image_path.relative_to(ROOT)), "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest()})
        page_object.close()
    pdf.close()
    status = {"created_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "renderer": "ReportLab",
              "source": str(SOURCE.relative_to(ROOT)), "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              "pdf": str(TARGET.relative_to(ROOT)), "pdf_sha256": hashlib.sha256(TARGET.read_bytes()).hexdigest(),
              "pages": len(pages), "page_images": pages, "all_pages_visually_inspected": False,
              "native_tex_compilation": "BLOCKED_UNVERIFIED", "native_platform_diagnostic": NATIVE_DIAGNOSTIC,
              "human_review": False, "arxiv_submission": "NOT_RUN", "manuscript_license": "NOT_SELECTED"}
    (RUN/"manuscript_build_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"pdf": str(TARGET), "pages": len(pages), "renderer": "ReportLab", "native_tex": "UNVERIFIED"}))


if __name__ == "__main__":
    main()
