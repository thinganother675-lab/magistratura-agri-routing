"""Small live functional checks, separate from frozen performance experiment."""
from datetime import datetime, timezone
import json
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]
def main():
    out=ROOT/'results'/('live_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    out.mkdir(exist_ok=False)
    with httpx.Client(base_url='http://127.0.0.1:8090',trust_env=False,timeout=70) as c:
        health=c.get('/api/health').json()
        weather=c.get('/api/weather').json()
        cases=[
            ('gdd',{'input':'Рассчитай GDD: tmin=[10,12], tmax=[20,22], base=5, temperature_unit=C'},'DETERMINISTIC_TOOL',22),
            ('missing',{'input':'Посчитай ET0.'},'ASK_FOR_DATA',None),
            ('invalid_units',{'input':'Рассчитай VPD: temperature=77, rh=50, temperature_unit=F'},'ASK_FOR_DATA',None),
            ('vpd',{'input':'Вычисли VPD: temperature=25, rh=50, temperature_unit=C'},'DETERMINISTIC_TOOL',1.58388885875),
            ('rain',{'input':'Рассчитай rain_deficit: rain=[10,20], target=25, precipitation_unit=mm'},'DETERMINISTIC_TOOL',0),
            ('moscow_weather',{k:weather[k] for k in ('input','inputs','context')},'DETERMINISTIC_TOOL',9.52),
            ('local_reader',{'input':'Which crop is mentioned?','context':'Wheat is a cereal crop.','method':'local'},None,None),
            ('ru_cascade',{'input':'Какая культура названа в тексте?','context':'Пшеница является зерновой культурой.','method':'cascade'},None,None),
            ('offline_unknown',{'input':'Оцени условия без исходных данных и без источника.','method':'offline','offline':True},'ABSTAIN',None),
            ('direct_cloud',{'input':'Return RISK iff minimum_temperature < scenario_threshold, otherwise NO_RISK. Stipulated rule.','inputs':{'minimum_temperature':-2,'scenario_threshold':0},'method':'cloud'},'CLOUD_MODEL',None),
        ]
        rows=[]
        for name,body,route,numeric in cases:
            r=c.post('/api/query',json=body);r.raise_for_status();obj=r.json()
            passed=(route is None or obj['route']==route) and (numeric is None or abs(obj['output']['numeric']-numeric)<.00001)
            if name=='offline_unknown':passed &= obj['cloud_calls']==0
            if name=='direct_cloud':passed &= obj['output']['answer']=='RISK'
            rows.append({'case':name,'request':body,'result':obj,'functional_check_passed':bool(passed)})
            print(name,obj['route'],obj['output']['answer'],passed,flush=True)
        for name,body in [('invalid_json_object',[]),('empty_question',{'input':''}),('invalid_inputs',{'input':'x','inputs':[]})]:
            r=c.post('/api/query',json=body)
            rows.append({'case':name,'http_status':r.status_code,'functional_check_passed':r.status_code==400})
        with (out/'checks.jsonl').open('x',encoding='utf-8') as f:
            for row in rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        (out/'manifest.json').write_text(json.dumps({'date_utc':datetime.now(timezone.utc).isoformat(),'type':'live functional smoke, NOT statistically representative latency experiment','health':health,'checks':len(rows),'passed':sum(row['functional_check_passed'] for row in rows),'known_cost_usd':sum(row.get('result',{}).get('cost_usd') or 0 for row in rows)},ensure_ascii=False,indent=2),encoding='utf-8')
    print(out)
    if not all(r['functional_check_passed'] for r in rows):raise RuntimeError('Live functional check failed; inspect saved records')

if __name__=='__main__':main()
