@echo off
rem Wario World Recomp installer: asks for your GWWE01 (USA, rev 0) ISO and an install folder.
where pythonw >nul 2>nul
if errorlevel 1 (
  echo Python 3.11 or newer is needed to run the installer.
  echo Get it from https://www.python.org/downloads/windows/ and tick "Add python.exe to PATH".
  start "" https://www.python.org/downloads/windows/
  pause
  exit /b 1
)
start "" pythonw "%~dp0installer\wario_installer.pyw" %*
