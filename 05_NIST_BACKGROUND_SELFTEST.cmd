@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "NISTMS_EXE="
if exist "nistms_path.txt" set /p NISTMS_EXE=<nistms_path.txt
where py >nul 2>nul
if %ERRORLEVEL%==0 ( set "PYCMD=py -3" ) else ( set "PYCMD=python" )
echo Running the licensed NIST /PAR=2 background-automation self-test...
echo.
if defined NISTMS_EXE (
  %PYCMD% "%~dp0scripts\nist_mssearch_bridge.py" background-test --nistms "%NISTMS_EXE%" --prelaunch
) else (
  %PYCMD% "%~dp0scripts\nist_mssearch_bridge.py" background-test --prelaunch
)
echo.
echo Expected: Hits parsed should be greater than 0.
echo If it is 0, enable NIST Automation, increase Number of hits to print,
echo and select at least one licensed library.
echo.
pause
endlocal
