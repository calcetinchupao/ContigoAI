@echo off
cd /d "%~dp0"
python pruebas\run_evidencia_ep3.py --sin-llm
if errorlevel 1 (
  echo La evaluacion encontro un error de ejecucion. Revisa la salida anterior.
  pause
  exit /b 1
)
echo Evaluacion guardada. Abre INICIAR_EP3.bat y entra a /observabilidad.
pause
