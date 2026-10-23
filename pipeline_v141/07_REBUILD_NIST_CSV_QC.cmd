@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
py -3 nist_search\scripts\run_mssearch_v141.py --scope all --export-only
if errorlevel 1 (echo FAILED. & pause & exit /b 2)
pause
