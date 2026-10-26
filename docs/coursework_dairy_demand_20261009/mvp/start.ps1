param([int]$Port = 8096, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$dairyCandidates = @((Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'), (Get-Command python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source), (Get-Command py -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -Unique
$dairyPython = $null
foreach ($candidate in $dairyCandidates) {
    & $candidate -c "import sys,importlib.util; sys.exit(0 if sys.version_info >= (3,10) and importlib.util.find_spec('numpy') else 1)"
    if ($LASTEXITCODE -eq 0) { $dairyPython = $candidate; break }
}
if (-not $dairyPython) { throw 'Нужен Python 3.10 или новее с NumPy. Установка: python -m pip install -r requirements.txt. Готовый просмотр: offline.html.' }
$dairyArguments = @('app.py', '--port', $Port)
if (-not $NoBrowser) { $dairyArguments += '--open-browser' }
& $dairyPython @dairyArguments
if ($LASTEXITCODE -ne 0) { throw 'Сервер не запустился. Если порт занят, выполните .\start.ps1 -Port 0. Для просмотра без сервера откройте offline.html.' }
