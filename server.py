from __future__ import annotations

import argparse
import asyncio
import io
import secrets
import socket
import webbrowser
from dataclasses import dataclass
from typing import Any

import qrcode
import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from qrcode.image.svg import SvgImage

from clipboard_win import set_clipboard_text
from runtime_support import (
    RuntimeInfo,
    build_runtime_info,
    default_store_path,
    generate_pairing_token,
    get_app_version,
    reserve_listener,
    resource_path,
)
from storage import init_db, insert_message, list_messages


AUTH_COOKIE = "clipmsg_auth"
APP_VERSION = get_app_version()


def is_loopback(host: str | None) -> bool:
    return host in {"127.0.0.1", "::1", "localhost"}


@dataclass(frozen=True)
class AppConfig:
    store_path: str
    pairing_token: str
    runtime: RuntimeInfo


class PairRequest(BaseModel):
    token: str = Field(min_length=8, max_length=256)


class MessageIn(BaseModel):
    sender: str = Field(min_length=1, max_length=32)
    text: str = Field(min_length=1, max_length=4000)


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        async with self._lock:
            clients = list(self._clients)
        for ws in clients:
            try:
                await ws.send_json(payload)
            except Exception:
                await self.disconnect(ws)


def _make_qr_svg(text: str) -> str:
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        border=2,
        box_size=10,
    )
    qr.add_data(text)
    qr.make(fit=True)

    image = qr.make_image(image_factory=SvgImage)
    buffer = io.BytesIO()
    image.save(buffer)
    return buffer.getvalue().decode("utf-8")


def _is_pairing_token_valid(candidate: str | None, *, expected: str) -> bool:
    return bool(candidate) and secrets.compare_digest(candidate, expected)


def _has_auth_cookie(token: str | None, *, expected: str) -> bool:
    return _is_pairing_token_valid(token, expected=expected)


def _require_auth_request(request: Request, *, expected: str) -> None:
    if not _has_auth_cookie(request.cookies.get(AUTH_COOKIE), expected=expected):
        raise HTTPException(status_code=401, detail="This device is not paired yet.")


def _require_auth_websocket(ws: WebSocket, *, expected: str) -> None:
    if not _has_auth_cookie(ws.cookies.get(AUTH_COOKIE), expected=expected):
        raise HTTPException(status_code=401, detail="This device is not paired yet.")


def _require_loopback(request: Request) -> None:
    client_host = request.client.host if request.client else None
    if not is_loopback(client_host):
        raise HTTPException(status_code=403, detail="This endpoint is only available from the local desktop.")


def create_app(*, config: AppConfig) -> FastAPI:
    init_db(config.store_path)

    app = FastAPI(title="ClipMsg", version=APP_VERSION)
    manager = ConnectionManager()

    web_dir = resource_path("web")
    index_html = web_dir / "index.html"

    @app.get("/api/health")
    async def api_health() -> dict[str, Any]:
        return {
            "ok": True,
            "version": APP_VERSION,
            "desktop_url": config.runtime.desktop_url,
            "phone_url": config.runtime.phone_url,
            "port": config.runtime.port,
        }

    @app.get("/api/session")
    async def api_session(request: Request) -> dict[str, bool]:
        _require_auth_request(request, expected=config.pairing_token)
        return {"paired": True}

    @app.post("/api/pair")
    async def api_pair(payload: PairRequest) -> JSONResponse:
        if not _is_pairing_token_valid(payload.token.strip(), expected=config.pairing_token):
            raise HTTPException(status_code=401, detail="Invalid pairing token.")

        response = JSONResponse({"ok": True, "paired": True})
        response.set_cookie(
            AUTH_COOKIE,
            config.pairing_token,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 30,
        )
        return response

    @app.post("/api/unpair")
    async def api_unpair() -> JSONResponse:
        response = JSONResponse({"ok": True})
        response.delete_cookie(AUTH_COOKIE)
        return response

    @app.get("/api/pairing")
    async def api_pairing(request: Request) -> dict[str, Any]:
        _require_loopback(request)
        return {
            "token": config.pairing_token,
            "desktop_url": config.runtime.desktop_url,
            "phone_url": config.runtime.phone_url,
            "pair_url": config.runtime.pair_url,
            "port": config.runtime.port,
        }

    @app.get("/api/pairing-qr.svg")
    async def api_pairing_qr(request: Request) -> Response:
        _require_loopback(request)
        if not config.runtime.pair_url:
            raise HTTPException(status_code=404, detail="No reachable phone URL is available on this machine.")
        return Response(_make_qr_svg(config.runtime.pair_url), media_type="image/svg+xml")

    @app.get("/api/messages")
    async def api_list_messages(request: Request, limit: int = 200) -> dict[str, Any]:
        _require_auth_request(request, expected=config.pairing_token)
        return {"messages": list_messages(config.store_path, limit=limit)}

    @app.post("/api/messages")
    async def api_post_message(request: Request, msg: MessageIn) -> dict[str, Any]:
        _require_auth_request(request, expected=config.pairing_token)

        sender = msg.sender.strip()[:32]
        text = msg.text.strip()
        if not text:
            raise HTTPException(status_code=422, detail="Empty message.")

        stored = insert_message(config.store_path, sender=sender, text=text)

        copied = False
        if sender == "phone":
            copied = set_clipboard_text(text)

        await manager.broadcast({"type": "message", "message": stored, "copied": copied})
        return {"ok": True, "message": stored, "copied": copied}

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket) -> None:
        try:
            _require_auth_websocket(ws, expected=config.pairing_token)
        except HTTPException:
            await ws.close(code=1008)
            return

        await manager.connect(ws)
        try:
            history = list_messages(config.store_path, limit=200)
            await ws.send_json({"type": "history", "messages": history})
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            await manager.disconnect(ws)

    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")

    @app.get("/{path:path}")
    async def spa_fallback(path: str) -> FileResponse:
        return FileResponse(str(index_html))

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ClipMsg: phone-to-desktop messages with automatic Windows clipboard copy."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {APP_VERSION}")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host.")
    parser.add_argument("--port", type=int, default=8765, help="Preferred port. ClipMsg auto-falls forward if busy.")
    parser.add_argument("--port-search-limit", type=int, default=50, help="How many sequential ports to try.")
    parser.add_argument("--store-path", default=str(default_store_path()), help="Message store path.")
    parser.add_argument("--token", default="", help="Optional pairing token override.")
    parser.add_argument("--no-open", action="store_true", help="Do not open the desktop page automatically.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pairing_token = args.token.strip() or generate_pairing_token()

    listener, actual_port = reserve_listener(args.host, args.port, search_limit=args.port_search_limit)
    runtime = build_runtime_info(bind_host=args.host, port=actual_port, token=pairing_token)

    config = AppConfig(
        store_path=args.store_path,
        pairing_token=pairing_token,
        runtime=runtime,
    )
    app = create_app(config=config)

    print("")
    print(f"ClipMsg v{APP_VERSION} is running.")
    print(f"- Desktop page: {runtime.desktop_url}")
    if runtime.phone_url:
        print(f"- Phone page:   {runtime.phone_url}")
    else:
        print("- Phone page:   unavailable (no reachable local IP was detected)")
    print(f"- Manual token: {pairing_token}")
    print(f"- Store path:   {config.store_path}")
    print("- Incoming phone messages are copied to the Windows clipboard automatically.")
    print("")

    if not args.no_open:
        try:
            webbrowser.open_new_tab(runtime.desktop_url)
        except OSError:
            pass

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=args.host,
            port=actual_port,
            log_level="warning",
            access_log=False,
        )
    )
    server.run(sockets=[listener])


if __name__ == "__main__":
    main()
