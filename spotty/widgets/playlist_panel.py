"""Left panel: navigable playlist list."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Label, ListItem, ListView, Static


class PlaylistPanel(Static):
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    class Selected(Message):
        def __init__(self, playlist_id: str, name: str) -> None:
            super().__init__()
            self.playlist_id = playlist_id
            self.name = name

    def __init__(self, playlists: list, **kwargs) -> None:
        super().__init__(**kwargs)
        self._playlists = playlists

    def compose(self) -> ComposeResult:
        yield Label(" Playlists", id="playlist-title")
        items = [
            ListItem(Label(f" {p.name}"), id=f"pl-{p.id}")
            for p in self._playlists
        ]
        yield ListView(*items, id="playlist-list")

    def action_cursor_down(self) -> None:
        self.query_one(ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(ListView).action_cursor_up()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id or ""
        playlist_id = item_id.removeprefix("pl-")
        playlist = next((p for p in self._playlists if p.id == playlist_id), None)
        if playlist:
            self.post_message(self.Selected(playlist.id, playlist.name))

    def refresh_playlists(self, playlists: list) -> None:
        self._playlists = playlists
        lv = self.query_one(ListView)
        lv.clear()
        for p in playlists:
            lv.append(ListItem(Label(f" {p.name}"), id=f"pl-{p.id}"))
