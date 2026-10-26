import importlib.util
from pathlib import Path
import sys
import hashlib
import json
import struct

import pytest
import httpx

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
spec = importlib.util.spec_from_file_location("local_baselines_20261002", SCRIPT_DIR / "local_baselines_20261002.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_fingerprint_fails_closed_on_wrong_quantization(tmp_path):
    spec = {"filename": "model.gguf", "size": 3, "sha256": "x"}
    with pytest.raises(RuntimeError, match="Q8_0"):
        m.fingerprint(spec, [{"path": "owner/repo/model.gguf", "quantization": {"name": "Q4_K_M"}}], tmp_path)


def test_fingerprint_verifies_exact_size_and_digest(tmp_path):
    path = tmp_path / "owner" / "repo" / "model.gguf"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"abc")
    spec = {"filename": "model.gguf", "size": 3, "sha256": m.digest(path)}
    inventory = [{"path": "owner/repo/model.gguf", "quantization": {"name": "Q8_0"}}]
    assert m.fingerprint(spec, inventory, tmp_path)["status"] == "CHECKSUM_VERIFIED"
    spec["sha256"] = "wrong"
    with pytest.raises(RuntimeError, match="checksum"):
        m.fingerprint(spec, inventory, tmp_path)


def test_extension_keeps_failures_in_denominator():
    rows = [{"score": {"correct": i < 6}, "local": {"error": None}} for i in range(12)]
    assert m.eligible_extension(rows)
    rows[0]["score"]["correct"] = False
    assert not m.eligible_extension(rows)
    rows[0]["score"]["correct"] = True
    for row in rows[:3]:
        row["local"]["error"] = {"type": "IncompleteCompletion"}
    assert not m.eligible_extension(rows)


def test_run_rejects_non_development_size_before_external_calls():
    with pytest.raises(ValueError):
        m.run(["qwen"], Path("unused"), 150)


def test_native_bitnet_failure_stays_local_and_preserves_unknown_usage():
    calls = []
    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(503, json={"error": "unavailable"})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = m.bitnet_request(client, "bitnet-native-i2s", m.old.choose_samples(12)[0])
    assert calls == ["http://127.0.0.1:1235/v1/chat/completions"]
    assert result["error"]["http_status"] == 503
    assert result["output"] is None
    assert result["usage"] == {}


def test_native_weights_checksum_blocks_inference(tmp_path):
    executable = tmp_path / "server.exe"
    executable.write_bytes(b"placeholder")
    model = tmp_path / "model.gguf"
    model.write_bytes(b"wrong")
    with pytest.raises(RuntimeError, match="checksum"):
        m.run_bitnet(executable, model, 12)


@pytest.mark.parametrize("response_status,content,expected", [(200, b"bc", "exact requested range"), (206, b"xx", "checksum/size mismatch")])
def test_public_resume_rejects_ignored_range_and_corrupt_checksum(tmp_path, monkeypatch, response_status, content, expected):
    monkeypatch.setattr(m, "ROOT", tmp_path)
    spec = {"url": "https://public.example/model.gguf", "size": 3, "sha256": hashlib.sha256(b"abc").hexdigest(), "target": "isolated/model.gguf"}
    monkeypatch.setitem(m.PUBLIC_DOWNLOADS, "test", spec)
    part = tmp_path / "isolated/model.gguf.part"
    part.parent.mkdir()
    part.write_bytes(b"a")
    original_client = httpx.Client
    def handler(request):
        assert request.headers["range"] == "bytes=1-2"
        assert "authorization" not in request.headers
        return httpx.Response(response_status, headers={"content-range": "bytes 1-2/3"}, content=content)
    monkeypatch.setattr(m.httpx, "Client", lambda **kwargs: original_client(transport=httpx.MockTransport(handler)))
    with pytest.raises(RuntimeError, match=expected):
        m.resume_public_download("test")
    assert part.read_bytes() == b"a"
    assert not (tmp_path / spec["target"]).exists()


def test_backend_derivation_leaves_unmatched_metrics_unknown(tmp_path):
    manifest = {"models": {"phi": {"own_instance_id": "own-instance"}}}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    raw = {"sample": {"id": "dev1"}, "local": {"usage": {"prompt_tokens": 3, "completion_tokens": 2}, "raw": {"events": []}}}
    (tmp_path / "phi_raw.jsonl").write_text(json.dumps(raw) + "\n")
    log = tmp_path / "server.log"
    log.write_text("[2026-10-02 21:22:00][INFO][unrelated] Running chat completion\n")
    result = m.derive_backend_metrics(tmp_path, "phi", log)
    assert not result["complete_alignment"]
    assert result["backend_decode_tps_median"] is None
    assert result["actual_offloaded_layers"] == "UNKNOWN"
    assert result["backend_process_association"]["status"] == "UNKNOWN"


def test_gguf_audit_counts_native_type_without_exporting_vocabulary_or_loading_tensors(tmp_path):
    def text(value):
        raw = value.encode()
        return struct.pack("<Q", len(raw)) + raw
    raw = b"GGUF" + struct.pack("<IQQ", 3, 1, 2)
    raw += text("general.architecture") + struct.pack("<I", 8) + text("bitnet-b1.58")
    raw += text("tokenizer.ggml.tokens") + struct.pack("<IIQ", 9, 8, 1) + text("VOCAB_NOT_EXPORTED")
    raw += text("weight") + struct.pack("<IQIQ", 1, 32, 36, 0)
    path = tmp_path / "metadata.gguf"
    path.write_bytes(raw)  # No tensor payload; the audit must not attempt to read it.
    result = m.read_gguf_identity(path)
    assert result["metadata"]["general.architecture"] == "bitnet-b1.58"
    assert result["native_bitnet_i2_s_type36"] == 1
    assert not result["tensor_data_read"]
    assert "VOCAB_NOT_EXPORTED" not in json.dumps(result)
    path.write_bytes(raw[:25])
    with pytest.raises(RuntimeError, match="Truncated"):
        m.read_gguf_identity(path)
