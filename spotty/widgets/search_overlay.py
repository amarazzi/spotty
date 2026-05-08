"""Search modal — / to open, Esc to close, Tab to toggle tracks/albums."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, ListItem, ListView

from spotty.api import Album, SpotifyAPI, Track


class SearchOverlay(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("tab", "toggle_mode", "Albums/Tracks", show=False),
        Binding("j", "cursor_down", "", show=False),
        Binding("k", "cursor_up", "", show=False),
    ]

    def __init__(self, api: SpotifyAPI, **kwargs) -> None:
        super().__init__(**kwargs)
        self.api = api
        self._results: list[Track | Album] = []
        self._mode = "tracks"

    def compose(self) -> ComposeResult:
        with Vertical(id="search-container"):
            yield Label(" Search Spotify", id="search-title")
            yield Input(placeholder="Artist, track, album…", id="search-input")
            yield Label(self._hint_text(), id="search-hint")
            yield ListView(id="search-results")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def _hint_text(self) -> str:
        mode_label = "[bold #1DB954]tracks[/bold #1DB954]  [dim]albums[/dim]" if self._mode == "tracks" \
            else "[dim]tracks[/dim]  [bold #1DB954]albums[/bold #1DB954]"
        return f"[dim]Tab to switch ·[/dim]  {mode_label}  [dim]· Enter to search[/dim]"

    def action_toggle_mode(self) -> None:
        self._mode = "albums" if self._mode == "tracks" else "tracks"
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

    @work(thread=True, exclusive=True, name="search")
    def _search(self, query: str) -> None:
        try:
            if self._mode == "tracks":
                results: list[Track | Album] = self.api.search_tracks(query, limit=20)
            else:
                results = self.api.search_albums(query, limit=15)
        except Exception:
            self.app.call_from_thread(
                self.query_one("#search-hint", Label).update,
                "[red]Search failed — check connection[/red]",
            )
            return
        self._results = results
        self.app.call_from_thread(self._populate, results)

    def _populate(self, results: list[Track | Album]) -> None:
        lv = self.query_one(ListView)
        lv.clear()
        if not results:
            self.query_one("#search-hint", Label).update("[dim]No results[/dim]")
            return
        self.query_one("#search-hint", Label).update(self._hint_text())
        for item in results:
            if isinstance(item, Track):
                d = item.duration_ms // 1000
                lv.append(ListItem(Label(
                    f"[#1DB954]♪[/#1DB954]  [bold]{item.name}[/bold]"
                    f"  [dim]· {item.artist}  {d // 60}:{d % 60:02d}[/dim]"
                )))
            else:
                lv.append(ListItem(Label(
                    f"[#1DB954]▣[/#1DB954]  [bold]{item.name}[/bold]"
                    f"  [dim]· {item.artist}  {item.total} tracks[/dim]"
                )))
        lv.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        lv = self.query_one(ListView)
        idx = lv.index
        if idx is not None and 0 <= idx < len(self._results):
            self.dismiss(self._results[idx])
        else:
            self.dismiss(None)
