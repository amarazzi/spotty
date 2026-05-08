"""Full-screen now-playing view with best-available image rendering."""

from __future__ import annotations

import time as _time
from io import BytesIO

import httpx
from PIL import Image as PILImage
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Label, Static

from spotty.api import Track

# Try the best image renderer available, fall back gracefully.
try:
    from textual_image.widget import AutoImage as _AutoImage
    _IMAGE_BACKEND = "textual-image"
except Exception:
    _AutoImage = None
    _IMAGE_BACKEND = "rich-pixels"

try:
    from rich_pixels import Pixels as _Pixels
except Exception:
    _Pixels = None

_ART_PX = 256


def _fetch_pil(url: str) -> PILImage.Image:
    data = httpx.get(url, timeout=8).content
    img = PILImage.open(BytesIO(data)).convert("RGB")
    return img.resize((_ART_PX, _ART_PX), PILImage.LANCZOS)


def _render_bar(width: int, pct: int) -> str:
    """Draw ━━━━●━━━━ style bar with a white cursor at current position."""
    if width <= 0:
        return ""
    pct = max(0, min(100, pct))
    filled = int(width * pct / 100)
    if pct == 0:
        return f"[#2D2D2D]{'━' * width}[/]"
    if filled >= width:
        return f"[#1DB954]{'━' * width}[/]"
    remaining = width - filled - 1
    return (
        f"[#1DB954]{'━' * filled}[/]"
        f"[bold white]●[/]"
        f"[#2D2D2D]{'━' * remaining}[/]"
    )


class NowPlaying(Widget):

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._last_cover: str | None = None
        self._progress_ms: int = 0
        self._progress_ref: float = _time.monotonic()
        self._is_playing: bool = False
        self._duration_ms: int = 0
        self._art_widget_id = "np-art-img" if _IMAGE_BACKEND == "textual-image" else "np-art-static"

    def compose(self) -> ComposeResult:
        with Horizontal(id="np-art-row"):
            if _IMAGE_BACKEND == "textual-image" and _AutoImage is not None:
                yield _AutoImage(None, id=self._art_widget_id, classes="np-art")
            else:
                yield Static("", id=self._art_widget_id, classes="np-art")

        yield Label("[dim]Nothing playing[/dim]", id="np-name")
        yield Label("", id="np-artist")
        yield Label("", id="np-album")
        yield Static("", id="np-bar")
        yield Label("", id="np-time")
        yield Label(
            "[dim]  /  search    l  playlists    r  recent"
            "    space  ▶⏸    n  →    p  ←[/dim]",
            id="np-hints",
        )

    def on_mount(self) -> None:
        self.set_interval(1, self._tick)
        self.call_after_refresh(self._tick)

    # ------------------------------------------------------------------
    # Progress tick
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        bar = self.query_one("#np-bar", Static)
        w = bar.size.width
        time_lbl = self.query_one("#np-time", Label)

        if self._duration_ms == 0:
            if w:
                bar.update(_render_bar(w, 0))
            return

        if not self._is_playing:
            # Paused: show static position without advancing
            pct = int(self._progress_ms / self._duration_ms * 100)
            if w:
                bar.update(_render_bar(w, pct))
            e = self._progress_ms // 1000
            t = self._duration_ms // 1000
            time_lbl.update(f"[dim]{e // 60}:{e % 60:02d}  ·  {t // 60}:{t % 60:02d}[/dim]")
            return

        elapsed = (_time.monotonic() - self._progress_ref) * 1000
        current_ms = min(int(self._progress_ms + elapsed), self._duration_ms)
        pct = int(current_ms / self._duration_ms * 100)

        if w:
            bar.update(_render_bar(w, pct))

        e = current_ms // 1000
        t = self._duration_ms // 1000
        time_lbl.update(f"[dim]{e // 60}:{e % 60:02d}  ·  {t // 60}:{t % 60:02d}[/dim]")

    # ------------------------------------------------------------------
    # Track update
    # ------------------------------------------------------------------

    def update_track(self, track: Track | None) -> None:
        name_lbl = self.query_one("#np-name", Label)
        artist_lbl = self.query_one("#np-artist", Label)
        album_lbl = self.query_one("#np-album", Label)

        if track is None:
            name_lbl.update("[dim]Nothing playing[/dim]")
            artist_lbl.update("")
            album_lbl.update("")
            self._is_playing = False
            return

        self._progress_ms = track.progress_ms
        self._progress_ref = _time.monotonic()
        self._is_playing = track.is_playing
        self._duration_ms = track.duration_ms

        icon = "▶" if track.is_playing else "⏸"
        name_lbl.update(f"[bold]{icon}  {track.name}[/bold]")
        artist_lbl.update(f"[green]{track.artist}[/green]")
        album_lbl.update(f"[dim]{track.album}[/dim]")

        if track.cover_url and track.cover_url != self._last_cover:
            self._last_cover = track.cover_url
            self._load_art(track.cover_url)

    # ------------------------------------------------------------------
    # Art loading
    # ------------------------------------------------------------------

    @work(thread=True, exclusive=True, name="art")
    def _load_art(self, url: str) -> None:
        try:
            img = _fetch_pil(url)
        except Exception:
            return

        if _IMAGE_BACKEND == "textual-image" and _AutoImage is not None:
            self.app.call_from_thread(self._set_art_textual, img)
        elif _Pixels is not None:
            pixels = _Pixels.from_image(img)
            self.app.call_from_thread(self._set_art_pixels, pixels)

    def _set_art_textual(self, img: PILImage.Image) -> None:
        try:
            widget = self.query_one(f"#{self._art_widget_id}", _AutoImage)
            widget.image = img
        except Exception:
            pass

    def _set_art_pixels(self, pixels) -> None:
        try:
            widget = self.query_one(f"#{self._art_widget_id}", Static)
            widget.update(pixels)
        except Exception:
            pass
