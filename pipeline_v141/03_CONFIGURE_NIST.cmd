@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
py -3 nist_search\scripts\run_mssearch_v141.py --setup
if errorlevel 1 (echo SETUP NOT COMPLETE. & pause & exit /b 2)
pause
