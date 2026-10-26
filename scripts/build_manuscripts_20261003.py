# SPDX-License-Identifier: Apache-2.0
"""Prepare new manuscript sources; never overwrite the historical 20261002 draft."""
from pathlib import Path
import importlib.util
import json
import re

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("historical_renderer", ROOT / "scripts/render_manuscript_20261002.py")
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)

def english():
    old = (ROOT / "manuscript/english_routing_20261002.md").read_text(encoding="utf-8")
    text = old.replace("Antonii Sarychev", "Antoniy Sarychev").replace("Working draft, 2 October 2026.", "WORKING DRAFT — NOT READY FOR SUBMISSION, 3 October 2026.")
    text = text.replace("a measured cost–quality tradeoff", "an observed cloud-use and latency–quality tradeoff")
    text = text.replace("1% relative or 0.02 absolute numerical tolerance", "math.isclose numerical tolerance (absolute difference at most max(0.02, 0.01 times the larger absolute prediction/reference))")
    text = re.sub(r"`results/[^`]+`", "the archived supplementary analysis", text)
    audit = """### 5.1 Versioned diagnostic audit and supplementary free-model screen

An independent Decimal recheck on 3 October agrees with the 30 numerical gold values. All 30 LOCAL numerical responses contain valid structured ANSWER outputs and the required units, but their values are outside the frozen tolerance. No unit, action/schema, formatting, parsing, incomplete-response or evaluator artifact explains this category's zero score. No intermediate derivation was recorded, so wrong arithmetic operations and wrong formula selection cannot be separated per response. This is a versioned diagnostic, not a rescore of HOME150.

The independent compound check agrees with gold on all 100 case-policy decisions. The historical verifier actually accepted 12 incorrect hybrid answers and 12 incorrect offline answers. Fixed LOCAL has another 12 incorrect labels that would pass literal grounding; that arm did not invoke the verifier, so these are not additional observed verifier acceptances. A separate DEV-only v2 candidate implements typed conjunction, negation, entity, branch, component and unit checks. It is not connected to historical or production policies. It returns UNKNOWN on untyped natural-language QA; it does not claim general agronomic entailment. Its public fact inventory and rule must come from task evidence independently of hidden gold. ASK/ABSTAIN explanations still require approved reference answers or human semantic review. Historical policy/scorer bytes remain unchanged. Actual human adjudication is still absent.

A new supplementary OpenRouter screen used the same nine observed DEV inputs across three explicit free models, with single-provider pins, no retries, all-zero price checks before every request and an existing zero-paid-limit inference key. Qwen3.8 27B scores 5/9, Ling 3.0 Flash Sante 4/9 and Dots3-Note Preview 4/9 under the historical strict scorer. Median end-to-end latencies are 0.673, 1.163 and 1.763 seconds; input/output tokens are 4,205/272, 4,343/358 and 4,077/309. All 27 responses are HTTP200, valid exact JSON schema and API-reported cost zero; key usage remains zero. These are paired development observations, not a new independent holdout or a robust model ranking. Dots is a preview alias. Mercury remains the historical cloud comparator.

The requested 21-name catalogue was resolved, but only seven distinct models received attempts across three separate new runs: four returned generations, three had distinct HTTP failures. Nine text candidates were absent from the account-filtered catalogue, two eligible candidates were not run under the bounded plan, and two paid music models plus one safety classifier were skipped. The management key explains the old 401; a new Ling3.1 response identifies the zero-total-limit 403, Apodex rejects json_schema despite advertised metadata, and Gemma26 reports an upstream shared-pool 429. The previous LFM privacy/ZDR incompatibility remains a blocker; exact account toggles are not API-observable here. Failed-attempt usage is unknown individually. Shared DEV costs are confirmed zero; no invoice or total-cost saving is inferred.

Two blank blinded reviewer forms were prepared for Antoniy and Denis. The current review40 contains no generated model answers, so this phase independently checks questions/references and authors gold; it cannot measure model-answer accuracy. Expert-needed or disputed cases remain unresolved until real adjudication. The next source-disjoint study is DATA_BLOCKED, with no new protocol freeze or confirmatory inference. New external-source candidates have separate source-group and rights audits; row count and translations do not establish independence.

"""
    text = text.replace("## 6. Limitations and reproducibility", audit + "## 6. Limitations and reproducibility")
    source = ROOT / "manuscript/english_routing_20261003.md"
    source.write_text(text, encoding="utf-8")
    renderer.SOURCE = source
    renderer.TARGET = ROOT / "manuscript/english_routing_20261003.tex"
    renderer.main()
    tex = renderer.TARGET.read_text(encoding="utf-8").replace("Antonii Sarychev", "Antoniy Sarychev").replace("2 October 2026", "3 October 2026")
    tex = tex.replace("Working draft; author approval and human validation pending; not submitted.", "WORKING DRAFT -- NOT READY FOR SUBMISSION; author approval and human validation pending.")
    tex = tex.replace(r"\usepackage[hidelinks]{hyperref}", r"\usepackage[hidelinks]{hyperref}" + "\n" + r"\hypersetup{pdftitle={What Does Local Inference Add After Deterministic Tools?},pdfauthor={Antoniy Sarychev; Denis Shesternin},pdfsubject={Working empirical draft, human validation pending}}")
    tex = tex.replace(r"\begin{document}", r"\setlength{\emergencystretch}{2em}" + "\n" + r"\begin{document}")
    tex = tex.replace("A preceding failed-start directory contains no policy decisions;", "A preceding failed-start directory contains no policy decisions;")
    renderer.TARGET.write_text(tex, encoding="utf-8")

def russian():
    source = ROOT / "manuscript/russian_routing_20261003.md"
    lines = source.read_text(encoding="utf-8").splitlines()
    title = lines[0][2:]
    body = []
    index = 1
    while index < len(lines):
        line = lines[index]
        if line == "## Литература":
            body.append(r"\section*{Литература}\begingroup\fontsize{12}{14}\selectfont\begin{enumerate}")
            for ref in lines[index + 1:]:
                match = re.match(r"\d+\. (.+)", ref)
                if match:
                    body.append(r"\item " + renderer.inline(match[1]))
            body.append(r"\end{enumerate}\endgroup")
            break
        if line.startswith("## "):
            body.append(r"\section*{" + renderer.inline(line[3:]) + "}")
        elif line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].startswith("|"):
                cells = [c.strip() for c in lines[index].strip("|").split("|")]
                if not all(re.fullmatch(r"[:\-]+", c) for c in cells):
                    rows.append(cells)
                index += 1
            body.extend([r"\begin{center}\fontsize{12}{14}\selectfont", r"\begin{tabular}{lrrrr}\toprule"])
            for n, row in enumerate(rows):
                body.append(" & ".join(renderer.inline(c) for c in row) + r" \\")
                if n == 0:
                    body.append(r"\midrule")
            body.extend([r"\bottomrule\end{tabular}", r"\end{center}"])
            continue
        elif line:
            body.append(renderer.inline(line) + "\n")
        else:
            body.append("")
        index += 1
    tex = r"""\documentclass[14pt,a4paper]{extarticle}
\usepackage[margin=20mm]{geometry}
\usepackage{fontspec}
\setmainfont{Times New Roman}
\setsansfont{Arial}
\setmonofont{Consolas}[Scale=MatchLowercase]
\usepackage{polyglossia}
\setdefaultlanguage{russian}
\setotherlanguage{english}
\usepackage{amsmath,booktabs,array}
\usepackage[hyphens]{url}
\usepackage[hidelinks]{hyperref}
\hypersetup{pdftitle={Инструментальная маршрутизация языковых моделей в аграрных задачах},pdfauthor={Антоний Сарычев; Денис Шестернин},pdfsubject={Рабочий исследовательский черновик; человеческая проверка не завершена}}
\setlength{\parindent}{1.25cm}
\setlength{\parskip}{0pt}
\setlength{\emergencystretch}{2em}
\sloppy
\begin{document}
\begin{center}\bfseries
""" + renderer.inline(title) + r"""
\end{center}
""" + "\n".join(body) + "\n" + r"\end{document}" + "\n"
    (ROOT / "manuscript/russian_routing_20261003.tex").write_text(tex, encoding="utf-8")
    abstract = source.read_text(encoding="utf-8").split("## Аннотация\n", 1)[1].split("Ключевые слова:", 1)[0].strip()
    assert 200 <= len(abstract) <= 300
    print(json.dumps({"russian_abstract_characters": len(abstract), "scientific_references": 18, "article_license": "NOT_SELECTED", "human_review": False}))

if __name__ == "__main__":
    english()
    russian()
