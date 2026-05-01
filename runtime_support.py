from __future__ import annotations

import os
import secrets
import socket
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote


APP_NAME = "ClipMsg"
DEFAULT_VERSION = "0.3.0"


@dataclass(frozen=True)
class RuntimeInfo:
    bind_host: str
    port: int
    desktop_url: str
    phone_url: str | None
    pair_url: str | None
    lan_ip: str | None


def resource_path(*parts: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_dir = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base_dir = Path(__file__).resolve().parent
    return base_dir.joinpath(*parts)


def get_app_version() -> str:
    candidates = [
        resource_path("VERSION"),
        Path(__file__).resolve().parent / "VERSION",
    ]

    for candidate in candidates:
        try:
            version = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue

        if version:
            return version

    return DEFAULT_VERSION


def default_data_dir() -> Path:
    candidates: list[Path] = []

    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        temp_root = Path(os.environ.get("TEMP", root / "Temp"))
        candidates.extend(
            [
                root / APP_NAME,
                temp_root / APP_NAME,
                temp_root / f"{APP_NAME}Data",
                Path.home() / f"{APP_NAME}Data",
            ]
        )
    elif sys.platform == "darwin":
        candidates.extend(
            [
                Path.home() / "Library" / "Application Support" / APP_NAME,
                Path.home() / "Documents" / APP_NAME,
            ]
        )
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        candidates.extend(
            [
                root / APP_NAME,
                Path.home() / f".{APP_NAME.lower()}",
            ]
        )

    candidates.append(Path.cwd() / ".clipmsg-runtime")

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return candidate
        except OSError:
            continue

    raise OSError("ClipMsg could not find a writable data directory.")


def default_store_path() -> Path:
    return default_data_dir() / "messages.json"


def generate_pairing_token() -> str:
    return secrets.token_urlsafe(24)


def guess_lan_ipv4() -> str | None:
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("1.1.1.1", 80))
            ip = probe.getsockname()[0]
        finally:
            probe.close()
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass

    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET, socket.SOCK_STREAM)
    except OSError:
        return None

    for info in infos:
        ip = info[4][0]
        if ip and not ip.startswith("127."):
            return ip
    return None


def reserve_listener(host: str, preferred_port: int, search_limit: int = 50) -> tuple[socket.socket, int]:
    if preferred_port < 0:
        raise ValueError("preferred_port must be >= 0")
    if search_limit < 1:
        raise ValueError("search_limit must be >= 1")

    candidates = [0] if preferred_port == 0 else [preferred_port + offset for offset in range(search_limit)]
    last_error: OSError | None = None

    for candidate in candidates:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if sys.platform == "win32" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind((host, candidate))
            listener.listen(2048)
            return listener, int(listener.getsockname()[1])
        except OSError as exc:
            last_error = exc
            listener.close()

    message = f"Could not bind any port starting from {preferred_port}."
    raise OSError(message) from last_error


def build_runtime_info(*, bind_host: str, port: int, token: str) -> RuntimeInfo:
    lan_ip = guess_lan_ipv4()
    desktop_url = f"http://127.0.0.1:{port}/pc"
    phone_url = f"http://{lan_ip}:{port}/phone" if lan_ip else None
    pair_url = f"{phone_url}#token={quote(token, safe='')}" if phone_url else None
    return RuntimeInfo(
        bind_host=bind_host,
        port=port,
        desktop_url=desktop_url,
        phone_url=phone_url,
        pair_url=pair_url,
        lan_ip=lan_ip,
    )
