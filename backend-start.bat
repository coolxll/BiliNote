@echo off
cd /d "%~dp0backend"
"%~dp0.venv\Scripts\python.exe" main.py >> "%~dp0logs\backend.log" 2>&1

