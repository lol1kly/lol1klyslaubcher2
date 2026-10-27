@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_CMD="
where py >nul 2>nul && set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD where python >nul 2>nul && set "PYTHON_CMD=python"
if not defined PYTHON_CMD (
  echo ERROR: Python was not found.
  echo Install Python 3.11 or newer from https://www.python.org/downloads/windows/
  echo During installation, check "Add python.exe to PATH".
  pause
  exit /b 1
)
%PYTHON_CMD% -m pip install -r requirements.txt
if errorlevel 1 pause & exit /b 1
%PYTHON_CMD% main.py
pause
