"""Exploratory irrigation lab. Synthetic experiments, never farm prescriptions.

The learned model is a chronological ridge regression for next-day root-zone
available water. Policy simulations use an explicitly separate bucket model.
"""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import date, timedelta
import hashlib
import io
import json
import math

import numpy as np


class InputError(ValueError):
    """A user-visible problem with a scenario or uploaded observations."""


@dataclass(frozen=True)
class Config:
    area_ha: float = 8.0
    capacity_mm: float = 90.0
    threshold_fraction: float = 0.60
    target_fraction: float = 0.72
    kc: float = 1.05
    efficiency: float = 0.85
    max_irrigation_mm: float = 25.0
    calendar_interval_days: int = 5
    calendar_amount_mm: float = 25.0
    water_rub_m3: float = 12.0
    investment_rub: float = 85000.0
    annual_opex_rub: float = 18000.0
    season_days: int = 120


BOUNDS = {
    "area_ha": (0.1, 10000), "capacity_mm": (20, 300),
    "threshold_fraction": (0.1, 0.9), "target_fraction": (0.15, 0.95),
    "kc": (0.2, 1.5), "efficiency": (0.3, 1),
    "max_irrigation_mm": (1, 60), "calendar_interval_days": (1, 14),
    "calendar_amount_mm": (1, 60), "water_rub_m3": (0, 1000),
    "investment_rub": (0, 10000000), "annual_opex_rub": (0, 10000000),
    "season_days": (1, 365),
}


def number(value, name, low, high):
    if isinstance(value, (bool, str)) or not isinstance(value, (int, float)):
        raise InputError(f"{name}: ожидается число")
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise InputError(f"{name}: допустимо от {low} до {high}")
    return value


def config_from_dict(data=None):
    if data is None:
        return Config()
    if not isinstance(data, dict):
        raise InputError("Параметры участка должны быть объектом")
    unknown = set(data) - set(BOUNDS)
    if unknown:
        raise InputError("Неизвестные параметры: " + ", ".join(sorted(unknown)))
    values = asdict(Config())
    for key, value in data.items():
        values[key] = number(value, key, *BOUNDS[key])
    for key in ("calendar_interval_days", "season_days"):
        if values[key] != int(values[key]):
            raise InputError(f"{key}: требуется целое число")
        values[key] = int(values[key])
    if values["target_fraction"] <= values["threshold_fraction"]:
        raise InputError("Целевой запас должен быть выше порога дефицита")
    if values["calendar_amount_mm"] > values["max_irrigation_mm"]:
        raise InputError("Календарная норма превышает суточный лимит")
    return Config(**values)


COLUMNS = ("date", "soil_mm", "rain_forecast_mm", "et0_forecast_mm",
           "irrigation_mm", "next_soil_mm", "rain_actual_mm", "et0_actual_mm")


def water_step(soil, rain, et0, irrigation, cfg):
    """Simplified daily balance; no runoff/salinity/groundwater/yield model."""
    available = soil + rain + cfg.efficiency * irrigation - cfg.kc * et0
    return max(0.0, min(cfg.capacity_mm, available)), max(0.0, available - cfg.capacity_mm)


def generate_demo(seed=42, days=120, cfg=None, scenario="mixed"):
    cfg = cfg or Config()
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 1000000:
        raise InputError("Seed: целое число от 0 до 1000000")
    if isinstance(days, bool) or not isinstance(days, int) or not 60 <= days <= 365:
        raise InputError("Длительность демонстрации: 60–365 дней")
    if scenario not in ("mixed", "dry", "rainy"):
        raise InputError("Неизвестный погодный сценарий")
    rng = np.random.default_rng(seed)
    rows, soil = [], cfg.capacity_mm * cfg.target_fraction
    for i in range(days):
        et0 = float(np.clip(4 + 1.25 * math.sin(i / 15) + rng.normal(0, .4), 1.4, 7))
        probability = {"dry": .06, "mixed": .24, "rainy": .48}[scenario]
        rain = float(rng.uniform(3, 18) if rng.random() < probability else 0)
        rain_forecast = max(0.0, rain + float(rng.normal(0, 2.4)))
        et0_forecast = max(.1, et0 + float(rng.normal(0, .45)))
        # Historical operator behavior includes varying doses, not optimal labels.
        irrigation = float(rng.uniform(8, cfg.max_irrigation_mm)) if soil < cfg.capacity_mm * .78 and i % 3 == 0 and cfg.max_irrigation_mm >= 8 else 0.0
        next_soil, _ = water_step(soil, rain, et0, irrigation, cfg)
        observed = float(np.clip(next_soil + rng.normal(0, .9), 0, cfg.capacity_mm))
        rows.append(dict(zip(COLUMNS, ((date(2026, 6, 1) + timedelta(days=i)).isoformat(),
                    round(soil, 4), round(rain_forecast, 4), round(et0_forecast, 4),
                    round(irrigation, 4), round(observed, 4), round(rain, 4), round(et0, 4)))))
        soil = next_soil
    return rows


def csv_text(rows):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows({key: row.get(key, "") for key in COLUMNS} for row in rows)
    return out.getvalue()


def parse_csv(text):
    if not isinstance(text, str) or len(text) > 180000:
        raise InputError("CSV должен быть текстом до 180 КБ")
    sample = text.lstrip("\ufeff")
    delimiter = ";" if ";" in sample.split("\n", 1)[0] else ","
    reader = csv.DictReader(io.StringIO(sample), delimiter=delimiter)
    required = set(COLUMNS[:6])
    if not required.issubset(reader.fieldnames or []):
        raise InputError("Нужны колонки: " + ", ".join(COLUMNS[:6]))
    rows = []
    for i, raw in enumerate(reader, 2):
        if i > 366:
            raise InputError("CSV: максимум 365 наблюдений")
        row = {"date": raw.get("date", "")}
        for key in COLUMNS[1:]:
            value = raw.get(key)
            if value is None or not value.strip():
                if key in COLUMNS[:6]:
                    raise InputError(f"Строка {i}: нет значения {key}; пропуск не равен нулю")
                continue
            try:
                row[key] = float(value.strip())
            except (ValueError, AttributeError):
                raise InputError(f"Строка {i}: некорректное число {key}") from None
        rows.append(row)
    return rows


def validate_rows(rows, cfg):
    if not isinstance(rows, list) or not 30 <= len(rows) <= 365:
        raise InputError("Нужны 30–365 ежедневных наблюдений")
    clean, previous = [], None
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise InputError(f"Строка {i}: ожидается объект")
        try:
            current = date.fromisoformat(row.get("date", ""))
        except (ValueError, TypeError):
            raise InputError(f"Строка {i}: дата в формате YYYY-MM-DD") from None
        if previous is not None and current != previous + timedelta(days=1):
            raise InputError("Даты должны идти ежедневно по порядку без пропусков и повторов")
        item = {"date": current.isoformat()}
        for key in COLUMNS[1:]:
            if key not in row:
                if key in COLUMNS[:6]:
                    raise InputError(f"Строка {i}: отсутствует {key}")
                continue
            hi = cfg.capacity_mm if key in ("soil_mm", "next_soil_mm") else 150 if "rain" in key else 20 if "et0" in key else 60
            item[key] = number(row[key], f"Строка {i}, {key}", 0, hi)
        clean.append(item)
        previous = current
    return clean


def features(row, soil=None, irrigation=None):
    s = row["soil_mm"] if soil is None else soil
    irr = row["irrigation_mm"] if irrigation is None else irrigation
    return [s, row["rain_forecast_mm"], row["et0_forecast_mm"], irr]


@dataclass
class Ridge:
    mean: np.ndarray
    scale: np.ndarray
    coefficients: np.ndarray

    def predict(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.r_[1.0, (x - self.mean) / self.scale] @ self.coefficients)


def fit_model(rows):
    x = np.asarray([features(row) for row in rows], dtype=float)
    y = np.asarray([row["next_soil_mm"] for row in rows], dtype=float)
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale < 1e-9] = 1.0
    design = np.column_stack([np.ones(len(x)), (x - mean) / scale])
    penalty = np.diag([0.0, 1.0, 1.0, 1.0, 1.0])
    coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ y)
    return Ridge(mean, scale, coefficients)


def choose_irrigation(policy, i, soil, row, cfg, model):
    threshold, target = cfg.capacity_mm * cfg.threshold_fraction, cfg.capacity_mm * cfg.target_fraction
    if policy == "calendar":
        amount = min(cfg.calendar_amount_mm, cfg.max_irrigation_mm) if i % cfg.calendar_interval_days == 0 else 0.0
        return amount, "Календарный день полива" if amount else "Пауза по календарю"
    predicted = (model.predict(features(row, soil, 0.0)) if policy == "ml" else
                 soil + row["rain_forecast_mm"] - cfg.kc * row["et0_forecast_mm"])
    if predicted >= threshold:
        return 0.0, "Ожидаемый запас выше порога"
    if policy == "rule":
        amount = min(cfg.max_irrigation_mm, max(0.0, (target - predicted) / cfg.efficiency))
        return amount, "Водный баланс прогнозирует дефицит"
    # Learned response to irrigation must be plausible before use in planning.
    response = model.predict(features(row, soil, cfg.max_irrigation_mm)) - predicted
    if not .15 * cfg.max_irrigation_mm <= response <= 1.2 * cfg.max_irrigation_mm:
        amount = min(cfg.max_irrigation_mm, max(0.0, (target - (soil + row["rain_forecast_mm"] - cfg.kc * row["et0_forecast_mm"])) / cfg.efficiency))
        return amount, "ML отклонён: расчётный резервный план"
    amounts = np.linspace(0, cfg.max_irrigation_mm, 101)
    for amount in amounts:
        if model.predict(features(row, soil, float(amount))) >= target:
            return float(amount), "Минимальная доза для целевого прогноза ML"
    return cfg.max_irrigation_mm, "Прогноз дефицита: достигнут суточный лимит"


def simulate(policy, rows, cfg, model):
    soil, daily = rows[0]["soil_mm"], []
    for i, row in enumerate(rows):
        amount, reason = choose_irrigation(policy, i, soil, row, cfg, model)
        rain, et0 = row["rain_actual_mm"], row["et0_actual_mm"]
        predicted = max(0, min(cfg.capacity_mm, model.predict(features(row, soil, amount))))
        next_soil, drainage = water_step(soil, rain, et0, amount, cfg)
        daily.append({"date": row["date"], "soil_start_mm": round(soil, 3),
                      "soil_end_mm": round(next_soil, 3), "predicted_soil_mm": round(predicted, 3),
                      "irrigation_mm": round(amount, 3), "rain_mm": rain,
                      "et0_mm": et0, "drainage_mm": round(drainage, 3),
                      "deficit": next_soil < cfg.capacity_mm * cfg.threshold_fraction,
                      "reason": reason})
        soil = next_soil
    total = sum(day["irrigation_mm"] for day in daily)
    return {"policy": policy, "water_mm": round(total, 3),
            "water_m3": round(total * cfg.area_ha * 10, 2),
            "water_cost_rub": round(total * cfg.area_ha * 10 * cfg.water_rub_m3, 2),
            "deficit_days": sum(day["deficit"] for day in daily),
            "irrigation_days": sum(day["irrigation_mm"] > 0 for day in daily),
            "drainage_mm": round(sum(day["drainage_mm"] for day in daily), 3),
            "daily": daily}


def analyse(payload):
    if not isinstance(payload, dict):
        raise InputError("Запрос должен быть объектом")
    cfg = config_from_dict(payload.get("config"))
    source = payload.get("source", "demo")
    if source == "demo":
        rows = generate_demo(payload.get("seed", 42), payload.get("days", 120), cfg,
                             payload.get("scenario", "mixed"))
    elif source == "csv":
        rows = parse_csv(payload.get("csv", ""))
    else:
        raise InputError("Выберите демонстрацию или CSV")
    rows = validate_rows(rows, cfg)
    split = int(len(rows) * .7)
    train, test = rows[:split], rows[split:]
    model = fit_model(train)
    errors = [max(0, min(cfg.capacity_mm, model.predict(features(row)))) - row["next_soil_mm"] for row in test]
    rule_errors = [max(0, min(cfg.capacity_mm, row["soil_mm"] + row["rain_forecast_mm"] + cfg.efficiency * row["irrigation_mm"] - cfg.kc * row["et0_forecast_mm"])) - row["next_soil_mm"] for row in test]
    can_simulate = all("rain_actual_mm" in row and "et0_actual_mm" in row for row in test)
    comparisons = {p: simulate(p, test, cfg, model) for p in ("calendar", "rule", "ml")} if can_simulate else {}
    economics = None
    if can_simulate:
        baseline, learned = comparisons["calendar"], comparisons["ml"]
        saved = baseline["water_m3"] - learned["water_m3"]
        annual_gross = saved * cfg.water_rub_m3 / len(test) * cfg.season_days
        net = annual_gross - cfg.annual_opex_rub
        economics = {"saved_m3": round(saved, 2),
                     "saved_percent": round(100 * saved / baseline["water_m3"], 2) if baseline["water_m3"] else None,
                     "annual_gross_rub": round(annual_gross, 2), "annual_net_rub": round(net, 2),
                     "payback_years": round(cfg.investment_rub / net, 2) if net > 0 else None,
                     "comparable_deficit": learned["deficit_days"] <= baseline["deficit_days"],
                     "label": "Сценарная проекция по симуляции; урожайность и прибыль не измерены"}
    last = rows[-1]
    amount, reason = choose_irrigation("ml", 0, last["soil_mm"], last, cfg, model)
    prediction = max(0, min(cfg.capacity_mm, model.predict(features(last, last["soil_mm"], amount))))
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {"schema": "agroplan-irrigation-v1", "source": source, "config": asdict(cfg),
            "data": {"rows": len(rows), "start": rows[0]["date"], "end": last["date"],
                     "sha256": digest, "simulation_available": can_simulate},
            "model": {"name": "Ridge regression", "train_rows": len(train), "test_rows": len(test),
                      "train_end": train[-1]["date"], "test_start": test[0]["date"],
                      "mae_mm": round(float(np.mean(np.abs(errors))), 3),
                      "rule_mae_mm": round(float(np.mean(np.abs(rule_errors))), 3),
                      "features": list(COLUMNS[1:5]), "alpha": 1.0,
                      "coefficients": model.coefficients.tolist(),
                      "mean": model.mean.tolist(), "scale": model.scale.tolist()},
            "recommendation": {"date": last["date"], "irrigation_mm": round(amount, 2),
                               "volume_m3": round(amount * cfg.area_ha * 10, 1),
                               "predicted_soil_mm": round(prediction, 2), "reason": reason,
                               "label": "План для даты последнего наблюдения; требуется проверка специалистом"},
            "comparisons": comparisons, "economics": economics,
            "limitations": ["Учебный MVP; тема и формат сдачи предварительные.",
                            "Демонстрационные данные синтетические; прогноз ML проверяется только на указанном ряде.",
                            "Сравнение политик — контрфактическая симуляция упрощённого водного баланса, не полевой опыт.",
                            "Параметры культуры, запаса и затрат — сценарные допущения, не агрономические нормы.",
                            "Поливная автоматика не подключена; план требует подтверждения специалистом.",
                            "Нет модели урожайности, штрафов за дефицит, солёности и полноценного FAO-56 расчёта ET0."],
            "sources": [{"title": "FAO-56: soil water balance", "url": "https://www.fao.org/4/X0490E/x0490e0e.htm"},
                        {"title": "FAO CROPWAT", "url": "https://www.fao.org/land-water/resources/tools/software/cropwat/en"}]}
