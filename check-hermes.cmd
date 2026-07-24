@echo off
setlocal
cd /d "%~dp0"

python scripts\hermes_doctor.py
set "HERMES_EXIT=%ERRORLEVEL%"

echo.
pause
exit /b %HERMES_EXIT%
