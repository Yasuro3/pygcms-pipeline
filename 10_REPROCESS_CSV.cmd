@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag an original batch ZIP or results folder onto this file.
  echo Or use: py scripts\qc_reprocess.py "INPUT" --out "NEW_OUTPUT"
  pause
  exit /b 1
)
set /p "QCOUT=New empty output folder: "
if not defined QCOUT exit /b 1
py scripts\qc_reprocess.py "%~1" --out "%QCOUT%"
if errorlevel 1 echo QC did not finish. See the error above; no successful result is implied.
pause
