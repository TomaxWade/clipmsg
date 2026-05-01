from __future__ import annotations

import argparse
import threading
import webbrowser

import uvicorn

from runtime_support import build_runtime_info, default_store_path, generate_pairing_token, reserve_listener
from server import AppConfig, create_app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ClipMsg desktop shell wrapper.")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host.")
    parser.add_argument("--port", type=int, default=8765, help="Preferred port.")
    parser.add_argument("--port-search-limit", type=int, default=50, help="How many sequential ports to try.")
    parser.add_argument("--store-path", default=str(default_store_path()), help="Message store path.")
    parser.add_argument("--token", default="", help="Optional pairing token override.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pairing_token = args.token.strip() or generate_pairing_token()
    listener, actual_port = reserve_listener(args.host, args.port, search_limit=args.port_search_limit)
    runtime = build_runtime_info(bind_host=args.host, port=actual_port, token=pairing_token)

    app = create_app(
        config=AppConfig(
            store_path=args.store_path,
            pairing_token=pairing_token,
            runtime=runtime,
        )
    )

    print("")
    print("ClipMsg desktop shell is running.")
    print(f"- Desktop page: {runtime.desktop_url}")
    if runtime.phone_url:
        print(f"- Phone page:   {runtime.phone_url}")
    else:
        print("- Phone page:   unavailable (no reachable local IP was detected)")
    print(f"- Manual token: {pairing_token}")
    print("")

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=args.host,
            port=actual_port,
            log_level="warning",
            access_log=False,
        )
    )

    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()

    try:
        import webview  # type: ignore

        webview.create_window("ClipMsg", runtime.desktop_url, width=1080, height=760)
        webview.start()
    except Exception:
        webbrowser.open_new_tab(runtime.desktop_url)
        thread.join()
        return
    finally:
        server.should_exit = True

    thread.join(timeout=2)


if __name__ == "__main__":
    main()
