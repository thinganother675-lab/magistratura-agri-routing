"""Policies never receive gold/category/split fields."""
import re
import time
from .tools import InputError, execute, REQUIRED
from .models import public_request

ALIASES = {"gdd": r"\bgdd\b|сумм\w* эффективн\w* температур|градусо.?дн|growing degree", "vpd": r"\bvpd\b|дефицит давления пара|vapou?r pressure deficit", "et0": r"\bet[₀0o]\b|эталонн\w* эвапотранспирац|reference evapotranspiration", "rain_deficit": r"\brain_deficit\b|дефицит осадков|rainfall deficit|rain deficit"}

def identify_tool(question):
    found = [tool for tool, pattern in ALIASES.items() if re.search(pattern, question.lower())]
    return found[0] if len(found) == 1 else None

def hard_gate(request):
    q, data = request["input"], request.get("inputs", {})
    tool = identify_tool(q)
    if not tool:
        return None
    if not re.search(r"рассчитай|посчитай|вычисли|calculate|compute", q.lower()):
        return None
    # Selection and explanation do not imply execution; no label lookup.
    if re.search(r"только (выбери|назови)|select only|choose only|не (рассчитывай|считай)|do not calculate", q.lower()):
        return None
    try:
        output = execute(tool, data)
        return {"route": "DETERMINISTIC_TOOL", "output": output, "reason": "Явный расчёт; входы и единицы проверены", "tool_calls": 1}
    except InputError as exc:
        return {"route": "ASK_FOR_DATA", "output": {"action": "ASK_FOR_DATA", "answer": str(exc), "numeric": None}, "reason": str(exc), "tool_calls": 0}

def grounded(request, result):
    out = result.get("output")
    if not out or out.get("action") != "ANSWER":
        return False
    # This checks support, NOT correctness. A wrong substring can pass.
    context = request.get("context", "")
    answer = out.get("answer", "").strip()
    return bool(context and len(answer) >= 2 and answer.lower() in context.lower())

def decide(request, method, local, cloud, cloud_available=True, threshold=900):
    start = time.perf_counter()
    tool_ms, local_calls, cloud_calls = 0.0, 0, 0
    traces = []
    if method in ("rule", "cascade", "offline", "tool_cloud"):
        ts = time.perf_counter()
        gate = hard_gate(request)
        tool_ms = (time.perf_counter() - ts) * 1000
        if gate:
            gate.update(latency_ms=tool_ms, cloud_calls=0, local_calls=0, cost_usd=0., trace=[], latency_kind="measured_tool")
            return gate
    if method == "cloud" or method == "tool_cloud" or (method == "rule" and len(request.get("context", "")) + len(request["input"]) > threshold):
        target = "cloud" if cloud_available else "local"
    else:
        target = "local"
    first = local(request) if target == "local" else cloud(request)
    traces.append(first)
    local_calls += target == "local"
    cloud_calls += target == "cloud"
    route = "LOCAL_MODEL" if target == "local" else "CLOUD_MODEL"
    reason = "Фиксированная политика" if method in ("local", "cloud") else "Правило по длине контекста" if method == "rule" else "Локальная попытка и проверка опоры на контекст"
    final = first
    if method in ("cascade", "offline") and not grounded(request, first):
        if cloud_available and method != "offline":
            final = cloud(request)
            cloud_calls += 1
            traces.append(final)
            route = "LOCAL_TO_CLOUD"
        else:
            route = "ABSTAIN"
            final = {"output": {"action": "ABSTAIN", "answer": "Нет проверяемой локальной опоры; облако недоступно", "numeric": None}}
    if final.get("error"):
        route = "ABSTAIN"
        output = {"action": "ABSTAIN", "answer": "Модель недоступна или вернула некорректный ответ", "numeric": None}
    else:
        output = final.get("output")
    costs = [r.get("cost_usd") for r in traces]
    elapsed = (time.perf_counter() - start) * 1000
    return {"route": route, "output": output, "reason": reason, "tool_calls": 0, "local_calls": int(local_calls), "cloud_calls": int(cloud_calls), "cost_usd": sum(costs) if all(v is not None for v in costs) else None, "latency_ms": elapsed, "trace": traces, "latency_kind": "measured_live"}
