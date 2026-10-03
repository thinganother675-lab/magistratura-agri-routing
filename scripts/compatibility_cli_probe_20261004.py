"""One read-only supported Claude CLI compatibility check, no model request."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agro_route.cli_product_20261003 import subscription_environment


def main():
    target = ROOT / "results/20261004_session/claude_cli_compatibility.json"
    if target.exists():
        raise RuntimeError("Read-only compatibility receipt already exists; no automatic retry")
    receipt = {"started_utc": datetime.now(timezone.utc).isoformat(), "scope": "CLI version and supported auth status only", "model_requests": 0, "DEV_requests": 0, "new_paid_api_calls": 0, "historical_inference_status": "403 authentication probes; no benchmark output", "inference_endpoint_rechecked": False}
    executable = shutil.which("claude")
    if not executable:
        receipt["status"] = "CLI_UNAVAILABLE"
    else:
        env = subscription_environment()
        try:
            version = subprocess.run([executable, "--version"], capture_output=True, env=env, timeout=15)
            match = re.search(rb"\b\d+\.\d+\.\d+\b", version.stdout)
            receipt["cli_version"] = match.group().decode("ascii") if match else None
            probe = subprocess.run([executable, "auth", "status", "--json"], capture_output=True, env=env, timeout=20)
            data = json.loads(probe.stdout)
            allowed = {"authMethod": {"claude.ai", "api_key", "none"}, "apiProvider": {"firstParty", "first-party", "anthropic", "bedrock", "vertex"}, "subscriptionType": {"pro", "max", "team", "enterprise"}}
            receipt["logged_in"] = data.get("loggedIn") if type(data.get("loggedIn")) is bool else None
            for name, choices in allowed.items():
                receipt[name] = data.get(name) if data.get(name) in choices else "UNRECOGNIZED_OR_UNAVAILABLE"
            receipt["auth_status_exit"] = probe.returncode
            receipt["status"] = "SUPPORTED_STATUS_READ_NO_INFERENCE"
        except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
            receipt.update(status="STATUS_CHECK_BLOCKED", error_type=type(exc).__name__)
    receipt["finished_utc"] = datetime.now(timezone.utc).isoformat()
    receipt["credential_values_or_personal_account_fields_persisted"] = False
    with target.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
