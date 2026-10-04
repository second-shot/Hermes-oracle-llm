@echo off
echo [legacy] This helper is Mia. Use check-mia.cmd for new shortcuts.
call "%~dp0check-mia.cmd" %*
exit /b %ERRORLEVEL%
