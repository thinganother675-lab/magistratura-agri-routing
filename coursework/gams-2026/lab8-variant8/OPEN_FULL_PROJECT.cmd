@echo off
setlocal
set "GAMS_DIR=C:\sarychev\Codex\magistratura\coursework\mmm-ppr\variant-11\runtime\gams\54.5"
cd /d "%~dp0"
start "" "%GAMS_DIR%\studio\studio.exe" --gams-dir "%GAMS_DIR%" "%~dp0lab8.gms" "%~dp0scenarios.gms" "%~dp0model.inc" "%~dp0conditions.inc" "%~dp0run_cases.inc" "%~dp0export_results.inc" "%~dp0conopt.opt" "%~dp0conopt.op2"
