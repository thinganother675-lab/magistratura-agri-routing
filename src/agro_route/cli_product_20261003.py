# SPDX-License-Identifier: Apache-2.0
"""Subscription CLI adapters. Product measurements, never raw-model claims.

No shell command construction, API authentication, benchmark gold transport, or
automatic retry. The caller must verify subscription authentication first.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

PRODUCTS = {"claude": "CLAUDE_CODE_PRODUCT_BASELINE", "codex": "CODEX_CLI_PRODUCT_BASELINE"}
# The environment is allowlisted, rather than logging and redacting its values.
ENV_ALLOW = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "USERPROFILE",
             "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)",
             "TEMP", "TMP", "LANG", "LC_ALL", "TZ", "HOMEDRIVE", "HOMEPATH"}
CODEX_DISABLED_FEATURES = ("shell_tool", "unified_exec", "apps", "plugins", "remote_plugin",
    "memories", "hooks", "multi_agent", "multi_agent_v2", "browser_use", "browser_use_external",
    "computer_use", "code_mode_host", "skill_search", "shell_snapshot", "view_image",
    "image_generation", "workspace_dependencies", "goals", "sleep_tool", "tool_suggest")


def subscription_environment(source=None):
    """Keep OS plumbing only; API keys, OAuth env overrides and providers excluded."""
    source = os.environ if source is None else source
    return {key: value for key, value in source.items() if key.upper() in ENV_ALLOW}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def redact_sensitive(text):
    text = re.sub(r'(?i)(Bearer\s+)[A-Za-z0-9._~+/-]+', r'\1[REDACTED]', text)
    text = re.sub(r'\bsk-[A-Za-z0-9_-]{8,}', '[REDACTED]', text)
    return re.sub(r'(?i)(["\']?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password)["\']?\s*[:=]\s*)["\']?[^\s,}"\']+["\']?', r'\1"[REDACTED]"', text)


def build_invocation(product, executable, cwd, system, model, effort):
    cwd = str(Path(cwd).resolve())
    if product == "claude":
        return [str(executable), "--print", "--model", model, "--effort", effort,
            "--tools", "", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
            "--safe-mode", "--restricted", "--disable-slash-commands", "--no-chrome",
            "--permission-mode", "dontAsk", "--permission-prompts", "none",
            "--no-session-persistence", "--output-format", "stream-json", "--verbose",
            "--system-prompt", system]
    if product == "codex":
        args = [str(executable), "exec", "--model", model, "--sandbox", "read-only",
            "--ignore-user-config", "--ignore-rules", "--ephemeral", "--skip-git-repo-check",
            "--cd", cwd, "--json", "--color", "never", "--strict-config",
            "-c", 'forced_login_method="chatgpt"', "-c", 'approval_policy="never"',
            "-c", 'web_search="disabled"', "-c", "project_doc_max_bytes=0",
            "-c", 'project_root_markers=[".benchmark_isolated_root"]',
            "-c", "mcp_servers={}", "-c", "model_reasoning_effort=" + json.dumps(effort),
            "-c", "developer_instructions=" + json.dumps(system, ensure_ascii=False)]
        for feature in CODEX_DISABLED_FEATURES:
            args.extend(["--disable", feature])
        return args + ["-"]
    raise ValueError("Unknown product")


def _events(stdout):
    events = []
    for line in stdout.splitlines():
        if line.strip():
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise ValueError("CLI event must be an object")
            events.append(obj)
    return events


def parse_output(product, stdout):
    events = _events(stdout)
    if product == "claude":
        final = next((e for e in reversed(events) if e.get("type") == "result"), None)
        initial = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
        tool_calls = [b for e in events if e.get("type") == "assistant"
                      for b in e.get("message", {}).get("content", []) if b.get("type") == "tool_use"]
        if final is None:
            raise ValueError("Claude result event missing")
        usage = final.get("usage", {})
        models = sorted(final.get("modelUsage", {}))
        return {"text": final.get("result", ""), "response_received": True,
            "error": {"type": "CLIResultError", "subtype": final.get("subtype")} if final.get("is_error") else None,
            "displayed_model": initial.get("model"), "returned_model_ids": models,
            "input_tokens": usage.get("input_tokens"), "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
            "cache_creation_input_tokens": usage.get("cache_creation_input_tokens"), "output_tokens": usage.get("output_tokens"),
            "reported_client_cost_estimate_usd": final.get("total_cost_usd"),
            "product_api_duration_ms": final.get("duration_api_ms"), "num_turns": final.get("num_turns"),
            "tools_exposed": initial.get("tools"), "mcp_servers_exposed": initial.get("mcp_servers"),
            "tool_calls_n": len(tool_calls), "permission_denials_n": len(final.get("permission_denials", [])),
            "harness_confounded": bool(tool_calls or final.get("permission_denials") or initial.get("tools") or initial.get("mcp_servers"))}
    if product == "codex":
        complete = next((e for e in reversed(events) if e.get("type") == "turn.completed"), None)
        messages = [e.get("item", {}).get("text", "") for e in events
                    if e.get("type") == "item.completed" and e.get("item", {}).get("type") == "agent_message"]
        tool_items = [e for e in events if e.get("type") == "item.completed"
                      and e.get("item", {}).get("type") not in {"agent_message", "reasoning", "error"}]
        # Codex emits recoverable transport warnings as error events. A completed
        # turn after HTTPS fallback is successful; preserve those warnings.
        failed = [e for e in events if e.get("type") == "turn.failed"]
        warnings = [e for e in events if e.get("type") == "error" or
                    (e.get("type") == "item.completed" and e.get("item", {}).get("type") == "error")]
        usage = (complete or {}).get("usage", {})
        return {"text": "\n".join(messages), "response_received": bool(complete),
            "error": {"type": "CLIResultError"} if failed or not complete else None,
            "displayed_model": None, "returned_model_ids": [], "input_tokens": usage.get("input_tokens"),
            "cache_read_input_tokens": usage.get("cached_input_tokens"), "output_tokens": usage.get("output_tokens"),
            "reported_client_cost_estimate_usd": None, "tool_calls_n": len(tool_items),
            "transport_warning_events_n": len(warnings),
            "product_internal_reconnect_events_n": sum("Reconnecting" in e.get("message", "") for e in warnings),
            "tools_exposed": None, "harness_confounded": bool(tool_items),
            "model_identity_limit": "CLI JSONL does not expose backend model ID; successful explicit catalog model selection only"}
    raise ValueError("Unknown product")


@dataclass(frozen=True)
class ProductConfig:
    product: str
    executable: str
    model: str
    effort: str
    cwd: Path
    system: str
    timeout_s: float = 120


def run_request(config, prompt):
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Nonempty text input required")
    if not config.cwd.is_dir() or any(config.cwd.iterdir()):
        raise ValueError("Isolated working directory must be empty")
    invocation = build_invocation(config.product, config.executable, config.cwd, config.system, config.model, config.effort)
    encoded = prompt.encode("utf-8")
    start = time.perf_counter()
    raw = {"invocation": invocation, "prompt": prompt, "prompt_bytes": len(encoded), "prompt_sha256": sha(encoded)}
    try:
        completed = subprocess.run(invocation, input=encoded, capture_output=True,
            cwd=config.cwd, env=subscription_environment(), timeout=config.timeout_s, shell=False)
        raw.update(stdout=redact_sensitive(completed.stdout.decode("utf-8", errors="replace")),
                   stderr=redact_sensitive(completed.stderr.decode("utf-8", errors="replace")), returncode=completed.returncode)
        result = parse_output(config.product, raw["stdout"])
        if completed.returncode and not result.get("error"):
            result["error"] = {"type": "CLIExitError", "returncode": completed.returncode}
    except subprocess.TimeoutExpired:
        # Do not save partial exception output, which might contain auth diagnostics.
        raw.update(stdout="", stderr="", returncode=None)
        result = {"text": "", "response_received": False, "error": {"type": "CLIWallTimeout"}, "harness_confounded": False, "tool_calls_n": 0}
    except (ValueError, json.JSONDecodeError):
        result = {"text": "", "response_received": False, "error": {"type": "CLIOutputParseError"}, "harness_confounded": False, "tool_calls_n": 0}
    result.update(latency_s=time.perf_counter() - start, prompt_bytes=len(encoded), prompt_sha256=sha(encoded),
                  subscription_cost="SUBSCRIPTION_INCLUDED", baseline_class=PRODUCTS[config.product])
    raw["parsed"] = result
    return result, raw
