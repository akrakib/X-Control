# Third-party notices

XControl bundles the following open-source components. Each remains under its own license.

| Component | Use in XControl | License |
| --- | --- | --- |
| [scrcpy](https://github.com/Genymobile/scrcpy) server v5.0.1 (Genymobile, Romain Vimont) | Runs on the phone to inject fast touch/keyboard input | Apache License 2.0 |
| [Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools) (`adb.exe`, `AdbWinApi.dll`, `AdbWinUsbApi.dll`) | Talks to the phone over USB | Apache License 2.0 (see Android SDK terms) |
| [Qt for Python (PySide6)](https://www.qt.io/qt-for-python) / Qt | User interface | LGPL v3 |
| [PyAV](https://github.com/PyAV-Org/PyAV) with FFmpeg libraries | Decodes the phone's H.264 video | BSD-3-Clause (PyAV), LGPL v2.1+ (FFmpeg) |
| [Python](https://www.python.org/) | Runtime bundled by PyInstaller | PSF License |
| [PyInstaller](https://pyinstaller.org/) bootloader | Packages the exe | GPL v2 with bootloader exception |

## Notes
- Apache 2.0 license text: https://www.apache.org/licenses/LICENSE-2.0
- LGPL v3 text: https://www.gnu.org/licenses/lgpl-3.0.html
- The Qt and FFmpeg libraries are bundled as separate files inside the exe and can be replaced
  by compatible versions. Source for these libraries is available from their upstream projects
  linked above.
- Android is a trademark of Google LLC. XControl is not affiliated with or endorsed by Google or Genymobile.
