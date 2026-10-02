"""Non-secret setup and isolated-window continuation checkpoint."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
metadata=ROOT/'results/20261002_182916Z_ef105dbe_openrouter21_metadata'
setup=json.loads((OUT/'setup_summary.json').read_text(encoding='utf-8'))
manifest=json.loads((metadata/'manifest.json').read_text(encoding='utf-8'))
checkpoint={
 'created_utc':datetime.now(timezone.utc).isoformat(),
 'status':'CHILD_READY_METADATA_ONLY_WAITING_EXCLUSIVE_WINDOW',
 'original_failed_screen':'results/20261002_181544Z_454d35c7_openrouter21_screen',
 'original_generation_attempts_preserved':1,
 'setup_status':setup['status'],
 'management_credential_source':'project_env:openrouter_api_key_2',
 'inference_credential_source':'project_env:OPENROUTER_INFERENCE_KEY_ZERO_20261002',
 'paid_spend_cap_usd':0,
 'child_inference_type_verified':setup['regular_inference_type_verified'],
 'child_limit_zero_verified':setup['zero_cap_verified'],
 'child_limit_zero_free_generations_supported':'UNKNOWN UNTIL FIRST FREE COMPLETION',
 'account_global_daily_free_quota':manifest['rows'] and setup['child_key']['free_model_daily_requests'],
 'no_quota_refresh_account_or_key_rotation':True,
 'privacy_settings_changed':False,
 'generation_attempts_setup_and_new_metadata':0,
 'total_external_requests_branch_to_checkpoint':51+setup['metadata_requests']+setup['setup_mutations']+manifest['metadata_requests_n'],
 'fresh_metadata_directory':metadata.relative_to(ROOT).as_posix(),
 'fresh_metadata_manifest_sha256':hashlib.sha256((metadata/'manifest.json').read_bytes()).hexdigest(),
 'current_driver_sha256':hashlib.sha256((ROOT/'scripts/openrouter_screen_20261002.py').read_bytes()).hexdigest(),
 'tests_passed':23,
 'planned_max_generations_new_trial':46,
 'session_generation_attempt_guard':49,
 'resume_command_after_root_grants_exclusive_window':'.venv\\Scripts\\python.exe scripts\\openrouter_screen_20261002.py --execute --credential-source zero_child --metadata-dir results\\20261002_182916Z_ef105dbe_openrouter21_metadata --measurement-window <NEW_ROOT_GRANTED_WINDOW>',
 'blockers':['A new exclusive measurement window is required while downloads/builds are active.',
             'The provider has not yet demonstrated that limit=0 permits zero-price completion. Do not raise the cap if blocked.'],
}
(OUT/'checkpoint.json').write_text(json.dumps(checkpoint,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
doc=ROOT/'docs/OPENROUTER_SCREEN_20261002_RU.md'
append='''

## Исправление аутентификации без платного лимита (18:29 UTC)

В рамках разрешённой настройки создан **один** обычный ключ inference в том же аккаунте через официальный `POST /api/v1/keys` (HTTP 201). Исходный management-ключ `openrouter_api_key_2` оставлен без изменений. Новый ключ находится только в игнорируемом Git проектном `.env`, переменная `OPENROUTER_INFERENCE_KEY_ZERO_20261002`; значения, префиксы и отпечатки ключей в артефакты не записаны.

Проверка `GET /api/v1/key` подтвердила `is_management_key=false`, `is_provisioning_key=false`, `limit=0`, `limit_remaining=0`, `include_byok_in_limit=true`. Срок действия — до 09.10.2026 23:59:59 UTC, сброс денежного лимита отключён. Общая бесплатная квота аккаунта осталась 50/50, использовано 0: создание ключа не формирует новую квоту. Генераций после настройки пока **NOT RUN**; допускает ли сервис бесплатную генерацию при `limit=0`, ещё не проверено. При отказе лимит не будет повышаться.

Путь доказательств: `results/20261002_182623Z_openrouter_zero_child_setup/setup_summary.json`; свежий каталог всех 21 позиций: `results/20261002_182916Z_ef105dbe_openrouter21_metadata/manifest.json`. 18 текстовых моделей допущены по явным нулевым ценам всех опубликованных компонентов и закреплённому endpoint. Две Lyria исключены из-за цены за музыкальный результат, Content Safety — из общей генеративной оценки. **23** профильных теста проходят.

Исходный эксперимент с одним HTTP 401 неизменен; его исходный код дополнительно сохранён как `driver_original.py` с совпадающим SHA256. Будущий запуск будет новым каталогом/claim/журналом, а не повторной записью старого результата. До checkpoint выполнено **78** внешних запросов всей ветки: 1 неуспешный generative POST, 1 setup POST и 76 metadata GET. Оплата отдельных неуспешных запросов UNKNOWN; аккаунтные снимки usage=0. Новых платных генераций не разрешено.

Точная команда продолжения после нового изолированного окна указана в `results/20261002_182623Z_openrouter_zero_child_setup/checkpoint.json`. Параметры, набор DEV и правила бесплатного теста сохранены. [Создание ключа](https://openrouter.ai/docs/api/api-reference/api-keys/create-a-new-api-key), [тип management-ключа](https://openrouter.ai/docs/guides/overview/auth/management-api-keys), [общие ограничения](https://openrouter.ai/docs/api/reference/limits).
'''
with doc.open('a',encoding='utf-8') as handle:
    handle.write(append)
print(json.dumps({'checkpoint':(OUT/'checkpoint.json').relative_to(ROOT).as_posix(),
                  'status':checkpoint['status'],'external_requests':checkpoint['total_external_requests_branch_to_checkpoint']}))
