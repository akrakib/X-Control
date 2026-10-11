<p align="center">
  <img src="icon.png" width="110" alt="XControl icon">
</p>

<h1 align="center">XControl</h1>

<p align="center">
  See and control your Android phone from Windows over USB.<br>
  Mouse, keyboard, clipboard and a floating icon bar. No root, nothing to install on the phone.
</p>

<p align="center">
  <a href="../../releases/latest"><b>Download for Windows</b></a>
  &nbsp;·&nbsp;
  <a href="https://akrakib.pages.dev/">akrakib.pages.dev</a>
</p>

---

## Features

- **Live phone screen** on your PC, resizable window.
- **Fast touch input.** A small scrcpy server runs on the phone, so taps and drags are live (no `adb input` lag). If it can't connect, XControl falls back to the slower `adb shell input` automatically.
- **Mouse = touch.** Left click and drag to tap, swipe or long press.
- **Keyboard = phone keyboard.** Type on your PC and the text goes to the phone. Bangla and other Unicode text works too (sent via clipboard paste).
- **Floating icon bar** next to the window: Back, Home, Recent apps, Power, Volume +/-, Screenshot. Hide or show it with the small handle, and hide the status bar if you want a cleaner window.
- **Screenshots** saved to `Pictures\XControl`.
- **Single exe.** No Python, no ADB install. Everything is bundled.

## Controls

| Action | Result on the phone |
| --- | --- |
| Left click / drag | Tap / swipe (hold = long press) |
| Right click | Back |
| Middle click | Home |
| Mouse wheel | Scroll |
| Typing | Text input |
| `Ctrl+V` | Paste your PC clipboard into the phone |
| `Esc` | Back |
| `Enter`, `Backspace`, `Delete`, arrows, `Tab` | Same keys on the phone |

## Getting started

1. Download `XControl.exe` from the [latest release](../../releases/latest).
2. On the phone: **Settings > About phone**, tap *Build number* 7 times, then enable **Developer options > USB debugging**.
   - Xiaomi / Redmi / POCO: also turn on **USB debugging (Security settings)**.
3. Connect the phone with a USB cable and tap **Allow USB debugging** on the phone.
4. Run `XControl.exe`. The status bar at the bottom shows `Control: FAST mode (scrcpy)` when fast input is active.

## Requirements

- Windows 10 or 11 (64-bit)
- Android phone with USB debugging enabled
- A USB cable that carries data (not charge-only)

## Known limits

- Banking apps and other secure screens show black (Android blocks screen capture there).
- Rotating the phone can distort the video for a moment. Portrait mode works best.
- Video comes from `adb screenrecord`, so there is a small display delay. Input itself is fast.
- Windows SmartScreen may warn about an unsigned app the first time. Choose **More info > Run anyway** if you trust the download.

## Source code

XControl is free to use, but the source code is not published. See [LICENSE.txt](LICENSE.txt).
Third-party components and their licenses are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Feedback

Found a bug or have an idea? Open an [issue](../../issues) and include your phone model, Android version and what the status bar says.

---

Made by [**akrakib**](https://akrakib.pages.dev/)
