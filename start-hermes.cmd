@echo off
echo [legacy] This helper is Mia. Use start-mia.cmd for new shortcuts.
call "%~dp0start-mia.cmd" %*
exit /b %ERRORLEVEL%
