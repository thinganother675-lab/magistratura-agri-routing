# Explicit, opt-in import of the workspace-local .env; never echo values.
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskEnvPath = Join-Path $taskRoot '.env'
if (!(Test-Path -LiteralPath $taskEnvPath)) { throw 'Create .env from .env.example, or configure process environment directly' }
foreach ($taskLine in Get-Content -LiteralPath $taskEnvPath) {
    if ($taskLine -match '^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*?)\s*$') {
        $taskName = $Matches[1]
        $taskValue = $Matches[2].Trim('"').Trim("'")
        if ($taskName -notmatch '^(LOCAL_|CLOUD_|MODEL_TIMEOUT_SECONDS)') { throw 'Only model configuration variables are permitted' }
        [Environment]::SetEnvironmentVariable($taskName, $taskValue, 'Process')
    }
}
