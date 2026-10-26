@echo off
setlocal
echo First save lab10.gms and complete F9 in GAMS Studio.
"C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" "C:\sarychev\Codex\magistratura\tmp\gams-simple-tools\statistics_simple.py" "%~dp0."
if errorlevel 1 (
  echo Statistics failed. Read the error above.
  pause
  exit /b 1
)
echo Updated spearman.csv and ranks.csv.
pause
