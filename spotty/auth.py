"""OAuth 2.0 Authorization Code Flow for Spotify (paste-URL flow)."""

import os
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

_ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(_ENV_PATH)

SCOPES = [
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "playlist-read-private",
    "playlist-read-collaborative",
    "user-library-read",
    "user-read-recently-played",
]

CACHE_PATH = Path.home() / ".spotify_cache"


def _get_oauth() -> SpotifyOAuth:
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")

    _PLACEHOLDERS = {"your_client_id_here", "your_client_secret_here", "", None}
    if client_id in _PLACEHOLDERS or client_secret in _PLACEHOLDERS:
        raise EnvironmentError(
            f".env not configured at {_ENV_PATH.resolve()}\n\n"
            "  1. Open https://developer.spotify.com/dashboard\n"
            "  2. Create an app → Settings\n"
            "  3. Copy Client ID and Client Secret to .env\n"
            "  4. Add redirect URI: http://127.0.0.1:8888/callback\n"
        )

    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=" ".join(SCOPES),
        cache_path=str(CACHE_PATH),
        open_browser=False,
    )


def _extract_code_from_url(url: str) -> str | None:
    params = parse_qs(urlparse(url).query)
    codes = params.get("code")
    return codes[0] if codes else None


def _paste_url_flow(oauth: SpotifyOAuth) -> None:
    """Run the one-time browser paste-URL flow and populate the token cache."""
    auth_url = oauth.get_authorize_url()
    print(
        "\n"
        "  ┌─────────────────────────────────────────────────────────┐\n"
        "  │  spotty — Spotify login                                  │\n"
        "  ├─────────────────────────────────────────────────────────┤\n"
        "  │  1. Browser opens. Log in with Spotify.                 │\n"
        "  │  2. Browser will try to redirect and fail — that's ok.  │\n"
        "  │  3. Copy the full URL from the address bar.             │\n"
        "  │  4. Paste it here and press Enter.                       │\n"
        "  └─────────────────────────────────────────────────────────┘\n"
    )
    webbrowser.open(auth_url)

    while True:
        try:
            pasted = input("  Callback URL → ").strip()
        except (EOFError, KeyboardInterrupt):
            raise SystemExit("\n  Authentication cancelled.")

        code = _extract_code_from_url(pasted)
        if code:
            break
        print("  Invalid URL, try again.")

    oauth.get_access_token(code, as_dict=True)
    print("\n  ✓ Authenticated. Starting spotty…\n")


def get_spotify_client() -> spotipy.Spotify:
    """Return an authenticated Spotify client with automatic token refresh."""
    oauth = _get_oauth()

    # If no cached token, run the one-time paste-URL flow to populate it.
    if not oauth.get_cached_token():
        _paste_url_flow(oauth)

    # auth_manager automatically refreshes the token when it expires (after 1h).
    return spotipy.Spotify(auth_manager=oauth, requests_timeout=10)
