# SPDX-License-Identifier: Apache-2.0
"""Read public source metadata and execute exact fetched metric function ASTs.

No benchmark question, inference, TEST input, upload, authentication, or hidden
answer is accessed. Original source files stay in ignored .cache. This does not
identify the scorer deployed by MERA's private evaluation service.
"""
from __future__ import annotations

import argparse
import ast
import collections
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import string
import subprocess
from types import SimpleNamespace
from typing import Any, Dict, List
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REPO = "MERA-Evaluation/MERA_Industrial"
PIN = "7752f19d1658ba80f5f34144895c26dd1bf5239d"
SQUAD_VERSION = "v4.57.1"
PIN_UTILS_SHA = "01cd4e52ebc32548a1208d2c16ad9c204bd552d676c45a588df084a52c059f5e"
# HTTP raw source is LF. The older cache used CRLF (hash 2246241f...);
# this hash pins the newly downloaded bytes without newline rewriting.
PIN_SQUAD_SHA = "fff72374f535aadddb8e75eade4e820b6fe9ff90f16d4f29e88e442f8d2e9eb8"
SYNTHETIC_CASES = (
    ("A", ""), ("A", "A"), ("A, C", "C"), ("A,C", "C"),
    ("A, C", "A,C"), ("A,C", "A,C"), ("B, C", "C, B"),
    ("B, C", "B,C"), ("А", "A"), ("A, C", "A, C"), ("", "A"),
)


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def extract_functions(source: str, names: set[str], namespace: dict) -> dict:
    """Compile unchanged original function nodes, skipping unrelated imports.

    Narrow extraction avoids importing full remote harness/model packages and
    cannot execute module-level initialization. Bodies are not rewritten.
    """
    tree = ast.parse(source)
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name in names]
    if {node.name for node in selected} != names:
        raise ValueError("Expected original source functions missing")
    for node in selected:
        if node.decorator_list:
            raise ValueError("Unexpected function decorator")
    isolated = ast.Module(body=selected, type_ignores=[])
    exec(compile(isolated, "<exact-fetched-source-functions>", "exec"), namespace)
    return namespace


def reproduce(utils_bytes: bytes, squad_bytes: bytes) -> list[dict]:
    if digest(utils_bytes) != PIN_UTILS_SHA or digest(squad_bytes) != PIN_SQUAD_SHA:
        raise ValueError("Pinned published source hash mismatch")
    squad = extract_functions(squad_bytes.decode(),
        {"normalize_answer", "get_tokens", "compute_exact", "compute_f1"},
        {"collections": collections, "re": re, "string": string})
    mera = extract_functions(utils_bytes.decode(), {"process_results"},
        {"Dict": Dict, "List": List, "Any": Any, "squad_metrics": SimpleNamespace(**squad)})
    rows = []
    for gold, prediction in SYNTHETIC_CASES:
        scores = mera["process_results"]({"outputs": gold}, [prediction])
        rows.append({"synthetic": True, "gold": gold, "prediction": prediction,
                     "normalized_gold": squad["normalize_answer"](gold),
                     "normalized_prediction": squad["normalize_answer"](prediction),
                     "published_mera_exact_source": scores})
    return rows


def fetch(url: str, target: Path) -> tuple[bytes, dict]:
    request = Request(url, headers={"User-Agent": "agro-route-research-source-audit",
                                  "Accept": "application/vnd.github+json" if "api.github.com" in url else "*/*"})
    with urlopen(request, timeout=40) as response:
        content = response.read()
        receipt = {"url": url, "http_status": response.status,
                   "sha256": digest(content), "bytes": len(content),
                   "etag": response.headers.get("ETag"),
                   "last_modified": response.headers.get("Last-Modified"),
                   "link": response.headers.get("Link"),
                   "rate_limit_remaining": response.headers.get("X-RateLimit-Remaining"),
                   "final_url": response.url}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return content, receipt


def audit(out: Path, cache: Path) -> dict:
    out.mkdir(parents=True, exist_ok=False)
    cache.mkdir(parents=True, exist_ok=True)
    sources, failures, responses = [], [], {}

    def get(label, url):
        try:
            content, receipt = fetch(url, cache / label)
            receipt["label"] = label
            sources.append(receipt)
            responses[label] = content
            return content
        except Exception as exc:
            failures.append({"label": label, "url": url, "type": type(exc).__name__, "message": str(exc)})
            return None

    api = f"https://api.github.com/repos/{REPO}"
    repo = json.loads(get("repository.json", api))
    default_branch = repo["default_branch"]
    head = json.loads(get("head.json", f"{api}/commits/{default_branch}"))["sha"]
    for label, url in (
        ("tags.json", f"{api}/tags?per_page=100"),
        ("releases.json", f"{api}/releases?per_page=100"),
        ("issues.json", f"{api}/issues?state=all&per_page=100"),
        ("pulls.json", f"{api}/pulls?state=all&per_page=100"),
        ("utils_history.json", f"{api}/commits?path=industrial_tasks/agro_bench/utils.py&per_page=100"),
        ("tree.json", f"{api}/git/trees/{head}?recursive=1"),
        ("transformers_tag.json", "https://api.github.com/repos/huggingface/transformers/git/ref/tags/v4.57.1"),
        ("hf_metadata.json", "https://huggingface.co/api/datasets/MERA-evaluation/ruTXTAgroBench"),
        ("hf_README.md", "https://huggingface.co/datasets/MERA-evaluation/ruTXTAgroBench/raw/b00011342a8f5f1e7968edaa2f6d50545a1e8f79/README.md"),
        ("task_page.html", "https://mera.a-ai.ru/ru/industrial/tasks/1"),
        ("terms.pdf", "https://mera.a-ai.ru/storage/custom/i7LuNHscdaHo8t5lnmsePtgKmmIQXiPrMcwuQHOs.pdf"),
        ("submission_entry.html", "https://mera.a-ai.ru/ru/industrial/submits/create"),
    ):
        get(label, url)
    for suffix, revision in (("pinned", PIN), ("head", head)):
        for path in ("industrial_tasks/agro_bench/utils.py", "industrial_tasks/agro_bench/task.yaml",
                     "README.md", "docs/model_scoring.md", "docs/dataset_hf.md", "LICENSE"):
            get(f"{suffix}_{path.replace('/', '__')}", f"https://raw.githubusercontent.com/{REPO}/{revision}/{path}")
    get("squad_metrics_v4.57.1.py", "https://raw.githubusercontent.com/huggingface/transformers/v4.57.1/src/transformers/data/metrics/squad_metrics.py")
    pulls = json.loads(responses.get("pulls.json", b"[]"))
    for pull in pulls:
        number = pull["number"]
        get(f"pr_{number}_files.json", f"{api}/pulls/{number}/files?per_page=100")
        get(f"pr_{number}_comments.json", f"{api}/issues/{number}/comments?per_page=100")
    history = json.loads(responses.get("utils_history.json", b"[]"))
    for entry in history:
        sha = entry["sha"]
        get(f"history_{sha}__utils.py", f"https://raw.githubusercontent.com/{REPO}/{sha}/industrial_tasks/agro_bench/utils.py")
    diagnostics = reproduce(responses["pinned_industrial_tasks__agro_bench__utils.py"],
                            responses["squad_metrics_v4.57.1.py"])
    def summary(label):
        raw = json.loads(responses.get(label, b"[]"))
        if label in {"pulls.json", "issues.json"}:
            return [{key: item.get(key) for key in ("number", "state", "title", "html_url", "created_at", "updated_at")}
                    | {"is_pull_request": "pull_request" in item} for item in raw]
        if label == "utils_history.json":
            return [{"sha": item["sha"], "date": item["commit"]["committer"]["date"],
                     "message": item["commit"]["message"], "url": item["html_url"]} for item in raw]
        return raw
    hf = json.loads(responses.get("hf_metadata.json", b"{}"))
    result = {
        "schema_version": "1.0", "run_id": "20261003_mera_scorer_recheck",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "executed_script_sha256": digest(Path(__file__).read_bytes()),
        "status": "DEV", "synthetic_only": True,
        "public_repository": REPO, "pinned_revision": PIN, "current_default_branch": default_branch,
        "current_head": head, "head_equals_pin": head == PIN,
        "head_utils_equals_pin": responses.get("head_industrial_tasks__agro_bench__utils.py") == responses.get("pinned_industrial_tasks__agro_bench__utils.py"),
        "execution": {"method": "compile unchanged AST function nodes from newly fetched exact source",
                      "original_functions": ["normalize_answer", "get_tokens", "compute_exact", "compute_f1", "process_results"],
                      "transformers_version": SQUAD_VERSION, "transformers_not_pinned_by_MERA_task": True,
                      "transformers_tag_object": json.loads(responses.get("transformers_tag.json", b"{}")),
                      "dependency_imports_replaced_by_stdlib_bindings": True, "function_bodies_modified": False},
        "diagnostics_synthetic": diagnostics,
        "tags": summary("tags.json"), "releases": summary("releases.json"),
        "issues": summary("issues.json"), "pull_requests": summary("pulls.json"),
        "utils_history": summary("utils_history.json"),
        "api_pagination_unread": [s["label"] for s in sources if s.get("link") and 'rel="next"' in s["link"]],
        "server_metric_certainty": "UNKNOWN",
        "server_metric_reason": "No production scorer code, deployed revision, or official option-A test result is exposed by the checked sources; no submission was sent.",
        "rights": {"decision": "USE_WITH_RESTRICTIONS", "redistribution": "DO_NOT_REDISTRIBUTE",
                   "current_hf_revision": hf.get("sha"), "hf_license": hf.get("cardData", {}).get("license"),
                   "code_MIT_not_dataset_grant": True,
                   "terms_hash_matches_previous_audit": digest(responses.get("terms.pdf", b"")) == "7e7ee8868f8302765f09c31dc6fb7d8f5afbc74721dd26579d8efe37ae77db00"},
        "private_test_ready": False, "maintainer_contacted": False, "scoring_submission_sent": False,
        "benchmark_content_downloaded": False,
        "source_receipts": sources, "fetch_failures": failures,
    }
    (out / "scorer_recheck.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "results/20261003_mera_scorer_recheck_verified")
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache/mera_scorer_recheck_20261003")
    args = parser.parse_args()
    result = audit(args.out, args.cache)
    print(json.dumps({key: result[key] for key in ("current_head", "head_utils_equals_pin", "tags", "releases", "issues", "pull_requests", "utils_history", "api_pagination_unread", "fetch_failures", "rights")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
