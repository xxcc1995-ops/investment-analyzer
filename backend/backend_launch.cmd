@echo off
cd /d "D:\investment-analyzer\backend"
call venv\Scripts\activate.bat
venv\Scripts\python.exe -m uvicorn app.main:app --port 8022 --no-use-colors > start_backend.log 2>&1
