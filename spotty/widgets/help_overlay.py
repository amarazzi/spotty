"""Help modal — ? to open, shows all keybindings."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Label

_SECTIONS = [
    ("Playback", [
        ("space",   "play / pause"),
        ("n",       "next track"),
        ("p",       "previous track"),
        ("[ ]",     "seek ±10s"),
        ("+ -",     "volume ±5%"),
        ("s",       "shuffle on/off"),
        ("x",       "repeat  off → all → one"),
        ("h",       "like / unlike current track"),
    ]),
    ("Browse", [
        ("/",       "search tracks & albums"),
        ("o",       "playlists"),
        ("f",       "liked songs"),
        ("r",       "recently played"),
        ("u",       "queue / recommendations"),
        ("l",       "lyrics  (synced if available)"),
        ("i",       "artist info + top tracks"),
        ("d",       "devices  (Spotify Connect)"),
    ]),
    ("Inside any overlay", [
        ("Enter",   "play"),
        ("a",       "add to queue"),
        ("j / k",   "navigate up / down"),
        ("Esc",     "close"),
    ]),
    ("General", [
        ("q",       "quit"),
        ("?",       "this help"),
    ]),
]


class HelpOverlay(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("question_mark", "dismiss", "Close", show=False),
        Binding("j", "scroll_down", "", show=False),
        Binding("k", "scroll_up", "", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Label(" Key bindings", id="modal-title")
            yield Label("[dim]Esc to close[/dim]", id="modal-hint")
            with VerticalScroll(id="lyrics-scroll"):
                lines: list[str] = []
                for section, keys in _SECTIONS:
                    lines.append(f"\n[bold #1DB954]{section}[/bold #1DB954]")
                    for key, desc in keys:
                        lines.append(
                            f"  [bold white]{key:<10}[/bold white]  [dim]{desc}[/dim]"
                        )
                yield Label("\n".join(lines).strip(), id="lyrics-text")

    def action_scroll_down(self) -> None:
        self.query_one(VerticalScroll).scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one(VerticalScroll).scroll_up()
