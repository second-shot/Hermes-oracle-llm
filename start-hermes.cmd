@echo off
setlocal
cd /d "%~dp0"

python scripts\hermes_doctor.py --start
set "HERMES_EXIT=%ERRORLEVEL%"

if not "%HERMES_EXIT%"=="0" (
    echo.
    echo Hermes did not start. Read the [FAIL] lines above.
    pause
)

exit /b %HERMES_EXIT%
