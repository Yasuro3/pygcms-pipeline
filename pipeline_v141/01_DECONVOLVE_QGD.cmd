@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PY=py -3"
py -3 -c "import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul
if errorlevel 1 set "PY=python"
%PY% -c "import numpy,scipy;import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul
if errorlevel 1 (echo First run 00_INSTALL_DEPENDENCIES.cmd & pause & exit /b 2)
echo Drag or enter a QGD ZIP, directory, or single QGD file.
set /p "INPUT=Raw QGD input path: "
if not defined INPUT (echo Missing input. & pause & exit /b 2)
set "INPUT=%INPUT:"=%"
echo Optional run manifest CSV/JSON. For the provided Kobe archive type: samples\kobe_fa_40_manifest_LOCAL.json
set /p "MANIFEST=Manifest path [ENTER for filename/folder inference]: "
if defined MANIFEST set "MANIFEST=%MANIFEST:"=%"
set "OPENBLAS_NUM_THREADS=1"
if defined MANIFEST (
  %PY% engine\batch_v141.py --input "%INPUT%" --manifest "%MANIFEST%" --output "%CD%\nist_search"
) else (
  %PY% engine\batch_v141.py --input "%INPUT%" --output "%CD%\nist_search"
)
if errorlevel 1 (echo DECONVOLUTION FAILED. Check source file, run metadata and existing NIST results. & pause & exit /b 2)
echo Deconvolution exported successfully. Next: 02_VERIFY_NIST_INPUTS.cmd
pause
