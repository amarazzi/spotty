"""Persist the last-played track to disk for instant startup display."""

from __future__ import annotations

import json
from pathlib import Path

from spotty.api import Track

_CACHE_FILE = Path.home() / ".cache" / "spotty" / "last_track.json"


def save(track: Track) -> None:
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps({
            "id": track.id,
            "name": track.name,
            "artist": track.artist,
            "album": track.album,
            "duration_ms": track.duration_ms,
            "cover_url": track.cover_url,
            "artist_id": track.artist_id,
            "album_id": track.album_id,
        }))
    except Exception:
        pass


def load() -> Track | None:
    try:
        data = json.loads(_CACHE_FILE.read_text())
        return Track(
            id=data["id"],
            name=data["name"],
            artist=data["artist"],
            album=data["album"],
            duration_ms=data["duration_ms"],
            cover_url=data.get("cover_url"),
            artist_id=data.get("artist_id"),
            album_id=data.get("album_id"),
            is_playing=False,
            progress_ms=0,
        )
    except Exception:
        return None
