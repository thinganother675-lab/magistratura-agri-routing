"""Complete trade-off figure unaffected by unknown API billing."""
import json
from pathlib import Path
import os
ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

directory=ROOT/'results/20260930T182756Z_6703e43b'
data=json.loads((directory/'analysis.json').read_text())['summary']
if (directory/'quality_calls_latency.png').exists():raise RuntimeError('Preserve completed figure')
fig,axes=plt.subplots(1,2,figsize=(11,4.3))
colors=['#728779','#d18132','#9a789f','#1b6850','#28669a','#a6b28f']
for r,color in zip(data,colors):
    low,high=r['quality_ci95'];q=r['quality']
    axes[0].errorbar(r['cloud_call_rate']*100,q*100,yerr=[[100*(q-low)],[100*(high-q)]],fmt='o',color=color,capsize=3,label=r['method'])
axes[0].set(xlabel='Cloud calls (% of requests)',ylabel='Task correctness (%) with group bootstrap 95% CI',xlim=(-5,105),ylim=(0,105))
axes[0].legend(fontsize=8,loc='lower right')
names=[r['method'] for r in data];means=[r['latency_mean_ms']/1000 for r in data];p95=[r['latency_p95_ms']/1000 for r in data]
axes[1].bar(names,means,color=colors,label='mean')
axes[1].plot(names,p95,'k_',markersize=14,label='p95')
axes[1].set(ylabel='Reconstructed trace latency (seconds)');axes[1].tick_params(axis='x',rotation=35);axes[1].legend(fontsize=8)
for ax in axes:ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
fig.suptitle('90 controlled agricultural requests: Qwen3.5-2B CPU + Mercury 2.5')
fig.tight_layout()
for ext in ['png','jpg','svg']:fig.savefig(directory/('quality_calls_latency.'+ext),dpi=180)
plt.close(fig)
print('Created quality/call-rate/latency publication figure')
