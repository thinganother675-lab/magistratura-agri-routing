# SPDX-License-Identifier: Apache-2.0
"""Safe aggregate CLI evidence; never publish question/reference/provider text."""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agro_route.cli_product_20261003 import parse_output, sha
from agro_route.mera_screen_metrics_20261003 import set_score, summarize

SAFE = ROOT / "results/20261003_cli_products"
RESTRICTED = ROOT / ".runtime/cli_products"
SOURCES = [
    {"url": "https://code.claude.com/docs/en/cli-reference", "supports": "-p, tools empty, strict MCP, safe-mode, JSON/stream JSON, system prompt"},
    {"url": "https://code.claude.com/docs/en/model-config", "supports": "Sonnet5.5 alias, installed version minimum, effort medium; adaptive reasoning cannot be disabled"},
    {"url": "https://code.claude.com/docs/en/headless", "supports": "programmatic print usage; client-side cost estimates are not invoice"},
    {"url": "https://learn.chatgpt.com/docs/developer-commands?surface=cli", "supports": "exec, model flag, JSONL, ephemeral, ignore-user-config"},
    {"url": "https://learn.chatgpt.com/docs/auth", "supports": "ChatGPT subscription authentication vs API-key metered usage; login status"},
    {"url": "https://learn.chatgpt.com/docs/config-file/config-basic", "supports": "web_search disabled, feature shell_tool/apps/memory/hooks toggles"},
    {"url": "https://learn.chatgpt.com/docs/config-file/config-reference", "supports": "project_doc_max_bytes, developer_instructions; reserved built-in provider IDs cannot be overridden"},
]


def write_new(path, obj):
    with path.open("x", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2); f.write("\n")


def main():
    baseline = json.loads((SAFE / "codex_dev60_manifest.json").read_text(encoding="utf-8"))
    rows = [json.loads(s) for s in (SAFE / "codex_dev60_metrics.jsonl").read_text(encoding="utf-8").splitlines()]
    if sha((SAFE / "codex_dev60_metrics.jsonl").read_bytes()) != baseline["metrics_sha256"]:
        raise ValueError("Metrics changed")
    primary = ROOT / "results/20261003_cloud_budget_only_c1184a27/cloud_development_analysis.json"
    mercury = json.loads(primary.read_text(encoding="utf-8"))
    # Append-only correction of the first escalated synthetic probe. Original raw
    # and misclassified metrics stay intact for audit; it is not benchmark data.
    original = json.loads((RESTRICTED / "codex_probe_unrestricted_raw.jsonl").read_text(encoding="utf-8").splitlines()[0])
    corrected = parse_output("codex", original["stdout"])
    corrected_score = set_score("A", corrected.pop("text"), "ABCD")
    overlay = {"status": "SUPPLEMENTARY", "reason": "recoverable warning events are not tool calls or failed completed turns",
        "parent_raw_sha256": sha((RESTRICTED / "codex_probe_unrestricted_raw.jsonl").read_bytes()),
        "corrected_result": {**corrected, **corrected_score}, "preserved_original": True}
    if not (SAFE / "codex_first_probe_correction.json").exists():
        write_new(SAFE / "codex_first_probe_correction.json", overlay)
    selection = {"selected_model": "gpt-6-luna", "display_name": "GPT-6-Luna",
        "catalog_provenance": "installed Codex models_cache.json selective noncredential fields inspected20261003; visible list entry",
        "effort": "medium", "access_verified_by": "four successful subscription-backed explicit-model CLI completions then DEV60",
        "actual_backend_model_id": None, "limitation": "CLI JSONL does not expose backend model identity or weight revision"}
    result = {"run_id": "20261003_cli_products", "status": "SUPPLEMENTARY", "private_test_run": False,
        "MERA_submissions": 0, "cost_class": "SUBSCRIPTION_INCLUDED", "no_api_keys_forwarded": True,
        "no_api_credit_purchase": True, "claude": {"baseline_class": "CLAUDE_CODE_PRODUCT_BASELINE",
            "status": "NOT_RUN_AUTHENTICATION_403", "cli_version": "2.1.288", "displayed_model": "claude-sonnet-5-5",
            "selected_effort": "medium", "auth_method": "claude.ai", "subscription": "pro",
            "tools_exposed": [], "mcp_exposed": [], "synthetic_attempts": 2, "synthetic_completed": 0,
            "dev60_attempts": 0, "accuracy": None, "usage_reported": 0, "no_opus_substitution": True},
        "codex": {"baseline_class": "CODEX_CLI_PRODUCT_BASELINE", "cli_version": "0.160.0",
            "execution_status": baseline["execution_status"], "model_selection": selection,
            "summary": summarize(rows, baseline["expected_ids"]),
            "tool_calls_n": sum(r["tool_calls_n"] for r in rows),
            "harness_confounded": any(r["harness_confounded"] for r in rows),
            "transport_warning_events_n": sum(r.get("transport_warning_events_n", 0) for r in rows),
            "product_internal_reconnect_events_n": sum(r.get("product_internal_reconnect_events_n", 0) for r in rows),
            "cache_read_input_tokens": sum(r.get("cache_read_input_tokens") or 0 for r in rows),
            "model_backend_identity": "NOT_EXPOSED", "TTFT": None, "generation_tps": None,
            "json_contract_success_n": sum(r["json_contract"] for r in rows),
            "json_contract_enforced_by_product": False,
            "latency_scope": "new CLI process end-to-end; includes transport recovery; no direct local-backend latency comparison"},
        "primary_scientific_cloud_baseline_recommendation": "Mercury2.5 direct remains PROVISIONAL_DEV_REFERENCE_NOT_PRIVATE_TEST_READY",
        "reason_primary": "direct documented API parameters, explicit response model; keep product harness context/effort/cache/transport distinct",
        "mercury_parent_data": str(primary.relative_to(ROOT)).replace("\\", "/"),
        "mercury_parent_sha256": sha(primary.read_bytes()),
        "scientific_limits": ["public DEV60 model-selection supplement; no confirmatory claim", "subscription cost is not zero inference cost",
            "default product system/harness context persists despite repository isolation", "CLI tools absent/disabled where supported and zero observed; hidden harness behavior remains",
            "effort and output budgeting differ from local models/direct Mercury", "provider hidden training contamination UNKNOWN",
            "Codex requested model selection verified operationally, backend returned model ID not exposed"],
        "official_documentation": SOURCES, "documentation_checked_date": "2026-10-03"}
    target = SAFE / "cli_products_analysis.json"
    write_new(target, result)
    compact = {"status": "SUPPLEMENTARY", "run_id": result["run_id"], "private_test_run": False,
        "subscription_cost": "SUBSCRIPTION_INCLUDED", "paid_api_keys_forwarded": False,
        "codex": {"version": "0.160.0", "selected_model": "gpt-6-luna", "selected_effort": "medium",
            "authentication": "ChatGPT", "attempted": len(rows), "completed": result["codex"]["summary"]["n_completed"],
            "EM": result["codex"]["summary"]["strict_set_em"], "F1": result["codex"]["summary"]["strict_set_f1"],
            "EM_count": result["codex"]["summary"]["strict_em_count"], "strict_denominator": result["codex"]["summary"]["n_scored"],
            "invalid_option_sets": result["codex"]["summary"]["invalid_output"],
            "strict_JSON_contract_failures": result["codex"]["summary"]["json_contract_failure"],
            "p50_s": result["codex"]["summary"]["latency_p50_s"], "p95_s": result["codex"]["summary"]["latency_p95_s"],
            "input_tokens": result["codex"]["summary"]["input_tokens"], "output_tokens": result["codex"]["summary"]["output_tokens"],
            "observed_tool_calls": result["codex"]["tool_calls_n"], "returned_backend_model_id": None},
        "claude": result["claude"], "primary_cloud_recommendation": result["primary_scientific_cloud_baseline_recommendation"],
        "source_analysis": str(target.relative_to(ROOT)).replace("\\", "/"), "source_analysis_sha256": sha(target.read_bytes()),
        "official_sources": [s["url"] for s in SOURCES], "limitations": result["scientific_limits"],
        "invocation_receipt": "results/20261003_cli_products/codex_dev60_plan_frozen.json",
        "invocation_flags": ["exec", "--model gpt-6-luna", "--sandbox read-only", "--ignore-user-config", "--ignore-rules",
            "--ephemeral", "--skip-git-repo-check", "--json", "--color never", "--strict-config", "web_search=disabled",
            "forced_login_method=chatgpt", "project_doc_max_bytes=0", "mcp_servers={}"
        ], "benchmark_content_in_this_summary": False}
    write_new(SAFE / "summary.json", compact)
    claims = []
    for field in ("strict_set_em", "strict_set_f1", "n_attempted", "n_completed", "invalid_output", "latency_p50_s", "latency_p95_s", "input_tokens", "output_tokens"):
        claims.append({"claim_id": "codex_cli_dev60_" + field,
            "statement": "Supplementary Codex CLI GPT-6-Luna medium product DEV60: " + field,
            "study_run_id": result["run_id"], "data_path": str(target.relative_to(ROOT)).replace("\\", "/"),
            "analysis_field": "/codex/summary/" + field, "value": result["codex"]["summary"][field],
            "code_commit": baseline["code_commit_before_changes"], "code_identity_note": "parent commit; exact executed worktree source hashes/snapshots in frozen DEV60 plan",
            "data_sha256": sha(target.read_bytes()), "status": "SUPPLEMENTARY"})
    write_new(SAFE / "claims_for_integration.json", {"claims": claims})
    s = result["codex"]["summary"]
    report = f'''# Подписочные CLI: дополнительные продуктовые базовые линии

3 октября 2026. **SUPPLEMENTARY, только публичный DEV.** Частный TEST и MERA submissions не запускались. Новые API-ключи и покупки API-кредитов отсутствуют. Цена классифицирована как **SUBSCRIPTION_INCLUDED**; ежемесячная подписка имеет стоимость, поэтому «бесплатная инференция» не заявляется.

**Codex CLI GPT-6-Luna / medium: {s['strict_em_count']}/{s['n_scored']} STRICT_SET_EM = {s['strict_set_em']:.6f}, STRICT_SET_F1 = {s['strict_set_f1']:.6f}. Claude Code Sonnet 5.5: DEV60 не запускался из-за подтверждённой ошибки авторизации HTTP403 до генерации.** Результаты не являются официальными метриками MERA и не сравнивают чистые модели API.

| Конфигурация | Попытки DEV / завершено | EM / F1 | Invalid sets / JSON failures | p50 / p95, с | Input / output tokens |
|---|---:|---:|---:|---:|---:|
| CODEX_CLI_PRODUCT_BASELINE,0.160.0, selected GPT-6-Luna,medium | {s['n_attempted']} / {s['n_completed']} | {s['strict_set_em']:.6f} / {s['strict_set_f1']:.6f} | {s['invalid_output']} / {s['json_contract_failure']} | {s['latency_p50_s']:.3f} / {s['latency_p95_s']:.3f} | {s['input_tokens']} / {s['output_tokens']} |
| CLAUDE_CODE_PRODUCT_BASELINE,2.1.288,Sonnet5.5,medium | 0 /0 | UNKNOWN | N/A | N/A | inference0 |

Общий неизменный DEV60 взят тем же reference-free selector, source SHA `{baseline['dev_source_sha256']}`. Исходный неоднозначный reference остаётся исключённым из strict denominator; conservative all-N EM = {s['conservative_all_n_em']:.6f}. Формат нормализован только презентационно, без извлечения ответа из прозы и без исправления содержания. Все60 option sets валидны, но строгий JSON-контракт соблюдён только{result['codex']['json_contract_success_n']}/60: в46 ответах формат представляет буквенный набор без JSON. Structured schema в CLI не навязывалась; local/direct API использовали response schema, это записанное различие условий. В CLI передаётся только исходный вопрос и прежняя русская инструкция JSON choices; labels передаются только локальному scorer после завершения ответа. Запросы/ответы и stdout/stderr сохранены в ignored `.runtime/cli_products`, в Git — метрики без текста вопросов и ответов.

Рабочий каталог пустой, новые процессы независимы и не возобновляют предыдущие беседы. Claude использует `--tools ""`, strict empty MCP, safe-mode, restricted, disabled slash commands, no Chrome, dontAsk и no-session-persistence. `--bare` сознательно не используется: установленная помощь указывает API-key-only auth вместо OAuth. [Официальная CLI reference](https://code.claude.com/docs/en/cli-reference) подтверждает режим `-p` и отключение built-in tools; [model configuration](https://code.claude.com/docs/en/model-config) подтверждает Sonnet5.5 и medium effort. Sonnet требует v2.1.284+, установленная2.1.288 подходит. Thinking Sonnet5.5 не выключается, поэтому фиксирован medium.

Claude `auth status` подтверждает claude.ai/Pro/firstParty; оба init показывают `claude-sonnet-5-5`, tools=[],MCP=[],skills=[],apiKeySource=none. Первый запуск внутри песочницы и один повтор вне неё получают `authentication_failed`,HTTP403,usage0. Это operational blocker, а не нулевая агрономическая точность. Происхождение403 не установлено; планы/авторизация не изменялись, Opus не подставлялся, платный API не пробовался.

Codex `login status` подтверждает ChatGPT; официальный [раздел authentication](https://learn.chatgpt.com/docs/auth) различает подписку и API-key billing. Локальный каталог содержит visible `gpt-6-luna`,medium поддержан, явный выбор прошёл4/4 синтетические проверки перед DEV60. Официальный [non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode) и установленный `exec --help` подтверждают exec/JSONL/ephemeral. User config/rules/AGENTS отключены; forced_login_method=chatgpt,web_search=disabled,empty MCP,features shell/apps/plugins/memories/hooks/subagents/browser/computer-use отключены. Эти переключатели описаны в [config basics](https://learn.chatgpt.com/docs/config-file/config-basic) и [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference). API-key/provider/secret environment не наследуется; allowlist оставляет только системное окружение Windows. Значения credentials не читаются и не сохраняются адаптером.

Наблюдаемых вызовов инструментов в DEV60: **{result['codex']['tool_calls_n']}**. JSONL не раскрывает полный список внутренних tool schemas, backend model ID и weight revision; поэтому сохранён selected model, а returned backend ID — UNKNOWN. Скрытый product harness и его system context остаются. Product input tokens включают около8 тысяч системных/служебных токенов на новый процесс плюс вопрос; значения нельзя приравнивать к токенам raw API. Cache-read input: {result['codex']['cache_read_input_tokens']}; суммарный input уже включает cached, его повторно не складывают. TTFT и generation tok/s UNKNOWN. Времена измерены monotonic wall clock от запуска процесса до его завершения.

WebSocket получает403 и штатный CLI выполняет переход на HTTPS. Наблюдалось {result['codex']['product_internal_reconnect_events_n']} reconnect events и {result['codex']['transport_warning_events_n']} warning/error events при успешных completed turns. Эти события не являются tool calls и не превращают завершённый HTTPS-ответ в неудачу. Начальная версия parser ошибочно классифицировала два warning items; raw/старые метрики сохранены, append-only `codex_first_probe_correction.json` исправляет только один синтетический probe. Добавлен тест recovered transport. Попытка override `model_providers.openai.supports_websockets=false` отвергнута CLI как reserved built-in provider, inference0; профиль возвращён к штатному fallback. Latency включает эту инфраструктурную задержку; её нельзя приписывать скорости модели или ставить рядом с warm LM Studio latency без пояснения.

**Primary scientific cloud reference остаётся Mercury2.5 direct,PROVISIONAL_DEV_REFERENCE_NOT_PRIVATE_TEST_READY.** Его existing DEV60:31/59 EM=.525424,F1=.657627,56/60 error-free,4 length failures. Параметры API и returned model яснее, но output budget/temperature/hidden reasoning и неустранённые failures ограничивают перенос на TEST. Codex — полезный дополнительный end-user product comparison; Claude пока NOT_RUN_AUTHENTICATION_403. Смешивать их условия, считать подписочную стоимость$0, выбирать cloud по DEV accuracy или объявлять confirmatory superiority нельзя.

Основной machine-readable результат: `results/20261003_cli_products/cli_products_analysis.json`; frozen plan,manifest,metrics,executed source snapshots и claim pointers рядом. Точные invocation templates, supplied prompt bytes/SHA,UTC start/end,usage,latency и raw hashes сохранены. Никаких статей/релизов/публичных submissions этот workstream не создаёт.
'''
    (ROOT / "docs/CLI_PRODUCT_BASELINES_20261003_RU.md").write_text(report, encoding="utf-8")
    print(json.dumps({"analysis": str(target), "codex_summary": s, "claude_status": result["claude"]["status"]}))


if __name__ == "__main__":
    main()
