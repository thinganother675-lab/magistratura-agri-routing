@echo off
setlocal
set "GAMS_DIR=%~dp0..\mmm-ppr\variant-11\runtime\gams\54.5"
set "MODEL=%~dp0lab2-variant8\lab2.gms"
if not exist "%GAMS_DIR%\studio\studio.exe" (
  echo GAMS Studio was not found in the existing local runtime.
  pause
  exit /b 1
)
if not exist "%MODEL%" (
  start "" "%GAMS_DIR%\studio\studio.exe" --skip-check-for-update --gams-dir "%GAMS_DIR%"
) else (
  start "" "%GAMS_DIR%\studio\studio.exe" --skip-check-for-update --gams-dir "%GAMS_DIR%" "%MODEL%"
)
