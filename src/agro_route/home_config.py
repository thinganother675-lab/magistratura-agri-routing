"""HOME-only credential aliases; no environment mutation or secret logging.

Historical configured_models() and its frozen environment contract stay intact.
Only names in this explicit allowlist are read from the project .env. Returned
values are for internal HTTP authentication; only the source name is metadata.
"""
from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEY_NAMES = {
    "local": ("LOCAL_API_KEY", "LM_API_TOKEN", "lm_api_token", "local_api_key"),
    "mercury": ("CLOUD_API_KEY", "mercury_api_key", "MERCURY_API_KEY", "INCEPTION_API_KEY"),
    "openrouter": ("OPENROUTER_API_KEY", "openrouter_api_key"),
    "jev": ("JEV_API_KEY", "jev_api_key"),
}
ALLOWED_NAMES = frozenset(name for names in KEY_NAMES.values() for name in names)


def parse_allowlisted_env(text: str) -> dict[str, str]:
    values = {}
    for line in text.splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip()
        if name not in ALLOWED_NAMES:
            continue
        if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
            value = value[1:-1].strip()
        values[name] = value
    return values


def resolve_from_sources(provider: str, process: Mapping[str, str],
                         project: Mapping[str, str]) -> tuple[str, str | None]:
    """Canonical nonempty key wins; aliases follow in allowlist order.

    For each name a nonempty process value wins over its project-file value.
    Missing credentials return an empty internal value and source None.
    """
    if provider not in KEY_NAMES:
        raise ValueError("Unknown credential provider")
    for name in KEY_NAMES[provider]:
        for source, values in (("process", process), ("project_env", project)):
            value = values.get(name, "").strip()
            if value:
                if "\r" in value or "\n" in value:
                    raise ValueError("Credential contains an invalid line break")
                return value, f"{source}:{name}"
    return "", None


def resolve_api_key(provider: str, *, env_path: Path | None = None,
                    environ: Mapping[str, str] | None = None) -> tuple[str, str | None]:
    path = ROOT / ".env" if env_path is None else Path(env_path)
    project = parse_allowlisted_env(path.read_text(encoding="utf-8-sig")) if path.is_file() else {}
    return resolve_from_sources(provider, os.environ if environ is None else environ, project)
