@echo off
chcp 65001 >nul
echo CAUTION: This opens the UNMODIFIED v1.4.0 BROWSER engine, not experimental v1.4.1 NNLS.
start "" "%~dp0nist_search\runtime\software\index.html"
