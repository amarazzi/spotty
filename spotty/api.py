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
    artist_id: str | None = None
    album_id: str | None = None
    shuffle: bool = False
    repeat: str = "off"  # "off", "track", "context"
    volume_percent: int | None = None
    is_episode: bool = False


@dataclass
class ArtistResult:
    id: str
    name: str
    genres: list[str]


@dataclass
class ArtistInfo:
    id: str
    name: str
    genres: list[str]
    followers: int
    popularity: int
    image_url: str | None
    top_tracks: list["Track"]


@dataclass
class Album:
    id: str
    name: str
    artist: str
    total: int


@dataclass
class Playlist:
    id: str
    name: str
    total: int
    tracks: list[Track] = field(default_factory=list)


class SpotifyAPI:
    def __init__(self, client: spotipy.Spotify) -> None:
        self._sp = client
        self._last_device_id: str | None = None

    # ------------------------------------------------------------------
    # Playback state
    # ------------------------------------------------------------------

    def current_track(self) -> Track | None:
        pb = self._sp.current_playback()
        if not pb or not pb.get("item"):
            return None
        device = pb.get("device") or {}
        if device.get("id"):
            self._last_device_id = device["id"]
        item = pb["item"]

        if item.get("type") == "episode":
            show = item.get("show") or {}
            images = show.get("images", [])
            cover = images[0]["url"] if images else None
            return Track(
                id=item["id"],
                name=item["name"],
                artist=show.get("name", "Podcast"),
                album=show.get("publisher", ""),
                duration_ms=item["duration_ms"],
                cover_url=cover,
                is_playing=pb["is_playing"],
                progress_ms=pb.get("progress_ms") or 0,
                shuffle=pb.get("shuffle_state", False),
                repeat=pb.get("repeat_state", "off"),
                volume_percent=device.get("volume_percent"),
                is_episode=True,
            )

        raw_artists = item.get("artists") or []
        artists = ", ".join(a["name"] for a in raw_artists)
        alb = item.get("album") or {}
        images = alb.get("images", [])
        cover = images[0]["url"] if images else None
        artist_id = raw_artists[0]["id"] if raw_artists else None
        return Track(
            id=item["id"],
            name=item["name"],
            artist=artists,
            album=alb.get("name", ""),
            album_id=alb.get("id"),
            duration_ms=item["duration_ms"],
            cover_url=cover,
            is_playing=pb["is_playing"],
            progress_ms=pb.get("progress_ms") or 0,
            artist_id=artist_id,
            shuffle=pb.get("shuffle_state", False),
            repeat=pb.get("repeat_state", "off"),
            volume_percent=device.get("volume_percent"),
        )

    # ------------------------------------------------------------------
    # Playback controls
    # ------------------------------------------------------------------

    def play_pause(self, fallback_uri: str | None = None, device_id: str | None = None) -> None:
        pb = self._sp.current_playback()
        if pb and pb["is_playing"]:
            self._sp.pause_playback(device_id=device_id)
        elif pb and pb.get("item"):
            self._sp.start_playback(device_id=device_id)
        elif fallback_uri:
            self._sp.start_playback(device_id=device_id, uris=[fallback_uri])
        else:
            self._sp.start_playback(device_id=device_id)

    def pause(self, device_id: str | None = None) -> None:
        self._sp.pause_playback(device_id=device_id or self._last_device_id)

    def resume(self, device_id: str | None = None) -> None:
        self._sp.start_playback(device_id=device_id or self._last_device_id)

    def next_track(self, device_id: str | None = None) -> None:
        self._sp.next_track(device_id=device_id)

    def previous_track(self, device_id: str | None = None) -> None:
        self._sp.previous_track(device_id=device_id)

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
            if not t or t.get("type") == "episode":
                continue
            artists = ", ".join(a["name"] for a in t["artists"])
            alb = t.get("album") or {}
            images = alb.get("images", [])
            cover = images[0]["url"] if images else None
            tracks.append(
                Track(
                    id=t["id"],
                    name=t["name"],
                    artist=artists,
                    album=alb.get("name", ""),
                    album_id=alb.get("id"),
                    duration_ms=t["duration_ms"],
                    cover_url=cover,
                )
            )
        return tracks

    def play_playlist(self, playlist_id: str, offset: int = 0, device_id: str | None = None) -> None:
        self._sp.start_playback(
            device_id=device_id,
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
            alb = t.get("album") or {}
            images = alb.get("images", [])
            cover = images[0]["url"] if images else None
            tracks.append(
                Track(
                    id=t["id"],
                    name=t["name"],
                    artist=artists,
                    album=alb.get("name", ""),
                    album_id=alb.get("id"),
                    duration_ms=t["duration_ms"],
                    cover_url=cover,
                )
            )
        return tracks

    def search_artists(self, query: str, limit: int = 15) -> list[ArtistResult]:
        result = self._sp.search(q=query, type="artist", limit=limit)
        items = result.get("artists", {}).get("items", [])
        artists = []
        for a in items:
            if not a:
                continue
            artists.append(ArtistResult(
                id=a["id"],
                name=a["name"],
                genres=a.get("genres", [])[:3],
            ))
        return artists

    def play_track(self, track_id: str, device_id: str | None = None) -> None:
        self._sp.start_playback(device_id=device_id, uris=[f"spotify:track:{track_id}"])

    def search_playlists(self, query: str, limit: int = 15) -> list[Playlist]:
        result = self._sp.search(q=query, type="playlist", limit=limit)
        items = result.get("playlists", {}).get("items", [])
        playlists = []
        for p in items:
            if not p:
                continue
            owner = p.get("owner", {}).get("display_name", "")
            total = p.get("tracks", {}).get("total", 0)
            playlists.append(Playlist(
                id=p["id"],
                name=p["name"],
                total=total,
                tracks=[],  # lazy
            ))
        return playlists

    def search_albums(self, query: str, limit: int = 15) -> list[Album]:
        result = self._sp.search(q=query, type="album", limit=limit)
        items = result.get("albums", {}).get("items", [])
        albums = []
        for a in items:
            if not a:
                continue
            artists = ", ".join(x["name"] for x in a["artists"])
            albums.append(Album(
                id=a["id"],
                name=a["name"],
                artist=artists,
                total=a["total_tracks"],
            ))
        return albums

    def album_tracks(self, album_id: str, limit: int = 50) -> list[Track]:
        result = self._sp.album_tracks(album_id, limit=limit)
        tracks = []
        for i, item in enumerate(result.get("items", [])):
            if not item:
                continue
            artists = ", ".join(a["name"] for a in item["artists"])
            tracks.append(Track(
                id=item["id"],
                name=item["name"],
                artist=artists,
                album="",
                duration_ms=item["duration_ms"],
                artist_id=item["artists"][0]["id"] if item.get("artists") else None,
            ))
        return tracks

    def play_album(self, album_id: str, offset: int = 0, device_id: str | None = None) -> None:
        self._sp.start_playback(
            device_id=device_id,
            context_uri=f"spotify:album:{album_id}",
            offset={"position": offset},
        )

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

    def get_queue(self, seed_track_id: str | None = None) -> tuple[list[Track], bool]:
        """Returns (tracks, is_recommendations). Falls back to recommendations if queue is empty."""
        result = self._sp.queue()
        tracks = []
        if result:
            for item in result.get("queue", [])[:25]:
                if not item or item.get("type") != "track":
                    continue
                artists = ", ".join(a["name"] for a in item["artists"])
                images = item["album"].get("images", [])
                cover = images[0]["url"] if images else None
                tracks.append(Track(
                    id=item["id"],
                    name=item["name"],
                    artist=artists,
                    album=item["album"]["name"],
                    duration_ms=item["duration_ms"],
                    cover_url=cover,
                ))

        if tracks:
            return tracks, False

        if not seed_track_id:
            return [], False

        # Try deprecated recommendations endpoint first (still works for older apps)
        try:
            recs = self._sp.recommendations(seed_tracks=[seed_track_id], limit=20)
            for item in recs.get("tracks", []):
                if not item:
                    continue
                artists = ", ".join(a["name"] for a in item["artists"])
                images = item["album"].get("images", [])
                cover = images[0]["url"] if images else None
                tracks.append(Track(
                    id=item["id"],
                    name=item["name"],
                    artist=artists,
                    album=item["album"]["name"],
                    duration_ms=item["duration_ms"],
                    cover_url=cover,
                ))
            if tracks:
                return tracks, True
        except Exception:
            pass

        # Fall back: related artists' top tracks
        similar = self._similar_tracks(seed_track_id)
        return similar, True

    def _similar_tracks(self, seed_track_id: str, limit: int = 20) -> list[Track]:
        """Similar tracks via artist top-tracks + genre search (no deprecated endpoints)."""
        try:
            track_info = self._sp.track(seed_track_id)
        except Exception:
            return []
        if not track_info:
            return []

        artist_ids = [a["id"] for a in track_info.get("artists", []) if a.get("id")]
        artist_name = track_info["artists"][0]["name"] if track_info.get("artists") else ""
        if not artist_ids:
            return []

        try:
            market = self._sp.current_user().get("country", "US")
        except Exception:
            market = "US"

        tracks: list[Track] = []
        seen: set[str] = {seed_track_id}

        def _append(t: dict) -> bool:
            if not t or t.get("id") in seen:
                return False
            seen.add(t["id"])
            arts = ", ".join(a["name"] for a in t.get("artists", []))
            imgs = t.get("album", {}).get("images", [])
            cover = imgs[0]["url"] if imgs else None
            tracks.append(Track(
                id=t["id"],
                name=t["name"],
                artist=arts,
                album=t.get("album", {}).get("name", ""),
                duration_ms=t.get("duration_ms", 0),
                cover_url=cover,
            ))
            return len(tracks) >= limit

        # 1. Current artist's own top tracks
        try:
            top = self._sp.artist_top_tracks(artist_ids[0], country=market)
            for t in top.get("tracks", []):
                if _append(t):
                    return tracks
        except Exception:
            pass

        # 2. Genre-based search using artist's genres
        try:
            artist_info = self._sp.artist(artist_ids[0])
            genres = artist_info.get("genres", [])[:3]
            for genre in genres:
                result = self._sp.search(q=f'genre:"{genre}"', type="track", limit=15, market=market)
                for t in result.get("tracks", {}).get("items", []):
                    if _append(t):
                        return tracks
        except Exception:
            pass

        # 3. Fallback: search by artist name
        if not tracks:
            try:
                result = self._sp.search(q=f'artist:"{artist_name}"', type="track", limit=20, market=market)
                for t in result.get("tracks", {}).get("items", []):
                    if _append(t):
                        return tracks
            except Exception:
                pass

        return tracks

    def toggle_shuffle(self, state: bool) -> None:
        self._sp.shuffle(state)

    def set_repeat(self, state: str) -> None:
        self._sp.repeat(state)

    def like_track(self, track_id: str) -> None:
        self._sp.current_user_saved_tracks_add([track_id])

    def unlike_track(self, track_id: str) -> None:
        self._sp.current_user_saved_tracks_delete([track_id])

    def is_track_liked(self, track_id: str) -> bool:
        result = self._sp.current_user_saved_tracks_contains([track_id])
        return bool(result and result[0])

    def add_to_queue(self, track_id: str, device_id: str | None = None) -> None:
        self._sp.add_to_queue(f"spotify:track:{track_id}", device_id=device_id)

    def liked_tracks(self, limit: int = 50) -> list[Track]:
        result = self._sp.current_user_saved_tracks(limit=limit)
        tracks: list[Track] = []
        for item in result.get("items", []):
            t = item.get("track")
            if not t:
                continue
            artists = ", ".join(a["name"] for a in t["artists"])
            artist_id = t["artists"][0]["id"] if t.get("artists") else None
            alb = t.get("album") or {}
            images = alb.get("images", [])
            cover = images[0]["url"] if images else None
            tracks.append(Track(
                id=t["id"],
                name=t["name"],
                artist=artists,
                album=alb.get("name", ""),
                album_id=alb.get("id"),
                duration_ms=t["duration_ms"],
                cover_url=cover,
                artist_id=artist_id,
            ))
        return tracks

    def top_tracks(self, time_range: str = "medium_term", limit: int = 20) -> list[Track]:
        result = self._sp.current_user_top_tracks(limit=limit, time_range=time_range)
        tracks: list[Track] = []
        for t in result.get("items", []):
            if not t:
                continue
            artists = ", ".join(a["name"] for a in t.get("artists", []))
            artist_id = t["artists"][0]["id"] if t.get("artists") else None
            alb = t.get("album") or {}
            images = alb.get("images", [])
            cover = images[0]["url"] if images else None
            tracks.append(Track(
                id=t["id"],
                name=t["name"],
                artist=artists,
                album=alb.get("name", ""),
                album_id=alb.get("id"),
                duration_ms=t.get("duration_ms", 0),
                cover_url=cover,
                artist_id=artist_id,
            ))
        return tracks

    def top_artists(self, time_range: str = "medium_term", limit: int = 15) -> list[ArtistResult]:
        result = self._sp.current_user_top_artists(limit=limit, time_range=time_range)
        artists: list[ArtistResult] = []
        for a in result.get("items", []):
            if not a:
                continue
            artists.append(ArtistResult(
                id=a["id"],
                name=a["name"],
                genres=a.get("genres", [])[:3],
            ))
        return artists

    def get_artist_full(self, artist_id: str) -> ArtistInfo:
        artist = self._sp.artist(artist_id)
        try:
            market = self._sp.current_user().get("country", "US")
        except Exception:
            market = "US"
        top_result = self._sp.artist_top_tracks(artist_id, country=market)
        images = artist.get("images", [])
        image_url = images[0]["url"] if images else None
        tracks: list[Track] = []
        for t in top_result.get("tracks", []):
            if not t:
                continue
            arts = ", ".join(a["name"] for a in t.get("artists", []))
            imgs = t.get("album", {}).get("images", [])
            cover = imgs[0]["url"] if imgs else None
            tracks.append(Track(
                id=t["id"],
                name=t["name"],
                artist=arts,
                album=t.get("album", {}).get("name", ""),
                duration_ms=t.get("duration_ms", 0),
                cover_url=cover,
                artist_id=artist_id,
            ))
        return ArtistInfo(
            id=artist_id,
            name=artist["name"],
            genres=artist.get("genres", [])[:3],
            followers=artist.get("followers", {}).get("total", 0),
            popularity=artist.get("popularity", 0),
            image_url=image_url,
            top_tracks=tracks,
        )

    def artist_top_tracks_by_id(self, artist_id: str) -> list[Track]:
        try:
            market = self._sp.current_user().get("country", "US")
        except Exception:
            market = "US"
        result = self._sp.artist_top_tracks(artist_id, country=market)
        tracks: list[Track] = []
        for t in result.get("tracks", []):
            if not t:
                continue
            arts = ", ".join(a["name"] for a in t.get("artists", []))
            imgs = t.get("album", {}).get("images", [])
            cover = imgs[0]["url"] if imgs else None
            tracks.append(Track(
                id=t["id"],
                name=t["name"],
                artist=arts,
                album=t.get("album", {}).get("name", ""),
                duration_ms=t.get("duration_ms", 0),
                cover_url=cover,
                artist_id=artist_id,
            ))
        return tracks

    _MADE_FOR_YOU_NAMES = (
        "daily mix", "discover weekly", "release radar", "daily drive",
        "on repeat", "repeat rewind", "time capsule", "your top songs",
        "songs to sing", "chill hits", "fresh finds",
    )

    def made_for_you(self) -> list[Playlist]:
        """Spotify-curated playlists: checks user library, then searches by well-known names."""
        seen: set[str] = set()
        playlists: list[Playlist] = []

        def _add(p: dict) -> None:
            pid = p.get("id")
            if not pid or pid in seen:
                return
            seen.add(pid)
            playlists.append(Playlist(
                id=pid,
                name=p["name"],
                total=p.get("tracks", {}).get("total", 0),
            ))

        # Phase 1: user's library, filtered by Spotify ownership or known names
        offset = 0
        while True:
            result = self._sp.current_user_playlists(limit=50, offset=offset)
            items = result.get("items", [])
            if not items:
                break
            for p in items:
                if not p:
                    continue
                owner_id = p.get("owner", {}).get("id", "")
                owner_name = p.get("owner", {}).get("display_name", "").lower()
                name_lower = p.get("name", "").lower()
                is_spotify = owner_id == "spotify" or owner_name == "spotify"
                has_keyword = any(kw in name_lower for kw in self._MADE_FOR_YOU_NAMES)
                if is_spotify or has_keyword:
                    _add(p)
            if not result.get("next"):
                break
            offset += 50

        # Phase 2: search for Daily Mix 1-6 and other personalized playlists
        if len(playlists) < 4:
            for query in ("Daily Mix", "Discover Weekly", "Release Radar"):
                try:
                    res = self._sp.search(q=query, type="playlist", limit=6)
                    for p in res.get("playlists", {}).get("items", []):
                        if not p:
                            continue
                        owner_id = p.get("owner", {}).get("id", "")
                        if owner_id == "spotify":
                            _add(p)
                except Exception:
                    pass

        return playlists[:12]

    def recently_played_albums(self, limit: int = 8) -> list[Album]:
        """Unique albums from the user's recently played history."""
        result = self._sp.current_user_recently_played(limit=50)
        seen: set[str] = set()
        albums: list[Album] = []
        for item in result.get("items", []):
            t = item.get("track")
            if not t:
                continue
            alb = t.get("album", {})
            album_id = alb.get("id")
            if not album_id or album_id in seen:
                continue
            seen.add(album_id)
            artists = ", ".join(a["name"] for a in alb.get("artists", []))
            albums.append(Album(
                id=album_id,
                name=alb.get("name", ""),
                artist=artists,
                total=alb.get("total_tracks", 0),
            ))
            if len(albums) >= limit:
                break
        return albums

    def home_recommendations(self, limit: int = 15) -> list[Track]:
        """Recommended tracks seeded from recently played or top tracks."""
        # Prefer recently played as seeds (most reliable)
        seed_ids: list[str] = []
        try:
            recent = self._sp.current_user_recently_played(limit=10)
            seen: set[str] = set()
            for item in recent.get("items", []):
                t = item.get("track")
                if t and t.get("id") and t["id"] not in seen:
                    seen.add(t["id"])
                    seed_ids.append(t["id"])
                    if len(seed_ids) == 5:
                        break
        except Exception:
            pass

        # Fall back to top tracks
        if not seed_ids:
            for time_range in ("short_term", "medium_term", "long_term"):
                try:
                    top = self._sp.current_user_top_tracks(limit=5, time_range=time_range)
                    seed_ids = [t["id"] for t in top.get("items", [])[:5]]
                    if seed_ids:
                        break
                except Exception:
                    continue

        if not seed_ids:
            return []

        def _parse(items: list) -> list[Track]:
            out: list[Track] = []
            for item in items:
                if not item:
                    continue
                artists = ", ".join(a["name"] for a in item.get("artists", []))
                images = item.get("album", {}).get("images", [])
                cover = images[0]["url"] if images else None
                out.append(Track(
                    id=item["id"],
                    name=item["name"],
                    artist=artists,
                    album=item.get("album", {}).get("name", ""),
                    duration_ms=item.get("duration_ms", 0),
                    cover_url=cover,
                ))
            return out

        try:
            recs = self._sp.recommendations(seed_tracks=seed_ids[:5], limit=limit)
            tracks = _parse(recs.get("tracks", []))
            if tracks:
                return tracks
        except Exception:
            pass

        return self._similar_tracks(seed_ids[0], limit=limit)

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
