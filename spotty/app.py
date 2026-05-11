"""Main Textual application — full-screen now-playing with modal overlays."""

from __future__ import annotations

import requests.exceptions
from spotipy.exceptions import SpotifyException
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding

from spotty.api import Album, SpotifyAPI
from spotty.messages import AddToQueue
from spotty.spotifyd_manager import DEVICE_NAME as _SPOTIFYD_DEVICE, is_installed as _spotifyd_installed
from spotty import track_cache
from spotty import cast_helper
from spotty import librespot_bridge as _lb
from spotty import media_keys
from spotty.widgets.album_tracks_overlay import AlbumTracksOverlay
from spotty.widgets.artist_overlay import ArtistOverlay
from spotty.widgets.devices_overlay import DevicesOverlay
from spotty.widgets.help_overlay import HelpOverlay
from spotty.widgets.home_overlay import HomeOverlay
from spotty.widgets.liked_songs_overlay import LikedSongsOverlay
from spotty.widgets.lyrics_overlay import LyricsOverlay
from spotty.widgets.now_playing import NowPlaying
from spotty.widgets.playlist_tracks_overlay import PlaylistTracksOverlay
from spotty.widgets.playlists_overlay import PlaylistsOverlay
from spotty.widgets.queue_overlay import QueueOverlay
from spotty.widgets.search_overlay import SearchOverlay
from spotty.widgets.top_overlay import TopOverlay


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
        Binding("s", "shuffle", "Shuffle"),
        Binding("x", "repeat", "Repeat"),
        Binding("h", "like", "Like"),
        Binding("f", "liked_songs", "Liked"),
        Binding("i", "artist", "Artist"),
        Binding("left_square_bracket", "seek_back", "Seek-"),
        Binding("right_square_bracket", "seek_forward", "Seek+"),
        Binding("d", "devices", "Devices"),
        Binding("b", "album", "Album"),
        Binding("t", "top", "Top"),
        Binding("question_mark", "help", "Help"),
    ]

    def __init__(self, api: SpotifyAPI) -> None:
        super().__init__()
        self.api = api
        self._volume = 50
        self._playlists: list = []
        self._connected: bool = False
        self._device_id: str | None = None
        self._shuffle: bool = False
        self._repeat: str = "off"  # "off", "track", "context"
        self._is_playing: bool = False
        self._last_liked_track_id: str | None = None
        self._soon_timer = None
        self._active_bridge: _lb.LibrespotBridge | None = None
        self._cast_info = None
        self._stream_url: str | None = None
        self._link_proc = None

    def compose(self) -> ComposeResult:
        yield NowPlaying(id="now-playing")

    def on_mount(self) -> None:
        self._load_initial_state()
        self._connect_spotifyd()
        media_keys.setup(
            on_play_pause=lambda: self.call_from_thread(self.action_play_pause),
            on_next=lambda: self.call_from_thread(self.action_next_track),
            on_prev=lambda: self.call_from_thread(self.action_previous_track),
        )

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
            self._shuffle = track.shuffle
            self._repeat = track.repeat
            self._is_playing = track.is_playing
        else:
            track = track_cache.load()
        np = self.query_one(NowPlaying)
        np.set_ready(track)
        np.volume = self._volume
        if track:
            self._last_liked_track_id = track.id
            self._fetch_liked(track.id)
            media_keys.update_now_playing(
                title=track.name,
                artist=track.artist,
                duration_ms=track.duration_ms,
                progress_ms=track.progress_ms,
                is_playing=track.is_playing,
            )
        self.set_interval(3, self._refresh)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        if not self._connected:
            return
        self._refresh_bg()

    @work(thread=True, exclusive=True, name="refresh")
    def _refresh_bg(self) -> None:
        track = self._safe_api(self.api.current_track, silent=True)
        if track is not None:
            track_cache.save(track)
            self._shuffle = track.shuffle
            self._repeat = track.repeat
            self._is_playing = track.is_playing
            if track.volume_percent is not None:
                self._volume = track.volume_percent
            # Sync _device_id from Spotify's active device, but only when the bridge
            # is not active — while casting, _device_id is managed by _bridge_cast_bg
            # and must not be overwritten by transient Spotify state (e.g. after a pause
            # Spotify may report a different device as "last active").
            if self.api._last_device_id and self._active_bridge is None:
                self._device_id = self.api._last_device_id
        else:
            track = track_cache.load()

        if track:
            media_keys.update_now_playing(
                title=track.name,
                artist=track.artist,
                duration_ms=track.duration_ms,
                progress_ms=track.progress_ms,
                is_playing=track.is_playing,
            )

        def _apply(t):
            np = self.query_one(NowPlaying)
            np.update_track(t)
            np.volume = self._volume
            if t and t.id != self._last_liked_track_id:
                self._last_liked_track_id = t.id
                self._fetch_liked(t.id)

        self.call_from_thread(_apply, track)

    def _refresh_soon(self) -> None:
        if self._soon_timer is not None:
            self._soon_timer.stop()
        self._soon_timer = self.set_timer(0.6, self._refresh)

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
        self._play_pause_bg(self._is_playing)
        self._is_playing = not self._is_playing
        self._refresh_soon()

    @work(thread=True, name="play-pause")
    def _play_pause_bg(self, is_playing: bool) -> None:
        did = self._device_id
        if is_playing:
            self._safe_api(lambda: self.api.pause(device_id=did))
        else:
            self._safe_api(lambda: self.api.resume(device_id=did))

    def action_next_track(self) -> None:
        if not self._connected:
            self.notify("Still connecting…", timeout=2)
            return
        prev = track_cache.load()
        prev_id = prev.id if prev else None
        did = self._device_id
        self._next_bg(did)
        self.set_timer(1.2, lambda: self._check_skipped(prev_id))
        # When casting via bridge, Google Home drops the stream during librespot's
        # track transition gap. Re-cast after a short delay to reconnect it.
        if self._active_bridge and self._cast_info and self._stream_url:
            self.set_timer(2.5, lambda: self._recast_bg(self._cast_info, self._stream_url))

    @work(thread=True, name="next")
    def _next_bg(self, device_id: str | None) -> None:
        self._safe_api(lambda: self.api.next_track(device_id=device_id))

    @work(thread=True, name="recast")
    def _recast_bg(self, cast_info, stream_url: str) -> None:
        if not self._active_bridge:
            return
        try:
            cast_helper.cast_url(cast_info, stream_url)
        except Exception:
            pass

    def action_previous_track(self) -> None:
        if not self._connected:
            self.notify("Still connecting…", timeout=2)
            return
        did = self._device_id
        self._previous_bg(did)
        self._refresh_soon()

    @work(thread=True, name="prev")
    def _previous_bg(self, device_id: str | None) -> None:
        self._safe_api(lambda: self.api.previous_track(device_id=device_id))

    def action_volume_up(self) -> None:
        self._volume = min(100, self._volume + 5)
        self.query_one(NowPlaying).volume = self._volume
        self.notify(f"Volume: {self._volume}%", timeout=1)
        self._set_volume_bg(self._volume)

    def action_volume_down(self) -> None:
        self._volume = max(0, self._volume - 5)
        self.query_one(NowPlaying).volume = self._volume
        self.notify(f"Volume: {self._volume}%", timeout=1)
        self._set_volume_bg(self._volume)

    @work(thread=True, exclusive=True, name="volume")
    def _set_volume_bg(self, vol: int) -> None:
        self._safe_api(lambda: self.api.set_volume(vol))

    def action_seek_forward(self) -> None:
        if not self._connected:
            return
        self._seek_by(10_000)

    def action_seek_back(self) -> None:
        if not self._connected:
            return
        self._seek_by(-10_000)

    @work(thread=True, name="seek")
    def _seek_by(self, delta_ms: int) -> None:
        pb = self._safe_api(self.api.current_track, silent=True)
        if not pb:
            return
        target = max(0, min(pb.progress_ms + delta_ms, pb.duration_ms - 500))
        self._safe_api(lambda: self.api.seek(target))
        self.call_from_thread(self._refresh_soon)

    def action_shuffle(self) -> None:
        if not self._connected:
            return
        self._shuffle = not self._shuffle
        self.query_one(NowPlaying).shuffle = self._shuffle
        self.notify("Shuffle " + ("on" if self._shuffle else "off"), timeout=1)
        self._shuffle_bg(self._shuffle)

    @work(thread=True, exclusive=True, name="shuffle")
    def _shuffle_bg(self, state: bool) -> None:
        self._safe_api(lambda: self.api.toggle_shuffle(state))

    def action_repeat(self) -> None:
        if not self._connected:
            return
        cycle = {"off": "context", "context": "track", "track": "off"}
        self._repeat = cycle.get(self._repeat, "off")
        self.query_one(NowPlaying).repeat = self._repeat
        self.notify(f"Repeat: {self._repeat}", timeout=1)
        self._repeat_bg(self._repeat)

    @work(thread=True, exclusive=True, name="repeat")
    def _repeat_bg(self, state: str) -> None:
        self._safe_api(lambda: self.api.set_repeat(state))

    def action_like(self) -> None:
        if not self._connected:
            return
        track = track_cache.load()
        if not track:
            self.notify("No track playing", timeout=2)
            return
        np = self.query_one(NowPlaying)
        new_liked = not np.is_liked
        np.is_liked = new_liked
        self.notify("heart" if new_liked else "unheart", timeout=2)
        self._like_bg(track.id, new_liked)

    @work(thread=True, name="like")
    def _like_bg(self, track_id: str, like: bool) -> None:
        try:
            if like:
                self.api.like_track(track_id)
            else:
                self.api.unlike_track(track_id)
        except Exception:
            self.call_from_thread(
                lambda: setattr(self.query_one(NowPlaying), "is_liked", not like)
            )

    @work(thread=True, exclusive=True, name="fetch-liked")
    def _fetch_liked(self, track_id: str) -> None:
        is_liked = self._safe_api(lambda: self.api.is_track_liked(track_id), silent=True)
        if is_liked is None:
            is_liked = False
        self.call_from_thread(lambda: setattr(self.query_one(NowPlaying), "is_liked", is_liked))

    # ------------------------------------------------------------------
    # AddToQueue message handler
    # ------------------------------------------------------------------

    def on_add_to_queue(self, event: AddToQueue) -> None:
        self._do_add_to_queue(event.track_id)

    @work(thread=True, name="add-queue")
    def _do_add_to_queue(self, track_id: str) -> None:
        did = self._device_id
        try:
            self.api.add_to_queue(track_id, device_id=did)
            self.call_from_thread(self.notify, "Added to queue", timeout=2)
        except Exception as e:
            self.call_from_thread(
                self.notify, f"Queue error: {e}", severity="error", timeout=3
            )

    # ------------------------------------------------------------------
    # Actions — overlays
    # ------------------------------------------------------------------

    @work(thread=True, name="play-track")
    def _play_track_bg(self, track_id: str) -> None:
        did = self._device_id
        self._safe_api(lambda: self.api.play_track(track_id, device_id=did))
        self.call_from_thread(self._refresh_soon)
        # Auto-queue similar tracks so playback continues after this track ends
        self.call_from_thread(self._autoqueue_bg, track_id, did)

    @work(thread=True, name="autoqueue")
    def _autoqueue_bg(self, seed_track_id: str, device_id: str | None) -> None:
        try:
            tracks, _ = self.api.get_queue(seed_track_id=seed_track_id)
            # get_queue returns recs when queue is empty — use those
            for t in tracks[:10]:
                try:
                    self.api.add_to_queue(t.id, device_id=device_id)
                except Exception:
                    pass
        except Exception:
            pass

    def action_search(self) -> None:
        from spotty.api import ArtistResult as _ArtistResult, Playlist as _Playlist

        def on_search_result(result) -> None:
            if not result:
                return
            if isinstance(result, Album):
                self._open_album_tracks(result)
            elif isinstance(result, _Playlist):
                self._open_playlist_tracks(result)
            elif isinstance(result, _ArtistResult):
                def on_track(t) -> None:
                    if t:
                        self._play_track_bg(t.id)
                self.push_screen(ArtistOverlay(api=self.api, artist_id=result.id, artist_name=result.name), on_track)
            else:
                self._play_track_bg(result.id)

        self.push_screen(SearchOverlay(api=self.api), on_search_result)

    def _open_playlist_tracks(self, playlist) -> None:
        def on_track_selected(selection) -> None:
            if not selection:
                return
            selected_playlist, offset = selection
            did = self._device_id
            self._safe_api(lambda: self.api.play_playlist(selected_playlist.id, offset=offset, device_id=did))
            self.notify(f"▶  {selected_playlist.name}", timeout=3)
            self._refresh_soon()
        self.push_screen(PlaylistTracksOverlay(api=self.api, playlist=playlist), on_track_selected)

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
        def on_playlist_selected(playlist) -> None:
            if not playlist:
                return
            def on_track_selected(selection) -> None:
                if not selection:
                    return
                selected_playlist, offset = selection
                did = self._device_id
                self._safe_api(lambda: self.api.play_playlist(selected_playlist.id, offset=offset, device_id=did))
                self.notify(f"▶  {selected_playlist.name}", timeout=3)
                self._refresh_soon()
            self.push_screen(PlaylistTracksOverlay(api=self.api, playlist=playlist), on_track_selected)

        self.push_screen(PlaylistsOverlay(api=self.api, playlists=self._playlists), on_playlist_selected)

    def action_home(self) -> None:
        def on_result(result) -> None:
            if not result:
                return
            kind, item = result
            if kind == "track":
                self._play_track_bg(item.id)
            elif kind == "playlist":
                did = self._device_id
                self._safe_api(lambda: self.api.play_playlist(item.id, device_id=did))
                self.notify(f"▶  {item.name}", timeout=3)
                self._refresh_soon()
            elif kind == "album":
                self._open_album_tracks(item)

        self.push_screen(HomeOverlay(api=self.api), on_result)

    def action_queue(self) -> None:
        def on_result(result) -> None:
            if not result:
                return
            track, remaining, is_recs = result
            if is_recs and remaining:
                self._play_with_recs_bg(track.id, [t.id for t in remaining])
            else:
                self._play_track_bg(track.id)

        current = track_cache.load()
        seed_id = current.id if current else None
        self.push_screen(QueueOverlay(api=self.api, current_track_id=seed_id), on_result)

    @work(thread=True, name="play-recs")
    def _play_with_recs_bg(self, track_id: str, queue_ids: list[str]) -> None:
        did = self._device_id
        for qid in queue_ids:
            try:
                self.api.add_to_queue(qid, device_id=did)
            except Exception:
                pass
        self._safe_api(lambda: self.api.play_track(track_id, device_id=did))
        self.call_from_thread(self._refresh_soon)

    def action_lyrics(self) -> None:
        self._open_lyrics()

    @work(thread=True, name="open-lyrics")
    def _open_lyrics(self) -> None:
        # Fresh API call so progress_ms is accurate for sync
        track = self._safe_api(self.api.current_track, silent=True)
        if not track:
            track = track_cache.load()
        if not track:
            self.call_from_thread(self.notify, "No track playing", timeout=2)
            return
        self.call_from_thread(lambda: self.push_screen(LyricsOverlay(track=track)))

    def action_liked_songs(self) -> None:
        def on_result(track) -> None:
            if track:
                self._play_track_bg(track.id)
        self.push_screen(LikedSongsOverlay(api=self.api), on_result)

    def action_artist(self) -> None:
        track = track_cache.load()
        artist_id = track.artist_id if track else None
        artist_name = track.artist if track else None
        if not artist_id:
            fresh = self._safe_api(self.api.current_track, silent=True)
            if fresh:
                artist_id = fresh.artist_id
                artist_name = fresh.artist
        if not artist_id:
            self.notify("Artist info unavailable", timeout=2)
            return
        def on_result(t) -> None:
            if t:
                self._play_track_bg(t.id)
        self.push_screen(ArtistOverlay(api=self.api, artist_id=artist_id, artist_name=artist_name or ""), on_result)

    def action_album(self) -> None:
        track = track_cache.load()
        if not track:
            track = self._safe_api(self.api.current_track, silent=True)
        if not track or not track.album_id:
            self.notify("No album info available", timeout=2)
            return
        album = Album(id=track.album_id, name=track.album, artist=track.artist, total=0)
        self._open_album_tracks(album)

    def action_top(self) -> None:
        from spotty.api import ArtistResult as _ArtistResult

        def on_result(result) -> None:
            if not result:
                return
            if isinstance(result, _ArtistResult):
                def on_track(t) -> None:
                    if t:
                        self._play_track_bg(t.id)
                self.push_screen(ArtistOverlay(api=self.api, artist_id=result.id, artist_name=result.name), on_track)
            else:
                self._play_track_bg(result.id)

        self.push_screen(TopOverlay(api=self.api), on_result)

    def action_devices(self) -> None:
        def on_result(device) -> None:
            if not device:
                return
            name = device.get("name", "")
            if "_cast_info" in device:
                self._bridge_cast_bg(device["_cast_info"], name)
            else:
                self._transfer_bg(device["id"], name)

        self.push_screen(DevicesOverlay(api=self.api), on_result)

    @work(thread=True, name="transfer")
    def _transfer_bg(self, device_id: str, name: str) -> None:
        self._stop_bridge()
        try:
            self.api.transfer_playback(device_id, force_play=False)
            self._device_id = device_id
            self.call_from_thread(self.notify, f"▸  {name}", timeout=3)
            self.call_from_thread(self._refresh_soon)
        except Exception as e:
            self.call_from_thread(self.notify, f"Transfer failed: {e}", severity="error", timeout=3)

    def _stop_bridge(self) -> None:
        if self._active_bridge:
            self._active_bridge.stop()
            self._active_bridge = None
        self._cast_info = None
        self._stream_url = None
        if self._link_proc:
            try:
                self._link_proc.kill()
            except Exception:
                pass
            self._link_proc = None

    @work(thread=True, name="cast-bridge")
    def _bridge_cast_bg(self, cast_info, cast_name: str) -> None:
        import time as _t

        if not _lb.is_librespot_installed():
            self.call_from_thread(
                self.notify,
                "librespot no instalado — corré: brew install librespot",
                severity="error", timeout=7,
            )
            return
        if not _lb.is_ffmpeg_installed():
            self.call_from_thread(
                self.notify,
                "ffmpeg no instalado — corré: brew install ffmpeg",
                severity="error", timeout=7,
            )
            return

        self._stop_bridge()

        # ── First time: need to capture credentials ──────────────────────
        if not _lb.has_credentials():
            bridge = _lb.LibrespotBridge()
            self.call_from_thread(
                self.notify,
                "Setup único: abrí Spotify → Dispositivos → 'spotty-bridge' → esperá",
                timeout=60,
            )
            link_proc = bridge.link()
            if not link_proc:
                self.call_from_thread(
                    self.notify, "Error iniciando librespot", severity="error", timeout=4
                )
                return
            self._link_proc = link_proc

            deadline = _t.monotonic() + 180
            while _t.monotonic() < deadline:
                if _lb.has_credentials():
                    break
                _t.sleep(1.0)

            try:
                link_proc.kill()
            except Exception:
                pass
            self._link_proc = None

            if not _lb.has_credentials():
                self.call_from_thread(
                    self.notify, "Timeout — intentá de nuevo", severity="warning", timeout=5
                )
                return

            _t.sleep(1.0)  # brief pause so librespot releases ports

        # ── Start bridge pipeline ─────────────────────────────────────────
        self.call_from_thread(self.notify, f"Conectando a {cast_name}…", timeout=25)
        bridge = _lb.LibrespotBridge()
        url = bridge.start()

        if not url:
            self.call_from_thread(
                self.notify,
                "Error iniciando bridge — credenciales vencidas, intentá de nuevo",
                severity="error", timeout=6,
            )
            # Remove stale credentials so next attempt re-links
            try:
                import os as _os
                _os.remove(_lb.CREDS_FILE)
            except Exception:
                pass
            return

        self._active_bridge = bridge
        self._cast_info = cast_info
        self._stream_url = url

        # ── Tell the Cast device to play the HTTP stream ──────────────────
        ok = cast_helper.cast_url(cast_info, url)
        if not ok:
            self.call_from_thread(
                self.notify, f"No se pudo conectar a {cast_name}", severity="error", timeout=5
            )
            bridge.stop()
            self._active_bridge = None
            return

        # ── Wait for 'spotty-bridge' to register in Spotify Connect ───────
        bridge_device_id = None
        deadline = _t.monotonic() + 20
        while _t.monotonic() < deadline:
            try:
                for d in self.api.available_devices():
                    if d.get("name") == _lb.BRIDGE_NAME:
                        bridge_device_id = d["id"]
                        break
                if bridge_device_id:
                    break
            except Exception:
                pass
            _t.sleep(1.5)

        if not bridge_device_id:
            self.call_from_thread(
                self.notify,
                "'spotty-bridge' no aparece en Spotify — intentá de nuevo",
                severity="warning", timeout=7,
            )
            bridge.stop()
            self._active_bridge = None
            return

        # ── Transfer playback ─────────────────────────────────────────────
        try:
            self.api.transfer_playback(bridge_device_id, force_play=True)
            self._device_id = bridge_device_id
            self.call_from_thread(self.notify, f"▸  {cast_name}", timeout=3)
            self.call_from_thread(self._refresh_soon)
        except Exception as e:
            self.call_from_thread(
                self.notify, f"Transfer error: {e}", severity="error", timeout=4
            )

    def action_help(self) -> None:
        self.push_screen(HelpOverlay())

    def on_unmount(self) -> None:
        if self._active_bridge:
            self._active_bridge.force_stop()
            self._active_bridge = None
        if self._link_proc:
            try:
                self._link_proc.kill()
            except Exception:
                pass
            self._link_proc = None

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
                        try:
                            self.api.pause()
                        except Exception:
                            pass
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
                    return None  # device activated (force_play handled it)
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
            preferred = next((d for d in devices if d.get("name") == _SPOTIFYD_DEVICE), None)
            device = preferred or devices[0]
            self.api.transfer_playback(device["id"], force_play=True)
            return True
        except Exception:
            pass
        return False
