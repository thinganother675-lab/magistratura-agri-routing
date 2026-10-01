import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile, FileBlob } from '@oai/artifact-tool';

// Use the bundled Node executable and node_modules junction beside this builder.
// Reads saved observations only. No inference, networking, or source-file edits.
const outputDir = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(outputDir, '../..');
const sourceRel = 'results/20261001_inventory_summary_3f4378ba/summary.json';
const sourceText = await fs.readFile(path.join(root, sourceRel), 'utf8');
const source = JSON.parse(sourceText);
const unknown = 'UNKNOWN';
const display = value => value === null || value === undefined ? unknown : value;
const numeric = value => typeof value === 'number' && Number.isFinite(value);
const sum = values => values.reduce((a, b) => a + (numeric(b) ? b : 0), 0);
const requireEqual = (actual, expected, label) => {
  if (actual !== expected) throw new Error(`${label}: ${actual} != ${expected}`);
};
const readJson = async rel => JSON.parse(await fs.readFile(path.join(root, rel), 'utf8'));
const manifestCache = new Map();
const manifestFor = async run => {
  if (!manifestCache.has(run)) manifestCache.set(run, await readJson(`results/${run}/manifest.json`));
  return manifestCache.get(run);
};
const statusText = status => ({
  'EARLY STOP': 'Досрочная остановка', 'COMPLETED DEV': 'DEV завершён',
  'RESOURCE STOP': 'Остановка по памяти', 'INFERENCE NOT RUN': 'Инференс не выполнен',
}[status] ?? status);

const allRows = [];
const rawVerification = [];
for (const run of source.all_runs) {
  const manifest = await manifestFor(run.run);
  const meta = manifest.models[run.model];
  const rawRel = `results/${run.run}/${run.model}_raw.jsonl`;
  let data = [];
  if (run.requests > 0) {
    data = (await fs.readFile(path.join(root, rawRel), 'utf8')).trim().split(/\r?\n/).map(JSON.parse);
  }
  requireEqual(data.length, run.requests, `${run.run}/${run.model} raw request count`);
  requireEqual(manifest.cloud_calls, 0, `${run.run} cloud calls`);
  const inputs = data.map(row => row.local.usage?.prompt_tokens ?? row.local.stats?.prompt_tokens);
  const outputs = data.map(row => row.local.usage?.completion_tokens ?? row.local.stats?.completion_tokens);
  const inCoverage = inputs.filter(numeric).length;
  const outCoverage = outputs.filter(numeric).length;
  requireEqual(inCoverage, run.input_usage_coverage_n, `${run.run}/${run.model} input coverage`);
  requireEqual(outCoverage, run.output_usage_coverage_n, `${run.run}/${run.model} output coverage`);
  if (inCoverage) requireEqual(sum(inputs), run.input_tokens_known_sum, `${run.run}/${run.model} input tokens`);
  if (outCoverage) requireEqual(sum(outputs), run.output_tokens_known_sum, `${run.run}/${run.model} output tokens`);
  const reasoning = data.filter(row => row.local.reasoning_rendered === true).length;
  const stats = run.diagnostic;
  let note = run.split === 'custom_dev' ? 'Парный EN/RU DEV probe. Human validation PENDING.' : 'Старый DEV, без final test90.';
  if (!inCoverage && data.length) note += ' Stats отсутствуют. Расход UNKNOWN.';
  if (run.model === 'gpt-oss-20b') note += ' Output и tok/s включают reasoning.';
  if (run.model === 'gpt-oss-20b' && run.requests === 6) note += ' Диагностика reasoning adapter, вне основного ranking.';
  if (run.phase_error) note += ' Загрузка/серия прервана. Не считать стабильным запуском.';
  if (meta.resource_guard_stop) note += ` RAM available ${meta.resource_guard_stop.ram_available_gib.toFixed(2)} GiB при guard stop.`;
  allRows.push([
    run.model, run.run, run.split === 'custom_dev' ? 'Парный QA DEV' : 'Исходный DEV', run.requests,
    stats ? stats.correct : unknown, null,
    display(run.input_tokens_known_sum), display(run.output_tokens_known_sum),
    run.input_usage_coverage_n, run.output_usage_coverage_n,
    display(stats?.latency_p50_s), display(stats?.latency_p95_s),
    display(stats?.decode_tps_median), display(stats?.ttft_median_s),
    display(meta.vram_mib_peak_sampled_total), null, display(meta.ram_gib_peak_sampled_system_used),
    display(meta.inventory?.sizeBytes / 2 ** 30), display(meta.inventory?.quantization?.name),
    run.offload_requested, 0, run.load_success ? 'Да' : 'Нет',
    run.phase_error ? 'Прерван' : meta.early_stop ? 'Досрочная остановка' : 'Серия сохранена',
    display(manifest.context), display(manifest.parallel), reasoning,
    run.requests > 0 ? rawRel : `results/${run.run}/manifest.json`, note,
  ]);
  rawVerification.push({run: run.run, model: run.model, requests: data.length,
    inputKnown: inCoverage ? sum(inputs) : null, outputKnown: outCoverage ? sum(outputs) : null,
    inputCoverage: inCoverage, outputCoverage: outCoverage});
}
requireEqual(sum(source.all_runs.map(run => run.requests)), 339, 'all saved requests');
requireEqual(sum(source.all_runs.map(run => run.input_tokens_known_sum)), 135133, 'known input tokens');
requireEqual(sum(source.all_runs.map(run => run.output_tokens_known_sum)), 39087, 'known output tokens');
requireEqual(sum(source.all_runs.map(run => run.input_usage_coverage_n)), 286, 'known input coverage');
requireEqual(sum(source.all_runs.map(run => run.output_usage_coverage_n)), 286, 'known output coverage');
requireEqual(source.session_usage.cloud_calls_actual, 0, 'session cloud calls');

const summaryRows = [];
for (const [key, model] of Object.entries(source.models)) {
  const record = model.record;
  const attempt = model.attempts.at(-1);
  const run = record?.source_run ?? attempt.run;
  const manifest = await manifestFor(run);
  const meta = manifest.models[key];
  const n = record?.n ?? 0;
  let note = n === 0 ? 'Две незавершённые попытки: offload 0.40 и 0.35. Tokens NOT RUN.' :
    n === 1 ? 'Только 1 ответ. Затем RAM guard. Стабильность и качество не установлены.' :
    record.status === 'EARLY STOP' ? 'Раннее завершение после format errors. N отличается.' :
    n === 36 ? 'Расширенный DEV36. Сравнивать с той же выборкой.' : 'Smoke DEV. Сравнивать одинаковые ID.';
  if (key === 'gpt-oss-20b') note += ' Tokens/tok/s включают reasoning; usage частичное.';
  const all = source.all_runs.find(row => row.run === run && row.model === key);
  const allIndex = source.all_runs.findIndex(row => row.run === run && row.model === key);
  if (!all) throw new Error(`Representative run not found: ${key}/${run}`);
  summaryRows.push([
    key, statusText(model.status), n, record ? record.correct : unknown, null,
    display(record?.input_tokens_known_sum), display(record?.output_tokens_known_sum),
    record?.input_usage_coverage_n ?? 0, record?.output_usage_coverage_n ?? 0,
    display(record?.p50_s), display(record?.p95_s), display(record?.tok_s), display(record?.ttft_s),
    display(record?.vram_mib_total), null, display(record?.ram_gib_system),
    record ? record.size_gib : attempt.inventory.sizeBytes / 2 ** 30,
    record?.quantization ?? attempt.inventory.quantization.name,
    record?.offload_requested ?? attempt.offload_requested,
    display(record?.errors), display(manifest.context), display(manifest.parallel),
    n ? allRows[allIndex][25] : unknown,
    n ? `results/${run}/${key}_raw.jsonl` : `results/${run}/manifest.json`, note,
  ]);
}
requireEqual(summaryRows.length, 15, 'model rows');
requireEqual(summaryRows.filter(row => row[2] > 0).length, 14, 'models with inference');

const workbook = Workbook.create();
const totals = workbook.worksheets.add('Итоги');
const runs = workbook.worksheets.add('Все прогоны');
const FONT = 'Arial';
const HEADER = '#243F5B';
const BODY = '#172B3A';
const LIGHT = '#F2F5F8';
const FIRST = 9;
const headerRow = 8;
const summaryEnd = FIRST + summaryRows.length - 1;
const runEnd = FIRST + allRows.length - 1;

function base(sheet, end, lastColumn) {
  sheet.showGridLines = false;
  const range = sheet.getRange(`A1:${lastColumn}${end}`);
  range.format.font = {name: FONT, size: 11, color: BODY};
  range.format.verticalAlignment = 'center';
  range.format.rowHeight = 30;
  sheet.getRange('A1:AB1').format.rowHeight = 10;
  sheet.getRange('A2').format.font = {name: FONT, size: 15, bold: true, color: HEADER};
  sheet.getRange('A2:AB2').format.rowHeight = 28;
  sheet.getRange('A3:AB3').format.rowHeight = 23;
  sheet.getRange(`A${headerRow}:${lastColumn}${headerRow}`).format = {
    fill: HEADER, font: {name: FONT, size: 11, color: '#FFFFFF', bold: true},
    horizontalAlignment: 'center', verticalAlignment: 'center', wrapText: true,
    rowHeight: 72,
    borders: {insideVertical: {style: 'thin', color: '#FFFFFF'}},
  };
  sheet.getRange(`A${FIRST}:${lastColumn}${end}`).format.rowHeight = 64;
  sheet.getRange(`A${FIRST}:${lastColumn}${end}`).format.wrapText = true;
  sheet.getRange(`C${FIRST}:${lastColumn}${end}`).format.horizontalAlignment = 'right';
  for (let row = FIRST; row <= end; row++) {
    if ((row - FIRST) % 2 === 1) sheet.getRange(`A${row}:${lastColumn}${row}`).format.fill = LIGHT;
  }
  sheet.freezePanes.freezeRows(headerRow);
  sheet.freezePanes.freezeColumns(2);
}
base(totals, summaryEnd, 'Y');
base(runs, runEnd, 'AB');
totals.tabColor = HEADER;

const summaryHeaders = [
  'Модель', 'Статус серии', 'N', 'Верно', 'Качество', 'Input tokens известно', 'Output tokens известно',
  'Input coverage, N', 'Output coverage, N', 'p50, с', 'p95, с', 'Decode, tok/s', 'TTFT, с',
  'VRAM total peak, MiB', 'VRAM total peak, GiB', 'RAM system peak, GiB', 'Файл, GiB', 'Квантование',
  'Offload запрошен', 'Ошибки', 'Контекст запрошен', 'Parallel запрошен', 'Reasoning случаев',
  'Источник серии', 'Примечание',
];
const runHeaders = [
  'Модель', 'Run ID', 'Выборка', 'N', 'Верно', 'Качество', 'Input tokens известно', 'Output tokens известно',
  'Input coverage, N', 'Output coverage, N', 'p50, с', 'p95, с', 'Decode, tok/s', 'TTFT, с',
  'VRAM total peak, MiB', 'VRAM total peak, GiB', 'RAM system peak, GiB', 'Файл, GiB', 'Квантование',
  'Offload запрошен', 'Cloud calls', 'Загрузка завершена', 'Статус попытки', 'Контекст запрошен',
  'Parallel запрошен', 'Reasoning случаев', 'Источник', 'Примечание',
];
totals.getRange(`A${headerRow}:Y${headerRow}`).values = [summaryHeaders];
totals.getRange(`A${FIRST}:Y${summaryEnd}`).values = summaryRows;
runs.getRange(`A${headerRow}:AB${headerRow}`).values = [runHeaders];
runs.getRange(`A${FIRST}:AB${runEnd}`).values = allRows;

totals.getRange(`E${FIRST}`).formulas = [[`=IF(C${FIRST}>0,D${FIRST}/C${FIRST},"NOT RUN")`]];
totals.getRange(`E${FIRST}:E${summaryEnd}`).fillDown();
totals.getRange(`O${FIRST}`).formulas = [[`=IF(ISNUMBER(N${FIRST}),N${FIRST}/1024,"UNKNOWN")`]];
totals.getRange(`O${FIRST}:O${summaryEnd}`).fillDown();
runs.getRange(`F${FIRST}`).formulas = [[`=IF(D${FIRST}>0,E${FIRST}/D${FIRST},"NOT RUN")`]];
runs.getRange(`F${FIRST}:F${runEnd}`).fillDown();
runs.getRange(`P${FIRST}`).formulas = [[`=IF(ISNUMBER(O${FIRST}),O${FIRST}/1024,"UNKNOWN")`]];
runs.getRange(`P${FIRST}:P${runEnd}`).fillDown();

totals.getRange('A2').values = [['Локальные модели: токены и память']];
totals.getRange('A3').values = [['01.10.2026. Репрезентативная DEV-серия каждой модели. Независимый final holdout не выполнен.']];
totals.getRange('A4').values = [['Моделей с сохранённым ответом']];
totals.getRange('B4').formulas = [[`=COUNTIFS(C${FIRST}:C${summaryEnd},">0")`]];
totals.getRange('A5').values = [['Всего проверено моделей']];
totals.getRange('B5').values = [[15]];
totals.getRange('F4').values = [['Статус и N важнее общей доли верных: выборки и ранние остановки различаются.']];
totals.getRange('F5').values = [['Coverage — число запросов с известным счётчиком токенов; знаменатель — число запросов N.']];
totals.getRange('A6').values = [['CLI temperature/seed/max tokens UNKNOWN. Peak памяти включает весь GPU/ПК и измерен примерно раз в 0.5 с.']];

runs.getRange('A2').values = [['Все сохранённые локальные серии']];
runs.getRange('A3').values = [['01.10.2026. Агрегат Run ID × модель. Повторные DEV-ответы не являются независимыми тестовыми наблюдениями.']];
runs.getRange('A4').values = [['Сохранено запросов']];
runs.getRange('B4').formulas = [[`=SUM(D${FIRST}:D${runEnd})`]];
runs.getRange('A5').values = [['Известно input tokens']];
runs.getRange('B5').formulas = [[`=SUM(G${FIRST}:G${runEnd})`]];
runs.getRange('A6').values = [['Известно output tokens']];
runs.getRange('B6').formulas = [[`=SUM(H${FIRST}:H${runEnd})`]];
runs.getRange('F4').formulas = [[`="Input coverage: "&SUM(I${FIRST}:I${runEnd})&"/"&SUM(D${FIRST}:D${runEnd})&". Output coverage: "&SUM(J${FIRST}:J${runEnd})&"/"&SUM(D${FIRST}:D${runEnd})`]];
runs.getRange('F5').formulas = [[`="Local-only. Облачных вызовов: "&SUM(U${FIRST}:U${runEnd})&". API billing отсутствует; энергия и время ПК не оценены."`]];
runs.getRange('F6').values = [['48 первых diagnostic requests не имеют stats. Известные суммы — нижняя доступная сумма, не полный расход.']];

const summaryWidths = [44,24,7,12,12,15,15,12,12,11,11,13,11,15,15,15,12,15,14,12,14,13,14,60,58];
const runWidths = [44,39,18,7,12,12,15,15,12,12,11,11,13,11,15,15,15,12,15,14,12,17,22,14,13,13,60,58];
function columnName(number) {
  let name = '';
  for (let n = number; n > 0; n = Math.floor((n - 1) / 26)) name = String.fromCharCode(65 + (n - 1) % 26) + name;
  return name;
}
for (const [index, width] of summaryWidths.entries()) totals.getRange(`${columnName(index+1)}1:${columnName(index+1)}${summaryEnd}`).format.columnWidth = width;
for (const [index, width] of runWidths.entries()) runs.getRange(`${columnName(index+1)}1:${columnName(index+1)}${runEnd}`).format.columnWidth = width;
totals.getRange(`A${FIRST}:B${summaryEnd}`).format.horizontalAlignment = 'left';
totals.getRange(`R${FIRST}:S${summaryEnd}`).format.horizontalAlignment = 'left';
totals.getRange(`X${FIRST}:Y${summaryEnd}`).format.horizontalAlignment = 'left';
runs.getRange(`A${FIRST}:C${runEnd}`).format.horizontalAlignment = 'left';
runs.getRange(`S${FIRST}:T${runEnd}`).format.horizontalAlignment = 'left';
runs.getRange(`V${FIRST}:W${runEnd}`).format.horizontalAlignment = 'left';
runs.getRange(`AA${FIRST}:AB${runEnd}`).format.horizontalAlignment = 'left';
for (const [sheet, columns, end] of [
  [totals,['C','D','F','G','H','I','N','T','U','V','W'],summaryEnd],
  [runs,['D','E','G','H','I','J','O','U','X','Y','Z'],runEnd],
]) for (const col of columns) sheet.getRange(`${col}${FIRST}:${col}${end}`).setNumberFormat('#,##0');
totals.getRange(`E${FIRST}:E${summaryEnd}`).setNumberFormat('0.0%');
runs.getRange(`F${FIRST}:F${runEnd}`).setNumberFormat('0.0%');
for (const [sheet, columns, end] of [
  [totals,['J','K','M'],summaryEnd], [runs,['K','L','N'],runEnd],
]) for (const col of columns) sheet.getRange(`${col}${FIRST}:${col}${end}`).setNumberFormat('0.000');
for (const [sheet, columns, end] of [
  [totals,['L','O','P','Q'],summaryEnd], [runs,['M','P','Q','R'],runEnd],
]) for (const col of columns) sheet.getRange(`${col}${FIRST}:${col}${end}`).setNumberFormat('0.00');
runs.getRange('B4:B6').setNumberFormat('#,##0');
for (const sheet of [totals,runs]) {
  sheet.getRange('A3:AB6').format.wrapText = false;
  sheet.getRange('A3').format.font = {name:FONT,size:11,color:'#506477',italic:true};
  sheet.getRange('A7:AB7').format.rowHeight = 12;
}

const summaryTable = totals.tables.add(`A${headerRow}:Y${summaryEnd}`, true, 'ModelSummary');
const runsTable = runs.tables.add(`A${headerRow}:AB${runEnd}`, true, 'AllLocalRuns');
summaryTable.showFilterButton = true;
runsTable.showFilterButton = true;
// Explicit statuses carry meaning; colors only help find unfinished series.
totals.getRange(`B${FIRST}:B${summaryEnd}`).conditionalFormats.add('containsText', {text:'не выполнен',format:{fill:'#FCE8E6',font:{color:'#9D2C23'}}});
totals.getRange(`B${FIRST}:B${summaryEnd}`).conditionalFormats.add('containsText', {text:'Остановка по памяти',format:{fill:'#FFF1D6',font:{color:'#825A12'}}});
totals.getRange(`F${FIRST}:G${summaryEnd}`).conditionalFormats.add('containsText', {text:unknown,format:{fill:'#FFF1D6',font:{color:'#825A12'}}});
runs.getRange(`G${FIRST}:H${runEnd}`).conditionalFormats.add('containsText', {text:unknown,format:{fill:'#FFF1D6',font:{color:'#825A12'}}});

const noteStart = summaryEnd + 3;
const notes = [
  ['Определения и ограничения', ''],
  ['Input / Output', 'LM Studio CLI Prompt/Predicted tokens. При необходимости взяты сохранённые stats; текст по символам не пересчитывался.'],
  ['Reasoning', 'GPT-OSS включает reasoning в output tokens и decode speed. Раздельное число reasoning tokens UNKNOWN.'],
  ['Память', 'VRAM — весь GPU, RAM — вся система. Sampled peak может пропустить точный максимум. Это не память только модели.'],
  ['Offload', 'Запрошенный режим max или fraction. Фактически перенесённое число GPU layers UNKNOWN.'],
  ['Неполные серии', 'UNKNOWN означает отсутствие измерения. N=0 означает, что inference не выполнен. Coder не завершил загрузку.'],
  ['Научный статус', 'DEV only. Переводы QA human validation PENDING. Новые cloud/hybrid/final holdout результаты отсутствуют.'],
  ['Источник агрегатов', sourceRel],
];
totals.getRange(`A${noteStart}:B${noteStart + notes.length - 1}`).values = notes;
totals.getRange(`A${noteStart}:J${noteStart + notes.length - 1}`).format.font = {name:FONT,size:11,color:'#506477'};
totals.getRange(`A${noteStart}:A${noteStart + notes.length - 1}`).format.font = {name:FONT,size:11,bold:true,color:BODY};
totals.getRange(`A${noteStart}:J${noteStart + notes.length - 1}`).format.rowHeight = 26;
totals.getRange(`B${noteStart}:B${noteStart + notes.length - 1}`).format.wrapText = false;

workbook.recalculate();
const checks = {
  modelCount: summaryRows.length,
  modelsWithInference: totals.getRange('B4').values[0][0],
  requests: runs.getRange('B4').values[0][0],
  inputKnown: runs.getRange('B5').values[0][0],
  outputKnown: runs.getRange('B6').values[0][0],
  inputCoverage: sum(source.all_runs.map(row=>row.input_usage_coverage_n)),
  outputCoverage: sum(source.all_runs.map(row=>row.output_usage_coverage_n)),
  cloudCalls: sum(allRows.map(row=>row[20])),
};
requireEqual(checks.modelsWithInference,14,'workbook model count');
requireEqual(checks.requests,339,'workbook request sum');
requireEqual(checks.inputKnown,135133,'workbook input sum');
requireEqual(checks.outputKnown,39087,'workbook output sum');
requireEqual(checks.cloudCalls,0,'workbook cloud calls');
for (let index=0;index<summaryRows.length;index++) {
  const row=FIRST+index; const n=summaryRows[index][2];
  requireEqual(totals.getRange(`E${row}`).values[0][0],n ? summaryRows[index][3]/n:'NOT RUN',`quality row ${row}`);
}
// Recalculation boundary checks in-place, then restore recorded data before export.
const originalN=totals.getRange('C9').values[0][0];
const originalCorrect=totals.getRange('D9').values[0][0];
totals.getRange('D9').values=[[6]];
requireEqual(totals.getRange('E9').values[0][0],6/originalN,'quality recalculates');
totals.getRange('C9').values=[[0]];
requireEqual(totals.getRange('E9').values[0][0],'NOT RUN','zero N guard');
totals.getRange('C9').values=[[originalN]];
totals.getRange('D9').values=[[originalCorrect]];
workbook.recalculate();

const inspections = [];
for (const range of ['Итоги!A8:M12','Итоги!N8:Y12','Итоги!A21:Y23','Все прогоны!A8:J13','Все прогоны!D27:AB33']) {
  const result=await workbook.inspect({kind:'table',range,include:'values,formulas',tableMaxRows:7,tableMaxCols:12,maxChars:7000});
  inspections.push({range,ndjson:result.ndjson});
}
const errorScan=await workbook.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},maxChars:3000});
await fs.writeFile(path.join(outputDir,'formula_inspection.json'),JSON.stringify({inspections,errorScan:errorScan.ndjson},null,2));

const previewRanges=[
  ['Итоги','A1:M24','itogi_tokens.png'],
  ['Итоги','N7:Y24','itogi_resources.png'],
  ['Итоги',`A${noteStart}:K${noteStart+notes.length-1}`,'itogi_notes.png'],
  ['Все прогоны','A1:N21','runs_first.png'],
  ['Все прогоны',`A22:N${runEnd}`,'runs_last.png'],
  ['Все прогоны',`O7:AB${runEnd}`,'runs_resources.png'],
];
for (const [sheetName,range,name] of previewRanges) {
  const image=await workbook.render({sheetName,range,scale:1,format:'png'});
  await fs.writeFile(path.join(outputDir,name),new Uint8Array(await image.arrayBuffer()));
}

const outputPath=path.join(outputDir,'home_pc_models_20261001.xlsx');
await (await SpreadsheetFile.exportXlsx(workbook)).save(outputPath);
const reopened=await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
requireEqual(reopened.worksheets.getItem('Все прогоны').getRange('B4').values[0][0],339,'exported request total');
requireEqual(reopened.worksheets.getItem('Итоги').getRange('E23').values[0][0],'NOT RUN','exported coder missing quality');
const validation={createdUtc:new Date().toISOString(),source:sourceRel,
  sourceSha256:crypto.createHash('sha256').update(sourceText).digest('hex'),
  workbook:path.basename(outputPath),sheets:['Итоги','Все прогоны'],checks,
  allRunModelAggregates:allRows.length,knownStatsAreLowerBound:true,unknownNeverImputedAsZero:true,
  formulasChecked:true,recalculationBoundaryChecked:true,exportReimportChecked:true,
  nativeExcelApplicationNotOpened:true,rawVerification,
  limitation:'CLI controls UNKNOWN; sampled whole-device/system memory; requested offload; no final holdout or new cloud benchmark.'};
await fs.writeFile(path.join(outputDir,'validation.json'),JSON.stringify(validation,null,2));
console.log(JSON.stringify({output:outputPath,checks,runModelAggregates:allRows.length,previewCount:previewRanges.length}));
