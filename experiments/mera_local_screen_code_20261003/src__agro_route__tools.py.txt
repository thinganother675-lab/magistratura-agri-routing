"""Small, unit-explicit numerical executors. FAO-56 eqs. 6, 11, 13."""
import math

REQUIRED = {
    "gdd": ("tmin", "tmax", "base", "temperature_unit"),
    "vpd": ("temperature", "rh", "temperature_unit"),
    "et0": ("temperature", "rn", "g", "u2", "es", "ea", "delta", "gamma", "temperature_unit"),
    "rain_deficit": ("target", "rain", "precipitation_unit"),
}
UNITS = {"gdd": "degC day", "vpd": "kPa", "et0": "mm/day", "rain_deficit": "mm"}

class InputError(ValueError):
    pass

def finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise InputError("Ожидается конечное число")
    return float(value)

def vector(value):
    values = value if isinstance(value, list) else [value]
    if not values:
        raise InputError("Пустой ряд")
    return [finite(v) for v in values]

def validate(tool, data):
    if tool not in REQUIRED:
        raise InputError("Неизвестный инструмент")
    missing = [k for k in REQUIRED[tool] if k not in data]
    if missing:
        raise InputError("Нужны входы: " + ", ".join(missing))
    if "temperature_unit" in data and data["temperature_unit"] != "C":
        raise InputError("Явно преобразуйте температуру в C; не угадываем единицы")
    if tool == "rain_deficit" and data["precipitation_unit"] != "mm":
        raise InputError("Осадки и целевой уровень должны быть в mm")

def execute(tool, data):
    validate(tool, data)
    if tool == "gdd":
        lo, hi, base = vector(data["tmin"]), vector(data["tmax"]), finite(data["base"])
        if len(lo) != len(hi) or any(a > b for a, b in zip(lo, hi)):
            raise InputError("Несогласованные tmin/tmax")
        if any(not -60 <= t <= 60 for t in lo + hi) or not -20 <= base <= 40:
            raise InputError("Температуры вне области демонстрационного инструмента")
        value = sum(max(0, (a + b) / 2 - base) for a, b in zip(lo, hi))
    elif tool == "vpd":
        t, rh = finite(data["temperature"]), finite(data["rh"])
        if not -40 <= t <= 60 or not 0 <= rh <= 100:
            raise InputError("Требуется -40<=T<=60 C и 0<=RH<=100 %")
        value = 0.6108 * math.exp(17.27 * t / (t + 237.3)) * (1 - rh / 100)
    elif tool == "et0":
        t, rn, g, u2, es, ea, delta, gamma = (finite(data[k]) for k in REQUIRED[tool][:-1])
        if not -40 <= t <= 60 or not (0 <= u2 <= 30 and 0 <= ea <= es <= 15 and 0 < delta < 2 and 0 < gamma < 1):
            raise InputError("Недопустимые входы FAO-56")
        # Rn and G are MJ m^-2 day^-1; u2 is m/s at 2 m; pressures kPa.
        value = (0.408 * delta * (rn - g) + gamma * (900 / (t + 273)) * u2 * (es - ea)) / (delta + gamma * (1 + 0.34 * u2))
    else:
        target, rain = finite(data["target"]), vector(data["rain"])
        if target < 0 or any(v < 0 for v in rain):
            raise InputError("Отрицательные осадки/цель")
        value = max(0, target - sum(rain))
    return {"action": "ANSWER", "answer": f"{value:.6g} {UNITS[tool]}", "numeric": value, "unit": UNITS[tool], "tool": tool}
