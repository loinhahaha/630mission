@echo off
setlocal

start "backend" cmd /k "cd /d %~dp0govdoc_checker\backend && call .venv\Scripts\activate && uvicorn main:app --reload --port 8000"

start "frontend" cmd /k "cd /d %~dp0govdoc_checker\frontend && npm run dev"