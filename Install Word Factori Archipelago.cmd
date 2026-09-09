@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Force %*
if errorlevel 1 (
  echo.
  echo Installation did not complete. Review the message above.
  pause
  exit /b 1
)
echo.
echo Word Factori Archipelago is ready. Use a fresh room and an empty mod save.
pause
