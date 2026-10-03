"""Append source-bound scientific claims after the implementation delivery commit.

The delivery commit contains exact executed source snapshots; execution used
the recorded parent HEAD plus frozen working-tree hashes. It is not falsely
claimed that these files were already committed when inference started.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from agro_route.claim_provenance_resource_20261003 import resolve_pointer, validate_provenance

ROOT = Path(__file__).resolve().parents[1]


def build(delivery_commit):
    subprocess.run(["git", "cat-file", "-e", delivery_commit + "^{commit}"], cwd=ROOT, check=True)
    claims = []
    documents = {}
    bindings = {}

    def add(identifier, statement, file, pointer, status, limitations, run_id=None):
        path = ROOT / file
        if file not in documents:
            raw = path.read_bytes()
            documents[file] = (json.loads(raw.decode("utf-8-sig")), hashlib.sha256(raw).hexdigest())
        source, digest = documents[file]
        run = source.get("run_id", run_id or "20261003_resource_session")
        commit = source.get("code_commit", delivery_commit)
        bindings[run] = commit
        claims.append({"claim_id": identifier, "statement": statement,
                       "run_id": run, "file": file, "field": pointer,
                       "value": resolve_pointer(source, pointer), "code_commit": commit,
                       "status": status, "data_sha256": digest, "limitations": limitations})

    analysis = "results/20261003_resource_analysis/analysis.json"
    dev_limit = "Historical DEV293 model-selection data; 289 scored, 4 reference issues, not official MERA or confirmatory"
    for model in ("qwen3.5-9b", "qwen3.8-27b", "gemma-4-26b-a4b-it"):
        for field in ("strict_em_count", "n_scored", "strict_set_em", "strict_set_f1", "invalid_output", "errors"):
            add(model + "_dev_" + field, model + " historical " + field, analysis,
                "/models/" + model + "/quality/" + field, "DEV", dev_limit)
        add(model + "_dev_latency", model + " historical HTTP latency distribution, seconds", analysis,
            "/models/" + model + "/latency", "DEV", "Historical profile; not V2 native telemetry")
    for field in ("em_retention", "f1_retention", "exact_gguf_size_27_minus_9_bytes"):
        add("qwen9_" + field, "Qwen9/Qwen27 descriptive " + field, analysis,
            "/ratios_qwen9_vs_qwen27/" + field, "DEV", dev_limit)
    for field in ("paired_qwen9_minus_qwen27", "paired_bootstrap", "by_domain", "by_answer_cardinality"):
        add("qwen_pair_" + field, "Paired same-example descriptive " + field, analysis,
            "/" + field, "DEV", "No non-inferiority margin frozen; exploratory paired/domain-stratified uncertainty")
    for model in ("qwen3.5-9b", "qwen3.8-27b"):
        for field in ("auc_correctness", "auc_interval", "calibrated_probability_of_correctness", "ece_brier_status"):
            add(model + "_confidence_" + field, "Lexical correctness diagnostic " + model + " " + field,
                analysis, "/confidence/" + model + "/" + field, "DEV",
                "Lexical token probability is not calibrated correctness; no entropy/full-option margin with top_logprobs=1")
    add("qwen9_cascade_replay", "Existing Qwen9 to Mercury DEV60 threshold replay", analysis,
        "/qwen9_mercury_dev60_replay", "SIMULATED", "No live requests, latency/cost savings or confidence benefit established")

    systems = "results/20261003_systems_checkpoint0_v2/systems_corrected_aggregate.json"
    for model in ("qwen3.5-9b", "qwen3.8-27b"):
        for field in ("n", "errors", "json_parse_invalid", "latency_s", "client_ttft_s", "backend_ttft_s",
                      "backend_tokens_per_second", "resources", "load_samples_s", "warmup_samples_s",
                      "context", "context_checkpoints", "concurrency", "gpu_placement", "finish_reason_status"):
            add(model + "_v2_" + field, model + " native TELEMETRY40 " + field, systems,
                "/models/" + model + "/" + field, "SYSTEMS_TELEMETRY",
                "Same40, ABBA, native automatic GPU placement UNKNOWN; sampled whole-device/system and basename RSS; two loads not cold tails")
    add("v2_resource_ratios", "Native40 latency ratio and sampled whole-memory differences", systems,
        "/ratios", "SYSTEMS_TELEMETRY", "Not isolated causal parameter-count effect; different GGUF quantization")
    for field in ("host_idle_before", "host_idle_after"):
        add("v2_" + field, "Measured free/used memory " + field, systems,
            "/" + field, "SYSTEMS_TELEMETRY", "Whole-host values include ordinary desktop processes; energy not estimated")
    identity = "results/20261003_resource_session/live_weight_identity.json"
    for index, model in enumerate(("qwen3.8-27b", "qwen3.5-9b")):
        add(model + "_gguf_identity", model + " exact weight SHA256/bytes verified before inference", identity,
            "/models/" + str(index), "SYSTEMS_TELEMETRY", "Primary GGUF excludes separate vision projector")
    metadata = "results/20261003_resource_session/model_author_metadata.json"
    add("official_language_parameter_labels", "Author-documented nominal language parameter sizes", metadata,
        "/nominal_language_parameters_billions", "SUPPLEMENTARY", "Not full vision/MTP tensor-element recount")
    env = "results/20261003_resource_session/environment_and_baseline.json"
    for field in ("lm_studio", "runtime_scope", "baseline_full_suite", "mera_server_scorer", "new_paid_api_spend_usd"):
        add("environment_" + field, "Verified session environment/status " + field, env,
            "/" + field, "SUPPLEMENTARY", "Baseline against initially dirty author letter; per-model runtime UNKNOWN; maintainer status author-reported")
    qa = "results/20261003_resource_session/independent_systems_v1_correction.json"
    add("v1_failures_preserved", "Independent audit preserves resource-censored V1 Qwen27 outcomes", qa,
        "/models", "SYSTEMS_TELEMETRY", "Failed attempts are not arithmetic quality; conditional successes not unbiased full40")

    study = "results/20261003_systems_checkpoint0_v2/study_c_corrected_aggregate.json"
    for model in ("qwen3.5-9b", "qwen3.8-27b", "deterministic_tools"):
        for field in ("n", "correct", "action_correct", "declared_real_tool_n", "declared_real_tool_correct",
                      "numeric_n", "numeric_correct", "numeric_rounding_1e4_correct",
                      "missing_input_or_invalid_input_n", "missing_input_or_invalid_input_correct",
                      "unit_conversion_n", "unit_conversion_correct", "source_run_counts", "latency_s"):
            add(model + "_study_c_" + field, model + " Study C " + field, study,
                "/models/" + model + "/" + field, "DEV",
                "27 constructed typed-task cases with formulas supplied; Q9/tools V1, Q27 V2; different operational profiles, no agronomic advice")
        add(model + "_study_c_tool_replay", model + " executor replay from declared tool", study,
            "/models/" + model + "/declared_tool_executor_replay", "SIMULATED",
            "26 eligible cases; original inputs supplied to code, not measured live tool-call argument transfer")

    cli = "results/20261003_cli_products/summary.json"
    add("codex_cli_dev60", "Codex CLI Luna medium product baseline on DEV60", cli,
        "/codex", "SUPPLEMENTARY", "59 scored, hidden product system/harness, startup latency, model backend ID not exposed; 46 JSON contract failures but valid option sets")
    add("claude_cli_status", "Claude Code Sonnet model selection and authentication blocker", cli,
        "/claude", "SUPPLEMENTARY", "Two synthetic attempts authentication403, no completed inference or DEV60; no Opus substitution")
    add("scientific_cloud_recommendation", "Primary scientific cloud baseline recommendation", cli,
        "/primary_cloud_recommendation", "SUPPLEMENTARY", "Provisional existing Mercury2.5 direct; different conditions from CLI and local")
    mercury = "results/20261003_cloud_budget_only_c1184a27/cloud_development_analysis.json"
    for field in ("strict_em_count", "n_scored", "strict_set_em", "strict_set_f1", "n_completed", "errors"):
        add("mercury_direct_" + field, "Existing direct Mercury2.5 DEV60 " + field, mercury,
            "/profiles/mercury25_instant512_t05/summary/" + field, "DEV", "Historical direct API reference; no new requests, one reference issue and length completions, not full293 or private TEST")
    effort = "results/20261003_cli_products/effort_summary.json"
    for profile in ("low", "medium", "high"):
        add("codex_effort_" + profile, "Frozen10 Codex product effort " + profile, effort,
            "/profiles/" + profile, "SUPPLEMENTARY", "9 scored, one stochastic pass; medium reused from60, extra low/high not full60; no optimum established")
    add("codex_effort_recommendation", "Retain medium full60, high candidate for future quality-focused protocol", effort,
        "/recommendation", "SUPPLEMENTARY", "Exploratory n9; do not extrapolate high accuracy to DEV60")
    research = "results/20261003_backup_benchmark/research.json"
    for field in ("primary_backup", "recommendation_state", "access_conditions_accepted", "benchmark_rows_downloaded_this_session"):
        add("backup_" + field, "One selected future independent agricultural benchmark: " + field, research,
            "/" + field, "SUPPLEMENTARY", "BhashaBench-Krishi English/test; gate/contact rights not accepted, no rows/evaluator acquired, contamination UNKNOWN")
    add("backup_provenance", "Primary backup expert/data/access/scoring evidence", research,
        "/candidates/0", "SUPPLEMENTARY", "Author-declared CC BY4.0/expert verification; exact files and generative scorer still unverified")

    document = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
                "source_commit": delivery_commit, "code_commit_role": "DELIVERY_COMMIT_CONTAINING_EXECUTED_SOURCE_SNAPSHOTS",
                "execution_parent_head": "6c496744107001d523c2311f236a61a5e14b93c2",
                "execution_identity_note": "Execution occurred on parent HEAD plus uncommitted code; frozen protocols and exact source archives bind bytes. Delivery commit contains them, not a claim of pre-execution commit.",
                "independent_holdout": False, "authorized_protocol": False, "private_test_run": False,
                "run_code_commits": bindings, "claims": claims}
    receipt = validate_provenance(document, ROOT)
    if not receipt["valid"]:
        raise ValueError(json.dumps(receipt))
    return document


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Supply verified implementation delivery commit")
    document = build(sys.argv[1])
    target = ROOT / "manuscript/CLAIM_PROVENANCE_RESOURCE_SESSION_20261003.json"
    with target.open("x", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"claims": len(document["claims"]), "provenance": target.relative_to(ROOT).as_posix()}))
