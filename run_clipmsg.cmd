@echo off
setlocal
set "ROOT=%~dp0"

title ClipMsg Launcher
cd /d "%ROOT%"

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%ROOT%run_clipmsg.ps1"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo ClipMsg failed to start. Press any key to close this window.
  pause >nul
)

exit /b %EXIT_CODE%
