"""Assemble dated article drafts and review artifacts without changing old runs.

Run with the bundled artifact Python. Compilation and GPU inference are separate
operations; --prepare performs text-only preparation while inference is active.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/20261004_article_build"
MAN = ROOT / "manuscript"
EVIDENCE = ROOT / "results/20261004_evidence_audit/analysis.json"
BIB = ROOT / "results/20261004_publication_sources/compact_bibliography_19.json"
ENGINE = ROOT / ".runtime/tex20261003/tectonic-msvc.exe"
RENDER = ROOT / ".cache/article_qa_20261004"
STEMS = {"ru": "russian_resource_20261004", "en": "english_resource_20261004"}


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare():
    refs = json.loads(BIB.read_text(encoding="utf-8"))["entries"]
    numbered = []
    for i, entry in enumerate(refs, 1):
        assert entry["manuscript_number"] == i
        authors = entry["authors"]
        # All four FAO authors are kept. Long team author lists are abbreviated.
        def abbreviated(name):
            if ", " not in name:
                return name
            family, given = name.split(", ", 1)
            return family + ", " + " ".join(part[0] + "." for part in given.split())
        names = "; ".join(abbreviated(name) for name in authors[:3]) + ("; et al." if len(authors) > 3 else "")
        if i == 17:
            names = "Gemma Team; et al."
        if i == 18:
            names = "Kpodo, J.; Kordjamshidi, P.; Nejadhashemi, A. P."
        if i == 19:
            names = "Allen, R. G.; Pereira, L. S.; Raes, D.; Smith, M."
        title = entry.get("published_title") or entry["title"]
        title = title.replace("$\\tau$", "tau")
        url = entry.get("published_primary_url") or entry["primary_url"]
        year = entry.get("published_year") or entry.get("initial_year", 1998)
        if i in (4, 5, 15):
            year = 2025
        venue = entry.get("venue") or ("FAO Irrigation and Drainage Paper 56" if i == 19 else "arXiv preprint")
        if i == 18:
            venue = "Computers and Electronics in Agriculture 225:109349"
        numbered.append(f"{i}. {names.rstrip('.')}. *{title}*. {venue}, {year}. [Primary source]({url}).")
    bibliography = "\n\n".join(numbered)
    corrections = {
        "en": [
            ("TELEMETRY40 selects four reference-free positions per discipline from the same DEV and is not independent validation.", "TELEMETRY40 selects four positions per discipline without inspecting reference answers from the same DEV and is not independent validation. Twenty of its IDs also occur in the initial DEV60."),
            ("Sampled whole-GPU peak, MiB", "Whole-GPU sampled request peak, MiB"),
            ("Sampled whole-system RAM peak, GiB", "Whole-system RAM sampled request peak, GiB"),
            ("LM Studio process-group RSS peak, MiB", "Process-group RSS sampled request peak, MiB"),
            ("Strict numerical results retain the original absolute tolerance of 1e-8. A separate 1e-4 rounding diagnostic is reported without replacing the historical scores.", "Strict results retain the original per-case tolerances: 1e-8 for twelve high-precision constructed numerical cases, and 0.001, 0.005 or 0.01 for four published rounded controls. The separate rounding diagnostic uses max(original case tolerance, 1e-4), without replacing historical scores."),
            ("The last is an arithmetic scenario, not an established field irrigation recommendation.", "GDD sums max(0, (Tmin + Tmax)/2 − base) over the supplied days. Single-observation VPD uses saturation pressure times (1 − RH/100); the separate daily form uses temperature and humidity extrema. The rain gap is an arithmetic scenario, not an established field irrigation recommendation."),
        ],
        "ru": [
            ("Независимый скрытый TEST в этой сессии не запускался.", "Независимый скрытый TEST в этой сессии не запускался. 9B — фокусная практическая конфигурация, 27B — reference с более высоким наблюдаемым качеством."),
            ("независимой проверкой он не является.", "независимой проверкой он не является. С первоначальным DEV60 пересекаются 20 его заданий."),
            ("Whole-GPU peak, MiB", "GPU request peak, MiB"),
            ("Whole-system RAM peak, GiB", "RAM request peak, GiB"),
            ("Process-group RSS peak, MiB", "RSS request peak, MiB"),
            ("Последняя не является готовой нормой полива.", "GDD суммирует max(0, (Tmin + Tmax)/2 − base) по заданным дням. VPD по одному наблюдению равен давлению насыщения, умноженному на (1 − RH/100); суточная версия использует экстремумы температуры и влажности. Разность осадков не является готовой нормой полива."),
            ("Исходный численный допуск 1e-8 сохраняется. Диагностика округления при 1e-4 выделяется отдельно и не заменяет строгие баллы;", "Сохранены исходные допуски каждого случая: 1e-8 у двенадцати высокоточных численных эталонов, 0,001/0,005/0,01 у четырёх опубликованных округлённых примеров. Отдельная диагностика использует max(исходный допуск, 1e-4) и не заменяет строгие баллы;"),
        ],
    }
    for language, stem in STEMS.items():
        path = MAN / (stem + ".md")
        text = path.read_text(encoding="utf-8")
        for before, after in corrections[language]:
            if after.startswith(before):
                suffix = after[len(before):]
                while suffix + suffix in text:
                    text = text.replace(suffix + suffix, suffix)
            if before in text and after not in text:
                text = text.replace(before, after)
        text = text.replace("<!-- VERIFIED_REFERENCES -->", bibliography)
        heading = "## References" if language == "en" else "## Литература"
        if heading + "\n" in text:
            text = text.split(heading + "\n", 1)[0] + heading + "\n\n" + bibliography + "\n"
        path.write_text(text, encoding="utf-8")
    print("Prepared aligned dated drafts with 19 verified scientific references.")


def finish_live_section():
    summary = json.loads((ROOT / "results/20261004_study_c_live/summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "COMPLETE" and summary["new_model_calls"] == 142
    q9 = summary["models"]["qwen3.5-9b"]
    q27 = summary["models"]["qwen3.8-27b"]
    for model in (q9, q27):
        assert all(v["n_attempted"] == 27 and v["errors"] == 0 for v in model.values())
        assert model["live_application_tools"]["strict_numeric_correct"] == 16
    def rows(language):
        output = []
        for name, model in (("Qwen9", q9), ("Qwen27", q27)):
            for arm, label in (("model_only", "model only" if language == "en" else "без tools"), ("live_application_tools", "live tools")):
                s = model[arm]
                latency = f"{s['latency_median_s']:.3f}"
                if language == "ru":
                    latency = latency.replace(".", ",")
                output.append(f"| {name} {label} | {s['strict_correct']}/27 | {s['strict_numeric_correct']}/16 | {s['numeric_executions']} | {latency} |")
        return "\n".join(output)
    english = """The new predeclared live comparison completes all 108 model–arm decisions, with 140 measured model calls and two separate synthetic warmups. Both models use the checkpoint-zero native load/decoding profile. The model-only arm makes one call; the tool arm chooses an allowlisted tool and supplies its full argument objects, which are checked against the public request before execution. The application never completes arguments from gold, a hidden category or expected tool. A successful numeric execution is followed by a model finalization call. This is application-level JSON dispatch, with explicit typed task and contracts supplied; native provider function calling and unrestricted intent discovery were not evaluated.

Table 3. Matched development Study C, 27 cases per arm. Full correctness uses the preserved per-case value/action/tool scorer; final-schema compliance is audited separately. Latency is the median sum of model HTTP wall spans, excluding application dispatch and logging.

| Configuration and arm | Full correct | Number + unit | Numeric executions | Summed latency, s |
|---|---:|---:|---:|---:|
""" + rows("en") + """

All 32 submitted numeric calls passed argument validation, executed the declared formula, and yielded correct final numeric values and units. Full nonnumeric correctness is 6/11 versus 2/11 for Qwen9 and 9/11 versus 9/11 for Qwen27, model-only versus tools. Thus the numeric improvement does not establish reliable clarification or unsupported-task handling; the smaller model loses correctness on four of those cases. No transport errors or output-budget truncations were observed. Offline final-contract checks find Qwen9 valid in 24/27 model-only and 26/27 tool outputs, and Qwen27 valid in 27/27 for both. All four malformed field-type cases already fail the preserved full-answer scorer, so this separate contract check changes none of the table's correctness counts.

Each call allows at most 512 output tokens; a successful numeric tool interaction permits two calls and up to twice the aggregate generation budget. Tool feedback and the number of calls therefore change together. Reported latency sums the measured model requests, rather than the entire application's end-to-end time. The run is one matched development comparison on reused constructed material, not independent agronomic validation. Its weight sizes/paths match retained identity receipts; full weight SHA verification belongs to the earlier provenance receipt and was not repeated during timed inference.
"""
    russian = """Новый заранее объявленный опыт завершил все 108 решений: 140 измеряемых модельных вызовов и два отдельных синтетических прогрева. Обе модели используют native-профиль checkpoints 0. Ветка без tools делает один вызов; инструментальная ветка выбирает разрешённую функцию и передаёт полные аргументы. Программа проверяет их равенство публичным входам и единицам, затем исполняет формулу и передаёт результат модели для итогового ответа. Из gold, скрытой категории или ожидаемого tool аргументы не дополняются. Это живое JSON-исполнение на уровне приложения с явно заданными типом и контрактами; native function-calling и обнаружение намерения из свободной речи не проверялись.

Таблица 3. Study C, 27 случаев в каждой ветви. Полная правильность сохраняет scorer значений/action/tool; контракт итогового JSON проверен отдельно. Задержка — сумма модельных HTTP-интервалов, без dispatch и журналирования.

| Конфигурация | Верно | Число + единица | Исполнений | p50 суммы, с |
|---|---:|---:|---:|---:|
""" + rows("ru") + """

Все 32 численных вызова прошли проверку аргументов и дали правильные итоговые значения с единицами. Среди 11 нечисленных случаев Qwen9 получил 6/11 без tools и 2/11 с tools; Qwen27 — 9/11 в обеих ветвях. Следовательно, улучшение арифметики не устанавливает надёжность уточнения данных и отказа: у Qwen9 четыре таких случая ухудшились. Ошибок транспорта и усечения по output budget не наблюдалось. Контракт итогового JSON валиден у Qwen9 в 24/27 и 26/27, у Qwen27 — 27/27 и 27/27; четыре нарушения типов уже неверны по исходному scorer, поэтому отдельная проверка баллы не меняет.

Максимум 512 токенов задан для одного вызова; успешная численная tool-ветвь обычно делает два и получает вдвое больший суммарный бюджет. Обратная связь инструмента меняется вместе с числом вызовов. Указана сумма задержек запросов, а не полная задержка приложения. Это один matched development-опыт на прежнем материале. Пути/размеры весов сверены; полный SHA относится к прежней квитанции и во время inference повторно не рассчитывался.
"""
    for language, section in (("en", english), ("ru", russian)):
        path = MAN / (STEMS[language] + ".md")
        text = path.read_text(encoding="utf-8")
        if "<!-- LIVE_STUDY_C_SECTION -->" in text:
            text = text.replace("<!-- LIVE_STUDY_C_SECTION -->", section.strip())
            if language == "en":
                text = text.replace("A constructed calculation study covers specified formulas, units and missing inputs; its historical tool-name replay is distinguished from the new live execution comparison.", "The live constructed calculation study obtains full correctness of 7/27 versus 18/27 for Qwen9 without/with tools and 15/27 versus 25/27 for Qwen27; each tool arm achieves 16/16 numeric answers, while clarification errors remain.")
                text = text.replace("Preparation of an English preprint", "Live deterministic execution improves specified numeric outcomes for both models, but Qwen9 retains tool-selection/clarification failures and successful interactions require an additional model call. Preparation of an English preprint")
                text = text.replace("The initial native profile with 32 checkpoints", "![Native quality-resource description](../results/20261004_article_build/native40_tradeoff.png)\n\nThe initial native profile with 32 checkpoints")
            else:
                text = text.replace("Подготовка RU/EN может продолжаться", "Живое исполнение улучшило численные ответы обеих моделей, сохранив ошибки выбора/уточнения у Qwen9 и дополнительный вызов для финализации. Подготовка RU/EN может продолжаться")
            path.write_text(text, encoding="utf-8")
    print("Inserted verified complete live results and precise methodological limits.")


def escape(value):
    mapping = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}", "→": r"\ensuremath{\to}", "−": "-", "–": "--", "—": "---", "×": r"\ensuremath{\times}", "’": "'", "“": "``", "”": "''", "Σ": r"\ensuremath{\Sigma}", "°": r"\ensuremath{^\circ}", "∩": r"\ensuremath{\cap}"}
    return "".join(mapping.get(c, c) for c in value)


def inline(value):
    tokens = []
    def keep(text):
        tokens.append(text)
        return f"KEEPTOKEN{len(tokens)-1}END"
    value = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", lambda m: keep(r"\href{" + m[2] + "}{" + escape(m[1]) + "}"), value)
    value = re.sub(r"\[(\d+(?:[–,-]\d+)*)\]", lambda m: keep(r"\cite{" + ",".join("ref" + str(x) for part in m[1].split(",") for x in (range(int(part.split("–")[0]), int(part.split("–")[1])+1) if "–" in part else [int(part)])) + "}"), value)
    value = re.sub(r"\*\*([^*]+)\*\*", lambda m: keep(r"\textbf{" + escape(m[1]) + "}"), value)
    value = re.sub(r"\*([^*]+)\*", lambda m: keep(r"\emph{" + escape(m[1]) + "}"), value)
    value = re.sub(r"`([^`]+)`", lambda m: keep(r"\texttt{" + escape(m[1]) + "}"), value)
    value = escape(value)
    for i, token in enumerate(tokens):
        value = value.replace(f"KEEPTOKEN{i}END", token)
    return value


def tex_sources():
    for language, stem in STEMS.items():
        lines = (MAN / (stem + ".md")).read_text(encoding="utf-8").splitlines()
        assert not any("<!--" in line for line in lines), "Finish live results before rendering."
        title = lines[0][2:]
        body = []
        i = 1
        while i < len(lines):
            line = lines[i]
            if line in ("## References", "## Литература"):
                body.append(r"\begin{thebibliography}{99}\fontsize{12}{14}\selectfont" if language == "ru" else r"\begin{thebibliography}{99}\small")
                for reference in lines[i+1:]:
                    match = re.match(r"(\d+)\. (.+)", reference)
                    if match:
                        body.append(r"\bibitem{ref" + match[1] + "}" + inline(match[2]))
                body.append(r"\end{thebibliography}")
                break
            if line.startswith("## "):
                title_part = re.sub(r"^\d+\.\s*", "", line[3:])
                body.append(r"\section*{" + inline(line[3:]) + "}" if language == "ru" or title_part == "Abstract" else r"\section{" + inline(title_part) + "}")
            elif line.startswith("### "):
                body.append(r"\subsection*{" + inline(re.sub(r"^\d+\.\d+\s*", "", line[4:])) + "}")
            elif line.startswith("|"):
                rows = []
                while i < len(lines) and lines[i].startswith("|"):
                    row = [x.strip() for x in lines[i].strip("|").split("|")]
                    if not all(re.fullmatch(r"[:\-]+", x) for x in row):
                        rows.append(row)
                    i += 1
                n = len(rows[0])
                widths = {3: [.44, .23, .23], 4: [.31, .24, .12, .23], 5: [.28, .16, .16, .16, .14]}.get(n)
                assert widths and all(len(row) == n for row in rows)
                cols = "@{}" + "".join(r">{\raggedright\arraybackslash}p{" + str(w) + r"\linewidth}" for w in widths) + "@{}"
                body.extend([r"\begin{center}\begingroup\fontsize{12}{14}\selectfont\setlength{\tabcolsep}{4pt}" if language == "ru" else r"\begin{center}\begingroup\small\setlength{\tabcolsep}{4pt}", r"\begin{tabular}{" + cols + "}", r"\toprule"])
                for j, row in enumerate(rows):
                    body.append(" & ".join(inline(cell) for cell in row) + r" \\")
                    if j == 0:
                        body.append(r"\midrule")
                body.extend([r"\bottomrule\end{tabular}\endgroup\end{center}\end{minipage}"])
                continue
            elif line.startswith("!["):
                body.extend([r"\begin{figure}[ht]\centering", r"\includegraphics[width=\linewidth]{../results/20261004_article_build/native40_tradeoff.pdf}", r"\caption{Native TELEMETRY40: retrospective strict EM on 39 references versus measured request latency on 40 calls. These two practical configurations both reuse DEV; point values do not establish equivalence or a causal size effect.}\end{figure}"])
            elif line:
                if line.startswith(("Table ", "Таблица ")):
                    body.append(r"\noindent\begin{minipage}{\linewidth}" + (r"\fontsize{12}{14}\selectfont" if language == "ru" else ""))
                body.append(inline(line) + "\n")
            else:
                body.append("")
            i += 1
        if language == "ru":
            preamble = r"""\documentclass[14pt,a4paper]{extarticle}
\usepackage[margin=20mm]{geometry}
\usepackage{fontspec}
\setmainfont{Times New Roman}
\setsansfont{Arial}
\setmonofont{Consolas}[Scale=MatchLowercase]
\usepackage{polyglossia}
\setdefaultlanguage{russian}
\setotherlanguage{english}
\usepackage{amsmath,booktabs,array,graphicx,needspace}
\usepackage[hyphens]{url}
\usepackage[hidelinks]{hyperref}
\setlength{\parindent}{1.25cm}
\setlength{\parskip}{0pt}
\setlength{\emergencystretch}{2em}
\clubpenalty=10000
\widowpenalty=10000
\sloppy
"""
        else:
            preamble = r"""\documentclass[10pt,a4paper]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[margin=22mm]{geometry}
\usepackage{lmodern}
\usepackage{amsmath,booktabs,array,graphicx,needspace}
\usepackage[hyphens]{url}
\usepackage[hidelinks]{hyperref}
\setlength{\parskip}{3pt}
\setlength{\emergencystretch}{2em}
\clubpenalty=10000
\widowpenalty=10000
"""
        meta = r"\hypersetup{pdftitle={" + inline(title) + "},pdfauthor={" + ("Антоний Сарычев; Денис Шестернин" if language == "ru" else "Antoniy Sarychev; Denis Shesternin") + "},pdfsubject={Working empirical draft; final author consent and license pending}}\n"
        document = preamble + meta + r"\begin{document}" + "\n" + r"\begin{center}\bfseries " + inline(title) + r"\end{center}" + "\n" + "\n".join(body) + "\n" + r"\end{document}" + "\n"
        (MAN / (stem + ".tex")).write_text(document, encoding="utf-8")


def figure():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    a = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    fig, ax = plt.subplots(figsize=(6.8, 3.4), constrained_layout=True)
    for model, label, color in [("qwen3.5-9b", "Qwen3.5-9B Q8_0", "#1c6596"), ("qwen3.8-27b", "Qwen3.8-27B UD-Q4_K_M", "#aa562c")]:
        x = a["telemetry_measurements"][model]["latency_s"]["p50"]
        y = a["retrospective_telemetry_compatibility"][model]["retrospective_native40"]["em"] * 100
        ax.scatter(x, y, s=65, color=color, zorder=3)
        ax.annotate(label, (x, y), xytext=(8, -20), textcoords="offset points", fontsize=9)
    ax.set(xlim=(0, 1.95), ylim=(50, 67), xlabel="Median request latency (seconds), n = 40", ylabel="Retrospective strict set EM (%), n = 39")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(alpha=.2)
    fig.savefig(OUT / "native40_tradeoff.pdf")
    fig.savefig(OUT / "native40_tradeoff.png", dpi=220)
    plt.close(fig)


def compile_and_verify():
    import os
    from PIL import Image, ImageDraw
    from pypdf import PdfReader
    import pypdfium2 as pdfium
    OUT.mkdir(parents=True, exist_ok=True)
    RENDER.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["TECTONIC_CACHE_DIR"] = str(ROOT / ".runtime/tex20261003/cache")
    report = {"created_utc": now(), "status": "COMPILED_VISUAL_REVIEW_PENDING", "engine": "Tectonic portable 0.17.0 MSVC", "engine_sha256": sha(ENGINE), "documents": {}, "external_submission": "NOT_RUN", "license": "NOT_SELECTED"}
    for language, stem in STEMS.items():
        source = MAN / (stem + ".tex")
        p = subprocess.run([str(ENGINE), "--keep-logs", "--outdir", str(MAN), str(source)], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
        transcript = p.stdout + p.stderr
        (OUT / (stem + "_compile.txt")).write_text(transcript, encoding="utf-8")
        assert p.returncode == 0, transcript[-3000:]
        assert not any(x in transcript for x in ("Missing character:", "Undefined control sequence", "LaTeX Error:", "undefined references")), transcript[-3000:]
        pdf = source.with_suffix(".pdf")
        reader = PdfReader(pdf)
        text = "\n".join(page.extract_text() for page in reader.pages)
        assert len(text) > 5000 and "\ufffd" not in text
        compact_text = re.sub(r"\s+", "", text)
        assert all(x in compact_text for x in ("141/289", "150/289", "22/39", "24/39", "FAO", "RouteLLM"))
        assert ("АнтонийСарычев" if language == "ru" else "AntoniySarychev") in compact_text
        assert ("ДенисШестернин" if language == "ru" else "DenisShesternin") in compact_text
        fonts = {}
        for page in reader.pages:
            for _, reference in page["/Resources"].get("/Font", {}).items():
                font = reference.get_object()
                descendants = font.get("/DescendantFonts", [reference])
                embedded = []
                for child in descendants:
                    descriptor = child.get_object().get("/FontDescriptor")
                    embedded.append(bool(descriptor and any(k in descriptor.get_object() for k in ("/FontFile", "/FontFile2", "/FontFile3"))))
                fonts[str(reference.idnum)] = {"name": str(font.get("/BaseFont")), "embedded": all(embedded)}
        assert fonts and all(f["embedded"] for f in fonts.values())
        renders = []
        doc = pdfium.PdfDocument(pdf)
        for n in range(len(doc)):
            image = doc[n].render(scale=1.7).to_pil()
            path = RENDER / (stem + f"_page_{n+1:02d}.png")
            image.save(path)
            thumb = image.copy()
            thumb.thumbnail((420, 600))
            tile = Image.new("RGB", (440, 635), "#dedede")
            tile.paste(thumb, ((440-thumb.width)//2, 10))
            ImageDraw.Draw(tile).text((10, 615), f"{language} page {n+1}", fill="black")
            renders.append(tile)
        doc.close()
        sheet = Image.new("RGB", (4*440, ((len(renders)+3)//4)*635), "white")
        for n, tile in enumerate(renders):
            sheet.paste(tile, ((n%4)*440, (n//4)*635))
        sheet.save(RENDER / (stem + "_contact.png"))
        (RENDER / (stem + "_text.txt")).write_text(text, encoding="utf-8")
        report["documents"][language] = {"source": source.relative_to(ROOT).as_posix(), "source_sha256": sha(source), "pdf": pdf.relative_to(ROOT).as_posix(), "pdf_sha256": sha(pdf), "pages": len(reader.pages), "text_characters": len(text), "selectable_text": True, "all_fonts_embedded": True, "fonts": fonts, "metadata": {str(k): str(v) for k,v in reader.metadata.items()}, "scientific_references": 19}
    save(OUT / "compilation_qa.json", report)
    print(json.dumps({k: {"pages": v["pages"], "fonts_embedded": v["all_fonts_embedded"]} for k,v in report["documents"].items()}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--finish-live", action="store_true")
    parser.add_argument("--figure", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.prepare:
        prepare()
    if args.finish_live:
        finish_live_section()
    if args.figure:
        figure()
    if args.build:
        if not (OUT / "native40_tradeoff.pdf").exists():
            subprocess.run([str(ROOT / ".venv/Scripts/python.exe"), str(Path(__file__).resolve()), "--figure"], check=True, cwd=ROOT)
        tex_sources()
        compile_and_verify()


if __name__ == "__main__":
    main()
