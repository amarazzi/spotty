"""Search modal — / to open, Tab to cycle tracks / albums / playlists / artists."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, ListItem, ListView

from spotty.api import Album, ArtistResult, Playlist, SpotifyAPI, Track
from spotty.messages import AddToQueue
from spotty import themes as _themes

_MODES = ("tracks", "albums", "playlists", "artists")


class SearchOverlay(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("tab", "toggle_mode", "", show=False),
        Binding("j", "cursor_down", "", show=False),
        Binding("k", "cursor_up", "", show=False),
        Binding("a", "add_to_queue", "", show=False),
    ]

    def __init__(self, api: SpotifyAPI, **kwargs) -> None:
        super().__init__(**kwargs)
        self.api = api
        self._results: list[Track | Album | Playlist | ArtistResult] = []
        self._mode = "tracks"

    def compose(self) -> ComposeResult:
        with Vertical(id="search-container"):
            yield Label(" Search Spotify", id="search-title")
            yield Input(placeholder="Artist, track, album, playlist…", id="search-input")
            yield Label(self._hint_text(), id="search-hint")
            yield ListView(id="search-results")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def _hint_text(self) -> str:
        p = _themes.primary()
        def _tab(name: str) -> str:
            if name == self._mode:
                return f"[bold {p}]{name}[/bold {p}]"
            return f"[dim]{name}[/dim]"
        tabs = "  ".join(_tab(m) for m in _MODES)
        suffix = "[dim]· Enter · a to queue[/dim]" if self._mode != "artists" else "[dim]· Enter to browse[/dim]"
        return f"[dim]Tab ·[/dim]  {tabs}  {suffix}"

    def action_toggle_mode(self) -> None:
        idx = (_MODES.index(self._mode) + 1) % len(_MODES)
        self._mode = _MODES[idx]
        self.query_one("#search-hint", Label).update(self._hint_text())
        query = self.query_one(Input).value.strip()
        if query:
            self._search(query)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if query:
            self.query_one("#search-hint", Label).update("[dim]Searching…[/dim]")
            self._search(query)

    def action_cursor_down(self) -> None:
        lv = self.query_one(ListView)
        if lv.index is None and len(lv) > 0:
            lv.focus()
        lv.action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(ListView).action_cursor_up()

    def action_add_to_queue(self) -> None:
        lv = self.query_one(ListView)
        idx = lv.index
        if idx is not None and 0 <= idx < len(self._results):
            item = self._results[idx]
            if isinstance(item, Track):
                self.post_message(AddToQueue(item.id))

    @work(thread=True, exclusive=True, name="search")
    def _search(self, query: str) -> None:
        try:
            if self._mode == "tracks":
                results: list[Track | Album | Playlist | ArtistResult] = self.api.search_tracks(query, limit=20)
            elif self._mode == "albums":
                results = self.api.search_albums(query, limit=15)
            elif self._mode == "playlists":
                results = self.api.search_playlists(query, limit=15)
            else:
                results = self.api.search_artists(query, limit=15)
        except Exception:
            self.app.call_from_thread(
                self.query_one("#search-hint", Label).update,
                "[red]Search failed — check connection[/red]",
            )
            return
        self._results = results
        self.app.call_from_thread(self._populate, results)

    def _populate(self, results: list[Track | Album | Playlist | ArtistResult]) -> None:
        lv = self.query_one(ListView)
        lv.clear()
        if not results:
            self.query_one("#search-hint", Label).update("[dim]No results[/dim]")
            return
        self.query_one("#search-hint", Label).update(self._hint_text())
        p = _themes.primary()
        for item in results:
            if isinstance(item, Track):
                d = item.duration_ms // 1000
                lv.append(ListItem(Label(
                    f"[{p}]♪[/{p}]  [bold]{item.name}[/bold]"
                    f"  [dim]· {item.artist}  {d // 60}:{d % 60:02d}[/dim]"
                )))
            elif isinstance(item, Album):
                lv.append(ListItem(Label(
                    f"[{p}]▣[/{p}]  [bold]{item.name}[/bold]"
                    f"  [dim]· {item.artist}  {item.total} tracks[/dim]"
                )))
            elif isinstance(item, ArtistResult):
                genres = "  ".join(item.genres[:2]) if item.genres else ""
                lv.append(ListItem(Label(
                    f"[{p}]◉[/{p}]  [bold]{item.name}[/bold]"
                    + (f"  [dim]{genres}[/dim]" if genres else "")
                )))
            else:  # Playlist
                lv.append(ListItem(Label(
                    f"[{p}]≡[/{p}]  [bold]{item.name}[/bold]"
                    f"  [dim]{item.total} tracks[/dim]"
                )))
        lv.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self.query_one(ListView).index
        if idx is not None and 0 <= idx < len(self._results):
            self.dismiss(self._results[idx])
        else:
            self.dismiss(None)
