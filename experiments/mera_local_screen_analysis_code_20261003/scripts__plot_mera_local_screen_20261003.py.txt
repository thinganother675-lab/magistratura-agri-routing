# SPDX-License-Identifier: Apache-2.0
"""Standalone aggregate-only research figure; never reads questions or gold."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / 'results/20261003_local_screen_571682f5'
NAMES = {'gemma-4-12b-it': 'Gemma 12B', 'gemma-4-26b-a4b-it': 'Gemma 26B-A4B',
         'unsloth/qwen3.5-4b': 'Qwen 4B', 'qwen3.5-9b': 'Qwen 9B',
         'qwen3.8-27b': 'Qwen 27B', 'phi-4-mini-instruct': 'Phi mini',
         'granite-4.1-8b': 'Granite 8B', 'minicpm5-1b': 'MiniCPM 1B'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    source = STUDY / 'final_analysis.json'
    result = json.loads(source.read_text(encoding='utf-8'))
    if result.get('status') != 'DEV' or result.get('private_test_run') is not False:
        raise ValueError('Only public development analysis may be plotted')
    outputs = [STUDY / name for name in ('quality_latency_dev.png', 'quality_latency_dev.svg', 'figure_provenance.json')]
    if any(p.exists() for p in outputs):
        raise ValueError('Append-only figure files already exist')
    fig, axes = plt.subplots(1, 2, figsize=(12.6, 5.7), layout='constrained')
    norm = Normalize(10, 32)
    for ax, stage, title in zip(axes, ('stage1', 'stage2'), ('Common DEV60: eight complete models', 'Full DEV293: frozen practical shortlist')):
        for p in result[stage]:
            if p['status'] != 'COMPLETE' or not p['summary']['complete_coverage']:
                continue
            s = p['summary']
            x, y = s['latency_p95_s'], 100 * s['strict_set_em']
            ax.scatter(x, y, c=[s['peak_ram_used_gib']], cmap='viridis', norm=norm, s=105, edgecolors='black', linewidth=.6, zorder=3)
            name = NAMES[p['model_key']]
            dx, dy = (7, -14) if name == 'Qwen 27B' else (7, 8)
            ax.annotate(name, (x, y), xytext=(dx, dy), textcoords='offset points', fontsize=9)
        ax.set_xscale('log'); ax.set_xlim(.08, 4); ax.set_ylim(-4, 83)
        ax.set_title(title, fontsize=11)
        ax.set_xlabel('p95 response latency, seconds (log scale)')
        ax.set_ylabel('STRICT_SET_EM, %')
        ax.grid(True, which='both', alpha=.23, zorder=0)
    fig.colorbar(ScalarMappable(norm=norm, cmap='viridis'), ax=axes, label='Sampled peak whole-system RAM used, GiB', shrink=.8)
    fig.suptitle('ruTXTAgroBench local selection — DEV evidence only', fontsize=14)
    fig.supxlabel('Scored references: 59/60 and 289/293; unresolved originals preserved. Latency excludes load/warmup.\nDEV293 includes DEV60: no independent holdout. Partial/failed models excluded from the plotted comparison.', fontsize=9)
    fig.savefig(outputs[0], dpi=180); fig.savefig(outputs[1]); plt.close(fig)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    record = {'status': 'DEV', 'private_test_run': False, 'source_analysis_sha256': sha(source),
              'source_analysis_path': str(source.relative_to(ROOT)).replace('\\', '/'),
              'plot_code_commit': commit, 'plot_source_sha256': sha(__file__),
              'outputs': {p.name: sha(p) for p in outputs[:2]},
              'contains_benchmark_text_or_predictions': False,
              'metric': 'STRICT_SET_EM on unmodified parseable original references',
              'latency_scope': 'p95 successful query response timing; excludes load and warmup',
              'resource_scope': 'sampled peak whole-system RAM, not model allocation'}
    with outputs[2].open('x', encoding='utf-8') as stream:
        json.dump(record, stream, indent=2); stream.write('\n')
    print(json.dumps({'figure_created': outputs[0].name, 'status': 'DEV'}))


if __name__ == '__main__':
    main()
