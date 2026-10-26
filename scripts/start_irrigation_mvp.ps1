param([int]$Port = 8094)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Не найден Python проекта в .venv\Scripts\python.exe' }
& $pythonPath (Join-Path $PSScriptRoot 'serve_irrigation_mvp.py') --port $Port
