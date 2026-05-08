"""Main Textual application — full-screen now-playing with modal overlays."""

from __future__ import annotations

import requests.exceptions
from spotipy.exceptions import SpotifyException
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding

from spotty.api import Album, SpotifyAPI
from spotty.spotifyd_manager import DEVICE_NAME as _SPOTIFYD_DEVICE, is_installed as _spotifyd_installed
from spotty import track_cache
from spotty.widgets.album_tracks_overlay import AlbumTracksOverlay
from spotty.widgets.home_overlay import HomeOverlay
from spotty.widgets.lyrics_overlay import LyricsOverlay
from spotty.widgets.now_playing import NowPlaying
from spotty.widgets.playlists_overlay import PlaylistsOverlay
from spotty.widgets.queue_overlay import QueueOverlay
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
        Binding("l", "lyrics", "Lyrics"),
        Binding("o", "playlists", "Playlists"),
        Binding("r", "home", "Recent"),
        Binding("u", "queue", "Queue"),
    ]

    def __init__(self, api: SpotifyAPI) -> None:
        super().__init__()
        self.api = api
        self._volume = 50
        self._playlists: list = []
        self._connected: bool = False
        self._device_id: str | None = None

    def compose(self) -> ComposeResult:
        yield NowPlaying(id="now-playing")

    def on_mount(self) -> None:
        self._load_initial_state()
        self._connect_spotifyd()

    @work(thread=True, exclusive=True, name="init-state")
    def _load_initial_state(self) -> None:
        try:
            self._playlists = self.api.playlists() or []
        except Exception:
            pass
        try:
            vol = self.api.current_volume()
            if vol is not None:
                self._volume = vol
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Ready transition
    # ------------------------------------------------------------------

    def _mark_ready(self) -> None:
        """Called from _connect_spotifyd when the device is up (or we give up)."""
        self._connected = True
        track = self._safe_api(self.api.current_track, silent=True)
        if track is not None:
            track_cache.save(track)
        else:
            track = track_cache.load()
        self.query_one(NowPlaying).set_ready(track)
        self.set_interval(3, self._refresh)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        if not self._connected:
            return
        track = self._safe_api(self.api.current_track, silent=True)
        if track is not None:
            track_cache.save(track)
        else:
            track = track_cache.load()
        self.query_one(NowPlaying).update_track(track)

    def _refresh_soon(self) -> None:
        self.set_timer(0.6, self._refresh)

    def _check_skipped(self, prev_id: str | None) -> None:
        """After next_track, if the track didn't change Spotify had no context — play something similar."""
        track = self._safe_api(self.api.current_track, silent=True)
        if track is not None:
            track_cache.save(track)
        else:
            track = track_cache.load()
        self.query_one(NowPlaying).update_track(track)

        if prev_id and (track is None or track.id == prev_id):
            self._play_similar_next(prev_id)

    @work(thread=True, exclusive=True, name="skip-similar")
    def _play_similar_next(self, seed_id: str) -> None:
        similar = self.api._similar_tracks(seed_id, limit=5)
        if not similar:
            self.call_from_thread(self.notify, "Nothing to skip to", timeout=2)
            return
        did = self._device_id
        track = similar[0]
        self.call_from_thread(
            lambda: self._safe_api(lambda: self.api.play_track(track.id, device_id=did))
        )
        self.call_from_thread(self._refresh_soon)

    # ------------------------------------------------------------------
    # Actions — playback
    # ------------------------------------------------------------------

    def action_play_pause(self) -> None:
        if not self._connected:
            self.notify("Still connecting…", timeout=2)
            return
        cached = track_cache.load()
        fallback = f"spotify:track:{cached.id}" if cached else None
        did = self._device_id
        self._safe_api(lambda: self.api.play_pause(fallback_uri=fallback, device_id=did))
        self._refresh_soon()

    def action_next_track(self) -> None:
        if not self._connected:
            self.notify("Still connecting…", timeout=2)
            return
        did = self._device_id
        prev = track_cache.load()
        prev_id = prev.id if prev else None
        self._safe_api(lambda: self.api.next_track(device_id=did))
        self.set_timer(1.2, lambda: self._check_skipped(prev_id))

    def action_previous_track(self) -> None:
        if not self._connected:
            self.notify("Still connecting…", timeout=2)
            return
        did = self._device_id
        self._safe_api(lambda: self.api.previous_track(device_id=did))
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
        def on_search_result(result) -> None:
            if not result:
                return
            if isinstance(result, Album):
                self._open_album_tracks(result)
            else:
                did = self._device_id
                self._safe_api(lambda: self.api.play_track(result.id, device_id=did))
                self._refresh_soon()

        self.push_screen(SearchOverlay(api=self.api), on_search_result)

    def _open_album_tracks(self, album: Album) -> None:
        def on_track_selected(selection) -> None:
            if not selection:
                return
            selected_album, offset = selection
            did = self._device_id
            self._safe_api(lambda: self.api.play_album(selected_album.id, offset=offset, device_id=did))
            self.notify(f"▶  {selected_album.name}", timeout=3)
            self._refresh_soon()

        self.push_screen(AlbumTracksOverlay(api=self.api, album=album), on_track_selected)

    def action_playlists(self) -> None:
        def on_result(playlist) -> None:
            if playlist:
                did = self._device_id
                self._safe_api(lambda: self.api.play_playlist(playlist.id, device_id=did))
                self.notify(f"▶  {playlist.name}", timeout=3)
                self._refresh_soon()

        self.push_screen(PlaylistsOverlay(api=self.api, playlists=self._playlists), on_result)

    def action_home(self) -> None:
        def on_result(track) -> None:
            if track:
                did = self._device_id
                self._safe_api(lambda: self.api.play_track(track.id, device_id=did))
                self._refresh_soon()

        self.push_screen(HomeOverlay(api=self.api), on_result)

    def action_queue(self) -> None:
        def on_result(track) -> None:
            if track:
                did = self._device_id
                self._safe_api(lambda: self.api.play_track(track.id, device_id=did))
                self._refresh_soon()

        current = self._safe_api(self.api.current_track, silent=True)
        if current is None:
            current = track_cache.load()
        seed_id = current.id if current else None
        self.push_screen(QueueOverlay(api=self.api, current_track_id=seed_id), on_result)

    def action_lyrics(self) -> None:
        track = track_cache.load()
        if not track:
            track = self._safe_api(self.api.current_track, silent=True)
        if not track:
            self.notify("No track playing", timeout=2)
            return
        self.push_screen(LyricsOverlay(track_name=track.name, artist=track.artist))

    # ------------------------------------------------------------------
    # spotifyd connection
    # ------------------------------------------------------------------

    @work(thread=True, exclusive=True, name="spotifyd-connect")
    def _connect_spotifyd(self) -> None:
        """Poll until the spotifyd device appears, then mark ready."""
        import time as _t
        if _spotifyd_installed():
            for _ in range(8):  # up to 4 seconds
                _t.sleep(0.5)
                try:
                    devices = self.api.available_devices()
                    device = next((d for d in devices if d.get("name") == _SPOTIFYD_DEVICE), None)
                    if device:
                        self._device_id = device["id"]
                        self.api.transfer_playback(device["id"], force_play=False)
                        break
                except Exception:
                    pass
        self.call_from_thread(self._mark_ready)

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def _safe_api(self, fn, *, silent: bool = False):
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
                if not silent:
                    self.notify(
                        "No device found — open Spotify on any device",
                        severity="warning",
                        timeout=5,
                    )
            elif not silent:
                if "403" in msg:
                    self.notify("Spotify Premium required for playback control", severity="error", timeout=4)
                else:
                    self.notify(f"Spotify error: {e}", severity="error", timeout=4)
            return None
        except requests.exceptions.ReadTimeout:
            return None
        except requests.exceptions.ConnectionError:
            return None
        except Exception as e:
            if not silent:
                self.notify(f"Network error: {e}", severity="warning", timeout=4)
            return None

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
