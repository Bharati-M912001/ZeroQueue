@echo off
REM ZeroQueue one-time setup. Double-click or run from the repo root.
REM Creates the .env, installs Python packages into the GenAI conda env,
REM and installs the web page packages.
if not exist .env (
  copy .env.example .env
  echo Created .env from .env.example - fill in keys later, mock mode works without them.
)
call conda activate GenAI
pip install -r requirements.txt
cd src\web
call npm install
cd ..\..
echo.
echo Setup done. Next: scripts\run_backend.bat in one terminal, scripts\run_web.bat in another.
pause
