import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';

// Read-only derivation. Never exports log bodies, request headers, prompts or responses.
const out=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(out,'../..');
const logPath='C:/Users/hustlePC/.lmstudio/server-logs/2026-10/2026-10-01.1.log';
const logBytes=await fs.readFile(logPath),lines=logBytes.toString('utf8').split(/\r?\n/);
const api=JSON.parse(await fs.readFile(path.join(root,'results/20261001_api_tables_35768dbf/summary.json'),'utf8'));
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const readJson=async rel=>JSON.parse(await fs.readFile(path.join(root,rel),'utf8'));
const records=[],known=new Map();
for(const r of api.all_runs) {
  const manifestRel=`results/${r.run}/manifest.json`,manifestBytes=await fs.readFile(path.join(root,manifestRel));
  const manifest=JSON.parse(manifestBytes),id=manifest.models[r.model]?.own_instance_id;
  const rawRel=`results/${r.run}/${r.model}_raw.jsonl`;
  const rawBytes=r.n?await fs.readFile(path.join(root,rawRel)):null;
  const raw=rawBytes?rawBytes.toString('utf8').trim().split(/\r?\n/).filter(Boolean).map(JSON.parse):[];
  const record={run:r.run,model:r.model,n:r.n,instance:id ?? null,rawRel,rawSha256:rawBytes?sha(rawBytes):null,
    manifestRel,manifestSha256:sha(manifestBytes),actualLoadConfig:manifest.models[r.model]?.actual_load_config ?? {},raw,blocks:[]};
  records.push(record);
  if(id) {if(known.has(id)) throw new Error('Duplicate saved own instance ID');known.set(id,record);}
}
let active=null,totalMetricLines=0,ambiguousKnownBlocks=0;
const tsOf=line=>line.match(/^\[?(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/)?.[1] ?? null;
for(let i=0;i<lines.length;i++) {
  const line=lines[i];
  const start=line.match(/^\[?\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]?\s*\[(?:INFO|DEBUG)\]\s*\[([^\]]+)\]\s+Running chat/);
  if(start) {
    if(active?.known) {active.rejected='another request started before own finish';ambiguousKnownBlocks++;known.get(active.id).blocks.push(active);}
    active={id:start[1],known:known.has(start[1]),startLine:i+1,startTimestamp:tsOf(line),prompt:[],decode:[],total:[],nTokens:[],finished:false};
  }
  const metric=line.match(/(prompt eval|eval) time\s*=\s*([\d.]+) ms\s*\/\s*(\d+) tokens\s*\(\s*([\d.]+) ms per token,\s*([\d.]+) tokens per second\)/);
  if(metric) {
    totalMetricLines++;
    if(active?.known) active[metric[1]==='prompt eval'?'prompt':'decode'].push({line:i+1,ms:Number(metric[2]),tokens:Number(metric[3]),msPerToken:Number(metric[4]),tps:Number(metric[5])});
  }
  if(active?.known) {
    const total=line.match(/total time\s*=\s*([\d.]+) ms\s*\/\s*(\d+) tokens/);
    if(total) active.total.push({line:i+1,ms:Number(total[1]),tokens:Number(total[2])});
    const nTokens=line.match(/\bn_tokens\s*=\s*(\d+)/);
    if(nTokens) active.nTokens.push({line:i+1,tokens:Number(nTokens[1])});
  }
  const end=line.match(/^\[?\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]?\s*\[(?:INFO|DEBUG)\]\s*\[([^\]]+)\]\s+Finished/);
  if(end && active) {
    if(active.known) {
      active.endLine=i+1;active.endTimestamp=tsOf(line);active.finished=end[1]===active.id;
      if(!active.finished) active.rejected='finish marker has another instance';
      known.get(active.id).blocks.push(active);
    }
    active=null;
  }
}
if(active?.known) {active.rejected='log ended before finish marker';known.get(active.id).blocks.push(active);}
const median=values=>{const s=values.toSorted((a,b)=>a-b),n=s.length;return n?n%2?s[(n-1)/2]:(s[n/2-1]+s[n/2])/2:null;};
const csvCell=value=>value===null||value===undefined?'UNKNOWN':typeof value==='string'?`"${value.replaceAll('"','""')}"`:String(value);
const requestRows=[],aggregates=[];
for(const record of records) {
  const countExact=record.blocks.length===record.n;
  let complete=countExact && record.n>0;
  const aligned=[];
  for(let i=0;i<record.raw.length;i++) {
    const row=record.raw[i],block=record.blocks[i],usage=row.local?.usage ?? {};
    const created=row.local?.raw?.events?.find(e=>Number.isFinite(e.data?.created))?.data?.created;
    const localAsUtc=block?.startTimestamp?Date.parse(block.startTimestamp.replace(' ','T')+'Z')/1000:null;
    const timestampOffsetS=Number.isFinite(created)&&Number.isFinite(localAsUtc)?localAsUtc-created:null;
    const tests={blockCountExact:countExact,ownInstanceBeginFinish:Boolean(block?.finished && !block.rejected),
      onePromptAndDecodeMetric:block?.prompt.length===1 && block?.decode.length===1,
      completionTokensExact:block?.decode[0]?.tokens===usage.completion_tokens,
      timezoneOffsetPlus3h:timestampOffsetS!==null && Math.abs(timestampOffsetS-10800)<=1,
      totalTokensExact:block?.total.length===1 && block.total[0].tokens===block.prompt[0]?.tokens+block.decode[0]?.tokens,
      promptPrefillSubset:Number.isFinite(usage.prompt_tokens)&&block?.prompt[0]?.tokens<=usage.prompt_tokens};
    const valid=Object.values(tests).every(Boolean);
    complete&&=valid;
    const detail={run:record.run,model:record.model,instance:record.instance,request_index:i+1,sample_id:row.sample.id,
      valid,alignment_tests:tests,prompt_tokens_reported:usage.prompt_tokens,completion_tokens_reported:usage.completion_tokens,
      timestamp_offset_seconds:timestampOffsetS,line_start:block?.startLine ?? null,line_end:block?.endLine ?? null,
      logged_context_n_tokens:block?.nTokens[0]?.tokens ?? null,context_n_tokens_difference:block?.nTokens[0]?block.nTokens[0].tokens-(usage.prompt_tokens+usage.completion_tokens-1):null,
      context_cache_diagnostic:{available:block?.nTokens.length===1,counter_n:block?.nTokens.length ?? 0,
        logged_values:block?.nTokens.map(n=>n.tokens) ?? [],exact_non_speculative_arithmetic:block?.nTokens.length===1 && block.nTokens[0].tokens===usage.prompt_tokens+usage.completion_tokens-1,
        speculative_draft_mtp:record.actualLoadConfig.speculative_draft_mtp ?? null},
      prompt_eval_tokens:valid?block.prompt[0].tokens:null,prompt_eval_ms:valid?block.prompt[0].ms:null,
      prompt_eval_tps:valid?block.prompt[0].tps:null,decode_tokens:valid?block.decode[0].tokens:null,
      decode_ms:valid?block.decode[0].ms:null,backend_decode_tps:valid?block.decode[0].tps:null,
      metric_line_prompt:block?.prompt[0]?.line ?? null,metric_line_decode:block?.decode[0]?.line ?? null};
    requestRows.push(detail);aligned.push(detail);
  }
  aggregates.push({run:record.run,model:record.model,instance:record.instance,n:record.n,log_block_n:record.blocks.length,
    unambiguously_aligned_n:aligned.filter(r=>r.valid).length,complete_alignment:complete,
    backend_decode_tps_median:complete?median(aligned.map(r=>r.backend_decode_tps)):null,
    backend_prompt_eval_tps_median:complete?median(aligned.map(r=>r.prompt_eval_tps)):null,
    actual_offloaded_layers:'UNKNOWN',rawRel:record.rawRel,rawSha256:record.rawSha256,
    manifestRel:record.manifestRel,manifestSha256:record.manifestSha256,
    actual_load_config:record.actualLoadConfig,
    line_ranges:record.blocks.map(b=>[b.startLine,b.endLine ?? null])});
}
const report={status:'LOG_DERIVED_AUXILIARY_ONLY',logPath,logSha256:sha(logBytes),logSizeBytes:logBytes.length,
 totalMetricLines,knownInstances:known.size,ambiguousKnownBlocks,requestN:requestRows.length,
 alignedRequests:requestRows.filter(r=>r.valid).length,completeSeries:aggregates.filter(r=>r.complete_alignment).length,
 contextCacheCounterExactN:requestRows.filter(r=>r.context_cache_diagnostic.exact_non_speculative_arithmetic).length,
 contextCacheCounterMissingN:requestRows.filter(r=>r.context_cache_diagnostic.counter_n===0).length,
 contextCacheCounterMultipleN:requestRows.filter(r=>r.context_cache_diagnostic.counter_n>1).length,
 limitation:'Only exact saved home-api instances. Prompt eval tokens are the uncached prefill subset; decode TPS is backend log timing and includes counted reasoning. Full usage counters are never replaced by cache/prefill counters. Native n_tokens cache arithmetic is separately diagnostic (MTP can differ); it is not required to identify a request whose exact instance, order/count, completion tokens and timestamp all agree. No backend TTFT or actual GPU layer count is established. Log request-start timestamps independently align at UTC+03:00 within one second.',
 aggregates,requests:requestRows};
await fs.writeFile(path.join(out,'backend_log_metrics.json'),JSON.stringify(report,null,2));
const cols=['run','model','instance','request_index','sample_id','valid','prompt_tokens_reported','completion_tokens_reported','line_start','line_end',
 'metric_line_prompt','metric_line_decode','prompt_eval_tokens','prompt_eval_ms','prompt_eval_tps','decode_tokens','decode_ms','backend_decode_tps'];
await fs.writeFile(path.join(out,'backend_log_metrics.csv'),[cols.join(','),...requestRows.map(r=>cols.map(c=>csvCell(r[c])).join(','))].join('\n')+'\n');
console.log(JSON.stringify({logSha256:report.logSha256,totalMetricLines,knownInstances:known.size,requestN:requestRows.length,alignedRequests:report.alignedRequests,
 completeSeries:report.completeSeries,ambiguousKnownBlocks,aggregates:aggregates.map(r=>({run:r.run,model:r.model,n:r.n,log_block_n:r.log_block_n,aligned:r.unambiguously_aligned_n,backendDecodeTps:r.backend_decode_tps_median,promptEvalTps:r.backend_prompt_eval_tps_median})),
 firstFailed:requestRows.filter(r=>!r.valid).slice(0,5).map(r=>({run:r.run,model:r.model,index:r.request_index,tests:r.alignment_tests}))}));
