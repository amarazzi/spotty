"""Top Tracks / Top Artists modal — t to open."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView

from spotty.api import ArtistResult, SpotifyAPI, Track
from spotty import themes as _themes

_VIEWS = ("tracks", "artists")
_RANGES = ("short_term", "medium_term", "long_term")
_RANGE_LABELS = {"short_term": "4 wk", "medium_term": "6 mo", "long_term": "all time"}


class TopOverlay(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("tab", "toggle_view", "", show=False),
        Binding("r", "toggle_range", "", show=False),
        Binding("j", "cursor_down", "", show=False),
        Binding("k", "cursor_up", "", show=False),
    ]

    def __init__(self, api: SpotifyAPI, **kwargs) -> None:
        super().__init__(**kwargs)
        self.api = api
        self._view = "tracks"
        self._range = "medium_term"
        self._results: list[Track | ArtistResult] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Label(" Top", id="modal-title")
            yield Label(self._hint_text(), id="modal-hint")
            yield ListView(id="home-list")

    def on_mount(self) -> None:
        self._load()

    def _hint_text(self) -> str:
        p = _themes.primary()
        def _v(name: str) -> str:
            return f"[bold {p}]{name}[/bold {p}]" if name == self._view else f"[dim]{name}[/dim]"

        def _r(key: str) -> str:
            return f"[bold {p}]{_RANGE_LABELS[key]}[/bold {p}]" if key == self._range else f"[dim]{_RANGE_LABELS[key]}[/dim]"

        views = "  ".join(_v(v) for v in _VIEWS)
        ranges = "  ".join(_r(r) for r in _RANGES)
        return f"{views}  [dim]·[/dim]  {ranges}  [dim]· Tab · r[/dim]"

    def action_toggle_view(self) -> None:
        self._view = _VIEWS[(_VIEWS.index(self._view) + 1) % len(_VIEWS)]
        self.query_one("#modal-hint", Label).update(self._hint_text())
        self._load()

    def action_toggle_range(self) -> None:
        self._range = _RANGES[(_RANGES.index(self._range) + 1) % len(_RANGES)]
        self.query_one("#modal-hint", Label).update(self._hint_text())
        self._load()

    def action_cursor_down(self) -> None:
        self.query_one(ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(ListView).action_cursor_up()

    @work(thread=True, exclusive=True, name="top-load")
    def _load(self) -> None:
        self.app.call_from_thread(
            self.query_one("#modal-hint", Label).update,
            "[dim]Loading…[/dim]",
        )
        try:
            if self._view == "tracks":
                results: list[Track | ArtistResult] = self.api.top_tracks(time_range=self._range)
            else:
                results = self.api.top_artists(time_range=self._range)
        except Exception as e:
            self.app.call_from_thread(
                self.query_one("#modal-hint", Label).update,
                f"[red]{e}[/red]",
            )
            return
        self._results = results
        self.app.call_from_thread(self._populate, results)

    def _populate(self, results: list[Track | ArtistResult]) -> None:
        lv = self.query_one(ListView)
        lv.clear()
        if not results:
            self.query_one("#modal-hint", Label).update("[dim]No data available[/dim]")
            return
        self.query_one("#modal-hint", Label).update(self._hint_text())
        for i, item in enumerate(results, 1):
            if isinstance(item, Track):
                d = item.duration_ms // 1000
                lv.append(ListItem(Label(
                    f"[dim]{i:2}[/dim]  [bold]{item.name}[/bold]"
                    f"  [dim]· {item.artist}  {d // 60}:{d % 60:02d}[/dim]"
                )))
            else:
                p2 = _themes.primary()
                genres = "  ".join(f"[{p2}]{g}[/]" for g in item.genres[:2]) if item.genres else ""
                lv.append(ListItem(Label(
                    f"[dim]{i:2}[/dim]  [bold]{item.name}[/bold]"
                    + (f"  [dim]{genres}[/dim]" if genres else "")
                )))
        lv.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self.query_one(ListView).index
        if idx is not None and 0 <= idx < len(self._results):
            self.dismiss(self._results[idx])
        else:
            self.dismiss(None)
