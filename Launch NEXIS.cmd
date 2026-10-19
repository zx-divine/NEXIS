@echo off
setlocal
cd /d "%~dp0"
if exist "dist\NEXIS\NEXIS.exe" (
    start "" "%~dp0dist\NEXIS\NEXIS.exe"
    exit /b
)
if exist ".venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0scripts\entry.py"
    exit /b
)
echo Build dist/NEXIS or create the .venv environment described in README.md first.
pause
