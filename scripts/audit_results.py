"""Add cost and failure audits without modifying completed primary analysis."""
import argparse
import json
from pathlib import Path
import numpy as np
from agro_route.models import SYSTEM_PROMPT, public_request
from agro_route.evaluation import score
from agro_route.routing import identify_tool

def main():
    parser=argparse.ArgumentParser();parser.add_argument('run');directory=Path(parser.parse_args().run)
    pairs=[json.loads(l) for l in (directory/'pairs.jsonl').read_text(encoding='utf-8').splitlines()]
    rows=[json.loads(l) for l in (directory/'normalized.jsonl').read_text(encoding='utf-8').splitlines()]
    manifest=json.loads((directory/'manifest.json').read_text())
    prices=manifest['prices_usd_per_m'];by_id={p['sample']['id']:p for p in pairs}
    unknown=[p for p in pairs if p['cloud']['cost_usd'] is None]
    bounds={p['sample']['id']:((len(SYSTEM_PROMPT.encode())+len(json.dumps(public_request(p['sample']),ensure_ascii=False).encode())+256)*prices['input']+512*prices['output'])/1e6 for p in unknown}
    costs={}
    for method in sorted({r['method'] for r in rows}):
        sub=[r for r in rows if r['method']==method]
        known=sum(r['cost_usd'] or 0 for r in sub)
        missing=sum(bounds.get(r['id'],0) for r in sub if r['cost_usd'] is None and r['cloud_calls'])
        costs[method]={'known_usage_cost_usd':known,'unknown_request_ids':[r['id'] for r in sub if r['cost_usd'] is None],'planning_total_range_usd':[known,known+missing],'planning_per_1000_range_usd':[known/len(sub)*1000,(known+missing)/len(sub)*1000]}
    cost_report={'type':'supplementary estimate; missing-usage upper endpoint is a planning assumption, NOT an invoice or guaranteed bound','unknown_cloud_calls':[{'id':p['sample']['id'],'error':p['cloud']['error']} for p in unknown],'method':costs,'known_cost_difference_cloud_minus_cascade':costs['cloud']['known_usage_cost_usd']-costs['cascade']['known_usage_cost_usd'],'note':'Same cached unknown-cost call is selected by cloud, tool_cloud and cascade; its cost cancels in their absolute difference. Local energy/compute not monetized.'}
    failures=[]
    for p in pairs:
        sample=p['sample']
        for model in ('local','cloud'):
            if not score(sample,p[model]['output'])['correct']:
                failures.append({'id':sample['id'],'category':sample['category'],'model':model,'input':sample['input'],'expected':sample['expected'],'output':p[model]['output'],'error':p[model]['error']})
    false_accepts=[{'id':r['id'],'output':r['output'],'expected':by_id[r['id']]['sample']['expected']} for r in rows if r['method']=='cascade' and r['route']=='LOCAL_MODEL' and not r['correct']]
    numeric=[]
    for method in sorted({r['method'] for r in rows}):
        for tool in ('gdd','vpd','et0','rain_deficit'):
            sub=[r for r in rows if r['method']==method and r['category']=='numeric' and identify_tool(by_id[r['id']]['sample']['input'])==tool]
            errors=[r['numeric_error'] for r in sub if r['numeric_error'] is not None]
            numeric.append({'method':method,'tool':tool,'n':len(sub),'valid_numeric_outputs':len(errors),'correct':sum(r['correct'] for r in sub),'mae_when_numeric_present':float(np.mean(errors)) if errors else None,'unit':next(by_id[r['id']]['sample']['expected']['unit'] for r in sub)})
    for name,obj in [('cost_audit.json',cost_report),('failure_audit.json',{'failures':failures,'false_local_accepts':false_accepts,'numeric_by_tool':numeric,'warning':'Primary analysis numeric_mae_when_present pools incompatible units; do not interpret it as a physical aggregate. Use per-tool MAE here.'})]:
        with (directory/name).open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
    print(json.dumps(cost_report,indent=2))

if __name__=='__main__':main()
