@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo Confirm the NIST software is IDLE and no search is still active.
set /p "OK=Type YES if NIST is idle: "
if /I not "%OK%"=="YES" (echo Cancelled & pause & exit /b 2)
py -3 nist_search\scripts\run_mssearch_v141.py --scope all --resume-after-check
if errorlevel 1 (echo Not complete. & pause & exit /b 2)
pause
