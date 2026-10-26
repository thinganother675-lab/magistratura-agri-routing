from pathlib import Path
from datetime import datetime,timedelta,timezone
from collections import Counter
import json,hashlib,re
from dateutil.rrule import rrulestr
R=Path(__file__).resolve().parent
root=R.parent
plan_path=R/'plan.json'
old=json.loads(plan_path.read_text(encoding='utf-8'))
backup=R/'plan_6_superseded.json'
if not backup.exists():backup.write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf-8')
assert all(x['status']=='scheduled' for x in old['slots'])
days=[
 ('2026-10-16','FR',[(1,'13:05'),(2,'15:43'),(3,'17:17')]),
 ('2026-10-19','MO',[(4,'12:23'),(5,'14:51'),(6,'17:36')]),
 ('2026-10-20','TU',[(7,'12:41'),(8,'15:29'),(9,'17:47')]),
 ('2026-10-21','WE',[(10,'11:37'),(11,'14:19'),(12,'17:11')]),
 ('2026-10-22','TH',[(13,'13:17'),(14,'16:03')]),
]
ids=[93649,93651,93652,93653,93655,93656,93657,93659,93660,93661,93662,93663,93664,93665]
complexity=[2,3,3,3,3,3,3,4,3,4,4,5,4,4]
tz=timezone(timedelta(hours=3))
slots=[];automations=[]
for date,weekday,entries in days:
    times=[datetime.fromisoformat(f'{date}T{t}:00+03:00') for n,t in entries]
    gaps=[int((b-a).total_seconds()/60) for a,b in zip(times,times[1:])]
    assert all(60<=x<=180 for x in gaps)
    hours=sorted({t.hour for t in times});minutes=sorted({t.minute for t in times})
    candidates=[(h,m) for h in hours for m in minutes]
    positions=[candidates.index((t.hour,t.minute))+1 for t in times]
    rule=f'FREQ=DAILY;BYDAY={weekday};BYHOUR='+','.join(map(str,hours))+';BYMINUTE='+','.join(map(str,minutes))+';BYSECOND=0;BYSETPOS='+','.join(map(str,positions))+f';COUNT={len(entries)}'
    generated=list(rrulestr(rule,dtstart=datetime(2026,10,16,11,20,tzinfo=tz)))
    assert generated==times,(generated,times)
    automations.append(dict(date=date,rrule=rule,automation_id=old['automation_id'] if date=='2026-10-16' else None,slots=[n for n,t in entries],stop_after=(times[-1]+timedelta(minutes=15)).isoformat()))
    for (n,_),start in zip(entries,times):
        primary=root/'run_20261016/submission'/f'PZ{n:02}_Сарычев_ДЭ39-26.{"pdf" if n==14 else "docx"}'
        paths=[primary]
        if n==12:paths.append(root/'run_20261016/submission/PZ12_Model_Сарычев.xlsx')
        files=[]
        for p in paths:
            assert p.is_file(),p
            files.append(dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size))
        assert start.minute!=0
        slots.append(dict(pz=n,complexity=complexity[n-1],scheduled_at=start.isoformat(),start_window_ends_at=(start+timedelta(minutes=15)).isoformat(),activity_url=f'https://sdo.timacad.ru/mod/assign/view.php?id={ids[n-1]}',
            file=str(primary),sha256=files[0]['sha256'],bytes=files[0]['bytes'],files=files,expected_identity='Антоний Сарычев',group='ДЭ 39-26',status='scheduled',submitted_at=None))
assert [s['pz'] for s in slots]==list(range(1,15))
assert max(Counter(x['scheduled_at'][:10] for x in slots).values())<=3
plan=dict(old)
plan.update(revision=2,rescheduled_at=datetime.now(tz).isoformat(),authorization_scope='Все 14 готовых ПЗ, максимум три в день; время с ненулевыми минутами, интервалы 1–3 часа. Прямое изменение пользователя 16.10.2026.',
 automation_id=old['automation_id'],automations=automations,slots=slots,stop_after=automations[-1]['stop_after'],
 schedule_rationale='Сохранены пятница и понедельник; затем последовательные рабочие дни. Более длинные интервалы перед контрактом обмена, выбором архитектуры, проверкой модели и итоговой экспертизой. Интервалы — расписание загрузки, не запись времени выполнения заданий.')
plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
log_path=R/'slot_log.json';log=json.loads(log_path.read_text(encoding='utf-8'))
log['events'].append(dict(type='rescheduled',at=plan['rescheduled_at'],old_slots=6,new_slots=14,submitted_now=0,reason='Прямой запрос пользователя'))
log_path.write_text(json.dumps(log,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='prepared',automations=automations,slots=[dict(pz=s['pz'],at=s['scheduled_at'],files=len(s['files'])) for s in slots]),ensure_ascii=False,indent=2))
