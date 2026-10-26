import fs from 'node:fs/promises';
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
