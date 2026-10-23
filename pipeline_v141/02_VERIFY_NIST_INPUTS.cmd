@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
py -3 nist_search\scripts\run_mssearch_v141.py --validate-only --scope all
if errorlevel 1 (echo FAILED. Correct inputs before starting NIST. & pause & exit /b 2)
pause
