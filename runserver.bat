@echo off
cd /d "%~dp0web"
start "Cliff Horse server" cmd /c "where py >nul 2>nul && py serve.py 8137 || python serve.py 8137"
timeout /t 1 /nobreak >nul
start http://localhost:8137/
