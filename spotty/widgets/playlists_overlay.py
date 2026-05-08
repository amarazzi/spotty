"""Playlists modal — l to open, Esc to close."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView

from spotty.api import Playlist, SpotifyAPI


class PlaylistsOverlay(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("j", "cursor_down", "", show=False),
        Binding("k", "cursor_up", "", show=False),
    ]

    def __init__(self, api: SpotifyAPI, playlists: list[Playlist], **kwargs) -> None:
        super().__init__(**kwargs)
        self.api = api
        self._playlists = playlists

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Label(" Your playlists", id="modal-title")
            yield Label(
                f"[dim]{len(self._playlists)} playlists — Enter to play[/dim]",
                id="modal-hint",
            )
            yield ListView(id="playlist-list")

    def on_mount(self) -> None:
        lv = self.query_one(ListView)
        for p in self._playlists:
            lv.append(
                ListItem(Label(f"[bold]{p.name}[/bold]  [dim]{p.total} tracks[/dim]"))
            )
        lv.focus()

    def action_cursor_down(self) -> None:
        self.query_one(ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(ListView).action_cursor_up()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        lv = self.query_one(ListView)
        idx = lv.index
        if idx is not None and 0 <= idx < len(self._playlists):
            self.dismiss(self._playlists[idx])
        else:
            self.dismiss(None)
