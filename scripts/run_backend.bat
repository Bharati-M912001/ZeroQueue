@echo off
REM Starts the ZeroQueue API on http://localhost:8000 (keep this terminal open).
REM IMPORTANT: --reload watches ONLY the app\ and models\ source folders.
REM Without this, uvicorn watches the WHOLE project - and every customer
REM message writes zeroqueue.db and uploads\, which makes the server restart
REM ITSELF mid-reply and the answer is silently never sent.
call conda activate GenAI
uvicorn app.main:app --reload --reload-dir app --reload-dir models --port 8000
