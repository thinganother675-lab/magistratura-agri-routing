"""Render the owned English Markdown draft as a standalone LaTeX source.

This does not install or invoke TeX. The Codex native compiler checks the source.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "manuscript/english_routing_20261002.md"
TARGET = ROOT / "manuscript/english_routing_20261002.tex"


def escape(text: str) -> str:
    mapping = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
               "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
               "→": r"\ensuremath{\to}", "−": "-", "–": "--", "—": "---", "×": r"\ensuremath{\times}", "’": "'", "“": "``", "”": "''"}
    return "".join(mapping.get(c, c) for c in text)


def inline(text: str) -> str:
    tokens = []
    def store(content: str) -> str:
        tokens.append(content)
        return f"REPLACETOKEN{len(tokens)-1}ENDTOKEN"
    def code(m: re.Match) -> str:
        value = m.group(1)
        if re.fullmatch("[0-9a-f]{64}", value):
            value = r"\allowbreak{}".join(value[i:i+8] for i in range(0, 64, 8))
            return store(r"{\small\texttt{" + value + "}}")
        return store(r"\texttt{" + escape(value) + "}")
    text = re.sub(r"`([^`]+)`", code, text)
    text = re.sub(r"\*\*([^*]+)\*\*", lambda m: store(r"\textbf{" + inline(m.group(1)) + "}"), text)
    text = re.sub(r"\*([^*]+)\*", lambda m: store(r"\emph{" + inline(m.group(1)) + "}"), text)
    text = re.sub(r"https?://[^\s]+", lambda m: store(r"\url{" + m.group(0) + "}"), text)
    text = escape(text)
    for index, value in enumerate(tokens): text = text.replace(f"REPLACETOKEN{index}ENDTOKEN", value)
    return text


def main() -> None:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    start = lines.index("## Abstract") + 1
    intro = next(i for i, line in enumerate(lines) if line.startswith("## 1."))
    abstract = " ".join(line for line in lines[start:intro] if line and not line.startswith("Keywords:"))
    body = []
    index = intro
    table_index = 0
    captions = ["Frozen controlled-run quality, actual cloud calls and end-to-end latency. All policies have 150 decisions.",
                "Correct decisions by category. Shared source/scenario variants are correlated observations.",
                "Reported token usage by policy and provider. Missing cloud usage is unknown, not zero.",
                "Supplementary observed DEV comparison: 36 cases per arm, not a new confirmatory test. Remote cost column gives known USD plus the number of unknown charge events; these are not an invoice."]
    while index < len(lines):
        line = lines[index]
        if line == "## References": break
        if not line.strip(): body.append(""); index += 1; continue
        if line.startswith("!["):
            # Pure standard-LaTeX diagram: native compiler supports one standalone file.
            body.extend([r"\begin{figure}[t]\centering", r"\setlength{\unitlength}{1pt}",
                         r"\begin{picture}(240,102)",
                         r"\put(30,22){\line(1,0){200}}",
                         r"\put(30,19){\line(0,1){6}}\put(80,19){\line(0,1){6}}\put(130,19){\line(0,1){6}}\put(155,19){\line(0,1){6}}\put(180,19){\line(0,1){6}}\put(230,19){\line(0,1){6}}",
                         r"\put(22,8){\small -25}\put(72,8){\small -15}\put(124,8){\small -5}\put(152,8){\small 0}\put(177,8){\small 5}\put(225,8){\small 15}",
                         r"\multiput(130,32)(0,5){11}{\line(0,1){2}}\multiput(155,32)(0,5){11}{\line(0,1){1}}",
                         r"\put(66.76,61){\line(1,0){117.41}}\put(66.76,56){\line(0,1){10}}\put(184.17,56){\line(0,1){10}}\put(135,61){\circle*{6}}",
                         r"\put(118,91){\small Estimate: -4.00 pp}\put(42,39){\small -17.65}\put(174,39){\small +5.83}",
                         r"\put(32,72){\small 95\% group-bootstrap interval}",
                         r"\end{picture}",
                         r"\caption{Hybrid minus tools plus cloud quality. The 95\% paired group-bootstrap interval crosses the frozen -5 pp margin (dashed line); non-inferiority is not demonstrated. Zero is dotted. 150 pairs, 25 groups, 5,000 resamples.}", r"\end{figure}"])
            index += 1; continue
        if line.startswith("Figure 1."):
            index += 1; continue
        if line.startswith("## "):
            title = re.sub(r"^\d+\.\s*", "", line[3:])
            body.append(r"\section{" + inline(title) + "}"); index += 1; continue
        if line.startswith("### "):
            title = re.sub(r"^\d+\.\d+\s*", "", line[4:])
            body.append(r"\subsection{" + inline(title) + "}"); index += 1; continue
        if line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].startswith("|"):
                row = [v.strip() for v in lines[index].strip("|").split("|")]
                if not all(re.fullmatch(r"[:\-]+", cell) for cell in row): rows.append(row)
                index += 1
            columns = len(rows[0]); align = "l" + "r"*(columns-1)
            body.extend([r"\begin{table*}[t]", r"\centering\small", r"\caption{"+inline(captions[table_index])+"}",
                         r"\resizebox{\textwidth}{!}{%", r"\begin{tabular}{"+align+"}", r"\toprule"])
            for count, row in enumerate(rows):
                body.append(" & ".join(inline(v) for v in row)+r" \\")
                if count == 0: body.append(r"\midrule")
            body.extend([r"\bottomrule", r"\end{tabular}}", r"\end{table*}", ""]); table_index += 1; continue
        body.append(inline(line)); index += 1
    refs = []
    for line in lines[index+1:]:
        match = re.match(r"(\d+)\. (.+)", line)
        if match: refs.append(r"\bibitem{ref"+match.group(1)+"}"+inline(match.group(2)))
    title = lines[0].removeprefix("# ")
    document = r"""\documentclass[10pt,a4paper,twocolumn]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[margin=18mm,columnsep=6mm]{geometry}
\usepackage{lmodern}
\usepackage{amsmath,booktabs,array,graphicx}
\usepackage[hyphens]{url}
\usepackage[hidelinks]{hyperref}
\setlength{\emergencystretch}{1em}
\setlength{\parskip}{2pt}
\title{"""+inline(title)+r"""}
\author{Antonii Sarychev \and Denis Shesternin}
\date{2 October 2026}
\begin{document}
\maketitle
\begin{center}\small
Russian State Agrarian University--Moscow Timiryazev Agricultural Academy, Moscow, Russia.\\
Working draft; author approval and human validation pending; not submitted.
\end{center}
\begin{abstract}
"""+inline(abstract)+r"""
\end{abstract}
\noindent\textbf{Keywords:} language model routing; deterministic tools; agricultural QA; model cascades; selective prediction; edge inference.

"""+"\n".join(body)+r"""

\begin{thebibliography}{99}
\small
"""+"\n\n".join(refs)+r"""
\end{thebibliography}
\noindent\footnotesize References 1--17: primary metadata and relevant PDF sections checked; no claim of fully reading every PDF. Reference 18: bibliographic metadata and dataset card checked, complete publisher article not read here. Provider prices and software/policy documentation are separate reproducibility sources.
\end{document}
"""
    TARGET.write_text(document, encoding="utf-8")
    print(f"Created {TARGET}; {len(refs)} inline scientific references; {table_index} standalone tables.")


if __name__ == "__main__":
    main()
