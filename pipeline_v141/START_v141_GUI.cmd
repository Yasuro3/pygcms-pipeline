@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
py -3 app_v141.py
if errorlevel 1 (
  echo The GUI could not be launched. Install Python 3.10+ and run 00_INSTALL_DEPENDENCIES.cmd.
  pause
)
