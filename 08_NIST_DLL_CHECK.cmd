@echo off
setlocal EnableExtensions
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL%==0 ( set "PYCMD=py -3" ) else ( set "PYCMD=python" )
echo ================================================================
echo  Optional NIST DLL backend preflight
echo ================================================================
echo This optional path requires the separately installed pyms-nist-search package.
echo The standard file-automation backend remains available without it.
echo.
%PYCMD% "%~dp0scripts\nist_dll_backend.py" --mssearch-dir "C:\NIST20\MSSEARCH"
echo.
pause
endlocal
