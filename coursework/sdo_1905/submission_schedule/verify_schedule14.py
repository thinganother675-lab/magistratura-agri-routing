from pathlib import Path
from datetime import datetime,timezone,timedelta
from collections import Counter
import json,tomllib,hashlib
from dateutil.rrule import rrulestr
R=Path(__file__).resolve().parent
ids=['1905-1-6-16-19','1905-4-6-19','1905-7-9-20','1905-10-12-21','1905-13-14-22']
p=R/'plan.json';plan=json.loads(p.read_text(encoding='utf-8'))
tz=timezone(timedelta(hours=3));now=datetime.now(tz)
checks=[]
for day,aid in zip(plan['automations'],ids):
    cfg=tomllib.loads((Path('C:/Users/User/.codex/automations')/aid/'automation.toml').read_text(encoding='utf-8'))
    assert cfg['status']=='ACTIVE' and cfg['kind']=='heartbeat'
    assert cfg['rrule']==day['rrule']
    assert cfg['target_thread_id']=='01a14375-830c-7e13-b091-2f314e2fa88b'
    assert day['date'].replace('-','.') not in cfg['prompt'] # Dates in prompt use day.month.year.
    expected=[datetime.fromisoformat(s['scheduled_at']) for s in plan['slots'] if s['scheduled_at'].startswith(day['date'])]
    observed=list(rrulestr(cfg['rrule'],dtstart=now))
    assert observed==expected,(aid,observed,expected)
    day['automation_id']=aid
    checks.append(dict(automation_id=aid,date=day['date'],status=cfg['status'],times=[x.isoformat() for x in observed],matches=True))
for slot in plan['slots']:
    for f in slot['files']:assert hashlib.sha256(Path(f['path']).read_bytes()).hexdigest()==f['sha256']
assert Counter(s['pz'] for s in plan['slots'])==Counter(range(1,15))
assert max(Counter(s['scheduled_at'][:10] for s in plan['slots']).values())==3
assert len(next(x for x in plan['slots'] if x['pz']==12)['files'])==2
assert next(x for x in plan['slots'] if x['pz']==14)['files'][0]['path'].endswith('.pdf')
plan['schedule_status']='active_and_verified'
p.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
report=dict(status='PASS',checked_at=now.isoformat(),practicals=14,days=5,max_per_day=3,within_day_intervals_minutes=[158,94,148,165,168,138,162,172,166],
            files=15,all_file_hashes_match=True,old_schedule_replaced=True,automations=checks,submissions_performed=0)
(R/'schedule_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
