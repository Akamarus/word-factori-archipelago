@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install_enhanced.ps1" -Restore %*
if errorlevel 1 (
  echo.
  echo Restore did not complete. Review the message above.
  pause
  exit /b 1
)
echo.
echo Original game restored. Your mod, saves, and original backup were kept.
pause
