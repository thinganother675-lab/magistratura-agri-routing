"""Run the full suite and retain a UTF-8, credential-redacted receipt."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from scan_public_artifacts import configured_secret_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    label = sys.argv[1] if len(sys.argv) == 2 else "final"
    if not re.fullmatch(r"[a-z0-9_]+", label):
        raise ValueError("Safe receipt label required")
    directory = ROOT / "results/20261003_resource_session"
    text_path = directory / ("pytest_" + label + ".txt")
    json_path = directory / ("tests_" + label + ".json")
    if text_path.exists() or json_path.exists():
        raise ValueError("Test receipts are append-only; use a new label")
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT,
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    transcript = result.stdout + result.stderr
    for secret in configured_secret_values(ROOT):
        transcript = transcript.replace(secret, "[REDACTED]")
    text_path.write_text(transcript, encoding="utf-8")
    counts = {key: 0 for key in ("passed", "failed", "skipped", "errors")}
    summary = next((line for line in reversed(transcript.splitlines())
                    if re.search(r"\d+ passed|\d+ failed|\d+ error", line)), "")
    for count, kind in re.findall(r"(\d+) (passed|failed|skipped|errors?)", summary):
        counts["errors" if kind.startswith("error") else kind] = int(count)
    receipt = {"start_utc": started, "end_utc": datetime.now(timezone.utc).isoformat(),
               "exit_code": result.returncode, "counts": counts,
               "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
               "scope": "full pytest suite against current working-tree bytes; commit is parent/assembly HEAD",
               "transcript": text_path.relative_to(ROOT).as_posix(),
               "transcript_sha256": hashlib.sha256(text_path.read_bytes()).hexdigest(),
               "private_test_run": False}
    json_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"receipt": json_path.relative_to(ROOT).as_posix(), "exit_code": result.returncode,
                      "counts": counts}))
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
