@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "OPENBLAS_NUM_THREADS=1"
py -3 engine\test_global.py
if errorlevel 1 (echo GLOBAL NNLS TEST FAILED. & pause & exit /b 2)
py -3 engine\test_nist_contract.py
if errorlevel 1 (echo NIST CONTRACT TEST FAILED. & pause & exit /b 2)
if exist "nist_search\inputs\query_index.json" (
 py -3 nist_search\scripts\run_mssearch_v141.py --validate-only
 if errorlevel 1 (echo SEARCH INPUT VALIDATION FAILED. & pause & exit /b 2)
)
echo All available tests passed. NIST GUI and authentic AMDIS require independent validation.
pause
