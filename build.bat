@echo off
cd /d "%~dp0"
echo === XControl build ===

where python >nul 2>nul
if errorlevel 1 goto nopython

call setup_adb.bat

if not exist venv python -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 goto piperr

pyinstaller --noconfirm --onefile --windowed --name XControl --icon xcontrol.ico --collect-all av ^
  --add-binary "bin\adb.exe;bin" ^
  --add-data "bin\scrcpy-server.jar;bin" ^
  --add-binary "bin\AdbWinApi.dll;bin" ^
  --add-binary "bin\AdbWinUsbApi.dll;bin" ^
  xcontrol.py
if errorlevel 1 goto builderr

echo.
echo Shesh! File ta: dist\XControl.exe
pause
exit /b 0

:nopython
echo Python paoa jayni. https://www.python.org theke install korun (Add to PATH tick diye), tarpor abar chalan.
pause
exit /b 1
:noadb
echo ADB download hoyni. Internet check korun, ba platform-tools manually download kore bin\ folder-e adb.exe, AdbWinApi.dll, AdbWinUsbApi.dll rakhun.
pause
exit /b 1
:piperr
echo pip install fail korse.
pause
exit /b 1
:builderr
echo Build fail korse.
pause
exit /b 1
