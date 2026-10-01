"""Apply explicit literature annotations without changing historical sections."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
NOTES = {
    "2305.05176": "Каскад и суммарная стоимость всех ступеней; не переносить заявленную экономию на аграрный corpus.",
    "2406.18665": "Preference router; отдельная аграрная и русская калибровка обязательна.",
    "2404.14618": "Hybrid small/large routing и управляемый компромисс quality/cost.",
    "2410.10347": "Различать однократный routing и последовательный cascade; качество estimator определяет выгоду.",
    "2403.12031": "Общая матрица ответов для paired routing comparison и диагностического oracle.",
    "2309.15789": "Сильные стороны моделей учатся на benchmark tasks; смена домена требует проверки переноса.",
    "2310.12963": "Self-verification noisy; verifier тоже имеет стоимость и latency.",
    "2410.03834": "Граф query/task/model; смена модели не эквивалентна прежней калибровке.",
    "2502.08773": "Routing для моделей, отсутствовавших при обучении; полезно при обновлении локального inventory.",
    "2502.18482": "Явные quality/cost/latency tradeoffs; не считать один cloud-call rate полной стоимостью.",
    "2506.03880": "Query-model representation; будущая learned router baseline, избыточна для первого малого pilot.",
    "2602.03478": "Проверять collapse: дешевле доступная модель может систематически игнорироваться router.",
    "2306.13063": "Verbal confidence часто завышен; поле JSON confidence не даёт вероятность корректности.",
    "2404.03163": "Rank-calibration отличает ранжирование риска от конкретной шкалы uncertainty.",
    "2407.18418": "Abstention оценивать вместе с answerability и ошибочным отказом, а не общей accuracy.",
    "2406.15927": "Semantic entropy probes требуют hidden states; не выдавать LM Studio JSON за реализацию метода.",
    "2605.18796": "Isotonic calibration и cost threshold; результаты NER/H100 нельзя экстраполировать на агрономию/5060 Ti.",
    "2407.04721": "Реальные индийские farmer queries; домен и языки отличаются от русской агрометеорологии.",
    "2508.08632": "Agri-342K/Tri-RAG/AgriBench-13K; веса и лицензия конкретного release не подтверждены.",
    "2503.04788": "Аграрный RAG chatbot уже опубликован как препринт; не заявлять аграрный RAG новым сам по себе.",
    "2410.08405": "AgroGPT3B/7B expert tuning для visual QA; text-only расчёты меняют задачу.",
    "2401.01600": "PLLaMa: domain continued pretraining; RU и tool calling не подтверждены.",
    "2601.08308": "Contract-driven/capability-aware agricultural orchestration: прямой конкурент инструментарной идеи.",
    "2605.22366": "Executable agricultural tool benchmark: сверять process/outcome и проверяемость инструментов.",
}
PUBLISHED = {
    "2406.18665": ("ICLR 2025", "https://proceedings.iclr.cc/paper_files/paper/2025/hash/5503a7c69d48a2f86fc00b3dc09de686-Abstract-Conference.html"),
    "2410.10347": ("ICML 2025, PMLR 267:12987-13010", "https://proceedings.mlr.press/v267/dekoninck25a.html"),
    "2502.18482": ("NAACL 2025", "https://aclanthology.org/2025.naacl-long.545/"),
    "2410.03834": ("ICLR 2025", "https://openreview.net/forum?id=eU39PDsZtT"),
    "2502.08773": ("ICLR 2026", "https://openreview.net/forum?id=ka82fvJ5f1"),
    "2410.08405": ("WACV 2025, pp.5687-5696", "https://openaccess.thecvf.com/content/WACV2025/papers/Awais_AgroGPT_Efficient_Agricultural_Vision-Language_Model_with_Expert_Tuning_WACV_2025_paper.pdf"),
    "2512.10624": ("ACM Web Conference 2026", "https://doi.org/10.1145/3774904.3792971"),
}
JOURNALS = [
    {"id": "doi:10.1016/j.compag.2024.109349", "title": "AgXQA: A benchmark for advanced Agricultural Extension question answering", "authors": ["Josué Kpodo", "Parisa Kordjamshidi", "A. Pouyan Nejadhashemi"], "submission_date": None, "publication_year": 2024, "publication_date": "2024-10", "group": "agriculture", "primary_url": "https://www.sciencedirect.com/science/article/pii/S0168169924007403", "doi": "10.1016/j.compag.2024.109349", "peer_review_status": "published_peer_reviewed", "venue": "Computers and Electronics in Agriculture 225:109349", "verification_level": "primary_publisher_metadata_and_abstract", "full_text_reviewed": False, "relevance_ru": "Externally sourced extractive irrigation QA; free-form correctness требует предметной проверки.", "scientific_candidate": True, "within_cutoff": True, "fetch_status": "verified_primary_record"},
    {"id": "doi:10.1016/j.compag.2026.111533", "title": "Evaluating the logical and mathematical reasoning capabilities of language models in agricultural water management", "authors": ["Josué Kpodo", "A. Pouyan Nejadhashemi", "Rasu Eeswaran"], "submission_date": None, "publication_year": 2026, "publication_date": "2026-04", "group": "agriculture", "primary_url": "https://www.sciencedirect.com/science/article/pii/S0168169926001286", "doi": "10.1016/j.compag.2026.111533", "peer_review_status": "published_peer_reviewed", "venue": "Computers and Electronics in Agriculture 245:111533", "verification_level": "primary_publisher_metadata_and_abstract", "full_text_reviewed": False, "relevance_ru": "DEW: 419 вопросов в 24 доменах; FLOW graph context; внешний источник проверяемых water-management случаев.", "scientific_candidate": True, "within_cutoff": True, "fetch_status": "verified_primary_record"},
]

def main():
    data = json.loads((OUT / "papers.json").read_text(encoding="utf-8"))
    # Keep the current-review pool within 60-70 and reserve older GPTQ/SmoothQuant
    # as optional foundations, not extra current-AI references.
    entries = [e for e in data["entries"] if e["id"].startswith("arxiv:") and e["id"] not in {"arxiv:2210.17323", "arxiv:2211.10438"}]
    for e in entries:
        paper = e["id"].split(":")[1]
        e["peer_review_status"] = "preprint_publication_not_verified"
        e["publication_year"] = int(e["submission_date"][:4])
        e["relevance_ru"] = NOTES.get(paper, "Библиографический кандидат: перед включением в статью проверить полный текст, ограничения и близость к эксперименту.")
        if paper in NOTES:
            e["verification_level"] = "primary_metadata_and_abstract_or_method_checked"
        if paper in PUBLISHED:
            e["peer_review_status"] = "published_peer_reviewed"
            e["venue"], e["published_primary_url"] = PUBLISHED[paper]
    entries.extend(JOURNALS)
    data["entries"] = entries
    data["candidate_count"] = len(entries)
    data["focused_checked_count"] = sum(e["verification_level"] != "primary_metadata_only" for e in entries)
    data["limitations"] = ["Thematic candidate pool, not systematic review", "Metadata verification is not full-text review", "Unverified proceedings status is explicitly marked", "Model cards and GitHub do not count as scientific references", "First-submission cutoff does not prove every latest revision was available at cutoff"]
    (OUT / "papers.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    with (OUT / "papers.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["id", "title", "publication_year", "group", "peer_review_status", "verification_level", "primary_url", "relevance_ru"]
        writer = csv.DictWriter(f, fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(entries)
    lines = ["# Кандидаты научной литературы на 01.10.2026", "", f"{len(entries)} уникальных работ. Проверка первичной библиографической записи выполнена для каждой; углублённая проверка abstract/метода выполнена для {data['focused_checked_count']}. Это кандидаты для отбора, а не 69 прочитанных полных текстов. Неподтверждённая публикация помечена явно.", ""]
    groups = dict.fromkeys(e["group"] for e in entries)
    for group in groups:
        lines.extend(["## " + group, "", "| Работа | Год | Статус | Проверка |", "|---|---:|---|---|"])
        for e in entries:
            if e["group"] == group:
                title = e["title"].replace("|", "\\|")
                lines.append(f"| [{title}]({e.get('published_primary_url', e['primary_url'])}) | {e['publication_year']} | {e.get('venue', 'Препринт; publication status не проверен')} | {e['verification_level']} |")
        lines.append("")
    (OUT / "CANDIDATES_RU.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"candidate_count": data["candidate_count"], "focused_checked_count": data["focused_checked_count"], "published_verified": sum(e["peer_review_status"] == "published_peer_reviewed" for e in entries)}))

if __name__ == "__main__":
    main()
