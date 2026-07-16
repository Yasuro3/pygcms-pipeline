@echo off
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R /C:":18789 .*LISTENING"') do taskkill /PID %%a /F
pause
