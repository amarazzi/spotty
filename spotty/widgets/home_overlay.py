"""Home / discovery modal — r to open.

Three sections:
  Made For You     — Daily Mixes, Discover Weekly, Release Radar (Spotify-curated)
  Jump Back In     — Recently played albums
  Recommended      — Tracks seeded from your recent listening
"""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView

from spotty.api import Album, Playlist, SpotifyAPI, Track
from spotty.messages import AddToQueue


class HomeOverlay(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("j", "cursor_down", "", show=False),
        Binding("k", "cursor_up", "", show=False),
        Binding("a", "add_to_queue", "", show=False),
    ]

    def __init__(self, api: SpotifyAPI, **kwargs) -> None:
        super().__init__(**kwargs)
        self.api = api
        self._items: list[Playlist | Album | Track | None] = []  # None = section header
        self._header_indices: set[int] = set()

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Label(" Discover", id="modal-title")
            yield Label("[dim]Loading…[/dim]", id="modal-hint")
            yield ListView(id="home-list")

    def on_mount(self) -> None:
        self._load()

    # ------------------------------------------------------------------
    # Navigation — skip section headers
    # ------------------------------------------------------------------

    def _move_cursor(self, delta: int) -> None:
        lv = self.query_one(ListView)
        idx = lv.index if lv.index is not None else (-1 if delta > 0 else len(self._items))
        new_idx = idx + delta
        while 0 <= new_idx < len(self._items) and new_idx in self._header_indices:
            new_idx += delta
        if 0 <= new_idx < len(self._items):
            lv.index = new_idx

    def action_cursor_down(self) -> None:
        self._move_cursor(1)

    def action_cursor_up(self) -> None:
        self._move_cursor(-1)

    def action_add_to_queue(self) -> None:
        lv = self.query_one(ListView)
        idx = lv.index
        if idx is not None and 0 <= idx < len(self._items):
            item = self._items[idx]
            if isinstance(item, Track):
                self.post_message(AddToQueue(item.id))

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    @work(thread=True, exclusive=True, name="home-discover")
    def _load(self) -> None:
        made_for_you: list[Playlist] = []
        jump_back: list[Album] = []
        recommended: list[Track] = []

        try:
            made_for_you = self.api.made_for_you()
        except Exception:
            pass

        try:
            jump_back = self.api.recently_played_albums()
        except Exception:
            pass

        try:
            recommended = self.api.home_recommendations()
        except Exception:
            pass

        self.app.call_from_thread(self._populate, made_for_you, jump_back, recommended)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _populate(
        self,
        made_for_you: list[Playlist],
        jump_back: list[Album],
        recommended: list[Track],
    ) -> None:
        lv = self.query_one(ListView)
        lv.clear()
        self._items = []
        self._header_indices = set()

        total = len(made_for_you) + len(jump_back) + len(recommended)
        if total == 0:
            self.query_one("#modal-hint", Label).update("[dim]Nothing to show[/dim]")
            return

        self.query_one("#modal-hint", Label).update(
            "[dim]Enter to play  ·  a to queue tracks  ·  j/k to navigate[/dim]"
        )

        def _header(title: str) -> None:
            idx = len(self._items)
            self._header_indices.add(idx)
            self._items.append(None)
            lv.append(ListItem(Label(f"[bold #1DB954]{title}[/bold #1DB954]")))

        def _playlist_row(p: Playlist) -> None:
            self._items.append(p)
            lv.append(ListItem(Label(
                f"[#606060]♪[/#606060]  [bold]{p.name}[/bold]"
                f"  [dim]{p.total} tracks[/dim]"
            )))

        def _album_row(a: Album) -> None:
            self._items.append(a)
            lv.append(ListItem(Label(
                f"[#606060]▣[/#606060]  [bold]{a.name}[/bold]"
                f"  [dim]{a.artist}[/dim]"
            )))

        def _track_row(t: Track) -> None:
            self._items.append(t)
            d = t.duration_ms // 1000
            lv.append(ListItem(Label(
                f"[#606060]♪[/#606060]  [bold]{t.name}[/bold]"
                f"  [dim]· {t.artist}  {d // 60}:{d % 60:02d}[/dim]"
            )))

        if made_for_you:
            _header("Made For You")
            for p in made_for_you:
                _playlist_row(p)

        if jump_back:
            _header("Jump Back In")
            for a in jump_back:
                _album_row(a)

        if recommended:
            _header("Recommended For You")
            for t in recommended:
                _track_row(t)

        # Focus first non-header item
        first = next((i for i in range(len(self._items)) if i not in self._header_indices), None)
        if first is not None:
            lv.index = first
        lv.focus()

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self.query_one(ListView).index
        if idx is None or idx in self._header_indices or idx >= len(self._items):
            return
        item = self._items[idx]
        if isinstance(item, Playlist):
            self.dismiss(("playlist", item))
        elif isinstance(item, Album):
            self.dismiss(("album", item))
        elif isinstance(item, Track):
            self.dismiss(("track", item))
        else:
            self.dismiss(None)
