XControl (by akrakib) - USB diye Android screen Windows-e dekha ar control kora

CHALANO
1. run.bat double-click (prothombar ADB download + library install hobe, internet lagbe).
2. Phone-e: Settings > Developer options > USB debugging ON.
   Xiaomi/Redmi/POCO hole "USB debugging (Security settings)" o ON korte hobe.
3. Cable lagan, phone-e "Allow USB debugging" e OK.

EXE BANANO
build.bat double-click -> dist\XControl.exe (ekta file, Python lage na).
Setup.exe chaile Inno Setup diye installer.iss compile korun.

CONTROL
- Left click/drag = touch (live drag), dhore rakhle long press
- Right click = Back, Middle click = Home, Mouse wheel = scroll
- Keyboard-e type = phone-e text. Bangla/Unicode text-o jay (clipboard paste diye).
- Ctrl+V = PC-r clipboard phone-e paste
- Esc = Back, Enter, Backspace, Arrow key, Tab kaj kore
- Phone-er dan pashe icon button: Back/Home/Recent/Power/Vol+/Vol-/Screenshot (naam dekhte mouse rakhun)

INPUT-ER DUI MODE (niche dan dike dekhabe)
- "Control: FAST mode (scrcpy)" : scrcpy v5.0.1 server phone-e chole, onek druto, live drag.
- Server connect na hole ager moto "adb shell input" (dhire) fallback hishebe kaj kore.

SIMA
- Banking app / secure screen-e screen kalo dekhabe (Android-er rule).
- Phone rotate korle video distort hote pare; portrait-e use korun.
- Video ekhono adb screenrecord diye ashe, tai screen dekhte kichu delay thakbe.

bin\scrcpy-server.jar-er version (5.0.1) client code-er SCRCPY_VERSION-er sathe milte hobe.
