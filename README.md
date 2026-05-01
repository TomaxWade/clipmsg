# ClipMsg

ClipMsg is a tiny local-first message bridge from your phone to your Windows desktop.

The key workflow is simple:

1. Send a text message from your phone.
2. ClipMsg receives it on your desktop.
3. The desktop app immediately copies that message into the Windows clipboard.
4. You can press `Ctrl+V` in any app right away.

That means you do not need to open the desktop browser page and manually copy the message again.

Current public release line: `0.3.x`

## Highlights

- Phone-to-desktop text relay over your reachable local network
- Automatic clipboard copy for incoming phone messages on Windows
- QR pairing flow that opens the phone page and pairs it automatically
- Manual pairing token fallback for cases where scanning is not convenient
- Automatic port selection when the preferred port is already in use
- Local JSON storage outside the repository directory
- Browser-based desktop UI with no cloud relay required

## Quick start from source

### Windows PowerShell

```powershell
./run_clipmsg.ps1
```

### Windows double-click

Double-click:

- `run_clipmsg.cmd`

The launcher:

1. Finds a usable local Python 3 installation.
2. Installs missing dependencies from `requirements.txt` if needed.
3. Starts ClipMsg.
4. Opens the desktop page in your browser.

## Pairing flow

When the desktop page opens, it shows:

- A QR code
- A pairing link
- A manual pairing token

The recommended flow is:

1. Open the desktop page on your PC.
2. Scan the QR code with your phone.
3. The phone browser opens the correct URL automatically.
4. The phone is paired without manually typing the token.

ClipMsg puts the pairing secret in the URL fragment (`#token=...`) instead of the normal query string, so the token is not sent as part of the initial page request.

## Packaging to EXE

Install build dependencies and create a Windows EXE:

```powershell
./build_exe.ps1
```

The generated executable will be placed in:

- `dist/ClipMsg.exe`

The EXE starts the local server and opens the desktop browser page automatically.

## Release ZIP for GitHub

Create the GitHub Release bundle:

```powershell
./build_release.ps1
```

This creates:

- `release/ClipMsg-v0.3.0-windows-x64.zip`

The ZIP contains:

- `ClipMsg.exe`
- `README.txt`
- `LICENSE.txt`

Windows end users only need the EXE release. They do not need Python or a virtual environment.

## Optional desktop shell

If you want a lightweight desktop shell window instead of the normal browser page:

```powershell
python -m pip install -r requirements-desktop.txt
python desktop.py
```

## Security notes

- ClipMsg is designed for trusted, reachable networks such as the same LAN.
- It does not publish your messages to a cloud service.
- Pairing uses a strong random token.
- After pairing, the browser keeps an HTTP-only cookie instead of repeatedly exposing the token to page scripts.
- The desktop-only pairing API is restricted to loopback requests.

For cross-network use, the safer approach is to connect the phone and desktop through a private network overlay such as Tailscale or WireGuard instead of opening ClipMsg directly to the public internet.

## Development notes

- Default message storage is outside the repo, under the first writable user data directory.
- On restrictive Windows machines, ClipMsg may automatically fall back to a writable folder under `TEMP`.
- The repo is intended to be MIT licensed.

## Versioning

ClipMsg uses a lightweight semantic versioning style:

- `0.x.y` while the app is still evolving quickly
- patch (`y`) for fixes and packaging/documentation updates
- minor (`x`) for new features or workflow changes

The current source-of-truth version is stored in `VERSION`, and user-facing changes are recorded in `CHANGELOG.md`.
