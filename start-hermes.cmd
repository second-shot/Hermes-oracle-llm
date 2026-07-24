@echo off
setlocal
cd /d "%~dp0"

call scripts\start_local_model.cmd
if errorlevel 1 (
    echo.
    echo Hermes could not prepare its free local model.
    pause
    exit /b 1
)

python scripts\hermes_doctor.py --start
set "HERMES_EXIT=%ERRORLEVEL%"

if not "%HERMES_EXIT%"=="0" (
    echo.
    echo Hermes did not start. Read the [FAIL] lines above.
    pause
)

exit /b %HERMES_EXIT%
