"""Create an isolated, rights-filtered editorial copy and portable TeX archive.

Run with the bundled artifact Python, after the final drafts are visually checked.
This command never launches an editor, sends a message, or submits a manuscript.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
from zipfile import ZipFile, ZIP_DEFLATED
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/20261004_article_build"
EDITOR = ROOT / "outputs/claude_article_editor_20261004"
STEMS = ("russian_resource_20261004", "english_resource_20261004")


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pointer(obj, field):
    for part in field.lstrip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        obj = obj[int(part)] if isinstance(obj, list) else obj[part]
    return obj


def copy_file(rel):
    source = ROOT / rel
    target = EDITOR / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def docx_qa():
    from docx import Document
    from zipfile import ZipFile
    import xml.etree.ElementTree as ET
    path = ROOT / "manuscript/russian_resource_20261004.docx"
    exported = ROOT / ".cache/article_qa_20261004/russian_resource_20261004_word.pdf"
    d = Document(path)
    assert len(d.tables) == 3
    assert d.styles["Normal"].font.name == "Times New Roman"
    assert d.styles["Normal"].font.size.pt == 14
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        styles = ET.fromstring(z.read("word/styles.xml"))
        assert not styles.findall(".//w:pBdr", ns)
        text = "".join(x.text or "" for x in root.findall(".//w:t", ns))
    assert all(x in text for x in ("141/289", "150/289", "22/39", "24/39", "16/16", "RouteLLM", "FAO"))
    r = PdfReader(exported)
    assert 6 <= len(r.pages) <= 8
    extracted = "\n".join(p.extract_text() for p in r.pages)
    compact = re.sub(r"\s+", "", extracted)
    assert all(x in compact for x in ("141/289", "150/289", "22/39", "24/39", "АнтонийСарычев", "ДенисШестернин"))
    embedded = []
    for page in r.pages:
        for ref in page["/Resources"].get("/Font", {}).values():
            f = ref.get_object()
            for desc in f.get("/DescendantFonts", [ref]):
                descriptor = desc.get_object().get("/FontDescriptor")
                embedded.append(bool(descriptor and any(k in descriptor.get_object() for k in ("/FontFile", "/FontFile2", "/FontFile3"))))
    assert embedded and all(embedded)
    save(OUT / "docx_qa.json", {"checked_utc": now(), "status": "PASS_STRUCTURAL_AND_ALL_8_PAGES_VISUAL", "source": path.relative_to(ROOT).as_posix(), "source_sha256": sha(path), "renderer": "Installed Microsoft Word hidden COM read-only export; PDFium PNG rendering", "packaged_renderer": "render_docx.py attempted: LibreOffice soffice.exe absent; sandbox tempfile ACL and Word activation failures; authorized host Word export succeeded", "qa_pdf": exported.relative_to(ROOT).as_posix(), "qa_pdf_sha256": sha(exported), "pages": len(r.pages), "text_selectable": True, "all_exported_fonts_embedded": True, "normal_font": "Times New Roman 14pt", "tables": 3, "visual_review": "All eight pages individually inspected by GPT-6.1 Sol, plus root contact-sheet inspection; AI review, not human approval", "qa_intermediates_not_delivered": True})


def portable_source():
    folder = ROOT / ".runtime/session_20261004/arxiv_source"
    folder.mkdir(parents=True, exist_ok=True)
    original = ROOT / "manuscript/english_resource_20261004.tex"
    text = original.read_text(encoding="utf-8").replace("../results/20261004_article_build/native40_tradeoff.pdf", "native40_tradeoff.pdf")
    assert "C:/" not in text and "C:\\" not in text
    (folder / "main.tex").write_text(text, encoding="utf-8")
    shutil.copy2(OUT / "native40_tradeoff.pdf", folder / "native40_tradeoff.pdf")
    shutil.copy2(ROOT / "results/20261004_publication_sources/references_19.bib", folder / "references_19.bib")
    env = os.environ.copy()
    env["TECTONIC_CACHE_DIR"] = str(ROOT / ".runtime/tex20261003/cache")
    cmd = [str(ROOT / ".runtime/tex20261003/tectonic-msvc.exe"), "--keep-logs", "main.tex"]
    p = subprocess.run(cmd, cwd=folder, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    (OUT / "portable_source_compile.txt").write_text(p.stdout + p.stderr, encoding="utf-8")
    assert p.returncode == 0, p.stderr[-1500:]
    candidate = PdfReader(folder / "main.pdf")
    original_pdf = PdfReader(original.with_suffix(".pdf"))
    assert len(candidate.pages) == len(original_pdf.pages) == 7
    normal = lambda r: re.sub(r"\s+", "", "".join(x.extract_text() for x in r.pages))
    assert normal(candidate) == normal(original_pdf)
    archive = OUT / "english_preprint_source_20261004.tar.gz"
    members = ["main.tex", "native40_tradeoff.pdf", "references_19.bib"]
    with tarfile.open(archive, "w:gz") as tar:
        for member in members:
            tar.add(folder / member, arcname=member)
    with tarfile.open(archive, "r:gz") as tar:
        assert sorted(tar.getnames()) == sorted(members)
    save(OUT / "portable_source_receipt.json", {"created_utc": now(), "status": "LOCAL_PORTABLE_SOURCE_COMPILE_PASS", "server_arxiv_validation": "NOT_RUN", "submission": "NOT_RUN", "license": "NOT_SELECTED", "archive": archive.relative_to(ROOT).as_posix(), "sha256": sha(archive), "pdf_pages": 7, "extracted_text_identical_to_final_english_pdf": True, "members": [{"path": x, "sha256": sha(folder / x)} for x in members]})


def package():
    docx_qa()
    portable_source()
    qa = json.loads((OUT / "compilation_qa.json").read_text(encoding="utf-8"))
    qa["status"] = "PASS_LOCAL_COMPILE_AND_ALL_PAGES_VISUAL"
    qa["visual_review"] = {"ru": "All eight page PNGs individually inspected at original resolution by GPT-6.1 Sol", "en": "All seven page PNGs individually inspected at original resolution by GPT-6.1 Sol", "root": "Both contact sheets and detailed table/figure pages inspected", "human_review": "NOT_CLAIMED"}
    qa["native_codex_compiler"] = {"status": "PLATFORM_UNAVAILABLE", "diagnostic": "Unable to find standard directories for platform", "sources_open_requested": True, "open_result": "queued", "local_pdf_engine_pass": True}
    save(OUT / "compilation_qa.json", qa)
    selected = []
    for stem in STEMS:
        selected += [f"manuscript/{stem}.{ext}" for ext in ("md", "tex", "pdf")]
    selected += ["manuscript/russian_resource_20261004.docx"]
    selected += [f"docs/{name}" for name in ("CURRENT_STUDY_20261004_RU.md", "EVIDENCE_AUDIT_20261004_RU.md", "PUBLICATION_METADATA_20261004_RU.md", "STUDY_C_LIVE_20261004_RU.md")]
    selected += [f"results/20261004_article_build/{name}" for name in ("native40_tradeoff.pdf", "native40_tradeoff.png", "claim_to_evidence.json", "compilation_qa.json", "docx_qa.json", "portable_source_receipt.json")]
    selected += [f"results/20261004_publication_sources/{name}" for name in ("compact_bibliography_19.json", "references_19.bib", "official_qwen_registry.json", "mera_methodological_source.md")]
    selected += [f"results/20261004_evidence_audit/{name}" for name in ("quality_telemetry_same40.csv", "configuration_comparison.csv", "model_coverage.csv")]
    selected += [f"results/20261004_study_c_live/{name}" for name in ("summary.json", "protocol_frozen.json", "protocol_clarifications_v2.json", "resources_by_arm_offline.json")]
    for rel in selected:
        copy_file(rel)
    # Copy only requested numeric/metadata fields from legacy summaries. Do not
    # export complete Mercury rows or other benchmark/model answer journals.
    claims = json.loads((OUT / "claim_to_evidence.json").read_text(encoding="utf-8"))
    excerpts = {}
    for c in claims["claims"]:
        for e in c["evidence"]:
            p = ROOT / e["path"]
            record = excerpts.setdefault(e["path"], {"original_sha256": sha(p), "fields": {}})
            obj = json.loads(p.read_text(encoding="utf-8"))
            for field in e["fields"]:
                record["fields"][field] = pointer(obj, field)
    save(EDITOR / "evidence_excerpts.json", {"scope": "Selected RFC6901 fields; original paths are repository relative; raw source rows intentionally absent", "sources": excerpts})
    instructions = """# Редакторская копия одной RU/EN работы — 04.10.2026

Статус: READY FOR EDITORIAL REVIEW. Это изолированная копия; запуск Claude,
совместная редактура исходного репозитория и внешняя подача не выполнены.
PDF: 8 страниц RU / 7 EN; editable RU DOCX: 8 страниц. Все страницы проверены
визуально AI-агентами. Это не человеческая рецензия и не submission approval.

Задача будущего редактора: улучшать ясность, связность, научный русский и
английский, подписи и вёрстку. Сначала прочитать docs/CURRENT_STUDY_20261004_RU.md,
затем обе рукописи и claim_to_evidence.json. Таблицы и evidence_excerpts.json
авторитетны для чисел; ключи excerpts — точные JSONPointers оригинальных файлов,
оригинальные hashes сохранены. Bibliography: 19 научных источников; FAO-56 —
источник формул. references_19.bib и полный компактный registry приложены.
Ссылки индекса на исторические журналы и Git delivery относятся к исходному
приватному репозиторию. Для автономной редактуры использовать selected excerpts;
полные исторические файлы не нужны и не включены в эту копию.

Разрешённые выводы: описательное сравнение двух практических конфигураций;
отдельное историческое DEV293 качество и собственное native40 качество/ресурсы;
улучшение заданных численных ответов живым исполнением при сохранении ошибок
уточнения Qwen9. 9B — практический фокус, 27B — quality reference. 32 исполнения
не устанавливают agronomic deployment safety. Это один development case study.

Запрещено менять значения, знаменатели, авторов или их порядок; выдумывать
эксперименты/источники; убирать DEV reuse, разные quantization/generation/offload,
больший tool-arm token budget, HTTP-sum latency и наблюдавшиеся отказы;
превращать DEV в TEST, replay в measured saving, AI review в human review,
94% ratio в accuracy/equivalence или optional35 monitoring failure в OOM.
Не добавлять benchmark questions, gold, raw answers, private correspondence,
credentials или полные сторонние model cards. Сравнения cloud/CLI — supplementary
и разнородные; endpoint Claude после прежнего403 не был повторно испытан.

Авторы: Антоний Сарычев / Antoniy Sarychev; Денис Шестернин / Denis Shesternin.
Аффилиация и точные недостающие поля/права — docs/PUBLICATION_METADATA_20261004_RU.md.
Финальное согласие, contributions и manuscript license требуют людей. RU/EN —
версии одной работы; не создавать два overlapping arXiv submissions. Текст и
source archive уже можно редактировать без ответа MERA и optional models.

После редактуры сохранить новую датированную версию, показать полный diff,
проверить цифры по evidence, пересобрать PDF/DOCX и просмотреть каждую страницу.
Самостоятельно не отправлять письма, не подавать статью и не выбирать лицензию.
"""
    EDITOR.mkdir(parents=True, exist_ok=True)
    (EDITOR / "README.md").write_text(instructions, encoding="utf-8")
    manifest = {"created_utc": now(), "status": "ISOLATED_EDITORIAL_COPY_NOT_APPROVED_FOR_SUBMISSION", "human_review": "PENDING", "license": "NOT_SELECTED", "restricted_raw_exported": False, "files": []}
    for p in sorted(EDITOR.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            manifest["files"].append({"path": p.relative_to(EDITOR).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)})
    save(EDITOR / "manifest.json", manifest)
    archive = ROOT / "outputs/claude_article_editor_20261004.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as z:
        for p in sorted(EDITOR.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(EDITOR).as_posix())
    save(OUT / "editorial_package_receipt.json", {"created_utc": now(), "directory": EDITOR.relative_to(ROOT).as_posix(), "zip": archive.relative_to(ROOT).as_posix(), "zip_sha256": sha(archive), "files": len(manifest["files"]) + 1, "bytes": archive.stat().st_size, "claude_editor_launched": False, "restricted_raw_exported": False})
    print(json.dumps({"editor_files": len(manifest["files"]) + 1, "zip_bytes": archive.stat().st_size, "docx_and_portable_source": "PASS"}))


if __name__ == "__main__":
    package()
