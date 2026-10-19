@echo off
rem Starts High Table Holdings v5 without a console window (falls back to python).
cd /d "%~dp0"
where pythonw >nul 2>nul && (start "" pythonw run.py & exit /b)
python run.py
