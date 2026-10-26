@echo off
setlocal
set "GAMS_DIR=%~dp0..\..\mmm-ppr\variant-11\runtime\gams\54.5"
if not exist "%GAMS_DIR%\studio\studio.exe" (
  echo Open lab2.gms in an installed GAMS Studio.
  pause
  exit /b 1
)
start "" "%GAMS_DIR%\studio\studio.exe" --skip-check-for-update --gams-dir "%GAMS_DIR%" "%~dp0lab2.gms"
