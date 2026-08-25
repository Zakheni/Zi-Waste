@echo off
setlocal
cd /d "%~dp0.."
if exist "venv32\Scripts\python.exe" (
    "venv32\Scripts\python.exe" -m app.main
) else (
    python -m app.main
)
