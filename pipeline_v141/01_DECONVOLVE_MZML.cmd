@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PY=py -3"
py -3 -c "import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul
if errorlevel 1 set "PY=python"
%PY% -c "import numpy,scipy;import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul
if errorlevel 1 (echo Run 00_INSTALL_DEPENDENCIES.cmd first. & pause & exit /b 2)
echo Enter an XML mzML file, mzML ZIP, or folder containing mzML.
set /p "INPUT=mzML path: "
if not defined INPUT (echo Missing input. & pause & exit /b 2)
set "INPUT=%INPUT:"=%"
set /p "MANIFEST=Optional SHA256 run manifest CSV/JSON [ENTER to infer]: "
if defined MANIFEST set "MANIFEST=%MANIFEST:"=%"
set "OPENBLAS_NUM_THREADS=1"
if defined MANIFEST (
  %PY% engine\batch_v141.py --input "%INPUT%" --manifest "%MANIFEST%" --output "%CD%\nist_search"
) else (
  %PY% engine\batch_v141.py --input "%INPUT%" --output "%CD%\nist_search"
)
if errorlevel 1 (echo mzML NNLS FAILED. & pause & exit /b 2)
echo Completed. Run 02_VERIFY_NIST_INPUTS.cmd next.
pause
