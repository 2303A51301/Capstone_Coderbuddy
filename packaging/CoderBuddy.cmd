@echo off
cd /d "%~dp0"
"%~dp0runtime\python.exe" "%~dp0launch.py"
if errorlevel 1 (
  echo CoderBuddy could not start. See the error above.
  pause
)
