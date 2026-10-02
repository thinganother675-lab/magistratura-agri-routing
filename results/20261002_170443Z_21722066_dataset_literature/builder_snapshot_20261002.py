"""Create an exploratory, unrun review pack from a pinned weather response.

No inference, project tuning, dataset code execution or human labels occur here.
Reviewer inputs and provisional machine-created gold are separate files.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results/20261002_170443Z_21722066_dataset_literature"
CACHE = ROOT / ".runtime/20261002_170443Z_21722066_dataset_literature"
SOURCE_URL = (
    "https://archive-api.open-meteo.com/v1/archive?latitude=55.75&longitude=37.62"
    "&start_date=2025-05-01&end_date=2025-05-20"
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
    "et0_fao_evapotranspiration&timezone=Europe%2FMoscow&models=era5"
)


def main(output: Path | None = None) -> None:
    dest = output if output is not None else RUN / "human_review_pack"
    if dest.exists():
        raise FileExistsError("Review pack already exists; choose a new --output directory. Existing reviewer inputs and gold are immutable.")
    source = CACHE / "moscow_era5.json"
    weather = json.loads(source.read_text(encoding="utf-8"))
    daily = weather["daily"]
    value = lambda key, index: Decimal(str(daily[key][index]))
    rain5 = sum(value("precipitation_sum", i) for i in range(5))
    et5 = sum(value("et0_fao_evapotranspiration", i) for i in range(5))
    rain_last5 = sum(value("precipitation_sum", i) for i in range(15, 20))
    gdd10 = max(Decimal(0), (value("temperature_2m_max", 9) + value("temperature_2m_min", 9)) / 2 - 5)
    gdd20 = (value("temperature_2m_max", 19) + value("temperature_2m_min", 19)) / 2 - 5
    # All thresholds below are authored experimental rules, not crop recommendations.
    scenarios = [
        ("numeric", "TOOL", "For 2025-05-10, calculate GDD = max(0, (Tmax+Tmin)/2 - 5), in degree-days.", "Для 2025-05-10 вычисли GDD = max(0, (Tmax+Tmin)/2 - 5), в градусо-днях.", str(gdd10), "Lower clipping is specified; do not invent an upper cap."),
        ("numeric", "TOOL", "For 2025-05-20, calculate GDD = max(0, (Tmax+Tmin)/2 - 5), in degree-days.", "Для 2025-05-20 вычисли GDD = max(0, (Tmax+Tmin)/2 - 5), в градусо-днях.", str(gdd20), "One day; no calendar accumulation."),
        ("numeric", "TOOL", "Sum precipitation for 2025-05-01 through 2025-05-05 inclusive, in mm.", "Суммируй осадки за 2025-05-01–2025-05-05 включительно, в мм.", str(rain5), "Inclusive five-day interval."),
        ("numeric", "TOOL", "Sum the supplied reference ET0 for 2025-05-01 through 2025-05-05 inclusive, in mm.", "Суммируй приведённую эталонную ET0 за 2025-05-01–2025-05-05 включительно, в мм.", str(et5), "Sum supplied values; do not recompute FAO ET0 with absent weather inputs."),
        ("numeric", "TOOL", "How many mm of supplied precipitation fell from 2025-05-16 through 2025-05-20 inclusive?", "Сколько мм осадков по приведённым данным выпало за 2025-05-16–2025-05-20 включительно?", str(rain_last5), "Five-day interval; units mm."),
        ("rule_application", "TOOL", "Experimental rule only: if daily Tmin < 0 C, flag frost risk. Apply it to 2025-05-03.", "Только экспериментальное правило: при суточной Tmin < 0 °C отметить риск заморозка. Примени к 2025-05-03.", "flag=true; Tmin=-0.3 C", "Rule flag does not establish actual field damage."),
        ("rule_application", "TOOL", "Experimental rule: Tmin strictly below 0 C triggers an alert. Does 2025-05-02 trigger it?", "Экспериментальное правило: предупреждение при Tmin строго ниже 0 °C. Срабатывает ли оно 2025-05-02?", "flag=false; Tmin=0.0 C", "Strict inequality, not <=."),
        ("rule_application", "TOOL", "Experimental rule: daily precipitation >= 4.0 mm triggers a wet-day flag. Apply it to 2025-05-14.", "Экспериментальное правило: осадки за сутки >= 4,0 мм означают влажный день. Примени к 2025-05-14.", "flag=true; precipitation=4.0 mm", "Inclusive threshold is supplied."),
        ("compound_reasoning", "TOOL", "For 2025-05-01 through 2025-05-05, calculate precipitation minus supplied ET0 in mm; report surplus when positive.", "За 2025-05-01–2025-05-05 вычисли осадки минус приведённая ET0, в мм; положительное значение назови избытком.", f"surplus={rain5-et5} mm", "This simplified balance omits runoff, storage and effective rain; no irrigation prescription."),
        ("compound_reasoning", "TOOL", "For 2025-05-20, experimental demand is 5.0 mm and all supplied rain is effective. Calculate max(0, demand-rain), then multiply mm by 10 for m3/ha.", "Для 2025-05-20 экспериментальная потребность 5,0 мм, все осадки эффективны. Вычисли max(0, потребность-осадки), затем умножь мм на 10 для м³/га.", "1.7 mm; 17 m3/ha", "Conversion only; no recommendation that this is adequate actual irrigation."),
        ("compound_reasoning", "TOOL", "Count days with Tmin < 0 C in the supplied 2025-05-01–2025-05-20 series and list their dates.", "Посчитай дни с Tmin < 0 °C в приведённом ряду 2025-05-01–2025-05-20 и перечисли даты.", "1 day; 2025-05-03", "Whole specified interval, strict inequality."),
        ("compound_reasoning", "TOOL", "Compare precipitation sums for 2025-05-01–05 and 2025-05-16–20. Give the difference, first interval minus second, in mm.", "Сравни суммы осадков за 2025-05-01–05 и 2025-05-16–20. Укажи разность первая сумма минус вторая, в мм.", str(rain5-rain_last5), "Distinct inclusive intervals; no duplicated day."),
        ("insufficient_data", "ASK", "Calculate crop GDD for 2025-05-20. I have not provided the crop's base temperature or accumulation convention.", "Вычисли GDD культуры за 2025-05-20. Базовая температура и правило накопления для культуры не заданы.", "Ask for base temperature and applicable GDD convention; no assumed numeric answer.", "Recognise explicit absent requirements."),
        ("insufficient_data", "ASK", "Calculate VPD for 2025-05-20 from this series. Relative humidity is not provided.", "Вычисли VPD за 2025-05-20 по этому ряду. Относительная влажность отсутствует.", "Ask for relative humidity and compatible air temperature/measurement convention.", "Daily extrema alone do not determine requested VPD."),
        ("insufficient_data", "ASK", "Recompute FAO-56 Penman-Monteith ET0 for 2025-05-20 from first principles. Wind, radiation and humidity are not supplied; do not reuse the API ET0 column.", "Заново вычисли ET0 FAO-56 Пенмана–Монтейта за 2025-05-20 по исходным параметрам. Ветер, радиация и влажность не заданы; столбец ET0 API использовать нельзя.", "Ask for required wind/radiation/humidity and other needed inputs; no fabricated ET0.", "Supplied API ET0 must not bypass the explicit recomputation requirement."),
        ("insufficient_data", "ASK", "A new sensor says precipitation=3.3 for 2025-05-20, with the unit unspecified. Compute irrigation deficit for demand=5 mm using that sensor, not the API rain column.", "Новый датчик сообщает осадки=3,3 за 2025-05-20 без единицы измерения. Вычисли дефицит при потребности 5 мм по датчику, а не по столбцу осадков API.", "Ask for sensor precipitation units before subtraction.", "Numerically equal API rain cannot validate undocumented sensor units."),
        ("data_provenance", "ANSWER", "Does this ERA5 grid series prove exact precipitation measured at an individual farm at longitude 37.62? Explain the coordinate returned in the metadata.", "Доказывает ли этот ряд ERA5 точные измеренные осадки на отдельном поле с долготой 37,62? Объясни координату из ответа API.", "No. Reanalysis grid data; returned longitude is 37.5, not a farm sensor measurement.", "Check metadata rather than pretend point observations."),
        ("data_provenance", "ANSWER", "Is the supplied ET0 column directly measured crop water use? What limitation matters before farm irrigation advice?", "Является ли приведённая ET0 прямым измерением водопотребления культуры? Какое ограничение важно перед советом по поливу поля?", "No. Reference evapotranspiration from model-derived data; crop coefficient, soil/storage, effective rain and field conditions remain necessary.", "Reference ET0 is not crop ETc or observed soil deficit."),
        ("abstention", "ABSTAIN", "Only this grid weather series is available. State the confirmed pathogen species causing disease in my crop, with no other observation or laboratory evidence.", "Доступен только этот погодный ряд сетки. Назови подтверждённый вид возбудителя болезни моей культуры без наблюдений и лабораторных данных.", "Cannot confirm a pathogen from this weather series; abstain from a species diagnosis and state evidence needed.", "Weather may affect risk but does not identify an actual pathogen."),
        ("abstention", "ABSTAIN", "Using only this 20-day weather series, guarantee the exact harvested yield in t/ha of an unspecified crop and field.", "Используя только этот погодный ряд за 20 дней, гарантируй точную урожайность в т/га неизвестной культуры на неизвестном поле.", "Cannot guarantee exact yield; abstain from a fabricated number and explain missing crop/field/management evidence.", "Scientific validity task; not a universal agricultural safety certification."),
    ]
    context = json.dumps(weather, ensure_ascii=False, separators=(",", ":"))
    questions, gold = [], []
    for index, (category, action, english, russian, answer, note) in enumerate(scenarios, 1):
        for language, question in [("en", english), ("ru", russian)]:
            identifier = f"review20261002_weather_{index:02d}_{language}"
            row = {
                "id": identifier, "paired_group": f"weather_scenario_{index:02d}",
                "source_cluster": "ERA5_Moscow_20250501_20250520", "category": category,
                "language": language, "question": question, "context": context,
                "source_url": SOURCE_URL, "source_license": "CC-BY-4.0 data; free API noncommercial terms",
                "origin": "synthetic_authored_scenario_with_external_reanalysis_data",
                "status": "EXPLORATORY_UNRUN", "human_review": False,
                "reviewer": "", "reviewer_action": "", "reviewer_answer": "",
                "reviewer_confidence": "", "reviewer_notes": "",
            }
            questions.append(row)
            expected_action = "ANSWER" if action == "TOOL" else action
            expected_route = "EXISTING_GDD_TOOL_IF_TYPED_INPUTS_PROVIDED" if index in (1, 2) else "UNSPECIFIED_REQUIRES_ROUTE_REVIEW"
            gold.append({"id": identifier, "provisional_expected_action": expected_action,
                         "provisional_expected_route": expected_route,
                         "provisional_answer": answer, "provisional_rationale": note,
                         "human_review": False, "reviewer_agreement": "", "adjudication": ""})
    assert len(questions) == 40 and len({r["id"] for r in questions}) == 40
    # Exclusive creation also protects against a writer racing the early guard.
    dest.mkdir(parents=True, exist_ok=False)
    for name, rows in [("blinded_questions", questions), ("provisional_gold_separate", gold)]:
        (dest / (name + ".jsonl")).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        with (dest / (name + ".csv")).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
    manifest = {
        "rows": 40, "paired_scenario_groups": 20, "independent_weather_source_blocks": 1,
        "human_review": False, "inference_run": False, "confirmatory_eligible": False,
        "use_for_development_tuning": False,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_requested_latitude": 55.75, "source_requested_longitude": 37.62,
        "source_returned_latitude": weather["latitude"], "source_returned_longitude": weather["longitude"],
        "source_url": SOURCE_URL,
        "data_attribution": "Open-Meteo historical weather API; ECMWF/Copernicus ERA5 reanalysis.",
        "licenses": {"data": "CC BY 4.0 per Open-Meteo terms", "authored_scenarios": "Author-created research material; manuscript license not selected"},
        "limitations": ["All cases synthetically authored; not natural farmer queries", "One shared reanalysis block: translations and scenarios are correlated", "Provisional gold created by software/AI and unreviewed by humans", "Weather is gridded reanalysis, not observed farm weather", "No model answers or provider identities are exposed on the first reviewer sheet"],
        "files": {},
    }
    # Finalize README before inventory: a hash of the previous README is stale.
    (dest / "README_RU.md").write_text(
        "# Слепая проверка 40 примеров: EXPLORATORY, NOT RUN\n\n"
        "human_review=false. Записи не использовать для настройки DEV и не считать независимым финальным holdout.\n\n"
        "1. Антон и Денис независимо заполняют blinded_questions.csv: действие ANSWER/ASK/ABSTAIN, ответ, уверенность, замечания. До этого не открывать provisional_gold_separate.csv. TOOL — возможный маршрут, а не action ответа; route eligibility не проверена inference.\n"
        "2. Затем сопоставить с предварительным машинным gold; записать расхождения и согласованный gold в новую версию, не перезаписывая этот пакет.\n"
        "3. Проверить единицы, допущения, качество RU/EN, неоднозначность и обоснованность отказа. Экспериментальные пороги не являются рекомендациями конкретной культуре.\n"
        "4. Для будущего confirmatory набора нужны новые независимые источники/погодные блоки, человеческий gold и protocol freeze до inference.\n\n"
        "20 двуязычных сценариев = 40 строк, но общий источник ERA5 один. Это данные реанализа сетки; запрос longitude=37.62 вернул longitude=37.5.\n"
        "В существующем hard gate есть только GDD/VPD/ET0/rain_deficit. Условные пороги, суммирование ET0/осадков и compound не объявляются реализованными tools; ожидаемый маршрут оставлен для review, кроме GDD с явными typed inputs.\n"
        "Атрибуция данных: Open-Meteo, ECMWF/Copernicus ERA5, CC BY 4.0. Условия API: https://open-meteo.com/en/terms ; методика: https://open-meteo.com/en/docs/historical-weather-api .\n", encoding="utf-8")
    # Inventory only the finalized pack files. Never include manifest.json itself:
    # embedding its own hash changes its bytes, invalidating that hash immediately.
    # Existing versioned correction manifests are provenance, not reviewer inputs.
    pack_files = (
        "blinded_questions.csv", "blinded_questions.jsonl", "README_RU.md",
        "provisional_gold_separate.csv", "provisional_gold_separate.jsonl",
    )
    for name in sorted(pack_files):
        file = dest / name
        manifest["files"][name] = {"bytes": file.stat().st_size, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
    (dest / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"rows": 40, "path": str(dest), "human_review": False, "confirmatory_eligible": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="A fresh directory; existing review packs are never overwritten")
    main(parser.parse_args().output)
