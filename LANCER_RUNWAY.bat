@echo off
cd /d "%~dp0"
pythonw runway_gui_v2.pyw
if errorlevel 1 (
  echo.
  echo Python, customtkinter, pillow ou requests manque. Installe:
  echo   pip install -r requirements.txt
  echo puis relance ce fichier.
  pause
)
