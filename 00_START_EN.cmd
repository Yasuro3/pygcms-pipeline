@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PORT=18789"
set "NISTMS_EXE="
set "WORK=%~dp0bridge_work"
if not exist "%WORK%" mkdir "%WORK%"
if not exist "%WORK%\batch_outputs" mkdir "%WORK%\batch_outputs"
if exist "nistms_path.txt" set /p NISTMS_EXE=<nistms_path.txt

for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
  echo Stopping existing PyGCMS Pipeline bridge on port %PORT%: PID %%a
  taskkill /PID %%a /F >nul 2>nul
)

where py >nul 2>nul
if %ERRORLEVEL%==0 ( set "PYCMD=py -3" ) else ( set "PYCMD=python" )

echo Starting PyGCMS Pipeline v1.3.0
echo App URL: http://127.0.0.1:%PORT%/app
echo Bridge output: %WORK%
echo.
echo For licensed NIST MS Search, copy nistms_path.example.txt to nistms_path.txt
echo and place the full path to NISTMS$.EXE on its first line.
echo Example: C:\NIST20\MSSEARCH\NISTMS$.EXE
echo.
if defined NISTMS_EXE (
  start "PyGCMS Pipeline bridge %PORT%" cmd /k %PYCMD% "%~dp0scripts\nist_mssearch_bridge_server.py" --nistms "%NISTMS_EXE%" --port %PORT% --workdir "%WORK%"
) else (
  start "PyGCMS Pipeline bridge %PORT%" cmd /k %PYCMD% "%~dp0scripts\nist_mssearch_bridge_server.py" --port %PORT% --workdir "%WORK%"
)

set "READY=0"
for /l %%i in (1,1,25) do (
  powershell -NoProfile -Command "try{$r=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:%PORT%/health' -TimeoutSec 1; if($r.StatusCode -eq 200){exit 0}else{exit 1}}catch{exit 1}" >nul 2>nul
  if not errorlevel 1 (
    set "READY=1"
    goto openapp
  )
  timeout /t 1 /nobreak >nul
)

:openapp
if "%READY%"=="1" (
  start "" "http://127.0.0.1:%PORT%/app"
) else (
  echo Bridge did not respond. Opening the browser application directly.
  start "" "%~dp0software\index.html"
  echo Run 02_CHECK_BRIDGE.cmd after checking the Python installation.
  pause
)
endlocal
