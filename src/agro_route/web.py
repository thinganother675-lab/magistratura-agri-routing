from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import time
from .models import configured_models
from .routing import decide

ROOT=Path(__file__).resolve().parents[2]

def parse_inline_inputs(q):
    data={}
    # Explicit key=value syntax only; never guess base temperature or units.
    for key,value in re.findall(r"\b(tmin|tmax|base|temperature|rh|rn|g|u2|es|ea|delta|gamma|target|rain|temperature_unit|precipitation_unit)\s*=\s*(\[[^\]]*\]|-?\d+(?:\.\d+)?|[A-Za-z]+)",q):
        try: data[key]=json.loads(value)
        except json.JSONDecodeError:data[key]=value
    return data

def demo_weather():
    path=ROOT/"data/raw/nasa_moscow_week.json"
    obj=json.loads(path.read_text(encoding="utf-8"));p=obj["properties"]["parameter"]
    lo=list(p["T2M_MIN"].values());hi=list(p["T2M_MAX"].values())
    if len(lo)!=7 or len(hi)!=7 or any(v==-999 for v in lo+hi): raise ValueError("Missing NASA data")
    return {"input":"Рассчитай сумму эффективных температур GDD для учебного участка в Московской области. base=5 задан сценарием, не нормой картофеля.","inputs":{"tmin":lo,"tmax":hi,"base":5,"temperature_unit":"C"},"context":"", "source":json.loads((ROOT/"data/raw/nasa_manifest.json").read_text())}

def serve(port=8090):
    local,cloud=configured_models()
    class Handler(BaseHTTPRequestHandler):
        def send(self,status,body,kind="application/json; charset=utf-8"):
            self.send_response(status);self.send_header("Content-Type",kind);self.send_header("Cache-Control","no-store");self.send_header("X-Content-Type-Options","nosniff");self.end_headers()
            self.wfile.write(body if isinstance(body,bytes) else json.dumps(body,ensure_ascii=False).encode())
        def do_GET(self):
            if self.path=="/":self.send(200,(Path(__file__).parent/"static/index.html").read_bytes(),"text/html; charset=utf-8")
            elif self.path=="/api/health":self.send(200,{"ok":True,"local_model":local.model,"cloud_model":cloud.model,"cloud_configured":bool(cloud.key),"cloud_enabled":os.getenv("CLOUD_AVAILABLE","false").lower()=="true"})
            elif self.path=="/api/weather":self.send(200,demo_weather())
            else:self.send(404,{"error":"Not found"})
        def do_POST(self):
            if self.path!="/api/query":return self.send(404,{"error":"Not found"})
            if self.headers.get("Origin") and self.headers["Origin"] not in (f"http://127.0.0.1:{port}",f"http://localhost:{port}"):
                return self.send(403,{"error":"Origin rejected"})
            try:
                length=int(self.headers.get("Content-Length","0"))
                if not 0<length<=20000:return self.send(400,{"error":"Request size"})
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict):return self.send(400,{"error":"Request must be a JSON object"})
                q=body.get("input","")
                if not isinstance(q,str) or not q.strip() or len(q)>6000:return self.send(400,{"error":"Question required, max 6000 characters"})
                inputs=body.get("inputs",{})
                if not isinstance(inputs,dict):return self.send(400,{"error":"inputs must be a JSON object"})
                context=body.get("context","")
                if not isinstance(context,str) or len(context)>10000:return self.send(400,{"error":"Context size"})
                request={"input":q,"context":context,"inputs":{**parse_inline_inputs(q),**inputs}}
                method=body.get("method","cascade")
                if method not in ("cascade","rule","local","cloud","offline","tool_cloud"):return self.send(400,{"error":"Unknown policy"})
                enabled=os.getenv("CLOUD_AVAILABLE","false").lower()=="true" and bool(cloud.key) and not body.get("offline",False)
                frozen=ROOT/"data/protocol_frozen.json"
                threshold=json.loads(frozen.read_text())["rule_threshold_chars"] if frozen.exists() else 900
                result=decide(request,method,local.call,cloud.call,enabled,threshold)
                result['stages']=[{k:stage.get(k) for k in ('model','latency_ms','cost_usd','error')} for stage in result.pop('trace',[])]
                result['cloud_available']=enabled
                result["models"]={"local":local.model,"cloud":cloud.model}
                self.send(200,result)
            except (ValueError,TypeError) as exc:self.send(400,{"error":type(exc).__name__})
        def log_message(self,*args):pass
    print(f"Agro Route Lab: http://127.0.0.1:{port}",flush=True)
    ThreadingHTTPServer(("127.0.0.1",port),Handler).serve_forever()
