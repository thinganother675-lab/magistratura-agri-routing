"""Versioned exploratory Q8 development baseline; old protocols stay immutable.

Imports the historical controlled DEV API payload/scorer and memory guards.
Only this controller may load/unload LM Studio. Downloads/builds must finish
before --run. The 150-item historical holdout is never read by this script.
"""
from __future__ import annotations

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import struct
import subprocess
import sys
import time
import uuid

import httpx
import home_lm_api_benchmark as api
import home_pc_benchmark as old
from agro_route.evaluation import score
from agro_route.home_config import resolve_api_key
from agro_route.models import SYSTEM_PROMPT

ROOT = Path(__file__).resolve().parents[1]
BASELINES = {
    "qwen": {"repo": "unsloth/Qwen3.5-4B-GGUF", "revision": "e87f176479d0855a907a41277aca2f8ee7a09523",
             "base_model": "Qwen/Qwen3.5-4B", "base_revision": "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a",
             "filename": "Qwen3.5-4B-Q8_0.gguf", "size": 4482403488,
             "sha256": "10cc391b403021dd11c614679d2fd92f611c3681d29e29651b717316965d61e1",
             "license": "apache-2.0", "model_key": "qwen3.5-4b", "gpu": "max"},
    "phi": {"repo": "unsloth/Phi-4-mini-instruct-GGUF", "revision": "78eb92a46fc37e6b524df991ed9aca9bc6aa7b80",
            "base_model": "microsoft/Phi-4-mini-instruct", "base_revision": "cfbefacb99257ffa30c83adab238a50856ac3083",
            "filename": "Phi-4-mini-instruct.Q8_0.gguf", "size": 4084611040,
            "sha256": "26188c6050d525376a88b04514c236c5e28a36730f1e936f2a00314212b7ba42",
            "license": "mit", "model_key": "phi-4-mini-instruct", "gpu": "max"},
}
BITNET = {"repo": "microsoft/bitnet-b1.58-2B-4T-gguf",
          "revision": "a1f2f1c765812aa8af3f6eda4a313707064bba15",
          "filename": "ggml-model-i2_s.gguf", "size": 1187801280,
          "sha256": "4221b252fdd5fd25e15847adfeb5ee88886506ba50b8a34548374492884c2162",
          "license": "mit", "quantization": "I2_S native ternary W1.58A8"}

PUBLIC_DOWNLOADS = {
    "qwen": {"url": "https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/e87f176479d0855a907a41277aca2f8ee7a09523/Qwen3.5-4B-Q8_0.gguf",
             "size": BASELINES["qwen"]["size"], "sha256": BASELINES["qwen"]["sha256"],
             "target": ".runtime/local_baselines/Qwen3.5-4B-Q8_0.gguf"},
    "bitnet": {"url": "https://huggingface.co/microsoft/bitnet-b1.58-2B-4T-gguf/resolve/a1f2f1c765812aa8af3f6eda4a313707064bba15/ggml-model-i2_s.gguf",
               "size": BITNET["size"], "sha256": BITNET["sha256"], "target": ".runtime/bitnet/models/BitNet-b1.58-2B-4T/ggml-model-i2_s.gguf"},
    "llvm": {"url": "https://github.com/mstorsjo/llvm-mingw/releases/download/20260922/llvm-mingw-20260922-ucrt-x86_64.zip",
             "size": 190725905, "sha256": "e3ad77d117a4bea19a7a3b333341824d79a5a371004a10e25b8504e7b3047666",
             "target": ".runtime/bitnet/llvm-mingw-20260922-ucrt-x86_64.zip"},
}


def derive_backend_metrics(directory, name, log_path):
    """Read-only exact-instance/count/token/time alignment; never export log text."""
    directory, log_path = Path(directory), Path(log_path)
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    model = manifest["models"][name]
    own = model["own_instance_id"]
    raw_path = directory / (name + "_raw.jsonl")
    raw = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines() if line]
    content = log_path.read_bytes()
    blocks, active = [], None
    marker = re.compile(r"^\[?(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]?\s*\[(?:INFO|DEBUG)\]\s*\[([^\]]+)\]\s+(Running chat|Finished)")
    metric = re.compile(r"(prompt eval|eval) time\s*=\s*([\d.]+) ms\s*/\s*(\d+) tokens\s*\(\s*([\d.]+) ms per token,\s*([\d.]+) tokens per second\)")
    for number, line in enumerate(content.decode("utf-8", errors="replace").splitlines(), 1):
        match = marker.search(line)
        if match and match[3] == "Running chat":
            if active:
                blocks.append(active)
            active = {"start": number, "timestamp": match[1], "finished": False, "prompt": [], "decode": [], "total": []} if match[2] == own else None
        if active:
            timing = metric.search(line)
            if timing:
                active["prompt" if timing[1] == "prompt eval" else "decode"].append({"line": number, "ms": float(timing[2]), "tokens": int(timing[3]), "tps": float(timing[5])})
            total = re.search(r"total time\s*=\s*([\d.]+) ms\s*/\s*(\d+) tokens", line)
            if total:
                active["total"].append({"ms": float(total[1]), "tokens": int(total[2])})
            if match and match[3] == "Finished":
                active.update(end=number, finished=match[2] == own)
                blocks.append(active)
                active = None
    if active:
        blocks.append(active)
    details = []
    for i, row in enumerate(raw):
        block = blocks[i] if i < len(blocks) else {}
        usage = row["local"].get("usage", {})
        created = next((e["data"]["created"] for e in row["local"].get("raw", {}).get("events", []) if isinstance(e.get("data", {}).get("created"), (int, float))), None)
        log_as_utc = datetime.strptime(block["timestamp"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp() if block.get("timestamp") else None
        prompt, decode, total = block.get("prompt", []), block.get("decode", []), block.get("total", [])
        checks = {"count_exact": len(blocks) == len(raw), "own_begin_finish": bool(block.get("finished")),
                  "one_prompt_decode": len(prompt) == len(decode) == 1,
                  "completion_tokens_exact": len(decode) == 1 and decode[0]["tokens"] == usage.get("completion_tokens"),
                  "timestamp_utc_plus3": created is not None and log_as_utc is not None and abs(log_as_utc - created - 10800) <= 1,
                  "prefill_subset": len(prompt) == 1 and prompt[0]["tokens"] <= usage.get("prompt_tokens", -1),
                  "total_token_arithmetic": len(total) == len(prompt) == len(decode) == 1 and total[0]["tokens"] == prompt[0]["tokens"] + decode[0]["tokens"]}
        valid = all(checks.values())
        details.append({"sample_id": row["sample"]["id"], "request_index": i, "valid": valid, "checks": checks,
                        "line_start": block.get("start"), "line_end": block.get("end"), "usage": usage,
                        "prompt_eval": prompt[0] if valid else None, "decode": decode[0] if valid else None})
    complete = bool(details) and all(d["valid"] for d in details)
    before = {p["Id"] for p in model.get("processes_before_load", {}).get("rows", []) if p.get("ProcessName") == "llama-server"}
    after = [p for p in model.get("processes_after_inference", {}).get("rows", []) if p.get("ProcessName") == "llama-server" and p["Id"] not in before]
    association = {"status": "INFERRED_UNIQUE_NEW_BACKEND" if len(after) == 1 else "UNKNOWN", "processes": after if len(after) == 1 else [],
                   "limitation": "OS process snapshot and exclusive API instance; native API does not expose process PID"}
    result = {"status": "LOG_DERIVED_AUXILIARY_ONLY", "instance": own, "n": len(raw), "log_block_n": len(blocks),
              "complete_alignment": complete, "unambiguously_aligned_n": sum(d["valid"] for d in details),
              "log_sha256": hashlib.sha256(content).hexdigest(), "log_size": len(content), "log_path": str(log_path),
              "manifest_sha256": digest(manifest_path), "raw_sha256": digest(raw_path),
              "backend_decode_tps_median": statistics.median(d["decode"]["tps"] for d in details) if complete else None,
              "backend_prompt_eval_tps_median": statistics.median(d["prompt_eval"]["tps"] for d in details) if complete else None,
              "backend_ttft_s": None, "actual_offloaded_layers": "UNKNOWN", "backend_process_association": association,
              "limitation": "Prefill token count is an uncached subset, never substitutes full input usage. Native TTFT/GPU layer count remain UNKNOWN. Log request times align UTC+03 within1s. Client TPS remains separately approximate.", "requests": details}
    output = directory / (name + "_backend_log_auxiliary.json")
    if output.exists():
        raise RuntimeError("Preserve existing derived evidence; choose a new analysis file")
    write(output, result)
    print(json.dumps({k: result[k] for k in ("n", "complete_alignment", "unambiguously_aligned_n", "backend_decode_tps_median", "backend_prompt_eval_tps_median")}), flush=True)
    return result


def resume_public_download(name):
    """Four bounded public HTTP ranges, exact-size/checksum-gated publication.

    No authentication, model execution or provider inference. Checkpoints are
    retained on failure. A matching finished artifact is reused without transfer.
    """
    spec = PUBLIC_DOWNLOADS[name]
    target = ROOT / spec["target"]
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.stat().st_size == spec["size"] and digest(target) == spec["sha256"]:
            print(json.dumps({"download": name, "status": "ALREADY_VERIFIED"}), flush=True)
            return target
        raise RuntimeError("Existing final artifact differs; preserve it and inspect")
    part = target.with_name(target.name + ".part")
    if name == "bitnet" and not part.exists():
        prior = sorted((target.parent / ".cache/huggingface/download").glob("*" + spec["sha256"] + "*.incomplete"), key=lambda p: p.stat().st_size, reverse=True)
        if prior and prior[0].stat().st_size:
            prior[0].rename(part)  # Same isolated workspace; all HF transfers stopped.
    if not part.exists():
        part.touch(exist_ok=False)
    prefix = part.stat().st_size
    if prefix > spec["size"]:
        raise RuntimeError("Partial file exceeds declared artifact size")
    chunks = target.with_name(target.name + ".range-checkpoints")
    chunks.mkdir(exist_ok=True)
    plan = [(index, start, min(spec["size"] - 1, start + 64 * 1024 * 1024 - 1))
            for index, start in enumerate(range(prefix, spec["size"], 64 * 1024 * 1024))]
    plan_file = chunks / "plan.json"
    current_plan = {"artifact": name, "prefix_bytes": prefix, "size": spec["size"], "sha256": spec["sha256"], "ranges": plan}
    if plan_file.exists() and json.loads(plan_file.read_text()) != json.loads(json.dumps(current_plan)):
        raise RuntimeError("Range checkpoint plan differs; retain and inspect before resume")
    write(plan_file, current_plan)
    started = time.perf_counter()
    def transfer(item):
        index, start, end = item
        path = chunks / f"{index:04d}_{start}_{end}.part"
        length = end - start + 1
        offset = path.stat().st_size if path.exists() else 0
        if offset > length:
            raise RuntimeError("Range checkpoint too large")
        for attempt in range(2):
            if offset == length:
                return
            try:
                with httpx.Client(timeout=httpx.Timeout(60, connect=30), follow_redirects=True) as client:
                    with client.stream("GET", spec["url"], headers={"Range": f"bytes={start + offset}-{end}"}) as response:
                        if response.status_code == 429:
                            retry = response.headers.get("retry-after", "1")
                            time.sleep(min(60, max(1, float(retry) if retry.isdecimal() else 1)))
                            continue
                        response.raise_for_status()
                        expected = f"bytes {start + offset}-{end}/{spec['size']}"
                        if response.status_code != 206 or response.headers.get("content-range") != expected:
                            raise RuntimeError("Server did not honor exact requested range")
                        with path.open("ab") as handle:
                            for block in response.iter_bytes(1024 * 1024):
                                if offset + len(block) > length:
                                    raise RuntimeError("Range body exceeds declared length")
                                handle.write(block)
                                handle.flush()
                                offset += len(block)
                if offset != length:
                    raise RuntimeError("Short range response")
                print(json.dumps({"download": name, "range": index, "range_bytes": length, "status": "RANGE_DONE"}), flush=True)
                return
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError):
                if attempt:
                    raise
        raise RuntimeError("Bounded public download attempts exhausted")
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(transfer, plan))
    # Assemble to a new file so failed assembly never destroys the prefix.
    assembled = target.with_name(target.name + ".assembled.part")
    with assembled.open("wb") as handle:
        for source in [part, *(chunks / f"{i:04d}_{start}_{end}.part" for i, start, end in plan)]:
            with source.open("rb") as raw:
                for block in iter(lambda: raw.read(4 * 1024 * 1024), b""):
                    handle.write(block)
    if assembled.stat().st_size != spec["size"] or digest(assembled) != spec["sha256"]:
        raise RuntimeError("Final public artifact checksum/size mismatch")
    assembled.rename(target)
    print(json.dumps({"download": name, "status": "CHECKSUM_VERIFIED", "bytes": spec["size"], "elapsed_s": time.perf_counter() - started, "target": str(target)}), flush=True)
    return target


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def snapshot_sources(directory):
    """Preserve exact driver/imported helpers before any model request."""
    sources = [Path(__file__), Path(api.__file__), Path(old.__file__),
               *(ROOT / "src/agro_route" / name for name in ("models.py", "routing.py", "evaluation.py", "tools.py", "home_config.py"))]
    target = Path(directory) / "source_snapshot"
    target.mkdir(exist_ok=False)
    result = {}
    for source in sources:
        raw = source.read_bytes()
        (target / source.name).write_bytes(raw)
        result[str(source.relative_to(ROOT))] = {"sha256": hashlib.sha256(raw).hexdigest(), "snapshot": "source_snapshot/" + source.name}
    return result


def read_gguf_identity(path):
    """Metadata/tensor types only; never loads tensor data or exports vocab."""
    allowed = {"general.architecture", "general.name", "general.file_type", "tokenizer.ggml.model", "tokenizer.ggml.pre", "tokenizer.ggml.bos_token_id", "tokenizer.ggml.eos_token_id", "tokenizer.ggml.add_bos_token", "tokenizer.ggml.add_eos_token", "tokenizer.chat_template"}
    formats = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}
    with Path(path).open("rb") as handle:
        def number(fmt):
            size = struct.calcsize("<" + fmt)
            raw = handle.read(size)
            if len(raw) != size:
                raise RuntimeError("Truncated GGUF metadata")
            return struct.unpack("<" + fmt, raw)[0]
        def string():
            size = number("Q")
            if size > 16 * 1024 * 1024:
                raise RuntimeError("GGUF metadata string bound exceeded")
            raw = handle.read(size)
            if len(raw) != size:
                raise RuntimeError("Truncated GGUF string")
            return raw.decode("utf-8", errors="replace")
        def value(kind):
            if kind in formats:
                return number(formats[kind])
            if kind == 8:
                return string()
            if kind == 9:
                subtype, count = number("I"), number("Q")
                if count > 2_000_000 or subtype == 9:
                    raise RuntimeError("GGUF metadata array bound exceeded")
                for _ in range(count):
                    value(subtype)
                return "ARRAY_OMITTED"
            raise RuntimeError("Unsupported GGUF metadata scalar type")
        if handle.read(4) != b"GGUF":
            raise RuntimeError("Not a GGUF file")
        version, tensors, count = number("I"), number("Q"), number("Q")
        if version not in (2, 3) or tensors > 100_000 or count > 100_000:
            raise RuntimeError("Unsupported GGUF header bounds")
        metadata = {}
        for _ in range(count):
            key = string()
            entry = value(number("I"))
            if key in allowed or key.endswith(".context_length") or key.endswith(".block_count"):
                metadata[key] = entry
        types = {}
        for _ in range(tensors):
            string()  # Name omitted; only counts are exported.
            dimensions = number("I")
            if dimensions > 8:
                raise RuntimeError("Unsupported GGUF tensor dimension count")
            for _ in range(dimensions):
                number("Q")
            kind = number("I")
            number("Q")
            types[str(kind)] = types.get(str(kind), 0) + 1
        return {"gguf_version": version, "tensor_count": tensors, "metadata": metadata, "tensor_type_counts": types,
                "native_bitnet_i2_s_type36": types.get("36", 0), "tensor_data_read": False,
                "type36_source": "pinned official BitNet llama.cpp ggml/include/ggml.h GGML_TYPE_I2_S=36"}


def diagnose_bitnet_tokenizer(server_path, model_path):
    """One native metadata override, fixed tokenization probes; no generation."""
    if Path(model_path).stat().st_size != BITNET["size"] or digest(model_path) != BITNET["sha256"]:
        raise RuntimeError("Native weight checksum mismatch")
    # Only the isolated reference tokenizer package; no Transformers/PyTorch.
    sys.path.insert(0, str(ROOT / ".runtime/bitnet/.venv/Lib/site-packages"))
    import tokenizers
    folder = ROOT / "results/20261002T170300Z_02a39af9_requested_local_metadata/bitnet_tokenizer_diagnostic"
    tokenizer_path = ROOT / ".runtime/bitnet/tokenizer-reference/tokenizer.json"
    expected = {"config.json": "2b43e80788972e6d53967b01ac3609d7df23cf0aabb0c866e51be694a59c1149",
                "tokenizer_config.json": "d27b698683435b0b0dd544a591a30196b2b63f5fd4c8c64b9060a84dc185386f",
                "special_tokens_map.json": "462d91939dbc37178aa5a3eae7068d1990ccc92e09f288cc71f42cdf139d69cc"}
    if any(digest(folder / name) != sha for name, sha in expected.items()) or digest(tokenizer_path) != "e134af98b985517b4f068e3755ae90d4e9cd2d45d328325dc503f1c6b2d06cc7":
        raise RuntimeError("Pinned official reference tokenizer differs")
    config = json.loads((folder / "tokenizer_config.json").read_text(encoding="utf-8"))
    hf = tokenizers.Tokenizer.from_file(str(tokenizer_path))
    hf_metadata = json.loads(tokenizer_path.read_text(encoding="utf-8"))
    regex = hf_metadata["pre_tokenizer"]["pretokenizers"][0]["pattern"]["Regex"]
    vocab_source = ROOT / ".runtime/bitnet/BitNet/3rdparty/llama.cpp/src/llama-vocab.cpp"
    code = vocab_source.read_text(encoding="utf-8")
    part = code.split("case LLAMA_VOCAB_PRE_TYPE_LLAMA3:", 1)[1].split("break;", 1)[0]
    original_regex_line = next(line.strip()[2:].strip().rstrip(",") for line in part.splitlines() if line.strip().startswith('//"(?i:'))
    if json.loads(original_regex_line) != regex or config["eos_token"] != "<|eot_id|>" or hf.token_to_id(config["eos_token"]) != 128009:
        raise RuntimeError("Official pre-tokenizer/EOS verification failed")
    converter = ROOT / ".runtime/bitnet/BitNet/utils/convert-hf-to-gguf-bitnet.py"
    syntax = ast.parse(converter.read_text(encoding="utf-8"))
    converter_probe = next(ast.literal_eval(node.value) for node in ast.walk(syntax) if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "chktxt" for t in node.targets))
    hf_hash = hashlib.sha256(str(hf.encode(converter_probe).ids).encode()).hexdigest()
    if hf_hash != "0ef9807a4087ebef797fc749390439009c3b9eda9ad1a097abbe738f486c01e5":
        raise RuntimeError("Official converter llama-bpe fingerprint did not match")
    template_file = folder / "official_chat_template_v1.jinja"
    if template_file.exists() and template_file.read_text(encoding="utf-8") != config["chat_template"]:
        raise RuntimeError("Preserve existing template; do not overwrite another variant")
    template_file.write_text(config["chat_template"], encoding="utf-8")
    overrides = "tokenizer.ggml.pre=str:llama-bpe,tokenizer.ggml.eos_token_id=int:128009,tokenizer.ggml.add_bos_token=bool:false,tokenizer.ggml.add_eos_token=bool:false"
    probe_texts = ["Calculate growing degree days with Tmin=10, Tmax=20, base=8.",
                   "Каких данных не хватает для расчёта дефицита осадков?",
                   "\n \n\n \t \t\t A  B\r\nC", "3 33 333 3333 3.3 -0.25 2026-10-02 19:00",
                   "I've been told he's there; 'RE you sure? 🚀 ✅", "<|begin_of_text|>System: Hello<|eot_id|>User: Привет<|eot_id|>Assistant: ", converter_probe]
    args = [str(Path(server_path).resolve()), "-m", str(Path(model_path).resolve()), "--alias", "bitnet-tokenizer-parity-v1",
            "--host", "127.0.0.1", "--port", "1235", "-c", "4096", "-t", "4", "-tb", "4", "-np", "1", "-ngl", "0", "--no-warmup",
            "--override-kv", overrides, "--chat-template-file", str(template_file)]
    log_path = folder / "native_tokenizer_parity_v1_log.txt"
    report_path = folder / "native_tokenizer_parity_v1.json"
    if report_path.exists() or log_path.exists():
        raise RuntimeError("This one diagnostic was already attempted; preserve it")
    key, _ = resolve_api_key("local")
    with httpx.Client(timeout=5, trust_env=False) as client:
        if any(m.get("loaded_instances") for m in api.native_models(client, key)):
            raise RuntimeError("Other LM Studio instance present")
        try:
            client.get("http://127.0.0.1:1235/health")
        except httpx.ConnectError:
            pass
        else:
            raise RuntimeError("Diagnostic port occupied")
    report = {"phase": "NON_GENERATIVE_TOKENIZER_PARITY_ONLY", "started_utc": old.now(), "generation_requests": 0,
              "official_model_revision": "04c3b9ad9361b824064a1f25ea60a8be9599b127", "official_tokenizer_sha256": digest(tokenizer_path),
              "reference_config_sha256": expected, "tokenizers_version": tokenizers.__version__, "pre_tokenizer_regex_exact": True,
              "official_converter_probe_hash": hf_hash, "converter_sha256": digest(converter), "native_vocab_source_sha256": digest(vocab_source),
              "weight_sha256": BITNET["sha256"], "server_sha256": digest(server_path), "header": read_gguf_identity(model_path),
              "runtime_overrides": overrides, "template_file": str(template_file.relative_to(ROOT)), "template_sha256": digest(template_file),
              "official_special_map_discrepancy": "special_tokens_map eos end_of_text128001; tokenizer_config eos eot_id128009; inference config uses tokenizer_config and its exact template", "probes": [], "format_probes": []}
    process = None
    try:
        with log_path.open("x", encoding="utf-8") as log:
            process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT)
            report["own_pid"] = process.pid
            started = time.perf_counter()
            with httpx.Client(timeout=10, trust_env=False) as client:
                while True:
                    if process.poll() is not None or time.perf_counter() - started > 60:
                        raise RuntimeError("Non-generative diagnostic server unavailable")
                    try:
                        if client.get("http://127.0.0.1:1235/health").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(.2)
                for index, text in enumerate(probe_texts):
                    expected_ids = hf.encode(text, add_special_tokens=False).ids
                    result = client.post("http://127.0.0.1:1235/tokenize", json={"content": text, "add_special": False, "parse_special": True})
                    result.raise_for_status()
                    ids = result.json()["tokens"]
                    report["probes"].append({"index": index, "text": text, "reference_ids": expected_ids, "native_ids": ids, "exact": ids == expected_ids})
                conversations = [[{"role": "system", "content": "Return clear agricultural guidance."}, {"role": "user", "content": " Какие данные нужны? "}],
                                 [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Привет"}, {"role": "user", "content": "  What next?\n"}]]
                for index, messages in enumerate(conversations):
                    expected_prompt = "".join(m["role"].capitalize() + ": " + m["content"].strip() + "<|eot_id|>" for m in messages) + "Assistant: "
                    response = client.post("http://127.0.0.1:1235/apply-template", json={"messages": messages, "model": "bitnet-tokenizer-parity-v1"})
                    response.raise_for_status()
                    prompt = response.json()["prompt"]
                    encoded = client.post("http://127.0.0.1:1235/tokenize", json={"content": prompt, "add_special": True, "parse_special": True})
                    encoded.raise_for_status()
                    reference_ids = hf.encode(expected_prompt, add_special_tokens=False).ids
                    report["format_probes"].append({"index": index, "reference_prompt": expected_prompt, "native_prompt": prompt,
                                                     "format_exact": prompt == expected_prompt, "token_ids_exact": encoded.json()["tokens"] == reference_ids,
                                                     "reference_ids": reference_ids, "native_ids": encoded.json()["tokens"]})
        report["parity_complete"] = all(p["exact"] for p in report["probes"]) and all(p["format_exact"] and p["token_ids_exact"] for p in report["format_probes"])
    except (RuntimeError, OSError, httpx.HTTPError) as exc:
        report.update(parity_complete=False, error_type=type(exc).__name__)
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        report["own_cleanup_confirmed"] = process is None or process.poll() is not None
        raw_log = log_path.read_bytes() if log_path.exists() else b""
        report["generation_log_markers_absent"] = b"prompt eval time" not in raw_log and b"processing task" not in raw_log
        report["native_log_sha256"] = hashlib.sha256(raw_log).hexdigest()
        report["finished_utc"] = old.now()
        write(report_path, report)
    if report["parity_complete"] and report["own_cleanup_confirmed"] and report["generation_log_markers_absent"]:
        protocol = {"version": "BITNET_HF_RUNTIME_OVERRIDE_V1", "state": "FROZEN_AFTER_PARITY_PENDING_ROOT_REVIEW", "created_utc": old.now(),
                    "phase": "DEV_CONFIGURATION_CHANGE_NOT_NEW_HOLDOUT", "original_weight_sha256": BITNET["sha256"],
                    "parity_report": str(report_path.relative_to(ROOT)), "parity_report_sha256": digest(report_path),
                    "reference_revision": report["official_model_revision"], "runtime_overrides": overrides,
                    "template_file": str(template_file.relative_to(ROOT)), "template_sha256": digest(template_file),
                    "parameters": {"cpu_threads": 4, "threads_batch": 4, "context": 4096, "parallel": 1, "gpu_layers": 0,
                                   "temperature": 0, "seed": 42, "max_tokens": 512, "top_p": 1, "warmup": False, "response_cache": False,
                                   "prefix_kv_cache": "runtime default enabled; usage.cache_n and prompt_n recorded"},
                    "extension_rule": "DEV12 correct>=6/12 and completion errors<=2/12 then append remaining24 once; no repeats",
                    "legacy_smoke_preserved": "results/20261002T185320Z_1027a4c6_bitnet_native_dev", "quality_trial": "NOT_RUN_WAITING_ROOT_GRANT"}
        write(folder / "BITNET_RUNTIME_OVERRIDE_PROTOCOL_V1.json", protocol)
    print(json.dumps({"parity_complete": report["parity_complete"], "probe_n": len(report["probes"]), "format_probe_n": len(report["format_probes"]),
                      "cleanup": report["own_cleanup_confirmed"], "generation_requests": 0, "directory": str(folder)}), flush=True)
    return report


def write(path, value):
    """Atomic reporting checkpoints; never rewrite raw requests."""
    path = Path(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    for attempt in range(20):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(.25)


def process_snapshot():
    """Backend process working sets, separate from whole-system RAM.

    Runtime PID to model association is UNKNOWN unless subsequently confirmed.
    Only allowlisted local runtime process names are returned; no command lines.
    """
    command = ("Get-Process -ErrorAction SilentlyContinue | Where-Object { "
               "$_.ProcessName -match '^(llama-server|llama-worker|lms|LM Studio|lmstudio.*)$' } | "
               "Select-Object Id,ProcessName,WorkingSet64,PeakWorkingSet64 | ConvertTo-Json -Compress")
    result = old.command(["powershell.exe", "-NoProfile", "-Command", command], timeout=20)
    if result.returncode:
        return {"status": "UNKNOWN", "error_type": "ProcessSnapshotFailed"}
    rows = json.loads(result.stdout or "[]")
    return {"status": "MEASURED", "rows": rows if isinstance(rows, list) else [rows],
            "model_process_association": "UNKNOWN", "scope": "OS process working sets; no command lines"}


def fingerprint(spec, inventory, model_root):
    matches = [m for m in inventory if m.get("path", "").endswith("/" + spec["filename"])]
    if len(matches) != 1:
        raise RuntimeError("Exact requested GGUF missing or ambiguous in LM Studio inventory")
    item = matches[0]
    if (item.get("quantization") or {}).get("name") != "Q8_0":
        raise RuntimeError("Requested ordinary faithful Q8_0 not confirmed")
    path = Path(model_root) / item["path"]
    actual_size, actual_hash = path.stat().st_size, digest(path)
    if actual_size != spec["size"] or actual_hash != spec["sha256"]:
        raise RuntimeError("GGUF checksum or size mismatch; no inference permitted")
    return {**spec, "local_path": str(path), "measured_size": actual_size,
            "measured_sha256": actual_hash, "inventory": item,
            "measured_utc": old.now(), "status": "CHECKSUM_VERIFIED"}


def eligible_extension(rows):
    # Predeclared compact-baseline screen, not a claim of matching larger models.
    return (len(rows) == 12 and sum(r["score"]["correct"] for r in rows) >= 6
            and sum(bool(r["local"]["error"]) for r in rows) <= 2)


def bitnet_request(client, identifier, sample):
    """Same public DEV payload/schema via dedicated native bitnet.cpp server."""
    started = time.perf_counter()
    result = {"output": None, "error": None, "raw": None, "usage": {}, "timing": {}, "cost_usd": 0.0}
    try:
        with client.stream("POST", "http://127.0.0.1:1235/v1/chat/completions", json=api.payload(identifier, sample)) as response:
            response.raise_for_status()
            raw = api.consume_sse(response.iter_lines(), started)
        result.update(raw=raw, usage=raw["usage"], timing=raw["timing"])
        # llama.cpp may expose timings in the same response rather than stats.
        timings = [e["data"].get("timings") for e in raw["events"] if isinstance(e["data"].get("timings"), dict)]
        if timings:
            result["timing"]["native_llama_timings"] = timings[-1]
            result["timing"]["backend_tokens_per_second"] = timings[-1].get("predicted_per_second")
        if raw["event_error"] or not raw["stream_done"] or raw["finish_reason"] != "stop":
            result["error"] = {"type": "IncompleteCompletion", "finish_reason": raw["finish_reason"]}
        else:
            answer = api.parse_output(raw["final_content"])
            if set(answer) != set(api.SCHEMA["required"]):
                raise ValueError("Structured schema mismatch")
            result["output"] = answer
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, RuntimeError) as exc:
        result["error"] = {"type": type(exc).__name__, "http_status": getattr(getattr(exc, "response", None), "status_code", None)}
    result["latency_ms"] = (time.perf_counter() - started) * 1000
    return result


def run_bitnet(server_path, model_path, n=36, runtime_protocol=None):
    if n not in (12, 36):
        raise ValueError("Only DEV12/DEV36 allowed")
    if not Path(server_path).is_file() or not Path(model_path).is_file():
        raise RuntimeError("Build native server and download exact I2_S weights first")
    if Path(model_path).stat().st_size != BITNET["size"] or digest(model_path) != BITNET["sha256"]:
        raise RuntimeError("Native BitNet checksum mismatch")
    # Require no LM Studio model and no occupied own server port.
    key, _ = resolve_api_key("local", env_path=ROOT / ".env")
    with httpx.Client(timeout=10, trust_env=False) as local_client:
        if any(m.get("loaded_instances") for m in api.native_models(local_client, key)):
            raise RuntimeError("LM Studio instance present; CPU baseline waits for a quiet window")
        try:
            local_client.get("http://127.0.0.1:1235/health")
        except httpx.ConnectError:
            pass
        else:
            raise RuntimeError("Native baseline port already occupied; do not stop another server")
    headroom = old.resource_headroom()
    if headroom["ram_available_gib"] < 3:
        raise RuntimeError("Insufficient CPU baseline RAM")
    directory = ROOT / "results" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8] + "_bitnet_native_dev")
    directory.mkdir(exist_ok=False)
    samples = old.choose_samples(n)
    identifier = "bitnet-native-i2s"
    args = [str(Path(server_path).resolve()), "-m", str(Path(model_path).resolve()), "--alias", identifier,
            "--host", "127.0.0.1", "--port", "1235", "-c", "4096", "-t", "4", "-tb", "4", "-np", "1", "-ngl", "0", "--no-warmup"]
    override = None
    if runtime_protocol:
        protocol_path = Path(runtime_protocol).resolve()
        if not protocol_path.is_relative_to(ROOT):
            raise RuntimeError("Runtime protocol must remain in this workspace")
        override = json.loads(protocol_path.read_text(encoding="utf-8"))
        if override.get("version") != "BITNET_HF_RUNTIME_OVERRIDE_V1" or override.get("original_weight_sha256") != BITNET["sha256"]:
            raise RuntimeError("Unexpected native metadata override version/weights")
        expected_override = "tokenizer.ggml.pre=str:llama-bpe,tokenizer.ggml.eos_token_id=int:128009,tokenizer.ggml.add_bos_token=bool:false,tokenizer.ggml.add_eos_token=bool:false"
        if override.get("runtime_overrides") != expected_override:
            raise RuntimeError("Only the one proven official metadata override is allowed")
        parity_path = (ROOT / override["parity_report"]).resolve()
        template_path = (ROOT / override["template_file"]).resolve()
        if not parity_path.is_relative_to(ROOT) or not template_path.is_relative_to(ROOT):
            raise RuntimeError("Override reference outside workspace")
        parity = json.loads(parity_path.read_text(encoding="utf-8"))
        if digest(parity_path) != override["parity_report_sha256"] or digest(template_path) != override["template_sha256"] or not all(parity.get(k) for k in ("parity_complete", "own_cleanup_confirmed", "generation_log_markers_absent")):
            raise RuntimeError("Native tokenizer parity evidence failed closed")
        args += ["--override-kv", expected_override, "--chat-template-file", str(template_path)]
        override = {"protocol": override, "protocol_file": str(protocol_path.relative_to(ROOT)), "protocol_sha256": digest(protocol_path)}
    manifest = {"started_utc": old.now(), "run_id": directory.name, "state": "running", "phase": "exploratory_development_only",
                "model": BITNET, "server_sha256": digest(server_path), "harness_sha256": digest(__file__),
                "sample_ids": [s["id"] for s in samples], "n_planned": n, "cloud_calls": 0,
                "runtime": "official microsoft/BitNet bitnet.cpp; isolated LLVM-MinGW Windows build",
                "runtime_commit": "0b341e582afbf9e1011f24744b554c96a3477eb5",
                "llama_submodule_commit": "390c307752ab78fd8189f359d6954c9ba1be74af",
                "cpu_threads": 4, "threads_batch": 4, "context": 4096, "parallel": 1,
                "runtime_override": override,
                "gpu_offload_requested_layers": 0, "actual_offload": "Confirm from own runtime startup log; CPU native baseline",
                "build_metadata": json.loads((ROOT / "results/20261002T170300Z_02a39af9_requested_local_metadata/bitnet_native_build_verified.json").read_text(encoding="utf-8")),
                "backend_server_args": args, "hidden_warmups": 0, "request_retries": 0,
                "extension_rule": "DEV12 correct>=6 and completion errors<=2, then remaining24 without repeats",
                "request_parameters": {k: v for k, v in api.payload(identifier, samples[0]).items() if k != "messages"},
                "data_sha256": digest(ROOT / "data/benchmark.jsonl"), "prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
                "latency_scope": "Measured streaming HTTP wall time; model loads and resource snapshots excluded",
                "limitations": ["Native CPU runtime differs from LM Studio GPU runtime", "Exploratory DEV, not independent final test", "No concurrent downloads/builds/model inference permitted"]}
    write(directory / "manifest.json", manifest)
    write(directory / "samples_dev.json", samples)
    manifest["source_snapshot"] = snapshot_sources(directory)
    (directory / "harness_source.py").write_bytes(Path(__file__).read_bytes())
    (directory / "system_prompt.txt").write_text(SYSTEM_PROMPT, encoding="utf-8")
    write(directory / "manifest.json", manifest)
    rows, monitor, process = [], old.Monitor(), None
    env = os.environ.copy()
    env["PATH"] = str(Path(server_path).resolve().parent) + os.pathsep + env.get("PATH", "")
    # Only this new server's PID is terminated in cleanup.
    try:
        with (directory / "native_server_log.txt").open("x", encoding="utf-8") as log, monitor:
            loaded_started = time.perf_counter()
            process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, env=env)
            manifest["own_server_pid"] = process.pid
            with httpx.Client(timeout=120, trust_env=False) as client:
                while True:
                    if process.poll() is not None:
                        raise RuntimeError("Native server stopped before health readiness")
                    if time.perf_counter() - loaded_started > 180:
                        raise RuntimeError("Native server readiness timeout")
                    try:
                        ready = client.get("http://127.0.0.1:1235/health", timeout=2)
                        if ready.status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(.5)
                manifest["cold_load_wall_s"] = time.perf_counter() - loaded_started
                with (directory / "bitnet_raw.jsonl").open("x", encoding="utf-8") as raw_handle:
                    for i, sample in enumerate(samples):
                        if i == 12 and not eligible_extension(rows):
                            manifest["state"] = "PARTIAL_SCREEN_REJECTED"
                            break
                        headroom = old.resource_headroom()
                        if headroom["ram_available_gib"] < 2:
                            raise RuntimeError("Native CPU RAM guard")
                        result = bitnet_request(client, identifier, sample)
                        item = {"run_id": directory.name, "sample": sample, "sample_index": i, "utc": old.now(),
                                "model": identifier, "local": result, "score": score(sample, result.get("output")),
                                "headroom_before_request": headroom}
                        rows.append(item)
                        raw_handle.write(json.dumps(item, ensure_ascii=False) + "\n")
                        raw_handle.flush()
                        print(json.dumps({"model": "bitnet", "completed": len(rows), "planned": n}), flush=True)
                    else:
                        manifest["state"] = "DONE"
                result = old.command(["powershell.exe", "-NoProfile", "-Command", f"Get-Process -Id {process.pid} | Select-Object Id,ProcessName,WorkingSet64,PeakWorkingSet64 | ConvertTo-Json -Compress"], 20)
                manifest["own_process_memory"] = json.loads(result.stdout) if result.returncode == 0 else {"status": "UNKNOWN"}
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired, httpx.HTTPError) as exc:
        manifest.update(state="BLOCKED" if not rows else "PARTIAL", error_type=type(exc).__name__)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        manifest["own_server_cleanup_confirmed"] = process is None or process.poll() is not None
        manifest["resources"] = monitor.summary()
        manifest["summary"] = api.summarize(rows)
        manifest["finished_utc"] = old.now()
        write(directory / "resources.json", monitor.rows)
        write(directory / "manifest.json", manifest)
    print(json.dumps({"run_directory": str(directory), "state": manifest["state"], "summary": manifest["summary"]}), flush=True)
    return directory


def run(names, model_root, development_n=36):
    if development_n not in (12, 36) or not names or set(names) - set(BASELINES):
        raise ValueError("Only the requested Qwen/Phi names and DEV12/DEV36 are allowed")
    key, source = resolve_api_key("local", env_path=ROOT / ".env")
    if not key:
        raise RuntimeError("LOCAL_API_KEY missing in legitimate project environment")
    client = httpx.Client(timeout=120, trust_env=False)
    catalog = api.native_models(client, key)
    if any(m.get("loaded_instances") for m in catalog):
        raise RuntimeError("Another model is loaded; this controller will not unload it")
    inventory = old.cli_json("ls", "--json")
    fingerprints = {name: fingerprint(BASELINES[name], inventory, model_root) for name in names}
    samples = old.choose_samples(development_n)
    directory = ROOT / "results" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8] + "_requested_local_dev")
    directory.mkdir(exist_ok=False)
    manifest = {"run_id": directory.name, "started_utc": old.now(), "state": "running",
                "phase": "exploratory_development_only", "n_planned_per_model": development_n,
                "sample_ids": [s["id"] for s in samples], "dataset_split": "old_dev",
                "data_sha256": digest(ROOT / "data/benchmark.jsonl"),
                "prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
                "harness_sha256": digest(__file__), "historical_api_sha256": digest(api.__file__),
                "core_source_sha256": {n: digest(ROOT / "src/agro_route" / n) for n in ("models.py", "routing.py", "evaluation.py", "tools.py")},
                "credential_source": source, "fingerprints": fingerprints, "models": {},
                "parameters": api.payload("unused", samples[0]), "context_length": 4096, "parallel": 1,
                "warmups": 0, "request_retries": 0, "response_cache": False,
                "extension_rule": "After fixed DEV12, append remaining 24 once only if correct>=6/12, completion errors<=2/12, and guards remain safe. Earlier requests are never repeated.",
                "latency_scope": "Measured streaming HTTP wall time. Model load and resource/process polling are outside request latency.",
                "execution_context": "Sequential GPU inference; no downloads, builds, CPU-heavy local inference or other GPU inference permitted during measurement.",
                "limitations": ["Development screening, not confirmatory holdout", "Original DEV agricultural extractive QA English-only", "Client TPS approximate", "Sampled whole-device VRAM and whole-system RAM", "Process RSS association UNKNOWN unless separately proven"]}
    manifest["parameters"]["messages"] = "SYSTEM_PROMPT + public_request(sample); no gold/category/expected route"
    write(directory / "manifest.json", api.redact(manifest, key))
    write(directory / "samples_dev.json", samples)
    (directory / "system_prompt.txt").write_text(SYSTEM_PROMPT, encoding="utf-8")
    (directory / "harness_source.py").write_bytes(Path(__file__).read_bytes())
    manifest["source_snapshot"] = snapshot_sources(directory)
    write(directory / "manifest.json", api.redact(manifest, key))
    print(json.dumps({"run_directory": str(directory)}), flush=True)
    try:
        for name in names:
            info = fingerprints[name]
            model_key = info["inventory"]["modelKey"]
            identifier = "requested-local-" + uuid.uuid4().hex[:8] + "-" + name
            meta = {"status": "NOT_RUN", "own_instance_id": identifier,
                    "requested_offload": info["gpu"], "actual_offloaded_layers": "UNKNOWN", "load_success": False}
            manifest["models"][name] = meta
            rows, monitor = [], old.Monitor()
            try:
                with monitor:
                    meta["processes_before_load"] = process_snapshot()
                    args = [old.LMS, "load", model_key, "--context-length", "4096", "--parallel", "1", "--gpu", info["gpu"], "--identifier", identifier, "--yes"]
                    estimate = old.command([*args, "--estimate-only"])
                    meta["estimate_returncode"] = estimate.returncode
                    (directory / (name + "_estimate.txt")).write_text(old.ANSI.sub("", estimate.stdout + estimate.stderr), encoding="utf-8")
                    if estimate.returncode:
                        raise RuntimeError("Resource estimate failed")
                    started = time.perf_counter()
                    loaded = old.guarded_load(args, directory / (name + "_load.txt"), meta)
                    meta["cold_load_wall_s"] = time.perf_counter() - started
                    meta["load_success"] = loaded.returncode == 0
                    if loaded.returncode:
                        raise RuntimeError("Guarded load failed")
                    current = api.native_models(client, key)
                    matches = [(m, instance) for m in current for instance in m.get("loaded_instances", []) if instance.get("id") == identifier]
                    if len(matches) != 1:
                        raise RuntimeError("Own instance not confirmed")
                    native, instance = matches[0]
                    meta.update(native_model_metadata=native, actual_load_config=instance.get("config"))
                    config = instance.get("config") or {}
                    if config.get("context_length") != 4096 or config.get("parallel") != 1:
                        raise RuntimeError("Controlled load configuration not confirmed")
                    allowed = ((native.get("capabilities") or {}).get("reasoning") or {}).get("allowed_options", [])
                    effort = "none" if "off" in allowed else None
                    meta["reasoning_effort_requested"] = effort
                    meta["processes_after_load"] = process_snapshot()
                    with (directory / (name + "_raw.jsonl")).open("x", encoding="utf-8") as handle:
                        for i, sample in enumerate(samples):
                            if i == 12 and not eligible_extension(rows):
                                meta["status"] = "PARTIAL_SCREEN_REJECTED"
                                break
                            headroom = old.resource_headroom()
                            if headroom["ram_available_gib"] < 2 or headroom["gpu_free_mib"] < 512:
                                meta["resource_guard_stop"] = headroom
                                raise RuntimeError("Resource guard before inference")
                            result = api.api_call(client, key, identifier, sample, effort)
                            item = {"run_id": directory.name, "sample": sample, "model": model_key,
                                    "sample_index": i, "utc": old.now(), "local": result,
                                    "score": score(sample, result.get("output")), "headroom_before_request": headroom}
                            rows.append(item)
                            handle.write(json.dumps(api.redact(item, key), ensure_ascii=False) + "\n")
                            handle.flush()
                            print(json.dumps({"model": name, "completed": len(rows), "planned": development_n}), flush=True)
                        else:
                            meta["status"] = "DONE"
                    meta["processes_after_inference"] = process_snapshot()
            except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired, httpx.HTTPError) as exc:
                meta.update(status="BLOCKED" if not rows else "PARTIAL", error_type=type(exc).__name__)
            finally:
                meta["resources"] = monitor.summary()
                meta["summary"] = api.summarize(rows)
                write(directory / (name + "_resources.json"), monitor.rows)
                current = api.native_models(client, key)
                if any(instance.get("id") == identifier for m in current for instance in m.get("loaded_instances", [])):
                    unloaded = old.command([old.LMS, "unload", identifier])
                    meta["unload_returncode"] = unloaded.returncode
                meta["own_cleanup_confirmed"] = not any(instance.get("id") == identifier for m in api.native_models(client, key) for instance in m.get("loaded_instances", []))
                write(directory / "manifest.json", api.redact(manifest, key))
                if not meta["own_cleanup_confirmed"]:
                    raise RuntimeError("Own instance cleanup failed; no later model permitted")
        manifest["state"] = "completed"
    finally:
        manifest["finished_utc"] = old.now()
        if manifest["state"] == "running":
            manifest["state"] = "interrupted"
        write(directory / "manifest.json", api.redact(manifest, key))
        client.close()
    print(json.dumps({"run_directory": str(directory), "state": manifest["state"], "models": {n: m.get("summary") for n, m in manifest["models"].items()}}), flush=True)
    return directory


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Must be scheduled by the lead after downloads/builds stop")
    parser.add_argument("--models", nargs="+", choices=list(BASELINES), default=list(BASELINES))
    parser.add_argument("--n", type=int, choices=[12, 36], default=36)
    parser.add_argument("--model-root", type=Path, default=Path.home() / ".lmstudio/models")
    parser.add_argument("--bitnet-server", type=Path)
    parser.add_argument("--bitnet-model", type=Path)
    parser.add_argument("--bitnet-runtime-protocol", type=Path)
    parser.add_argument("--diagnose-bitnet-tokenizer", action="store_true", help="Non-generative fixed tokenization/format parity only")
    parser.add_argument("--resume-public", choices=list(PUBLIC_DOWNLOADS))
    parser.add_argument("--derive-log", type=Path, help="Read-only auxiliary log metrics for --run-directory")
    parser.add_argument("--run-directory", type=Path)
    args = parser.parse_args()
    if args.derive_log:
        if not args.run_directory or len(args.models) != 1:
            parser.error("Log derivation requires one --models value and --run-directory")
        derive_backend_metrics(args.run_directory, args.models[0], args.derive_log)
    elif args.resume_public:
        resume_public_download(args.resume_public)
    elif args.diagnose_bitnet_tokenizer:
        if not args.bitnet_server or not args.bitnet_model or args.run:
            parser.error("Tokenizer diagnostic requires native paths and does not permit --run")
        diagnose_bitnet_tokenizer(args.bitnet_server, args.bitnet_model)
    elif args.bitnet_server or args.bitnet_model:
        if not args.run or not args.bitnet_server or not args.bitnet_model:
            parser.error("Native BitNet requires --run, --bitnet-server and --bitnet-model")
        run_bitnet(args.bitnet_server, args.bitnet_model, args.n, args.bitnet_runtime_protocol)
    elif args.run:
        run(args.models, args.model_root, args.n)
    else:
        inventory = old.cli_json("ls", "--json")
        print(json.dumps({name: fingerprint(BASELINES[name], inventory, args.model_root) for name in args.models}, ensure_ascii=False, indent=2))
