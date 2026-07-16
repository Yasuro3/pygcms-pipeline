@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "NISTMS_EXE="
if exist "nistms_path.txt" set /p NISTMS_EXE=<nistms_path.txt
where py >nul 2>nul
if %ERRORLEVEL%==0 ( set "PYCMD=py -3" ) else ( set "PYCMD=python" )
echo PyGCMS Pipeline - NIST bridge doctor
echo.
if defined NISTMS_EXE (
  %PYCMD% "%~dp0scripts\nist_mssearch_bridge.py" doctor --nistms "%NISTMS_EXE%"
) else (
  %PYCMD% "%~dp0scripts\nist_mssearch_bridge.py" doctor
)
echo.
pause
endlocal
