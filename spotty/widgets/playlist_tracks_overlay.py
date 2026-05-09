"""Playlist tracklist modal — shown when selecting a playlist."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView

from spotty.api import Playlist, SpotifyAPI, Track
from spotty.messages import AddToQueue


class PlaylistTracksOverlay(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("j", "cursor_down", "", show=False),
        Binding("k", "cursor_up", "", show=False),
        Binding("a", "add_to_queue", "", show=False),
    ]

    def __init__(self, api: SpotifyAPI, playlist: Playlist, **kwargs) -> None:
        super().__init__(**kwargs)
        self.api = api
        self.playlist = playlist
        self._tracks: list[Track] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Label(f" {self.playlist.name}", id="modal-title")
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

    @work(thread=True, exclusive=True, name="playlist-tracks")
    def _load(self) -> None:
        try:
            tracks = self.api.playlist_tracks(self.playlist.id)
        except Exception as e:
            self.app.call_from_thread(
                self.query_one("#modal-hint", Label).update,
                f"[red]{e}[/red]",
            )
            return
        self._tracks = tracks
        self.app.call_from_thread(self._populate, tracks)

    def _populate(self, tracks: list[Track]) -> None:
        lv = self.query_one(ListView)
        lv.clear()
        if not tracks:
            self.query_one("#modal-hint", Label).update("[dim]No tracks found[/dim]")
            return
        self.query_one("#modal-hint", Label).update(
            f"[dim]{len(tracks)} tracks — Enter to play from here  ·  a to queue[/dim]"
        )
        for i, t in enumerate(tracks, 1):
            d = t.duration_ms // 1000
            lv.append(ListItem(Label(
                f"[dim]{i:2}[/dim]  [bold]{t.name}[/bold]"
                f"  [dim]· {t.artist}  {d // 60}:{d % 60:02d}[/dim]"
            )))
        lv.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self.query_one(ListView).index
        if idx is not None and 0 <= idx < len(self._tracks):
            self.dismiss((self.playlist, idx))
        else:
            self.dismiss(None)
