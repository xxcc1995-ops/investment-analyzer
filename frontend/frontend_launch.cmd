@echo off
cd /d "D:\investment-analyzer\frontend"
set VITE_API_TARGET=http://localhost:8022
"C:\Program Files\nodejs\node.exe" node_modules\vite\bin\vite.js --port 5180 --host 127.0.0.1 > start_frontend.log 2>&1
