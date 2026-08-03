@echo off
setlocal

rem LM_API_TOKEN is a legacy remote-link token. Never pass a stale user value
rem into the local LM Studio daemon; local loopback mode does not require it.
set "LM_API_TOKEN="

set "HERMES_MODEL=qwen/qwen3.5-4b"
set "HERMES_MODEL_DOWNLOAD=qwen/qwen3.5-4b@q4_k_m"
set "HERMES_MODEL_ID=hermes-free"

where lms >nul 2>&1
if errorlevel 1 (
    echo [FAIL] LM Studio CLI was not found.
    echo        Open LM Studio once, then run this file again.
    exit /b 1
)

lms daemon up >nul 2>&1

lms ps | findstr /I /C:"%HERMES_MODEL_ID%" >nul 2>&1
if not errorlevel 1 goto ensure_server

lms ls | findstr /I /C:"qwen3.5-4b" >nul 2>&1
if errorlevel 1 (
    echo [INFO] First run: downloading Qwen3.5-4B Q4_K_M. This is free and local.
    lms get "%HERMES_MODEL_DOWNLOAD%" --gguf
    if errorlevel 1 (
        echo [FAIL] The free model download did not complete.
        exit /b 1
    )
)

echo [INFO] Loading %HERMES_MODEL_ID% with an 8192-token context.
lms unload --all >nul 2>&1
lms load "%HERMES_MODEL%" --context-length 8192 --identifier "%HERMES_MODEL_ID%"
if errorlevel 1 (
    echo [FAIL] LM Studio could not load Qwen3.5-4B.
    echo        Open LM Studio and check the model runtime, then retry.
    exit /b 1
)

:ensure_server
lms server start >nul 2>&1
echo [OK] Free local model ready: %HERMES_MODEL_ID%
exit /b 0
