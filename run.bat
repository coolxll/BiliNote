@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo uv environment not found: .venv\Scripts\python.exe
    exit /b 1
)

if not exist "logs" mkdir "logs"
start "" /b "%~dp0backend-start.bat"
start "" /b "%~dp0frontend-start.bat"
timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:3015/

