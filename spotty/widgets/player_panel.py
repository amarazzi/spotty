"""Center panel: ASCII art cover, track info, track list."""

from __future__ import annotations

import httpx
from PIL import Image
from io import BytesIO
from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import DataTable, Label, Static


ASCII_CHARS = " .,:;i1tfLCG08@"
ASCII_WIDTH = 40
ASCII_HEIGHT = 20


def _image_to_ascii(url: str) -> str:
    try:
        response = httpx.get(url, timeout=5)
        img = Image.open(BytesIO(response.content)).convert("L")
        img = img.resize((ASCII_WIDTH, ASCII_HEIGHT))
        pixels = img.getdata()
        chars = [ASCII_CHARS[int(p / 256 * len(ASCII_CHARS))] for p in pixels]
        lines = ["".join(chars[i : i + ASCII_WIDTH]) for i in range(0, len(chars), ASCII_WIDTH)]
        return "\n".join(lines)
    except Exception:
        return "\n".join([" " * ASCII_WIDTH] * ASCII_HEIGHT)


class PlayerPanel(Static):
    class TrackSelected(Message):
        def __init__(self, track_id: str) -> None:
            super().__init__()
            self.track_id = track_id

    def compose(self) -> ComposeResult:
        yield Label("", id="ascii-art")
        yield Label("", id="track-name")
        yield Label("", id="track-artist")
        yield Label("", id="track-album")
        yield DataTable(id="track-list", show_header=True, cursor_type="row")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("#", "Title", "Artist", "Duration")

    def update_now_playing(self, track) -> None:
        if track is None:
            self.query_one("#track-name", Label).update("[dim]Nothing playing[/dim]")
            self.query_one("#track-artist", Label).update("")
            self.query_one("#track-album", Label).update("")
            self.query_one("#ascii-art", Label).update("")
            return

        state = "▶" if track.is_playing else "⏸"
        self.query_one("#track-name", Label).update(
            f"[bold green]{state}  {track.name}[/bold green]"
        )
        self.query_one("#track-artist", Label).update(f"[cyan]   {track.artist}[/cyan]")
        self.query_one("#track-album", Label).update(f"[dim]   {track.album}[/dim]")

        if track.cover_url:
            self.run_worker(
                self._load_ascii(track.cover_url), exclusive=True, thread=True
            )

    async def _load_ascii(self, url: str) -> None:
        import asyncio
        loop = asyncio.get_event_loop()
        art = await loop.run_in_executor(None, _image_to_ascii, url)
        self.query_one("#ascii-art", Label).update(f"[dim]{art}[/dim]")

    def load_tracks(self, tracks: list) -> None:
        table = self.query_one(DataTable)
        table.clear()
        self._tracks = tracks
        for i, t in enumerate(tracks, 1):
            mins, secs = divmod(t.duration_ms // 1000, 60)
            table.add_row(str(i), t.name, t.artist, f"{mins}:{secs:02d}", key=t.id)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value:
            self.post_message(self.TrackSelected(event.row_key.value))
