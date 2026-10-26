@echo off
setlocal
set "PYTHON=C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
set "SCRIPT=C:\sarychev\Codex\magistratura\tmp\gams-future-tools\lab10\analyze.py"
echo First save lab10.gms and complete its F9 run in GAMS Studio.
echo This step reads input_data.csv and efficiencies.csv from that run.
if not exist "%PYTHON%" (
  echo Bundled Python not found.
  pause
  exit /b 1
)
if not exist "%SCRIPT%" (
  echo Statistics script not found: %SCRIPT%
  pause
  exit /b 1
)
"%PYTHON%" "%SCRIPT%" "%~dp0."
if errorlevel 1 (
  echo Statistics failed. Read the error above.
  pause
  exit /b 1
)
echo Statistics updated: spearman.csv, ranks.csv, and text results.
pause

