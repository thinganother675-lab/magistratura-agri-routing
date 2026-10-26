param([Parameter(ValueFromRemainingArguments=$true)][string[]]$GamsArguments)
$ErrorActionPreference = 'Stop'
$gamsExecutable = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../mmm-ppr/variant-11/runtime/gams/54.5/gams.exe'))
if (-not (Test-Path -LiteralPath $gamsExecutable)) {
    throw "Existing local GAMS runtime not found: $gamsExecutable"
}
& $gamsExecutable @GamsArguments
exit $LASTEXITCODE
