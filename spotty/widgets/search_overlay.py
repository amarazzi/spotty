"""Search modal — / to open, Esc to close."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, ListItem, ListView

from spotty.api import SpotifyAPI, Track


class SearchOverlay(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("j", "cursor_down", "", show=False),
        Binding("k", "cursor_up", "", show=False),
    ]

    def __init__(self, api: SpotifyAPI, **kwargs) -> None:
        super().__init__(**kwargs)
        self.api = api
        self._results: list[Track] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="search-container"):
            yield Label(" Search Spotify", id="search-title")
            yield Input(placeholder="Artist, track, album…", id="search-input")
            yield Label("[dim]Type and press Enter[/dim]", id="search-hint")
            yield ListView(id="search-results")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

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
            results = self.api.search_tracks(query, limit=20)
        except Exception:
            self.app.call_from_thread(
                self.query_one("#search-hint", Label).update,
                "[red]Search failed — check connection[/red]",
            )
            return
        self._results = results
        self.app.call_from_thread(self._populate, results)

    def _populate(self, tracks: list[Track]) -> None:
        lv = self.query_one(ListView)
        lv.clear()
        if not tracks:
            self.query_one("#search-hint", Label).update("[dim]No results[/dim]")
            return
        self.query_one("#search-hint", Label).update(
            f"[dim]{len(tracks)} results — Enter to play[/dim]"
        )
        for t in tracks:
            d = t.duration_ms // 1000
            lv.append(
                ListItem(
                    Label(
                        f"[#1DB954]♪[/#1DB954]  [bold]{t.name}[/bold]"
                        f"  [dim]· {t.artist}  {d // 60}:{d % 60:02d}[/dim]"
                    )
                )
            )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        lv = self.query_one(ListView)
        idx = lv.index
        if idx is not None and 0 <= idx < len(self._results):
            self.dismiss(self._results[idx])
        else:
            self.dismiss(None)
