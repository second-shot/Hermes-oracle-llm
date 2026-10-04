@echo off
call "%~dp0start-mia.cmd" --doctor
exit /b %ERRORLEVEL%
