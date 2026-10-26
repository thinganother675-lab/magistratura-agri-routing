@echo off
setlocal
set "GAMS_DIR=C:\sarychev\Codex\magistratura\coursework\mmm-ppr\variant-11\runtime\gams\54.5"
if not exist "%GAMS_DIR%\studio\studio.exe" (
  echo Open lab2.gms manually in GAMS Studio.
  pause
  exit /b 1
)
cd /d "%~dp0"
start "" "%GAMS_DIR%\studio\studio.exe" --gams-dir "%GAMS_DIR%" "%~dp0lab2.gms"
