"""Build the 20261005 editorial RU/EN manuscripts from their Markdown sources.

Markdown is the single editable source; TeX and DOCX are rendered from it so the
formats cannot drift. No factual content is generated here.
Usage: python scripts/build_editorial_20261005.py [tex|docx|all] [revision, e.g. r2]
"""
from pathlib import Path
import re
import sys

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
MS = ROOT / "manuscript"
DOCS = {
    "ru": MS / "russian_resource_20261005_claude.md",
    "en": MS / "english_resource_20261005_claude.md",
}
REF_HEADINGS = {"Список литературы", "Технические источники", "References", "Technical sources"}
AUTHORS = {"ru": "Антоний Сарычев; Денис Шестернин", "en": "Antoniy Sarychev; Denis Shesternin"}


def parse(path):
    """Return a list of (kind, payload) blocks."""
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks, i = [], 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                row = [x.strip() for x in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", x) for x in row):
                    rows.append(row)
                i += 1
            blocks.append(("table", rows))
        else:
            for prefix, kind in (("### ", "h3"), ("## ", "h2"), ("# ", "title")):
                if line.startswith(prefix):
                    blocks.append((kind, line[len(prefix):]))
                    break
            else:
                fig = re.fullmatch(r"!\[(.+)\]\((.+)\)", line)
                if fig:
                    blocks.append(("figure", (fig[1], fig[2])))
                elif re.match(r"(УДК|UDC) ", line):
                    blocks.append(("udk", line))
                elif re.match(r"(\d+|Т\d+|T\d+)\. ", line):
                    blocks.append(("ref", line))
                elif re.match(r"(Таблица|Table) \d+\.", line):
                    blocks.append(("caption", line))
                else:
                    blocks.append(("para", line))
            i += 1
    return blocks


# ---------------------------------------------------------------- TeX

def tex_escape(s):
    out = []
    for ch in s:
        out.append({"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
                    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\^{}"}.get(ch, ch))
    return "".join(out)


def tex_inline(s):
    links = []

    def keep(tex):
        links.append(tex)
        return f"\x00{len(links) - 1}\x00"

    s = re.sub(r"https?://[^\s)]+", lambda m: keep(r"\url{" + m[0] + "}"), s)
    s = re.sub(r"DOI: (10\.[^\s]+?)(\.?)(?=\s|$)",
               lambda m: keep(r"DOI:~\href{https://doi.org/" + m[1] + "}{" + tex_escape(m[1]) + "}") + m[2], s)
    s = re.sub(r"arXiv:(\d{4}\.\d{4,5})", lambda m: keep(r"\href{https://arxiv.org/abs/" + m[1] + "}{arXiv:" + m[1] + "}"), s)
    s = tex_escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", s)
    s = re.sub(r"\*(.+?)\*", r"\\emph{\1}", s)
    s = re.sub(r"(\d) (\d{3})", r"\1\\,\2", s)  # thin space in 2\,935-style numbers
    return re.sub("\x00(\\d+)\x00", lambda m: links[int(m[1])], s)


RU_PREAMBLE = r"""\documentclass[14pt,a4paper]{extarticle}
\usepackage[top=20mm,bottom=20mm,left=20mm,right=15mm]{geometry}
\usepackage{fontspec}
\setmainfont{Times New Roman}
\setmonofont{Consolas}[Scale=MatchLowercase]
\usepackage{polyglossia}
\setdefaultlanguage{russian}
\setotherlanguage{english}
\usepackage{booktabs,array,graphicx,titlesec,enumitem}
\usepackage[hyphens]{url}
\usepackage[hidelinks]{hyperref}
\setlength{\parindent}{1.25cm}
\setlength{\parskip}{0pt}
\setlength{\emergencystretch}{2em}
\clubpenalty=10000
\widowpenalty=10000
\sloppy
\urlstyle{same}
\makeatletter
\renewcommand\normalsize{\@setfontsize\normalsize\@xivpt{16.1}}
\makeatother
\AtBeginDocument{\normalsize}
\titleformat{\section}{\centering\bfseries}{}{0pt}{}
\titlespacing*{\section}{0pt}{8pt}{3pt}
\titleformat{\subsection}{\bfseries\itshape}{}{0pt}{}
\titlespacing*{\subsection}{\parindent}{6pt}{2pt}
"""

EN_PREAMBLE = r"""\documentclass[10pt,a4paper]{article}
\usepackage[margin=22mm]{geometry}
\usepackage{fontspec}
\usepackage{newunicodechar}
\newunicodechar{τ}{\ensuremath{\tau}}
\usepackage{booktabs,array,graphicx,titlesec,enumitem}
\usepackage[hyphens]{url}
\usepackage[hidelinks]{hyperref}
\setlength{\parskip}{3pt}
\setlength{\emergencystretch}{2em}
\clubpenalty=10000
\widowpenalty=10000
\urlstyle{same}
\titleformat{\section}{\large\bfseries}{}{0pt}{}
\titleformat{\subsection}{\normalsize\bfseries}{}{0pt}{}
"""


def tex_table(rows, small):
    n = len(rows[0])
    widths = {3: [0.50, 0.22, 0.22], 4: [0.33, 0.24, 0.12, 0.25], 5: [0.30, 0.12, 0.16, 0.15, 0.17]}[n]
    spec = "".join((r">{\raggedright\arraybackslash}" if k == 0 else r">{\centering\arraybackslash}")
                   + f"p{{{w}\\linewidth}}" for k, w in enumerate(widths))
    body = [r"{\centering" + small + r" \setlength{\tabcolsep}{4pt}", r"\begin{tabular}{@{}" + spec + "@{}}", r"\toprule"]
    for j, row in enumerate(rows):
        body.append(" & ".join(tex_inline(c) for c in row) + r" \\")
        if j == 0:
            body.append(r"\midrule")
    body += [r"\bottomrule", r"\end{tabular}\par}"]
    return "\n".join(body)


def build_tex(lang):
    blocks = parse(DOCS[lang])
    title = next(p for k, p in blocks if k == "title")
    small = r"\fontsize{12}{14}\selectfont" if lang == "ru" else r"\small"
    out = [RU_PREAMBLE if lang == "ru" else EN_PREAMBLE,
           r"\hypersetup{pdftitle={" + tex_escape(title) + "},pdfauthor={" + AUTHORS[lang] + "}}",
           r"\begin{document}"]
    in_refs = False
    pending_caption = None
    front = True
    for idx, (kind, p) in enumerate(blocks):
        if kind == "udk":
            out.append(r"\noindent\textbf{" + tex_inline(p) + r"}\par\medskip")
        elif kind == "title":
            out.append(r"\begin{center}\bfseries\large " + tex_inline(p) + r"\end{center}")
        elif kind == "h2":
            if in_refs:
                out.append(r"\end{enumerate}\endgroup")
            front = False
            in_refs = p in REF_HEADINGS
            out.append(r"\section*{" + tex_inline(p) + "}")
            if in_refs:
                refsize = r"\fontsize{11}{13}\selectfont" if lang == "ru" else small
                out.append(r"\begingroup\sloppy" + refsize + r" \begin{enumerate}[label={},leftmargin=0.9cm,itemindent=-0.9cm,itemsep=0pt,parsep=0pt,topsep=2pt]")
        elif kind == "h3":
            out.append(r"\subsection*{" + tex_inline(p) + "}")
        elif kind == "ref":
            out.append(r"\item " + tex_inline(p))
        elif kind == "caption":
            pending_caption = p
        elif kind == "table":
            cap = (r"\noindent{" + small + " " + tex_inline(pending_caption) + r"\par}\nopagebreak\vspace{3pt}") if pending_caption else ""
            out.append(r"\par\smallskip\noindent\begin{minipage}{\linewidth}" + cap + "\n" + tex_table(p, small) + r"\end{minipage}\par\medskip")
            pending_caption = None
        elif kind == "figure":
            cap, path = p
            out.append(r"\begin{figure}[ht]\centering\includegraphics[width=0.9\linewidth]{" + path + r"}"
                       r"\par\smallskip{\small Figure 1. " + tex_inline(cap) + r"\par}\end{figure}")
        else:
            if front and lang == "ru" and idx <= 3:
                # authors and affiliation directly under the title
                style = r"\textbf" if idx == 2 else r"\textit"
                out.append(r"\begin{center}" + style + "{" + tex_inline(p) + r"}\end{center}")
            elif front and lang == "en" and idx <= 3:
                out.append(r"\begin{center}" + tex_inline(p) + r"\end{center}")
            elif front:
                out.append(r"{\noindent" + small + " " + tex_inline(p) + r"\par}\smallskip")
            elif p.startswith("*") and p.endswith("*") and lang == "ru":
                out.append(r"\vspace{6pt}{\noindent\fontsize{11}{13}\selectfont " + tex_inline(p) + r"\par}")
            elif p.startswith("**") and lang == "ru" and not in_refs:
                out.append(r"{\noindent\fontsize{11}{13}\selectfont " + tex_inline(p) + r"\par}\smallskip")
            else:
                out.append(tex_inline(p) + "\n")
    if in_refs:
        out.append(r"\end{enumerate}\endgroup")
    out.append(r"\end{document}")
    target = DOCS[lang].with_suffix(".tex")
    target.write_text("\n".join(out) + "\n", encoding="utf-8")
    return target


# ---------------------------------------------------------------- DOCX

def docx_text(text):
    # Keep numbers, units and compound names together, as the TeX build does.
    text = re.sub(r"(\d) (\d{3})", "\\1\u00a0\\2", text)
    text = text.replace("\u03c4-bench", "\u03c4\u2011bench").replace("\u043f. \u043f.", "\u043f.\u00a0\u043f.").replace(" %", "\u00a0%")
    return text


def docx_inline(paragraph, text, size, italic=False):
    text = docx_text(text)
    for part in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*|https?://[^\s)]+)", text):
        if not part:
            continue
        if re.fullmatch(r"https?://[^\s)]+", part):
            rel = paragraph.part.relate_to(part, RT.HYPERLINK, is_external=True)
            link = OxmlElement("w:hyperlink")
            link.set(qn("r:id"), rel)
            run = OxmlElement("w:r")
            props = OxmlElement("w:rPr")
            sz = OxmlElement("w:sz")
            sz.set(qn("w:val"), str(2 * size))
            props.append(sz)
            run.append(props)
            t = OxmlElement("w:t")
            t.text = part
            run.append(t)
            link.append(run)
            paragraph._p.append(link)
            continue
        run = paragraph.add_run(part.strip("*"))
        run.font.size = Pt(size)
        run.bold = part.startswith("**")
        run.italic = italic or (part.startswith("*") and not part.startswith("**"))


def set_style_font(style, size, family):
    style.font.name = family
    style.font.size = Pt(size)
    style.font.color.rgb = RGBColor(0, 0, 0)
    fonts = style.element.get_or_add_rPr().rFonts
    for key in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn("w:" + key), family)
    for key in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
        fonts.attrib.pop(qn("w:" + key), None)


def build_docx(lang):
    ru = lang == "ru"
    body, small = (14, 12) if ru else (10, 9)
    family = "Times New Roman" if ru else "Cambria"
    d = Document()
    sec = d.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    if ru:
        sec.top_margin = sec.bottom_margin = Cm(2)
        sec.left_margin, sec.right_margin = Cm(2), Cm(1.5)
    else:
        sec.top_margin = sec.bottom_margin = sec.left_margin = sec.right_margin = Cm(2.2)
    for name in ("Normal", "Title", "Heading 1", "Heading 2"):
        set_style_font(d.styles[name], body, family)
        f = d.styles[name].paragraph_format
        f.space_before = f.space_after = Pt(0)
        f.line_spacing = 1
        f.first_line_indent = Cm(1.25 if (name == "Normal" and ru) else 0)
        f.widow_control = True
    if not ru:
        d.styles["Normal"].paragraph_format.space_after = Pt(3)
    for border in d.styles.element.xpath(".//w:pBdr"):
        border.getparent().remove(border)
    for name in ("Title", "Heading 1", "Heading 2"):
        d.styles[name].font.bold = True
        d.styles[name].paragraph_format.keep_with_next = True
        # No hyphenation in titles; CT_PPr is order-sensitive, so insert before spacing/ind/jc.
        ppr = d.styles[name].element.get_or_add_pPr()
        flag = OxmlElement("w:suppressAutoHyphens")
        later = [c for c in ppr if c.tag in {qn("w:spacing"), qn("w:ind"), qn("w:jc"), qn("w:outlineLvl"), qn("w:rPr")}]
        later[0].addprevious(flag) if later else ppr.append(flag)
    d.styles["Heading 2"].font.italic = ru
    d.styles["Heading 1"].paragraph_format.space_before = Pt(8)
    d.styles["Heading 1"].paragraph_format.space_after = Pt(4)
    d.styles["Heading 2"].paragraph_format.space_before = Pt(4)
    d.styles["Heading 2"].paragraph_format.space_after = Pt(2)
    if ru:
        d.styles["Heading 2"].paragraph_format.first_line_indent = Cm(1.25)
    foot = sec.footer.paragraphs[0]
    foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    foot._p.append(fld)

    blocks = parse(DOCS[lang])
    in_refs, front, pending = False, True, None
    for idx, (kind, p) in enumerate(blocks):
        if kind == "udk":
            para = d.add_paragraph()
            para.paragraph_format.first_line_indent = Cm(0)
            para.paragraph_format.space_after = Pt(6)
            docx_inline(para, "**" + p + "**", body)
        elif kind == "title":
            para = d.add_paragraph(style="Title")
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            para.paragraph_format.space_after = Pt(8)
            docx_inline(para, p, body + 1 if ru else 13)
            for r in para.runs:
                r.bold = True
        elif kind == "h2":
            front = False
            in_refs = p in REF_HEADINGS
            para = d.add_paragraph(p, style="Heading 1")
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER if ru else WD_ALIGN_PARAGRAPH.LEFT
        elif kind == "h3":
            d.add_paragraph(p, style="Heading 2")
        elif kind == "caption":
            pending = p
        elif kind == "table":
            if pending:
                cap = d.add_paragraph()
                cap.paragraph_format.first_line_indent = Cm(0)
                cap.paragraph_format.space_before = Pt(6)
                cap.paragraph_format.space_after = Pt(3)
                cap.paragraph_format.keep_with_next = True
                cap.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                docx_inline(cap, pending, small)
                pending = None
            n = len(p[0])
            total = 17.5 if ru else 16.6
            frac = {3: [0.50, 0.25, 0.25], 4: [0.34, 0.24, 0.14, 0.28], 5: [0.30, 0.13, 0.19, 0.17, 0.21]}[n]
            table = d.add_table(rows=len(p), cols=n)
            table.autofit = False
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            borders = OxmlElement("w:tblBorders")
            for edge in ("top", "bottom", "insideH"):
                el = OxmlElement("w:" + edge)
                for k, v in {"val": "single", "sz": "6" if edge != "insideH" else "2", "color": "000000" if edge != "insideH" else "BFBFBF"}.items():
                    el.set(qn("w:" + k), v)
                borders.append(el)
            table._tbl.tblPr.append(borders)
            for j, row in enumerate(p):
                tr = table.rows[j]._tr.get_or_add_trPr()
                tr.append(OxmlElement("w:cantSplit"))
                if j == 0:
                    tr.append(OxmlElement("w:tblHeader"))
                for k, value in enumerate(row):
                    c = table.cell(j, k)
                    c.width = Cm(total * frac[k])
                    c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                    cp = c.paragraphs[0]
                    cp.paragraph_format.first_line_indent = Cm(0)
                    cp.paragraph_format.space_before = cp.paragraph_format.space_after = Pt(1)
                    cp.paragraph_format.keep_with_next = j < len(p) - 1
                    cp.alignment = WD_ALIGN_PARAGRAPH.LEFT if k == 0 else WD_ALIGN_PARAGRAPH.CENTER
                    docx_inline(cp, value, small)
                    for r in cp.runs:
                        r.bold = j == 0
            spacer = d.add_paragraph()
            spacer.paragraph_format.space_after = Pt(0)
            spacer.paragraph_format.line_spacing = Pt(6)  # thin gap, not a full empty 14 pt line
        elif kind == "figure":
            cap, path = p
            png = (MS / path).resolve().with_suffix(".png")
            para = d.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            para.paragraph_format.first_line_indent = Cm(0)
            para.paragraph_format.keep_with_next = True
            para.add_run().add_picture(str(png), width=Cm(14))
            cp = d.add_paragraph()
            cp.paragraph_format.first_line_indent = Cm(0)
            docx_inline(cp, "Figure 1. " + cap, small)
        else:
            para = d.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            size = body
            if kind == "ref" or in_refs:
                size = 11 if ru else small
                para.paragraph_format.first_line_indent = Cm(-0.7)
                para.paragraph_format.left_indent = Cm(0.7)
                para.paragraph_format.space_after = Pt(2)
            elif front and idx <= 3:
                para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                para.paragraph_format.first_line_indent = Cm(0)
                para.paragraph_format.space_after = Pt(2 if idx == 2 else 8)
                docx_inline(para, ("**" + p + "**") if (ru and idx == 2) else p, body, italic=ru and idx == 3)
                continue
            elif front or (ru and (p.startswith("**") or (p.startswith("*") and p.endswith("*")))):
                size = small if front else 11
                para.paragraph_format.first_line_indent = Cm(0)
                para.paragraph_format.space_after = Pt(4)
            docx_inline(para, p, size)
    # Hyphenation is switched on by Word itself in export_docx_pdf_20261005.ps1;
    # a hand-written w:autoHyphenation flag made hidden Word automation hang.
    lang_el = OxmlElement("w:lang")
    lang_el.set(qn("w:val"), "ru-RU" if ru else "en-US")
    d.styles["Normal"].element.get_or_add_rPr().append(lang_el)
    d.core_properties.title = next(x for k, x in blocks if k == "title")
    d.core_properties.author = AUTHORS[lang]
    d.core_properties.language = "ru-RU" if ru else "en-US"
    target = DOCS[lang].with_suffix(".docx")
    d.save(target)
    return target


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    langs = ("ru", "en")
    if len(sys.argv) > 2:
        # Revision suffix, e.g. "r2": build only the revised Russian manuscript.
        DOCS["ru"] = MS / f"russian_resource_20261005_claude_{sys.argv[2]}.md"
        langs = ("ru",)
    for lang in langs:
        if what in ("tex", "all"):
            print(build_tex(lang))
        if what in ("docx", "all"):
            print(build_docx(lang))
