"""Reuse the existing MVP with authenticated HOME providers and HOME routing.

This demonstrator never downloads or loads a model. Load the documented model
instance explicitly; absent/changed instances cause graceful provider blocking.
Cloud is disabled unless CLOUD_AVAILABLE=true before launching the process.
No demo query is added to the frozen scientific result directories.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

import httpx
from agro_route import web
from agro_route.home_config import resolve_api_key

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_home_final as final

ROOT = Path(__file__).resolve().parents[1]
LEGACY_DECIDE = web.decide


class HomeLocal:
    model = final.LOCAL['model']

    def __init__(self, key, instance):
        self.key, self.instance = key, instance

    def call(self, request):
        if not self.key:
            raise final.ProviderBlocked('local', 'local_credential_missing')
        try:
            available = final.home.resource_headroom()
        except (RuntimeError, OSError, ValueError) as exc:
            raise final.ProviderBlocked('local', 'resource_guard_' + type(exc).__name__) from None
        if available['ram_available_gib'] < 2 or available['gpu_free_mib'] < 512:
            raise final.ProviderBlocked('local', {'type': 'resource_guard', **available})
        with httpx.Client(timeout=60, trust_env=False) as client:
            try:
                catalog = final.api.native_models(client, self.key)
            except (httpx.HTTPError, RuntimeError, ValueError) as exc:
                raise final.ProviderBlocked('local', type(exc).__name__) from None
            matches = [(model, instance) for model in catalog for instance in model.get('loaded_instances', [])
                       if instance.get('id') == self.instance and model.get('key') == self.model]
            if len(matches) != 1:
                raise final.ProviderBlocked('local', 'documented_demo_instance_not_loaded')
            model, instance = matches[0]
            config = instance.get('config') or {}
            if model.get('quantization', {}).get('name') != final.LOCAL['quantization'] or config.get('context_length') != 4096 or config.get('parallel') != 1:
                raise final.ProviderBlocked('local', 'demo_model_configuration_mismatch')
            return {**final.api.api_call(client, self.key, self.instance, request, 'none'),
                    'provider': 'local', 'model': self.model}


class HomeCloud:
    model = final.CLOUD['model']

    def __init__(self, key):
        self.key = key
        self.provider = final.Model(final.CLOUD['base_url'], self.model, key, .04, .15, timeout=60)

    def call(self, request):
        if not self.key:
            raise final.ProviderBlocked('cloud', 'cloud_credential_missing')
        return final.strict_cloud_record(self.provider.call(request))


REASONS = {
    'DETERMINISTIC_TOOL': 'Входы проверены; результат вычислен детерминированным инструментом.',
    'ASK_FOR_DATA': 'Обязательные входы или единицы отсутствуют либо некорректны.',
    'LOCAL_MODEL': 'Локальная модель ответила; для каскада проверена буквальная опора на контекст.',
    'LOCAL_TO_CLOUD': 'Локальный ответ не прошёл проверку опоры; запрос передан облаку.',
    'CLOUD_MODEL': 'Выбрана облачная политика либо отсутствует проверяемая локальная опора.',
    'ABSTAIN': 'Облако выключено, а проверяемой локальной опоры для ответа нет.',
    'NOT_RUN': 'Выбранный провайдер сейчас недоступен; запрос к нему не выполнен.'}


def demo_decide(request, method, local, cloud, enabled, threshold):
    if method == 'rule':
        return LEGACY_DECIDE(request, method, local, cloud, enabled, threshold)
    selected = 'hybrid' if method == 'cascade' else method
    if not enabled and selected in ('cloud', 'tool_cloud', 'hybrid'):
        selected = 'offline'
    result = final.measured_decision(request, selected, local, cloud)
    result['reason'] = REASONS.get(result['route'], 'Маршрут записан в измерениях.')
    result['demo_policy'] = selected
    result['experiment_record'] = False
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8090)
    parser.add_argument('--model-instance', default='home-demo-gemma26')
    args = parser.parse_args()
    local_key, _ = resolve_api_key('local', env_path=ROOT / '.env')
    cloud_key, _ = resolve_api_key('mercury', env_path=ROOT / '.env')
    local, cloud = HomeLocal(local_key, args.model_instance), HomeCloud(cloud_key)
    # Scoped process-only adapters; frozen source files are unchanged.
    web.configured_models = lambda: (local, cloud)
    web.decide = demo_decide
    web.serve(args.port)


if __name__ == '__main__':
    main()
