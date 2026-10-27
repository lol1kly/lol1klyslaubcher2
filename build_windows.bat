\
@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher "py" was not found.
  echo If you do not want to install Python locally, use BUILD_WITHOUT_PYTHON_RU.md
  echo to build the EXE in GitHub Actions instead.
  pause
  exit /b 1
)
py -3 -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed.
  pause
  exit /b 1
)
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name BlockLaunch main.py
if errorlevel 1 (
  echo EXE build failed.
  pause
  exit /b 1
)
if not exist "dist\BlockLaunch.exe" (
  echo Build command finished but dist\BlockLaunch.exe was not created.
  pause
  exit /b 1
)
echo Build successful: dist\BlockLaunch.exe
pause
