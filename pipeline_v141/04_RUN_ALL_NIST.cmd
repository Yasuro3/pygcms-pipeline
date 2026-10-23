@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
py -3 nist_search\scripts\run_mssearch_v141.py --scope all
if errorlevel 1 (echo Search stopped. Read errors and wait until NIST is idle before resuming. & pause & exit /b 2)
pause
