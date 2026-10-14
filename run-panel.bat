@echo off
REM Panel de agentes en http://localhost:8020
cd /d "%~dp0"
python -m pip install -q fastapi uvicorn
start http://localhost:8020
python board\server.py
