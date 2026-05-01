# ClipMsg

ClipMsg is a tiny local-first bridge that lets you send text from your phone to your Windows desktop.

Its main job is simple:

1. You send a message from your phone.
2. ClipMsg receives it on your PC.
3. The incoming phone message is copied to the Windows clipboard automatically.
4. You can paste it immediately in any app with `Ctrl+V`.

That clipboard-first workflow is the reason this project exists: you do not need to manually copy text from the desktop browser page after it arrives.

Current public release line: `0.3.x`

## Highlights

- Automatic clipboard copy for incoming phone messages on Windows
- QR pairing that opens the phone page and pairs the browser automatically
- Minimal browser UI for both desktop and phone
- Automatic port fallback if the preferred port is already in use
- Local-first design with no cloud relay
- Strong pairing token plus cookie-based session after pairing

## Download

Windows end users do **not** need Python, Conda, or a virtual environment.

Download the latest packaged release from:

- [GitHub Releases](https://github.com/TomaxWade/clipmsg/releases)

For `v0.3.0`, the Windows package is:

- `ClipMsg-v0.3.0-windows-x64.zip`

The ZIP contains:

- `ClipMsg.exe`
- `README.txt`
- `LICENSE.txt`

## Quick Start

1. Download the latest Windows ZIP from the Releases page.
2. Extract the ZIP anywhere you like.
3. Double-click `ClipMsg.exe`.
4. Wait for the desktop page to open in your browser.
5. Scan the QR code with your phone.
6. Send text from your phone.
7. Paste it anywhere on your PC with `Ctrl+V`.

## How Pairing Works

When the desktop page opens, it shows:

- a QR code
- a phone link
- a manual pairing token

The recommended flow is:

1. Open ClipMsg on your Windows PC.
2. Scan the QR code with your phone.
3. Your phone browser opens the correct page automatically.
4. The browser pairs without manually typing the token.

If scanning is inconvenient, you can still open the phone link manually and use the token fallback.

## Network Model

ClipMsg is designed for trusted, reachable networks.

Recommended setups:

- the same local network / Wi-Fi
- a private network overlay such as Tailscale or WireGuard

ClipMsg is **not** intended to be exposed directly to the public internet.

## Security Notes

- Pairing uses a strong random token
- The pairing token is placed in the URL fragment (`#token=...`) instead of the normal query string
- After pairing, the browser keeps an HTTP-only cookie session
- The desktop-only pairing API is restricted to loopback requests
- Messages stay local to your own ClipMsg server; the app does not depend on a cloud relay

## Build From Source

If you want to run the project from source:

```powershell
./run_clipmsg.ps1
```

The launcher will:

1. Find a usable local Python 3 installation
2. Install missing dependencies from `requirements.txt` if needed
3. Start ClipMsg
4. Open the desktop page in your browser

## Build a Windows Release

To build the standalone EXE:

```powershell
./build_exe.ps1
```

To build the GitHub Release ZIP bundle:

```powershell
./build_release.ps1
```

This creates:

- `release/ClipMsg-v0.3.0-windows-x64.zip`

## Optional Desktop Shell

If you prefer a lightweight desktop shell window instead of the normal browser page:

```powershell
python -m pip install -r requirements-desktop.txt
python desktop.py
```

## Project Notes

- Default message storage is outside the repository directory
- On restrictive Windows machines, ClipMsg may fall back to a writable folder under `TEMP`
- The project is MIT licensed

## Versioning

ClipMsg currently follows a lightweight `0.x.y` versioning style:

- patch (`y`) for fixes and packaging/documentation updates
- minor (`x`) for new features or workflow changes

The current source-of-truth version is stored in `VERSION`, and user-facing changes are recorded in `CHANGELOG.md`.
