"""Public policy catalogue only; no inference or settings changes."""
from pathlib import Path
from datetime import datetime,timezone
import json
import httpx

OUT=Path(__file__).resolve().parent
url='https://openrouter.ai/api/v1/endpoints/zdr'
response=httpx.get(url,timeout=30,follow_redirects=False)
body=response.json() if response.status_code==200 else None
result={'retrieved_utc':datetime.now(timezone.utc).isoformat(),'url':url,
        'http_status':response.status_code,'response':body,'external_metadata_requests':1,
        'generation_attempts':0,'settings_changed':False}
(OUT/'zdr_catalogue.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
data=body.get('data') if isinstance(body,dict) else None
print(json.dumps({'status':response.status_code,'body_keys':list(body) if isinstance(body,dict) else None,
                  'data_type':type(data).__name__,'data_n':len(data) if isinstance(data,(list,dict)) else None,
                  'first_two':data[:2] if isinstance(data,list) else None}))
