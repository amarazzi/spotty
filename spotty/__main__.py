"""Entry point: authenticate, start spotifyd if available, then launch the TUI."""

from __future__ import annotations

from spotty.auth import get_spotify_client


def main() -> None:
    try:
        sp_client = get_spotify_client()
    except EnvironmentError as exc:
        print(f"\n  Error: {exc}\n")
        raise SystemExit(1)

    from spotty.spotifyd_manager import setup_and_start
    setup_and_start()

    from spotty.app import SpottyApp
    from spotty.api import SpotifyAPI

    api = SpotifyAPI(sp_client)
    app = SpottyApp(api=api)
    app.run()


if __name__ == "__main__":
    main()
