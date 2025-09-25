@echo off
REM ---------- 1. Activar entorno virtual ----------
call venv\Scripts\activate

REM ---------- 2. Ejecutar servidor ----------
start python app.py

REM ---------- 3. Abrir navegador ----------
timeout /t 3 /nobreak >nul
start http://127.0.0.1:5000

REM ---------- 4. Mantener ventana abierta ----------
pause

