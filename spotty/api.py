"""Thin wrapper around spotipy for spotty's use cases."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import spotipy


@dataclass
class Track:
    id: str
    name: str
    artist: str
    album: str
    duration_ms: int
    cover_url: str | None = None
    is_playing: bool = False
    progress_ms: int = 0


@dataclass
class Playlist:
    id: str
    name: str
    total: int
    tracks: list[Track] = field(default_factory=list)


class SpotifyAPI:
    def __init__(self, client: spotipy.Spotify) -> None:
        self._sp = client

    # ------------------------------------------------------------------
    # Playback state
    # ------------------------------------------------------------------

    def current_track(self) -> Track | None:
        pb = self._sp.current_playback()
        if not pb or not pb.get("item"):
            return None
        item = pb["item"]
        artists = ", ".join(a["name"] for a in item["artists"])
        images = item["album"].get("images", [])
        cover = images[0]["url"] if images else None
        return Track(
            id=item["id"],
            name=item["name"],
            artist=artists,
            album=item["album"]["name"],
            duration_ms=item["duration_ms"],
            cover_url=cover,
            is_playing=pb["is_playing"],
            progress_ms=pb.get("progress_ms", 0),
        )

    # ------------------------------------------------------------------
    # Playback controls
    # ------------------------------------------------------------------

    def play_pause(self, fallback_uri: str | None = None) -> None:
        pb = self._sp.current_playback()
        if pb and pb["is_playing"]:
            self._sp.pause_playback()
        elif pb and pb.get("item"):
            self._sp.start_playback()
        elif fallback_uri:
            self._sp.start_playback(uris=[fallback_uri])
        else:
            self._sp.start_playback()

    def next_track(self) -> None:
        self._sp.next_track()

    def previous_track(self) -> None:
        self._sp.previous_track()

    def set_volume(self, percent: int) -> None:
        self._sp.volume(max(0, min(100, percent)))

    def seek(self, position_ms: int) -> None:
        self._sp.seek_track(position_ms)

    # ------------------------------------------------------------------
    # Playlists
    # ------------------------------------------------------------------

    def playlists(self, limit: int = 50) -> list[Playlist]:
        result = self._sp.current_user_playlists(limit=limit)
        items: list[Any] = result.get("items", [])
        return [
            Playlist(
                id=p["id"],
                name=p["name"],
                total=p["tracks"]["total"],
            )
            for p in items
            if p
        ]

    def playlist_tracks(self, playlist_id: str, limit: int = 100) -> list[Track]:
        result = self._sp.playlist_tracks(playlist_id, limit=limit)
        tracks: list[Track] = []
        for item in result.get("items", []):
            t = item.get("track")
            if not t:
                continue
            artists = ", ".join(a["name"] for a in t["artists"])
            images = t["album"].get("images", [])
            cover = images[0]["url"] if images else None
            tracks.append(
                Track(
                    id=t["id"],
                    name=t["name"],
                    artist=artists,
                    album=t["album"]["name"],
                    duration_ms=t["duration_ms"],
                    cover_url=cover,
                )
            )
        return tracks

    def play_playlist(self, playlist_id: str, offset: int = 0) -> None:
        self._sp.start_playback(
            context_uri=f"spotify:playlist:{playlist_id}",
            offset={"position": offset},
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_tracks(self, query: str, limit: int = 20) -> list[Track]:
        result = self._sp.search(q=query, type="track", limit=limit)
        items = result.get("tracks", {}).get("items", [])
        tracks: list[Track] = []
        for t in items:
            artists = ", ".join(a["name"] for a in t["artists"])
            images = t["album"].get("images", [])
            cover = images[0]["url"] if images else None
            tracks.append(
                Track(
                    id=t["id"],
                    name=t["name"],
                    artist=artists,
                    album=t["album"]["name"],
                    duration_ms=t["duration_ms"],
                    cover_url=cover,
                )
            )
        return tracks

    def play_track(self, track_id: str) -> None:
        self._sp.start_playback(uris=[f"spotify:track:{track_id}"])

    # ------------------------------------------------------------------
    # Home / Browse
    # ------------------------------------------------------------------

    def current_volume(self) -> int:
        pb = self._sp.current_playback()
        if pb and pb.get("device"):
            return pb["device"].get("volume_percent", 50)
        return 50

    def available_devices(self) -> list[dict]:
        return self._sp.devices().get("devices", [])

    def transfer_playback(self, device_id: str, force_play: bool = True) -> None:
        self._sp.transfer_playback(device_id, force_play=force_play)

    def recently_played(self, limit: int = 20) -> list[Track]:
        result = self._sp.current_user_recently_played(limit=limit)
        seen: set[str] = set()
        tracks: list[Track] = []
        for item in result.get("items", []):
            t = item.get("track")
            if not t or t["id"] in seen:
                continue
            seen.add(t["id"])
            artists = ", ".join(a["name"] for a in t["artists"])
            images = t["album"].get("images", [])
            cover = images[0]["url"] if images else None
            tracks.append(Track(
                id=t["id"],
                name=t["name"],
                artist=artists,
                album=t["album"]["name"],
                duration_ms=t["duration_ms"],
                cover_url=cover,
            ))
        return tracks
