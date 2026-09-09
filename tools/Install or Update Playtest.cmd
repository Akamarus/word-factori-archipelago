@echo off
setlocal
tasklist /FI "IMAGENAME eq word factori.exe" /NH | find /I "word factori.exe" >nul
if not errorlevel 1 (
  echo Close Word Factori and its client before installing this playtest.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Force
if errorlevel 1 (
  echo Installation did not complete. Review the message above.
  pause
  exit /b 1
)
echo Now run enhanced\Install Enhanced Patch.cmd and follow START HERE.md.
pause
