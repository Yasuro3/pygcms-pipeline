@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "NISTMS_EXE="
if exist "nistms_path.txt" set /p NISTMS_EXE=<nistms_path.txt
where py >nul 2>nul
if %ERRORLEVEL%==0 ( set "PYCMD=py -3" ) else ( set "PYCMD=python" )
echo Launching licensed NIST MS Search for PyGCMS Pipeline...
echo.
if defined NISTMS_EXE (
  %PYCMD% "%~dp0scripts\nist_mssearch_bridge.py" launch --nistms "%NISTMS_EXE%"
) else (
  %PYCMD% "%~dp0scripts\nist_mssearch_bridge.py" launch
)
echo.
echo In NIST MS Search: Options ^> Library Search Options ^> Automation
echo   1) Enable Automation
echo   2) Set Number of hits to print to the app's candidate count or higher
echo   3) Select at least one licensed search library
echo Leave NIST running while searches are performed.
echo.
pause
endlocal
