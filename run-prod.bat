@echo off
cd frontend
if not exist node_modules npm install
call npm run build
cd ..\backend
if not exist .venv py -3.12 -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
