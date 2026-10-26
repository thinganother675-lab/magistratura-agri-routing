param([ValidateSet('0.8B','2B')][string]$Size='2B',[int]$Port=8081)
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskBinary = Join-Path $taskRoot '.runtime\llama\llama-server.exe'
$taskModel = Join-Path $taskRoot "models\Qwen3.5-$Size-Q4_K_M.gguf"
if (!(Test-Path -LiteralPath $taskBinary) -or !(Test-Path -LiteralPath $taskModel)) { throw 'Run scripts/prepare_assets.py first' }
# Foreground startup makes failure visible and lets Ctrl+C stop this exact server.
& $taskBinary -m $taskModel --host 127.0.0.1 --port $Port -c 4096 -t 4 -np 1 --alias "Qwen3.5-$Size-Q4_K_M" --reasoning-budget 0
