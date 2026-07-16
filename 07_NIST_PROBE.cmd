@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "NISTMS_EXE="
if exist "nistms_path.txt" set /p NISTMS_EXE=<nistms_path.txt
where py >nul 2>nul
if %ERRORLEVEL%==0 ( set "PYCMD=py -3" ) else ( set "PYCMD=python" )
echo ================================================================
echo  NIST automation probe - tests supported switch combinations
echo ================================================================
echo Close NIST MS Search before continuing; the probe relaunches it.
pause
if defined NISTMS_EXE (
  %PYCMD% "%~dp0scripts\nist_mssearch_bridge.py" probe --nistms "%NISTMS_EXE%" --all
) else (
  %PYCMD% "%~dp0scripts\nist_mssearch_bridge.py" probe --all
)
echo.
pause
endlocal
