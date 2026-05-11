"""Spotify auth — PKCE flow with local callback server. No setup required."""

from __future__ import annotations

import http.server
import threading
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import spotipy
from spotipy.oauth2 import SpotifyPKCE

# Public client_id — safe to commit (PKCE needs no secret).
_CLIENT_ID = "0d9f756568b748339c35d3a09110ec21"
_REDIRECT_URI = "http://127.0.0.1:8888/callback"
_PORT = 8888

SCOPES = " ".join([
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "playlist-read-private",
    "playlist-read-collaborative",
    "user-library-read",
    "user-library-modify",
    "user-read-recently-played",
    "user-top-read",
])

CACHE_PATH = Path.home() / ".cache" / "spotty" / "token"

_HTML_SUCCESS = (
    b"<!DOCTYPE html><html><head><meta charset='utf-8'><title>spotty</title>"
    b"<style>body{font-family:monospace;background:#121212;color:#1DB954;"
    b"display:flex;align-items:center;justify-content:center;height:100vh;margin:0}"
    b"p{color:#B3B3B3;margin-top:.5rem}</style></head>"
    b"<body><div style='text-align:center'><h2>spotty</h2>"
    b"<p>Logged in. You can close this tab.</p></div></body></html>"
)


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    code: str | None = None
    event: threading.Event = threading.Event()

    def do_GET(self) -> None:
        params = parse_qs(urlparse(self.path).query)
        codes = params.get("code")
        if codes:
            _CallbackHandler.code = codes[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(_HTML_SUCCESS)
        else:
            self.send_response(400)
            self.end_headers()
        _CallbackHandler.event.set()

    def log_message(self, *_) -> None:  # silence access logs
        pass


def _get_pkce() -> SpotifyPKCE:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return SpotifyPKCE(
        client_id=_CLIENT_ID,
        redirect_uri=_REDIRECT_URI,
        scope=SCOPES,
        cache_path=str(CACHE_PATH),
        open_browser=False,
    )


def _login_flow(pkce: SpotifyPKCE) -> None:
    _CallbackHandler.code = None
    _CallbackHandler.event.clear()

    server = http.server.HTTPServer(("127.0.0.1", _PORT), _CallbackHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    print(
        "\n"
        "  ┌──────────────────────────────────────────┐\n"
        "  │  spotty — Spotify login                   │\n"
        "  ├──────────────────────────────────────────┤\n"
        "  │  Browser opening — log in with Spotify.  │\n"
        "  │  The tab will close automatically.       │\n"
        "  └──────────────────────────────────────────┘\n"
    )
    webbrowser.open(pkce.get_authorize_url())

    if not _CallbackHandler.event.wait(timeout=120):
        server.shutdown()
        raise SystemExit("\n  Login timed out. Run spotty again to retry.")

    server.shutdown()

    if not _CallbackHandler.code:
        raise SystemExit("\n  Login failed — no code received.")

    pkce.get_access_token(_CallbackHandler.code)
    print("  ✓ Logged in. Starting spotty…\n")


def get_spotify_client() -> spotipy.Spotify:
    pkce = _get_pkce()
    if not pkce.get_cached_token():
        _login_flow(pkce)
    return spotipy.Spotify(auth_manager=pkce, requests_timeout=10)
