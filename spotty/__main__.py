"""Entry point: authenticate, start spotifyd if available, then launch the TUI."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from spotty.auth import get_spotify_client


def main() -> None:
    try:
        sp_client = get_spotify_client()
    except EnvironmentError as exc:
        print(f"\n  Error: {exc}\n")
        raise SystemExit(1)

    load_dotenv(Path(__file__).parent.parent / ".env")
    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")

    from spotty.spotifyd_manager import setup_and_start
    setup_and_start(client_id, client_secret)

    from spotty.app import SpottyApp
    from spotty.api import SpotifyAPI

    api = SpotifyAPI(sp_client)
    app = SpottyApp(api=api)
    app.run()


if __name__ == "__main__":
    main()
