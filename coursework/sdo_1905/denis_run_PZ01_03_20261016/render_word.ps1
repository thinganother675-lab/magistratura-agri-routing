$ErrorActionPreference='Stop'
$taskRoot=$PSScriptRoot
$taskWord=$null;$taskDoc=$null;$taskReport=@()
try {
 $taskWord=New-Object -ComObject Word.Application
 $taskWord.Visible=$false;$taskWord.DisplayAlerts=0
 foreach($taskFile in Get-ChildItem -LiteralPath (Join-Path $taskRoot 'submission') -Filter '*.docx' -File){
  $taskDoc=$taskWord.Documents.Open($taskFile.FullName,$false,$true)
  $taskDoc.Repaginate()
  $taskPdf=Join-Path $taskRoot ('qa/'+$taskFile.BaseName+'.pdf')
  $taskDoc.ExportAsFixedFormat($taskPdf,17)
  $taskReport+=@{file=$taskFile.Name;pages=$taskDoc.ComputeStatistics(2);pdf=$taskPdf;word_version=$taskWord.Version}
  $taskDoc.Close(0);$taskDoc=$null
 }
 $taskReport|ConvertTo-Json -Depth 4|Set-Content (Join-Path $taskRoot 'evidence/word_render.json') -Encoding utf8
 $taskReport|Select-Object file,pages|ConvertTo-Json
}finally{
 if($taskDoc){$taskDoc.Close(0)}
 if($taskWord){$taskWord.Quit();[void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($taskWord)}
}
