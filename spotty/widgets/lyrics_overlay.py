"""Lyrics modal — l to open, shows lyrics for the current track."""

from __future__ import annotations

import re

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Label


class LyricsOverlay(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("j", "scroll_down", "", show=False),
        Binding("k", "scroll_up", "", show=False),
    ]

    def __init__(self, track_name: str, artist: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._track_name = track_name
        self._artist = artist

    def compose(self) -> ComposeResult:
        with Vertical(id="lyrics-container"):
            yield Label(f" {self._track_name}", id="modal-title")
            yield Label(f"[dim]{self._artist}[/dim]", id="modal-hint")
            with VerticalScroll(id="lyrics-scroll"):
                yield Label("", id="lyrics-text")

    def on_mount(self) -> None:
        self._load()

    def action_scroll_down(self) -> None:
        self.query_one("#lyrics-scroll", VerticalScroll).scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one("#lyrics-scroll", VerticalScroll).scroll_up()

    @work(thread=True, exclusive=True, name="lyrics")
    def _load(self) -> None:
        try:
            import syncedlyrics
            text = syncedlyrics.search(f"{self._track_name} {self._artist}")
        except Exception as e:
            self.app.call_from_thread(
                self.query_one("#modal-hint", Label).update,
                f"[red]{e}[/red]",
            )
            return

        if not text:
            self.app.call_from_thread(
                self.query_one("#modal-hint", Label).update,
                "[dim]Lyrics not found[/dim]",
            )
            return

        self.app.call_from_thread(self._show_lyrics, text)

    def _show_lyrics(self, raw: str) -> None:
        lines = raw.splitlines()
        clean: list[str] = []
        for line in lines:
            # Strip LRC timestamps like [01:23.45]
            stripped = re.sub(r"^\[\d+:\d+\.\d+\]", "", line).strip()
            # Skip LRC metadata tags like [ar:Artist]
            if re.match(r"^\[.+:.+\]$", stripped):
                continue
            clean.append(stripped)

        self.query_one("#lyrics-text", Label).update("\n".join(clean).strip())
        self.query_one("#modal-hint", Label).update(
            f"[dim]{self._artist}  ·  j/k to scroll[/dim]"
        )
