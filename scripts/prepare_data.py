import csv
import hashlib
import json
import math
from pathlib import Path
import random
import httpx

ROOT = Path(__file__).resolve().parents[1]
SEED = 20260930

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    raw = ROOT / "data/raw"
    raw.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(timeout=60, follow_redirects=True)
    repo = "MSU-CECO/agxqa_benchmark_v1"
    commit = client.get(f"https://api.github.com/repos/{repo}/commits/main").json()["sha"]
    url = f"https://raw.githubusercontent.com/{repo}/{commit}/data/for_qa_data_annotated/annotations_part_B_Nov03_Dec23_2023.json"
    resp = client.get(url)
    resp.raise_for_status()
    (raw / "agxqa").mkdir(exist_ok=True)
    (raw / "agxqa/annotations.json").write_bytes(resp.content)
    lic = client.get(f"https://raw.githubusercontent.com/{repo}/{commit}/LICENSE")
    lic.raise_for_status()
    (raw / "agxqa/LICENSE").write_bytes(lic.content)
    qa = []
    total_q = total_p = 0
    seen = set()
    for doc in resp.json()["data"]:
        for paragraph in doc["paragraphs"]:
            total_p += 1
            total_q += len(paragraph["qas"])
            group = sha(paragraph["context"].encode())
            if group in seen:
                continue
            seen.add(group)
            eligible = [q for q in paragraph["qas"] if q.get("answers") and not q.get("is_impossible") and all(a["text"].strip().lower() in paragraph["context"].lower() for a in q["answers"])]
            if not eligible or len(paragraph["context"]) > 1600:
                continue
            q = eligible[0]
            qa.append({"id": f"agxqa_{q['id']}", "group": group, "category": "extractive_qa", "language": "en", "input": q["question"], "context": paragraph["context"], "inputs": {}, "expected": {"action": "ANSWER", "answers": [a["text"].strip() for a in q["answers"]]}, "scoring": "span_em_f1", "source": url, "license": "Apache-2.0 repository declaration; underlying Extension material retains provenance", "difficulty": "not_assigned"})
    qa.sort(key=lambda s: sha((str(SEED) + s["group"]).encode()))
    qa = qa[:120]
    for i, sample in enumerate(qa):
        sample["split"] = "train" if i < 60 else "dev" if i < 90 else "test"
    samples = list(qa)
    rng = random.Random(SEED)
    # Controlled parameter holdout, not independently authored natural questions.
    prefixes = ["В исследовательском примере", "Для учебного участка", "По предоставленным входам", "В контрольной задаче", "Для агрометеорологического стенда", "В демонстрационном расчёте", "Проверь числовой сценарий", "Для сопоставления алгоритмов", "Из исходных величин", "В опыте с погодой", "Для воспроизводимой проверки", "В задаче анализа условий"]
    categories = ["numeric", "missing_data", "tool_selection", "rule_interpretation", "compound_reasoning"]
    for category in categories:
        for group in range(12):
            split = "train" if group < 6 else "dev" if group < 9 else "test"
            for variant in range(4):
                tool = ["gdd", "vpd", "et0", "rain_deficit"][variant]
                language = "ru" if group % 2 == 0 else "en"
                t = rng.randint(12, 28)
                data = {}
                expected = {"action": "ANSWER"}
                if category == "numeric" or category == "missing_data":
                    if tool == "gdd":
                        lo = [rng.randint(2, 13) for _ in range(3)]
                        hi = [x + rng.randint(7, 16) for x in lo]
                        base = rng.choice([0, 5, 10])
                        data = {"tmin": lo, "tmax": hi, "base": base, "temperature_unit": "C"}
                        value = sum(max(0, (x + y) * .5 - base) for x, y in zip(lo, hi))
                        unit = "degC day"
                    elif tool == "vpd":
                        rh = rng.randint(30, 85)
                        data = {"temperature": t, "rh": rh, "temperature_unit": "C"}
                        value = 0.6108 * math.exp(17.27 * t / (t + 237.3)) * (100 - rh) / 100
                        unit = "kPa"
                    elif tool == "et0":
                        data = {"temperature": t, "rn": rng.randint(5, 15), "g": 0, "u2": rng.choice([1, 2, 3]), "es": 2.4, "ea": 1.3, "delta": .15, "gamma": .066, "temperature_unit": "C"}
                        value = (.408*.15*data["rn"]+.066*900/(t+273)*data["u2"]*1.1)/(.15+.066*(1+.34*data["u2"]))
                        unit = "mm/day"
                    else:
                        rain = [rng.randint(0, 12) for _ in range(3)]
                        target = rng.randint(20, 45)
                        data = {"rain": rain, "target": target, "precipitation_unit": "mm"}
                        value = max(0, target - sum(rain))
                        unit = "mm"
                    q = f"{prefixes[group]}, рассчитай {tool}." if language == "ru" else f"Controlled scenario {group}: calculate {tool}."
                    expected.update(numeric=value, unit=unit)
                    if category == "missing_data":
                        removed = {"gdd": "base", "vpd": "rh", "et0": "rn", "rain_deficit": "target"}[tool]
                        data.pop(removed)
                        if group % 3 == 0 and tool != "rain_deficit":
                            data[removed] = 10
                            data["temperature_unit"] = "F"
                        expected = {"action": "ASK_FOR_DATA"}
                elif category == "tool_selection":
                    desc = {"gdd": "тепловую сумму по tmin/tmax и base", "vpd": "дефицит давления пара по температуре и RH", "et0": "эталонную эвапотранспирацию FAO-56", "rain_deficit": "дефицит осадков относительно заданной цели"}[tool]
                    english = {"gdd": "accumulated heat from daily minimum/maximum temperatures and a base", "vpd": "vapour pressure deficit from temperature and relative humidity", "et0": "FAO-56 reference evapotranspiration", "rain_deficit": "rainfall deficit relative to a stated target"}[tool]
                    q = f"{prefixes[group]}: только выбери инструмент, чтобы оценить {desc}; не рассчитывай." if language == "ru" else f"Scenario {group}: select only the tool for {english}; do not calculate."
                    expected["answers"] = [tool]
                elif category == "rule_interpretation":
                    threshold = rng.randint(-4, 4)
                    low = rng.randint(-6, 8)
                    data = {"minimum_temperature": low, "scenario_threshold": threshold, "temperature_unit": "C"}
                    q = f"{prefixes[group]}: по условному правилу RISK тогда и только тогда, когда minimum_temperature < scenario_threshold, иначе NO_RISK. Классифицируй. Порог задан условием, это не норма культуры." if language == "ru" else f"Scenario {group}: return RISK iff minimum_temperature < scenario_threshold, otherwise NO_RISK. This is a stipulated rule, not a crop threshold."
                    expected["answers"] = ["RISK" if low < threshold else "NO_RISK"]
                else:
                    lo, hi = [rng.randint(0, 12) for _ in range(5)], [rng.randint(18, 30) for _ in range(5)]
                    rain = [rng.randint(0, 10) for _ in range(5)]
                    base, target = 5, 25
                    heat = sum(max(0, (x+y)/2-base) for x,y in zip(lo,hi))
                    data = {"daily_min": lo, "daily_max": hi, "daily_rain": rain, "base_c": base, "heat_threshold": 45, "rain_target_mm": target}
                    q = f"{prefixes[group]}: условный ALERT, если сумма max(0,(daily_min+daily_max)/2-base_c) больше heat_threshold И сумма daily_rain меньше rain_target_mm; иначе OK. Верни только метку. Это формальная проверка, без рекомендаций по поливу." if language == "ru" else f"Scenario {group}: return ALERT if sum(max(0,(daily_min+daily_max)/2-base_c)) > heat_threshold AND sum(daily_rain) < rain_target_mm, otherwise OK. No irrigation prescription."
                    expected["answers"] = ["ALERT" if heat > 45 and sum(rain) < target else "OK"]
                samples.append({"id": f"controlled_{category}_{group}_{variant}", "group": f"controlled_{category}_{group}", "split": split, "category": category, "language": language, "input": q, "context": "", "inputs": data, "expected": expected, "scoring": "numeric_tolerance" if category == "numeric" else "action" if category == "missing_data" else "exact_label", "source": "scripts/prepare_data.py; formula-controlled synthetic research scenarios", "license": "CC0-1.0 (new controlled scenarios)", "difficulty": "not_assigned"})
    output = ROOT / "data/benchmark.jsonl"
    content = "".join(json.dumps(s, ensure_ascii=False) + "\n" for s in samples).encode("utf-8")
    output.write_bytes(content)
    manifest = {"version": "agro-route-v0.2", "seed": SEED, "access_date": "2026-09-30", "benchmark_sha256": sha(content), "sample_count": len(samples), "agxqa_commit": commit, "agxqa_raw_sha256": sha(resp.content), "agxqa_raw_questions": total_q, "agxqa_raw_paragraphs": total_p, "agxqa_selected": len(qa), "split": {s: sum(x["split"] == s for x in samples) for s in ("train", "dev", "test")}, "provenance": {"agxqa": url}}
    (ROOT / "data/dataset_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    # Reproducible demonstration outside the benchmark.
    weather_url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {"parameters": "T2M_MIN,T2M_MAX,PRECTOTCORR", "community": "AG", "longitude": 37.3, "latitude": 56.0, "start": "20250501", "end": "20250507", "format": "JSON", "time-standard": "UTC"}
    weather = client.get(weather_url, params=params)
    weather.raise_for_status()
    (raw / "nasa_moscow_week.json").write_bytes(weather.content)
    (raw / "nasa_manifest.json").write_text(json.dumps({"url": str(weather.url), "sha256": sha(weather.content), "access_date": "2026-09-30", "coordinates": [37.3,56.0], "time_standard": "UTC"}, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))

if __name__ == "__main__":
    main()
