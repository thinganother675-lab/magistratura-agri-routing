@echo off
setlocal
set "STUDIO=C:\sarychev\Codex\magistratura\coursework\mmm-ppr\variant-11\runtime\gams\54.5\studio\studio.exe"
if not exist "%STUDIO%" (
  echo GAMS Studio not found: %STUDIO%
  pause
  exit /b 1
)
echo Open lab10.gms, save changes, then press F9.
echo After GAMS finishes, run 04_RECALCULATE_STATS.cmd.
start "" "%STUDIO%" "%~dp0lab10.gms"
