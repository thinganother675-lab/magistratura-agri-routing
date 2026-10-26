"""Build/validate a scalar evidence map without touching historical artifacts.

No MERA questions, gold, per-item records or generated answers are copied.
Historical exact execution HEADs absent from manifests remain UNKNOWN.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "manuscript/CLAIM_PROVENANCE_20261003.json"
VALIDATION = ROOT / "results/20261003_mera_agro_routing_3de88b82/claim_provenance_validation.json"
HOME_COMMIT = "b063c079af44cdd6353db39293671f6d8d11f3d2"
ARCHIVE_COMMIT = "420c3eccf46b4a233780b62b5fda86cf7f5f1e80"
NEW_COMMIT = "72b0c32ebc1eb1b514adc3489a2e87231d299250"
GUARD_COMMIT = "6155f58f66d45a8d62e78ab15c637d94b33d8646"
HOME = "results/analysis_input_reconciled_20261002_052358Z_804ced2b"
HOME_ANALYSIS = HOME + "/analysis_20261002_052438Z_2c0beea8"
SUPP = "results/20261002_180119Z_76283d02_prerouting_dev"
AUDIT = "results/20261003_045520Z_1bd51445_scorer_audit"
STUDY_B = "results/20261003_mera_agro_routing_3de88b82"

# source_id: (file, originating run, scope, code identity, numeric roots)
SPECS = {
    "home150": (HOME_ANALYSIS + "/statistics_reporting_corrected.json", "analysis_input_reconciled_20261002_052358Z_804ced2b", "FROZEN_HOME150_CONTROLLED_STUDY_A", HOME_COMMIT,
                ["/target_n", "/source_groups", "/statistics", "/summary", "/paired", "/category", "/language", "/hypothesis", "/actual_cloud_attempts_manifest", "/cloud_traces_journaled", "/actual_local_attempts_manifest", "/local_traces_journaled", "/resource_peak_total_scope", "/model_load_metadata", "/prices_and_provider"]),
    "home_manifest": (HOME + "/manifest.json", "analysis_input_reconciled_20261002_052358Z_804ced2b", "FROZEN_HOME150_EXECUTION_METADATA", HOME_COMMIT,
                      ["/target_n", "/local", "/cloud", "/total_completed_cases", "/total_unique_policy_decisions", "/cloud_calls_actual", "/local_calls_actual"]),
    "provider_observations": (HOME_ANALYSIS + "/provider_observations.json", "analysis_20261002_052438Z_2c0beea8", "POST_HOC_PROVIDER_OBSERVATIONS_NOT_NEW_INFERENCE", "UNKNOWN",
                              ["/cloud_calls", "/returned_raw_n", "/warnings_observed_cloud_calls", "/warning_call_coverage_by_policy", "/actual_raw_model_counts", "/requested_temperature", "/provider_reported_effective_temperature"]),
    "supplementary_dev36": (SUPP + "/analysis_20261002_181438Z_c3905087/summary.json", "20261002_180119Z_76283d02_prerouting_dev", "EXPLORATORY_DEV36_NOT_CONFIRMATORY", "UNKNOWN",
                            ["/n", "/source_groups", "/methods", "/paired_quality"]),
    "supplementary_manifest": (SUPP + "/manifest.json", "20261002_180119Z_76283d02_prerouting_dev", "EXPLORATORY_DEV36_EXECUTION_METADATA", "UNKNOWN", ["/rows", "/expected_rows"]),
    "scorer_audit": (AUDIT + "/summary.json", "20261003_045520Z_1bd51445_scorer_audit", "POST_HOC_DIAGNOSTIC_NOT_HOME150_RESCORING", "UNKNOWN",
                     ["/diagnostic_version", "/new_generations", "/numeric_n", "/historic_local_numeric_correct", "/numeric_cause_counts", "/independent_numeric_gold_agreement", "/compound_false_acceptance_by_method", "/compound_false_literal_would_pass_by_method", "/independent_compound_gold_agreement", "/protected_historical_files"]),
    "numeric_diagnostics": (AUDIT + "/home150_local_numeric_diagnostics_v2.json", "20261003_045520Z_1bd51445_scorer_audit", "HISTORICAL_PER_ITEM_DIAGNOSTIC_SOURCE_NOT_COPIED", "UNKNOWN", []),
    "compound_diagnostics": (AUDIT + "/home150_compound_diagnostics_v2.json", "20261003_045520Z_1bd51445_scorer_audit", "HISTORICAL_PER_ITEM_DIAGNOSTIC_SOURCE_NOT_COPIED", "UNKNOWN", []),
    "agxqa_overlap": ("results/20261002_170443Z_21722066_dataset_literature/external_dataset_overlap.json", "20261002_170443Z_21722066_dataset_literature", "DATA_PROVENANCE_AUDIT_NOT_MODEL_EVALUATION", "UNKNOWN", ["/splits", "/pair_overlaps"]),
    "mera_dev": (STUDY_B + "/dev_analysis.json", "20261003_mera_agro_routing_3de88b82", "STUDY_B_DEV_ONLY_EXPLORATORY_NOT_OFFICIAL_REMOTE_SCORE", NEW_COMMIT,
                 ["/model_profiles", "/counterfactual_grid", "/actual_inference_accounting"]),
    "study_c": ("data/study_c_technical_20261003.json", "study_c_technical_20261003_v1", "DEVELOPMENT_REFERENCE_ONLY_NO_LLM_EVALUATION", NEW_COMMIT, []),
    "replay_profile": (STUDY_B + "/replay_profile_provenance.json", "20261003_mera_agro_routing_3de88b82", "COUNTERFACTUAL_PROFILE_ATTRIBUTION_ONLY_NO_NEW_METRICS", NEW_COMMIT, ["/cloud_parameters/temperature", "/cloud_parameters/max_completion_tokens"]),
    "decision_gate": (STUDY_B + "/decision_gate.json", "20261003_mera_agro_routing_3de88b82", "PLAN_ONLY_NOT_SELECTED_BUDGET_NOT_MEASURED_RESULT", "UNKNOWN", ["/planning_only_not_selected_budget"]),
    "software_validation": (STUDY_B + "/validation_final.json", "20261003_mera_agro_routing_3de88b82", "OBSERVED_SOFTWARE_TESTS_NOT_AGRONOMIC_VALIDATION", NEW_COMMIT, ["/tests_observed_in_this_session", "/protected_historical_files_rechecked", "/executed_source_archives_verified_against_git", "/restricted_raw_run_hashes_verified", "/study_c_development_cases", "/generative_models_downloaded", "/external_submissions", "/leaderboard_publications", "/messages_to_maintainers"]),
    "continuation_integrity": (STUDY_B + "/continuation_integrity.json", "20261003_mera_agro_routing_3de88b82", "ARCHIVE_INTEGRITY_CHECK_NOT_MODEL_EVALUATION", "UNKNOWN", ["/pre_continuation_research_files", "/manuscript_files_preserved"]),
    "confidence_guard": (STUDY_B + "/validation_confidence_guard.json", "20261003_mera_agro_routing_3de88b82", "FINAL_SOFTWARE_TESTS_AT_6155_NOT_NEW_INFERENCE", GUARD_COMMIT, ["/baseline_passed", "/prior_full_suite_at_72b0c32_passed", "/final_full_suite_passed", "/duration_seconds", "/new_regression_cases", "/new_inference_calls"]),
}
NEW_SOURCE_IDS = {"mera_dev", "study_c", "replay_profile", "decision_gate", "software_validation", "continuation_integrity", "confidence_guard"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pointer(document, path: str):
    """RFC 6901 pointer; an empty pointer selects the document root."""
    if path == "":
        return document
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("Invalid JSON pointer")
    value = document
    for token in path[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            if not token.isascii() or not token.isdigit() or (len(token)>1 and token.startswith("0")):
                raise ValueError("Invalid RFC6901 array index")
            value=value[int(token)]
        else:
            value=value[token]
    return value


def escape(value) -> str:
    return str(value).replace("~", "~0").replace("/", "~1")


def numeric_leaves(value, prefix=""):
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in {"per_item", "question", "questions", "outputs", "output", "request", "expected", "gold", "ids", "row_ids"}:
                continue
            yield from numeric_leaves(nested, prefix + "/" + escape(key))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from numeric_leaves(nested, prefix + "/" + str(index))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(value):
            raise ValueError("Nonfinite numeric claim: " + prefix)
        yield prefix, value


def git_bytes(commit: str, path: str) -> bytes:
    result = subprocess.run(["git", "show", commit + ":" + path], cwd=ROOT, capture_output=True, check=False)
    if result.returncode:
        raise ValueError("Git source unavailable: " + commit + ":" + path)
    return result.stdout


def commit_exists(commit: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", commit + "^{commit}"], cwd=ROOT, capture_output=True, check=False).returncode == 0


def code_hash_evidence(commit: str, hashes: dict) -> dict:
    evidence = {}
    for path, expected in hashes.items():
        observed = hashlib.sha256(git_bytes(commit, path)).hexdigest()
        if observed != expected:
            raise ValueError("Code blob does not match recorded hash: " + path)
        evidence[path] = expected
    return {"commit": commit, "basis": "git blob SHA256 matches recorded source hash; exact execution HEAD is a separate fact", "verified_hashes": evidence}


def load_documents() -> dict:
    return {key: json.loads((ROOT / spec[0]).read_text(encoding="utf-8")) for key, spec in SPECS.items()}


def derived_value(expression: dict, documents: dict):
    values = [pointer(documents[x["source_id"]], x["json_pointer"]) for x in expression["operands"]]
    operation = expression["operation"]
    if operation == "length": return len(values[0])
    if operation == "sum": return sum(values)
    if operation == "difference": return values[0] - values[1]
    if operation == "relative_reduction_percent": return 100 * (values[0] - values[1]) / values[0]
    if operation == "fraction_to_percentage_points": return 100 * values[0]
    if operation == "count_true_field": return sum(row.get(expression["field"]) is True for row in values[0])
    raise ValueError("Unsupported deterministic claim derivation")


def build_map(documents: dict) -> dict:
    registry = {}
    catalogs = {}
    for source_id, (path, run, scope, commit, roots) in SPECS.items():
        registry[source_id] = {
            "analysis_file": path, "run_id": run, "sha256": sha256(ROOT / path), "scope": scope,
            "code_commit": commit, "archive_commit": ARCHIVE_COMMIT if source_id not in NEW_SOURCE_IDS else None,
            "exact_execution_HEAD": "UNKNOWN" if source_id not in NEW_SOURCE_IDS else "Recorded development/analysis source identity where available; sidecar writer execution HEAD not asserted",
            "code_commit_role": "verified frozen analyzer/source identity" if commit == HOME_COMMIT else "recorded analysis, test or authored reference source identity" if commit != "UNKNOWN" else "not recorded by source artifact; an archive commit is not an execution assertion",
        }
        catalogs[source_id] = dict(pair for root in roots for pair in numeric_leaves(pointer(documents[source_id], root), root))
    registry["home150"]["code_hash_evidence"] = code_hash_evidence(HOME_COMMIT, documents["home_manifest"]["code_sha256"])
    registry["home_manifest"]["code_hash_evidence"] = registry["home150"]["code_hash_evidence"]
    correction = documents["home150"]["reporting_correction"]
    registry["home150"]["reporting_helper"] = code_hash_evidence(ARCHIVE_COMMIT, {"scripts/correct_home_final_reporting.py":correction["helper_sha256"]})
    registry["home150"]["pointer_code_commit_overrides"] = {"/summary/"+policy+"/ask_coverage":ARCHIVE_COMMIT for policy in documents["home150"]["summary"]}
    if documents["mera_dev"]["analysis_code_commit"] != NEW_COMMIT:
        raise ValueError("Unexpected Study B analysis commit")
    registry["mera_dev"]["code_hash_evidence"] = code_hash_evidence(NEW_COMMIT, {"scripts/analyze_mera_dev_20261003.py":documents["mera_dev"]["analysis_source_sha256"]})
    registry["mera_dev"]["inference_version_limitation"] = "Model profiles record inference baseline 420c separately from executed source hashes; profiles used different working source versions. Analysis commit72b0 does not claim identical inference code across profiles."
    registry["study_c"]["code_hash_evidence"] = code_hash_evidence(NEW_COMMIT, {path:sha256(ROOT/path) for path in ["scripts/build_study_c_reference_20261003.py","src/agro_route/deterministic_study_20261003.py"]})
    if documents["confidence_guard"]["code_commit"]!=GUARD_COMMIT:
        raise ValueError("Unexpected confidence guard test commit")
    guard_paths={"adapter":"src/agro_route/mera_adapter_20261003.py", "runner_tests":"tests/test_mera_dev_20261003.py", "runner":"scripts/mera_dev_20261003.py", "adapter_tests":"tests/test_mera_adapter_20261003.py"}
    registry["confidence_guard"]["code_hash_evidence"] = code_hash_evidence(GUARD_COMMIT, {guard_paths[key]:value for key,value in documents["confidence_guard"]["source_sha256"].items()})
    registry["confidence_guard"]["exact_test_source_commit"] = GUARD_COMMIT

    claims = []
    def key(claim_id, label, source_id, path, unit=None, interpretation=None):
        value = pointer(documents[source_id], path)
        if isinstance(value, (dict, list)):
            raise ValueError("Named claims must be scalars; lists belong to derived claims")
        source = registry[source_id]
        claims.append({"claim_id":claim_id,"claim_ru":label,"source_id":source_id,"run_id":source["run_id"],"analysis_file":source["analysis_file"],"json_pointer":path,"value":value,"unit":unit,"sha256":source["sha256"],"code_commit":source.get("pointer_code_commit_overrides",{}).get(path,source["code_commit"]),"scope":source["scope"],"interpretation":interpretation})

    key("home150_n","Размер замороженной выборки HOME150","home150","/target_n","cases")
    key("home150_groups","Группы источников/сценариев HOME150","home150","/source_groups","groups")
    key("home150_decisions","Отдельные решения задача×политика","home_manifest","/total_unique_policy_decisions","decisions")
    for policy in documents["home150"]["summary"]:
        for field, unit in [("correct","correct_cases"),("quality","fraction"),("cloud_calls","requests"),("cloud_cost_known_total_usd","USD")]:
            key("home150_"+policy+"_"+field,policy+": "+field,"home150","/summary/"+policy+"/"+field,unit)
        for field in ["mean_s","p50_s","p95_s"]:
            key("home150_"+policy+"_latency_"+field,policy+": наблюдаемая задержка "+field,"home150","/summary/"+policy+"/latency_measured_end_to_end/"+field,"seconds")
    p="/paired/hybrid_minus_tool_cloud/quality_a_minus_b"
    key("home150_quality_difference","Hybrid минус TOOLS+CLOUD: разность качества","home150",p+"/estimate","fraction")
    key("home150_quality_ci_lower","Нижняя граница кластерного 95% интервала разности","home150",p+"/ci95/0","fraction")
    key("home150_quality_ci_upper","Верхняя граница кластерного 95% интервала разности","home150",p+"/ci95/1","fraction")
    key("home150_noninferiority","Неухудшение качества: замороженный критерий","home150","/hypothesis/criteria/quality_noninferiority/status",interpretation="FAIL means noninferiority NOT ESTABLISHED, not proof of inferiority; manuscript shorthand NI=FAILED")
    key("home150_hypothesis_supported","Выполнена совокупность замороженных критериев","home150","/hypothesis/supported_on_frozen_controlled_sample")
    key("home150_relative_reduction_denominator","Обращения TOOLS+CLOUD — знаменатель относительного сокращения","home150","/summary/tool_cloud/cloud_calls","requests")
    key("home150_absolute_reduction_fraction","Абсолютное сокращение обращений от всех150 задач","home150","/paired/hybrid_minus_tool_cloud/cloud_call_reduction_all_target","fraction",interpretation="0.5333 fraction equals53.33percentage points; distinct from80percent relative reduction")
    for field in ["actual_cloud_attempts_manifest","actual_local_attempts_manifest"]:
        key("home150_"+field,field,"home150","/"+field,"attempts")
    for field in ["cloud_calls","returned_raw_n","provider_reported_effective_temperature"]:
        key("home150_provider_"+field,field,"provider_observations","/"+field)
    for method in ["rule_first","jev_first","laya_first","offline_laya"]:
        for field in ["correct","generative_cloud_calls","hosted_router_calls","total_external_requests"]:
            key("dev36_"+method+"_"+field,method+": "+field,"supplementary_dev36","/methods/"+method+"/"+field)
    for field in ["numeric_n","historic_local_numeric_correct","independent_numeric_gold_agreement","independent_compound_gold_agreement","human_review"]:
        key("audit_"+field,field,"scorer_audit","/"+field)
    for method in ["hybrid","offline"]:
        key("audit_false_acceptance_"+method,"Ложное принятие составной ветви: "+method,"scorer_audit","/compound_false_acceptance_by_method/"+method,"decisions")
    for field in ["status","selected_local_candidate","cloud_candidate","cloud_primary_selection_status","cloud_profile_limitations","partial_local_not_ranked","candidate_router_status","MERA_PRIVATE_TEST_READY","private_test_run","official_remote_scores","paired_confirmatory_ci","data_rights"]:
        key("mera_"+field,field,"mera_dev","/"+field)
    for field in documents["mera_dev"]["actual_inference_accounting"]:
        key("mera_actual_"+field,"Фактический учёт: "+field,"mera_dev","/actual_inference_accounting/"+field,interpretation="Actually incurred requests/cost estimates, not counterfactual deployment savings")
    for model in documents["mera_dev"]["model_profiles"]:
        prefix="/model_profiles/"+escape(model)+"/summary/"
        for field in ["n","diagnostic_set_exact_match","diagnostic_set_f1","official_compatible_raw_exact_match","official_compatible_raw_f1","errors","invalid_options","strict_format_failures","mean_latency_ms"]:
            key("mera_profile_"+model+"_"+field,model+": "+field,"mera_dev",prefix+field,interpretation="Small public DEV; official-compatible implementation is not an official MERA returned score; Qwen17-case partial screen is not ranked against completed60-case profiles")
    key("study_c_status","Техническая подборка для разработки, без оценки моделей","study_c","/status")
    for field in ["counterfactual_local_profile", "counterfactual_cloud_profile", "original_medium128_profile_in_counterfactual", "status"]:
        key("replay_"+field,"Происхождение всех строк моделируемого каскада: "+field,"replay_profile","/"+field)
    for field in ["cloud_only_usd", "two_full_cloud_branches_usd", "cloud_only_minutes_at_pilot_mean_without_overhead"]:
        key("planned_test_"+field,"Плановый сценарий бюджета, не измеренный расход: "+field,"decision_gate","/planning_only_not_selected_budget/"+field,interpretation="PLAN_ONLY;1000input tokens,256output token limit,2642test cases; requires re-estimate after model and routing selection")
    for field,claim_name in [("baseline_passed","baseline_passed"),("final_passed","full_suite_at_72b0_pre_guard"),("final_duration_seconds","duration_at_72b0_pre_guard")]:
        key("software_tests_"+claim_name,"Наблюдавшаяся программная проверка до дополнительной защиты confidence: "+field,"software_validation","/tests_observed_in_this_session/"+field,interpretation="Observed suite execution at72b0 BEFOREconfidence guard, not finaldelivery suite count and not agronomic validation")
    for field in ["baseline_passed", "prior_full_suite_at_72b0c32_passed", "final_full_suite_passed", "duration_seconds", "new_regression_cases", "new_inference_calls"]:
        key("confidence_guard_"+field,"Финальная программная проверка на версии6155: "+field,"confidence_guard","/"+field,interpretation="521tests observed at6155; distinct from prior509at72b0. Guard repair made no new inference calls and did not recompute DEV analysis.")
    key("historical_files_preserved","Исследовательские файлы до продолжения, сверенные с архивом","continuation_integrity","/pre_continuation_research_files","files")
    key("historical_manuscripts_preserved","Сохранённые прежние файлы рукописей","continuation_integrity","/manuscript_files_preserved","files")

    derived=[]
    def calculation(claim_id,label,operation,operands,unit=None,**kwargs):
        expression={"operation":operation,"operands":[{"source_id":sid,"json_pointer":ptr} for sid,ptr in operands],**kwargs}
        derived.append({"claim_id":claim_id,"claim_ru":label,"value":derived_value(expression,documents),"unit":unit,"derivation":expression,"source_sha256":{sid:registry[sid]["sha256"] for sid,_ in operands},"code_commits":{sid:registry[sid]["code_commit"] for sid,_ in operands}})
    calculation("home150_policy_count","Пять политик","length",[("home_manifest","/policies")],"policies")
    calculation("home150_relative_cloud_reduction_percent","Относительное сокращение облачных вызовов100→20","relative_reduction_percent",[("home150","/summary/tool_cloud/cloud_calls"),("home150","/summary/hybrid/cloud_calls")],"percent_of_tool_cloud_calls")
    calculation("home150_absolute_cloud_reduction_pp","Абсолютное сокращение обращений по всем150 задачам","fraction_to_percentage_points",[("home150","/paired/hybrid_minus_tool_cloud/cloud_call_reduction_all_target")],"percentage_points")
    calculation("dev36_policies","Число политик дополнительного DEV36","length",[("supplementary_dev36","/methods")],"policies")
    calculation("numeric_diagnostic_rows","Количество независимо проверенных численных ответов","length",[("numeric_diagnostics","")],"cases")
    calculation("numeric_diagnostic_agreement","Совпадение независимых численных эталонов","count_true_field",[("numeric_diagnostics","")],"cases",field="independent_gold_agreement")
    calculation("compound_diagnostic_agreement","Совпадение независимых составных условий","count_true_field",[("compound_diagnostics","")],"decisions",field="independent_gold_agreement")
    calculation("agxqa_conservative_remaining_test","Остаток теста после консервативной фильтрации источников","length",[("agxqa_overlap","/fresh_test_row_ids")],"rows")
    calculation("study_c_case_count","27 технических разработческих случаев; не результаты языковых моделей","length",[("study_c","/cases")],"development_reference_cases")
    calculation("review40_preserved_files","Сохранённые архивные файлы review40","length",[("continuation_integrity","/review40_files")],"files")

    return {"schema_version":1,"created_utc":datetime.now(timezone.utc).isoformat(),"date":"2026-10-03","purpose":"Stable numeric evidence map for human manuscript review and editorial tools; not an automatic publication approval",
            "builder_source_sha256":sha256(Path(__file__)),"source_register":registry,"numeric_claim_catalogs":catalogs,"key_claims":claims,"derived_claims":derived,
            "interpretation_guards":["HOME150 is frozen; new Study B/C scores are never pooled into it.","Study B is exploratory publicDEV; no official/privateTEST score exists.","MERA counterfactual_grid contains cached replay projections, not actual cloud-call savings;actual saved requests in this screen=0.","medium128 cloud run is an output-budget compatibility failure; instant256 is a separate weakDEV profile; Qwen is partial17/60.","Study C27 cases are development references with authoritative formulas; noLLM experiment performed.","Unknown costs, missing statistics and unrecorded exactexecutionHEAD remain unknown.","Archive/source blob identity is distinct from exactexecutionHEAD; originalHOME analyzer and laterASK reporting helper have separate verifiedcommits.","NoMERA questions,gold,fulloutputs orper_item records are included."],
            "manuscript_targets":["manuscript/english_routing_20261003.md","manuscript/russian_routing_20261003.md","manuscript/english_routing_20261003.tex","manuscript/russian_routing_20261003.tex"]}


def validate_map(mapping: dict, documents: dict) -> dict:
    failures=[]
    checks=0
    checks+=1
    if mapping["builder_source_sha256"]!=sha256(Path(__file__)):
        failures.append("Builder source hash mismatch: regeneration requires an explicit updated evidence map")
    checks+=1
    if documents["replay_profile"]["analysis_sha256"]!=mapping["source_register"]["mera_dev"]["sha256"]:
        failures.append("Replay profile sidecar does not bind this exact analysis")
    for sid,source in mapping["source_register"].items():
        checks+=1
        spec=SPECS[sid]
        if source["analysis_file"]!=spec[0] or source["run_id"]!=spec[1] or source["scope"]!=spec[2] or source["code_commit"]!=spec[3]:
            failures.append("Source registration/code identity mismatch:"+sid)
        if sha256(ROOT/source["analysis_file"]) != source["sha256"]: failures.append("Source hash mismatch:"+sid)
        for commit in {source["code_commit"],source.get("archive_commit")} - {"UNKNOWN",None}:
            checks+=1
            if not commit_exists(commit): failures.append("Commit unavailable:"+commit)
        for evidence_name in ["code_hash_evidence","reporting_helper"]:
            if evidence_name in source:
                evidence=source[evidence_name]
                for path,expected in evidence["verified_hashes"].items():
                    checks+=1
                    if hashlib.sha256(git_bytes(evidence["commit"],path)).hexdigest()!=expected: failures.append("Code hash mismatch:"+path)
    for sid,catalog in mapping["numeric_claim_catalogs"].items():
        for path,value in catalog.items():
            checks+=1
            actual=pointer(documents[sid],path)
            if type(actual) is not type(value) or actual!=value: failures.append("Numeric pointer/value mismatch:"+sid+path)
            if "/per_item/" in path or any(token in path for token in ["/question/","/questions/","/output/","/gold/"]): failures.append("Forbidden content pointer:"+sid+path)
    for claim in mapping["key_claims"]:
        checks+=1
        sid=claim["source_id"];source=mapping["source_register"][sid]
        expected_commit=source.get("pointer_code_commit_overrides",{}).get(claim["json_pointer"],source["code_commit"])
        actual=pointer(documents[sid],claim["json_pointer"])
        if type(actual) is not type(claim["value"]) or actual!=claim["value"]: failures.append("Named pointer/value mismatch:"+claim["claim_id"])
        if claim["code_commit"]!=expected_commit or claim["sha256"]!=source["sha256"] or claim["analysis_file"]!=source["analysis_file"] or claim["run_id"]!=source["run_id"]: failures.append("Named provenance mismatch:"+claim["claim_id"])
    for claim in mapping["derived_claims"]:
        checks+=1
        actual=derived_value(claim["derivation"],documents)
        if actual!=claim["value"]: failures.append("Derived claim mismatch:"+claim["claim_id"])
        for operand in claim["derivation"]["operands"]:
            sid=operand["source_id"];source=mapping["source_register"][sid]
            if claim["source_sha256"][sid]!=source["sha256"] or claim["code_commits"][sid]!=source["code_commit"]: failures.append("Derived provenance mismatch:"+claim["claim_id"])
    return {"created_utc":datetime.now(timezone.utc).isoformat(),"status":"PASS" if not failures else "FAIL","checks":checks,"source_files":len(mapping["source_register"]),"numeric_pointer_claims":sum(len(c) for c in mapping["numeric_claim_catalogs"].values()),"named_claims":len(mapping["key_claims"]),"derived_claims":len(mapping["derived_claims"]),"historical_sources_with_unrecorded_execution_head":[sid for sid,s in mapping["source_register"].items() if s["exact_execution_HEAD"]=="UNKNOWN"],"historical_artifacts_modified":False,"failures":failures,"claim_map_sha256":sha256(OUTPUT),"builder_source_sha256":sha256(Path(__file__))}


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument("--validate-only",action="store_true",help="Read existing map without regenerating values; write separate validation report")
    mode.add_argument("--rebuild",action="store_true",help="Explicitly regenerate this map only; never modify source artifacts")
    args=parser.parse_args()
    if OUTPUT.exists() and not args.validate_only and not args.rebuild:
        parser.error("Evidence map already exists; use --validate-only or explicitly --rebuild")
    documents=load_documents()
    if args.validate_only:
        mapping=json.loads(OUTPUT.read_text(encoding="utf-8"))
    else:
        mapping=build_map(documents)
        OUTPUT.write_text(json.dumps(mapping,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    validation=validate_map(mapping,documents)
    VALIDATION.write_text(json.dumps(validation,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in validation.items() if k in {"status","checks","source_files","numeric_pointer_claims","named_claims","derived_claims","failures"}},ensure_ascii=True))
    if validation["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
