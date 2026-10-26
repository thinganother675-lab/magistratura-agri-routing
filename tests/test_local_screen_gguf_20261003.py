import io
from pathlib import Path
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from inspect_local_screen_gguf_20261003 import inspect


def s(v):
    data = v.encode()
    return struct.pack('<Q', len(data)) + data


def sample():
    metadata = s('general.architecture') + struct.pack('<I', 8) + s('gpt-oss')
    metadata += s('tokenizer.ggml.tokens') + struct.pack('<IIQ', 9, 8, 2) + s('a') + s('b')
    descriptor = s('blk.0.ffn_down_exps.weight') + struct.pack('<IQQIQ', 2, 64, 32, 39, 0)
    descriptor += s('output.weight') + struct.pack('<IQIQ', 1, 128, 8, 4096)
    return b'GGUF' + struct.pack('<IQQ', 3, 2, 2) + metadata + descriptor


def test_header_only_histogram_preserves_mixed_expert_types():
    header = sample()
    stream = io.BytesIO(header + b'tensor payload must remain unread')
    got = inspect(stream, {39: 'MXFP4', 8: 'Q8_0'})
    assert stream.tell() == len(header)
    assert got['total_stored_elements'] == 2176
    assert got['tensor_type_histogram']['MXFP4']['expert_elements'] == 2048
    assert got['tensor_type_histogram']['Q8_0']['expert_elements'] == 0
    assert got['metadata'] == {'general.architecture': 'gpt-oss'}
    assert got['tensor_payload_read'] is False


@pytest.mark.parametrize('data', [b'', b'GGUF' + struct.pack('<I', 2), sample()[:-1], sample()[:35]])
def test_truncated_or_unsupported_header_fails_closed(data):
    with pytest.raises(ValueError):
        inspect(io.BytesIO(data), {})


def test_unknown_type_retains_number_without_guessing_quantization():
    got = inspect(io.BytesIO(sample()), {})
    assert 'UNKNOWN_TYPE_39' in got['tensor_type_histogram']
