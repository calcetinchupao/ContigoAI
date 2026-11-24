@echo off
cd /d "%~dp0"
echo ContigoAI EP3 - Iniciando en http://127.0.0.1:8000
echo Monitoreo: http://127.0.0.1:8000/observabilidad
python -m uvicorn src.api:app --host 127.0.0.1 --port 8000 --no-access-log
if errorlevel 1 (
  echo No se pudo iniciar. Revisa README.md y ejecuta python -m pip install -r requirements.txt
  pause
)
