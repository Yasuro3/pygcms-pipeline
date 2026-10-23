@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PY=py -3"
py -3 -c "import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul
if errorlevel 1 set "PY=python"
%PY% -c "import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)"
if errorlevel 1 (
 echo Python 3.10 or higher is required. Install Python 3 for Windows first.
 pause
 exit /b 2
)
%PY% -m pip install -r engine\requirements.txt
if errorlevel 1 (echo Python package installation FAILED & pause & exit /b 2)
%PY% engine\test_global.py
if errorlevel 1 (echo Engine self-tests FAILED & pause & exit /b 2)
echo Dependencies and numerical tests passed.
pause
