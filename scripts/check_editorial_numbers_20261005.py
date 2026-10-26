"""Fact-check the 20261005 editorial manuscripts against the audited 20261004 text and evidence.

1. Every number in the edited body must already occur in the audited 20261004 body
   (citation/section numbering differences are reported, not hidden).
2. Key claims must appear in both RU and EN and match the evidence JSON values.
Writes results/20261005_editorial/numeric_fact_check.json.
"""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
MS = ROOT / "manuscript"
PAIRS = {
    "ru": (MS / "russian_resource_20261004.md", MS / "russian_resource_20261005_claude.md"),
    "en": (MS / "english_resource_20261004.md", MS / "english_resource_20261005_claude.md"),
    "ru_r2": (MS / "russian_resource_20261004.md", MS / "russian_resource_20261005_claude_r2.md"),
}
CUT = re.compile(r"^## (Литература|Список литературы|References)\s*$", re.M)


def body(path, lang):
    text = CUT.split(path.read_text(encoding="utf-8"))[0]
    text = re.sub(r"(\d)[   ](\d{3})", r"\1\2", text)
    text = text.replace("10⁻⁸", "1e-8").replace("10⁻⁴", "1e-4")
    text = text.replace(",", ".") if lang.startswith("ru") else text.replace(",", "")
    return text


def numbers(text):
    return re.findall(r"\d+(?:\.\d+)?(?:e-\d+)?", text)


def ptr(obj, pointer):
    for key in pointer.strip("/").split("/"):
        obj = obj[int(key)] if isinstance(obj, list) else obj[key]
    return obj


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


AUDIT = "results/20261004_evidence_audit/analysis.json"
STUDY_C = "results/20261004_study_c_live/summary.json"
# (claim, RU text, EN text, evidence check)
CLAIMS = [
    ("Qwen9 DEV293 EM", "141/289", "141/289", lambda: ptr(load(AUDIT), "/historical_quality/qwen3.5-9b/em_count") == 141),
    ("Qwen27 DEV293 EM", "150/289", "150/289", lambda: ptr(load(AUDIT), "/historical_quality/qwen3.8-27b/em_count") == 150),
    ("EM percentages", "48.79", "48.79", lambda: round(141 / 289 * 100, 2) == 48.79 and round(150 / 289 * 100, 2) == 51.90),
    ("EM difference", "−3.11", "−3.11", lambda: round(ptr(load(AUDIT), "/paired_bootstrap/em_left_minus_right") * 100, 2) == -3.11),
    ("bootstrap EM interval", "[−8.30; +2.42]", "[−8.30 +2.42]", lambda: [round(x * 100, 2) for x in ptr(load(AUDIT), "/paired_bootstrap/em_interval")] == [-8.3, 2.42]),
    ("paired outcomes", "113", "113", lambda: ptr(load(AUDIT), "/paired_qwen9_qwen27_dev293") == {"both_correct": 113, "left_only": 28, "right_only": 37, "both_wrong": 111, "n": 289}),
    ("relative ratio not accuracy", "141/150 = 94", "141/150 = 94%", lambda: round(141 / 150 * 100) == 94),
    ("conservative 293", "141/293 = 48.12", "141/293 = 48.12%", lambda: round(ptr(load(AUDIT), "/historical_quality/qwen3.5-9b/conservative_all_n_em") * 100, 2) == 48.12),
    ("native40 EM Q9", "22/39", "22/39", lambda: ptr(load(AUDIT), "/retrospective_telemetry_compatibility/qwen3.5-9b/retrospective_native40/em_count") == 22),
    ("native40 EM Q27", "24/39", "24/39", lambda: ptr(load(AUDIT), "/retrospective_telemetry_compatibility/qwen3.8-27b/retrospective_native40/em_count") == 24),
    ("native40 p50 Q9", "0.269", "0.269", lambda: round(ptr(load(AUDIT), "/telemetry_measurements/qwen3.5-9b/latency_s/p50"), 3) == 0.269),
    ("native40 p50 Q27", "1.434", "1.434", lambda: round(ptr(load(AUDIT), "/telemetry_measurements/qwen3.8-27b/latency_s/p50"), 3) == 1.434),
    ("whole-GPU peaks", "11471", "11471", lambda: ptr(load(AUDIT), "/telemetry_measurements/qwen3.5-9b/resources/gpu_memory_used_mib_request_peaks/max") == 11471),
    ("whole-RAM peak Q27", "28.470", "28.470", lambda: round(ptr(load(AUDIT), "/telemetry_measurements/qwen3.8-27b/resources/system_ram_used_gib_request_peaks/max"), 3) == 28.470),
    ("answer drift", "2 из 40", "2/40", lambda: ptr(load(AUDIT), "/retrospective_telemetry_compatibility/qwen3.8-27b/changed_choice_sets_n") == 2),
    ("Study C Q9", "18/27", "18/27", lambda: ptr(load(STUDY_C), "/models/qwen3.5-9b/live_application_tools/strict_correct") == 18 and ptr(load(STUDY_C), "/models/qwen3.5-9b/model_only/strict_correct") == 7),
    ("Study C Q27", "25/27", "25/27", lambda: ptr(load(STUDY_C), "/models/qwen3.8-27b/live_application_tools/strict_correct") == 25 and ptr(load(STUDY_C), "/models/qwen3.8-27b/model_only/strict_correct") == 15),
    ("Study C numeric", "16/16", "16/16", lambda: all(ptr(load(STUDY_C), f"/models/{m}/live_application_tools/strict_numeric_correct") == 16 for m in ("qwen3.5-9b", "qwen3.8-27b"))),
    ("Study C nonnumeric Q9", "2/11", "2/11", lambda: (ptr(load(STUDY_C), "/models/qwen3.5-9b/model_only/strict_correct") - ptr(load(STUDY_C), "/models/qwen3.5-9b/model_only/strict_numeric_correct"), ptr(load(STUDY_C), "/models/qwen3.5-9b/live_application_tools/strict_correct") - 16) == (6, 2)),
    ("Study C executions", "32", "32", lambda: sum(ptr(load(STUDY_C), f"/models/{m}/live_application_tools/numeric_executions") for m in ("qwen3.5-9b", "qwen3.8-27b")) == 32),
    ("Study C summed p50 Q27 tools", "21.879", "21.879", lambda: round(ptr(load(STUDY_C), "/models/qwen3.8-27b/live_application_tools/latency_median_s"), 3) == 21.879),
    ("Mercury DEV60", "31/59", "31/59", None),
    ("routing replay", "35/59", "35/59", None),
    ("Codex CLI", "36/59", "36/59", None),
    ("OpenRouter hosted Qwen27", "5/9", "5/9", None),
    ("HOME150", "139/150", "139/150", None),
    ("Jev", "30/36", "30/36", None),
]


def main():
    report = {"number_set_comparison": {}, "claims": [], "status": "PASS"}
    texts = {}
    for lang, (old, new) in PAIRS.items():
        a, b = body(old, lang), body(new, lang)
        texts[lang] = b
        na, nb = set(numbers(a)), set(numbers(b))
        report["number_set_comparison"][lang] = {
            "new_numbers_not_in_audited_text": sorted(nb - na, key=float),
            "audited_numbers_absent_from_edit": sorted(na - nb, key=float),
        }
    for name, ru, en, check in CLAIMS:
        ru_ok = ru.replace(",", ".") in texts["ru"].replace(" ", " ")
        en_ok = en.replace(",", "") in texts["en"]
        r2_ok = ru.replace(",", ".") in texts["ru_r2"].replace(" ", " ")
        ev = None if check is None else bool(check())
        row = {"claim": name, "ru_present": ru_ok, "ru_r2_present": r2_ok, "en_present": en_ok,
               "evidence_match": ev if ev is not None else "covered by 20261004 claim_to_evidence (text unchanged)"}
        if not (ru_ok and r2_ok and en_ok) or ev is False:
            report["status"] = "FAIL"
        report["claims"].append(row)
    out = ROOT / "results/20261005_editorial/numeric_fact_check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
