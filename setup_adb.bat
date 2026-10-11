@echo off
cd /d "%~dp0"
if exist bin\adb.exe goto done
echo ADB (platform-tools) download hocche...
powershell -NoProfile -Command "Invoke-WebRequest https://dl.google.com/android/repository/platform-tools-latest-windows.zip -OutFile pt.zip; Expand-Archive pt.zip -DestinationPath pt_tmp -Force"
if not exist pt_tmp\platform-tools\adb.exe goto fail
mkdir bin 2>nul
copy /y pt_tmp\platform-tools\adb.exe bin\ >nul
copy /y pt_tmp\platform-tools\AdbWinApi.dll bin\ >nul
copy /y pt_tmp\platform-tools\AdbWinUsbApi.dll bin\ >nul
rmdir /s /q pt_tmp
del pt.zip
:done
exit /b 0
:fail
echo ADB download hoyni. Internet check korun.
pause
exit /b 1
