@echo off
cd /d "%~dp0BillNote_frontend"
pnpm.cmd dev >> "%~dp0logs\frontend.log" 2>&1

