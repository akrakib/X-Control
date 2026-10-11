@echo off
cd /d "%~dp0"
call setup_adb.bat
if not exist venv (
  python -m venv venv
  call venv\Scripts\activate.bat
  pip install PySide6 av
) else (
  call venv\Scripts\activate.bat
)
python xcontrol.py
