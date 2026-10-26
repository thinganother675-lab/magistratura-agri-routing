param([string]$PythonExe='', [string]$GamsExe='', [switch]$BuildReports)
$ErrorActionPreference='Stop'
$taskRoot=$PSScriptRoot
if (-not $PythonExe) {
    $bundledPython=Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
    if (Test-Path -LiteralPath $bundledPython) {$PythonExe=$bundledPython}
    else {$PythonExe=(Get-Command python -ErrorAction Stop).Source}
}
if (-not $GamsExe) {
    $localGams=Join-Path $taskRoot 'runtime/gams/54.5/gams.exe'
    if (Test-Path -LiteralPath $localGams) {$GamsExe=$localGams}
    elseif (Test-Path -LiteralPath (Join-Path $taskRoot '../variant-11/runtime/gams/54.5/gams.exe')) {$GamsExe=(Resolve-Path (Join-Path $taskRoot '../variant-11/runtime/gams/54.5/gams.exe')).Path}
    else {$GamsExe=(Get-Command gams -ErrorAction Stop).Source}
}
function Invoke-Checked([string]$exe,[string[]]$arguments) {
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) {throw "Command failed, exit code $LASTEXITCODE"}
}
Invoke-Checked $PythonExe @((Join-Path $taskRoot 'scripts/prepare_data.py'))
Invoke-Checked $PythonExe @((Join-Path $taskRoot 'scripts/independent_check.py'))
Push-Location (Join-Path $taskRoot 'models')
try {
    foreach ($lab in @('lab2','lab8','lab10')) {
        Invoke-Checked $GamsExe @("$lab.gms",'lo=2','appendlog=0',"o=../logs/$lab.lst","lf=../logs/$lab.log")
    }
} finally {Pop-Location}
Invoke-Checked $PythonExe @((Join-Path $taskRoot 'scripts/verify_gams.py'))
if ($BuildReports) {Invoke-Checked $PythonExe @((Join-Path $taskRoot 'scripts/build_reports.py'))}
Write-Host 'All numerical checks passed. Files are in results/.'
