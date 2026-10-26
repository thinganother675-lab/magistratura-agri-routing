"""Host test receipt with configured credentials redacted before persistence."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from scan_public_artifacts import configured_secret_values

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/20261004_session"


def main():
    start = datetime.now(timezone.utc).isoformat()
    cmd = [str(ROOT / ".venv/Scripts/python.exe"), "-X", "utf8", "-m", "pytest", "-q", "--basetemp=.runtime/session_20261004/pytest_final_host"]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    log = p.stdout + p.stderr
    for value in configured_secret_values(ROOT):
        log = log.replace(value, "[REDACTED_CONFIGURED_SECRET]")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "final_tests.txt").write_text(log, encoding="utf-8")
    lines = [s for s in log.splitlines() if " passed" in s or " failed" in s or "ERROR " in s or s.startswith("FAILED ")]
    receipt = {"started_utc": start, "finished_utc": datetime.now(timezone.utc).isoformat(), "exit_code": p.returncode, "command": ".venv/Scripts/python.exe -X utf8 -m pytest -q --basetemp=.runtime/session_20261004/pytest_final_host", "environment": "Windows host; sandbox tempfile ACL failures bypassed by authorized elevated execution", "summary": lines[-8:], "log": "results/20261004_session/final_tests.txt", "configured_secrets_redacted": True}
    (OUT / "final_tests.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))
    raise SystemExit(p.returncode)


if __name__ == "__main__":
    main()
