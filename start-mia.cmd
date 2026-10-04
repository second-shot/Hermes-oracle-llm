@echo off
setlocal
cd /d "%~dp0"
if not defined HERMES_PYTHON set "HERMES_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%HERMES_PYTHON%" (
  echo [FAIL] Mia Python environment missing. Set HERMES_PYTHON to a Python with requirements.txt installed.
  exit /b 1
)
if not defined HERMES_DATA_DIR set "HERMES_DATA_DIR=%LOCALAPPDATA%\HermesOracle"
set "PYTHONDONTWRITEBYTECODE=1"
"%HERMES_PYTHON%" scripts\operator.py %*
exit /b %ERRORLEVEL%
