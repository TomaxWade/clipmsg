from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any


_LOCK = threading.Lock()


def _default_payload() -> dict[str, Any]:
    return {"next_id": 1, "messages": []}


def _read_payload(store_path: str) -> dict[str, Any]:
    path = Path(store_path)
    if not path.exists():
        return _default_payload()

    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return _default_payload()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _default_payload()

    if not isinstance(data, dict):
        return _default_payload()

    messages = data.get("messages")
    next_id = data.get("next_id")
    if not isinstance(messages, list) or not isinstance(next_id, int):
        return _default_payload()

    return {"next_id": next_id, "messages": messages}


def _write_payload(store_path: str, payload: dict[str, Any]) -> None:
    path = Path(store_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def init_db(store_path: str) -> None:
    with _LOCK:
        payload = _read_payload(store_path)
        _write_payload(store_path, payload)


def insert_message(store_path: str, *, sender: str, text: str) -> dict[str, Any]:
    ts = int(time.time() * 1000)
    with _LOCK:
        payload = _read_payload(store_path)
        msg_id = int(payload["next_id"])
        message = {"id": msg_id, "ts": ts, "sender": sender, "text": text}
        payload["messages"].append(message)
        payload["next_id"] = msg_id + 1
        _write_payload(store_path, payload)
    return message


def list_messages(store_path: str, *, limit: int = 200) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 1000))
    with _LOCK:
        payload = _read_payload(store_path)
        messages = payload["messages"][-safe_limit:]
    return [dict(item) for item in messages]
