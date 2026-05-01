from __future__ import annotations

import subprocess
import sys
import time


def is_windows() -> bool:
    return sys.platform == "win32"


def _set_clipboard_text_via_powershell(text: str) -> bool:
    if not text or not is_windows():
        return False

    command = (
        "[Console]::InputEncoding=[System.Text.UTF8Encoding]::new($false); "
        "$text=[Console]::In.ReadToEnd(); "
        "Set-Clipboard -Value $text"
    )
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-STA", "-Command", command],
            input=text,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=5,
            creationflags=creationflags,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False

    return completed.returncode == 0


def set_clipboard_text(text: str, *, retries: int = 8, delay_s: float = 0.05) -> bool:
    if not text:
        return False
    if not is_windows():
        return False

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    OpenClipboard = user32.OpenClipboard
    OpenClipboard.argtypes = [wintypes.HWND]
    OpenClipboard.restype = wintypes.BOOL

    CloseClipboard = user32.CloseClipboard
    CloseClipboard.argtypes = []
    CloseClipboard.restype = wintypes.BOOL

    EmptyClipboard = user32.EmptyClipboard
    EmptyClipboard.argtypes = []
    EmptyClipboard.restype = wintypes.BOOL

    SetClipboardData = user32.SetClipboardData
    SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    SetClipboardData.restype = wintypes.HANDLE

    GlobalAlloc = kernel32.GlobalAlloc
    GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    GlobalAlloc.restype = wintypes.HGLOBAL

    GlobalLock = kernel32.GlobalLock
    GlobalLock.argtypes = [wintypes.HGLOBAL]
    GlobalLock.restype = wintypes.LPVOID

    GlobalUnlock = kernel32.GlobalUnlock
    GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    GlobalUnlock.restype = wintypes.BOOL

    GlobalFree = kernel32.GlobalFree
    GlobalFree.argtypes = [wintypes.HGLOBAL]
    GlobalFree.restype = wintypes.HGLOBAL

    GetConsoleWindow = kernel32.GetConsoleWindow
    GetConsoleWindow.argtypes = []
    GetConsoleWindow.restype = wintypes.HWND

    GetModuleHandleW = kernel32.GetModuleHandleW
    GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    GetModuleHandleW.restype = wintypes.HMODULE

    CreateWindowExW = user32.CreateWindowExW
    CreateWindowExW.argtypes = [
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        wintypes.HMENU,
        wintypes.HINSTANCE,
        wintypes.LPVOID,
    ]
    CreateWindowExW.restype = wintypes.HWND

    DestroyWindow = user32.DestroyWindow
    DestroyWindow.argtypes = [wintypes.HWND]
    DestroyWindow.restype = wintypes.BOOL

    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    # Windows clipboard expects CRLF for newlines in CF_UNICODETEXT.
    win_text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    buf_size = (len(win_text) + 1) * ctypes.sizeof(ctypes.c_wchar)

    api_copy_ok = False
    fallback_result = False
    temp_owner_hwnd = None
    owner_hwnd = GetConsoleWindow()
    if not owner_hwnd:
        temp_owner_hwnd = CreateWindowExW(
            0,
            "STATIC",
            "ClipMsgClipboardOwner",
            0,
            0,
            0,
            0,
            0,
            None,
            None,
            GetModuleHandleW(None),
            None,
        )
        owner_hwnd = temp_owner_hwnd

    if not owner_hwnd:
        return _set_clipboard_text_via_powershell(text)

    for _ in range(max(1, retries)):
        if OpenClipboard(owner_hwnd):
            break
        time.sleep(delay_s)
    else:
        return _set_clipboard_text_via_powershell(text)

    h_mem = None
    try:
        h_mem = GlobalAlloc(GMEM_MOVEABLE, buf_size)
        if not h_mem:
            fallback_result = _set_clipboard_text_via_powershell(text)
            return fallback_result

        locked = GlobalLock(h_mem)
        if not locked:
            fallback_result = _set_clipboard_text_via_powershell(text)
            return fallback_result

        ctypes.memmove(locked, ctypes.c_wchar_p(win_text), buf_size)
        GlobalUnlock(h_mem)

        if not EmptyClipboard():
            fallback_result = _set_clipboard_text_via_powershell(text)
            return fallback_result

        if not SetClipboardData(CF_UNICODETEXT, h_mem):
            fallback_result = _set_clipboard_text_via_powershell(text)
            return fallback_result

        # Clipboard takes ownership of h_mem on success.
        h_mem = None
        api_copy_ok = True
        return True
    finally:
        CloseClipboard()
        if h_mem:
            GlobalFree(h_mem)
        if temp_owner_hwnd:
            DestroyWindow(temp_owner_hwnd)
        if not api_copy_ok and not fallback_result:
            _set_clipboard_text_via_powershell(text)
