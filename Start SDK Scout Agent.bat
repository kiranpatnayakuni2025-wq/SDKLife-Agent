@echo off
setlocal
cd /d "%~dp0"
title SDK Scout Agent

set PY=
where py >nul 2>&1 && set PY=py -3
if "%PY%"=="" where python >nul 2>&1 && set PY=python
if "%PY%"=="" (
  echo.
  echo Python is not installed on this computer.
  echo 1. Open https://www.python.org/downloads/ and install Python.
  echo 2. IMPORTANT: tick "Add python.exe to PATH" on the first install screen.
  echo 3. Double-click this file again.
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo First start: setting things up. This takes a few minutes, only once...
  %PY% -m venv .venv
  if errorlevel 1 ( echo Setup failed. & pause & exit /b 1 )
)

echo Checking required parts...
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
if errorlevel 1 ( echo Could not install required parts. Check your internet and try again. & pause & exit /b 1 )

echo.
echo Starting SDK Scout Agent. Your browser will open. Keep this window open while you use it.
echo.
".venv\Scripts\python.exe" -m streamlit run app.py --browser.gatherUsageStats false
pause
