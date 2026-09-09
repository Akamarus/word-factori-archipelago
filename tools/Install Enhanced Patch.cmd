@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_enhanced.ps1" %*
if errorlevel 1 (
  echo Enhanced installation did not complete. Review the message above.
  pause
  exit /b 1
)
pause
