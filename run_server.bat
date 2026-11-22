@echo off
cd /d "%~dp0"
set PY=python
if exist "venv\Scripts\python.exe" set PY=venv\Scripts\python.exe
if "%PY%"=="python" if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe
if "%PY%"=="python" if exist "C:\Haircare\hair_care_advisor\venv\Scripts\python.exe" set PY=C:\Haircare\hair_care_advisor\venv\Scripts\python.exe
echo Using Python: %PY%
if not exist "checkpoints\balding_model.pt" echo WARNING: checkpoints\balding_model.pt is missing
if not exist "checkpoints\scalp_model.pt" echo WARNING: checkpoints\scalp_model.pt is missing
"%PY%" -m uvicorn service.main:app --host 127.0.0.1 --port 8000
pause
