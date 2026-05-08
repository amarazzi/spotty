"""Home modal — r to open, shows recently played tracks."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView

from spotty.api import SpotifyAPI, Track


class HomeOverlay(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("j", "cursor_down", "", show=False),
        Binding("k", "cursor_up", "", show=False),
    ]

    def __init__(self, api: SpotifyAPI, **kwargs) -> None:
        super().__init__(**kwargs)
        self.api = api
        self._tracks: list[Track] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Label(" Recently played", id="modal-title")
            yield Label("[dim]Loading…[/dim]", id="modal-hint")
            yield ListView(id="home-list")

    def on_mount(self) -> None:
        self._load()

    def action_cursor_down(self) -> None:
        self.query_one(ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(ListView).action_cursor_up()

    @work(thread=True, exclusive=True, name="home")
    def _load(self) -> None:
        try:
            tracks = self.api.recently_played()
        except Exception:
            self.app.call_from_thread(
                self.query_one("#modal-hint", Label).update,
                "[red]Failed to load — check connection[/red]",
            )
            return
        self._tracks = tracks
        self.app.call_from_thread(self._populate, tracks)

    def _populate(self, tracks: list[Track]) -> None:
        lv = self.query_one(ListView)
        lv.clear()
        if not tracks:
            self.query_one("#modal-hint", Label).update("[dim]No history available[/dim]")
            return
        self.query_one("#modal-hint", Label).update(
            f"[dim]{len(tracks)} tracks — Enter to play[/dim]"
        )
        for t in tracks:
            d = t.duration_ms // 1000
            lv.append(
                ListItem(
                    Label(f"[bold]{t.name}[/bold]  [dim]{t.artist}  {d // 60}:{d % 60:02d}[/dim]")
                )
            )
        lv.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        lv = self.query_one(ListView)
        idx = lv.index
        if idx is not None and 0 <= idx < len(self._tracks):
            self.dismiss(self._tracks[idx])
        else:
            self.dismiss(None)
