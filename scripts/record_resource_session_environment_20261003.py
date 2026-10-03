"""Record versions and baseline counts without process arguments or credentials."""
from pathlib import Path
import json
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def run():
    # Verified active LM Studio executable, read-only version metadata.
    info = subprocess.check_output([
        "powershell", "-NoProfile", "-Command",
        "$i=(Get-Item -LiteralPath 'C:\\sarychev\\LM_Studio\\LM Studio\\LM Studio.exe').VersionInfo;"
        "[pscustomobject]@{FileVersion=$i.FileVersion;ProductVersion=$i.ProductVersion}|ConvertTo-Json",
    ], text=True)
    runtime = subprocess.check_output(["lms", "runtime", "ls"], text=True)
    selected = [line.strip() for line in runtime.splitlines() if "2.51.0" in line]
    receipt = {
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "lm_studio": json.loads(info),
        "global_runtime_listing_selected": selected,
        "runtime_scope": "global selected runtime; per-model engine build UNKNOWN",
        "baseline_head": "6c496744107001d523c2311f236a61a5e14b93c2",
        "baseline_full_suite": {"passed": 632, "failed": 1, "failure": "stale maintainer-letter co-signature assertion after author edited own letter", "receipt": "results/20261003_resource_session/pytest_baseline_unsandboxed.txt"},
        "sandbox_test_attempts": "Windows temporary-directory ACL errors; rerun full suite using authorized elevated local execution",
        "private_test_run": False,
        "mera_server_scorer": "WAITING_FOR_MAINTAINER",
        "maintainer_contact": "SENT_BY_AUTHOR_REPORTED; no duplicate sent; no independently observed reply",
        "new_paid_api_spend_usd": 0,
        "subscription_billing_label": "SUBSCRIPTION_INCLUDED",
        "energy": "NOT_ESTIMATED",
        "host_background": "ordinary desktop apps; subscription CLI calls overlapped local run; no downloads/heavy parallel GPU computation launched",
    }
    target = ROOT / "results/20261003_resource_session/environment_and_baseline.json"
    with target.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"receipt": str(target.relative_to(ROOT)), "lm_studio": receipt["lm_studio"]}))


if __name__ == "__main__":
    run()
