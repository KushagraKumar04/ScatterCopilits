@echo off
start "BPMN backend" cmd /k "cd backend && if not exist .venv py -3.14 -m venv .venv && call .venv\Scripts\activate && pip install -r requirements.txt && python -m uvicorn app.main:app --reload --port 8000"
start "BPMN frontend" cmd /k "cd frontend && if not exist node_modules npm install && npm run dev"
