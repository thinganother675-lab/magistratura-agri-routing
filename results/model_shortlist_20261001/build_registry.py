"""Curate the metadata-only shortlist. All memory ranges are estimates, not runs."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ROWS = [
    (1, "Qwen/Qwen3.5-4B", "bartowski/Qwen_Qwen3.5-4B-GGUF", "Qwen_Qwen3.5-4B-Q8_0.gguf",
     "Q8_0", "small_multilingual_q8", 4.0, None, [5, 7], [6, 9], 262144,
     "Official LM Studio family listing; this pinned quantization NOT TESTED", "https://lmstudio.ai/models/qwen3.5"),
    (2, "microsoft/Phi-4-mini-instruct", "bartowski/microsoft_Phi-4-mini-instruct-GGUF", "microsoft_Phi-4-mini-instruct-Q8_0.gguf",
     "Q8_0", "small_typed_tool_router", 3.8, None, [5, 7], [6, 9], 131072,
     "UNKNOWN on installed LM Studio runtime; public GGUF exists", "https://arxiv.org/abs/2503.01743"),
    (3, "microsoft/bitnet-b1.58-2B-4T", "microsoft/bitnet-b1.58-2B-4T-gguf", "ggml-model-i2_s.gguf",
     "native_W1.58A8_I2_S", "cpu_native_ternary_baseline", 2.41282048, None, [0, 0], [2, 5], 4096,
     "UNKNOWN in LM Studio; official bitnet.cpp CPU path, Windows build NOT TESTED", "https://arxiv.org/abs/2504.12285"),
    (4, "CohereLabs/tiny-aya-global", "CohereLabs/tiny-aya-global-GGUF", "tiny-aya-global-q8_0.gguf",
     "Q8_0", "russian_multilingual_diversity", 3.35, None, [4, 6], [5, 8], 8192,
     "UNKNOWN on installed LM Studio runtime (cohere2); official GGUF exists", "https://arxiv.org/abs/2603.11510"),
    (5, "google/gemma-4-E4B-it", "unsloth/gemma-4-E4B-it-GGUF", "gemma-4-E4B-it-Q8_0.gguf",
     "Q8_0", "small_effective_compute_q8", 8.0, 4.5, [9, 12], [10, 14], 131072,
     "Official LM Studio E4B listing; this pinned quantization NOT TESTED", "https://arxiv.org/abs/2607.02770"),
    (6, "HuggingFaceTB/SmolLM3-3B", "bartowski/HuggingFaceTB_SmolLM3-3B-GGUF", "HuggingFaceTB_SmolLM3-3B-Q8_0.gguf",
     "Q8_0", "small_dense_architecture_control", 3.0, None, [4, 6], [5, 8], 65536,
     "UNKNOWN on installed LM Studio runtime (smollm3); public GGUF exists", "https://huggingface.co/blog/smollm3"),
    (7, "ibm-granite/granite-4.0-h-tiny", "ibm-granite/granite-4.0-h-tiny-GGUF", "granite-4.0-h-tiny-Q8_0.gguf",
     "Q8_0", "hybrid_moe_tool_control", 7.0, 1.0, [8, 11], [9, 13], 131072,
     "UNKNOWN on installed LM Studio runtime (granitehybrid/Mamba2); official GGUF exists", "https://huggingface.co/ibm-granite/granite-4.0-h-tiny"),
    (8, "Qwen/Qwen3-30B-A3B-Instruct-2507", "unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF", "Qwen3-30B-A3B-Instruct-2507-UD-IQ1_S.gguf",
     "UD-IQ1_S_post_training_mixed_precision", "experimental_extreme_quantized_moe", 30.5, 3.3, [10, 13], [11, 16], 262144,
     "UNKNOWN for this pinned IQ1 artifact/runtime; Qwen3 family listed", "https://arxiv.org/abs/2505.09388"),
    (9, "Qwen/Qwen3.5-35B-A3B", "unsloth/Qwen3.5-35B-A3B-GGUF", "Qwen3.5-35B-A3B-UD-IQ2_M.gguf",
     "UD-IQ2_M_post_training_mixed_precision", "same_checkpoint_precision_ablation", 35.0, 3.0, [12, 15], [13, 18], 262144,
     "Qwen3.5 family already loads locally; this pinned IQ2 artifact NOT TESTED", "https://huggingface.co/Qwen/Qwen3.5-35B-A3B"),
]


def read(repo):
    return json.loads((ROOT / "metadata" / (repo.replace("/", "__") + ".json")).read_text(encoding="utf-8"))


def file_record(quant_repo, filename):
    metadata = read(quant_repo)["metadata"]
    f = next(s for s in metadata["siblings"] if s["rfilename"] == filename)
    return {"repo": quant_repo, "revision": metadata["sha"], "filename": filename,
            "size_bytes": f["size"], "size_GB_decimal": f["size"] / 1e9,
            "size_GiB_binary": f["size"] / 2**30, "sha256": f["lfs"]["sha256"],
            "file_url": f"https://huggingface.co/{quant_repo}/blob/{metadata['sha']}/{filename}",
            "created_at": metadata["createdAt"], "last_modified": metadata["lastModified"]}


if __name__ == "__main__":
    candidates = []
    for rank, base_repo, quant_repo, filename, quant, role, total_b, active_b, vram, ram, context, compatibility, source in ROWS:
        base = read(base_repo)["metadata"]
        q = read(quant_repo)["metadata"]
        candidates.append({"rank": rank, "model": base_repo, "base_revision": base["sha"],
            "model_card_url": f"https://huggingface.co/{base_repo}/blob/{base['sha']}/README.md",
            "base_created_at": base["createdAt"], "base_last_modified": base["lastModified"],
            "logical_params_B_reported": total_b, "effective_or_active_params_B": active_b,
            "safetensors_metadata": base.get("safetensors"),
            "license_base_card": base.get("cardData", {}).get("license"),
            "license_quant_card": q.get("cardData", {}).get("license"),
            "quantization": quant, "scientific_role": role, "file": file_record(quant_repo, filename),
            "context_reported_or_config_tokens": context, "context_proposed_tokens": 4096,
            "memory_estimate_context": "one sequential text-only instance, 4096 context, no vision projector",
            "memory_estimate_method": "planning range from GGUF bytes plus KV/recurrent state and backend buffers; not measured",
            "estimated_incremental_vram_GiB": vram, "estimated_incremental_cpu_mode_ram_GiB": ram,
            "compatibility_status": compatibility, "source": source,
            "download_status": "NOT DOWNLOADED", "load_status": "NOT RUN", "inference_status": "NOT RUN",
            "ru_agricultural_quality": "NOT MEASURED"})
    bitnet_bf16 = read("microsoft/bitnet-b1.58-2B-4T-bf16")["metadata"]
    registry = {"research_as_of": "2026-10-01", "status": "METADATA ONLY, NO WEIGHTS, NO INFERENCE",
        "hardware_snapshot_source": "results/hardware/home_pc_2026-10-01.json",
        "hardware_measured": {"cpu": "AMD Ryzen 7 8700F", "vram_MiB": 16311,
                              "ram_GiB": 31.62, "c_free_GiB_at_snapshot": 77.74},
        "candidates": candidates,
        "first_three_weight_bytes": sum(c["file"]["size_bytes"] for c in candidates[:3]),
        "all_nine_weight_bytes": sum(c["file"]["size_bytes"] for c in candidates),
        "bitnet_logical_parameter_evidence": {"repo": bitnet_bf16["id"], "revision": bitnet_bf16["sha"],
            "safetensors": bitnet_bf16.get("safetensors"), "weights_downloaded": False,
            "note": "Packed U8 tensor element count is not a logical parameter count."},
        "extreme_quant_alternatives": [file_record("unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF", f)
            for f in ["Qwen3-30B-A3B-Instruct-2507-UD-IQ1_M.gguf", "Qwen3-30B-A3B-Instruct-2507-UD-TQ1_0.gguf"]],
        "domain_deferred": {"model": "Xianjun/PLLaMa-7b-instruct", "revision": read("Xianjun/PLLaMa-7b-instruct")["metadata"]["sha"],
            "source": "https://arxiv.org/abs/2401.01600", "status": "DEFERRED, NOT DOWNLOADED, NOT RUN",
            "reason": "Base LLaMA-2; HF Apache-2.0 metadata conflicts with incomplete license card; trusted GGUF and Russian evaluation not verified."},
        "sources": [
            {"url": "https://lmstudio.ai/models/qwen3.5", "type": "official_model_compatibility_catalog"},
            {"url": "https://lmstudio.ai/models/gemma-4", "type": "official_model_compatibility_catalog"},
            {"url": "https://lmstudio.ai/docs/app/basics/download-model", "type": "official_download_and_quantization_docs"},
            {"url": "https://github.com/microsoft/BitNet", "type": "official_software_instructions_not_scientific_citation"},
            {"url": "https://arxiv.org/abs/2504.12285", "type": "technical_report_abstract_and_card_cross_check"},
            {"url": "https://arxiv.org/abs/2503.01743", "type": "technical_report_abstract_and_card_cross_check"},
            {"url": "https://arxiv.org/abs/2603.11510", "type": "technical_report_abstract_and_card_cross_check"},
            {"url": "https://arxiv.org/abs/2607.02770", "type": "technical_report_entry_and_card_cross_check"},
            {"url": "https://huggingface.co/blog/smollm3", "type": "official_training_and_evaluation_blog"},
            {"url": "https://arxiv.org/abs/2401.01600", "type": "domain_paper_abstract_and_card_cross_check"}],
        "limitations": ["No new model has been downloaded or run.",
            "Published base benchmarks are not quality measurements for these quantizations or this agriculture benchmark.",
            "Planning memory ranges are not observed peaks; inspect free resources before any load.",
            "HF revision is not proof of the quantizer's exact upstream conversion revision.",
            "Public metadata/config requests use no credential. Tiny Aya base config was gated; no bypass attempted."]}
    (ROOT / "primary_sources_registry.json").write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (ROOT / "download_candidates.tsv").open("w", encoding="utf-8", newline="") as stream:
        fields = ["rank", "model", "quant_repo", "revision", "filename", "size_bytes", "sha256", "file_url", "status"]
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for candidate in candidates:
            f = candidate["file"]
            writer.writerow({"rank": candidate["rank"], "model": candidate["model"], "quant_repo": f["repo"],
                "revision": f["revision"], "filename": f["filename"], "size_bytes": f["size_bytes"],
                "sha256": f["sha256"], "file_url": f["file_url"], "status": "NOT DOWNLOADED / NOT RUN"})
    manifest = []
    for file in sorted((ROOT / "metadata").glob("*.json")):
        manifest.append({"path": file.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                         "size_bytes": file.stat().st_size})
    (ROOT / "metadata_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"candidates": len(candidates), "first3_bytes": registry["first_three_weight_bytes"],
                      "all9_bytes": registry["all_nine_weight_bytes"], "metadata_files": len(manifest)}))
