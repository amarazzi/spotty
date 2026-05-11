"""Queue modal — u to open, shows upcoming tracks or recommendations."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView

from spotty.api import SpotifyAPI, Track
from spotty.messages import AddToQueue
from spotty import themes as _themes


class QueueOverlay(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("j", "cursor_down", "", show=False),
        Binding("k", "cursor_up", "", show=False),
        Binding("a", "add_to_queue", "", show=False),
    ]

    def __init__(self, api: SpotifyAPI, current_track_id: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.api = api
        self._current_track_id = current_track_id
        self._tracks: list[Track] = []
        self._is_recs: bool = False

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Label(" Up next", id="modal-title")
            yield Label("[dim]Loading…[/dim]", id="modal-hint")
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

    @work(thread=True, exclusive=True, name="queue")
    def _load(self) -> None:
        try:
            tracks, is_recs = self.api.get_queue(seed_track_id=self._current_track_id)
        except Exception as e:
            self.app.call_from_thread(
                self.query_one("#modal-hint", Label).update,
                f"[red]{e}[/red]",
            )
            return
        self._tracks = tracks
        self.app.call_from_thread(self._populate, tracks, is_recs)

    def _populate(self, tracks: list[Track], is_recs: bool) -> None:
        lv = self.query_one(ListView)
        lv.clear()
        if not tracks:
            self.query_one("#modal-hint", Label).update("[dim]Nothing upcoming[/dim]")
            return

        self._is_recs = is_recs
        if is_recs:
            self.query_one("#modal-title", Label).update(" Recommended")
            self.query_one("#modal-hint", Label).update(
                f"[dim]{len(tracks)} tracks based on what you're playing[/dim]"
            )
            icon = "[#505050]✦[/#505050]"
        else:
            self.query_one("#modal-hint", Label).update(
                f"[dim]{len(tracks)} tracks — Enter to play[/dim]"
            )
            icon = f"[{_themes.primary()}]♪[/{_themes.primary()}]"

        for t in tracks:
            d = t.duration_ms // 1000
            lv.append(ListItem(Label(
                f"{icon}  [bold]{t.name}[/bold]"
                f"  [dim]· {t.artist}  {d // 60}:{d % 60:02d}[/dim]"
            )))
        lv.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self.query_one(ListView).index
        if idx is not None and 0 <= idx < len(self._tracks):
            remaining = self._tracks[idx + 1:]
            self.dismiss((self._tracks[idx], remaining, self._is_recs))
        else:
            self.dismiss(None)
