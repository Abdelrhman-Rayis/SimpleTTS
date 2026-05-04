"""
SimpleTTS desktop wrapper.

Runs the FastAPI app in a background thread and opens a native window
(WKWebView on macOS, WebView2 on Windows, GTK WebKit on Linux) pointing
at it. Closing the window stops the process — the daemon-thread server
goes down with it.

    python desktop.py
"""
import os
import socket
import sys
import threading
import time

import uvicorn
import webview

# Ensure relative paths in app.py (models/, audio_cache/, index.html)
# resolve correctly even when launched from elsewhere (e.g. Finder).
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)

from app import app  # noqa: E402

WINDOW_TITLE = "SimpleTTS"
WINDOW_W, WINDOW_H = 1280, 820
MIN_W,    MIN_H    = 820,  560


def find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_server(port: int, timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def serve(port: int) -> None:
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def main() -> None:
    port = find_free_port()
    threading.Thread(target=serve, args=(port,), daemon=True).start()

    if not wait_for_server(port):
        print("Server failed to start.", file=sys.stderr)
        sys.exit(1)

    webview.create_window(
        WINDOW_TITLE,
        f"http://127.0.0.1:{port}",
        width=WINDOW_W,
        height=WINDOW_H,
        min_size=(MIN_W, MIN_H),
    )
    webview.start()


if __name__ == "__main__":
    main()
