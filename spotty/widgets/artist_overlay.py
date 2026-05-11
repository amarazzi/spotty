"""Artist modal — i to open, shows photo, bio, and top tracks."""

from __future__ import annotations

import re
import urllib.parse
from io import BytesIO

import httpx
from PIL import Image as PILImage
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView, Static

from spotty.api import ArtistInfo, SpotifyAPI, Track
from spotty.messages import AddToQueue
from spotty import themes as _themes

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


def _fetch_wiki_bio(artist_name: str) -> str:
    encoded = urllib.parse.quote(artist_name)
    for lang in ("en", "es", "pt", "fr", "de"):
        try:
            resp = httpx.get(
                f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{encoded}",
                timeout=5,
                headers={"User-Agent": "spotty/1.0 (music player)"},
            )
            if resp.status_code == 200:
                extract = resp.json().get("extract", "")
                if extract:
                    sentences = re.split(r"(?<=[.!?])\s+", extract)
                    bio = " ".join(sentences[:2])
                    if len(bio) > 240:
                        bio = bio[:237] + "…"
                    return bio
        except Exception:
            pass
    return ""


def _pop_bar(popularity: int) -> str:
    filled = popularity // 10
    empty = 10 - filled
    p = _themes.primary()
    return f"[{p}]{'█' * filled}[/][#383838]{'░' * empty}[/]"


class ArtistOverlay(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("j", "cursor_down", "", show=False),
        Binding("k", "cursor_up", "", show=False),
        Binding("a", "add_to_queue", "", show=False),
    ]

    def __init__(self, api: SpotifyAPI, artist_id: str, artist_name: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.api = api
        self._artist_id = artist_id
        self._artist_name = artist_name
        self._tracks: list[Track] = []
        self._art_id = "artist-img" if _IMAGE_BACKEND == "textual-image" else "artist-static"

    def compose(self) -> ComposeResult:
        with Vertical(id="artist-container"):
            yield Label(f" {self._artist_name}", id="modal-title")
            yield Label("[dim]Loading…[/dim]", id="modal-hint")
            with Horizontal(id="artist-top"):
                if _IMAGE_BACKEND == "textual-image" and _AutoImage is not None:
                    yield _AutoImage(None, id=self._art_id, classes="artist-art")
                else:
                    yield Static("", id=self._art_id, classes="artist-art")
                with Vertical(id="artist-info"):
                    yield Label("", id="artist-genres")
                    yield Label("", id="artist-bio")
                    yield Label("", id="artist-stats")
            yield Static("", id="artist-sep")
            yield ListView(id="home-list")

    def on_mount(self) -> None:
        self._load()

    def action_cursor_down(self) -> None:
        self.query_one(ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(ListView).action_cursor_up()

    def action_add_to_queue(self) -> None:
        idx = self.query_one(ListView).index
        if idx is not None and 0 <= idx < len(self._tracks):
            self.post_message(AddToQueue(self._tracks[idx].id))

    @work(thread=True, exclusive=True, name="artist-full")
    def _load(self) -> None:
        try:
            info = self.api.get_artist_full(self._artist_id)
        except Exception as e:
            self.app.call_from_thread(
                self.query_one("#modal-hint", Label).update,
                f"[red]{e}[/red]",
            )
            return
        bio = _fetch_wiki_bio(info.name)
        self._tracks = info.top_tracks
        self.app.call_from_thread(self._populate, info, bio)

    def _populate(self, info: ArtistInfo, bio: str) -> None:
        self.query_one("#modal-hint", Label).update(
            "[dim]Enter to play  ·  a to queue[/dim]"
        )

        p = _themes.primary()
        genres = "  ".join(
            f"[bold {p}]{g}[/]" for g in info.genres
        ) if info.genres else "[dim]—[/dim]"
        self.query_one("#artist-genres", Label).update(genres)

        self.query_one("#artist-bio", Label).update(
            f"[#909090]{bio}[/]" if bio else "[dim]No description available[/dim]"
        )

        followers = f"{info.followers:,}" if info.followers else "—"
        self.query_one("#artist-stats", Label).update(
            f"[dim]{followers} followers[/dim]"
        )

        width = self.query_one("#artist-container").content_size.width or 76
        self.query_one("#artist-sep", Static).update(
            "[#282828]" + "─" * max(1, width - 1) + "[/]"
        )

        if info.image_url:
            self._load_art(info.image_url)

        lv = self.query_one(ListView)
        lv.clear()
        for i, t in enumerate(info.top_tracks, 1):
            d = t.duration_ms // 1000
            lv.append(ListItem(Label(
                f"[dim]{i:2}[/dim]  [bold]{t.name}[/bold]"
                f"  [dim]· {t.album}  {d // 60}:{d % 60:02d}[/dim]"
            )))
        lv.focus()

    @work(thread=True, exclusive=True, name="artist-art")
    def _load_art(self, url: str) -> None:
        try:
            data = httpx.get(url, timeout=8).content
            img = PILImage.open(BytesIO(data)).convert("RGB").resize((192, 192), PILImage.LANCZOS)
        except Exception:
            return
        if _IMAGE_BACKEND == "textual-image" and _AutoImage is not None:
            self.app.call_from_thread(self._set_art_textual, img)
        elif _Pixels is not None:
            pixels = _Pixels.from_image(img)
            self.app.call_from_thread(self._set_art_pixels, pixels)

    def _set_art_textual(self, img: PILImage.Image) -> None:
        try:
            self.query_one(f"#{self._art_id}", _AutoImage).image = img
        except Exception:
            pass

    def _set_art_pixels(self, pixels) -> None:
        try:
            self.query_one(f"#{self._art_id}", Static).update(pixels)
        except Exception:
            pass

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self.query_one(ListView).index
        if idx is not None and 0 <= idx < len(self._tracks):
            self.dismiss(self._tracks[idx])
        else:
            self.dismiss(None)
