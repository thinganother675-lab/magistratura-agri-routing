import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile, FileBlob } from '@oai/artifact-tool';

const outputDir = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(outputDir, '../..');
const sourceCheckOnly = process.argv[2] === '--source-check';
const devPreviewOnly = process.argv[2] === '--preview-dev';
const noFinal = sourceCheckOnly || devPreviewOnly;
const finalAnalysisRel = noFinal ? null : process.argv[2];
if (!finalAnalysisRel && !noFinal) throw new Error('Pass the actual final analysis statistics.json path; no placeholder results are authored.');
const UNKNOWN = 'UNKNOWN';
const NA = 'N/A';
const isNum = x => typeof x === 'number' && Number.isFinite(x);
const shown = x => x === null || x === undefined ? UNKNOWN : x;
const sum = xs => xs.reduce((a,x) => a + (isNum(x) ? x : 0), 0);
const eq = (a,b,label) => {if (a !== b) throw new Error(`${label}: ${a} != ${b}`);};
const readJson = async rel => JSON.parse(await fs.readFile(path.resolve(root,rel),'utf8'));
const readJsonl = async rel => (await fs.readFile(path.resolve(root,rel),'utf8')).trim().split(/\r?\n/).filter(Boolean).map(JSON.parse);
const sha = text => crypto.createHash('sha256').update(text).digest('hex');
const apiRel = 'results/20261001_api_tables_35768dbf/summary.json';
const cliRel = 'results/20261001_inventory_summary_3f4378ba/summary.json';
const mercuryDir = 'results/20261001_200720Z_e2dad72a_mercurydev36';
const jevRel = 'results/20261001_200150Z_881eb739_jevdev/summary.json';
const [api,cli,mercury,mercuryMetrics,jev,final] = await Promise.all([
  readJson(apiRel),readJson(cliRel),readJson(`${mercuryDir}/summary.json`),
  readJson(`${mercuryDir}/analysis_metrics.json`),readJson(jevRel),noFinal?null:readJson(finalAnalysisRel),
]);
const mercuryManifest=await readJson(`${mercuryDir}/manifest.json`);
const backendLogRel='outputs/home_pc_final_20261002_analytics7b4c/backend_log_metrics.json';
const backendLog=await readJson(backendLogRel);
eq(backendLog.alignedRequests,242,'backend log matched requests');
const backendByKey=new Map(backendLog.aggregates.map(r=>[`${r.run}/${r.model}`,r]));
const finalManifestRel=noFinal?null:(process.argv[3] ?? path.join(path.dirname(finalAnalysisRel),'../manifest.json'));
const finalManifest=noFinal?null:await readJson(finalManifestRel);
const finalObservationsRel=noFinal?null:path.join(path.dirname(finalAnalysisRel),'provider_observations.json');
const finalObservations=noFinal?null:await readJson(finalObservationsRel);
const mercuryRaw=await readJsonl(`${mercuryDir}/combined_mercury_raw.jsonl`);
eq(mercuryRaw.length,36,'Mercury raw N');
for(const [field,total] of [['prompt_tokens',19819],['completion_tokens',6463]]) {
 const values=mercuryRaw.map(r=>r.cloud?.usage?.[field]);eq(values.filter(isNum).length,34,`Mercury ${field} coverage`);eq(sum(values),total,`Mercury ${field}`);
}
const mercuryTemperatureWarningN=mercuryRaw.filter(r=>r.cloud?.raw?.warning?.includes('Temperature has been set to 1')).length;
eq(api.representative.length,15,'API representative models');
eq(api.representative.filter(r => r.n > 0).length,13,'API measured models');
for (const [key,expected] of Object.entries({requests:242,input_tokens_known:113332,output_tokens_known:17259,reasoning_tokens_known:9083,input_usage_coverage_n:242,output_usage_coverage_n:242})) eq(api.usage[key],expected,`API ${key}`);
eq(sum(cli.all_runs.map(r=>r.requests)),339,'CLI requests');
eq(sum(cli.all_runs.map(r=>r.input_tokens_known_sum)),135133,'CLI input');
eq(sum(cli.all_runs.map(r=>r.output_tokens_known_sum)),39087,'CLI output');
eq(mercury.combined.n_saved,36,'Mercury DEV requests');
eq(mercury.combined.input_tokens_known_sum,19819,'Mercury DEV input');
eq(mercury.combined.output_tokens_known_sum,6463,'Mercury DEV output');

// One record is one saved run × model aggregate. Repeated DEV observations are kept separate.
const rawVerification = [];
const runs = [];
const runNotes=[];
const apiKeyIndex = new Map();
function runRow(o) {
  runNotes.push(o.notes ?? '');
  return [o.family,o.model,o.run,o.split,o.state,o.n,shown(o.correct),null,shown(o.errors),
    shown(o.input),shown(o.output),shown(o.reasoning),o.inCov ?? 0,o.outCov ?? 0,o.reasonCov ?? 0,
    shown(o.mean),shown(o.p50),shown(o.p95),shown(o.firstDelta),shown(o.firstAnswer),
    shown(o.clientTps),shown(o.backendTtft),shown(o.backendTps),shown(o.vram),null,
    shown(o.ram),shown(o.file),shown(o.quant),shown(o.offload),o.layers ?? UNKNOWN,shown(o.context),
    shown(o.parallel),shown(o.temperature),shown(o.maxTokens),shown(o.seed),shown(o.load),
    o.reasonProfile ?? UNKNOWN,`${o.run}/${o.model}`,null,o.source];
}
for (const rec of api.all_runs) {
  const detail = api.details[`${rec.run}/${rec.model}`];
  const rawRel = `results/${rec.run}/${rec.model}_raw.jsonl`;
  const raw = rec.n ? await readJsonl(rawRel) : [];
  eq(raw.length,rec.n,`API raw count ${rec.run}/${rec.model}`);
  const inputs=raw.map(r=>r.local?.usage?.prompt_tokens), outputs=raw.map(r=>r.local?.usage?.completion_tokens);
  const reason=raw.map(r=>r.local?.usage?.completion_tokens_details?.reasoning_tokens);
  for (const [values,total,cov,label] of [[inputs,rec.input_tokens_known,rec.input_coverage,'input'],[outputs,rec.output_tokens_known,rec.output_coverage,'output'],[reason,rec.reasoning_tokens_known,rec.reasoning_coverage,'reasoning']]) {
    eq(values.filter(isNum).length,cov,`API ${label} coverage ${rec.model}/${rec.run}`);
    if(cov) eq(sum(values),total,`API ${label} tokens ${rec.model}/${rec.run}`);
  }
  const config=detail.actual_load_config ?? {}, requested=detail.requested_parameters ?? {};
  const timing=detail.summary ?? {};
  const backend=backendByKey.get(`${rec.run}/${rec.model}`);
  const backendValid=backend?.complete_alignment && backend.unambiguously_aligned_n===rec.n;
  if(backendValid) {
    eq(backend.rawSha256,sha(await fs.readFile(path.join(root,rawRel))),`backend raw provenance ${rec.model}/${rec.run}`);
  }
  const notes=[rec.early_stop,rec.phase_error,rec.resource_guard_stop?'Whole-system RAM guard stopped series':null,
    rec.split==='custom_dev'?'Paired bilingual DEV12, separate dataset':null,
    rec.reasoning_profile===null?'Default reasoning diagnostic':null].filter(Boolean).join('. ');
  apiKeyIndex.set(`${rec.run}/${rec.model}`,runs.length);
  runs.push(runRow({family:'LM Studio API DEV',model:rec.model,run:rec.run,split:rec.split,state:rec.state,n:rec.n,
    correct:rec.correct,errors:rec.errors,input:rec.input_tokens_known,output:rec.output_tokens_known,
    reasoning:rec.reasoning_tokens_known,inCov:rec.input_coverage,outCov:rec.output_coverage,reasonCov:rec.reasoning_coverage,
    mean:rec.latency_mean_s,p50:rec.p50_s,p95:rec.p95_s,firstDelta:rec.first_delta_p50_s,
    firstAnswer:timing.client_first_answer_delta_p50_s,clientTps:rec.client_tps_approx_p50,
    vram:rec.vram_mib_total_peak,ram:rec.ram_gib_system_peak,file:rec.file_gib,quant:rec.quantization,
    offload:rec.gpu_offload_requested,context:config.context_length,parallel:config.parallel,
    temperature:requested.temperature,maxTokens:requested.max_tokens,seed:requested.seed,load:rec.cold_load_s,
    backendTps:backendValid?backend.backend_decode_tps_median:null,
    reasonProfile:rec.reasoning_profile,notes:notes+(backendValid?` Backend decode aligned in saved own-instance log ${rec.n}/${rec.n}.`:''),source:rec.n?rawRel:`results/${rec.run}/manifest.json`}));
  rawVerification.push({family:'API',run:rec.run,model:rec.model,n:raw.length,inputKnown:sum(inputs),outputKnown:sum(outputs),reasoningKnown:sum(reason)});
}
const manifestCache=new Map();
async function manifestFor(run) {if(!manifestCache.has(run)) manifestCache.set(run,await readJson(`results/${run}/manifest.json`));return manifestCache.get(run);}
for (const rec of cli.all_runs) {
  const manifest=await manifestFor(rec.run), meta=manifest.models[rec.model], diagnostic=rec.diagnostic;
  const rawRel=`results/${rec.run}/${rec.model}_raw.jsonl`, raw=rec.requests?await readJsonl(rawRel):[];
  eq(raw.length,rec.requests,`CLI raw count ${rec.run}/${rec.model}`);
  const inputs=raw.map(r=>r.local?.usage?.prompt_tokens ?? r.local?.stats?.prompt_tokens);
  const outputs=raw.map(r=>r.local?.usage?.completion_tokens ?? r.local?.stats?.completion_tokens);
  eq(inputs.filter(isNum).length,rec.input_usage_coverage_n,`CLI input coverage ${rec.model}/${rec.run}`);
  eq(outputs.filter(isNum).length,rec.output_usage_coverage_n,`CLI output coverage ${rec.model}/${rec.run}`);
  if(rec.input_usage_coverage_n) eq(sum(inputs),rec.input_tokens_known_sum,`CLI input ${rec.model}/${rec.run}`);
  if(rec.output_usage_coverage_n) eq(sum(outputs),rec.output_tokens_known_sum,`CLI output ${rec.model}/${rec.run}`);
  runs.push(runRow({family:'Historical CLI DEV',model:rec.model,run:rec.run,split:rec.split,
    state:rec.phase_error?'INTERRUPTED':meta.early_stop?'EARLY_STOP':rec.requests?'SAVED':'NOT RUN',n:rec.requests,
    correct:diagnostic?.correct,errors:diagnostic?.errors,input:rec.input_tokens_known_sum,output:rec.output_tokens_known_sum,
    inCov:rec.input_usage_coverage_n,outCov:rec.output_usage_coverage_n,mean:diagnostic?.latency_mean_s,
    p50:diagnostic?.latency_p50_s,p95:diagnostic?.latency_p95_s,backendTtft:diagnostic?.ttft_median_s,backendTps:diagnostic?.decode_tps_median,
    vram:meta.vram_mib_peak_sampled_total,ram:meta.ram_gib_peak_sampled_system_used,file:meta.inventory?.sizeBytes/2**30,
    quant:meta.inventory?.quantization?.name,offload:rec.offload_requested,context:manifest.context,parallel:manifest.parallel,
    notes:rec.phase_error ?? 'Historical CLI controls UNKNOWN. Repeated DEV observations; excluded from API quality selection.',
    source:rec.requests?rawRel:`results/${rec.run}/manifest.json`}));
  rawVerification.push({family:'CLI',run:rec.run,model:rec.model,n:raw.length,inputKnown:sum(inputs),outputKnown:sum(outputs)});
}
const mercuryIndex=runs.length;
runs.push(runRow({family:'Mercury API DEV',model:mercuryManifest.model,run:mercury.run_id,split:'old_dev',state:'DEVELOPMENT_ONLY',
  n:36,correct:27,errors:4,input:19819,output:6463,inCov:34,outCov:34,mean:mercuryMetrics.latency_mean_s,
  p50:mercuryMetrics.latency_p50_s,p95:mercuryMetrics.latency_p95_s,offload:NA,layers:NA,vram:NA,ram:NA,file:NA,quant:NA,load:NA,
  temperature:mercuryManifest.temperature,maxTokens:mercuryManifest.max_tokens,reasonProfile:mercuryManifest.reasoning_effort,
  notes:`Combined DEV36 includes earlier pilot once. Two calls have unknown cost/usage. Remote resources N/A. Server sets requested temperature 0 to 1 in ${mercuryTemperatureWarningN} saved responses.`,source:`${mercuryDir}/combined_mercury_raw.jsonl`}));
eq(new Set(runs.map(r=>r[37])).size,runs.length,'unique run/model source keys');

if(sourceCheckOnly) {
  await fs.writeFile(path.join(outputDir,'source_validation.json'),JSON.stringify({apiUsage:api.usage,cliUsage:cli.session_usage,
    mercuryUsage:mercury.combined,mercuryTemperatureWarningN,runAggregates:runs.length,rawVerification},null,2));
  console.log(JSON.stringify({stage:'raw_sources_verified',runAggregates:runs.length,apiUsage:api.usage,cliUsage:cli.session_usage,mercuryTemperatureWarningN}));
  process.exit(0);
}

const workbook=Workbook.create();
const compare=workbook.worksheets.add('Модели DEV');
const policy=workbook.worksheets.add('FINAL150');
const allRuns=workbook.worksheets.add('Все серии');
const FONT='Arial',HEADER='#243F5B',BODY='#172B3A',MUTED='#526679',LIGHT='#F2F5F8';
const first=9,header=8,lastRun=first+runs.length-1;
const col=n=>{let s='';while(n){s=String.fromCharCode(65+(n-1)%26)+s;n=Math.floor((n-1)/26);}return s;};
function base(sheet,last,lastCol,title,subtitle) {
  sheet.showGridLines=false;
  sheet.getRange(`A1:${lastCol}${last}`).format={font:{name:FONT,size:11,color:BODY},verticalAlignment:'center',rowHeight:26};
  sheet.getRange(`A1:${lastCol}1`).format.rowHeight=10;
  sheet.getRange('A2').values=[[title]];
  sheet.getRange('A2').format.font={name:FONT,size:15,bold:true,color:HEADER};
  sheet.getRange(`A2:${lastCol}2`).format.rowHeight=30;
  sheet.getRange(`A2:${lastCol}2`).format.borders={bottom:{style:'thin',color:'#A8B6C3'}};
  sheet.getRange('A3').values=[[subtitle]];
  sheet.getRange('A3').format.font={name:FONT,size:11,italic:true,color:MUTED};
  sheet.getRange(`A${header}:${lastCol}${header}`).format={fill:HEADER,font:{name:FONT,size:11,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',verticalAlignment:'center',wrapText:true,rowHeight:70,borders:{insideVertical:{style:'thin',color:'#FFFFFF'}}};
  sheet.getRange(`A${first}:${lastCol}${last}`).format.rowHeight=46;
  sheet.getRange(`A${first}:${lastCol}${last}`).format.horizontalAlignment='right';
  sheet.getRange(`A${first}:${lastCol}${last}`).format.wrapText=false;
  sheet.freezePanes.freezeRows(header);
  sheet.freezePanes.freezeColumns(2);
}
function widths(sheet,values,last) {values.forEach((w,i)=>sheet.getRange(`${col(i+1)}1:${col(i+1)}${last}`).format.columnWidth=w);}
function fmt(sheet,columns,last,format) {columns.forEach(c=>sheet.getRange(`${c}${first}:${c}${last}`).setNumberFormat(format));}
function table(sheet,name,last,lastCol) {const t=sheet.tables.add(`A${header}:${lastCol}${last}`,true,name);t.showFilterButton=true;return t;}
function flags(sheet,range) {
  sheet.getRange(range).conditionalFormats.add('containsText',{text:'NOT_RUN',format:{fill:'#FFF1D6',font:{color:'#825A12'}}});
  sheet.getRange(range).conditionalFormats.add('containsText',{text:'STOP',format:{fill:'#FFF1D6',font:{color:'#825A12'}}});
}
base(allRuns,lastRun,'AN','Все сохранённые серии и ресурсы','API и CLI — отдельные серии измерений. Повторные DEV-запросы не суммируются в качество.');
const runHeaders=['Серия','Модель','Run ID','Выборка','Статус','N','Верно','Качество','Ошибки',
  'Input известно','Output известно','Reasoning известно','Input coverage N','Output coverage N','Reasoning coverage N',
  'Среднее, с','p50, с','p95, с','Первый delta p50, с','Первый answer p50, с','Client approx tok/s',
  'Backend TTFT p50, с','Backend decode tok/s','VRAM весь GPU MiB','VRAM весь GPU GiB','RAM весь ПК GiB',
  'Каталог файлов GiB','Квантование','Offload запрошен','GPU layers фактически','Контекст','Parallel','Temperature requested','Max tokens','Seed',
  'Cold load, с','Reasoning профиль','Run model ID','','Источник'];
allRuns.getRange(`A${header}:AN${header}`).values=[runHeaders];
allRuns.getRange(`A${first}:AN${lastRun}`).values=runs;
allRuns.getRange(`H${first}`).formulas=[[`=IF(F${first}=0,"NOT RUN",G${first}/F${first})`]];
allRuns.getRange(`H${first}:H${lastRun}`).fillDown();
allRuns.getRange(`Y${first}`).formulas=[[`=IF(ISNUMBER(X${first}),X${first}/1024,X${first})`]];
allRuns.getRange(`Y${first}:Y${lastRun}`).fillDown();
allRuns.getRange(`A${first}:E${lastRun}`).format.horizontalAlignment='left';
allRuns.getRange(`A${first}:E${lastRun}`).format.wrapText=true;
allRuns.getRange(`AB${first}:AD${lastRun}`).format.horizontalAlignment='left';
allRuns.getRange(`AK${first}:AN${lastRun}`).format.horizontalAlignment='left';
widths(allRuns,[25,48,40,15,27,7,13,12,13,15,15,15,13,13,13,11,11,11,15,15,15,15,15,15,15,15,15,16,15,19,11,11,13,13,9,13,18,87,3,85],lastRun);
fmt(allRuns,['F','G','I','J','K','L','M','N','O','X','AE','AF','AH','AI'],lastRun,'#,##0');
fmt(allRuns,['H'],lastRun,'0.0%');
fmt(allRuns,['P','Q','R','S','T','V','AJ'],lastRun,'0.000');
fmt(allRuns,['U','W','Y','Z','AA'],lastRun,'0.00');
table(allRuns,'SavedSeries',lastRun,'AL');
// Sources are ordinary cells outside the filterable table, after one blank spacer column.
allRuns.getRange(`AM${header}:AN${lastRun}`).format.fill='#FFFFFF';
allRuns.getRange('AN8').format.font={name:FONT,size:11,bold:true,color:BODY};
allRuns.getRange('AP8').values=[['Примечание']];
allRuns.getRange(`AP${first}:AP${lastRun}`).values=runNotes.map(n=>[n]);
allRuns.getRange(`AP8:AP${lastRun}`).format={font:{name:FONT,size:11,color:MUTED},columnWidth:100,verticalAlignment:'center'};
flags(allRuns,`E${first}:E${lastRun}`);
allRuns.getRange('A4').values=[['LM Studio API запросы']];
allRuns.getRange('B4').formulas=[[`=SUMIFS(F${first}:F${lastRun},A${first}:A${lastRun},"LM Studio API DEV")`]];
allRuns.getRange('D4').values=[['Input tokens API']];
allRuns.getRange('E4').formulas=[[`=SUMIFS(J${first}:J${lastRun},A${first}:A${lastRun},"LM Studio API DEV")`]];
allRuns.getRange('G4').values=[['Output API']];
allRuns.getRange('H4').formulas=[[`=SUMIFS(K${first}:K${lastRun},A${first}:A${lastRun},"LM Studio API DEV")`]];
allRuns.getRange('J4').values=[['Reasoning API']];
allRuns.getRange('K4').formulas=[[`=SUMIFS(L${first}:L${lastRun},A${first}:A${lastRun},"LM Studio API DEV")`]];
allRuns.getRange('A5').values=[['Исторические CLI запросы']];
allRuns.getRange('B5').formulas=[[`=SUMIFS(F${first}:F${lastRun},A${first}:A${lastRun},"Historical CLI DEV")`]];
allRuns.getRange('D5').values=[['Input tokens CLI']];
allRuns.getRange('E5').formulas=[[`=SUMIFS(J${first}:J${lastRun},A${first}:A${lastRun},"Historical CLI DEV")`]];
allRuns.getRange('G5').values=[['Output CLI']];
allRuns.getRange('H5').formulas=[[`=SUMIFS(K${first}:K${lastRun},A${first}:A${lastRun},"Historical CLI DEV")`]];
allRuns.getRange('A6').values=[['API usage 242/242. CLI usage 286/339. VRAM/RAM — sampled peak всего GPU/ПК, не аллокация модели.']];

const comparisonHeaders=['Модель','Статус','N','Верно','Качество','Ошибки','Input известно','Output известно','Reasoning известно',
  'Input coverage N','Output coverage N','p50, с','p95, с','Первый delta p50, с','Первый answer p50, с','Client approx tok/s',
  'Backend TTFT, с','Backend decode tok/s','VRAM весь GPU GiB','RAM весь ПК GiB','Каталог файлов GiB','Квантование',
  'Offload запрошен','GPU layers фактически','Контекст','Parallel','Temperature requested','Max tokens','Seed','Cold load, с','Reasoning профиль'];
const modelLast=first+api.representative.length;
base(compare,modelLast,'AE','LM Studio и Mercury: DEV измерения','Качество сравнивается только на одинаковых ID. Полный DEV36: Qwen 27B, Gemma 26B и Mercury.');
compare.tabColor=HEADER;
compare.getRange('A8:AE8').values=[comparisonHeaders];
const map=['B','E','F','G','H','I','J','K','L','M','N','Q','R','S','T','U','V','W','Y','Z','AA','AB','AC','AD','AE','AF','AG','AH','AI','AJ','AK'];
for(const [i,rec] of [...api.representative,{model:mercuryManifest.model,run:mercury.run_id}].entries()) {
  const key=`${rec.run}/${rec.model}`;
  compare.getRange(`A${first+i}:AE${first+i}`).formulas=[map.map(c=>`=INDEX('Все серии'!$${c}$${first}:$${c}$${lastRun},MATCH("${key}",'Все серии'!$AL$${first}:$AL$${lastRun},0))`)];
}
widths(compare,[49,28,7,13,12,13,15,15,15,13,13,12,12,15,15,15,15,15,15,15,15,16,15,20,11,11,13,13,9,13,18],modelLast);
compare.getRange(`A${first}:B${modelLast}`).format.horizontalAlignment='left';
compare.getRange(`A${first}:B${modelLast}`).format.wrapText=true;
compare.getRange(`V${first}:X${modelLast}`).format.horizontalAlignment='left';
compare.getRange(`AE${first}:AE${modelLast}`).format.horizontalAlignment='left';
fmt(compare,['C','D','F','G','H','I','J','K','Y','Z','AB','AC'],modelLast,'#,##0');
fmt(compare,['E'],modelLast,'0.0%');
fmt(compare,['L','M','N','O','Q','AD'],modelLast,'0.000');
fmt(compare,['P','R','S','T','U'],modelLast,'0.00');
table(compare,'ModelComparison',modelLast,'AE');
flags(compare,`B${first}:B${modelLast}`);
compare.getRange('A4').values=[['API: 15 моделей, 13 с ответами. Две модели NOT RUN после предыдущей остановки по памяти.']];
compare.getRange('A5').values=[['LM Studio API: native JSON schema, temperature 0, top_p 1, seed 42, max_tokens 512. none/low — экспериментальный reasoning control.']];
compare.getRange('A6').values=[['Client TPS включает counted reasoning. Backend decode — отдельный log с точным matching; backend TTFT UNKNOWN. Первый delta может быть reasoning.']];
compare.getRange('A7').values=[[`Mercury: requested temperature 0; сервер изменил на 1 во всех ${mercuryTemperatureWarningN} успешных DEV ответах.`]];
compare.getRange('A7').format.font={name:FONT,size:11,color:MUTED};

// Typed decision services use separate metrics. They do not enter generative QA quality.
const typedHeader=modelLast+4,typedFirst=typedHeader+1,typedLast=typedFirst+1;
compare.getRange(`A${typedHeader-2}`).values=[['Typed decisions: отдельные 12 контролируемых DEV сценариев']];
compare.getRange(`A${typedHeader-2}`).format.font={name:FONT,size:13,bold:true,color:HEADER};
const typedHeaders=['Система','Режим','N','Route верно','Route quality','Missing data\nверно','Missing data\nquality','p50, с','p95, с','Input известно','Output известно','Cost estimate USD','Process RSS GiB','TTFT','Output tok/s'];
compare.getRange(`A${typedHeader}:O${typedHeader}`).values=[typedHeaders];
compare.getRange(`A${typedHeader}:O${typedHeader}`).format={fill:HEADER,font:{name:FONT,size:11,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'center',verticalAlignment:'center',rowHeight:64};
compare.getRange(`A${typedFirst}:O${typedLast}`).values=[
 ['Jev 1.13.0','Remote typed API',12,jev.route_correct,null,jev.missing_data_correct,null,jev.latency_p50_ms/1000,jev.latency_p95_ms/1000,jev.input_tokens,jev.output_tokens,jev.estimated_cost_usd,NA,UNKNOWN,UNKNOWN],
 ['Laya multilingual','CPU local typed model',12,jev.baseline.route_correct,null,jev.baseline.missing_data_correct,null,jev.baseline.latency_p50_ms/1000,jev.baseline.latency_p95_ms/1000,NA,NA,NA,jev.baseline.peak_process_rss_bytes/2**30,NA,NA],
];
compare.getRange(`E${typedFirst}`).formulas=[[`=D${typedFirst}/C${typedFirst}`]];compare.getRange(`E${typedFirst}:E${typedLast}`).fillDown();
compare.getRange(`G${typedFirst}`).formulas=[[`=F${typedFirst}/C${typedFirst}`]];compare.getRange(`G${typedFirst}:G${typedLast}`).fillDown();
compare.getRange(`E${typedFirst}:G${typedLast}`).setNumberFormat('0.0%');
compare.getRange(`F${typedFirst}:F${typedLast}`).setNumberFormat('#,##0');
compare.getRange(`H${typedFirst}:I${typedLast}`).setNumberFormat('0.000');
compare.getRange(`L${typedFirst}:L${typedLast}`).setNumberFormat('"$"0.000000');
compare.getRange(`M${typedFirst}:M${typedLast}`).setNumberFormat('0.00');
compare.getRange(`A${typedFirst}:O${typedLast}`).format={font:{name:FONT,size:11,color:BODY},verticalAlignment:'center',rowHeight:34};
compare.getRange(`C${typedFirst}:O${typedLast}`).format.horizontalAlignment='right';
for(const c of ['C','D','F','J','K']) compare.getRange(`${c}${typedFirst}:${c}${typedLast}`).setNumberFormat('#,##0');
compare.getRange(`A${typedLast+2}`).values=[['Jev: remote VRAM/RAM/offload N/A. Laya RSS — только процесс. Цена Jev — оценка по тарифу, не invoice.']];
compare.getRange(`A${typedLast+3}`).values=[['OpenRouter free: SKIP после HTTP 401, успешных ответов 0.']];
compare.getRange(`A${typedLast+2}:O${typedLast+3}`).format={font:{name:FONT,size:11,color:MUTED},rowHeight:27};

// Final policy table is populated below from the analyzer's actual immutable statistics schema.
const policyNames=['local','cloud','tool_cloud','hybrid','offline'];
if(devPreviewOnly) {
  workbook.recalculate();
  for(const [sheetName,range,name] of [['Модели DEV','A1:K24','models_quality.png'],['Модели DEV','L7:U24','models_timing_memory.png'],
    ['Модели DEV',`A${typedHeader-2}:O${typedLast+3}`,'typed_decisions.png'],['Все серии','A1:N20','runs_first.png']]) {
    const preview=await workbook.render({sheetName,range,scale:1,format:'png'});
    await fs.writeFile(path.join(outputDir,name),new Uint8Array(await preview.arrayBuffer()));
  }
  const errors=await workbook.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},maxChars:3000});
  console.log(JSON.stringify({stage:'dev_preview_ready',errors:errors.ndjson,exportedXlsx:false}));
  process.exit(0);
}
eq(policyNames.every(name=>final.summary?.[name]),true,'all five final policy summaries present');
const finalRawRel=path.join(path.dirname(finalManifestRel),'raw_decisions.jsonl');
const finalRawText=await fs.readFile(path.resolve(root,finalRawRel),'utf8');
eq(sha(finalRawText),finalObservations.raw_sha256,'FINAL observations raw SHA');
const finalRaw=finalRawText.trim().split(/\r?\n/).filter(Boolean).map(JSON.parse);
eq(finalRaw.length,750,'FINAL saved decisions');
eq(new Set(finalRaw.map(r=>`${r.sample.id}/${r.method}`)).size,750,'FINAL unique sample-policy pairs');
eq(finalRaw.every(r=>r.result.status==='MEASURED'),true,'FINAL all measured');
const finalRawChecks=[];
for(const name of policyNames) {
 const rows=finalRaw.filter(r=>r.method===name),s=final.summary[name];
 eq(rows.length,150,`${name} raw measured N`);
 eq(rows.filter(r=>r.score.correct).length,s.correct,`${name} raw correct`);
 eq(rows.filter(r=>r.score.critical_error).length,s.critical_errors,`${name} raw critical errors`);
 for(const provider of ['local','cloud']) {
  const traces=rows.flatMap(r=>r.result.trace).filter(t=>t.provider===provider),p=s.providers[provider];
  eq(traces.length,p.calls,`${name}/${provider} raw calls`);
  for(const [field,totalField,coverageField] of [['prompt_tokens','input_tokens_known_sum','input_usage_coverage_n'],['completion_tokens','output_tokens_known_sum','output_usage_coverage_n']]) {
   const values=traces.map(t=>t.usage?.[field]);
   eq(values.filter(isNum).length,p[coverageField],`${name}/${provider} ${field} coverage`);
   if(values.some(isNum)) eq(sum(values),p[totalField],`${name}/${provider} ${field} sum`);
  }
 }
 finalRawChecks.push({method:name,uniqueMeasured:rows.length,correct:s.correct,critical:s.critical_errors});
}
await fs.writeFile(path.join(outputDir,'source_stage_validation.json'),JSON.stringify({apiUsage:api.usage,cliUsage:cli.session_usage,rawVerification,finalAnalysisRel},null,2));
console.log(JSON.stringify({stage:'sources_ready',runRows:runs.length,finalAnalysisRel,finalSummaryKeys:Object.keys(final.summary)}));

const policyLabels={local:'Local LLM',cloud:'Cloud Mercury',tool_cloud:'Tool-first + cloud',hybrid:'Hybrid',offline:'Offline'};
const policyLast=first+policyNames.length-1;
base(policy,policyLast,'X','FINAL150: пять замороженных политик','Новая выборка: 150 cases × 5 политик. 2 сегмента после WinError5; без replay. Human/manual validation PENDING.');
policy.getRange('A14:X65').format={font:{name:FONT,size:11,color:BODY},verticalAlignment:'center',rowHeight:27};
policy.tabColor='#476D8E';
policy.getRange('A8:X8').values=[['Политика','Статус','Target N','Measured N','Coverage','Верно','Качество','CI95 low','CI95 high',
 'Критические ошибки','Critical rate','Error decisions','Call errors','QA N','QA EM','QA F1','Cloud calls','Local calls','Tool calls',
 'Latency coverage N','Mean, с','p50, с','p95, с','Missing / NOT RUN']];
const policyRows=policyNames.map(name=>{
 const s=final.summary[name],t=s.latency_measured_end_to_end,ci=s.quality_cluster?.ci95 ?? [null,null];
 return [policyLabels[name],s.measured_n===s.target_n?'MEASURED COMPLETE':'PARTIAL',s.target_n,s.measured_n,null,s.correct,null,shown(ci[0]),shown(ci[1]),
 s.critical_errors,null,s.error_decisions,s.call_errors,s.qa_measured_n,shown(s.qa_em),shown(s.qa_f1_mean),s.cloud_calls,s.local_calls,s.tool_calls,
 t.known_n,shown(t.mean_s),shown(t.p50_s),shown(t.p95_s),`${s.missing_n} / ${s.recorded_not_run_n}`];
});
policy.getRange(`A${first}:X${policyLast}`).values=policyRows;
policy.getRange(`E${first}`).formulas=[[`=D${first}/C${first}`]];policy.getRange(`E${first}:E${policyLast}`).fillDown();
policy.getRange(`G${first}`).formulas=[[`=IF(D${first}=0,"NOT RUN",F${first}/D${first})`]];policy.getRange(`G${first}:G${policyLast}`).fillDown();
policy.getRange(`K${first}`).formulas=[[`=IF(D${first}=0,"NOT RUN",J${first}/D${first})`]];policy.getRange(`K${first}:K${policyLast}`).fillDown();
widths(policy,[29,25,11,12,12,13,12,12,12,16,13,13,12,14,12,12,12,12,12,15,12,12,12,18],65);
policy.getRange(`A${first}:B${policyLast}`).format.horizontalAlignment='left';
fmt(policy,['C','D','F','J','L','M','N','Q','R','S','T'],policyLast,'#,##0');
fmt(policy,['E','G','H','I','K','O','P'],policyLast,'0.0%');
fmt(policy,['U','V','W'],policyLast,'0.000');
table(policy,'FrozenPolicySummary',policyLast,'X');
policy.getRange('A4').values=[['Качество = correct / measured. Coverage показывается отдельно. Ошибки включены в знаменатель measured.']];
policy.getRange('A5').values=[['Reasoning tokens входят в completion tokens и не прибавляются повторно. CI95 — cluster bootstrap по source group.']];
policy.getRange('A6').values=[['Latency — end-to-end измеренных решений. Стоимость — известная оценка провайдера; электричество и invoice отсутствуют.']];
policy.getRange('A7').values=[[`Mercury: requested temperature ${finalObservations.requested_temperature}; provider сообщил effective ${finalObservations.provider_reported_effective_temperature} в ${finalObservations.warnings_observed_cloud_calls}/${finalObservations.cloud_calls} вызовах; 12 timeout UNKNOWN.`]];
policy.getRange('A7').format.font={name:FONT,size:11,color:MUTED};

const tokenHeader=18,tokenFirst=19,tokenLast=28;
policy.getRange('A16').values=[['Токены, streaming и стоимость по провайдеру']];
policy.getRange('A16').format.font={name:FONT,size:13,bold:true,color:HEADER};
const tokenHeaders=['Политика','Provider','Calls','Input известно','Output известно','Reasoning известно','Input coverage N','Output coverage N',
 'Reasoning coverage N','Usage complete','Первый delta p50, с','Первый answer p50, с','Client approx tok/s','Cost known USD','Cost coverage N',
 'Unknown cost calls','Cost / 1000 complete USD','Cost / 1000 lower bound USD','Billing source complete'];
policy.getRange(`A${tokenHeader}:S${tokenHeader}`).values=[tokenHeaders];
policy.getRange(`A${tokenHeader}:S${tokenHeader}`).format={fill:HEADER,font:{name:FONT,size:11,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'center',verticalAlignment:'center',rowHeight:78};
const tokenRows=[];
for(const name of policyNames) for(const provider of ['local','cloud']) {
 const p=final.summary[name].providers[provider],s=final.summary[name];
 tokenRows.push([policyLabels[name],provider,p.calls,shown(p.input_tokens_known_sum),shown(p.output_tokens_known_sum),shown(p.reasoning_tokens_reported_known_sum),
 p.input_usage_coverage_n,p.output_usage_coverage_n,p.reasoning_usage_coverage_n,p.usage_complete?'Да':'Нет',
 shown(p.client_ttft_median_s),shown(p.client_first_answer_delta_median_s),shown(p.approx_tps_median),shown(p.known_cost_estimate_usd),
 p.known_cost_coverage_n,p.unknown_cost_calls,provider==='cloud'?null:NA,provider==='cloud'?null:NA,
 provider==='cloud'?(s.cloud_cost_per_1000_measured_usd!==null?'Да':'Нет'):NA]);
}
policy.getRange(`A${tokenFirst}:S${tokenLast}`).values=tokenRows;
policy.getRange(`A${tokenFirst}:S${tokenLast}`).format={font:{name:FONT,size:11,color:BODY},rowHeight:34,verticalAlignment:'center',horizontalAlignment:'right'};
policy.getRange(`A${tokenFirst}:B${tokenLast}`).format.horizontalAlignment='left';
for(const [i,name] of policyNames.entries()) {
 const row=tokenFirst+i*2+1,summaryRow=first+i;
 policy.getRange(`Q${row}`).formulas=[[`=IF(AND(D${summaryRow}=C${summaryRow},P${row}=0,J${row}="Да",S${row}="Да"),N${row}/C${summaryRow}*1000,"UNKNOWN")`]];
 policy.getRange(`R${row}`).formulas=[[`=IF(AND(D${summaryRow}=C${summaryRow},P${row}=0,J${row}="Да",S${row}="Да"),"N/A",IF(ISNUMBER(N${row}),N${row}/C${summaryRow}*1000,"UNKNOWN"))`]];
}
policy.tables.add(`A${tokenHeader}:S${tokenLast}`,true,'FinalProviderUsage').showFilterButton=true;
policy.getRange(`C${tokenFirst}:I${tokenLast}`).setNumberFormat('#,##0');
policy.getRange(`K${tokenFirst}:L${tokenLast}`).setNumberFormat('0.000');
policy.getRange(`M${tokenFirst}:M${tokenLast}`).setNumberFormat('0.00');
policy.getRange(`N${tokenFirst}:N${tokenLast}`).setNumberFormat('"$"0.00000000');
policy.getRange(`O${tokenFirst}:P${tokenLast}`).setNumberFormat('#,##0');
policy.getRange(`Q${tokenFirst}:R${tokenLast}`).setNumberFormat('"$"0.0000');
policy.getRange(`Z${tokenHeader}`).values=[['Источник']];
policy.getRange(`Z${tokenFirst}`).values=[[finalAnalysisRel]];
policy.getRange(`Z${tokenFirst}`).format.columnWidth=95;
policy.getRange(`Z${tokenFirst}`).format.horizontalAlignment='left';
policy.getRange(`Z${tokenHeader}:Z${tokenFirst}`).format.font={name:FONT,size:11,color:MUTED};
policy.getRange('A30').values=[['N/A означает неприменимый показатель. UNKNOWN означает отсутствующее измерение. Нулевые вызовы имеют настоящую стоимость 0.']];
policy.getRange('A31').values=[[`Всего FINAL: 310 local + 270 cloud вызовов; известная cloud cost $${sum(policyNames.map(n=>final.summary[n].providers.cloud.known_cost_estimate_usd)).toFixed(8)} + 12 unknown-cost timeout calls.`]];

const resources=final.resource_peak_total_scope ?? {},load=final.model_load_metadata ?? {};
policy.getRange('A32').values=[['Память FINAL150: общий sampled peak прогона']];
policy.getRange('A32').format.font={name:FONT,size:13,bold:true,color:HEADER};
policy.getRange('A34:H34').values=[['Local model','VRAM весь GPU MiB','VRAM весь GPU GiB','RAM весь ПК GiB','Offload запрошен','GPU layers\nфакт.','Load сегмента 2, с','Контекст']];
policy.getRange('A34:H34').format={fill:HEADER,font:{name:FONT,size:11,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'center',rowHeight:66};
policy.getRange('A35:H35').values=[[shown(finalManifest.local?.model),
 shown(resources.vram_mib_peak_sampled_total),null,shown(resources.ram_gib_peak_sampled_system_used),
 shown(finalManifest.local?.gpu),shown(load.actual_offloaded_layers),
 shown(load.cold_load_wall_s ?? load.cold_load_s),shown(load.actual_load_config?.context_length)]];
policy.getRange('C35').formulas=[['=IF(ISNUMBER(B35),B35/1024,"UNKNOWN")']];
policy.getRange('A35:H35').format={font:{name:FONT,size:11,color:BODY},rowHeight:34,horizontalAlignment:'right'};
policy.getRange('A35').format.horizontalAlignment='left';
policy.getRange('B35').setNumberFormat('#,##0');policy.getRange('C35:D35').setNumberFormat('0.00');policy.getRange('G35').setNumberFormat('0.000');
policy.getRange('A37').values=[['Память относится ко всему FINAL запуску. Samples 2862; original poll error log UNKNOWN. Remote cloud VRAM/RAM/offload N/A.']];

policy.getRange('A39').values=[['Основной контраст: hybrid минус tool_cloud']];
policy.getRange('A39').format.font={name:FONT,size:13,bold:true,color:HEADER};
policy.getRange('A41:E41').values=[['Критерий','Значение','Порог','Условие','Статус']];
policy.getRange('A41:E41').format={fill:HEADER,font:{name:FONT,size:11,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',rowHeight:32};
const crit=Object.entries(final.hypothesis?.criteria ?? {});
const criterionNames={quality_noninferiority:'Quality CI low',additional_cloud_call_reduction:'Cloud call reduction',critical_error_difference:'Critical difference CI high',hybrid_p95_latency:'Hybrid p95, с'};
if(crit.length) policy.getRange(`A42:E${41+crit.length}`).values=crit.map(([key,r])=>[criterionNames[key] ?? key,shown(r.value),shown(r.threshold),r.operator,r.status]);
policy.getRange(`A42:E${41+crit.length}`).format={font:{name:FONT,size:11,color:BODY},rowHeight:30};
policy.getRange(`D42:E${41+crit.length}`).format.horizontalAlignment='center';
policy.getRange(`B42:C${41+crit.length}`).setNumberFormat('0.000');
policy.getRange('B42:C44').setNumberFormat('0.0%');
const primaryPair=final.paired?.hybrid_minus_tool_cloud?.quality_a_minus_b;
policy.getRange('A46').values=[[`Разность качества hybrid − tool_cloud: ${(primaryPair.estimate*100).toFixed(1)} п.п.; CI95 [${(primaryPair.ci95[0]*100).toFixed(2)}; ${(primaryPair.ci95[1]*100).toFixed(2)}] п.п.`]];
policy.getRange('A47').values=[[`Статус гипотезы: ${final.hypothesis?.status ?? UNKNOWN}. Поддержка на frozen controlled sample: ${shown(final.hypothesis?.supported_on_frozen_controlled_sample)}.`]];
policy.getRange('A48').values=[['Отсутствие noninferiority не доказывает inferiority. Human manual audit и переносимость на агрономическую практику не установлены.']];
const segmentMetadata=finalManifest.segment_metadata ?? finalManifest.execution_segments ?? [];
if(Array.isArray(segmentMetadata) && segmentMetadata.length) {
  const coldLoads=segmentMetadata.map(s=>s.local_load_metadata?.cold_load_wall_s ?? s.cold_load_wall_s ?? null);
  policy.getRange('A50').values=[['Сегменты исполнения и холодные загрузки']];
  policy.getRange('A50').format.font={name:FONT,size:13,bold:true,color:HEADER};
  policy.getRange('A52:D52').values=[['Сегмент','Cold load, с','Решения сохранены','Примечание']];
  policy.getRange('D52:H52').merge();
  policy.getRange('A52:H52').format={fill:HEADER,font:{name:FONT,size:11,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:46};
  policy.getRange(`A53:D${52+segmentMetadata.length}`).values=segmentMetadata.map((s,i)=>[shown((s.run_id ?? s.run ?? `Segment ${i+1}`).replace(/^results[\\/]/,'')),shown(coldLoads[i]),
    shown(s.raw_rows ?? s.decision_rows ?? s.n_decisions ?? s.rows),s.manifest_state==='running'?'Interrupted by WinError5; saved manifest state is stale running':s.note ?? s.manifest_state ?? s.state ?? '']);
  policy.getRange(`D53:H${52+segmentMetadata.length}`).merge(true);
  policy.getRange(`A53:H${52+segmentMetadata.length}`).format={font:{name:FONT,size:11,color:BODY},rowHeight:54,wrapText:true,verticalAlignment:'center'};
  policy.getRange(`B53:C${52+segmentMetadata.length}`).format.horizontalAlignment='right';
  policy.getRange(`C53:C${52+segmentMetadata.length}`).format.horizontalAlignment='center';
  policy.getRange(`B53:B${52+segmentMetadata.length}`).setNumberFormat('0.000');
}
const segmentNoteRow=54+(Array.isArray(segmentMetadata)?segmentMetadata.length:0);
if(finalManifest.procedural_deviation || finalManifest.continuation_deviation) {
  policy.getRange(`A${segmentNoteRow}`).values=[[finalManifest.procedural_deviation ?? finalManifest.continuation_deviation]];
  policy.getRange(`A${segmentNoteRow+1}`).values=[['Метрики по уникальным решениям вычислены; строгий непрерывный preregistered запуск не заявлен. Gap и повторная загрузка не входят в latency решения.']];
}
policy.getRange(`A${segmentNoteRow+2}`).values=[[`Interruption gap sampled: ${finalManifest.interruption_gap_sampled_s.toFixed(3)} с; cold loads: ${finalManifest.cold_load_count}; 750 unique sample × policy pairs, no replay.`]];
policy.getRange(`A${segmentNoteRow+3}`).values=[['Local FINAL: Gemma 26B IQ4_NL_XL; context 4096; parallel 1; offload requested 0.70; temp 0; top_p 1; seed 42; max_tokens 512; reasoning none; strict JSON schema.']];
policy.getRange(`A${segmentNoteRow+4}`).values=[['Backend decode TPS / native TTFT FINAL: UNKNOWN. Mercury effective temperature — provider-reported; independently verified sampling UNKNOWN.']];
policy.getRange(`A${segmentNoteRow+5}`).values=[['QA/scoring controlled benchmark; compound reasoning Hybrid 8/20 vs Tool-first + cloud 18/20. Manual30 validation PENDING.']];
policy.getRange(`A${segmentNoteRow}:I${segmentNoteRow+5}`).merge(true);
policy.getRange(`A${segmentNoteRow}:I${segmentNoteRow+5}`).format={font:{name:FONT,size:11,color:BODY},rowHeight:45,wrapText:true,horizontalAlignment:'left',verticalAlignment:'center'};

// Metric definitions sit with source aggregates rather than in output annotations.
const definitionFirst=lastRun+3;
const definitions=[['Определения',''],['Единица наблюдения','Run ID × model. В summary не объединяются повторные ответы разных DEV запусков.'],
 ['Выбор API серии','Largest completed off-or-low old_dev; latest run breaks ties; highest score is never the selector.'],
 ['Память','VRAM sampled whole GPU / RAM sampled whole PC. Other apps are included. Model allocation and exact peak UNKNOWN.'],
 ['Offload','Requested max/fraction is retained. Actually offloaded GPU layers UNKNOWN.'],
 ['Каталог файлов','Catalog size includes weights and associated mmproj/config. Gemma total 16847892149 bytes; main weight 14556687680 bytes.'],
 ['Reasoning','Reported reasoning is a subset of completion tokens. Missing reasoning counts remain UNKNOWN.'],
 ['Client TPS','Counted completion tokens / interval from first to last nonempty delta; first-token interval omitted; backend decode differs.'],
 ['Backend TPS log','242/242 requests uniquely match own home-api instance, order/count, completion tokens and timestamp. Cache n_tokens diagnostic differs in 32 records; source usage is unchanged.'],
 ['Backend log source',backendLogRel],
 ['TTFT','API first delta can be reasoning. First answer delta is separately recorded. CLI backend TTFT is a different measurement.'],
 ['API source',apiRel],['CLI source',cliRel],['Mercury source',`${mercuryDir}/summary.json`],['Jev/Laya source',jevRel],['FINAL source',finalAnalysisRel],['FINAL warnings source',finalObservationsRel]];
allRuns.getRange(`A${definitionFirst}:B${definitionFirst+definitions.length-1}`).values=definitions;
allRuns.getRange(`A${definitionFirst}:B${definitionFirst+definitions.length-1}`).format={font:{name:FONT,size:11,color:MUTED},rowHeight:27};
allRuns.getRange(`A${definitionFirst}:A${definitionFirst+definitions.length-1}`).format.font={name:FONT,size:11,bold:true,color:BODY};
allRuns.getRange(`B${definitionFirst}:B${definitionFirst+definitions.length-1}`).format.wrapText=false;

workbook.recalculate();
compare.getRange(`AC8:AC${modelLast}`).format.columnWidth=13;
compare.getRange(`AE${first}:AE${modelLast}`).format.horizontalAlignment='center';
allRuns.getRange(`AB${first}:AB${lastRun}`).format.horizontalAlignment='center';
const computedChecks={apiRequests:allRuns.getRange('B4').values[0][0],apiInput:allRuns.getRange('E4').values[0][0],
 apiOutput:allRuns.getRange('H4').values[0][0],apiReasoning:allRuns.getRange('K4').values[0][0],
 cliRequests:allRuns.getRange('B5').values[0][0],cliInput:allRuns.getRange('E5').values[0][0],cliOutput:allRuns.getRange('H5').values[0][0]};
for(const [key,expected] of Object.entries({apiRequests:242,apiInput:113332,apiOutput:17259,apiReasoning:9083,cliRequests:339,cliInput:135133,cliOutput:39087})) eq(computedChecks[key],expected,key);
for(const [i,name] of policyNames.entries()) {
 const row=first+i,s=final.summary[name],cloudRow=tokenFirst+i*2+1;
 eq(policy.getRange(`G${row}`).values[0][0],s.measured_n?s.correct/s.measured_n:'NOT RUN',`${name} final quality`);
 if(s.cloud_cost_per_1000_measured_usd !== null) eq(policy.getRange(`Q${cloudRow}`).values[0][0],s.cloud_cost_per_1000_measured_usd,`${name} cost/1000`);
}
// Behavior check then restore the exact recorded inputs before delivery.
const originalCorrect=allRuns.getRange('G9').values[0][0],originalN=allRuns.getRange('F9').values[0][0];
allRuns.getRange('G9').values=[[0]];eq(allRuns.getRange('H9').values[0][0],0,'quality recalculates');
allRuns.getRange('F9').values=[[0]];eq(allRuns.getRange('H9').values[0][0],'NOT RUN','zero denominator guard');
allRuns.getRange('F9').values=[[originalN]];allRuns.getRange('G9').values=[[originalCorrect]];
workbook.recalculate();
const errorScan=await workbook.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},maxChars:3000});
const inspections=[];
for(const range of ['Модели DEV!A8:K24','Модели DEV!L8:U24','FINAL150!A8:X13','FINAL150!A18:R28','Все серии!A8:N14','Все серии!S8:AI14']) {
 const r=await workbook.inspect({kind:'table',range,include:'values,formulas',tableMaxRows:6,tableMaxCols:12,maxChars:4000});inspections.push({range,ndjson:r.ndjson});
}
await fs.writeFile(path.join(outputDir,'formula_inspection.json'),JSON.stringify({errorScan:errorScan.ndjson,inspections},null,2));
const previews=[['Модели DEV','A1:K24','models_quality.png'],['Модели DEV','L7:U24','models_timing_memory.png'],['Модели DEV','V7:AE24','models_controls.png'],
 ['Модели DEV',`A${typedHeader-2}:O${typedLast+3}`,'typed_decisions.png'],['FINAL150','A1:M14','final_quality.png'],['FINAL150','N7:X14','final_calls_latency.png'],
 ['FINAL150','A16:J30','final_tokens.png'],['FINAL150','K17:S30','final_stream_cost.png'],['FINAL150','A32:H48','final_resources_hypothesis.png'],
 ['Все серии','A1:N20','runs_first.png'],['Все серии',`A${lastRun-7}:N${lastRun}`,'runs_last.png'],['Все серии','S7:AJ20','runs_resources.png'],
 ['Все серии',`A${definitionFirst}:H${definitionFirst+definitions.length-1}`,'definitions.png']];
if(Array.isArray(segmentMetadata) && segmentMetadata.length) previews.push(['FINAL150',`A50:I${segmentNoteRow+5}`,'final_segments.png']);
for(const [sheetName,range,name] of previews) {
 const preview=await workbook.render({sheetName,range,scale:1,format:'png'});
 await fs.writeFile(path.join(outputDir,name),new Uint8Array(await preview.arrayBuffer()));
}
const outputPath=path.join(outputDir,'home_pc_models_final150_20261002.xlsx');
await (await SpreadsheetFile.exportXlsx(workbook)).save(outputPath);
const reopened=await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
eq(reopened.worksheets.getItem('Все серии').getRange('B4').values[0][0],242,'reimport API requests');
eq(reopened.worksheets.getItem('Все серии').getRange('E5').values[0][0],135133,'reimport CLI tokens');
for(const [i,name] of policyNames.entries()) eq(reopened.worksheets.getItem('FINAL150').getRange(`G${first+i}`).values[0][0],policy.getRange(`G${first+i}`).values[0][0],`reimport ${name} quality`);
const sourceHashes={};
for(const rel of [apiRel,cliRel,`${mercuryDir}/summary.json`,jevRel,finalAnalysisRel,finalManifestRel,finalRawRel,finalObservationsRel,backendLogRel]) sourceHashes[rel]=sha(await fs.readFile(path.resolve(root,rel),'utf8'));
const finalUsage={};
for(const provider of ['local','cloud']) finalUsage[provider]={calls:sum(policyNames.map(n=>final.summary[n].providers[provider].calls)),
 inputKnown:sum(policyNames.map(n=>final.summary[n].providers[provider].input_tokens_known_sum)),outputKnown:sum(policyNames.map(n=>final.summary[n].providers[provider].output_tokens_known_sum)),
 inputCoverage:sum(policyNames.map(n=>final.summary[n].providers[provider].input_usage_coverage_n)),outputCoverage:sum(policyNames.map(n=>final.summary[n].providers[provider].output_usage_coverage_n)),
 costKnown:sum(policyNames.map(n=>final.summary[n].providers[provider].known_cost_estimate_usd)),unknownCostCalls:sum(policyNames.map(n=>final.summary[n].providers[provider].unknown_cost_calls))};
const validation={createdUtc:new Date().toISOString(),output:outputPath,sheets:['Модели DEV','FINAL150','Все серии'],runAggregates:runs.length,
 modelRows:16,localModelsMeasured:13,localModelsNotRun:2,computedChecks,finalStatus:final.status,finalUsage,rawVerification,finalRawChecks,sourceHashes,
 backendLog:{matchedRequests:backendLog.alignedRequests,completeSeries:backendLog.completeSeries,logSha256:backendLog.logSha256,contextCacheCounterExactN:backendLog.contextCacheCounterExactN,
   contextCacheCounterMissingN:backendLog.contextCacheCounterMissingN,actualOffloadedLayers:'UNKNOWN',backendTtft:'UNKNOWN'},
 formulaErrorScan:errorScan.ndjson,recalculationBoundaryChecked:true,exportReimportChecked:true,nativeExcelApplicationNotOpened:true,previews:previews.map(p=>p[2])};
await fs.writeFile(path.join(outputDir,'validation.json'),JSON.stringify(validation,null,2));
console.log(JSON.stringify({output:outputPath,computedChecks,finalUsage,finalStatus:final.status,previewCount:previews.length}));
