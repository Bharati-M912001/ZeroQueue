@echo off
REM Runs the automated test suite (14 tests, all offline).
call conda activate GenAI
pytest test -q
pause
