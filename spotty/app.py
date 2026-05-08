"""Main Textual application — full-screen now-playing with modal overlays."""

from __future__ import annotations

import requests.exceptions
from spotipy.exceptions import SpotifyException
from textual.app import App, ComposeResult
from textual.binding import Binding

from spotty.api import SpotifyAPI
from spotty.spotifyd_manager import is_running as _spotifyd_is_running
from spotty.widgets.home_overlay import HomeOverlay
from spotty.widgets.now_playing import NowPlaying
from spotty.widgets.playlists_overlay import PlaylistsOverlay
from spotty.widgets.search_overlay import SearchOverlay


class SpottyApp(App):
    TITLE = "spotty"
    CSS_PATH = "spotty.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("space", "play_pause", "Play/Pause"),
        Binding("n", "next_track", "Next"),
        Binding("p", "previous_track", "Prev"),
        Binding("equal,plus", "volume_up", "Vol+"),
        Binding("minus", "volume_down", "Vol-"),
        Binding("slash", "search", "Search"),
        Binding("l", "playlists", "Playlists"),
        Binding("r", "home", "Recent"),
    ]

    def __init__(self, api: SpotifyAPI) -> None:
        super().__init__()
        self.api = api
        self._volume = 50
        self._playlists: list = []

    def compose(self) -> ComposeResult:
        yield NowPlaying(id="now-playing")

    def on_mount(self) -> None:
        self._playlists = self._safe_api(self.api.playlists) or []
        vol = self._safe_api(self.api.current_volume)
        if vol is not None:
            self._volume = vol
        self._activate_spotifyd_if_running()
        self._refresh()
        self.set_interval(3, self._refresh)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        track = self._safe_api(self.api.current_track)
        self.query_one(NowPlaying).update_track(track)

    def _refresh_soon(self) -> None:
        """Refresh state after a short delay (gives Spotify API time to catch up)."""
        self.set_timer(0.6, self._refresh)

    # ------------------------------------------------------------------
    # Actions — playback
    # ------------------------------------------------------------------

    def action_play_pause(self) -> None:
        self._safe_api(self.api.play_pause)
        self._refresh_soon()

    def action_next_track(self) -> None:
        self._safe_api(self.api.next_track)
        self._refresh_soon()

    def action_previous_track(self) -> None:
        self._safe_api(self.api.previous_track)
        self._refresh_soon()

    def action_volume_up(self) -> None:
        self._volume = min(100, self._volume + 5)
        self._safe_api(lambda: self.api.set_volume(self._volume))
        self.notify(f"Volume: {self._volume}%", timeout=1)

    def action_volume_down(self) -> None:
        self._volume = max(0, self._volume - 5)
        self._safe_api(lambda: self.api.set_volume(self._volume))
        self.notify(f"Volume: {self._volume}%", timeout=1)

    # ------------------------------------------------------------------
    # Actions — overlays
    # ------------------------------------------------------------------

    def action_search(self) -> None:
        def on_result(track) -> None:
            if track:
                self._safe_api(lambda: self.api.play_track(track.id))
                self._refresh_soon()

        self.push_screen(SearchOverlay(api=self.api), on_result)

    def action_playlists(self) -> None:
        def on_result(playlist) -> None:
            if playlist:
                self._safe_api(lambda: self.api.play_playlist(playlist.id))
                self.notify(f"▶  {playlist.name}", timeout=3)
                self._refresh_soon()

        self.push_screen(PlaylistsOverlay(api=self.api, playlists=self._playlists), on_result)

    def action_home(self) -> None:
        def on_result(track) -> None:
            if track:
                self._safe_api(lambda: self.api.play_track(track.id))
                self._refresh_soon()

        self.push_screen(HomeOverlay(api=self.api), on_result)

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def _safe_api(self, fn):
        try:
            return fn()
        except SpotifyException as e:
            msg = str(e)
            if "NO_ACTIVE_DEVICE" in msg:
                if self._try_activate_device():
                    try:
                        return fn()
                    except SpotifyException:
                        pass
                self.notify(
                    "No device found — open Spotify on any device",
                    severity="warning",
                    timeout=5,
                )
            elif "403" in msg:
                self.notify("Spotify Premium required for playback control", severity="error", timeout=4)
            else:
                self.notify(f"Spotify error: {e}", severity="error", timeout=4)
            return None
        except requests.exceptions.ReadTimeout:
            return None
        except requests.exceptions.ConnectionError:
            return None
        except Exception as e:
            self.notify(f"Network error: {e}", severity="warning", timeout=4)
            return None

    def _activate_spotifyd_if_running(self) -> None:
        """Silently transfer playback to the spotty device if spotifyd is up."""
        try:
            if not _spotifyd_is_running():
                return
            devices = self.api.available_devices()
            device = next((d for d in devices if d.get("name") == "spotty"), None)
            if device:
                self.api.transfer_playback(device["id"], force_play=False)
        except Exception:
            pass

    def _try_activate_device(self) -> bool:
        try:
            devices = self.api.available_devices()
            if not devices:
                return False
            preferred = next((d for d in devices if d.get("name") == "spotty"), None)
            device = preferred or devices[0]
            self.api.transfer_playback(device["id"], force_play=True)
            return True
        except Exception:
            pass
        return False
