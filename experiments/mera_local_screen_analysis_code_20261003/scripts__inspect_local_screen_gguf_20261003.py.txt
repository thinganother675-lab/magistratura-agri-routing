# SPDX-License-Identifier: Apache-2.0
"""Read GGUF metadata/tensor descriptors only; no tensor payload or inference.

The backend's single quantization label need not describe every tensor. The
type-name map is recovered as data from a pinned official ggml header, never
executed. Model hashes refer to the earlier complete installed-weight receipt.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / 'results/20261003_local_screen_571682f5'
SCALARS = {0: 'B', 1: 'b', 2: 'H', 3: 'h', 4: 'I', 5: 'i', 6: 'f',
           7: '?', 10: 'Q', 11: 'q', 12: 'd'}


def read_exact(stream, n):
    result = stream.read(n)
    if len(result) != n:
        raise ValueError('Truncated GGUF descriptor')
    return result


def scalar(stream, fmt):
    return struct.unpack('<' + fmt, read_exact(stream, struct.calcsize('<' + fmt)))[0]


def string(stream, keep=True):
    n = scalar(stream, 'Q')
    if n > 128 * 1024 * 1024:
        raise ValueError('GGUF metadata string exceeds inspection bound')
    if keep:
        return read_exact(stream, n).decode('utf-8')
    if len(stream.read(n)) != n:
        raise ValueError('Truncated GGUF string')
    return None


def value(stream, kind, keep=False, depth=0):
    if depth > 2:
        raise ValueError('Unsupported nested GGUF array')
    if kind in SCALARS:
        v = scalar(stream, SCALARS[kind])
        return v if keep else None
    if kind == 8:
        return string(stream, keep)
    if kind == 9:
        subtype, n = scalar(stream, 'I'), scalar(stream, 'Q')
        if n > 2_000_000:
            raise ValueError('GGUF array exceeds inspection bound')
        for _ in range(n):
            value(stream, subtype, False, depth + 1)
        return None
    raise ValueError('Unknown GGUF metadata type')


def inspect(stream, type_names):
    if read_exact(stream, 4) != b'GGUF' or scalar(stream, 'I') != 3:
        raise ValueError('Inspection supports little-endian GGUFv3 only')
    tensors, entries = scalar(stream, 'Q'), scalar(stream, 'Q')
    if tensors > 1_000_000 or entries > 100_000:
        raise ValueError('GGUF header exceeds inspection bound')
    metadata = {}
    for _ in range(entries):
        key, kind = string(stream), scalar(stream, 'I')
        keep = key in {'general.name', 'general.architecture', 'general.file_type',
                       'general.quantization_version'} or key.endswith(('.context_length', '.block_count'))
        v = value(stream, kind, keep)
        if keep:
            metadata[key] = v
    histogram = defaultdict(lambda: {'tensor_count': 0, 'stored_elements': 0, 'expert_elements': 0})
    for _ in range(tensors):
        name, dimensions = string(stream), scalar(stream, 'I')
        if not 1 <= dimensions <= 8:
            raise ValueError('Unsupported GGUF tensor dimensions')
        shape = [scalar(stream, 'Q') for _ in range(dimensions)]
        if any(n == 0 for n in shape):
            raise ValueError('Empty GGUF tensor dimension')
        kind = scalar(stream, 'I')
        scalar(stream, 'Q')  # byte offset; do not seek into tensor payload
        count = math.prod(shape)
        label = type_names.get(kind, 'UNKNOWN_TYPE_' + str(kind))
        histogram[label]['tensor_count'] += 1
        histogram[label]['stored_elements'] += count
        if '_exps' in name:
            histogram[label]['expert_elements'] += count
    total = sum(v['stored_elements'] for v in histogram.values())
    for v in histogram.values():
        v['fraction_of_stored_elements'] = v['stored_elements'] / total if total else None
    return {'gguf_version': 3, 'metadata': metadata, 'tensor_count': tensors,
            'total_stored_elements': total, 'tensor_type_histogram': dict(sorted(histogram.items())),
            'descriptor_end_byte': stream.tell(), 'tensor_payload_read': False,
            'element_count_is_active_parameter_count': False}


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'magistratura-GGUF-reproducibility-audit'})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def main():
    target = STUDY / 'installed_gguf_tensor_types.json'
    if target.exists():
        raise ValueError('Append-only inspection receipt already exists')
    revision = json.loads(fetch('https://api.github.com/repos/ggml-org/ggml/commits/master'))['sha']
    url = f'https://raw.githubusercontent.com/ggml-org/ggml/{revision}/include/ggml.h'
    header = fetch(url)
    body = re.search(r'enum ggml_type\s*\{(.*?)\};', header.decode('utf-8'), re.S)
    if body is None:
        raise ValueError('Official type enum unavailable')
    names = {int(number): name for name, number in re.findall(r'GGML_TYPE_(\w+)\s*=\s*(\d+)', body.group(1)) if name != 'COUNT'}
    receipts = json.loads((STUDY / 'installed_weight_checksums.json').read_text(encoding='utf-8'))
    model_root = (Path.home() / '.lmstudio/models').resolve()
    models = []
    for receipt in receipts['models']:
        path = (model_root / receipt['relative_model_path']).resolve()
        if not path.is_relative_to(model_root):
            raise ValueError('Model path escapes installation root')
        before = path.stat()
        if before.st_size != receipt['bytes']:
            raise ValueError('Installed model size changed after checksum receipt')
        with path.open('rb') as stream:
            descriptor = inspect(stream, names)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('Installed model changed during header inspection')
        models.append({'model_key': receipt['model_key'], 'weight_sha256_prior_receipt': receipt['sha256'],
                       'backend_reported_quantization': receipt['quantization'], **descriptor})
    report = {'status': 'DEV_REPRODUCIBILITY_RECEIPT', 'utc': datetime.now(timezone.utc).isoformat(),
              'primary_source_url': url, 'ggml_commit': revision,
              'type_enum_source_sha256': hashlib.sha256(header).hexdigest(),
              'format_reference': 'https://github.com/ggml-org/ggml/blob/' + revision + '/docs/gguf.md',
              'source_was_executed': False, 'weights_copied_or_modified': False,
              'models': models, 'scope': 'primary GGUF descriptors only; projector files and active MoE parameters not counted'}
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2); stream.write('\n')
    print(json.dumps({'models_inspected': len(models), 'tensor_payload_read': False,
                      'gpt_oss_tensor_types': next(m['tensor_type_histogram'] for m in models if m['model_key'] == 'gpt-oss-20b')}))


if __name__ == '__main__':
    main()
