"""Prepare / author one new Oct2 analytics workbook; historical XLSX stays immutable.

This collector has no model, provider, credential, Git or downloader interaction.
XLSX authoring uses the bundled artifact-tool JS runtime only. --build is for an
explicit quiet window; preparation can be performed without rendering/export.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import uuid
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEPS = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies"
NODE = DEPS / "node/bin/node.exe"
NODE_MODULES = DEPS / "node/node_modules"
MARKER = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/plugins/openai-primary-runtime/plugins/spreadsheets/skills/spreadsheets/container_tools/mark_artifact_operation_started.mjs"
OLD_XLSX = ROOT / "outputs/home_pc_final_20261002_analytics7b4c/home_pc_models_final150_20261002.xlsx"
OLD_SHA = "002619615be4d8a7a0f58409c15e8c15d1e10a02490830ff78ee27b84f79a04c"
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def nullable(value):
    return None if value in ("UNKNOWN", "N/A", "NOT RUN", "", None) else value


def relative(path):
    return Path(path).resolve().relative_to(ROOT).as_posix()


def resolve(value):
    path = Path(value)
    path = (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("Only project evidence is supported")
    return path


def last_file(pattern):
    files = sorted((ROOT / "results").glob(pattern))
    return files[-1] if files else None


def historic_rows():
    """Read typed saved values through ZIP/XML, never author with Python XLSX libs."""
    if sha(OLD_XLSX) != OLD_SHA:
        raise ValueError("Historical workbook has changed")
    with zipfile.ZipFile(OLD_XLSX) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ["".join(item.itertext()) for item in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        doc = ET.fromstring(archive.read("xl/worksheets/sheet3.xml"))
        records = []
        for row in doc.findall("s:sheetData/s:row", NS):
            if not 9 <= int(row.attrib["r"]) <= 53:
                continue
            values = {}
            for cell in row.findall("s:c", NS):
                key = "".join(ch for ch in cell.attrib["r"] if ch.isalpha())
                value = cell.find("s:v", NS)
                typ = cell.attrib.get("t")
                if typ == "s":
                    value = strings[int(value.text)]
                elif typ == "inlineStr":
                    value = "".join(cell.find("s:is", NS).itertext())
                elif value is None:
                    value = None
                elif typ in ("str", "e"):
                    if typ == "e":
                        raise ValueError("Historical XLSX contains a formula error")
                    value = value.text
                elif typ == "b":
                    value = value.text == "1"
                else:
                    value = float(value.text)
                    if value.is_integer():
                        value = int(value)
                values[key] = value
            records.append(values)
    if len(records) != 45:
        raise ValueError("Expected all 45 historical source series")
    rows = []
    source_hashes = {}
    # Map from the existing verified workbook. Reasons/counters are not recomputed
    # or pooled between CLI, reasoning profiles and different DEV selections.
    mapping = ["B", "A", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O",
               "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Z", "AA", "AB", "AC", "AD",
               "AE", "AF", "AG", "AH", "AI", "AJ", "AK", "C"]
    for rec in records:
        row = [nullable(rec.get(k)) for k in mapping]
        for index, coverage_index in ((8, 11), (9, 12), (10, 13)):
            if not row[coverage_index]:
                row[index] = None
        source = rec.get("AN")
        if not isinstance(source, str):
            raise ValueError("Historical source reference is missing")
        path = resolve(source)
        digest = source_hashes.setdefault(source, sha(path))
        rows.append(row + [source, digest])
    controls = {
        "series": len(rows),
        "api_n": sum(r[4] for r in rows if r[1] == "LM Studio API DEV"),
        "cli_n": sum(r[4] for r in rows if r[1] == "Historical CLI DEV"),
        "api_input": sum(r[8] or 0 for r in rows if r[1] == "LM Studio API DEV"),
        "api_output": sum(r[9] or 0 for r in rows if r[1] == "LM Studio API DEV"),
        "cli_input": sum(r[8] or 0 for r in rows if r[1] == "Historical CLI DEV"),
        "cli_output": sum(r[9] or 0 for r in rows if r[1] == "Historical CLI DEV"),
    }
    if controls != {"series": 45, "api_n": 242, "cli_n": 339, "api_input": 113332,
                    "api_output": 17259, "cli_input": 135133, "cli_output": 39087}:
        raise ValueError("Historical controls disagree with immutable verified source")
    return rows, controls


def token(summary, field):
    item = (summary.get("token_totals") or {}).get(field) or {}
    coverage = item.get("coverage", 0)
    return item.get("total") if coverage else None, coverage


def distribution(summary, field, statistic):
    return (summary.get(field) or {}).get(statistic)


def jsonl(path):
    path = Path(path)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []


def number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value >= 0


def reasoning_totals(records):
    values=[(r.get("usage",{}).get("completion_tokens_details") or {}).get("reasoning_tokens") for r in records]
    values=[v for v in values if number(v)]
    return (sum(values) if values else None),len(values)


def local_rows(selection_path, requested_paths, bitnet_path, bitnet_corrected_path=None):
    selection = load(selection_path)
    compatibility_path = selection_path.parent / "bitnet_compatibility.json"
    compatibility = load(compatibility_path)
    rows = []
    configurations=[("qwen", "Qwen3.5-4B",None), ("phi", "Phi-4-mini-instruct",None),
                    ("bitnet", "BitNet b1.58 2B4T legacy GGUF config",bitnet_path)]
    if bitnet_corrected_path:
        configurations.append(("bitnet_corrected", "BitNet b1.58 2B4T official-config alternative",bitnet_corrected_path))
    for key, label, native_path in configurations:
        native_mode = key.startswith("bitnet")
        native = load(native_path) if native_path else {}
        requested_path=requested_paths.get(key)
        q8 = load(requested_path) if requested_path else {}
        spec = compatibility if native_mode else selection["q8_models"][key]
        meta = native if native_mode else q8.get("models", {}).get(key, {})
        summary = meta.get("summary") or {}
        resources = meta.get("resources") or {}
        if native_mode:
            repo, rev, size, expected_sha = spec["model"], spec["model_revision"], 1187801280, None
            status = native.get("state") or compatibility.get("status") or "NOT_RUN"
            expected_sha=(native.get("model") or {}).get("sha256")
            note = "Native CPU I2_S runtime, not ordinary Q8/post-training IQ1. " + (
                "Measured live CPU run." if native else "Native inference NOT RUN; compatibility checkpoint only.")
            quant, requested, layers, rss = "native I2_S W1.58A8", 0, None, (native.get("own_process_memory") or {}).get("WorkingSet64")
            source = native_path or compatibility_path
            weight_state = "SHA256 VERIFIED by native driver" if native else "Weight validation UNKNOWN; compatibility " + compatibility.get("status", "UNKNOWN")
            if native:
                flags=(native.get("build_metadata") or {}).get("compiler_flags") or []
                if "GGML_CUDA=OFF" in flags and native.get("gpu_offload_requested_layers")==0:
                    layers=0
                    note += " CPU-only binary; whole-GPU usage is background, not BitNet allocation."
                startup=source.parent/"native_server_log.txt"
                if startup.is_file() and "GENERATION QUALITY WILL BE DEGRADED" in startup.read_text(encoding="utf-8"):
                    status="COMPATIBILITY_LIMITED: " + status
                    note += " Missing pre-tokenizer/degraded generation warning: scored quality is not intrinsic model ranking."
                if key=="bitnet_corrected":
                    note += " Separate official-config runtime compatibility alternative; original12 retained; configuration is an extra factor."
        else:
            repo, rev, size, expected_sha = spec["repo"], spec["revision"], spec["size"], spec["sha256"]
            status = meta.get("status") or "NOT_RUN"
            note = "Ordinary faithful Q8_0, same old DEV12 screening and optional remaining24; no confirmatory result."
            if not meta:
                note += " Download/validation checkpoint; downloaded does not mean benchmarked."
            quant, requested, layers, rss = "Q8_0", meta.get("requested_offload", spec["gpu"]), nullable(meta.get("actual_offloaded_layers")), None
            source = requested_path or selection_path
            fingerprint = (q8.get("fingerprints") or {}).get(key) or {}
            weight_state = "SHA256 VERIFIED by Q8 driver" if fingerprint.get("measured_sha256") == expected_sha else "Weight validation UNKNOWN; metadata " + selection.get("status", "UNKNOWN") + " at " + selection.get("recorded_utc", "UNKNOWN")
        input_tokens, input_cov = token(summary, "prompt_tokens")
        output_tokens, output_cov = token(summary, "completion_tokens")
        reason = summary.get("reasoning_tokens_reported") or {}
        n = summary.get("n", 0)
        raw_path = source.parent / ("bitnet_raw.jsonl" if native_mode else key + "_raw.jsonl")
        raw = jsonl(raw_path) if n else []
        native_tps=[r.get("local",{}).get("timing",{}).get("backend_tokens_per_second") for r in raw]
        native_tps=[v for v in native_tps if number(v)]
        backend_tps=statistics.median(native_tps) if native_tps else None
        auxiliary_path=source.parent / (key + "_backend_log_auxiliary.json")
        if not native_mode and n and auxiliary_path.is_file():
            auxiliary=load(auxiliary_path)
            if (auxiliary.get("complete_alignment") is True and auxiliary.get("unambiguously_aligned_n")==n
                    and auxiliary.get("raw_sha256")==sha(raw_path) and auxiliary.get("manifest_sha256")==sha(source)):
                backend_tps=auxiliary.get("backend_decode_tps_median")
                association=auxiliary.get("backend_process_association") or {}
                processes=association.get("processes") or []
                if len(processes)==1 and number(processes[0].get("WorkingSet64")):
                    rss=processes[0]["WorkingSet64"]
                    note += " RSS: " + association.get("status", "UNKNOWN") + "."
                note += " Native log alignment " + str(n) + "/" + str(n) + "; source in Методика."
            else:
                raise ValueError("Auxiliary log provenance mismatch for " + key)
        rows.append([label, "native CPU" if native_mode else "LM Studio API GPU", status,
                     meta.get("load_success") if not native_mode else ("own_server_pid" in native if native else None),
                     n, summary.get("correct") if n else None, summary.get("quality") if n else None,
                     summary.get("errors") if n else None, input_tokens, output_tokens,
                     reason.get("total") if reason.get("coverage") else None, input_cov, output_cov, reason.get("coverage", 0),
                     summary.get("latency_mean_s"), summary.get("latency_p50_s"), summary.get("latency_p95_s"),
                     summary.get("client_first_delta_p50_s"), summary.get("client_first_answer_delta_p50_s"),
                     summary.get("client_completion_tps_approx_p50"), backend_tps,
                     resources.get("vram_mib_peak_sampled_total"), resources.get("ram_gib_peak_sampled_system_used"),
                     rss, size / 2**30, quant, requested, layers, meta.get("cold_load_wall_s"),
                     repo, rev, expected_sha, note, weight_state, relative(source), sha(source)])
    return rows


def route_rows(path):
    if not path:
        return [], {"status": "NOT RUN"}
    report = load(path)
    if report.get("phase") != "EXPLORATORY_DEV_NOT_CONFIRMATORY":
        raise ValueError("Only new exploratory DEV routing analysis supported")
    run = resolve(report["run"])
    resources_path = run / "resources.json"
    resources = load(resources_path).get("summary", {}) if resources_path.is_file() else {}
    rows = []
    for method, s in report["methods"].items():
        def known(scope, field):
            item = s.get(scope, {}).get(field, {})
            return item.get("known_total") if item.get("coverage", 0) else None
        def cov(scope, field):
            return s.get(scope, {}).get(field, {}).get("coverage", 0)
        lat = s.get("latency_operational_all_s") or s.get("operational_latency_s") or s.get("latency_s") or {}
        successful = s.get("successful_latency_s") or {}
        def breakdown(field):
            return "; ".join(str(key) + ": " + str(value.get("correct", "?")) + "/" + str(value.get("n", "?"))
                             for key,value in s.get(field, {}).items())
        rows.append([method, s["intended_n"], s["recorded_n"], s["correct"], s["quality_intended"],
                     s["errors"], s["router_errors"], s.get("blocked_before_dispatch_decisions"), s["local_calls"],
                     s["generative_cloud_calls"], s["hosted_router_calls"], s["total_external_requests"], s["tool_calls"],
                     s["clarifications"], s["abstentions"], s["known_remote_cost_usd"], s["unknown_cost_events"],
                     s["known_cost_per_intended_request_usd"], lat.get("mean"), lat.get("p50"), lat.get("p95"),
                     successful.get("mean"), successful.get("p50"), successful.get("p95"),
                     distribution(s, "router_latency_ms", "p50"), known("local_tokens", "prompt_tokens"),
                     known("local_tokens", "completion_tokens"), cov("local_tokens", "prompt_tokens"), cov("local_tokens", "completion_tokens"),
                     known("cloud_tokens", "prompt_tokens"), known("cloud_tokens", "completion_tokens"), cov("cloud_tokens", "prompt_tokens"), cov("cloud_tokens", "completion_tokens"),
                     known("hosted_router_tokens", "input_tokens"), known("hosted_router_tokens", "output_tokens"), cov("hosted_router_tokens", "input_tokens"),
                     distribution(s, "local_client_ttft_s", "p50"), distribution(s, "local_client_tps_approx", "p50"),
                     distribution(s, "local_backend_tps", "p50"), s.get("laya_cpu_rss_peak_bytes"),
                     resources.get("vram_mib_peak_sampled_total"), resources.get("ram_gib_peak_sampled_system_used"),
                     breakdown("by_language"), breakdown("by_category"),
                     relative(path), sha(path)])
    if len(rows) != 6:
        raise ValueError("All six routing policy records must remain present")
    return rows, report


def openrouter_rows(path):
    data = load(path)
    raw = jsonl(path.parent / "raw.jsonl")
    rows = []
    for s in data["rows"]:
        consolidated=isinstance(s.get("attempts"),list)
        attempt_n=s.get("generation_attempts") if consolidated else s.get("attempts",0)
        inp, out = s.get("known_input_tokens") or {}, s.get("known_output_tokens") or {}
        if consolidated:
            coverage=s.get("token_usage_coverage") or {}
            inp={"known_sum":s.get("input_tokens"),"coverage_n":coverage.get("known_n",0)}
            out={"known_sum":s.get("output_tokens"),"coverage_n":coverage.get("known_n",0)}
        reasoning = s.get("reasoning_tokens") or {}
        reason_total, reason_coverage = reasoning_totals([r for r in raw if r.get("model_requested")==s.get("resolved_model_id")])
        if not reasoning:
            reasoning={"known_sum":reason_total,"coverage_n":reason_coverage}
        successful=s.get("successful_generations")
        rows.append([s["requested_display_name"], s.get("resolved_model_id"), s["status"],
                     s.get("scope"), s.get("test_scope", "ACCESS_DIAGNOSTIC_ONLY" if consolidated and attempt_n else "METADATA_ONLY"), attempt_n,
                     successful, s.get("correct") if successful else None, s.get("accuracy_all_attempts") if successful else None,
                     sum(a.get("http_status")!=200 for a in s.get("attempts",[])) if consolidated else s.get("errors"), s.get("structured_failures"), inp.get("known_sum"), out.get("known_sum"),
                     reasoning.get("known_sum"), inp.get("coverage_n", 0), out.get("coverage_n", 0), reasoning.get("coverage_n", 0),
                     s.get("mean_latency_seconds") if successful else None, s.get("p50_latency_seconds") if successful else None, s.get("p95_latency_seconds") if successful else None,
                     s.get("ttft_seconds"), s.get("tokens_per_second"), s.get("reported_cost_known_sum_usd"),
                     attempt_n if consolidated and s.get("reported_cost_usd") is None else s.get("unknown_cost_events"), s.get("provider_endpoint_pinned",s.get("endpoint_pinned")), s.get("identity_stability"),
                     s.get("reason"), relative(path), sha(path)])
    if len(rows) != 21:
        raise ValueError("OpenRouter needs all 21 requested display names")
    return rows


JS = r'''import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook,SpreadsheetFile,FileBlob} from '@oai/artifact-tool';
const out=path.dirname(fileURLToPath(import.meta.url));
const data=JSON.parse(await fs.readFile(path.join(out,'workbook_data.json'),'utf8'));
const wb=Workbook.create(),FONT='Arial',DARK='#253F5B',TEXT='#172B3A',MUTED='#536577';
const col=n=>{let s='';while(n){s=String.fromCharCode(65+(n-1)%26)+s;n=Math.floor((n-1)/26);}return s;};
const checks=[];
for(const spec of data.sheets){
 const sheet=wb.worksheets.add(spec.name),first=7,last=first+Math.max(spec.rows.length,1)-1,end=col(spec.headers.length);
 sheet.showGridLines=false;sheet.tabColor=spec.color;
 sheet.getRange(`A1:${end}${last}`).format={font:{name:FONT,size:11,color:TEXT},verticalAlignment:'center',rowHeight:26};
 sheet.getRange('A1').format.rowHeight=10;
 sheet.getRange('A2').values=[[spec.title]];
 sheet.getRange('A2').format.font={name:FONT,size:15,bold:true,color:DARK};
 sheet.getRange(`A2:${end}2`).format.borders={bottom:{style:'thin',color:'#A8B6C3'}};
 sheet.getRange('A3').values=[[spec.note]];sheet.getRange('A3').format.font={name:FONT,size:11,italic:true,color:MUTED};
 sheet.getRange(`A6:${end}6`).values=[spec.headers];
 sheet.getRange(`A6:${end}6`).format={fill:DARK,font:{name:FONT,size:11,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'center',verticalAlignment:'center',rowHeight:64,borders:{insideVertical:{style:'thin',color:'#FFFFFF'}}};
 if(spec.rows.length){sheet.getRange(`A7:${end}${last}`).values=spec.rows;}
 sheet.getRange(`A7:${end}${last}`).format.horizontalAlignment='right';
 sheet.getRange(`A7:${end}${last}`).format.wrapText=false;
 spec.widths.forEach((width,i)=>sheet.getRange(`${col(i+1)}1:${col(i+1)}${last}`).format.columnWidth=width);
 for(const i of spec.text){sheet.getRange(`${col(i+1)}7:${col(i+1)}${last}`).format.horizontalAlignment='left';}
 if(spec.name==='Новые локальные'){for(const c of ['A','C','AG','AH'])sheet.getRange(`${c}7:${c}${last}`).format.wrapText=true;sheet.getRange(`A7:${end}${last}`).format.rowHeight=78;}
 if(spec.name==='OpenRouter21'){for(const c of ['A','B','C','D','E','AA'])sheet.getRange(`${c}7:${c}${last}`).format.wrapText=true;sheet.getRange(`A7:${end}${last}`).format.rowHeight=62;}
 if(spec.name==='Маршруты DEV'){for(const c of ['AQ','AR'])sheet.getRange(`${c}7:${c}${last}`).format.wrapText=true;sheet.getRange(`A7:${end}${last}`).format.rowHeight=78;}
 if(spec.name==='Методика'){sheet.getRange(`A7:C${last}`).format.wrapText=true;sheet.getRange(`A7:C${last}`).format.rowHeight=62;}
 for(const [indexes,format] of spec.formats){for(const i of indexes){sheet.getRange(`${col(i+1)}7:${col(i+1)}${last}`).setNumberFormat(format);}}
 for(const [target,formula] of (spec.formulas||[])){sheet.getRange(`${target}7`).formulas=[[formula]];sheet.getRange(`${target}7:${target}${last}`).fillDown();}
 if(spec.rows.length){const table=sheet.tables.add(`A6:${end}${last}`,true,spec.table);table.showFilterButton=true;}
 sheet.freezePanes.freezeRows(6);sheet.freezePanes.freezeColumns(2);
 for(const i of spec.status){const r=sheet.getRange(`${col(i+1)}7:${col(i+1)}${last}`);
  for(const text of ['BLOCKED','NOT_RUN','NOT RUN','RATE_LIMITED','PARTIAL','PAID_NOT_AUTHORIZED'])r.conditionalFormats.add('containsText',{text,format:{fill:'#FFF1D6',font:{color:'#825A12'}}});}
 if(spec.rows.length){for(const block of spec.previews){checks.push({sheet:spec.name,range:block});}}
}
wb.recalculate();
const errorReport=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},maxChars:6000});
await fs.writeFile(path.join(out,'formula_error_scan.ndjson'),errorReport.ndjson);
const errorLines=errorReport.ndjson.trim().split('\n').filter(Boolean).map(JSON.parse);
if(!errorLines.some(x=>x.kind==='notice'&&/matched 0 entries/.test(x.message||'')))throw new Error('Formula error scan did not confirm zero matches');
const spot=await wb.inspect({kind:'table',range:'Маршруты DEV!A6:U12',include:'values,formulas',tableMaxRows:7,tableMaxCols:21,maxChars:8000});
await fs.writeFile(path.join(out,'route_inspection.ndjson'),spot.ndjson);
for(let i=0;i<checks.length;i++){const p=checks[i];const blob=await wb.render({sheetName:p.sheet,range:p.range,scale:1,format:'png'});await fs.writeFile(path.join(out,`qa_${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await blob.arrayBuffer()));}
const filename='magistratura_continuation_20261002.xlsx';
const file=await SpreadsheetFile.exportXlsx(wb);await file.save(path.join(out,filename));
const imported=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(out,filename)));
const summary=await imported.inspect({kind:'sheet',include:'id,name',maxChars:4000});
await fs.writeFile(path.join(out,'reimport_sheets.ndjson'),summary.ndjson);
// Export/reimport representative typed cells and recalculation boundaries.
const metrics={};
let checkedCells=0,checkedFormulaCells=0;
for(const spec of data.sheets){
 const sheet=imported.worksheets.getItem(spec.name),values=sheet.getRange(`A7:${col(spec.headers.length)}${6+spec.rows.length}`).values;
 const formulaColumns=new Set((spec.formulas||[]).map(([c])=>c));
 for(let r=0;r<spec.rows.length;r++){for(let c=0;c<spec.headers.length;c++){
  if(formulaColumns.has(col(c+1))){
   if(spec.name!=='История45'||col(c+1)!=='G')throw new Error('Unexpected formula validation scope');
   const n=spec.rows[r][4],correct=spec.rows[r][5],want=n&&typeof correct==='number'?correct/n:null;
   const got=values[r]?.[c]=== ''?null:(values[r]?.[c]??null);
   if(!(want===null?got===null:typeof got==='number'&&Math.abs(got-want)<=1e-10))throw new Error(`Quality formula mismatch: G${7+r}`);
   checkedFormulaCells++;continue;
  }
  const want=spec.rows[r][c]??null,got=values[r]?.[c]??null;
  const ok=typeof want==='number'&&typeof got==='number'?Math.abs(want-got)<=1e-9*Math.max(1,Math.abs(want)):want===got;
  if(!ok)throw new Error(`Reimport value mismatch: ${spec.name}!${col(c+1)}${7+r}`);
  checkedCells++;
 }}
 metrics[spec.name]={rows:spec.rows.length,firstRow:values[0].slice(0,12)};
}
metrics.validation={nonformula_typed_cells_checked:checkedCells,quality_formula_cells_checked:checkedFormulaCells,result:'PASS'};
await fs.writeFile(path.join(out,'reimport_checks.json'),JSON.stringify(metrics,null,2));
console.log(JSON.stringify({xlsx:path.join(out,filename),sheets:data.sheets.length,visual_checks:checks.length,source_controls:data.historical_controls}));
'''


def spec(name, title, note, headers, rows, text, formats, widths, previews, *, status=(), formulas=(), color="#486681"):
    if any(len(r) != len(headers) for r in rows) or len(widths) != len(headers):
        raise ValueError(name + " table shape mismatch")
    return dict(name=name,title=title,note=note,headers=headers,rows=rows,text=text,formats=formats,
                widths=widths,previews=previews,status=list(status),formulas=list(formulas),color=color,
                table="Continuation" + str(uuid.uuid4().hex[:8]))


def assemble(args):
    history, controls = historic_rows()
    route_path = resolve(args.prerouting_analysis) if args.prerouting_analysis else None
    requested_paths={}
    for path in sorted((ROOT / "results").glob("*_requested_local_dev/manifest.json")):
        for key in load(path).get("models",{}):
            if key in ("qwen","phi"):
                requested_paths[key]=path
    if args.requested_manifest:
        path=resolve(args.requested_manifest)
        for key in load(path).get("models",{}):
            if key in ("qwen","phi"):
                requested_paths[key]=path
    for key in ("qwen","phi"):
        if getattr(args,key+"_manifest"):
            requested_paths[key]=resolve(getattr(args,key+"_manifest"))
    originals=sorted((ROOT / "results").glob("*_bitnet_native_dev/manifest.json"))
    bitnet_path = resolve(args.bitnet_manifest) if args.bitnet_manifest else (originals[0] if originals else None)
    bitnet_corrected_path=resolve(args.bitnet_corrected_manifest) if args.bitnet_corrected_manifest else None
    if bitnet_corrected_path==bitnet_path and bitnet_corrected_path is not None:
        raise ValueError("Corrected native configuration must be a separate immutable run")
    selection_path = resolve(args.selection_manifest) if args.selection_manifest else last_file("*_requested_local_metadata/selection_manifest.json")
    or_path = resolve(args.openrouter_summary) if args.openrouter_summary else last_file("*_openrouter_zero_diagnostic/current_21_model_matrix.json") or last_file("*_openrouter21_screen/summary.json")
    if not or_path:
        correction = last_file("*_openrouter21_metadata/eligibility_correction_v2.json")
        or_path = correction if correction else last_file("*_openrouter21_metadata/manifest.json")
    local = local_rows(selection_path,requested_paths,bitnet_path,bitnet_corrected_path)
    routes, route_report = route_rows(route_path)
    ors = openrouter_rows(or_path)
    route_headers = ["Политика","N план","N записан","Верно","Качество / N план","Ошибки решения","Ошибки router","До HTTP blocked N","Local calls","Cloud generation","Hosted router calls","Все внешние requests","Tool calls","Clarify","Abstain","Известно USD","Unknown cost events","USD / N план известно","Среднее E2E, с","p50 E2E, с","p95 E2E, с","Success mean, с","Success p50, с","Success p95, с","Router p50, ms","Local input","Local output","Local input coverage","Local output coverage","Cloud input","Cloud output","Cloud input coverage","Cloud output coverage","Router input","Router output","Router input coverage","Client TTFT p50, с","Client approx tok/s","Native backend tok/s","Laya RSS peak B","VRAM run-wide MiB","RAM run-wide GiB","По языкам","По категориям","Источник","SHA256 источника"]
    local_headers = ["Модель","Runtime","Test status","Load success","N","Верно","Качество","Ошибки","Input известно","Output известно","Reasoning известно","Input coverage N","Output coverage N","Reasoning coverage N","Среднее, с","p50, с","p95, с","Client TTFT p50, с","Первый answer p50, с","Client approx tok/s","Native backend tok/s","VRAM весь GPU MiB","RAM весь ПК GiB","Process RSS B","Main expected GiB","Квантование","Offload requested","Actual GPU layers","Cold load, с","HF repo","Revision","Expected main SHA256","Ограничения / статус","Weight validation","Источник","SHA256 источника"]
    or_headers = ["Requested display name","Actual model ID","Статус","Scope","Объём теста","Попыток","Успешных генераций","Верно","Качество попыток","Ошибки","Structured failures","Input известно","Output известно","Reasoning известно","Input coverage N","Output coverage N","Reasoning coverage N","Среднее, с","p50, с","p95, с","TTFT, с","tok/s","Reported cost USD","Unknown cost events","Pinned endpoint","Identity stability","Причина / ограничения","Источник","SHA256 источника"]
    history_headers = ["Модель","Серия","Выборка","Статус","N","Верно","Качество","Ошибки","Input известно","Output известно","Reasoning известно","Input coverage N","Output coverage N","Reasoning coverage N","Среднее, с","p50, с","p95, с","Client delta p50, с","Client answer p50, с","Client approx tok/s","Native TTFT p50, с","Native decode tok/s","VRAM весь GPU MiB","RAM весь ПК GiB","Каталог files GiB","Квантование","Offload requested","Actual GPU layers","Контекст","Parallel","Temperature requested","Max tokens","Seed","Cold load, с","Reasoning профиль","Run ID","Источник","SHA256 источника"]
    definitions = [
        ["Статус исследования","Observed DEV exploratory; old final150 observed","human_review FALSE; new independent confirmatory holdout NOT RUN"],
        ["Качество","Correct / declared intended N or individual measured N","Нет общего рейтинга между CLI/API, разными DEV/profile или unequal probes"],
        ["Пропущенные числа","Пустая numeric cell означает UNKNOWN / NOT RUN / N/A","Реальный измеренный0 сохраняется; рядом coverage and status"],
        ["Input/output","Provider reported usage counters; known subtotal and coverage","Partial usage does not establish the full total"],
        ["Reasoning tokens","Subset of output if provider reports that accounting","Не прибавляется ещё раз к output; неизвестный subtotal blank"],
        ["TTFT клиентский","First nonempty streaming delta at this client","Includes transport; first answer may occur after reasoning"],
        ["Native TTFT/tok/s","Backend metric only when proven same request or saved aligned log","Client approx TPS is a separate estimate; UNKNOWN not replaced"],
        ["VRAM","Sampled entire GPU MiB, not weight allocation","Routing table peak applies to whole run, not individual policy"],
        ["RAM","Sampled entire system GiB","Process RSS B is separate; missing reliable PID association remains blank"],
        ["GPU offload","Requested fraction/max/layers separate from actual backend layers","LM Studio native model listing may omit actual offload config"],
        ["Prefix/KV caching","Native traces can report cache_n384 and reuse system-prefix KV","No hidden warm-up does not mean cold requests; cache reuse is distinct from saved-answer replay"],
        ["BitNet configurations","Original legacy GGUF config and official-config compatibility alternative remain separate rows","Do not pool N/tokens/quality/latency; runtime config is an extra experimental factor"],
        ["Каталог files GiB","Historical model directory can include mmproj/config files","New Main weights GiB specifically main GGUF; don't equate them"],
        ["Полная E2E latency","Routing: router + gate + provider + resource guard","All journaled decisions, including blocked/failed, use the same operational latency scope"],
        ["Success latency","MEASURED with output object and no final decision error","Technical completion, not correct-answer latency; router fallback can still occur"],
        ["Hosted Jev","Counts as external request even if chosen generator is local","Generative cloud calls and total external calls are distinct"],
        ["Стоимость","Known estimate/reported cost; unknown events retained","Provider invoice/account ownership UNKNOWN; OpenRouter paid authorization$0"],
        ["Offline","Local Laya + LM Studio loopback; no hosted router/cloud","Actual raw counters, not reused hosted answers"],
        ["Исторический Excel","Old XLSX immutableSHA " + OLD_SHA,"All45 series retained; no original output edited"],
        ["Исторические controls",json.dumps(controls,ensure_ascii=False),"Source counters verified exactly"],
        ["Дата создания UTC","UTC " + datetime.now(timezone.utc).isoformat(),"Actual execution date; no backdating"],
        ["Источники нового DEV",relative(route_path) if route_path else "NOT RUN",sha(route_path) if route_path else None],
        ["Источники моделей",json.dumps({k:relative(v) for k,v in requested_paths.items()},ensure_ascii=False) if requested_paths else relative(selection_path),"Each model row retains its own independent manifest and SHA256"],
        ["Источники BitNet",relative(bitnet_path) if bitnet_path else relative(selection_path.parent / "bitnet_compatibility.json"),sha(bitnet_path or selection_path.parent / "bitnet_compatibility.json")],
        ["Источники OpenRouter",relative(or_path),sha(or_path)],
    ]
    if bitnet_corrected_path:
        definitions.append(["BitNet official-config alternative",relative(bitnet_corrected_path),sha(bitnet_corrected_path)])
    or_data=load(or_path)
    if "metadata_get_requests" in or_data:
        definitions.extend([
            ["OpenRouter external accounting",str(or_data.get("total_external_requests"))+" total = "+str(or_data.get("metadata_get_requests"))+" GET metadata + "+str(or_data.get("credential_setup_post_requests"))+" setup POST + "+str(or_data.get("generation_attempts"))+" failed completions","0 successful generations; failed diagnostic latency is not model generation speed"],
            ["OpenRouter cost/token coverage",json.dumps(or_data.get("cost_usage_coverage"),ensure_ascii=False),"No provider usage/cost evidence for three HTTP failures; paid cap$0; account aggregate does not establish individual billing"],
            ["OpenRouter free quota",json.dumps(or_data.get("current_global_daily_free_requests"),ensure_ascii=False),"Account-wide quota snapshot; no per-key rotation and no privacy preference change"],
        ])
    for key,path in requested_paths.items():
        auxiliary=path.parent/(key+"_backend_log_auxiliary.json")
        if auxiliary.is_file():
            definitions.append([key+" native metrics auxiliary",relative(auxiliary),sha(auxiliary)])
    route_note="36 previously observed DEV cases; 6 live arms. Shared guards versus historical cascade are an explicit extra factor. New confirmatory NOT RUN."
    if not routes:
        route_note="NOT RUN. Live routing results pending; no placeholder scores. Observed old150 is excluded from tuning."
    widths_history=[46,25,16,25,8,10,12,10,16,16,16,15,15,16,12,12,12,16,16,16,16,16,17,16,17,18,18,17,12,11,15,12,10,13,20,43,86,70]
    return {"created_utc":datetime.now(timezone.utc).isoformat(),"historical_controls":controls,
            "source_paths":{"routing":relative(route_path) if route_path else None,"requested":{k:relative(v) for k,v in requested_paths.items()},"bitnet":relative(bitnet_path) if bitnet_path else None,"bitnet_corrected":relative(bitnet_corrected_path) if bitnet_corrected_path else None,"openrouter":relative(or_path)},
            "sheets":[
                spec("Маршруты DEV","Предварительная маршрутизация, 2 октября",route_note,route_headers,routes,[0,42,43,44,45],[( [4],"0.0%"),([15,17],"0.00000000"),([18,19,20,21,22,23,36],"0.000"),([24,37,38,41],"0.00")], [26]+[13]*41+[45,105,170,70], ["A1:X13","Y6:AP13","AQ6:AT13"],status=[0],color="#253F5B"),
                spec("Новые локальные","Запрошенные компактные локальные baseline","Ordinary Q8_0 and native ternary CPU are separate runtime experiments. UNKNOWN metrics remain blank.",local_headers,local,[0,1,2,25,26,27,29,30,31,32,33,34,35],[([6],"0.0%"),([14,15,16,17,18,28],"0.000"),([19,20,22,24],"0.00")],[44,24,26,15]+[13]*25+[50,48,70,110,90,90,70],[f"A1:T{7+len(local)}",f"U6:AJ{7+len(local)}"],status=[2],color="#486681"),
                spec("OpenRouter21","Все 21 запрошенное имя OpenRouter","FREE ONLY $0 new paid authorization; probes/unequalN are not a model ranking. Remote VRAM/RAM/offload N/A.",or_headers,ors,[0,1,2,3,4,24,25,26,27,28],[([8],"0.0%"),([17,18,19,20,21],"0.000"),([22],"0.00000000")],[44,52,29,31,55]+[14]*19+[45,31,120,95,70],["A1:M28","N6:AC28"],status=[2],color="#486681"),
                spec("История45","Все 45 исторических серий, 1–2 октября","CLI/API/reasoningprofiles and different DEV selections remain separate; partial coverage is visible.",history_headers,history,[0,1,2,3,25,26,27,34,35,36,37],[([6],"0.0%"),([14,15,16,17,18,20,33],"0.000"),([19,21,23,24],"0.00")],widths_history,["A1:N19","O6:AB19","AC6:AL19","A43:N51"],status=[3],formulas=[("G",'=IF(E7=0,"",IF(ISNUMBER(F7),F7/E7,""))')],color="#768DA2"),
                spec("Методика","Определения, coverage и воспроизводимость","Human validation FALSE. Each source is an immutable or versioned project artifact.",["Поле","Определение / значение","Ограничение"],definitions,[0,1,2],[],[33,155,115],["A1:C17",f"A18:C{6+len(definitions)}"],color="#909EA9"),
            ]}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path)
    p.add_argument("--prerouting-analysis");p.add_argument("--requested-manifest");p.add_argument("--bitnet-manifest")
    p.add_argument("--qwen-manifest");p.add_argument("--phi-manifest")
    p.add_argument("--bitnet-corrected-manifest")
    p.add_argument("--selection-manifest");p.add_argument("--openrouter-summary")
    p.add_argument("--build",action="store_true",help="Author/render only in root-approved quiet window")
    args=p.parse_args()
    out=resolve(args.out) if args.out else ROOT/"outputs"/("continuation_20261002_"+datetime.now(timezone.utc).strftime("%H%M%SZ")+"_"+uuid.uuid4().hex[:8])
    if not out.is_relative_to(ROOT/"outputs"):
        raise ValueError("New workbook outputs must be inside outputs")
    if out.is_relative_to(OLD_XLSX.parent):
        raise ValueError("Historical output directory is immutable")
    out.mkdir(parents=True,exist_ok=True)
    data=assemble(args)
    write(out/"workbook_data.json",data)
    (out/"build_workbook.mjs").write_text(JS,encoding="utf-8")
    write(out/"source_validation.json",{"historical_controls":data["historical_controls"],"old_xlsx_sha256":sha(OLD_XLSX),"data_sha256":sha(out/"workbook_data.json"),"human_review":False,"new_confirmatory":"NOT RUN","sources":data["source_paths"]})
    if args.build:
        if not (out/"node_modules").exists():
            # Single controlled junction to the read-only bundled dependency root.
            subprocess.run(["cmd.exe","/d","/c","mklink","/J",str(out/"node_modules"),str(NODE_MODULES)],check=True,capture_output=True,text=True)
        marker=out/"operation_started.txt"
        if not marker.exists():
            result=subprocess.run([str(NODE),str(MARKER),"--operation-kind","create","--expected-output-count","1","--output-format","xlsx"],check=True,capture_output=True,text=True)
            marker.write_text(result.stdout,encoding="utf-8")
        subprocess.run([str(NODE),str(out/"build_workbook.mjs")],cwd=out,check=True)
        if sha(OLD_XLSX)!=OLD_SHA:
            raise ValueError("Historical workbook changed during authoring")
    print(json.dumps({"output":relative(out),"build":args.build,"sheets":{s["name"]:len(s["rows"]) for s in data["sheets"]},"historical_controls":data["historical_controls"]},ensure_ascii=True))


if __name__=="__main__":
    main()
